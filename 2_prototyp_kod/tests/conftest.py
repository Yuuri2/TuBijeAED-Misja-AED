"""Wspólne fixture'y testów. Właściciel: Backend.

Każdy test dostaje własną, tymczasową bazę SQLite (env DB_PATH) – nigdy nie dotyka data/aed.sqlite.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def tymczasowa_baza(tmp_path, monkeypatch):
    sciezka = tmp_path / "aed_test.sqlite"
    monkeypatch.setenv("DB_PATH", str(sciezka))
    return sciezka


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    # bez `with` – nie uruchamia lifespan (baza startuje pusta, bez danych przykładowych)
    return TestClient(app)
