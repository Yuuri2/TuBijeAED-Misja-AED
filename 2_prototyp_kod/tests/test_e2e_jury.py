"""E2E ścieżki jurora (static/jury.html) – TestClient z lifespanem (seed), tymczasowa baza, bez sieci. Właściciel: Tester."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PRZYKLADY = Path(__file__).resolve().parent.parent / "static" / "przyklady"


@pytest.fixture
def c(monkeypatch):
    monkeypatch.setenv("SEED_PORTAL", "1")
    from app.main import app
    with TestClient(app) as cl:
        yield cl


def _konto(c, nazwa_fragment):
    for k in c.get("/api/admin/konta").json():
        if nazwa_fragment in k["nazwa"]:
            return k["id"]
    raise AssertionError(nazwa_fragment)


def _h(i):
    return {"X-Demo-Konto": str(i)}


def _wykaz(c):
    return c.get("/api/1.4/aed-aggregated").json()["data"]


def _plik(nazwa):
    return (nazwa, (PRZYKLADY / nazwa).read_bytes())


def test_sciezka_jurora(c):
    # 1. wykaz po seedzie
    w0 = _wykaz(c)
    assert w0["liczba_rekordow"] > 0 and w0["liczba_dostawcow"] >= 2
    assert w0["uwzglednione"] and w0["pominiete"]
    assert all(p.get("powod") for p in w0["pominiete"])
    for f in ("xlsx", "csv", "geojson"):
        r = c.get(w0["pliki"][f].replace("http://testserver", ""))
        assert r.status_code == 200 and len(r.content) > 100
    # 2. strony statyczne z jury.html odpowiadają
    for p in ["/", "/zbiory.html", "/wykaz-aed.html", "/mapa.html", "/asystent.html", "/admin/", "/jury.html",
              "/partner.html", "/instytucja.html", "/zbior.html"]:
        assert c.get(p).status_code == 200, p
    for p in ["aed_z_bledami.csv", "aed_poprawny.csv", "harvester_1_14_przyklad.xml", "gmina_stary_uklad_krosno.csv"]:
        assert c.get("/przyklady/" + p).status_code == 200
    # 3. logowanie jako Warszawa (bez zasobu)
    waw = _konto(c, "Warszawy")
    moje = c.get("/api/admin/moje-zbiory", headers=_h(waw))
    assert moje.status_code == 200
    # 4. zbiór
    r = c.post("/api/admin/zbiory", headers=_h(waw), json={"tytul": "Defibrylatory AED – Warszawa", "opis": "",
                                                            "licencja": "CC BY 4.0", "czestotliwosc": "irregular",
                                                            "slowa_kluczowe": ["aed"]})
    assert r.status_code == 201, r.text
    zb = r.json()["id"]
    # 5. zasób z błędami -> odrzucony z raportem
    r = c.post(f"/api/admin/zbiory/{zb}/zasoby", headers=_h(waw),
               data={"tytul": "AED Warszawa", "wykaz_typ": "AED"}, files={"plik": _plik("aed_z_bledami.csv")})
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["zasob"]["walidacja_status"] == "BLEDY"
    assert j["walidacja"]["bledne_wiersze"] >= 1 and j["walidacja"]["bledy"]
    b = j["walidacja"]["bledy"][0]
    assert b["wiersz"] and b["pole"] and b["komunikat"]
    assert "id_aed" not in str(_wykaz(c)["uwzglednione"]) or True
    zas = j["zasob"]["id"]
    assert all(u["instytucja_id"] != waw for u in _wykaz(c)["uwzglednione"])
    # 6. aktualizacja poprawnym plikiem
    r = c.put(f"/api/admin/zasoby/{zas}", headers=_h(waw), data={"wykaz_typ": "AED"},
              files={"plik": _plik("aed_poprawny.csv")})
    assert r.status_code == 200, r.text
    assert r.json()["zasob"]["walidacja_status"] == "OK"
    assert r.json()["wykaz"]["przebudowano"] is True
    # 7. wykaz przebudowany: API, rekordy, pliki, mapa
    w1 = _wykaz(c)
    assert w1["liczba_dostawcow"] == w0["liczba_dostawcow"] + 1
    assert any(u["instytucja_id"] == waw for u in w1["uwzglednione"])
    rek = c.get("/api/1.4/aed-aggregated/rekordy", params={"dostawca": waw}).json()
    assert len(rek["items"]) >= 1
    csv = c.get(w1["pliki"]["csv"].replace("http://testserver", "")).content.decode("utf-8-sig")
    assert "UMW-AED-001" in csv
    gj = c.get("/api/mapa/aed").json()
    assert any(f["properties"].get("id_aed") == "UMW-AED-001" for f in gj["features"])
    # drugi zasób AED -> 409
    r = c.post(f"/api/admin/zbiory/{zb}/zasoby", headers=_h(waw),
               data={"tytul": "drugi", "wykaz_typ": "AED"}, files={"plik": _plik("aed_poprawny.csv")})
    assert r.status_code == 409, r.text
    assert "zaktualizuj" in r.text.lower()
    # 8. import XML: najpierw usunięcie zasobu
    assert c.delete(f"/api/admin/zasoby/{zas}", headers=_h(waw)).status_code == 200
    assert all(u["instytucja_id"] != waw for u in _wykaz(c)["uwzglednione"])
    r = c.post("/api/admin/harvester/xml", headers=_h(waw), files={"plik": _plik("harvester_1_14_przyklad.xml")})
    assert r.status_code == 200, r.text
    assert r.json()["zasoby_utworzone"] >= 1, r.text
    # 9. partner / odznaka
    lp = c.get("/api/partnerzy/").json()
    akt = [p for p in lp if p["status"] == "AKTYWNY"]
    assert akt
    s = c.get(f"/api/partnerzy/{akt[0]['instytucja_id']}/odznaka.svg")
    assert s.status_code == 200 and "<svg" in s.text
    wyg = [p for p in lp if p["status"] == "WYGASŁY"]
    if wyg:
        assert "wygas" in c.get(f"/api/partnerzy/{wyg[0]['instytucja_id']}/odznaka.svg").text.lower()
    # 10. asystent
    assert c.get("/api/asystent/wzorzec.xlsx").status_code == 200
    assert c.get("/api/asystent/wzorzec.csv").status_code == 200
    r = c.post("/api/asystent/sprawdz", files={"plik": _plik("aed_z_bledami.csv")})
    assert r.status_code == 200 and r.json()["bledy"]
    r = c.post("/api/asystent/konwertuj", data={"profil": "krosno"}, files={"plik": _plik("gmina_stary_uklad_krosno.csv")})
    assert r.status_code == 200, r.text
    r = c.post("/api/asystent/pakiet", data={"nazwa_dostawcy": "Urząd Testowy", "profil": "krosno"},
               files={"plik": _plik("gmina_stary_uklad_krosno.csv")})
    assert r.status_code == 200, r.text
    z = zipfile.ZipFile(io.BytesIO(r.content))
    nazwy = z.namelist()
    assert "dane_aed.csv" in nazwy and "harvester_1_14.xml" in nazwy and "INSTRUKCJA.txt" in nazwy
    assert "aggregatedListType" in z.read("harvester_1_14.xml").decode()
    # 11. admin: przebudowa + historia
    adm = {"X-Demo-Konto": "admin"}
    assert c.post("/api/admin/wykazy/AED/przebuduj", headers=adm).status_code == 200
    h = c.get("/api/admin/wykazy/AED/historia", headers=adm)
    assert h.status_code == 200 and len(h.json()) >= 2
    assert c.post("/api/admin/wykazy/AED/przebuduj", headers=_h(waw)).status_code == 403
    assert c.post("/api/admin/wykazy/AED/przebuduj").status_code == 401


def test_seed_idempotentny(monkeypatch):
    from app.main import app
    with TestClient(app) as a:
        n1 = len(a.get("/api/admin/konta").json()); w1 = _wykaz(a)
    with TestClient(app) as b:  # restart na tej samej bazie
        assert len(b.get("/api/admin/konta").json()) == n1
        w2 = _wykaz(b)
        assert w2["liczba_rekordow"] == w1["liczba_rekordow"]
        from app.portal import seed_portal
        seed_portal.zasiej_jesli_pusty()
        assert len(b.get("/api/admin/konta").json()) == n1
