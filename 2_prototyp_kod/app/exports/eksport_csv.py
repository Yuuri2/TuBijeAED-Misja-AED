"""Eksport CSV (UTF-8, RFC 4180) dla dane.gov.pl. Właściciel: API."""
from __future__ import annotations

import csv
import io
import math

from .kolumny import do_publikacji, kolumny_eksportu


def _wartosc(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        if not math.isfinite(v):
            return ""
        return repr(v)                     # pełna precyzja, kropka dziesiętna (niezależnie od locale)
    return str(v)


def do_csv(rekordy: list[dict]) -> str:
    """Rekordy -> tekst CSV. Nagłówek zawsze obecny (także dla pustej listy)."""
    kolumny = kolumny_eksportu()
    bufor = io.StringIO()
    w = csv.writer(bufor, lineterminator="\r\n")
    w.writerow(kolumny)
    for r in do_publikacji(rekordy):
        w.writerow([_wartosc(r.get(k)) for k in kolumny])
    return bufor.getvalue()
