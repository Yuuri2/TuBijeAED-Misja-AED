"""Harvester XML 1.13 / 1.14 – import zbiorów i zasobów dostawcy (właściciel: API). Kontrakt: docs/PROTOTYP.md.

Odpowiedniki w mcod (kod portalu dane.gov.pl):
  * data/harvester/xml_import_otwarte_dane_1_13.xsd  -> app/harvester/xsd/ (1.13 bez zmian + 1.14 z `aggregatedListType`)
  * mcod/harvester/serializers.py  XMLResourceSchema.contains_protected_data / validate_contains_protected_data
                                   -> _waliduj_zasob_aed() + repo_portal (walidacja kolumn wzorca, 1 zasób AED na instytucję)
  * mcod/resources/dga_utils.py    get_dga_resources_info_from_xml_harvester_file
                                   -> zasoby_aed_w_pliku() (więcej niż 1 zasób AED w pliku = błąd)
  * mcod/resources/dga_utils.py    request_remote_dga (timeout (3, 5) s) -> pobierz_plik()
  * mcod/harvester/models.py       DataSource (import XML, upsert po ext_ident) -> importuj_xml()

Różnice względem mcod (świadome, prototyp):
  * błąd jednego zasobu NIE odrzuca całego pliku – trafia do `bledy`, reszta się importuje
    (mcod przy błędzie walidacji schematu odrzuca zbiór); dzięki temu dostawca widzi wszystkie problemy naraz;
  * `containsProtectedData` jest czytane, ale prototyp nie prowadzi wykazu DGA – tylko ostrzeżenie.

Bezpieczeństwo: parser bez encji zewnętrznych / DTD / sieci, limit rozmiaru pliku XML i pobieranych zasobów,
pobieranie tylko http(s) z odrzuceniem adresów prywatnych/pętli zwrotnej (SSRF), timeouty.
Tryb demo offline: adresy `https://demo.tubijeaed.example/<plik>` (domena zastrzeżona RFC 2606, nigdy nie
jest odpytywana) są czytane z katalogu `app/harvester/demo_pliki/`.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

from lxml import etree

NS_113 = "urn:otwarte-dane:harvester:1.13"
NS_114 = "urn:otwarte-dane:harvester:1.14"
WERSJE = {NS_113: "1.13", NS_114: "1.14"}

KATALOG_XSD = Path(__file__).resolve().parent / "xsd"
PLIKI_XSD = {
    "1.13": KATALOG_XSD / "xml_import_otwarte_dane_1_13.xsd",   # kopia 1:1 oficjalnego pliku z mcod
    "1.14": KATALOG_XSD / "xml_import_otwarte_dane_1_14.xsd",
}
KATALOG_DEMO = Path(__file__).resolve().parent / "demo_pliki"
DEMO_HOST = "demo.tubijeaed.example"

MAKS_ROZMIAR_XML = 5 * 1024 * 1024
MAKS_ROZMIAR_PLIKU = 10 * 1024 * 1024
TIMEOUT = (3.0, 10.0)               # mcod request_remote_dga: (3.0, 5.0); 10 s na odczyt dla wolnych BIP-ów
MAKS_PRZEKIEROWAN = 3
MAKS_BLEDOW_XSD = 20
FORMATY_WYKAZU = (".csv", ".xlsx")  # mcod: xls/xlsx/csv; walidator wzorca czyta csv i xlsx
TYPY_WYKAZOW = ("AED",)
STATUS = {"published": "opublikowany", "draft": "szkic"}
_TYP_NA_ROZSZERZENIE = {
    "text/csv": ".csv",
    "application/csv": ".csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/json": ".json",
    "application/geo+json": ".geojson",
    "application/vnd.geo+json": ".geojson",
    "application/xml": ".xml",
    "text/xml": ".xml",
}

Pobieracz = Callable[[str], "tuple[bytes, str]"]


class BladPobierania(RuntimeError):
    """Nie udało się pobrać pliku zasobu (sieć, HTTP, rozmiar, niedozwolony adres)."""


# ---------------------------------------------------------------------------------------------- XSD / parsowanie

_schematy: dict[str, etree.XMLSchema] = {}


def schemat_xsd(wersja: str) -> etree.XMLSchema:
    if wersja not in _schematy:
        _schematy[wersja] = etree.XMLSchema(etree.parse(str(PLIKI_XSD[wersja])))
    return _schematy[wersja]


def _parser() -> etree.XMLParser:
    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False,
                           remove_comments=True)


class BladPliku(ValueError):
    """Cały plik XML nie nadaje się do importu (składnia, wersja, XSD)."""

    def __init__(self, kod: str, komunikat: str, szczegoly: list[str] | None = None):
        super().__init__(komunikat)
        self.kod, self.komunikat, self.szczegoly = kod, komunikat, szczegoly or []


def wczytaj_i_waliduj(tresc: bytes) -> tuple[str, etree._Element]:
    """-> (wersja '1.13'|'1.14', korzeń). Rzuca BladPliku. Wersja rozpoznawana po przestrzeni nazw korzenia."""
    if not tresc or not tresc.strip():
        raise BladPliku("pusty", "Plik XML jest pusty.")
    if len(tresc) > MAKS_ROZMIAR_XML:
        raise BladPliku("rozmiar", f"Plik XML jest za duży (maks. {MAKS_ROZMIAR_XML // 1024 // 1024} MB).")
    try:
        korzen = etree.fromstring(tresc, _parser())
    except etree.XMLSyntaxError as e:
        raise BladPliku("skladnia", f"Niepoprawna składnia XML: {e}") from e
    drzewo = korzen.getroottree()
    if drzewo.docinfo.doctype or drzewo.docinfo.internalDTD is not None:
        raise BladPliku("dtd", "Plik XML nie może zawierać deklaracji DOCTYPE/encji (wymóg bezpieczeństwa).")
    ns = etree.QName(korzen).namespace
    wersja = WERSJE.get(ns or "")
    if wersja is None or etree.QName(korzen).localname != "datasets":
        raise BladPliku("wersja", "Nieobsługiwany format pliku: oczekiwano elementu <datasets> w przestrzeni nazw "
                                  f"{NS_113} lub {NS_114} (otrzymano: {{{ns}}}{etree.QName(korzen).localname}).")
    xsd = schemat_xsd(wersja)
    try:
        poprawny = xsd.validate(korzen)
    except etree.XMLSchemaValidateError as e:
        raise BladPliku("xsd", f"Nie udało się sprawdzić pliku schematem XSD {wersja}: {e}") from e
    if not poprawny:
        bledy = [f"linia {b.line}: {b.message}" for b in list(xsd.error_log)[:MAKS_BLEDOW_XSD]]
        raise BladPliku("xsd", f"Plik nie jest zgodny ze schematem XSD {wersja} ({len(xsd.error_log)} błędów).", bledy)
    return wersja, korzen


def _txt(el: etree._Element | None, sciezka: str) -> str | None:
    if el is None:
        return None
    x = el.find(sciezka)
    if x is None or x.text is None:
        return None
    return x.text.strip() or None


def _bool(el, sciezka: str) -> bool:
    return (_txt(el, sciezka) or "").lower() in ("true", "1")


@dataclass
class ZasobXML:
    ext_ident: str
    url: str
    tytul: str
    opis: str
    status: str = "published"
    availability: str | None = None
    data_danych: str | None = None
    ostatnia_aktualizacja: str | None = None
    wykaz_typ: str | None = None
    chronione: bool = False


@dataclass
class ZbiorXML:
    ext_ident: str
    tytul: str
    opis: str
    status: str = "published"
    czestotliwosc: str = "irregular"
    licencja: str | None = None
    kategorie: list[str] = field(default_factory=list)
    slowa_kluczowe: list[str] = field(default_factory=list)
    zasoby: list[ZasobXML] = field(default_factory=list)


def parsuj(korzen: etree._Element) -> list[ZbiorXML]:
    """Zwalidowany korzeń -> lista zbiorów (czysta funkcja; odpowiednik XMLDatasetSchema/XMLResourceSchema)."""
    wynik = []
    for ds in korzen.findall("dataset"):
        zb = ZbiorXML(
            ext_ident=_txt(ds, "extIdent"),
            tytul=_txt(ds, "title/polish"),
            opis=_txt(ds, "description/polish") or "",
            status=ds.get("status", "published"),
            czestotliwosc=_txt(ds, "updateFrequency") or "irregular",
            licencja=_txt(ds, "conditions/dbOrCopyrightedLicenseChosen"),
            kategorie=[c.text.strip() for c in ds.findall("categories/category") if c.text],
            slowa_kluczowe=[t.text.strip() for t in ds.findall("tags/tag") if t.text and t.get("lang") == "pl"],
        )
        for r in ds.findall("resources/resource"):
            zb.zasoby.append(ZasobXML(
                ext_ident=_txt(r, "extIdent"),
                url=_txt(r, "url"),
                tytul=_txt(r, "title/polish"),
                opis=_txt(r, "description/polish") or "",
                status=r.get("status", "published"),
                availability=_txt(r, "availability"),
                data_danych=_txt(r, "dataDate"),
                ostatnia_aktualizacja=_txt(r, "lastUpdateDate"),
                wykaz_typ=_txt(r, "aggregatedListType"),
                chronione=_bool(r, "containsProtectedData"),
            ))
        wynik.append(zb)
    return wynik


def zasoby_aed_w_pliku(zbiory: list[ZbiorXML]) -> list[tuple[str, str]]:
    """Odpowiednik dga_utils.get_dga_resources_info_from_xml_harvester_file: [(extIdent, tytuł)] zasobów AED."""
    return [(r.ext_ident, r.tytul) for z in zbiory for r in z.zasoby if r.wykaz_typ == "AED"]


# ---------------------------------------------------------------------------------------------- pobieranie

def _sprawdz_host(host: str | None) -> None:
    """Ochrona SSRF: nie pobieramy z sieci lokalnej (chyba że HARVESTER_ZEZWOL_LOKALNE=1 – testy/dev)."""
    if not host:
        raise BladPobierania("adres bez nazwy hosta")
    if os.environ.get("HARVESTER_ZEZWOL_LOKALNE") == "1":
        return
    try:
        adresy = {i[4][0] for i in socket.getaddrinfo(host, None)}
    except socket.gaierror as e:
        raise BladPobierania(f"nie można rozwiązać nazwy hosta „{host}”") from e
    for a in adresy:
        ip = ipaddress.ip_address(a.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise BladPobierania(f"adres „{host}” wskazuje sieć wewnętrzną – niedozwolony")


def _nazwa_pliku(url: str, content_type: str | None) -> str:
    nazwa = Path(urlparse(url).path).name or "zasob"
    if not Path(nazwa).suffix:
        typ = (content_type or "").split(";")[0].strip().lower()
        nazwa += _TYP_NA_ROZSZERZENIE.get(typ, "")
    return nazwa


def _plik_demo(url: str) -> tuple[bytes, str]:
    nazwa = Path(urlparse(url).path).name
    sciezka = (KATALOG_DEMO / nazwa).resolve()
    if not nazwa or sciezka.parent != KATALOG_DEMO or not sciezka.is_file():
        raise BladPobierania(f"brak pliku demo „{nazwa}” (tryb offline: {DEMO_HOST})")
    dane = sciezka.read_bytes()
    if len(dane) > MAKS_ROZMIAR_PLIKU:
        raise BladPobierania("plik większy niż limit")
    return dane, nazwa


def pobierz_plik(url: str) -> tuple[bytes, str]:
    """Pobiera plik zasobu -> (bajty, nazwa_pliku z rozszerzeniem). Rzuca BladPobierania.

    Kolejność: host demo (offline) -> http(s) z limitem rozmiaru, timeoutem i ręcznie śledzonymi
    przekierowaniami (każde sprawdzane pod kątem SSRF).
    """
    p = urlparse(url or "")
    if p.hostname == DEMO_HOST:
        return _plik_demo(url)
    if p.scheme not in ("http", "https"):
        raise BladPobierania(f"nieobsługiwany schemat adresu „{p.scheme}” (dozwolone: http, https)")
    import requests

    sesja = requests.Session()
    sesja.headers["User-Agent"] = "TuBijeAED-harvester/0.2 (+prototyp HackNation 2026)"
    biezacy = url
    for _ in range(MAKS_PRZEKIEROWAN + 1):
        _sprawdz_host(urlparse(biezacy).hostname)
        try:
            r = sesja.get(biezacy, timeout=TIMEOUT, stream=True, allow_redirects=False)
        except requests.Timeout as e:
            raise BladPobierania(f"adres nie odpowiada w {TIMEOUT[1]:.0f} s") from e
        except requests.RequestException as e:
            raise BladPobierania(f"błąd połączenia ({e.__class__.__name__})") from e
        if r.is_redirect and r.headers.get("location"):
            biezacy = urljoin(biezacy, r.headers["location"])
            if urlparse(biezacy).scheme not in ("http", "https"):
                raise BladPobierania("przekierowanie na niedozwolony schemat")
            continue
        if r.status_code != 200:
            raise BladPobierania(f"adres zwrócił HTTP {r.status_code}")
        dane = r.raw.read(MAKS_ROZMIAR_PLIKU + 1, decode_content=True)
        if len(dane) > MAKS_ROZMIAR_PLIKU:
            raise BladPobierania(f"plik większy niż {MAKS_ROZMIAR_PLIKU // 1024 // 1024} MB")
        return dane, _nazwa_pliku(biezacy, r.headers.get("content-type"))
    raise BladPobierania("zbyt wiele przekierowań")


# ---------------------------------------------------------------------------------------------- import

def _blad(bledy: list, *, zbior: str | None, zasob: str | None, kod: str, komunikat: str, **dodatkowe) -> None:
    bledy.append({"poziom": "zasob" if zasob else ("zbior" if zbior else "plik"),
                  "zbior": zbior, "zasob": zasob, "kod": kod, "komunikat": komunikat, **dodatkowe})


def importuj_xml(tresc: bytes, instytucja_id: int, *, pobieracz: Pobieracz | None = None) -> dict:
    """Import pliku harvestera XML (1.13 lub 1.14) na konto instytucji.

    -> {wersja, zbiory_utworzone, zasoby_utworzone, bledy: [{poziom, zbior, zasob, kod, komunikat}],
        ostrzezenia: [str], zasoby: [{ext_ident, id, tytul, wykaz_typ, walidacja_status, wykaz}]}
    `zbiory_utworzone`/`zasoby_utworzone` liczą zbiory/zasoby zapisane (utworzone lub zaktualizowane po ext_ident).
    Błąd całego pliku (składnia, wersja, XSD) -> liczniki 0 i jeden błąd z `poziom="plik"`.
    """
    from ..portal import repo_portal
    from ..portal.wykazy import BladWykazu

    pobierz = pobieracz or pobierz_plik
    wynik = {"wersja": None, "zbiory_utworzone": 0, "zasoby_utworzone": 0, "bledy": [], "ostrzezenia": [],
             "zasoby": []}
    bledy, ostrz = wynik["bledy"], wynik["ostrzezenia"]
    try:
        wersja, korzen = wczytaj_i_waliduj(tresc)
    except BladPliku as e:
        _blad(bledy, zbior=None, zasob=None, kod=e.kod, komunikat=e.komunikat, szczegoly=e.szczegoly)
        return wynik
    wynik["wersja"] = wersja
    zbiory = parsuj(korzen)
    if wersja == "1.13":
        ostrz.append("Plik w wersji 1.13 – brak elementu aggregatedListType, żaden zasób nie zostanie dodany do "
                     "Wykazu zbiorczego AED. Użyj wersji 1.14, aby oznaczyć zasób AED.")

    # mcod: „There is more than 1 resource in the harvester file containing the 'containsProtectedData'…”
    aed = zasoby_aed_w_pliku(zbiory)
    odrzucone_aed: set[str] = set()
    komunikat = ""
    if len(aed) > 1:
        lista = ", ".join(f"Zasób {i}: 'title' = {t}, 'extIdent' = {e}" for i, (e, t) in enumerate(aed, 1))
        komunikat = (f"W pliku harvestera jest więcej niż 1 zasób z elementem aggregatedListType = AED "
                     f"(dostawca może mieć w wykazie tylko jeden zasób AED). {lista}")
        odrzucone_aed = {e for e, _ in aed}

    for zb in zbiory:
        try:
            zbior = repo_portal.utworz_zbior(
                instytucja_id, tytul=zb.tytul, opis=zb.opis, licencja=zb.licencja or "CC BY 4.0",
                czestotliwosc=zb.czestotliwosc, slowa_kluczowe=zb.slowa_kluczowe,
                status=STATUS.get(zb.status, "opublikowany"), zrodlo="harvester", ext_ident=zb.ext_ident)
        except NotImplementedError:
            raise
        except BladWykazu as e:
            _blad(bledy, zbior=zb.ext_ident, zasob=None, kod=f"wykaz_{e.kod_http}", komunikat=e.komunikat)
            continue
        except Exception as e:  # noqa: BLE001 – błąd jednego zbioru nie przerywa importu
            _blad(bledy, zbior=zb.ext_ident, zasob=None, kod="zapis", komunikat=f"Nie zapisano zbioru: {e}")
            continue
        wynik["zbiory_utworzone"] += 1

        for zs in zb.zasoby:
            if zs.chronione:
                ostrz.append(f"Zasób „{zs.ext_ident}”: containsProtectedData=true – prototyp nie prowadzi wykazu "
                             "DGA, flaga pominięta.")
            if zs.ext_ident in odrzucone_aed:
                _blad(bledy, zbior=zb.ext_ident, zasob=zs.ext_ident, kod="wiele_zasobow_aed", komunikat=komunikat)
                continue
            _importuj_zasob(zbior["id"], zb, zs, pobierz, repo_portal, BladWykazu, wynik)
    return wynik


def _importuj_zasob(zbior_id: int, zb: ZbiorXML, zs: ZasobXML, pobierz: Pobieracz, repo_portal, BladWykazu,
                    wynik: dict) -> None:
    bledy = wynik["bledy"]
    wykaz = zs.wykaz_typ if zs.wykaz_typ in TYPY_WYKAZOW else None
    plik, nazwa = None, None
    # Zasób wykazu musi być pobrany (walidacja kolumn – jak request_remote_dga w mcod); availability=local
    # oznacza kopię pliku w portalu. Zasób „remote” spoza wykazu zostaje samym linkiem.
    if wykaz or zs.availability != "remote":
        try:
            plik, nazwa = pobierz(zs.url)
        except BladPobierania as e:
            if wykaz:
                _blad(bledy, zbior=zb.ext_ident, zasob=zs.ext_ident, kod="url_niedostepny",
                      komunikat=f"Adres w polu url zasobu z aggregatedListType = {wykaz} nie odpowiada: {e}.")
                return
            wynik["ostrzezenia"].append(f"Zasób „{zs.ext_ident}”: nie pobrano pliku ({e}) – zapisano jako link.")
    if wykaz and Path(nazwa or "").suffix.lower() not in FORMATY_WYKAZU:
        _blad(bledy, zbior=zb.ext_ident, zasob=zs.ext_ident, kod="format",
              komunikat=f"Zasób z aggregatedListType = {wykaz} musi wskazywać plik CSV lub XLSX "
                        f"(otrzymano: „{nazwa}”).")
        return
    try:
        odp = repo_portal.dodaj_lub_zaktualizuj_zasob(
            zbior_id, tytul=zs.tytul, opis=zs.opis, plik=plik, nazwa_pliku=nazwa, url=zs.url, wykaz_typ=wykaz,
            status=STATUS.get(zs.status, "opublikowany"), data_danych=zs.data_danych, ext_ident=zs.ext_ident)
    except NotImplementedError:
        raise
    except BladWykazu as e:
        _blad(bledy, zbior=zb.ext_ident, zasob=zs.ext_ident, kod=f"wykaz_{e.kod_http}", komunikat=e.komunikat,
              szczegoly=e.szczegoly)
        return
    except Exception as e:  # noqa: BLE001
        _blad(bledy, zbior=zb.ext_ident, zasob=zs.ext_ident, kod="zapis", komunikat=f"Nie zapisano zasobu: {e}")
        return
    wynik["zasoby_utworzone"] += 1
    zasob = (odp or {}).get("zasob") or {}
    if wykaz and zasob.get("walidacja_status") == "BLEDY":
        wynik["ostrzezenia"].append(
            f"Zasób „{zs.ext_ident}” zapisano, ale ma błędy walidacji wierszy – nie wejdzie do wykazu {wykaz}, "
            "dopóki dostawca ich nie poprawi.")
    wynik["zasoby"].append({
        "ext_ident": zs.ext_ident, "id": zasob.get("id"), "tytul": zs.tytul, "wykaz_typ": wykaz,
        "walidacja_status": zasob.get("walidacja_status"), "wykaz": (odp or {}).get("wykaz"),
    })
