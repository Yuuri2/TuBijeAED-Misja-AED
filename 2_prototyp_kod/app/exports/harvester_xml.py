"""Eksport metadanych w formacie importu XML dane.gov.pl, schemat 1.13 i 1.14 (pakiet dostawcy). Właściciel: API.

Zgodność sprawdzana testem z oficjalnym XSD (tests/fixtures/xml_import_otwarte_dane_1_13.xsd):
  * XSD ma elementFormDefault="unqualified": przestrzeń nazw `urn:otwarte-dane:harvester:1.13`
    ma TYLKO element główny (z prefiksem), elementy potomne są bez przestrzeni nazw.
    Domyślny xmlns (jak w starym prototypie) wciągałby do niej dzieci i XML nie przechodził walidacji.
  * URL zasobu musi pasować do wzorca `https://.*` – dlatego adres http:// zamieniamy na https://.
  * Licencja: tylko CC0 1.0 / CC BY* (ODbL nie istnieje w słowniku), stąd dane OSM są wyłączone.
"""
from __future__ import annotations

from datetime import datetime, timezone

from lxml import etree

from .kolumny import do_publikacji

NS = "urn:otwarte-dane:harvester:1.13"
EXT_ID = "tubijeaed-rejestr-aed"          # maks. 36 znaków (XSD)
LICENCJA = "CC BY 4.0"
TAGI = ["AED", "defibrylator", "pierwsza pomoc", "ratownictwo", "NZK", "zdrowie", "#TuBijeAED"]
MAKS_REGIONOW = 20                         # XSD: regions/terytIdent maxOccurs=20


def adres_https(base_url: str) -> str:
    """XSD wymaga https:// w adresach zasobów. Dla http://localhost w demie zamieniamy schemat –
    w produkcji BASE_URL powinien i tak wskazywać publiczny adres https."""
    b = (base_url or "").strip().rstrip("/")
    if b.startswith("http://"):
        b = "https://" + b[len("http://"):]
    elif not b.startswith("https://"):
        b = "https://" + b
    return b


def _tekst(rodzic, nazwa: str, wartosc: str, **atrybuty):
    el = etree.SubElement(rodzic, nazwa, **atrybuty)
    el.text = wartosc
    return el


def _dwujezyczny(rodzic, nazwa: str, pl: str, en: str | None = None):
    el = etree.SubElement(rodzic, nazwa)
    _tekst(el, "polish", pl)
    if en:
        _tekst(el, "english", en)
    return el


def _flagi(rodzic, chronione: bool | None = None):
    """Flagi wartości danych – ustawione świadomie:

    * hasDynamicData=false – rejestr aktualizowany raz na dobę, to nie są dane „dynamiczne”
      (strumień w czasie rzeczywistym, np. położenie pojazdów);
    * hasHighValueData=false – AED nie figuruje w krajowym wykazie danych o wysokiej wartości;
    * hasHighValueDataFromEuropeanCommissionList=false – rozporządzenie wykonawcze KE 2023/138
      obejmuje 6 kategorii (geoprzestrzenne, obserwacja Ziemi i środowisko, meteorologiczne,
      statystyczne, przedsiębiorstwa, mobilność) – rejestr AED do nich nie należy;
    * hasResearchData=false – to dane administracyjne, nie wyniki badań naukowych;
    * containsProtectedData=false – brak danych osobowych (kontakty wyłącznie funkcyjne).
    """
    for nazwa in ("hasDynamicData", "hasHighValueData", "hasHighValueDataFromEuropeanCommissionList",
                  "hasResearchData"):
        _tekst(rodzic, nazwa, "false")
    if chronione is not None:
        _tekst(rodzic, "containsProtectedData", "true" if chronione else "false")


def kody_teryt(rekordy: list[dict]) -> list[str]:
    """Unikalne kody TERC gmin (7 cyfr); gdy > 20 – zwijamy do województw (2 cyfry)."""
    gminy = sorted({r["teryt_gmina"] for r in rekordy
                    if isinstance(r.get("teryt_gmina"), str) and len(r["teryt_gmina"]) == 7
                    and r["teryt_gmina"].isdigit()})
    if len(gminy) <= MAKS_REGIONOW:
        return gminy
    return sorted({g[:2] for g in gminy})[:MAKS_REGIONOW]


def _xsd_datetime(s: str | None) -> str | None:
    """'2024-02-19T17:32:25Z' -> poprawny xs:dateTime (albo None)."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =========================================================================================== XML 1.14 (Sprint 2)
# Pakiet dostawcy: JEDEN zbiór dostawcy z JEDNYM zasobem AED oznaczonym <aggregatedListType>AED</aggregatedListType>.
# Odpowiednik w mcod: zasób z <containsProtectedData>true</containsProtectedData> w pliku 1.13 (wykaz DGA).
# Dostawca publikuje ten plik u siebie i podpina jako źródło harvestera na swoim koncie w dane.gov.pl –
# portal pobiera zasób, waliduje go wzorcem i scala do Wykazu zbiorczego AED.

NS_114 = "urn:otwarte-dane:harvester:1.14"
NAMESPACES = {"1.13": NS, "1.14": NS_114}
MAKS_EXT_ID = 36


def ext_ident(*czesci: str) -> str:
    """Bezpieczny extIdent (maks. 36 znaków, [a-z0-9-])."""
    import re
    import unicodedata

    s = "-".join(c for c in czesci if c)
    s = unicodedata.normalize("NFKD", s.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return (s[:MAKS_EXT_ID].rstrip("-")) or "aed"


def zbuduj_xml_dostawcy(
    *,
    nazwa_dostawcy: str,
    url_zasobu: str,
    rekordy: list[dict] | None = None,
    licencja: str = LICENCJA,
    ext_ident_zbioru: str | None = None,
    ext_ident_zasobu: str | None = None,
    czestotliwosc: str = "monthly",
    wersja: str = "1.14",
    teraz: datetime | None = None,
) -> bytes:
    """Plik harvestera dla JEDNEGO dostawcy: zbiór „Defibrylatory AED – <dostawca>” z zasobem AED.

    `rekordy` (wiersze wzorca) służą tylko do wyliczenia regionów TERYT i daty aktualizacji.
    wersja="1.13" daje plik bez aggregatedListType (zgodność wsteczna – zasób NIE wejdzie do wykazu).
    """
    if wersja not in NAMESPACES:
        raise ValueError(f"nieobsługiwana wersja {wersja}")
    teraz = (teraz or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rekordy = rekordy or []
    nazwa = (nazwa_dostawcy or "").strip() or "Dostawca danych"
    zb_id = ext_ident_zbioru or ext_ident("aed", nazwa)
    zs_id = ext_ident_zasobu or ext_ident(zb_id[:30], "csv")
    daty = [d for d in (_xsd_datetime(r.get("data_aktualizacji")) for r in rekordy) if d]
    ostatnia = max(daty) if daty else teraz.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = url_zasobu.strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]

    korzen = etree.Element(f"{{{NAMESPACES[wersja]}}}datasets", nsmap={"ns2": NAMESPACES[wersja]})
    ds = etree.SubElement(korzen, "dataset", status="published")
    _tekst(ds, "extIdent", zb_id)
    _dwujezyczny(ds, "title", f"Defibrylatory AED – {nazwa}"[:300], f"AED defibrillators – {nazwa}"[:300])
    _dwujezyczny(
        ds, "description",
        (f"Lokalizacje automatycznych defibrylatorów zewnętrznych (AED) udostępniane przez: {nazwa}. "
         "Dane według wzorcowego zakresu danych AED (#TuBijeAED). Zasób jest oznaczony jako element "
         "Wykazu defibrylatorów AED – wykazu zbiorczego dane.gov.pl. Za dane odpowiada dostawca.")[:1000],
        f"Locations of automated external defibrillators (AED) published by {nazwa}."[:1000])
    _tekst(ds, "updateFrequency", czestotliwosc)
    _flagi(ds)
    kategorie = etree.SubElement(ds, "categories")
    _tekst(kategorie, "category", "HEAL")
    warunki = etree.SubElement(ds, "conditions")
    _tekst(warunki, "source", "true")
    _tekst(warunki, "modification", "true")
    _tekst(warunki, "responsibilities",
           f"Za aktualność i poprawność danych odpowiada {nazwa}. W sytuacji zagrożenia życia dzwoń pod 112.")
    _tekst(warunki, "dbOrCopyrightedLicenseChosen", licencja)
    _tekst(warunki, "personalData", "Zasób nie zawiera danych osobowych – podawane są wyłącznie kontakty funkcyjne.")

    zasoby = etree.SubElement(ds, "resources")
    z = etree.SubElement(zasoby, "resource", status="published")
    _tekst(z, "extIdent", zs_id)
    _tekst(z, "url", url)
    _dwujezyczny(z, "title", f"Defibrylatory AED – {nazwa} (CSV, wzorzec AED)"[:300],
                 f"AED defibrillators – {nazwa} (CSV)"[:300])
    _dwujezyczny(z, "description",
                 "Plik CSV UTF-8 zgodny ze wzorcowym zakresem danych AED (aed_schema.json): jeden wiersz = jedno "
                 "urządzenie, współrzędne WGS84, godziny dostępności w formacie OSM opening_hours.")
    _tekst(z, "availability", "local")
    _tekst(z, "dataDate", teraz.strftime("%Y-%m-%d"))
    _tekst(z, "lastUpdateDate", ostatnia)
    _flagi(z, chronione=False)
    if wersja == "1.14":
        # xs:all – kolejność dowolna; umieszczamy obok containsProtectedData (analogia DGA)
        _tekst(z, "aggregatedListType", "AED")
    teryt = kody_teryt(rekordy)
    if teryt:
        regiony = etree.SubElement(z, "regions")
        for kod in teryt:
            _tekst(regiony, "terytIdent", kod)

    tagi = etree.SubElement(ds, "tags")
    for t in ("AED", "defibrylator", "pierwsza pomoc", "#TuBijeAED"):
        _tekst(tagi, "tag", t, lang="pl")
    _tekst(ds, "lastUpdateDate", ostatnia)
    return etree.tostring(korzen, xml_declaration=True, encoding="UTF-8", pretty_print=True)
