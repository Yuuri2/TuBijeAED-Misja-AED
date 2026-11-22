"""Warstwa SQLite (stdlib, bez ORM). Właściciel: Backend.

Agent API NIE importuje tego modułu – korzysta wyłącznie z app/repo.py.
Połączenie jest otwierane na żądanie (bezpieczne dla wątków FastAPI), a schemat
tworzony przy pierwszym użyciu danego pliku bazy.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMAT_SQL = """
CREATE TABLE IF NOT EXISTS zrodla (
    id TEXT PRIMARY KEY,
    typ TEXT NOT NULL,
    nazwa TEXT NOT NULL,
    url TEXT,
    licencja TEXT NOT NULL,
    ostatnia_synchronizacja TEXT
);
CREATE TABLE IF NOT EXISTS rekordy (
    uid TEXT PRIMARY KEY,
    zrodlo_id TEXT NOT NULL,
    zrodlo_typ TEXT NOT NULL,
    status_weryfikacji TEXT,
    licencja TEXT,
    identyfikator_dysponenta TEXT,
    wojewodztwo TEXT,
    szerokosc_geo REAL NOT NULL,
    dlugosc_geo REAL NOT NULL,
    kompletnosc REAL,
    duplikat_z TEXT,
    dane TEXT NOT NULL          -- pełny rekord (pola schematu + systemowe) jako JSON
);
CREATE INDEX IF NOT EXISTS idx_rekordy_zrodlo ON rekordy(zrodlo_id);
CREATE INDEX IF NOT EXISTS idx_rekordy_typ ON rekordy(zrodlo_typ);
CREATE INDEX IF NOT EXISTS idx_rekordy_dysp ON rekordy(identyfikator_dysponenta);
CREATE INDEX IF NOT EXISTS idx_rekordy_dup ON rekordy(duplikat_z);
"""

_lock = threading.Lock()
_zainicjowane: set[str] = set()


def teraz_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db(sciezka: Path | str | None = None) -> None:
    """Tworzy katalog i tabele (idempotentnie)."""
    sciezka = Path(sciezka) if sciezka else config.get_db_path()
    klucz = str(sciezka)
    with _lock:
        if klucz in _zainicjowane and sciezka.exists():
            return
        sciezka.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(sciezka)
        try:
            con.executescript(SCHEMAT_SQL)
            con.commit()
        finally:
            con.close()
        _zainicjowane.add(klucz)


def polacz() -> sqlite3.Connection:
    sciezka = config.get_db_path()
    init_db(sciezka)
    con = sqlite3.connect(sciezka, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    return con


@contextmanager
def transakcja():
    """Połączenie z commitem na wyjściu (rollback przy wyjątku) i zamknięciem."""
    con = polacz()
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()
