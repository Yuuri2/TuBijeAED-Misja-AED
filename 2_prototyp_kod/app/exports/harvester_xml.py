"""Eksport metadanych w formacie importu XML dane.gov.pl, schemat 1.13. Właściciel: API.

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


def zbuduj_harvester_xml(rekordy: list[dict], base_url: str, teraz: datetime | None = None) -> bytes:
    """Rekordy (już przefiltrowane przez repo) -> dokument XML importu dane.gov.pl 1.13."""
    teraz = (teraz or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rekordy = do_publikacji(rekordy)
    baza = adres_https(base_url)
    api = f"{baza}/api/v1"
    daty = [d for d in (_xsd_datetime(r.get("data_aktualizacji")) for r in rekordy) if d]
    ostatnia = max(daty) if daty else teraz.strftime("%Y-%m-%dT%H:%M:%SZ")
    teryt = kody_teryt(rekordy)
    liczba = len(rekordy)
    gminy = len({r.get("teryt_gmina") or r.get("gmina") for r in rekordy if r.get("teryt_gmina") or r.get("gmina")})

    korzen = etree.Element(f"{{{NS}}}datasets", nsmap={"ns2": NS})
    ds = etree.SubElement(korzen, "dataset", status="published")
    _tekst(ds, "extIdent", EXT_ID)
    _dwujezyczny(ds, "title",
                 "Defibrylatory AED w Polsce – zintegrowany rejestr #TuBijeAED",
                 "AED defibrillators in Poland – integrated #TuBijeAED registry")
    _dwujezyczny(
        ds, "description",
        "Ujednolicony zbiór lokalizacji automatycznych defibrylatorów zewnętrznych (AED) według wzorcowego "
        "zakresu danych #TuBijeAED: adres, współrzędne WGS84, dokładne miejsce w obiekcie, godziny dostępności, "
        "zabezpieczenie dostępu, status urządzenia i dysponent. Zbiór łączy rejestry AED opublikowane przez "
        f"jednostki samorządu w dane.gov.pl oraz zgłoszenia dysponentów (stan: {liczba} urządzeń, {gminy} gmin). "
        "Nie zawiera danych OpenStreetMap (licencja ODbL).",
        "Harmonised dataset of automated external defibrillator (AED) locations in Poland following the "
        "#TuBijeAED data model. Combines AED registries published by local governments on dane.gov.pl "
        "and submissions from AED owners.")
    _tekst(ds, "url", f"{baza}/")
    _tekst(ds, "updateFrequency", "daily")
    _flagi(ds)
    kategorie = etree.SubElement(ds, "categories")
    _tekst(kategorie, "category", "HEAL")

    warunki = etree.SubElement(ds, "conditions")
    _tekst(warunki, "source", "true")          # CC BY 4.0 wymaga wskazania źródła
    _tekst(warunki, "modification", "true")
    _tekst(warunki, "responsibilities",
           "Dane pochodzą od dysponentów urządzeń i jednostek samorządu. Przed użyciem w sytuacji zagrożenia "
           "życia należy kierować się wskazówkami dyspozytora numeru alarmowego 112.")
    _tekst(warunki, "dbOrCopyrightedLicenseChosen", LICENCJA)
    _tekst(warunki, "personalData", "Zbiór nie zawiera danych osobowych – podawane są wyłącznie kontakty funkcyjne.")

    zasoby = etree.SubElement(ds, "resources")
    for ext, sciezka, tytul_pl, tytul_en, opis in (
        ("tubijeaed-aed-csv", "export/csv", "Rejestr AED – CSV (UTF-8)", "AED registry – CSV (UTF-8)",
         "Tabela CSV w kodowaniu UTF-8, separator przecinek. Kolumny zgodne z wzorcowym zakresem danych "
         "(aed_schema.json) oraz źródło, licencja i status weryfikacji każdego rekordu."),
        ("tubijeaed-aed-geojson", "export/geojson", "Rejestr AED – GeoJSON", "AED registry – GeoJSON",
         "Dane przestrzenne GeoJSON (RFC 7946), układ WGS84, punkty [długość, szerokość]; atrybuty jak w CSV."),
    ):
        z = etree.SubElement(zasoby, "resource", status="published")
        _tekst(z, "extIdent", ext)
        _tekst(z, "url", f"{api}/{sciezka}")
        _dwujezyczny(z, "title", tytul_pl, tytul_en)
        _dwujezyczny(z, "description", opis)
        _tekst(z, "availability", "remote")
        _tekst(z, "dataDate", teraz.strftime("%Y-%m-%d"))
        _tekst(z, "lastUpdateDate", ostatnia)
        _flagi(z, chronione=False)
        if teryt:
            regiony = etree.SubElement(z, "regions")
            for kod in teryt:
                _tekst(regiony, "terytIdent", kod)

    tagi = etree.SubElement(ds, "tags")
    for t in TAGI:
        _tekst(tagi, "tag", t, lang="pl")
    _tekst(ds, "lastUpdateDate", ostatnia)

    dodatki = etree.SubElement(ds, "supplements")
    dod = etree.SubElement(dodatki, "supplement")
    _tekst(dod, "url", f"{api}/schema")
    _dwujezyczny(dod, "name", "Wzorcowy zakres danych AED (Table Schema, JSON)", "AED data model (Table Schema, JSON)")
    _tekst(dod, "language", "pl")

    return etree.tostring(korzen, xml_declaration=True, encoding="UTF-8", pretty_print=True)
