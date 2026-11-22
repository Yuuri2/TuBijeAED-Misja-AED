"""Asystent dostawcy: konwersja istniejącego pliku gminy do wzorca AED + pakiet do publikacji. Właściciel: API.

Ścieżka migracji dla gmin, które już publikują AED w dane.gov.pl w „swoich” formatach (Krosno, Przemyśl,
Marki, Legionowo, Warszawa): mapowania z Sprintu 1 (mapowania_danegov.py) zamieniają plik na wiersze wzorca.

Zasada: NIE zgadujemy. Czego plik źródłowy nie zawiera (np. czy_zamkniete, status_urzadzenia, dysponent),
zostaje puste i trafia do raportu jako „do uzupełnienia przez dostawcę”. Jedyne wartości spoza pliku to
te, które dostawca poda jawnie w formularzu (dysponent, data aktualizacji) oraz obszar (gmina/TERYT)
wynikający z WYBRANEGO profilu – przy profilu `auto` obszar uzupełniamy tylko gdy dopasowanie jest jednoznaczne.

Odpowiednik w mcod: brak (portal tylko waliduje – validate_dga_df_columns); to narzędzie po stronie dostawcy.
"""
from __future__ import annotations

import csv
import io
import math
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .. import schema, validation
from ..exports.bezpieczne import bezpieczna_komorka
from . import czytniki, danegov
from .mapowania_danegov import MAPOWANIA
from .wspolne import klucz_kolumny

PROFILE = {"krosno": "3624", "przemysl": "4581", "marki": "4955", "legionowo": "40593", "warszawa": "39512"}
FORMATY = {".csv": "csv", ".xlsx": "xlsx", ".json": "json", ".geojson": "geojson"}
POLA_DYSPONENTA = ("nazwa_dysponenta", "identyfikator_dysponenta", "typ_dysponenta", "kontakt_dysponenta")
DO_UZUPELNIENIA = "do uzupełnienia przez dostawcę"


class BladKonwersji(ValueError):
    def __init__(self, komunikat: str, status: int = 400):
        super().__init__(komunikat)
        self.komunikat, self.status = komunikat, status


@dataclass
class WynikKonwersji:
    profil: str
    profil_wykryty: str | None
    rekordy: list[dict]
    csv: str
    ostrzezenia: list[str] = field(default_factory=list)
    do_uzupelnienia: list[dict] = field(default_factory=list)
    walidacja: dict = field(default_factory=dict)

    def raport(self) -> dict:
        return {
            "profil": self.profil,
            "profil_wykryty": self.profil_wykryty,
            "liczba_rekordow": len(self.rekordy),
            "ostrzezenia_konwersji": self.ostrzezenia,
            "do_uzupelnienia": self.do_uzupelnienia,
            "walidacja": self.walidacja,
        }


def _wartosc(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v) if math.isfinite(v) else ""
    return bezpieczna_komorka(str(v))


def do_csv_wzorca(rekordy: list[dict]) -> str:
    """Wiersze -> CSV UTF-8 z kolumnami DOKŁADNIE jak `fields` w aed_schema.json (bez pól systemowych)."""
    kolumny = schema.nazwy_pol()
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(kolumny)
    for r in rekordy:
        w.writerow([_wartosc(r.get(k)) for k in kolumny])
    return buf.getvalue()


def wykryj_profil(wiersze: list[dict]) -> list[str]:
    """Profile, których WSZYSTKIE kolumny mapowania występują w pliku."""
    if not wiersze:
        return []
    obecne = {klucz_kolumny(k) for k in wiersze[0] if k != "_geometria"}
    return [p for p, zid in PROFILE.items()
            if all(klucz_kolumny(k) in obecne for k in MAPOWANIA[zid]["kolumny"].values())]


def _braki(rekordy: list[dict]) -> list[dict]:
    wynik = []
    for p in schema.pola():
        if p.get("x-wymagane") not in ("TAK", "ZALECANE", "WARUNKOWO"):
            continue
        puste = sum(1 for r in rekordy if not schema.pole_wypelnione(r.get(p["name"])))
        if p.get("x-wymagane") == "WARUNKOWO":
            puste = sum(1 for r in rekordy
                        if schema.warunek_aktywny(p, r) and not schema.pole_wypelnione(r.get(p["name"])))
        if puste:
            wynik.append({"pole": p["name"], "tytul": p.get("title"), "wymagane": p.get("x-wymagane"),
                          "puste_wiersze": puste, "komunikat": DO_UZUPELNIENIA})
    return wynik


def wczytaj_wiersze(dane: bytes, nazwa_pliku: str) -> list[dict]:
    fmt = FORMATY.get(Path(nazwa_pliku or "").suffix.lower())
    if fmt is None:
        raise BladKonwersji("Obsługiwane pliki: .csv, .xlsx, .json, .geojson.")
    try:
        wiersze = czytniki.czytaj(dane, fmt)
    except czytniki.BladFormatu as e:
        raise BladKonwersji(f"Nie można odczytać pliku: {e}") from e
    if not wiersze:
        raise BladKonwersji("Plik nie zawiera wierszy z danymi.")
    return wiersze


def konwertuj(dane: bytes, nazwa_pliku: str, profil: str = "auto", *, dysponent: dict | None = None,
              data_aktualizacji: str | None = None) -> WynikKonwersji:
    """Plik gminy (csv/xlsx/json/geojson) -> wiersze wzorca + CSV + raport. Rzuca BladKonwersji."""
    from ..config import MAX_FILE_BYTES

    if len(dane) > MAX_FILE_BYTES:
        raise BladKonwersji(f"Plik jest za duży (maks. {MAX_FILE_BYTES // 1024 // 1024} MB).", 413)
    profil = (profil or "auto").strip().lower()
    if profil != "auto" and profil not in PROFILE:
        raise BladKonwersji(f"Nieznany profil „{profil}”. Dostępne: {', '.join([*PROFILE, 'auto'])}.", 422)
    wiersze = wczytaj_wiersze(dane, nazwa_pliku)
    ostrzezenia: list[str] = []
    wykryty = None
    if profil == "auto":
        pasujace = wykryj_profil(wiersze)
        if len(pasujace) == 1:
            wykryty = pasujace[0]
            konfig = MAPOWANIA[PROFILE[wykryty]]
            ostrzezenia.append(f"Rozpoznano układ pliku: profil „{wykryty}”.")
        elif pasujace:
            # ten sam układ kolumn w kilku gminach (np. Krosno i Marki) – kolumny tak, obszar NIE
            konfig = {k: v for k, v in MAPOWANIA[PROFILE[pasujace[0]]].items() if k in ("kolumny",)}
            ostrzezenia.append(f"Układ kolumn pasuje do profili: {', '.join(pasujace)} – nie uzupełniono "
                               "województwa/powiatu/gminy. Wybierz właściwy profil lub uzupełnij obszar.")
        else:
            konfig = None
    else:
        konfig = MAPOWANIA[PROFILE[profil]]
    if konfig is not None:
        konfig = {k: v for k, v in konfig.items() if k not in ("pobieranie", "zasoby")}

    zbior = {"id": profil, "attributes": {"license_name": "CC BY 4.0"}}   # licencja nie trafia do wzorca
    try:
        rekordy, uwagi = danegov.normalizuj(wiersze, zbior=zbior, instytucja={}, zasob=None, konfig=konfig,
                                            dysponent={k: (dysponent or {}).get(k) for k in POLA_DYSPONENTA})
    except danegov.BladZrodla as e:
        raise BladKonwersji(str(e)) from e
    ostrzezenia += uwagi
    pola = schema.nazwy_pol()
    rekordy = [{k: r.get(k) for k in pola} for r in rekordy]
    for r in rekordy:
        r["data_aktualizacji"] = data_aktualizacji or None
    tekst_csv = do_csv_wzorca(rekordy)
    try:
        walidacja = validation.waliduj_plik(tekst_csv.encode("utf-8"), "dane_aed.csv").jako_dict()
    except validation.BladPliku as e:
        walidacja = {"bledy": [{"wiersz": None, "pole": None, "kod": "plik", "komunikat": e.komunikat}]}
    return WynikKonwersji(profil=profil, profil_wykryty=wykryty, rekordy=rekordy, csv=tekst_csv,
                          ostrzezenia=ostrzezenia, do_uzupelnienia=_braki(rekordy), walidacja=walidacja)


def wzorzec_z_pliku(dane: bytes, nazwa_pliku: str) -> tuple[list[dict], dict]:
    """Plik JUŻ we wzorcu (csv/xlsx) -> (wiersze w kolejności kolumn wzorca, raport walidacji).

    Wiersze z błędami zostają (dostawca poprawia je u siebie) – raport mówi, co poprawić.
    """
    try:
        _, wiersze, _ = validation.wczytaj_plik(dane, nazwa_pliku)
        raport = validation.waliduj_plik(dane, nazwa_pliku).jako_dict()
    except validation.BladPliku as e:
        raise BladKonwersji(e.komunikat, e.status) from e
    znane = {n.lower(): n for n in schema.nazwy_pol()}
    rekordy = [{znane[k.lower()]: v for k, v in w.items() if k and k.lower() in znane} for _, w in wiersze]
    return rekordy, raport


# ---------------------------------------------------------------------------------------------- pakiet

def instrukcja(*, nazwa_dostawcy: str, url_zasobu: str, url_domyslny: bool, raport: dict, base_url: str) -> str:
    poprawne, bledne = raport.get("poprawne_wiersze", 0), raport.get("bledne_wiersze", 0)
    stan = (f"Stan pliku dane_aed.csv: {poprawne} poprawnych wierszy, {bledne} z błędami."
            + ("\n  UWAGA: popraw wiersze z błędami (raport w asystencie: „Sprawdź plik”) – zasób z błędami\n"
               "  zostanie zapisany w portalu, ale NIE wejdzie do Wykazu zbiorczego AED." if bledne else ""))
    adres = (f"  W pliku harvester_1_14.xml wpisano adres zastępczy {url_zasobu}\n"
             "  – ZAMIEŃ go na prawdziwy adres https, pod którym opublikujesz dane_aed.csv.\n" if url_domyslny else
             f"  Adres pliku w harvester_1_14.xml: {url_zasobu}\n")
    return f"""#TuBijeAED – pakiet do publikacji danych o defibrylatorach AED w dane.gov.pl
Dostawca: {nazwa_dostawcy}
{stan}

Zawartość pakietu
  dane_aed.csv          dane w wzorcowym zakresie danych AED (CSV UTF-8, kolumny jak w aed_schema.json)
  harvester_1_14.xml    opis zbioru i zasobu do importu automatycznego (schemat XML 1.14)
  INSTRUKCJA.txt        ten plik

Zasada: dane publikujesz na SWOIM koncie w dane.gov.pl i to Ty za nie odpowiadasz.
Portal sam scala zasoby wszystkich dostawców w „Wykaz defibrylatorów AED – wykaz zbiorczy”.
Wystarczy oznaczyć zasób jako element wykazu AED (sposób A lub B poniżej).

Przed publikacją
  1. Otwórz dane_aed.csv i uzupełnij puste kolumny wymagane (raport asystenta: „do uzupełnienia przez
     dostawcę”) – np. czy_zamkniete, status_urzadzenia, wewnatrz_budynku, data_aktualizacji.
     Nie wpisuj wartości „na oko”: jeśli nie wiesz, sprawdź urządzenie na miejscu.
  2. Sprawdź plik w asystencie: {base_url}/asystent.html → „Sprawdź plik”. Cel: 0 błędów.

Sposób A – ręcznie w panelu dostawcy (jednorazowo lub rzadko)
  3. Zaloguj się do panelu dostawcy dane.gov.pl (w prototypie: {base_url}/admin/ → „Zaloguj jako…”).
  4. Dodaj zbiór (lub otwórz istniejący) „Defibrylatory AED – {nazwa_dostawcy}”, kategoria Zdrowie,
     licencja CC BY 4.0 lub CC0 1.0.
  5. Dodaj zasób: wybierz plik dane_aed.csv i zaznacz pole
     „Zasób wchodzi do Wykazu zbiorczego AED”. Status: opublikowany.
  6. Portal pokaże raport walidacji. Jeśli są błędy – popraw plik i zaktualizuj TEN SAM zasób
     (instytucja może mieć tylko jeden zasób w wykazie AED).
  7. Po zapisaniu poprawnego zasobu wykaz zbiorczy przebudowuje się automatycznie – sprawdź
     {base_url}/wykaz-aed.html, czy Twoja instytucja jest na liście „uwzględnione”.

Sposób B – automatycznie przez harvester XML (regularne aktualizacje)
  3. Opublikuj dane_aed.csv pod stałym adresem https na swoim serwerze (np. BIP).
{adres}  4. Opublikuj harvester_1_14.xml pod stałym adresem https.
     Element <aggregatedListType>AED</aggregatedListType> w zasobie oznacza go jako element wykazu AED
     (odpowiednik <containsProtectedData> dla wykazu chronionych danych). W pliku 1.13 tego elementu
     nie ma – zasób z pliku 1.13 nie wejdzie do wykazu.
  5. W panelu dane.gov.pl zgłoś źródło harvestera XML (w prototypie: panel → „Import XML harvestera”,
     wgraj harvester_1_14.xml). Portal sprawdzi plik schematem XSD 1.14, pobierze dane_aed.csv,
     zwaliduje go wzorcem i przebuduje wykaz.
  6. Aktualizacja = podmiana dane_aed.csv pod tym samym adresem (te same extIdent w XML).

Odznaka „Partner #TuBijeAED – zweryfikowane w dane.gov.pl”
  Przyznawana automatycznie, gdy zasób jest w aktualnym wykazie, ma 0 błędów walidacji, był
  aktualizowany w ostatnich 12 miesiącach, a średnia kompletność rekordów wynosi co najmniej 80%.

W sytuacji zagrożenia życia dzwoń pod 112.
"""


def zbuduj_pakiet(*, rekordy: list[dict], raport: dict, nazwa_dostawcy: str, url_zasobu: str | None,
                  base_url: str, licencja: str = "CC BY 4.0") -> tuple[bytes, bytes]:
    """-> (zip, xml). XML generowany w wersji 1.14 z aggregatedListType=AED."""
    from ..exports import harvester_xml

    domyslny = not (url_zasobu or "").strip()
    url = (url_zasobu or "").strip() or "https://twoja-domena.example/dane_aed.csv"
    xml = harvester_xml.zbuduj_xml_dostawcy(nazwa_dostawcy=nazwa_dostawcy, url_zasobu=url, rekordy=rekordy,
                                             licencja=licencja)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dane_aed.csv", do_csv_wzorca(rekordy).encode("utf-8"))
        z.writestr("harvester_1_14.xml", xml)
        z.writestr("INSTRUKCJA.txt", instrukcja(nazwa_dostawcy=nazwa_dostawcy, url_zasobu=url,
                                                url_domyslny=domyslny, raport=raport,
                                                base_url=base_url).encode("utf-8"))
    return buf.getvalue(), xml
