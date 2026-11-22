"""Czytniki plików zasobów (CSV / XLSX / JSON / GeoJSON) -> list[dict] surowych wierszy. Właściciel: API.

Każdy wiersz to słownik {nazwa_kolumny_ze_źródła: wartość}. Dla GeoJSON i JSON z geometrią
dodawany jest klucz `_geometria` (obiekt GeoJSON geometry). Mapowanie na pola schematu
odbywa się dopiero w danegov.py wg konfiguracji z mapowania_danegov.py.
"""
from __future__ import annotations

import csv
import io
import json

from .wspolne import tekst

MAKS_WIERSZY = 50_000


class BladFormatu(ValueError):
    """Zasobu nie da się odczytać jako tabeli (zły format, zepsuty plik)."""


def dekoduj(dane: bytes) -> str:
    for kodowanie in ("utf-8-sig", "cp1250"):
        try:
            return dane.decode(kodowanie)
        except UnicodeDecodeError:
            continue
    return dane.decode("latin-1")


def _parsuj_csv(tekst_csv: str) -> list[list[str]]:
    probka = tekst_csv[:5000]
    try:
        dialekt = csv.Sniffer().sniff(probka, delimiters=",;\t|")
        separator = dialekt.delimiter
    except csv.Error:
        separator = max(",;\t|", key=lambda z: probka.splitlines()[0].count(z) if probka else 0)
    return [w for w in csv.reader(io.StringIO(tekst_csv), delimiter=separator, skipinitialspace=True)
            if any(c.strip() for c in w)]


def _rozwin_zawiniete(wiersze: list[list[str]]) -> list[list[str]]:
    """Naprawa „CSV w CSV”: cały wiersz w jednej komórce (tak eksportuje m.in. Marki, zbiór 4955).

    Komórka: 52.32, 21.10,"Defibrylator","Urząd"  ->  ['52.32', '21.10', 'Defibrylator', 'Urząd'].
    """
    if not wiersze or any(len(w) != 1 for w in wiersze) or "," not in wiersze[0][0]:
        return wiersze
    return [next(csv.reader([w[0]], skipinitialspace=True)) for w in wiersze]


def _do_slownikow(wiersze: list[list]) -> list[dict]:
    if not wiersze:
        return []
    naglowek = [str(h).strip() if h is not None else f"kolumna_{i + 1}" for i, h in enumerate(wiersze[0])]
    wynik = []
    for w in wiersze[1:MAKS_WIERSZY + 1]:
        if not any(tekst(c) for c in w):
            continue
        wynik.append({naglowek[i]: (w[i] if i < len(w) else None) for i in range(len(naglowek))})
    return wynik


def czytaj_csv(dane: bytes) -> list[dict]:
    return _do_slownikow(_rozwin_zawiniete(_parsuj_csv(dekoduj(dane))))


def czytaj_xlsx(dane: bytes) -> list[dict]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(dane), read_only=True, data_only=True)
    except Exception as e:  # zły zip, zaszyfrowany plik itp.
        raise BladFormatu(f"nie można otworzyć arkusza XLSX: {e}") from e
    ws = wb.worksheets[0]
    wiersze = [["" if c is None else (c if isinstance(c, (int, float)) else str(c)) for c in w]
               for w in ws.iter_rows(values_only=True)]
    wiersze = [w for w in wiersze if any(tekst(c) for c in w)]
    # arkusz z jedną kolumną „CSV w komórce” traktujemy jak CSV
    if wiersze and all(len([c for c in w if tekst(c)]) == 1 for w in wiersze) and "," in str(wiersze[0][0]):
        wiersze = _rozwin_zawiniete([[str(next(c for c in w if tekst(c)))] for w in wiersze])
    return _do_slownikow(wiersze)


def _z_cechy(obiekt: dict) -> dict:
    """Feature GeoJSON (także bez pola "type", jak w API Warszawy) -> płaski wiersz + _geometria."""
    wiersz = dict(obiekt.get("properties") or {})
    wiersz["_geometria"] = obiekt.get("geometry")
    return wiersz


def czytaj_json(dane: bytes) -> list[dict]:
    try:
        obj = json.loads(dekoduj(dane))
    except json.JSONDecodeError as e:
        raise BladFormatu(f"niepoprawny JSON: {e}") from e
    if isinstance(obj, dict):
        if isinstance(obj.get("features"), list):
            obj = obj["features"]
        else:
            # typowe opakowania API: {"data": [...]}, {"result": {"records": [...]}}, {"records": [...]}
            for klucz in ("data", "records", "result", "items", "elements"):
                v = obj.get(klucz)
                if isinstance(v, dict):
                    v = v.get("records") or v.get("data") or v.get("items")
                if isinstance(v, list):
                    obj = v
                    break
    if not isinstance(obj, list):
        raise BladFormatu("JSON nie zawiera listy rekordów")
    wynik = []
    for e in obj[:MAKS_WIERSZY]:
        if not isinstance(e, dict):
            continue
        if "geometry" in e and ("properties" in e or e.get("type") == "Feature"):
            wynik.append(_z_cechy(e))
        elif isinstance(e.get("attributes"), dict):   # JSON:API
            wynik.append(dict(e["attributes"], id=e.get("id")))
        else:
            wynik.append(e)
    return wynik


CZYTNIKI = {
    "csv": czytaj_csv,
    "xlsx": czytaj_xlsx,
    "json": czytaj_json,
    "geojson": czytaj_json,
}


def czytaj(dane: bytes, format_: str) -> list[dict]:
    f = (format_ or "").lower().strip(".")
    if f not in CZYTNIKI:
        raise BladFormatu(f"format „{format_}” nieobsługiwany (obsługiwane: {', '.join(CZYTNIKI)})")
    if f in ("json", "geojson", "csv") and dane[:200].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise BladFormatu("zamiast danych serwer zwrócił stronę HTML (zasób wskazuje stronę katalogu, nie plik)")
    return CZYTNIKI[f](dane)
