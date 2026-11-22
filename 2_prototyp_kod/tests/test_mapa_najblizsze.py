"""Mapa #TuBijeAED: dostępność teraz (podzbiór OSM opening_hours), najbliższe AED, GeoJSON wykazu, warstwa OSM."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.portal import partnerzy, repo_portal, wykazy
from app.routers import mapa
from app.sources import godziny, osm

WAW = ZoneInfo("Europe/Warsaw")
PON_10 = datetime(2026, 11, 23, 10, 0, tzinfo=WAW)       # poniedziałek
PON_20 = datetime(2026, 11, 23, 20, 0, tzinfo=WAW)
SOB_10 = datetime(2026, 11, 28, 10, 0, tzinfo=WAW)
NIEDZ_10 = datetime(2026, 11, 29, 10, 0, tzinfo=WAW)


# ---------------------------------------------------------------------------------------------- godziny

@pytest.mark.parametrize("wyrazenie,chwila,oczekiwane", [
    ("24/7", PON_20, True),
    ("24/7", NIEDZ_10, True),
    ("Mo-Fr 08:00-16:00", PON_10, True),
    ("Mo-Fr 08:00-16:00", PON_20, False),                       # poza godzinami
    ("Mo-Fr 08:00-16:00", SOB_10, False),                       # weekend
    ("Mo-Fr 08:00-16:00; Sa 09:00-13:00", SOB_10, True),
    ("Mo-Fr 08:00-16:00; Sa 09:00-13:00; Su off", NIEDZ_10, False),
    ("Mo-Su 08:00-22:00; Su off", NIEDZ_10, False),             # późniejsza reguła zastępuje
    ("Mo,We,Fr 08:00-12:00,13:00-16:00", PON_10, True),
    ("Mo,We,Fr 08:00-12:00,13:00-16:00", datetime(2026, 11, 23, 12, 30, tzinfo=WAW), False),
    ("08:00-21:00", PON_20, True),                              # bez dni = codziennie
    ("Su 22:00-02:00", datetime(2026, 11, 30, 1, 0, tzinfo=WAW), True),   # przez północ (nd -> pn)
    ("Su 22:00-02:00", datetime(2026, 11, 30, 3, 0, tzinfo=WAW), False),
    ("Sa-Mo 10:00-11:00", NIEDZ_10, True),                      # zakres zawijany
])
def test_czy_otwarte(wyrazenie, chwila, oczekiwane):
    assert godziny.czy_otwarte(wyrazenie, chwila) is oczekiwane


def test_czas_przeliczany_na_strefe_warszawy():
    utc = ZoneInfo("UTC")
    # listopad (CET, UTC+1): 15:30 UTC = 16:30 w Warszawie -> po zamknięciu; 14:30 UTC = 15:30 -> otwarte
    assert godziny.czy_otwarte("Mo-Fr 08:00-16:00", datetime(2026, 11, 23, 15, 30, tzinfo=utc)) is False
    assert godziny.czy_otwarte("Mo-Fr 08:00-16:00", datetime(2026, 11, 23, 14, 30, tzinfo=utc)) is True
    # lipiec (CEST, UTC+2): 14:30 UTC = 16:30 -> zamknięte
    assert godziny.czy_otwarte("Mo-Fr 08:00-16:00", datetime(2026, 7, 20, 14, 30, tzinfo=utc)) is False


@pytest.mark.parametrize("godz,typ,status,oczekiwane", [
    (None, None, "sprawne", None),                  # brak godzin -> nie wiadomo
    ("", "godziny_otwarcia", None, None),
    (None, "24_7", "sprawne", True),                # 24_7 bez godzin
    ("Mo-Fr 08:00-16:00 PH off", None, None, None),  # składnia spoza podzbioru -> nie zgadujemy
    ("sunrise-sunset", None, None, None),
    ("Mo-Fr 25:00-26:00", None, None, None),
    ("Pn-Pt 8-16", None, None, None),
    ("24/7", "24_7", "w_serwisie", False),          # urządzenie w serwisie
    ("Mo-Fr 08:00-16:00", None, "nieznany", True),  # status nieznany nie wpływa na godziny
])
def test_dostepny_teraz(godz, typ, status, oczekiwane):
    assert godziny.dostepny_teraz(godz, typ, status, chwila=PON_10) is oczekiwane


def test_czas_domyslny_w_warszawie():
    assert godziny.teraz().tzinfo is not None and godziny.teraz().utcoffset() == datetime.now(WAW).utcoffset()


# ---------------------------------------------------------------------------------------------- router (atrapa portalu)

def _rek(id_aed, lat, lon, **kw):
    return {"id_aed": id_aed, "instytucja_id": kw.pop("inst", 3), "nazwa_dostawcy": "Urząd", "szerokosc_geo": lat,
            "dlugosc_geo": lon, "status_urzadzenia": kw.pop("status", "sprawne"),
            "godziny_dostepnosci": kw.pop("godz", None), "dostepnosc_typ": kw.pop("typ", None),
            "wojewodztwo": "mazowieckie", **kw}


# Punkt odniesienia: pl. Bankowy, Warszawa (52.2428, 21.0021)
REKORDY = [
    _rek("BLISKO-24", 52.2430, 21.0025, godz="24/7", typ="24_7"),                   # ~35 m
    _rek("WYCOFANY", 52.2429, 21.0022, status="wycofane", godz="24/7"),             # najbliżej, ale ukryty
    _rek("BIURO", 52.2440, 21.0040, godz="Mo-Fr 08:00-16:00", inst=4),             # ~185 m
    _rek("NIEZNANY", 52.2450, 21.0060, status=None),                               # ~350 m
    _rek("DALEKO", 52.4000, 21.2000, status="nieznany", godz="Sa 09:00-13:00"),     # ~22 km
    _rek("BEZ-WSP", None, None),
]


@pytest.fixture
def portal(monkeypatch):
    stan = {"wykaz": {"typ": "AED", "zasob_id": 30}}
    monkeypatch.setattr(wykazy, "aktualny_wykaz", lambda typ="AED": stan["wykaz"])
    monkeypatch.setattr(wykazy, "rekordy_wykazu",
                        lambda typ="AED", *, wojewodztwo=None, instytucja_id=None, bbox=None:
                        [dict(r) for r in REKORDY if instytucja_id is None or r["instytucja_id"] == instytucja_id])
    monkeypatch.setattr(repo_portal, "pobierz_zasob", lambda i: {"id": i, "status": "opublikowany", "zbior_id": 10})
    monkeypatch.setattr(partnerzy, "status_partnera", lambda i: {"status": "AKTYWNY" if i == 4 else "BRAK"})
    monkeypatch.setattr(godziny, "teraz", lambda: PON_20)          # poniedziałek 20:00 – biuro zamknięte
    return stan


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(mapa.router, prefix="/api/mapa")
    return TestClient(app)


def test_najblizsze_kolejnosc_wycofane_ukryte_nieznane_oznaczone(api, portal):
    j = api.get("/api/mapa/najblizsze", params={"lat": 52.2428, "lon": 21.0021, "limit": 3}).json()
    items = j["items"]
    assert [i["id_aed"] for i in items] == ["BLISKO-24", "BIURO", "NIEZNANY"]
    assert items[0]["odleglosc_m"] < items[1]["odleglosc_m"] < items[2]["odleglosc_m"]
    assert 20 < items[0]["odleglosc_m"] < 60
    assert [i["dostepny_teraz"] for i in items] == [True, False, None]
    assert [i["status_nieznany"] for i in items] == [False, False, True]
    assert [i["partner"] for i in items] == [False, True, False]
    assert items[0]["nawigacja_url"].startswith("https://www.openstreetmap.org/directions")
    assert j["meta"]["strefa"] == "Europe/Warsaw" and j["meta"]["czas"].startswith("2026-11-23T20:00")


def test_najblizsze_limit_i_walidacja(api, portal):
    assert len(api.get("/api/mapa/najblizsze", params={"lat": 52.2, "lon": 21.0, "limit": 20}).json()["items"]) == 4
    assert len(api.get("/api/mapa/najblizsze", params={"lat": 52.2, "lon": 21.0}).json()["items"]) == 3
    for p in ({"lat": 91, "lon": 21}, {"lat": 52, "lon": 21, "limit": 0}, {"lat": 52, "lon": 21, "limit": 21},
              {"lon": 21}):
        assert api.get("/api/mapa/najblizsze", params=p).status_code == 422


def test_najblizsze_bez_wykazu(api, portal):
    portal["wykaz"] = None
    j = api.get("/api/mapa/najblizsze", params={"lat": 52.2, "lon": 21.0}).json()
    assert j["items"] == [] and "nie jest jeszcze dostępny" in j["meta"]["komunikat"]


def test_geojson_aed_z_partnerem(api, portal, monkeypatch):
    monkeypatch.setattr(godziny, "teraz", lambda: PON_10)
    gj = api.get("/api/mapa/aed").json()
    assert gj["type"] == "FeatureCollection"
    ids = [f["properties"]["id_aed"] for f in gj["features"]]
    assert ids == ["BLISKO-24", "BIURO", "NIEZNANY", "DALEKO"]          # bez wycofanych i bez współrzędnych
    biuro = gj["features"][1]
    assert biuro["geometry"] == {"type": "Point", "coordinates": [21.004, 52.244]}
    assert biuro["properties"]["partner"] is True and biuro["properties"]["dostepny_teraz"] is True
    assert gj["features"][3]["properties"]["status_nieznany"] is True
    assert [f["properties"]["id_aed"] for f in api.get("/api/mapa/aed", params={"dostawca": 4}).json()["features"]] \
        == ["BIURO"]
    assert [f["properties"]["id_aed"] for f in
            api.get("/api/mapa/aed", params={"bbox": "21.1,52.3,21.3,52.5"}).json()["features"]] == ["DALEKO"]
    assert api.get("/api/mapa/aed", params={"bbox": "x"}).status_code == 422


def test_geojson_bez_wykazu_pusty(api, portal):
    portal["wykaz"] = None
    assert api.get("/api/mapa/aed").json()["features"] == []


# ---------------------------------------------------------------------------------------------- warstwa OSM

def _elementy():
    p = Path(__file__).parent / "fixtures" / "osm" / "overpass_sosnowiec.json"
    return json.loads(p.read_text(encoding="utf-8"))["elements"]


def test_warstwa_osm_pobierz_i_odczyt(api, portal, monkeypatch):
    rekordy, _ = osm.normalizuj_elementy(_elementy(), "Sosnowiec")
    monkeypatch.setattr(osm, "pobierz", lambda miasto, session=None: (rekordy, [], len(rekordy)))
    r = api.post("/api/mapa/osm/pobierz", data={"miasto": "Sosnowiec"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["licencja"] == "ODbL 1.0" and j["status_weryfikacji"] == "DO_WERYFIKACJI" and j["w_wykazie"] is False
    assert j["zapisano"] == len(rekordy) > 0
    gj = api.get("/api/mapa/osm").json()
    assert gj["licencja"] == "ODbL 1.0" and gj["atrybucja"].startswith("© OpenStreetMap")
    assert len(gj["features"]) >= 1
    assert all(f["properties"]["status_weryfikacji"] == "DO_WERYFIKACJI" and f["properties"]["w_wykazie"] is False
               for f in gj["features"])
    assert api.get("/api/mapa/osm", params={"bbox": "0,0,1,1"}).json()["features"] == []
    # OSM nigdy nie miesza się z wykazem
    assert all(f["properties"]["id_aed"] != r["id_aed"] for f in api.get("/api/mapa/aed").json()["features"]
               for r in rekordy)


def test_warstwa_osm_bledy(api, portal, monkeypatch):
    assert api.post("/api/mapa/osm/pobierz", data={"miasto": "x\ny"}).status_code == 422

    def awaria(miasto, session=None):
        raise osm.BladOverpass("Nie udało się pobrać danych z OpenStreetMap")
    monkeypatch.setattr(osm, "pobierz", awaria)
    assert api.post("/api/mapa/osm/pobierz", data={"miasto": "Sosnowiec"}).status_code == 502
