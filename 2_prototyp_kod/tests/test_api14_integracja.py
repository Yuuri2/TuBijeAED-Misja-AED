"""Integracja API 1.4 + mapa + harvester z prawdziwym portalem (seed Backendu, app.main). Bez sieci.

Pomijane, dopóki Backend nie dostarczy app/portal/seed_portal.py.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_harvester_import import backend_gotowy

pytestmark = pytest.mark.skipif(not backend_gotowy(), reason="app/portal jeszcze niezaimplementowany (Backend)")

XML_114 = (Path(__file__).parent / "fixtures" / "harvester" / "import_aed_1_14.xml").read_bytes()


@pytest.fixture
def klient():
    from app.main import app

    with TestClient(app) as c:                     # lifespan: tabele + seed demo
        yield c


def test_wykaz_api_i_mapa_po_seedzie(klient):
    a = klient.get("/api/1.4/aed-aggregated")
    assert a.status_code == 200, a.text
    d = a.json()["data"]
    assert d["liczba_rekordow"] > 0 and d["liczba_dostawcow"] >= 1 and {"xlsx", "csv", "geojson"} <= set(d["pliki"])
    for url in d["pliki"].values():
        assert klient.get(url).status_code == 200
    zb = klient.get(f"/api/1.4/datasets/{d['zbior_id']}").json()["data"]
    assert zb["attributes"]["is_aggregated_list"] is True
    assert klient.get("/api/1.4/datasets", params={"wykaz": "AED"}).json()["meta"]["count"] >= 1

    rek = klient.get("/api/1.4/aed-aggregated/rekordy").json()
    assert rek["meta"]["count"] == d["liczba_rekordow"]
    assert {"nazwa_dostawcy", "id_aed", "instytucja_id"} <= set(rek["items"][0])

    gj = klient.get("/api/mapa/aed").json()
    assert gj["features"] and all("partner" in f["properties"] for f in gj["features"])
    assert all(f["properties"].get("status_urzadzenia") != "wycofane" for f in gj["features"])
    p = gj["features"][0]["geometry"]["coordinates"]
    n = klient.get("/api/mapa/najblizsze", params={"lat": p[1], "lon": p[0]}).json()["items"]
    assert n and n[0]["odleglosc_m"] == 0 and "dostepny_teraz" in n[0]

    inst = klient.get("/api/1.4/institutions").json()
    assert inst["meta"]["count"] >= 2 and "partner" in inst["data"][0]["attributes"]


def test_import_xml_przez_panel_dolacza_warszawe_do_wykazu(klient):
    konta = klient.get("/api/admin/konta").json()
    waw = next((k for k in konta if "Warszaw" in str(k.get("nazwa"))), None)
    if waw is None:
        pytest.skip("seed bez Urzędu m.st. Warszawy")
    przed = klient.get("/api/1.4/aed-aggregated").json()["data"]
    r = klient.post("/api/admin/harvester/xml", headers={"X-Demo-Konto": str(waw["id"])},
                    files={"plik": ("import_aed_1_14.xml", XML_114, "application/xml")})
    assert r.status_code == 200, r.text
    assert r.json()["bledy"] == [] and r.json()["zasoby_utworzone"] == 2
    po = klient.get("/api/1.4/aed-aggregated").json()["data"]
    assert po["liczba_rekordow"] == przed["liczba_rekordow"] + 3
    assert [x["id_aed"] for x in klient.get("/api/1.4/aed-aggregated/rekordy",
                                            params={"dostawca": waw["id"]}).json()["items"]] \
        == ["WAW-DEMO-001", "WAW-DEMO-002", "WAW-DEMO-003"]
