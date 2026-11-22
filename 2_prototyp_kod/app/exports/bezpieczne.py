"""Ochrona przed wstrzykiwaniem formuł (CSV/XLSX injection, OWASP). Właściciel: API.

Wartość tekstowa zaczynająca się od `=`, `+`, `-`, `@`, tabulatora albo CR jest w Excelu/LibreOffice
interpretowana jako formuła. Zabezpieczenie: prefiks apostrofu `'` (zalecenie OWASP).
Nie ruszamy liczb (int/float) ani tekstów będących zwykłą liczbą ze znakiem (np. `-1` w `kondygnacja`, `-12.5`).

Użycie w CSV:   csv.writer(...).writerow([bezpieczna_komorka(v) for v in wiersz])
Użycie w XLSX:  ws.cell(value=bezpieczna_komorka(v)) i dodatkowo, dla tekstu, `cell.data_type = "s"`
                (openpyxl zamienia string zaczynający się od `=` na formułę – apostrof + data_type='s' to blokuje).
"""
from __future__ import annotations

import math
import re

ZNAKI_FORMULY = ("=", "+", "-", "@", "\t", "\r")
_LICZBA = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")


def bezpieczna_komorka(v):
    """Zwraca wartość bezpieczną dla komórki arkusza/CSV. None -> "", float nieskończony -> "".

    Liczby (int, float, bool) przechodzą bez zmian; tekst groźny dostaje prefiks `'`.
    """
    if v is None:
        return ""
    if isinstance(v, float) and not math.isfinite(v):
        return ""
    if not isinstance(v, str):
        return v
    if v.startswith(ZNAKI_FORMULY) and not _LICZBA.match(v):
        return "'" + v
    return v
