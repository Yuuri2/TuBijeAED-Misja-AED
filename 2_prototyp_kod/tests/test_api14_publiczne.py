"""Publiczne API 1.4 (JSON:API jak api.dane.gov.pl) – z podmienionym app.portal (bez sieci, bez bazy portalu)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.portal import partnerzy, repo_portal, wykazy
from app.routers import api_14

INSTYTUCJE = [
    {"id": 1, "nazwa": "Ministerstwo Cyfryzacji", "regon": "000000000", "typ": "state", "email": None, "www": None},
    {"id": 3, "nazwa": "Urząd Miasta Krosna", "regon": "000526989", "typ": "local", "email": "um@um.krosno.pl",
     "www": None},
]
ZBIORY = [
    {"id": 10, "instytucja_id": 1, "tytul": "Wykaz defibrylatorów AED – wykaz zbiorczy", "opis": "Scalony",
     "kategoria": "HEAL", "licencja": "CC BY 4.0", "czestotliwosc": "daily", "slowa_kluczowe": ["AED"],
     "status": "opublikowany", "zrodlo": "system", "utworzono": "2026-11-22T10:00:00Z",
     "zmodyfikowano": "2026-11-22T10:00:00Z", "liczba_zasobow": 3, "czy_wykaz_zbiorczy": True},
    {"id": 11, "instytucja_id": 3, "tytul": "Defibrylatory – Krosno", "opis": "AED w Krośnie",
     "kategoria": "HEAL", "licencja": "CC0 1.0", "czestotliwosc": "monthly", "slowa_kluczowe": '["AED", "Krosno"]',
     "status": "opublikowany", "zrodlo": "panel", "utworzono": "2026-11-21T10:00:00Z",
     "zmodyfikowano": "2026-11-21T10:00:00Z", "liczba_zasobow": 2, "czy_wykaz_zbiorczy": False},
    {"id": 12, "instytucja_id": 3, "tytul": "Szkic", "opis": "", "status": "szkic", "liczba_zasobow": 0},
]
ZASOBY = {
    20: {"id": 20, "zbior_id": 11, "tytul": "AED Krosno (CSV)", "opis": "", "format": "csv", "url": None,
         "wykaz_typ": "AED", "status": "opublikowany", "walidacja_status": "OK", "liczba_wierszy": 6,
         "data_danych": "2026-11-20", "zmodyfikowano": "2026-11-21T10:00:00Z", "plik_sciezka": None,
         "walidacja_raport": '{"poprawne_wiersze": 6, "bledne_wiersze": 0}'},
    21: {"id": 21, "zbior_id": 11, "tytul": "Strona BIP", "opis": "", "format": "www",
         "url": "https://bip.krosno.example/aed", "wykaz_typ": None, "status": "opublikowany",
         "walidacja_status": "NIE_DOTYCZY", "plik_sciezka": None},
    22: {"id": 22, "zbior_id": 11, "tytul": "Szkic zasobu", "status": "szkic", "plik_sciezka": None},
    30: {"id": 30, "zbior_id": 10, "tytul": "Wykaz AED", "status": "opublikowany", "plik_sciezka": None},
}
REKORDY = [
    {"instytucja_id": 3, "nazwa_dostawcy": "Urząd Miasta Krosna", "id_aed": "K1", "wojewodztwo": "podkarpackie",
     "szerokosc_geo": 49.69, "dlugosc_geo": 21.77},
    {"instytucja_id": 4, "nazwa_dostawcy": "Urząd Miasta Marki", "id_aed": "M1", "wojewodztwo": "mazowieckie",
     "szerokosc_geo": 52.32, "dlugosc_geo": 21.10},
]


@pytest.fixture
def portal(monkeypatch, tmp_path):
    stan = {"wykaz": None, "wywolania": []}
    plik_csv = tmp_path / "wykaz.csv"
    plik_csv.write_text("nazwa_dostawcy,id_aed\nKrosno,K1\n", encoding="utf-8")
    plik_zasobu = tmp_path / "krosno.csv"
    plik_zasobu.write_text("id_aed\nK1\n", encoding="utf-8")
    ZASOBY[20]["plik_sciezka"] = str(plik_zasobu)

    def lista_zbiorow(*, instytucja_id=None, tylko_wykazy=False, q=None, tylko_opublikowane=True):
        stan["wywolania"].append({"instytucja_id": instytucja_id, "tylko_wykazy": tylko_wykazy, "q": q})
        return [z for z in ZBIORY if z["status"] == "opublikowany"
                and (instytucja_id is None or z["instytucja_id"] == instytucja_id)
                and (not tylko_wykazy or z["czy_wykaz_zbiorczy"])]

    def rekordy_wykazu(typ="AED", *, wojewodztwo=None, instytucja_id=None, bbox=None):
        return [r for r in REKORDY if (not wojewodztwo or r["wojewodztwo"] == wojewodztwo)
                and (instytucja_id is None or r["instytucja_id"] == instytucja_id)]

    monkeypatch.setattr(repo_portal, "lista_instytucji", lambda: INSTYTUCJE)
    monkeypatch.setattr(repo_portal, "pobierz_instytucje", lambda i: next((x for x in INSTYTUCJE if x["id"] == i), None))
    monkeypatch.setattr(repo_portal, "lista_zbiorow", lista_zbiorow)
    monkeypatch.setattr(repo_portal, "pobierz_zbior", lambda i: next((z for z in ZBIORY if z["id"] == i), None))
    monkeypatch.setattr(repo_portal, "lista_zasobow", lambda i, **k: [z for z in ZASOBY.values() if z["zbior_id"] == i])
    monkeypatch.setattr(repo_portal, "pobierz_zasob", lambda i: ZASOBY.get(i))
    monkeypatch.setattr(wykazy, "aktualny_wykaz", lambda typ="AED": stan["wykaz"])
    monkeypatch.setattr(wykazy, "rekordy_wykazu", rekordy_wykazu)
    monkeypatch.setattr(partnerzy, "status_partnera",
                        lambda i: {"status": "AKTYWNY" if i == 3 else "BRAK", "kryteria": [],
                                   "wazny_do": "2027-11-22" if i == 3 else None})
    stan["wykaz_ok"] = {
        "typ": "AED", "zbior_id": 10, "zasob_id": 30, "utworzono": "2026-11-22T10:00:00Z", "liczba_rekordow": 2,
        "liczba_dostawcow": 2, "pliki": {"csv": str(plik_csv), "xlsx": str(tmp_path / "brak.xlsx"), "geojson": None},
        "uwzglednione": [{"instytucja": "Urząd Miasta Krosna", "zasob_id": 20, "rekordy": 1}],
        "pominiete": [{"instytucja": "Galeria", "zasob_id": 25, "powod": "błędy walidacji"}],
    }
    return stan


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(api_14.router, prefix="/api/1.4")
    return TestClient(app)


def _koperta(j):
    assert j["jsonapi"] == {"version": "1.4"}
    assert "self" in j["links"]
    return j["data"]


def test_lista_zbiorow_ksztalt_jsonapi(api, portal):
    r = api.get("/api/1.4/datasets")
    assert r.status_code == 200
    j = r.json()
    data = _koperta(j)
    assert j["meta"]["count"] == 2 and len(data) == 2                  # szkic ukryty
    d = data[1]
    assert d["id"] == "11" and d["type"] == "dataset"
    a = d["attributes"]
    assert a["institution"] == {"id": "3", "title": "Urząd Miasta Krosna", "type": "local"}
    assert a["keywords"] == ["AED", "Krosno"] and a["categories"][0]["code"] == "HEAL"
    assert a["resources_count"] == 2 and a["is_aggregated_list"] is False and a["license"] == "CC0 1.0"
    assert {"title", "notes", "modified"} <= set(a)
    assert d["links"]["self"].endswith("/api/1.4/datasets/11")
    assert d["relationships"]["resources"]["links"]["related"].endswith("/api/1.4/datasets/11/resources")
    assert data[0]["attributes"]["is_aggregated_list"] is True


def test_paginacja_i_filtry(api, portal):
    j = api.get("/api/1.4/datasets", params={"per_page": 1, "page": 2}).json()
    assert len(j["data"]) == 1 and j["meta"] == {"count": 2, "page": 2, "per_page": 1}
    assert "prev" in j["links"] and "next" not in j["links"] and "page=1" in j["links"]["first"]
    assert "page=2" in j["links"]["last"]
    j = api.get("/api/1.4/datasets", params={"per_page": 1}).json()
    assert "next" in j["links"] and "prev" not in j["links"]
    assert api.get("/api/1.4/datasets", params={"per_page": 101}).status_code == 422
    assert api.get("/api/1.4/datasets", params={"page": 0}).status_code == 422
    assert api.get("/api/1.4/datasets", params={"page": 9}).json()["data"] == []

    api.get("/api/1.4/datasets", params={"instytucja": 3, "wykaz": "AED", "q": " krosno "})
    assert portal["wywolania"][-1] == {"instytucja_id": 3, "tylko_wykazy": True, "q": "krosno"}
    assert api.get("/api/1.4/datasets", params={"wykaz": "DGA"}).status_code == 422


def test_zbior_i_zasoby(api, portal):
    d = _koperta(api.get("/api/1.4/datasets/11").json())
    assert d["relationships"]["resources"]["data"] == [{"type": "resource", "id": "20"}, {"type": "resource", "id": "21"}]
    assert api.get("/api/1.4/datasets/12").status_code == 404            # szkic
    assert api.get("/api/1.4/datasets/999").status_code == 404
    j = api.get("/api/1.4/datasets/11/resources").json()
    assert j["meta"]["count"] == 2
    a = j["data"][0]["attributes"]
    assert a["aggregated_list_type"] == "AED" and a["validation_status"] == "OK" and a["format"] == "csv"
    assert a["download_url"].endswith("/api/1.4/resources/20/file") and "modified" in a
    assert j["data"][1]["attributes"]["aggregated_list_type"] is None


def test_zasob_metadane_i_plik(api, portal):
    d = _koperta(api.get("/api/1.4/resources/20").json())
    assert d["attributes"]["validation_report"]["poprawne_wiersze"] == 6
    assert d["relationships"]["dataset"]["data"] == {"type": "dataset", "id": "11"}
    f = api.get("/api/1.4/resources/20/file")
    assert f.status_code == 200 and f.text == "id_aed\nK1\n"
    r = api.get("/api/1.4/resources/21/file", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://bip.krosno.example/aed"
    assert api.get("/api/1.4/resources/22").status_code == 404            # szkic
    assert api.get("/api/1.4/resources/22/file").status_code == 404


def test_instytucje_z_partnerem(api, portal):
    j = api.get("/api/1.4/institutions").json()
    assert j["meta"]["count"] == 2
    krosno = _koperta(api.get("/api/1.4/institutions/3").json())
    assert krosno["type"] == "institution" and krosno["attributes"]["institution_type"] == "local"
    assert krosno["attributes"]["partner"] == {"status": "AKTYWNY", "wazny_do": "2027-11-22"}
    assert krosno["attributes"]["datasets_count"] == 1
    assert api.get("/api/1.4/institutions/77").status_code == 404


def test_partner_niezaimplementowany_nie_psuje_api(api, portal, monkeypatch):
    def brak(i):
        raise NotImplementedError
    monkeypatch.setattr(partnerzy, "status_partnera", brak)
    assert api.get("/api/1.4/institutions/3").json()["data"]["attributes"]["partner"] is None


def test_aed_aggregated_404_gdy_brak_wykazu(api, portal):
    """Jak AggregatedDGAInfoView: brak wpisu -> 404."""
    assert api.get("/api/1.4/aed-aggregated").status_code == 404
    assert api.get("/api/1.4/aed-aggregated/rekordy").status_code == 404
    assert api.get("/api/1.4/aed-aggregated/plik/csv").status_code == 404


def test_aed_aggregated_404_gdy_zasob_nieopublikowany(api, portal, monkeypatch):
    portal["wykaz"] = dict(portal["wykaz_ok"], zasob_id=22)
    assert api.get("/api/1.4/aed-aggregated").status_code == 404


def test_aed_aggregated(api, portal):
    portal["wykaz"] = portal["wykaz_ok"]
    j = api.get("/api/1.4/aed-aggregated").json()
    d = _koperta(j)
    assert (d["zbior_id"], d["zasob_id"], d["dataset_id"], d["resource_id"]) == (10, 30, 10, 30)
    assert d["liczba_rekordow"] == 2 and d["liczba_dostawcow"] == 2 and d["utworzono"].startswith("2026-11-22")
    assert set(d["pliki"]) == {"csv", "xlsx"} and d["pliki"]["csv"].endswith("/api/1.4/aed-aggregated/plik/csv")
    assert d["uwzglednione"][0]["rekordy"] == 1 and d["pominiete"][0]["powod"] == "błędy walidacji"
    assert "/tmp" not in str(d)                                      # ścieżki dyskowe nie wyciekają
    r = api.get("/api/1.4/aed-aggregated/plik/csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "wykaz_aed_zbiorczy.csv" in r.headers["content-disposition"]
    assert api.get("/api/1.4/aed-aggregated/plik/xlsx").status_code == 404    # plik zniknął z dysku
    assert api.get("/api/1.4/aed-aggregated/plik/pdf").status_code == 404


def test_aed_aggregated_rekordy_filtry(api, portal):
    portal["wykaz"] = portal["wykaz_ok"]
    j = api.get("/api/1.4/aed-aggregated/rekordy").json()
    assert j["meta"]["count"] == 2 and len(j["items"]) == 2 and j["jsonapi"]["version"] == "1.4"
    assert [r["id_aed"] for r in api.get("/api/1.4/aed-aggregated/rekordy",
                                         params={"wojewodztwo": "mazowieckie"}).json()["items"]] == ["M1"]
    assert [r["id_aed"] for r in api.get("/api/1.4/aed-aggregated/rekordy",
                                         params={"dostawca": 3}).json()["items"]] == ["K1"]
    bbox = api.get("/api/1.4/aed-aggregated/rekordy", params={"bbox": "20.5,52.0,21.5,52.5"}).json()["items"]
    assert [r["id_aed"] for r in bbox] == ["M1"]
    for zly in ("abc", "1,2,3", "21.5,52.0,20.5,52.5", "nan,1,2,3"):
        assert api.get("/api/1.4/aed-aggregated/rekordy", params={"bbox": zly}).status_code == 422
