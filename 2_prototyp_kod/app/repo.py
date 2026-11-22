"""Wspólny interfejs dostępu do danych (KONTRAKT między agentami Backend i API).

Właściciel implementacji: agent Backend.
Agent API korzysta WYŁĄCZNIE z funkcji poniżej (nie importuje bezpośrednio db.py).

Rekord = dict z polami `fields` + `x-pola-systemowe` z 1_wzorzec_danych/aed_schema.json.
Brakujące wartości = None (nigdy "nan", "" ani "None").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Zrodlo:
    id: str                 # np. "dane-gov-pl:3624", "dysponent:5252248481", "osm:Sosnowiec"
    typ: str                # DANE_GOV_PL | DYSPONENT | OSM
    nazwa: str
    url: str | None
    licencja: str           # "CC0 1.0" | "CC BY 4.0" | "ODbL 1.0"


@dataclass
class WynikZapisu:
    dodano: int = 0
    zaktualizowano: int = 0
    oznaczono_duplikaty: int = 0
    ostrzezenia: list[str] = field(default_factory=list)


def zarejestruj_zrodlo(zrodlo: Zrodlo) -> None:
    """Upsert źródła; ustawia ostatnia_synchronizacja = teraz (UTC)."""
    raise NotImplementedError


def zapisz_rekordy(rekordy: Iterable[dict], zrodlo_id: str, zastap: bool = True) -> WynikZapisu:
    """Zapisuje znormalizowane rekordy źródła.

    - zastap=True: usuwa wcześniejsze rekordy tego źródła, których nie ma w nowej partii (pełna synchronizacja).
    - Wylicza `kompletnosc`, `uid` (jeśli brak), uruchamia deduplikację wg `x-priorytet-zrodel`.
    """
    raise NotImplementedError


def lista_rekordow(
    *,
    tylko_otwarte_licencje: bool = False,   # True => bez ODbL (eksport dla dane.gov.pl)
    zrodlo_typ: str | None = None,
    uwzglednij_duplikaty: bool = False,
    identyfikator_dysponenta: str | None = None,
) -> list[dict]:
    raise NotImplementedError


def lista_zrodel() -> list[dict]:
    """[{id, typ, nazwa, url, licencja, liczba_rekordow, ostatnia_synchronizacja}]"""
    raise NotImplementedError
