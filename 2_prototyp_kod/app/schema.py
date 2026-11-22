"""Dostęp do kontraktu danych 1_wzorzec_danych/aed_schema.json. Właściciel: Backend.

Cała walidacja i wyliczanie kompletności są sterowane tym plikiem (jedno źródło prawdy).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from .config import SCHEMA_PATH

WARUNEK_RE = re.compile(r"gdy\s+(\w+)\s*(!=|==|=)\s*'([^']*)'")


@lru_cache(maxsize=1)
def get_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def pola() -> list[dict]:
    return get_schema()["fields"]


def pola_systemowe() -> list[dict]:
    return get_schema().get("x-pola-systemowe", [])


def nazwy_pol() -> list[str]:
    return [p["name"] for p in pola()]


def nazwy_systemowe() -> list[str]:
    return [p["name"] for p in pola_systemowe()]


def nazwy_wszystkich() -> list[str]:
    return nazwy_pol() + nazwy_systemowe()


def pole(nazwa: str) -> dict | None:
    for p in pola() + pola_systemowe():
        if p["name"] == nazwa:
            return p
    return None


def slownik(nazwa: str) -> list[str] | None:
    p = pole(nazwa)
    return (p or {}).get("constraints", {}).get("enum")


def priorytet_zrodel() -> list[str]:
    return list(get_schema().get("x-priorytet-zrodel", []))


def klucz_glowny() -> list[str]:
    return list(get_schema().get("primaryKey", []))


def warunek(p: dict) -> tuple[str, str, str] | None:
    """Parsuje `x-warunek` ("wymagane, gdy pole != 'wartosc'") -> (pole, operator, wartosc)."""
    tekst = p.get("x-warunek")
    if not tekst:
        return None
    m = WARUNEK_RE.search(tekst)
    if not m:
        return None
    op = "==" if m.group(2) in ("=", "==") else "!="
    return m.group(1), op, m.group(3)


def warunek_aktywny(p: dict, rekord: dict) -> bool:
    """Czy pole WARUNKOWO jest w danym rekordzie wymagane.

    Warunek jest aktywny tylko wtedy, gdy pole, od którego zależy, jest wypełnione
    (brak tego pola to osobny błąd „wymagane”).
    """
    w = warunek(p)
    if w is None:
        return False
    nazwa, op, wartosc = w
    v = rekord.get(nazwa)
    if v is None or str(v).strip() == "":
        return False
    return (str(v) == wartosc) if op == "==" else (str(v) != wartosc)


def pole_wypelnione(v) -> bool:
    return v is not None and not (isinstance(v, str) and v.strip() == "")


def kompletnosc(rekord: dict) -> float:
    """Odsetek wypełnionych pól x-wymagane ∈ {TAK, ZALECANE, WARUNKOWO (gdy warunek aktywny)}."""
    licz = 0
    wypelnione = 0
    for p in pola():
        poziom = p.get("x-wymagane")
        if poziom in ("TAK", "ZALECANE"):
            pass
        elif poziom == "WARUNKOWO" and warunek_aktywny(p, rekord):
            pass
        else:
            continue
        licz += 1
        if pole_wypelnione(rekord.get(p["name"])):
            wypelnione += 1
    return round(wypelnione / licz, 4) if licz else 0.0
