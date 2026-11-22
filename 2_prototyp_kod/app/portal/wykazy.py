"""Wykazy zbiorcze – uogólnienie mechanizmu „Wykaz chronionych danych (DGA) – wykaz zbiorczy” z mcod.
Właściciel: Backend. Kontrakt: docs/PROTOTYP.md.

Mapowanie na kod portalu (mcod/resources):
  dga_constants.py  DGA_COLUMNS, MAIN_DGA_COLUMNS,      -> KonfiguracjaWykazu.kolumny / kolumny_wymagane /
                    MAIN_DGA_REQUIRED_SOURCE_COLUMNS,      kolumny_wynikowe, dozwolone_typy_instytucji,
                    ALLOWED_DGA_INSTITUTIONS,              rozszerzenia  (słownik WYKAZY = jeden wpis na wykaz)
                    DGA_RESOURCE_EXTENSIONS
  settings/base.py  MAIN_DGA_DATASET_OWNER_ORGANIZATION_PK, MAIN_DGA_*_TITLE/DESC, MAIN_DGA_XLSX_*
                                                         -> KonfiguracjaWykazu.wlasciciel / tytul_* / opis_* / prefiks_pliku
  forms.py          _validate_dga_file, _validate_institution_when_contains_protected_data,
                    _remove_dga_flag_from_current_dga_resource_if_needed
                                                         -> waliduj_zasob_wykazu()
  dga_utils.py      validate_dga_df_columns              -> sprawdz_kolumny()
                    get_dga_resource_for_institution     -> zasob_wykazu_instytucji()
                    validate_institution_type_for_contains_protected_data -> sprawdz_typ_instytucji()
                    get_all_dga_resources_sorted_by_organizations -> _zasoby_zrodlowe()
                    get_main_dga_source_df + MainDGA*Error -> _wczytaj_zasob_zrodlowy() + BladZasobuZrodlowego
                    create_main_dga_df                   -> _zbuduj_wykaz()
                    add_style_to_main_dga_excel_file     -> _styl_xlsx()
                    create_main_dga_file                 -> krok 1 + _zapisz_pliki()
                    create_main_dga_dataset / create_main_dga_resource_with_dataset -> _utworz_zasoby_wykazu()
                    check_all_resource_validations_status -> _zweryfikuj_wynik()
                    update_or_create_aggr_dga_info_and_delete_old_main_dga -> _zapisz_info_i_usun_poprzedni()
                    clean_up_after_main_dga_resource_creation -> _posprzataj()
                    get_main_dga_resource / AggregatedDGAInfo -> aktualny_wykaz()
  tasks/dga.py      create_main_dga_resource_task (4 kroki, sprzątanie przy błędzie) -> utworz_wykaz_zbiorczy()

Różnice wobec DGA (świadome):
* Kolejność kolumn w zasobie źródłowym jest DOWOLNA, a nazwy porównujemy bez wielkości liter. DGA wymaga
  dokładnej listy i kolejności 5 kolumn (`df.columns.to_list() == DGA_COLUMNS`), bo wykaz DGA jest krótki
  i wypełniany ręcznie wg jednego szablonu. Wzorzec AED ma ~30 pól, a dostawcy (gminy, firmy) eksportują
  dane z różnych systemów – wymuszanie kolejności odrzucałoby poprawne dane z powodów czysto technicznych,
  nie dając żadnej korzyści: scalanie i tak odbywa się PO NAZWACH kolumn (reindex do kolumn wynikowych).
  Wymagamy obecności kolumn oznaczonych w aed_schema.json jako `x-wymagane: TAK`; brak pozostałych to
  ostrzeżenie, a w wykazie kolumna jest pusta.
* Oprócz kolumn sprawdzamy WARTOŚCI każdego wiersza wg wzorca (app/validation.py). DGA sprawdza w tym
  miejscu tylko puste wartości wymaganych kolumn; u nas zasób z błędami zapisuje się (`walidacja_status=BLEDY`,
  raport per wiersz), ale nie wchodzi do wykazu – tak jak w mcod zasób z `data_tasks_last_status != SUCCESS`.
* Dozwolone typy instytucji: local, state, private, other (DGA: tylko local, state). Defibrylatory są
  w dużej części własnością firm i organizacji (galerie, dworce, kluby) – one też muszą móc być dostawcą.
  `developer` (konta deweloperów aplikacji) – wykluczony.
* Wynik w trzech formatach (XLSX jak DGA + CSV UTF-8 + GeoJSON dla map), historia uruchomień w `wykazy_info`
  zamiast singletonu AggregatedDGAInfo, raport jakości (potencjalne duplikaty między dostawcami – tylko
  informacja, dostawca odpowiada za swoje dane).
* Synchronicznie w procesie API (zamiast Celery) z blokadą – w prototypie przebudowa trwa ułamek sekundy.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from .. import config, dedup, schema, validation
from . import baza

logger = logging.getLogger("tubijeaed.wykazy")


class BladPortalu(Exception):
    """Błąd operacji portalu z kodem HTTP i polskim komunikatem (router zamienia na {"error": ...})."""

    def __init__(self, kod_http: int, komunikat: str, szczegoly: dict | None = None):
        super().__init__(komunikat)
        self.kod_http, self.komunikat, self.szczegoly = kod_http, komunikat, szczegoly or {}


class BladWykazu(BladPortalu):
    """Naruszenie reguł wykazu (np. brak kolumn wzorca -> 422, drugi zasób AED instytucji -> 409)."""


class BladZasobuZrodlowego(Exception):
    """Zasób źródłowy pominięty przy scalaniu (odpowiednik MainDGAResourceReadError,
    MainDGAMissingRequiredColumnError, MainDGAEmptyRequiredValuesError)."""


class BladWeryfikacjiWykazu(Exception):
    """Wygenerowany wykaz nie przeszedł weryfikacji (odpowiednik FailedValidationException)."""


# ============================================================================ konfiguracja

KOLUMNY_DOSTAWCY: tuple[str, ...] = (
    "nazwa_dostawcy", "regon_dostawcy", "typ_dostawcy",
    "id_zasobu_zrodlowego", "url_zasobu_zrodlowego", "data_aktualizacji_zasobu",
)


@dataclass(frozen=True)
class KonfiguracjaWykazu:
    """Jeden wykaz zbiorczy. Kolejny wykaz (np. apteki) = nowy wpis w WYKAZY z własnym walidatorem."""

    typ: str
    tytul_zbioru: str
    opis: str
    wlasciciel: str                                   # nazwa instytucji-właściciela zbioru wykazu
    kolumny: tuple[str, ...]                          # pola wzorca w kolejności wzorca
    kolumny_wymagane: tuple[str, ...]                 # muszą wystąpić w pliku źródłowym (kolejność dowolna)
    tytul_zasobu: str
    opis_zasobu: str
    prefiks_pliku: str
    kolumny_dostawcy: tuple[str, ...] = KOLUMNY_DOSTAWCY
    dozwolone_typy_instytucji: tuple[str, ...] = ("local", "state", "private", "other")
    rozszerzenia: tuple[str, ...] = ("xlsx", "csv")
    slowa_kluczowe: tuple[str, ...] = ()
    kategoria: str = "HEAL"
    licencja: str = "CC BY 4.0"
    nazwa_arkusza: str = "Arkusz 1"
    pole_lat: str | None = "szerokosc_geo"
    pole_lon: str | None = "dlugosc_geo"
    promien_duplikatow_m: float = dedup.PROMIEN_M
    # walidator wierszy pliku (bytes, nazwa_pliku) -> validation.Raport; inny wykaz = inny walidator
    waliduj_plik: Callable[[bytes, str], validation.Raport] = field(default=validation.waliduj_plik, compare=False)
    kompletnosc: Callable[[dict], float] = field(default=schema.kompletnosc, compare=False)

    @property
    def kolumny_wynikowe(self) -> tuple[str, ...]:
        return tuple(self.kolumny_dostawcy) + tuple(self.kolumny)


def _konfiguracja_aed() -> KonfiguracjaWykazu:
    pola = schema.pola()
    return KonfiguracjaWykazu(
        typ="AED",
        tytul_zbioru="Wykaz defibrylatorów AED – wykaz zbiorczy",
        opis=("Zbiorczy wykaz automatycznych defibrylatorów zewnętrznych (AED) tworzony automatycznie przez portal "
              "z zasobów opublikowanych przez dostawców (urzędy, instytucje, firmy) i oznaczonych jako zasób "
              "„Wykazu AED”. Każdy wiersz wskazuje dostawcę, który odpowiada za dane, oraz zasób źródłowy. "
              "Do wykazu trafiają wyłącznie zasoby zgodne z wzorcowym zakresem danych AED. "
              "Kampania #TuBijeAED. PROTOTYP – modyfikacja portalu dane.gov.pl (HackNation 2026)."),
        wlasciciel="Ministerstwo Cyfryzacji",
        kolumny=tuple(p["name"] for p in pola),
        kolumny_wymagane=tuple(p["name"] for p in pola if p.get("x-wymagane") == "TAK"),
        tytul_zasobu="Wykaz defibrylatorów AED",
        opis_zasobu="Scalony wykaz AED ze wszystkich zasobów dostawców zgodnych z wzorcem (aktualizowany automatycznie).",
        prefiks_pliku="wykaz_aed_zbiorczy",
        slowa_kluczowe=("AED", "defibrylator", "#TuBijeAED", "wykaz zbiorczy", "zdrowie"),
    )


WYKAZY: dict[str, KonfiguracjaWykazu] = {"AED": _konfiguracja_aed()}

NAZWY_TYPOW_INSTYTUCJI = {"local": "samorządowa", "state": "rządowa", "private": "prywatna",
                          "other": "inna", "developer": "deweloper"}


def konfiguracja(typ: str) -> KonfiguracjaWykazu:
    konf = WYKAZY.get((typ or "").strip().upper())
    if konf is None:
        raise BladWykazu(422, f"Nieznany typ wykazu „{typ}”. Dostępne: {', '.join(WYKAZY)}.")
    return konf


# ============================================================================ walidacja zasobu (formularz)

def rozszerzenie(nazwa_pliku: str | None) -> str:
    return Path(nazwa_pliku or "").suffix.lower().lstrip(".")


def sprawdz_typ_instytucji(konf: KonfiguracjaWykazu, typ_instytucji: str, nazwa: str = "") -> None:
    """Wzór: validate_institution_type_for_contains_protected_data + komunikat z formularza zasobu."""
    if typ_instytucji not in konf.dozwolone_typy_instytucji:
        dozwolone = ", ".join(NAZWY_TYPOW_INSTYTUCJI.get(t, t) for t in konf.dozwolone_typy_instytucji)
        raise BladWykazu(422, f"Instytucja {('„' + nazwa + '” ') if nazwa else ''}(typ: "
                              f"{NAZWY_TYPOW_INSTYTUCJI.get(typ_instytucji, typ_instytucji)}) nie może publikować zasobów "
                              f"„{konf.tytul_zbioru}”. Dozwolone typy instytucji: {dozwolone}.",
                         {"pole": "wykaz_typ", "typ_instytucji": typ_instytucji,
                          "dozwolone_typy_instytucji": list(konf.dozwolone_typy_instytucji)})


def sprawdz_rozszerzenie(konf: KonfiguracjaWykazu, nazwa_pliku: str | None) -> None:
    """Wzór: _validate_dga_file (DGA_RESOURCE_EXTENSIONS)."""
    if rozszerzenie(nazwa_pliku) not in konf.rozszerzenia:
        raise BladWykazu(422, f"Zasób oznaczony jako zasób wykazu „{konf.tytul_zbioru}” musi być plikiem w formacie "
                              f"{' lub '.join('.' + r for r in konf.rozszerzenia)}.",
                         {"pole": "plik", "dozwolone_rozszerzenia": list(konf.rozszerzenia)})


def brakujace_kolumny(konf: KonfiguracjaWykazu, naglowki: list[str]) -> list[str]:
    obecne = {(h or "").strip().lower() for h in naglowki}
    return [k for k in konf.kolumny_wymagane if k.lower() not in obecne]


def sprawdz_kolumny(konf: KonfiguracjaWykazu, dane: bytes, nazwa_pliku: str) -> list[str]:
    """Wzór: validate_dga_file_columns / validate_dga_df_columns – ale kolejność kolumn jest dowolna
    (uzasadnienie w docstringu modułu). Zwraca nagłówki pliku; brak wymaganych kolumn -> BladWykazu(422)."""
    try:
        naglowki, _, _ = validation.wczytaj_plik(dane, nazwa_pliku)
    except validation.BladPliku as e:
        raise BladWykazu(413 if e.status == 413 else 422, e.komunikat, {"pole": "plik"}) from e
    brak = brakujace_kolumny(konf, naglowki)
    if brak:
        raise BladWykazu(422, f"Zasób oznaczony jako zasób wykazu „{konf.tytul_zbioru}” musi zawierać kolumny wzorca "
                              f"(kolejność dowolna). Brakuje kolumn: {', '.join(brak)}. Pobierz wzorzec: "
                              "/api/asystent/wzorzec.xlsx lub skonwertuj plik w asystencie dostawcy.",
                         {"pole": "plik", "brakujace_kolumny": brak, "wymagane_kolumny": list(konf.kolumny_wymagane)})
    return naglowki


def zasob_wykazu_instytucji(typ: str, instytucja_id: int, wyklucz_zasob_id: int | None = None,
                            con=None) -> dict | None:
    """Opublikowany zasób źródłowy wykazu danej instytucji (wzór: get_dga_resource_for_institution –
    z wykluczeniem zasobów wynikowych wykazu i zasobu o podanym id)."""
    sql = ("SELECT z.id, z.tytul, z.zbior_id FROM zasoby z JOIN zbiory zb ON zb.id = z.zbior_id "
           "WHERE zb.instytucja_id = ? AND z.wykaz_typ = ? AND z.status = 'opublikowany' "
           "AND z.wykaz_zbiorczy IS NULL AND z.id != ? ORDER BY z.id")
    args = (instytucja_id, typ, wyklucz_zasob_id or -1)
    if con is not None:
        wiersze = con.execute(sql, args).fetchall()
    else:
        with baza.transakcja() as c:
            wiersze = c.execute(sql, args).fetchall()
    if len(wiersze) > 1:
        logger.error("Instytucja %s ma %d opublikowanych zasobów wykazu %s", instytucja_id, len(wiersze), typ)
    return dict(wiersze[0]) if wiersze else None


def waliduj_zasob_wykazu(typ: str, *, instytucja: dict, dane: bytes, nazwa_pliku: str,
                         zasob_id: int | None = None, status: str = "opublikowany",
                         potwierdz_zastapienie: bool = False) -> dict:
    """Pełna walidacja zasobu oznaczonego jako zasób wykazu (wzór: ResourceForm.clean dla DGA).

    Kolejność: typ instytucji (422) -> format pliku (422) -> kolumny wzorca (422) -> jeden opublikowany zasób
    wykazu na instytucję (409; przy `potwierdz_zastapienie` flaga zostanie zdjęta z poprzedniego zasobu jak
    w `_remove_dga_flag_from_current_dga_resource_if_needed`) -> wartości wierszy (OK/BLEDY, bez wyjątku).
    Zwraca {walidacja_status, raport, liczba_wierszy, zdejmij_flage_z: id|None}.
    """
    konf = konfiguracja(typ)
    sprawdz_typ_instytucji(konf, instytucja["typ"], instytucja.get("nazwa", ""))
    sprawdz_rozszerzenie(konf, nazwa_pliku)
    sprawdz_kolumny(konf, dane, nazwa_pliku)

    zdejmij = None
    if status == "opublikowany":
        istniejacy = zasob_wykazu_instytucji(konf.typ, instytucja["id"], zasob_id)
        if istniejacy:
            if not potwierdz_zastapienie:
                raise BladWykazu(
                    409,
                    f"Instytucja „{instytucja.get('nazwa', '')}” ma już opublikowany zasób wykazu „{konf.tytul_zbioru}” "
                    f"(„{istniejacy['tytul']}”, id {istniejacy['id']}). Jedna instytucja może mieć tylko jeden taki zasób – "
                    "zaktualizuj istniejący zasób (podmień plik) albo potwierdź zastąpienie "
                    "(pole potwierdz_zastapienie=true zdejmie oznaczenie z poprzedniego zasobu).",
                    {"pole": "wykaz_typ", "istniejacy_zasob_id": istniejacy["id"],
                     "istniejacy_zbior_id": istniejacy["zbior_id"]})
            zdejmij = istniejacy["id"]

    try:
        raport = konf.waliduj_plik(dane, nazwa_pliku)
    except validation.BladPliku as e:
        raise BladWykazu(413 if e.status == 413 else 422, e.komunikat, {"pole": "plik"}) from e
    ok = raport.bledne_wiersze == 0 and raport.poprawne_wiersze > 0 and not raport.bledy
    return {"walidacja_status": "OK" if ok else "BLEDY", "raport": raport.jako_dict(),
            "liczba_wierszy": raport.liczba_wierszy, "zdejmij_flage_z": zdejmij}


# ============================================================================ scalanie (4 kroki)

_blokada = threading.RLock()
_cache: dict[tuple[str, str], tuple[int, list[dict]]] = {}


_ALFABET_PL = "aąbcćdeęfghijklłmnńoópqrsśtuvwxyzźż"
_RANGA_PL = {c: i for i, c in enumerate(_ALFABET_PL)}


def klucz_sortowania_pl(s: str | None) -> tuple:
    """Sortowanie wg polskiego alfabetu (jak ORDER BY title w PostgreSQL z collation pl_PL)."""
    t = (s or "").lower()
    return tuple(_RANGA_PL.get(c, 100 + ord(unicodedata.normalize("NFKD", c)[0])) for c in t)


def _base_url() -> str:
    return os.environ.get("BASE_URL", config.BASE_URL).rstrip("/")


def _zasoby_zrodlowe(konf: KonfiguracjaWykazu, con) -> list[dict]:
    """Krok 1a – wzór: get_all_dga_resources_sorted_by_organizations.

    Zwraca WSZYSTKIE opublikowane zasoby źródłowe wykazu (także z błędami walidacji – trafią do `pominiete`
    z powodem; mcod odfiltrowuje je po cichu prefiltrem data_tasks_last_status=SUCCESS), posortowane po nazwie
    instytucji wg polskiego alfabetu.
    """
    wiersze = con.execute(
        "SELECT z.*, zb.instytucja_id, zb.status AS zbior_status, i.nazwa AS instytucja_nazwa, "
        "i.regon AS instytucja_regon, i.typ AS instytucja_typ "
        "FROM zasoby z JOIN zbiory zb ON zb.id = z.zbior_id JOIN instytucje i ON i.id = zb.instytucja_id "
        "WHERE z.wykaz_typ = ? AND z.status = 'opublikowany' AND z.wykaz_zbiorczy IS NULL",
        (konf.typ,)).fetchall()
    zasoby = [dict(w) for w in wiersze]
    zasoby.sort(key=lambda z: (klucz_sortowania_pl(z["instytucja_nazwa"]), z["id"]))
    return zasoby


def _data_aktualizacji_zasobu(z: dict) -> str:
    return (z.get("data_danych") or z.get("zmodyfikowano") or "")[:10]


def _wczytaj_zasob_zrodlowy(konf: KonfiguracjaWykazu, z: dict) -> list[dict]:
    """Krok 1b – wzór: get_main_dga_source_df. Rzuca BladZasobuZrodlowego z powodem pominięcia."""
    if z["zbior_status"] != "opublikowany":
        raise BladZasobuZrodlowego("zbiór zawierający zasób nie jest opublikowany")
    if z["instytucja_typ"] not in konf.dozwolone_typy_instytucji:
        raise BladZasobuZrodlowego(f"typ instytucji „{z['instytucja_typ']}” nie jest dozwolony dla tego wykazu")
    if z["walidacja_status"] == "BRAK":
        raise BladZasobuZrodlowego("brak pliku do walidacji (nie udało się pobrać zasobu z adresu URL)")
    if z["walidacja_status"] != "OK":
        raport = baza.z_json(z.get("walidacja_raport"), {}) or {}
        n = raport.get("bledne_wiersze")
        raise BladZasobuZrodlowego("zasób nie przeszedł walidacji wzorca"
                                   + (f" ({n} błędnych wierszy)" if n else "") + " – popraw plik i opublikuj ponownie")
    sciezka = baza.sciezka_absolutna(z.get("plik_sciezka"))
    if sciezka is None or not sciezka.exists():                       # MainDGAResourceReadError
        raise BladZasobuZrodlowego("nie można odczytać pliku zasobu (plik nie istnieje)")
    dane = sciezka.read_bytes()
    nazwa = z.get("nazwa_pliku") or sciezka.name
    try:
        naglowki, _, _ = validation.wczytaj_plik(dane, nazwa)
        brak = brakujace_kolumny(konf, naglowki)                      # MainDGAMissingRequiredColumnError
        if brak:
            raise BladZasobuZrodlowego(f"brak wymaganych kolumn: {', '.join(brak)}")
        raport = konf.waliduj_plik(dane, nazwa)
    except validation.BladPliku as e:                                 # MainDGAResourceReadError
        raise BladZasobuZrodlowego(f"nie można odczytać pliku zasobu: {e.komunikat}") from e
    if raport.bledne_wiersze or raport.bledy:                         # MainDGAEmptyRequiredValuesError
        raise BladZasobuZrodlowego(f"zasób zawiera {raport.bledne_wiersze or len(raport.bledy)} błędnych wierszy")
    if not raport.rekordy:
        raise BladZasobuZrodlowego("zasób nie zawiera wierszy z danymi")
    return raport.rekordy


def _zbuduj_wykaz(konf: KonfiguracjaWykazu, zasoby: list[dict]) -> tuple[pd.DataFrame, list[dict], list[dict], list[dict]]:
    """Krok 1c – wzór: create_main_dga_df. Zwraca (df, rekordy z instytucja_id, uwzglednione, pominiete)."""
    rekordy: list[dict] = []
    uwzglednione: list[dict] = []
    pominiete: list[dict] = []
    base = _base_url()
    for z in zasoby:
        wpis = {"instytucja": z["instytucja_nazwa"], "instytucja_id": z["instytucja_id"], "zasob_id": z["id"],
                "zbior_id": z["zbior_id"], "tytul_zasobu": z["tytul"]}
        try:
            wiersze = _wczytaj_zasob_zrodlowy(konf, z)
        except BladZasobuZrodlowego as e:
            logger.warning("Pominięto zasób %s (%s): %s", z["id"], z["instytucja_nazwa"], e)
            pominiete.append({**wpis, "powod": str(e)})
            continue
        dostawca = {
            "nazwa_dostawcy": z["instytucja_nazwa"],
            "regon_dostawcy": z["instytucja_regon"],
            "typ_dostawcy": z["instytucja_typ"],
            "id_zasobu_zrodlowego": z["id"],
            "url_zasobu_zrodlowego": f"{base}/api/1.4/resources/{z['id']}",
            "data_aktualizacji_zasobu": _data_aktualizacji_zasobu(z),
        }
        for w in wiersze:
            rek = {**dostawca, **{k: w.get(k) for k in konf.kolumny}}
            rek["instytucja_id"] = z["instytucja_id"]
            rekordy.append(rek)
        uwzglednione.append({**wpis, "rekordy": len(wiersze)})
    logger.info("Wykaz %s: wczytano %d/%d zasobów, %d rekordów", konf.typ, len(uwzglednione), len(zasoby), len(rekordy))
    df = pd.DataFrame([{k: r.get(k) for k in konf.kolumny_wynikowe} for r in rekordy],
                      columns=list(konf.kolumny_wynikowe))
    return df, rekordy, uwzglednione, pominiete


def _raport_jakosci(konf: KonfiguracjaWykazu, rekordy: list[dict]) -> dict:
    """Potencjalne duplikaty między dostawcami (< promień) – tylko informacja, nic nie usuwamy."""
    dupl = []
    if konf.pole_lat and konf.pole_lon:
        punkty = [{**r, "szerokosc_geo": r.get(konf.pole_lat), "dlugosc_geo": r.get(konf.pole_lon)} for r in rekordy]
        for i, j, d in dedup.bliskie_pary_miedzy_grupami(punkty, "instytucja_id", konf.promien_duplikatow_m):
            a, b = rekordy[i], rekordy[j]
            dupl.append({
                "odleglosc_m": round(d, 1),
                "a": {"dostawca": a["nazwa_dostawcy"], "instytucja_id": a["instytucja_id"],
                      "zasob_id": a["id_zasobu_zrodlowego"], "id_aed": a.get("id_aed")},
                "b": {"dostawca": b["nazwa_dostawcy"], "instytucja_id": b["instytucja_id"],
                      "zasob_id": b["id_zasobu_zrodlowego"], "id_aed": b.get("id_aed")},
                "komunikat": (f"Urządzenia „{a.get('id_aed')}” ({a['nazwa_dostawcy']}) i „{b.get('id_aed')}” "
                              f"({b['nazwa_dostawcy']}) są {round(d)} m od siebie – możliwe, że to to samo urządzenie. "
                              "Oba pozostają w wykazie; dostawcy powinni to wyjaśnić."),
            })
    return {"potencjalne_duplikaty": dupl, "liczba_potencjalnych_duplikatow": len(dupl),
            "promien_m": konf.promien_duplikatow_m}


def _styl_xlsx(sciezka: Path, arkusz: str, kolumny: tuple[str, ...]) -> None:
    """Wzór: add_style_to_main_dga_excel_file – zamrożony pierwszy wiersz, bez obramowań, wyrównanie do lewej,
    stałe szerokości kolumn; dodatkowo pogrubiony nagłówek i autofiltr."""
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.utils import get_column_letter

    wb = load_workbook(sciezka)
    ws = wb[arkusz]
    ws.freeze_panes = "A2"
    bez = Border(left=Side(style=None), right=Side(style=None), top=Side(style=None), bottom=Side(style=None))
    lewo = Alignment(horizontal="left")
    for wiersz in ws.iter_rows():
        for c in wiersz:
            c.border = bez
            c.alignment = lewo
    for c in ws[1]:
        c.font = Font(bold=True)
    szerokie = {"nazwa_dostawcy": 36, "url_zasobu_zrodlowego": 40, "nazwa_dysponenta": 36,
                "lokalizacja_szczegolowa": 50, "instrukcja_dostepu": 40, "kontakt_dysponenta": 28}
    for i, k in enumerate(kolumny, start=1):
        ws.column_dimensions[get_column_letter(i)].width = szerokie.get(k, max(12, min(len(k) + 2, 26)))
    if ws.max_row >= 1 and kolumny:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(kolumny))}{max(ws.max_row, 1)}"
    wb.save(sciezka)


def _wartosc_json(v):
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    return v


def _zapisz_pliki(konf: KonfiguracjaWykazu, df: pd.DataFrame, rekordy: list[dict], katalog: Path,
                  znacznik: str) -> dict[str, Path]:
    """Krok 2a – wzór: create_main_dga_file (+ CSV i GeoJSON). Zwraca {format: ścieżka}."""
    katalog.mkdir(parents=True, exist_ok=True)
    rdzen = f"{konf.prefiks_pliku}_{znacznik}"
    pliki = {"xlsx": katalog / f"{rdzen}.xlsx", "csv": katalog / f"{rdzen}.csv", "geojson": katalog / f"{rdzen}.geojson"}

    df.to_excel(pliki["xlsx"], sheet_name=konf.nazwa_arkusza, index=False, engine="openpyxl")
    _styl_xlsx(pliki["xlsx"], konf.nazwa_arkusza, konf.kolumny_wynikowe)

    with open(pliki["csv"], "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(konf.kolumny_wynikowe)
        for r in rekordy:
            w.writerow(["" if r.get(k) is None else r.get(k) for k in konf.kolumny_wynikowe])

    cechy = []
    for r in rekordy:
        lat, lon = (r.get(konf.pole_lat), r.get(konf.pole_lon)) if konf.pole_lat else (None, None)
        if lat is None or lon is None:
            continue
        cechy.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                      "properties": {k: _wartosc_json(r.get(k)) for k in konf.kolumny_wynikowe}})
    geo = {"type": "FeatureCollection", "name": konf.tytul_zbioru, "features": cechy}
    pliki["geojson"].write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")

    # wewnętrzna kopia rekordów (z instytucja_id) – szybki odczyt dla API/mapy, nie jest zasobem portalu
    (katalog / "rekordy.json").write_text(
        json.dumps([{k: _wartosc_json(v) for k, v in r.items()} for r in rekordy], ensure_ascii=False), encoding="utf-8")
    return pliki


def _instytucja_wlasciciela(konf: KonfiguracjaWykazu, con) -> dict:
    w = con.execute("SELECT * FROM instytucje WHERE nazwa = ? ORDER BY id LIMIT 1", (konf.wlasciciel,)).fetchone()
    if w is None:   # wzór: create_main_dga_dataset -> ObjectDoesNotExist
        raise BladWykazu(500, f"Nie znaleziono instytucji właściciela wykazu („{konf.wlasciciel}”) – "
                              "nie można utworzyć zbioru wykazu zbiorczego.")
    return dict(w)


def _utworz_zasoby_wykazu(konf: KonfiguracjaWykazu, pliki: dict[str, Path], liczba: int, utworzone: dict) -> tuple[int, dict]:
    """Krok 2b – wzór: create_main_dga_resource_with_dataset (+ create_main_dga_dataset).

    Tworzy zbiór wykazu w instytucji właściciela, jeśli nie istnieje, oraz NOWE zasoby (XLSX/CSV/GeoJSON)
    ze statusem walidacji 'BRAK' (oczekuje na krok 3). Metadane zasobu głównego przejmuje z poprzedniego.
    Identyfikatory utworzonych obiektów trafiają do `utworzone` (do sprzątania przy błędzie).
    """
    teraz = baza.teraz_iso()
    with baza.transakcja() as con:
        zb = con.execute("SELECT * FROM zbiory WHERE wykaz_zbiorczy = ? ORDER BY id LIMIT 1", (konf.typ,)).fetchone()
        if zb is None:
            wlasc = _instytucja_wlasciciela(konf, con)
            cur = con.execute(
                "INSERT INTO zbiory (instytucja_id, tytul, opis, kategoria, licencja, czestotliwosc, slowa_kluczowe, "
                "status, zrodlo, wykaz_zbiorczy, utworzono, zmodyfikowano) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (wlasc["id"], konf.tytul_zbioru, konf.opis, konf.kategoria, konf.licencja, "daily",
                 baza.do_json(list(konf.slowa_kluczowe)), "opublikowany", "system", konf.typ, teraz, teraz))
            zbior_id = cur.lastrowid
            utworzone["zbior_id"] = zbior_id
        else:
            zbior_id = zb["id"]
            con.execute("UPDATE zbiory SET zmodyfikowano = ? WHERE id = ?", (teraz, zbior_id))
        poprzedni = con.execute(
            "SELECT tytul, opis FROM zasoby WHERE zbior_id = ? AND wykaz_zbiorczy = ? AND format = 'xlsx' "
            "ORDER BY id DESC LIMIT 1", (zbior_id, konf.typ)).fetchone()
        tytul_gl = poprzedni["tytul"] if poprzedni else f"{konf.tytul_zasobu} (XLSX)"
        opis_gl = poprzedni["opis"] if poprzedni else konf.opis_zasobu
        ids = {}
        for fmt, p in pliki.items():
            tytul = tytul_gl if fmt == "xlsx" else f"{konf.tytul_zasobu} ({fmt.upper() if fmt != 'geojson' else 'GeoJSON'})"
            opis = opis_gl if fmt == "xlsx" else konf.opis_zasobu
            cur = con.execute(
                "INSERT INTO zasoby (zbior_id, tytul, opis, format, plik_sciezka, nazwa_pliku, wykaz_zbiorczy, status, "
                "walidacja_status, liczba_wierszy, data_danych, utworzono, zmodyfikowano) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (zbior_id, tytul, opis, fmt, baza.sciezka_wzgledna(p), p.name, konf.typ, "opublikowany", "BRAK",
                 liczba, teraz[:10], teraz, teraz))
            ids[fmt] = cur.lastrowid
            utworzone["zasoby"].append(cur.lastrowid)
    return zbior_id, ids


def _zweryfikuj_wynik(konf: KonfiguracjaWykazu, pliki: dict[str, Path], liczba: int, ids: dict) -> None:
    """Krok 3 – wzór: check_all_resource_validations_status. Ponowny odczyt wygenerowanych plików."""
    from openpyxl import load_workbook

    oczekiwane = list(konf.kolumny_wynikowe)
    wb = load_workbook(pliki["xlsx"], read_only=True)
    try:
        wiersze = list(wb[konf.nazwa_arkusza].iter_rows(values_only=True))
    finally:
        wb.close()
    if not wiersze or list(wiersze[0]) != oczekiwane:
        raise BladWeryfikacjiWykazu("plik XLSX ma nieprawidłowy nagłówek")
    if len(wiersze) - 1 != liczba:
        raise BladWeryfikacjiWykazu(f"plik XLSX ma {len(wiersze) - 1} wierszy zamiast {liczba}")
    with open(pliki["csv"], encoding="utf-8", newline="") as f:
        cz = list(csv.reader(f))
    if not cz or cz[0] != oczekiwane or len(cz) - 1 != liczba:
        raise BladWeryfikacjiWykazu("plik CSV ma nieprawidłowy nagłówek lub liczbę wierszy")
    geo = json.loads(pliki["geojson"].read_text(encoding="utf-8"))
    if geo.get("type") != "FeatureCollection" or len(geo.get("features", [])) > liczba:
        raise BladWeryfikacjiWykazu("plik GeoJSON jest nieprawidłowy")
    with baza.transakcja() as con:
        for fmt, zid in ids.items():
            con.execute("UPDATE zasoby SET walidacja_status = 'OK' WHERE id = ?", (zid,))


def _zapisz_info_i_usun_poprzedni(konf, *, zbior_id, ids, pliki, katalog, liczba, uwzglednione, pominiete,
                                  raport, czas_ms) -> int:
    """Krok 4 – wzór: update_or_create_aggr_dga_info_and_delete_old_main_dga."""
    poprzedni = _ostatni_ok(konf.typ)
    with baza.transakcja() as con:
        cur = con.execute(
            "INSERT INTO wykazy_info (typ, zbior_id, zasob_id, zasoby, pliki, katalog, utworzono, liczba_rekordow, "
            "liczba_dostawcow, uwzglednione, pominiete, raport_jakosci, status, komunikat, czas_ms) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (konf.typ, zbior_id, ids["xlsx"], baza.do_json(ids),
             baza.do_json({k: baza.sciezka_wzgledna(p) for k, p in pliki.items()}), baza.sciezka_wzgledna(katalog),
             baza.teraz_iso(), liczba, len(uwzglednione), baza.do_json(uwzglednione), baza.do_json(pominiete),
             baza.do_json(raport), "OK",
             f"Scalono {liczba} rekordów od {len(uwzglednione)} dostawców; pominięto zasobów: {len(pominiete)}.",
             czas_ms))
        info_id = cur.lastrowid
        # usunięcie poprzednich zasobów wynikowych (wszystkich spoza nowego zestawu)
        stare = con.execute("SELECT id, plik_sciezka FROM zasoby WHERE wykaz_zbiorczy = ? AND id NOT IN (?,?,?)",
                            (konf.typ, ids["xlsx"], ids["csv"], ids["geojson"])).fetchall()
        for s in stare:
            con.execute("DELETE FROM zasoby WHERE id = ?", (s["id"],))
    for s in stare:
        _usun_plik(s["plik_sciezka"])
    if poprzedni and poprzedni.get("katalog") and poprzedni["katalog"] != baza.sciezka_wzgledna(katalog):
        _usun_katalog(poprzedni["katalog"])
    return info_id


def _usun_plik(wzgl: str | None) -> None:
    p = baza.sciezka_absolutna(wzgl)
    try:
        if p and p.exists():
            p.unlink()
    except OSError as e:
        logger.error("Nie usunięto pliku %s: %s", p, e)


def _usun_katalog(wzgl: str | Path | None) -> None:
    if not wzgl:
        return
    p = wzgl if isinstance(wzgl, Path) else baza.sciezka_absolutna(str(wzgl))
    try:
        media = baza.katalog_media().resolve()
        if p and p.exists() and media in p.resolve().parents:
            shutil.rmtree(p)
    except OSError as e:
        logger.error("Nie usunięto katalogu %s: %s", p, e)


def _posprzataj(utworzone: dict) -> None:
    """Wzór: clean_up_after_main_dga_resource_creation(exception_occurred=True)."""
    try:
        with baza.transakcja() as con:
            for zid in utworzone.get("zasoby", []):
                con.execute("DELETE FROM zasoby WHERE id = ?", (zid,))
            if utworzone.get("zbior_id"):
                con.execute("DELETE FROM zasoby WHERE zbior_id = ?", (utworzone["zbior_id"],))
                con.execute("DELETE FROM zbiory WHERE id = ?", (utworzone["zbior_id"],))
    except Exception as e:  # noqa: BLE001 – sprzątanie nie może maskować pierwotnego błędu
        logger.error("Sprzątanie po nieudanym scaleniu nie powiodło się: %s", e)
    _usun_katalog(utworzone.get("katalog"))


def utworz_wykaz_zbiorczy(typ: str = "AED") -> dict:
    """Scalenie (4 kroki jak create_main_dga_resource_task). Zwraca wpis wykazy_info (status OK albo BLAD).

    1. zebranie opublikowanych zasobów źródłowych (posortowanych po instytucji) i budowa tabeli wykazu,
    2. zapis XLSX/CSV/GeoJSON + utworzenie zbioru (jeśli trzeba) i nowych zasobów w instytucji właściciela,
    3. weryfikacja wygenerowanych plików,
    4. zapis wpisu w wykazy_info, usunięcie poprzednich zasobów i plików wykazu.
    Przy błędzie: sprzątanie utworzonych obiektów i plików, wpis BLAD; poprzedni wykaz pozostaje aktualny.
    """
    konf = konfiguracja(typ)
    with _blokada:
        start = time.monotonic()
        utworzone: dict = {"zasoby": [], "zbior_id": None, "katalog": None}
        uwzglednione: list[dict] = []
        pominiete: list[dict] = []
        try:
            logger.info("Wykaz %s – krok 1/4: zbieranie zasobów źródłowych.", konf.typ)
            with baza.transakcja() as con:
                zasoby = _zasoby_zrodlowe(konf, con)
            df, rekordy, uwzglednione, pominiete = _zbuduj_wykaz(konf, zasoby)
            raport = _raport_jakosci(konf, rekordy)

            logger.info("Wykaz %s – krok 2/4: zapis plików i zasobów.", konf.typ)
            znacznik = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            katalog = baza.katalog_media() / "wykazy" / konf.typ / znacznik
            utworzone["katalog"] = katalog
            pliki = _zapisz_pliki(konf, df, rekordy, katalog, znacznik[:15])
            zbior_id, ids = _utworz_zasoby_wykazu(konf, pliki, len(rekordy), utworzone)

            logger.info("Wykaz %s – krok 3/4: weryfikacja wyniku.", konf.typ)
            _zweryfikuj_wynik(konf, pliki, len(rekordy), ids)

            logger.info("Wykaz %s – krok 4/4: zapis wykazy_info i usunięcie poprzedniego wykazu.", konf.typ)
            info_id = _zapisz_info_i_usun_poprzedni(
                konf, zbior_id=zbior_id, ids=ids, pliki=pliki, katalog=katalog, liczba=len(rekordy),
                uwzglednione=uwzglednione, pominiete=pominiete, raport=raport,
                czas_ms=int((time.monotonic() - start) * 1000))
        except Exception as e:  # noqa: BLE001 – każdy błąd: sprzątanie i wpis BLAD (jak w tasks/dga.py)
            logger.exception("Scalanie wykazu %s nie powiodło się", konf.typ)
            _posprzataj(utworzone)
            komunikat = e.komunikat if isinstance(e, BladPortalu) else f"{e.__class__.__name__}: {e}"
            with baza.transakcja() as con:
                cur = con.execute(
                    "INSERT INTO wykazy_info (typ, utworzono, uwzglednione, pominiete, status, komunikat, czas_ms) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (konf.typ, baza.teraz_iso(), baza.do_json(uwzglednione), baza.do_json(pominiete), "BLAD",
                     f"Scalenie nie powiodło się – poprzedni wykaz pozostaje aktualny. Przyczyna: {komunikat}",
                     int((time.monotonic() - start) * 1000)))
                info_id = cur.lastrowid
        _cache.pop((str(config.get_db_path()), konf.typ), None)
        return _info(info_id)


# ============================================================================ odczyt

def _wiersz_info(w) -> dict:
    d = dict(w)
    for k, dom in (("uwzglednione", []), ("pominiete", []), ("raport_jakosci", {}), ("zasoby", {}), ("pliki", {})):
        d[k] = baza.z_json(d.get(k), dom)
    d["pliki"] = {k: str(baza.sciezka_absolutna(v)) for k, v in (d["pliki"] or {}).items()}
    d.pop("katalog", None)
    return d


def _info(info_id: int) -> dict:
    with baza.transakcja() as con:
        return _wiersz_info(con.execute("SELECT * FROM wykazy_info WHERE id = ?", (info_id,)).fetchone())


def _ostatni_ok(typ: str) -> dict | None:
    with baza.transakcja() as con:
        w = con.execute("SELECT * FROM wykazy_info WHERE typ = ? AND status = 'OK' ORDER BY id DESC LIMIT 1",
                        (typ,)).fetchone()
    return dict(w) if w else None


def aktualny_wykaz(typ: str = "AED") -> dict | None:
    """Ostatnie udane scalenie: {id, typ, zbior_id, zasob_id, zasoby: {xlsx, csv, geojson} (id zasobów),
    utworzono, liczba_rekordow, liczba_dostawcow, pliki: {xlsx, csv, geojson} (ścieżki absolutne),
    uwzglednione: [...], pominiete: [...], raport_jakosci, status, komunikat} lub None (wzór: get_main_dga_resource)."""
    typ = konfiguracja(typ).typ
    with baza.transakcja() as con:
        w = con.execute("SELECT * FROM wykazy_info WHERE typ = ? AND status = 'OK' ORDER BY id DESC LIMIT 1",
                        (typ,)).fetchone()
    return _wiersz_info(w) if w else None


def historia(typ: str = "AED", limit: int = 50) -> list[dict]:
    """Wszystkie uruchomienia scalania (najnowsze pierwsze), także nieudane."""
    typ = konfiguracja(typ).typ
    aktualny = aktualny_wykaz(typ)
    with baza.transakcja() as con:
        w = con.execute("SELECT * FROM wykazy_info WHERE typ = ? ORDER BY id DESC LIMIT ?", (typ, limit)).fetchall()
    wynik = [_wiersz_info(x) for x in w]
    for x in wynik:
        x["aktualny"] = bool(aktualny and x["id"] == aktualny["id"])
    return wynik


def _rekordy_z_cache(typ: str) -> list[dict]:
    with baza.transakcja() as con:
        w = con.execute("SELECT id, katalog FROM wykazy_info WHERE typ = ? AND status = 'OK' ORDER BY id DESC LIMIT 1",
                        (typ,)).fetchone()
    if w is None:
        return []
    klucz = (str(config.get_db_path()), typ)
    trafienie = _cache.get(klucz)
    if trafienie and trafienie[0] == w["id"]:
        return trafienie[1]
    sciezka = baza.sciezka_absolutna(w["katalog"]) / "rekordy.json"
    try:
        rekordy = json.loads(sciezka.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.error("Nie można odczytać rekordów wykazu %s: %s", typ, e)
        rekordy = []
    _cache[klucz] = (w["id"], rekordy)
    return rekordy


def rekordy_wykazu(typ: str = "AED", *, wojewodztwo: str | None = None, instytucja_id: int | None = None,
                   bbox: tuple[float, float, float, float] | None = None) -> list[dict]:
    """Wiersze aktualnego wykazu (kolumny wykazu z docs/PROTOTYP.md + `instytucja_id`).

    Odczyt z pamięci podręcznej unieważnianej przy każdej przebudowie (klucz = id wpisu wykazy_info).
    bbox = (minLon, minLat, maxLon, maxLat).
    """
    konf = konfiguracja(typ)
    wynik = []
    woj = wojewodztwo.strip().lower() if wojewodztwo else None
    for r in _rekordy_z_cache(konf.typ):
        if woj and (r.get("wojewodztwo") or "").lower() != woj:
            continue
        if instytucja_id is not None and r.get("instytucja_id") != int(instytucja_id):
            continue
        if bbox is not None:
            lat, lon = r.get(konf.pole_lat), r.get(konf.pole_lon)
            if lat is None or lon is None or not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
                continue
        wynik.append(dict(r))
    return wynik


def wyczysc_cache() -> None:
    _cache.clear()


__all__ = ["BladPortalu", "BladWykazu", "KonfiguracjaWykazu", "WYKAZY", "konfiguracja", "waliduj_zasob_wykazu",
           "zasob_wykazu_instytucji", "utworz_wykaz_zbiorczy", "aktualny_wykaz", "historia", "rekordy_wykazu"]
