"""OpenStreetMap / Overpass – testy BEZ sieci (fixture: tests/fixtures/osm/overpass_sosnowiec.json)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from app import schema
from app.sources import osm

FIX = Path(__file__).parent / "fixtures" / "osm" / "overpass_sosnowiec.json"


def _elementy():
    return json.loads(FIX.read_text(encoding="utf-8"))["elements"]


def test_escapowanie_nazwy_miasta():
    q = osm.zbuduj_zapytanie('Sosnowiec"]->.x;node(1);out;("')
    linia = q.splitlines()[1]
    # cudzysłów zamknięty dopiero przez nas – wstrzyknięcie pozostaje częścią literału
    assert '["name"="Sosnowiec\\"]->.x;node(1);out;(\\""]' in linia
    assert osm.escapuj("a\\b") == "a\\\\b"
    for zla in ("", "   ", "Sosnowiec\nout;", "x" * 101):
        with pytest.raises(osm.BladNazwy):
            osm.zbuduj_zapytanie(zla)


def test_normalizacja_tagow():
    rek, ostrz = osm.normalizuj_elementy(_elementy(), "Sosnowiec", data_pobrania="2026-11-22T10:00:00Z")
    assert len(rek) == 4 and any("bez współrzędnych" in o for o in ostrz)
    pola = set(schema.nazwy_pol())
    for r in rek:
        assert pola <= set(r)
        assert r["status_urzadzenia"] == "nieznany"
        assert r["status_weryfikacji"] == "DO_WERYFIKACJI"
        assert r["licencja"] == "ODbL 1.0" and r["zrodlo_typ"] == "OSM"
        assert r["zrodlo_url"].startswith("https://www.openstreetmap.org/")
    r = {x["id_aed"]: x for x in rek}
    a = r["OSM-n4400000001"]
    assert a["lokalizacja_szczegolowa"] == "Hala główna dworca, przy kasach biletowych"
    assert a["dostepnosc_typ"] == "24_7" and a["godziny_dostepnosci"] == "24/7"
    assert a["wewnatrz_budynku"] == "TAK" and a["kondygnacja"] == "0" and a["czy_zamkniete"] == "NIE"
    assert a["nazwa_dysponenta"] == "PKP S.A." and a["kontakt_dysponenta"] == "+48 22 474 00 00"
    assert (a["ulica"], a["nr_budynku"], a["kod_pocztowy"]) == ("3 Maja", "16", "41-200")
    b = r["OSM-n4400000002"]
    assert b["dostepnosc_typ"] == "godziny_otwarcia" and b["czy_zamkniete"] is None
    assert "locked=yes" in b["instrukcja_dostepu"] and b["lokalizacja_szczegolowa"] == "Recepcja – AED wydaje ochrona"
    assert r["OSM-n4400000003"]["dostepnosc_typ"] == "ograniczona"
    w = r["OSM-w4400000004"]                                # obiekt „way” – współrzędne z center
    assert (w["szerokosc_geo"], w["dlugosc_geo"]) == (50.2901, 19.1302) and w["wewnatrz_budynku"] == "NIE"
    assert w["miejscowosc"] == "Sosnowiec"


class _Odp:
    def __init__(self, status, dane=None):
        self.status_code, self._dane = status, dane

    def json(self):
        return self._dane


class _Sesja:
    def __init__(self, odpowiedzi):
        self.odpowiedzi, self.wyslane = list(odpowiedzi), []

    def post(self, url, data=None, timeout=None, headers=None):
        self.wyslane.append((url, data))
        o = self.odpowiedzi.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


def test_pobierz_z_zapasowym_serwerem(monkeypatch):
    monkeypatch.delenv("OVERPASS_URL", raising=False)
    sesja = _Sesja([requests.Timeout(), _Odp(200, {"elements": _elementy()})])
    rek, ostrz, n = osm.pobierz("Sosnowiec", session=sesja)
    assert n == 5 and len(rek) == 4
    assert [u for u, _ in sesja.wyslane] == list(osm.DOMYSLNE_SERWERY)


def test_pobierz_czytelny_blad_gdy_overpass_nie_dziala(monkeypatch):
    monkeypatch.setenv("OVERPASS_URL", "https://a.example/api, https://b.example/api")
    sesja = _Sesja([requests.Timeout(), _Odp(504)])
    with pytest.raises(osm.BladOverpass) as e:
        osm.pobierz("Sosnowiec", session=sesja)
    assert "brak odpowiedzi w 30 s" in str(e.value) and "HTTP 504" in str(e.value)
