"""Testy API Backendu przez TestClient: /aed, /schema, /statystyki, /dysponent/*, /upload-institution, seed."""
import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app import repo, seed
from tests.test_validation import dobry, zrob_csv

WZORZEC = Path(__file__).resolve().parents[2] / "1_wzorzec_danych"
FORM = {"nazwa_dysponenta": "Urząd Testowy", "identyfikator_dysponenta": "5252248481", "typ_dysponenta": "JST"}


def csv_plik(wiersze):
    return {"file": ("dane.csv", zrob_csv(wiersze), "text/csv")}


def xlsx_przykladowe() -> bytes:
    wb = load_workbook(WZORZEC / "wzorzec_danych_aed.xlsx")
    del wb["Dane"]
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_aplikacja_serwuje_statyczny_index_i_api_pod_prefiksem(client):
    r = client.get("/")
    assert r.status_code == 200 and "AED" in r.text
    assert client.get("/api/v1/aed").json() == {"count": 0, "items": []}


def test_schema_i_statystyki_pustej_bazy(client):
    s = client.get("/api/v1/schema").json()
    assert s["name"] == "aed-wzorzec" and s["fields"]
    st = client.get("/api/v1/statystyki").json()
    assert st["razem"] == 0 and st["wg_zrodlo_typ"] == {}


def test_walidacja_wzorca_xlsx_przyklady_zero_bledow(client):
    r = client.post("/api/v1/dysponent/walidacja", files={"file": ("wzorzec.xlsx", xlsx_przykladowe(), "application/octet-stream")})
    assert r.status_code == 200
    j = r.json()
    assert j["bledy"] == [] and j["poprawne_wiersze"] == 3 and j["bledne_wiersze"] == 0
    assert client.get("/api/v1/aed").json()["count"] == 0          # walidacja nic nie zapisuje


def test_walidacja_raport_per_wiersz(client):
    r = client.post("/api/v1/dysponent/walidacja", files=csv_plik([dobry(), dobry(id_aed="B", kod_pocztowy="123", identyfikator_dysponenta="5252248482")]))
    j = r.json()
    assert j["poprawne_wiersze"] == 1 and j["bledne_wiersze"] == 1
    assert {(b["wiersz"], b["pole"], b["kod"]) for b in j["bledy"]} == {(3, "kod_pocztowy", "pattern"), (3, "identyfikator_dysponenta", "suma_kontrolna")}


@pytest.mark.parametrize("nazwa,tresc,status", [("a.txt", b"x", 400), ("a.xlsx", b"nie-xlsx", 400), ("a.csv", b"", 400)])
def test_walidacja_zle_pliki(client, nazwa, tresc, status):
    r = client.post("/api/v1/dysponent/walidacja", files={"file": (nazwa, tresc, "application/octet-stream")})
    assert r.status_code == status and r.json()["error"]


def test_walidacja_za_duzy_plik(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "MAX_FILE_BYTES", 50)
    r = client.post("/api/v1/dysponent/walidacja", files={"file": ("a.csv", b"a" * 500, "text/csv")})
    assert r.status_code == 413


def test_zgloszenie_zapisuje_i_oznacza_zrodlo(client):
    r = client.post("/api/v1/dysponent/zgloszenie", data=FORM, files=csv_plik([dobry(), dobry(id_aed="B", szerokosc_geo=52.3)]))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["zapisano"] == 2 and j["bledne_wiersze"] == 0 and j["zrodlo_id"] == "dysponent:5252248481"
    items = client.get("/api/v1/aed").json()["items"]
    assert len(items) == 2
    for it in items:
        assert it["zrodlo_typ"] == "DYSPONENT" and it["status_weryfikacji"] == "ZGLOSZONY_PRZEZ_DYSPONENTA"
        assert it["licencja"] == "CC BY 4.0" and it["zrodlo_id"] == "dysponent:5252248481"
    zr = client.get("/api/v1/aed/" + items[0]["uid"])      # uid z dwukropkami
    assert zr.status_code == 200 and zr.json()["uid"] == items[0]["uid"]
    st = client.get("/api/v1/statystyki").json()
    assert st["razem"] == 2 and st["wg_status_weryfikacji"] == {"ZGLOSZONY_PRZEZ_DYSPONENTA": 2}


def test_zgloszenie_pola_formularza_nadpisuja_plik(client):
    form = {"nazwa_dysponenta": "Nazwa z formularza", "identyfikator_dysponenta": "525-224-84-81", "typ_dysponenta": "NGO_Inne"}
    r = client.post("/api/v1/dysponent/zgloszenie", data=form, files=csv_plik([dobry(nazwa_dysponenta="Z pliku", identyfikator_dysponenta="5250000251", typ_dysponenta="JST")]))
    assert r.status_code == 200 and r.json()["zapisano"] == 1
    it = client.get("/api/v1/aed").json()["items"][0]
    assert (it["nazwa_dysponenta"], it["identyfikator_dysponenta"], it["typ_dysponenta"]) == ("Nazwa z formularza", "5252248481", "NGO_Inne")
    assert it["uid"] == "DYSPONENT:5252248481:TEST-001"


def test_zgloszenie_bledny_nip_z_formularza(client):
    r = client.post("/api/v1/dysponent/zgloszenie", data={**FORM, "identyfikator_dysponenta": "5252248482"}, files=csv_plik([dobry()]))
    assert r.status_code == 422
    assert r.json()["bledy_formularza"][0]["kod"] == "suma_kontrolna"
    assert client.get("/api/v1/aed").json()["count"] == 0


def test_zgloszenie_brak_pol_formularza(client):
    r = client.post("/api/v1/dysponent/zgloszenie", data={"nazwa_dysponenta": "X"}, files=csv_plik([dobry()]))
    assert r.status_code == 422
    assert {b["pole"] for b in r.json()["bledy_formularza"]} == {"identyfikator_dysponenta", "typ_dysponenta"}


def test_zgloszenie_zapisuje_tylko_poprawne_wiersze(client):
    r = client.post("/api/v1/dysponent/zgloszenie", data=FORM, files=csv_plik([dobry(id_aed="OK"), dobry(id_aed="ZLY", kod_pocztowy="x")]))
    j = r.json()
    assert j["zapisano"] == 1 and j["bledne_wiersze"] == 1 and j["bledy"][0]["wiersz"] == 3
    assert [i["id_aed"] for i in client.get("/api/v1/aed").json()["items"]] == ["OK"]


def test_zgloszenie_z_bledami_nie_usuwa_wczesniejszych_rekordow(client):
    client.post("/api/v1/dysponent/zgloszenie", data=FORM, files=csv_plik([dobry(id_aed="A"), dobry(id_aed="B", szerokosc_geo=52.3)]))
    client.post("/api/v1/dysponent/zgloszenie", data=FORM, files=csv_plik([dobry(id_aed="A"), dobry(id_aed="B", kod_pocztowy="x")]))
    assert sorted(i["id_aed"] for i in client.get("/api/v1/aed").json()["items"]) == ["A", "B"]
    # plik bez błędów = pełna synchronizacja
    client.post("/api/v1/dysponent/zgloszenie", data=FORM, files=csv_plik([dobry(id_aed="A")]))
    assert [i["id_aed"] for i in client.get("/api/v1/aed").json()["items"]] == ["A"]


def test_zgloszenie_xlsx_ze_wzorca(client):
    r = client.post("/api/v1/dysponent/zgloszenie", data=FORM, files={"file": ("w.xlsx", xlsx_przykladowe(), "application/octet-stream")})
    assert r.status_code == 200 and r.json()["zapisano"] == 3
    assert client.get("/api/v1/aed", params={"wojewodztwo": "śląskie"}).json()["count"] == 1


def test_alias_upload_institution(client):
    r = client.post("/api/v1/upload-institution", data={"nazwa_dysponenta": "Urząd", "nip_regon": "5252248481", "typ_dysponenta": "JST"}, files=csv_plik([dobry()]))
    assert r.status_code == 200
    j = r.json()
    assert j["imported"] == 1 and "message" in j and isinstance(j["warnings"], list)
    assert client.get("/api/v1/aed").json()["count"] == 1


def test_aed_filtry_i_bbox(client):
    client.post("/api/v1/dysponent/zgloszenie", data=FORM, files=csv_plik([dobry(id_aed="W"), dobry(id_aed="K", wojewodztwo="małopolskie", szerokosc_geo=50.06, dlugosc_geo=19.94)]))
    g = lambda **p: client.get("/api/v1/aed", params=p).json()          # noqa: E731
    assert g(wojewodztwo="małopolskie")["count"] == 1
    assert g(zrodlo_typ="OSM")["count"] == 0 and g(zrodlo_typ="DYSPONENT")["count"] == 2
    assert g(status_weryfikacji="ZGLOSZONY_PRZEZ_DYSPONENTA")["count"] == 2
    assert [i["id_aed"] for i in g(bbox="19.5,49.9,20.5,50.2")["items"]] == ["K"]
    assert client.get("/api/v1/aed", params={"bbox": "abc"}).status_code == 422


def test_aed_duplikaty_domyslnie_ukryte(client):
    gov = repo.Zrodlo(id="dane-gov-pl:1", typ="DANE_GOV_PL", nazwa="G", url=None, licencja="CC BY 4.0")
    osm = repo.Zrodlo(id="osm:X", typ="OSM", nazwa="O", url=None, licencja="ODbL 1.0")
    repo.zarejestruj_zrodlo(gov)
    repo.zarejestruj_zrodlo(osm)
    repo.zapisz_rekordy([{**dobry(), "id_aed": "G1", "szerokosc_geo": 52.0, "dlugosc_geo": 21.0}], gov.id)
    repo.zapisz_rekordy([{"id_aed": "n1", "szerokosc_geo": 52.00003, "dlugosc_geo": 21.0}], osm.id)
    assert client.get("/api/v1/aed").json()["count"] == 1
    wszystkie = client.get("/api/v1/aed", params={"uwzglednij_duplikaty": "true"}).json()
    assert wszystkie["count"] == 2 and any(i["duplikat_z"] for i in wszystkie["items"])
    assert client.get("/api/v1/statystyki").json()["duplikaty"] == 1


def test_aed_404(client):
    r = client.get("/api/v1/aed/nie:ma:takiego")
    assert r.status_code == 404 and r.json()["error"]


def test_seed_tylko_do_pustej_bazy_i_oznaczony_jako_przykladowy():
    assert seed.zasiej_jesli_pusta() == 3
    rekordy = repo.lista_rekordow()
    assert len(rekordy) == 3
    for r in rekordy:
        assert r["zrodlo_nazwa"] == "DANE PRZYKŁADOWE (demo)" and r["zrodlo_typ"] == "DYSPONENT"
        assert r["status_weryfikacji"] == "ZGLOSZONY_PRZEZ_DYSPONENTA"
    assert seed.zasiej_jesli_pusta() == 0 and len(repo.lista_rekordow()) == 3


def test_seed_przechodzi_walidacje_schematu():
    from app import validation
    for r in seed.REKORDY_PRZYKLADOWE:
        _, bledy, _ = validation.waliduj_wiersz(r)
        assert bledy == [], (r["id_aed"], bledy)


def test_start_aplikacji_zasiewa_baze():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/v1/aed").json()["count"] == 3
