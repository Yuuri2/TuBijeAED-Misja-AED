"""Tabele prototypu portalu dane.gov.pl (SQLite, ta sama baza co reszta aplikacji). Właściciel: Backend.

Odpowiedniki w mcod (Django ORM, PostgreSQL):
  instytucje   <- mcod/organizations/models.py  Organization (institution_type: local/state/private/other/developer)
  zbiory       <- mcod/datasets/models.py       Dataset
  zasoby       <- mcod/resources/models.py      Resource (+ ResourceFile); `wykaz_typ` uogólnia
                                                 `contains_protected_data` (DGA) na wiele wykazów
  wykazy_info  <- mcod/resources/models.py      AggregatedDGAInfo (u nas: historia uruchomień + wskaźnik
                                                 aktualnego wykazu, zamiast singletonu)
Pliki (MEDIA_ROOT w mcod) – katalog `config.get_media_dir()`; w bazie trzymamy ścieżki WZGLĘDNE.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .. import config, db

SCHEMAT_PORTAL_SQL = """
CREATE TABLE IF NOT EXISTS instytucje (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    regon TEXT,
    nip TEXT,
    typ TEXT NOT NULL CHECK (typ IN ('local','state','private','other','developer')),
    email TEXT,
    www TEXT,
    utworzono TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS zbiory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instytucja_id INTEGER NOT NULL REFERENCES instytucje(id),
    tytul TEXT NOT NULL,
    opis TEXT NOT NULL DEFAULT '',
    kategoria TEXT NOT NULL DEFAULT 'HEAL',
    licencja TEXT NOT NULL DEFAULT 'CC BY 4.0',
    czestotliwosc TEXT NOT NULL DEFAULT 'irregular',
    slowa_kluczowe TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'opublikowany' CHECK (status IN ('opublikowany','szkic')),
    zrodlo TEXT NOT NULL DEFAULT 'panel' CHECK (zrodlo IN ('panel','harvester','system')),
    ext_ident TEXT,
    wykaz_zbiorczy TEXT,            -- typ wykazu, jeśli to zbiór wykazu zbiorczego (np. 'AED')
    utworzono TEXT NOT NULL,
    zmodyfikowano TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_zbiory_inst ON zbiory(instytucja_id);
CREATE TABLE IF NOT EXISTS zasoby (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zbior_id INTEGER NOT NULL REFERENCES zbiory(id),
    tytul TEXT NOT NULL,
    opis TEXT NOT NULL DEFAULT '',
    format TEXT,
    plik_sciezka TEXT,              -- względem config.get_media_dir()
    nazwa_pliku TEXT,
    url TEXT,
    wykaz_typ TEXT,                 -- NULL | 'AED'  (zasób ŹRÓDŁOWY wykazu, jak contains_protected_data)
    wykaz_zbiorczy TEXT,            -- NULL | 'AED'  (plik WYNIKOWY wykazu zbiorczego, zasób systemowy)
    status TEXT NOT NULL DEFAULT 'opublikowany' CHECK (status IN ('opublikowany','szkic')),
    walidacja_status TEXT NOT NULL DEFAULT 'NIE_DOTYCZY' CHECK (walidacja_status IN ('OK','BLEDY','BRAK','NIE_DOTYCZY')),
    walidacja_raport TEXT,
    liczba_wierszy INTEGER,
    data_danych TEXT,
    ext_ident TEXT,
    utworzono TEXT NOT NULL,
    zmodyfikowano TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_zasoby_zbior ON zasoby(zbior_id);
CREATE INDEX IF NOT EXISTS idx_zasoby_wykaz ON zasoby(wykaz_typ, status, walidacja_status);
CREATE TABLE IF NOT EXISTS wykazy_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    typ TEXT NOT NULL,
    zbior_id INTEGER,
    zasob_id INTEGER,               -- główny zasób (XLSX), jak AggregatedDGAInfo.resource
    zasoby TEXT,                    -- {"xlsx": id, "csv": id, "geojson": id}
    pliki TEXT,                     -- {"xlsx": sciezka_wzgledna, ...}
    katalog TEXT,                   -- katalog plików tego uruchomienia (względny)
    utworzono TEXT NOT NULL,
    liczba_rekordow INTEGER NOT NULL DEFAULT 0,
    liczba_dostawcow INTEGER NOT NULL DEFAULT 0,
    uwzglednione TEXT NOT NULL DEFAULT '[]',
    pominiete TEXT NOT NULL DEFAULT '[]',
    raport_jakosci TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK (status IN ('OK','BLAD')),
    komunikat TEXT,
    czas_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_wykazy_typ ON wykazy_info(typ, status);
"""

_lock = threading.Lock()
_zainicjowane: set[str] = set()


def init_portal(sciezka: Path | str | None = None) -> None:
    """Tworzy tabele portalu (idempotentnie) w bazie `config.get_db_path()`."""
    sciezka = Path(sciezka) if sciezka else config.get_db_path()
    klucz = str(sciezka)
    with _lock:
        if klucz in _zainicjowane and sciezka.exists():
            return
        db.init_db(sciezka)
        con = sqlite3.connect(sciezka)
        try:
            con.executescript(SCHEMAT_PORTAL_SQL)
            con.commit()
        finally:
            con.close()
        _zainicjowane.add(klucz)


@contextmanager
def transakcja():
    """Połączenie z tabelami portalu: commit na wyjściu, rollback przy wyjątku."""
    init_portal()
    con = db.polacz()
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def teraz_iso() -> str:
    return db.teraz_iso()


# ----------------------------------------------------------------------------- pliki

def katalog_media() -> Path:
    k = config.get_media_dir()
    k.mkdir(parents=True, exist_ok=True)
    return k


def sciezka_absolutna(wzgledna: str | None) -> Path | None:
    if not wzgledna:
        return None
    return katalog_media() / wzgledna


def sciezka_wzgledna(p: Path) -> str:
    return p.resolve().relative_to(katalog_media().resolve()).as_posix()


# ----------------------------------------------------------------------------- JSON w kolumnach

def z_json(s: str | None, domyslne=None):
    if s in (None, ""):
        return domyslne
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return domyslne


def do_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
