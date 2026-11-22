"""Konfiguracja aplikacji (#TuBijeAED). Właściciel: Backend.

Wszystkie ścieżki są absolutne i liczone od położenia tego pliku, więc aplikacja
działa tak samo niezależnie od katalogu, z którego uruchomiono serwer.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent            # .../2_prototyp_kod/app
PROJECT_DIR = APP_DIR.parent                          # .../2_prototyp_kod
REPO_DIR = PROJECT_DIR.parent                         # korzeń repozytorium

STATIC_DIR = PROJECT_DIR / "static"
SCHEMA_PATH = REPO_DIR / "1_wzorzec_danych" / "aed_schema.json"

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")

DEFAULT_DB_PATH = PROJECT_DIR / "data" / "aed.sqlite"
DB_PATH = Path(os.environ.get("DB_PATH") or DEFAULT_DB_PATH)

# Limity wgrywanych plików (panel dysponenta).
MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", 5 * 1024 * 1024))   # 5 MB
MAX_ROWS = int(os.environ.get("MAX_ROWS", 10_000))
# Maksymalna liczba pozycji w jednej liście raportu walidacji (błędy / ostrzeżenia).
MAX_RAPORT_POZYCJI = 1000


def get_db_path() -> Path:
    """Ścieżka bazy liczona przy każdym wywołaniu (env DB_PATH ma pierwszeństwo – testy)."""
    env = os.environ.get("DB_PATH")
    return Path(env) if env else DB_PATH

# ----------------------------------------------------------------------------- prototyp portalu (Sprint 2)
DEFAULT_MEDIA_DIR = PROJECT_DIR / "data" / "media"
# Pliki demo (seed portalu): przycięte, prawdziwe zasoby gmin z dane.gov.pl w app/portal/dane_demo/ – działają bez sieci.
DANEGOV_FIXTURES_DIR = PROJECT_DIR / "app" / "portal" / "dane_demo"   # nazwa historyczna; dane demo nie zależą od tests/
BRAND_DIR = STATIC_DIR / "brand"
KONCEPCJE_DIR = REPO_DIR / "3_branding" / "koncepcje"
# Limit pliku XML harvestera (panel dostawcy).
MAX_XML_BYTES = int(os.environ.get("MAX_XML_BYTES", 5 * 1024 * 1024))


def get_media_dir() -> Path:
    """Katalog plików portalu (wgrane zasoby, wygenerowane wykazy) – odpowiednik MEDIA_ROOT w mcod.

    Kolejność: env MEDIA_DIR; gdy ustawiono DB_PATH (testy, uruchomienie demo w katalogu tymczasowym) –
    obok bazy (`<katalog bazy>/media`), żeby baza i pliki zawsze były spójne; domyślnie data/media/.
    """
    env = os.environ.get("MEDIA_DIR")
    if env:
        return Path(env)
    db = os.environ.get("DB_PATH")
    return Path(db).parent / "media" if db else DEFAULT_MEDIA_DIR


def seed_wlaczony() -> bool:
    """Seed portalu przy starcie (env SEED_PORTAL=0 wyłącza – np. w testach innych modułów)."""
    return os.environ.get("SEED_PORTAL", "1").strip().lower() not in ("0", "false", "nie", "no")
