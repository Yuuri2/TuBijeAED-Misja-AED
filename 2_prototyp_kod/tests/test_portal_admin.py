"""Panel portalu /api/admin – demo-uwierzytelnianie, uprawnienia, dodawanie zasobów AED, wykazy (admin)."""
from __future__ import annotations

import pytest

from app import schema
from app.portal import repo_portal, wykazy
from tests.portal_pomoc import aed, dodaj_aed, plik_csv, portal_testowy


@pytest.fixture
def p():
    return portal_testowy()


def H(konto) -> dict:
    return {"X-Demo-Konto": str(konto)}


def _multipart(wiersze, nazwa="aed.csv", **pola):
    dane = {"tytul": "AED", "wykaz_typ": "AED", "status": "opublikowany", **pola}
    return {"files": {"plik": (nazwa, plik_csv(wiersze), "text/csv")}, "data": dane}


def test_konta_bez_naglowka(client, p):
    k = client.get("/api/admin/konta").json()
    assert k[-1] == {"id": "admin", "nazwa": "Administrator portalu (MC)", "typ": "admin"}
    assert {"id": p["a"]["id"], "nazwa": "Urząd Miasta Alfa", "typ": "local"} in k


def test_brak_naglowka_401_i_zle_konto(client, p):
    r = client.get("/api/admin/moje-zbiory")
    assert r.status_code == 401 and r.json()["error"]
    assert client.get("/api/admin/moje-zbiory", headers=H(999)).status_code == 401
    assert client.get("/api/admin/moje-zbiory", headers=H("ktos")).status_code == 401


def test_dodanie_zasobu_poprawnego_i_blednego_przez_panel(client, p):
    zb = p["zbior"][p["a"]["id"]]
    r = client.post(f"/api/admin/zbiory/{zb}/zasoby", headers=H(p["a"]["id"]), **_multipart([aed("A1")]))
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["zasob"]["walidacja_status"] == "OK" and "plik_sciezka" not in j["zasob"]
    assert j["walidacja"]["poprawne_wiersze"] == 1 and j["wykaz"]["przebudowano"] is True

    zb_b = p["zbior"][p["b"]["id"]]
    r = client.post(f"/api/admin/zbiory/{zb_b}/zasoby", headers=H(p["b"]["id"]),
                    **_multipart([aed("B1", lat=12.0)]))
    assert r.status_code == 201
    j = r.json()
    assert j["zasob"]["walidacja_status"] == "BLEDY"
    assert j["walidacja"]["bledy"][0]["wiersz"] == 2 and j["walidacja"]["bledy"][0]["pole"] == "szerokosc_geo"
    assert [u["instytucja"] for u in wykazy.aktualny_wykaz()["uwzglednione"]] == ["Urząd Miasta Alfa"]


def test_brak_kolumn_422_drugi_zasob_409_zly_typ_422(client, p):
    a = p["a"]["id"]
    kolumny = [k for k in schema.nazwy_pol() if k != "id_aed"]
    r = client.post(f"/api/admin/zbiory/{p['zbior'][a]}/zasoby", headers=H(a),
                    files={"plik": ("aed.csv", plik_csv([aed("A1")], kolumny), "text/csv")},
                    data={"tytul": "AED", "wykaz_typ": "AED"})
    assert r.status_code == 422 and r.json()["brakujace_kolumny"] == ["id_aed"] and "error" in r.json()

    assert client.post(f"/api/admin/zbiory/{p['zbior'][a]}/zasoby", headers=H(a), **_multipart([aed("A1")])).status_code == 201
    nowy = client.post("/api/admin/zbiory", headers=H(a), json={"tytul": "Drugi"}).json()
    r = client.post(f"/api/admin/zbiory/{nowy['id']}/zasoby", headers=H(a), **_multipart([aed("A2")]))
    assert r.status_code == 409 and "zaktualizuj istniejący zasób" in r.json()["error"]

    d = p["dev"]["id"]
    r = client.post(f"/api/admin/zbiory/{p['zbior'][d]}/zasoby", headers=H(d), **_multipart([aed("D1")]))
    assert r.status_code == 422 and r.json()["typ_instytucji"] == "developer"


def test_uprawnienia_cudzy_zbior_i_zasob(client, p):
    a, b = p["a"]["id"], p["b"]["id"]
    r = client.post(f"/api/admin/zbiory/{p['zbior'][b]}/zasoby", headers=H(a), **_multipart([aed("X")]))
    assert r.status_code == 403
    z = dodaj_aed(p["zbior"][b], [aed("B1")])["zasob"]
    assert client.delete(f"/api/admin/zasoby/{z['id']}", headers=H(a)).status_code == 403
    assert client.put(f"/api/admin/zasoby/{z['id']}", headers=H(a), data={"tytul": "x"}).status_code == 403
    # moje zbiory – tylko własne
    moje = client.get("/api/admin/moje-zbiory", headers=H(a)).json()
    assert {zb["instytucja_id"] for zb in moje} == {a}
    # zbiór/zasoby wykazu zbiorczego – nieedytowalne nawet dla admina
    w = wykazy.aktualny_wykaz()
    assert client.post(f"/api/admin/zbiory/{w['zbior_id']}/zasoby", headers=H("admin"),
                       **_multipart([aed("M")])).status_code == 403
    assert client.delete(f"/api/admin/zasoby/{w['zasob_id']}", headers=H("admin")).status_code == 403
    # przebudowa i historia – tylko admin
    assert client.post("/api/admin/wykazy/AED/przebuduj", headers=H(a)).status_code == 403
    assert client.get("/api/admin/wykazy/AED/historia", headers=H(a)).status_code == 403


def test_put_aktualizuje_plik_i_flage_delete_przebudowuje(client, p):
    a = p["a"]["id"]
    z = dodaj_aed(p["zbior"][a], [aed("A1")])["zasob"]
    r = client.put(f"/api/admin/zasoby/{z['id']}", headers=H(a),
                   files={"plik": ("nowy.csv", plik_csv([aed("A1"), aed("A2", lat=52.3)]), "text/csv")})
    assert r.status_code == 200 and r.json()["zasob"]["liczba_wierszy"] == 2 and r.json()["zasob"]["tytul"] == "AED"
    assert wykazy.aktualny_wykaz()["liczba_rekordow"] == 2
    r = client.put(f"/api/admin/zasoby/{z['id']}", headers=H(a), data={"wykaz_typ": ""})
    assert r.json()["zasob"]["wykaz_typ"] is None and wykazy.aktualny_wykaz()["liczba_rekordow"] == 0
    r = client.put(f"/api/admin/zasoby/{z['id']}", headers=H(a), data={"wykaz_typ": "AED"})
    assert r.json()["zasob"]["walidacja_status"] == "OK" and wykazy.aktualny_wykaz()["liczba_rekordow"] == 2
    r = client.delete(f"/api/admin/zasoby/{z['id']}", headers=H(a))
    assert r.status_code == 200 and r.json()["wykaz"]["przebudowano"]
    assert wykazy.aktualny_wykaz()["liczba_rekordow"] == 0
    assert client.delete(f"/api/admin/zasoby/{z['id']}", headers=H(a)).status_code == 404


def test_admin_przebudowa_i_historia(client, p):
    dodaj_aed(p["zbior"][p["a"]["id"]], [aed("A1")])
    r = client.post("/api/admin/wykazy/AED/przebuduj", headers=H("admin"))
    assert r.status_code == 200 and r.json()["status"] == "OK" and r.json()["liczba_dostawcow"] == 1
    h = client.get("/api/admin/wykazy/AED/historia", headers=H("admin")).json()
    assert len(h) == 2 and h[0]["aktualny"] and h[0]["liczba_rekordow"] == 1
    assert client.post("/api/admin/wykazy/XYZ/przebuduj", headers=H("admin")).status_code == 422


def test_nowy_zbior_i_limity(client, p, monkeypatch):
    a = p["a"]["id"]
    r = client.post("/api/admin/zbiory", headers=H(a), json={"tytul": "Nowy", "slowa_kluczowe": ["AED"]})
    assert r.status_code == 201 and r.json()["instytucja_id"] == a and r.json()["zrodlo"] == "panel"
    assert client.post("/api/admin/zbiory", headers=H("admin"), json={"tytul": "X"}).status_code == 422
    from app import config
    monkeypatch.setattr(config, "MAX_FILE_BYTES", 50)
    r = client.post(f"/api/admin/zbiory/{r.json()['id']}/zasoby", headers=H(a), **_multipart([aed("A1")]))
    assert r.status_code == 413
    r = client.post(f"/api/admin/zbiory/{p['zbior'][a]}/zasoby", headers=H(a), data={"tytul": "x"})
    assert r.status_code == 422


def test_harvester_xml_wywoluje_modul_api(client, p, monkeypatch):
    from app import harvester
    wywolania = []

    def importuj(tresc, instytucja_id):
        wywolania.append((tresc, instytucja_id))
        return {"zbiory_utworzone": 0, "zasoby_utworzone": 0, "bledy": []}

    monkeypatch.setattr(harvester, "importuj_xml", importuj)
    a = p["a"]["id"]
    r = client.post("/api/admin/harvester/xml", headers=H(a), files={"plik": ("h.xml", b"<x/>", "application/xml")})
    assert r.status_code == 200 and wywolania == [(b"<x/>", a)]
    assert client.post("/api/admin/harvester/xml", headers=H(a),
                       files={"plik": ("h.txt", b"<x/>", "text/plain")}).status_code == 400

    def brak(tresc, instytucja_id):
        raise NotImplementedError

    monkeypatch.setattr(harvester, "importuj_xml", brak)
    r = client.post("/api/admin/harvester/xml", headers=H(a), files={"plik": ("h.xml", b"<x/>", "application/xml")})
    assert r.status_code == 501 and r.json()["error"]
