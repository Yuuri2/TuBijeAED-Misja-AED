"""Kolumny i filtry wspólne dla eksportów. Właściciel: API."""
from __future__ import annotations

from .. import schema

# Kolumny systemowe dołączane po polach `fields` (kolejność wg docs/PROTOTYP.md).
KOLUMNY_ZRODLA = ["zrodlo_typ", "zrodlo_nazwa", "zrodlo_url", "licencja", "status_weryfikacji"]
OTWARTE_LICENCJE = ("CC0 1.0", "CC BY 4.0")


def kolumny_eksportu() -> list[str]:
    """Kolejność = `fields` z aed_schema.json + KOLUMNY_ZRODLA."""
    return schema.nazwy_pol() + KOLUMNY_ZRODLA


def do_publikacji(rekordy: list[dict]) -> list[dict]:
    """Tylko rekordy, które wolno opublikować w dane.gov.pl: licencja CC0/CC BY, nie OSM, nie duplikat.

    Repozytorium filtruje to samo (`tylko_otwarte_licencje=True`), ale eksport nie może polegać
    wyłącznie na wywołującym – rekord ODbL w harvesterze byłby naruszeniem licencji.
    """
    return [r for r in rekordy
            if r.get("licencja") in OTWARTE_LICENCJE and r.get("zrodlo_typ") != "OSM" and not r.get("duplikat_z")]
