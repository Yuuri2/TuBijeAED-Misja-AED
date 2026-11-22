"""Asystent dostawcy: pliki wzorca, sprawdzanie, konwersja plików gmin (każdy profil), pakiet ZIP z XML 1.14."""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import harvester, schema
from app.routers import asystent

FIX = Path(__file__).parent / "fixtures" / "danegov"
DEMO_CSV = (harvester.KATALOG_DEMO / "warszawa_aed_demo.csv").read_bytes()
PLIKI_GMIN = [
    ("krosno", "krosno_3624.csv", "podkarpackie", 6),
    ("przemysl", "przemysl_62093.geojson", "podkarpackie", 3),
    ("marki", "marki_4955.csv", "mazowieckie", 8),
    ("marki", "marki_4955.xlsx", "mazowieckie", 8),
    ("legionowo", "legionowo_2625221.csv", "mazowieckie", 7),
    ("warszawa", "warszawa_api_39512.json", "mazowieckie", 1),
]


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(asystent.router, prefix="/api/asystent")
    return TestClient(app)


def _wiersze(tekst: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(tekst)))


def test_pliki_wzorca(api):
    x = api.get("/api/asystent/wzorzec.xlsx")
    assert x.status_code == 200 and x.content[:2] == b"PK"
    c = api.get("/api/asystent/wzorzec.csv")
    assert c.status_code == 200 and c.text.splitlines()[0].split(",") == schema.nazwy_pol()
    s = api.get("/api/asystent/schemat.json").json()
    assert [f["name"] for f in s["fields"]] == schema.nazwy_pol()


def test_sprawdz_bez_zapisu(api):
    r = api.post("/api/asystent/sprawdz", files={"plik": ("aed.csv", DEMO_CSV, "text/csv")})
    assert r.status_code == 200 and r.json()["poprawne_wiersze"] == 3 and r.json()["bledne_wiersze"] == 0
    zly = DEMO_CSV.replace(b"00-950", b"00950X")
    j = api.post("/api/asystent/sprawdz", files={"plik": ("aed.csv", zly, "text/csv")}).json()
    assert j["bledne_wiersze"] == 1 and any(b["pole"] == "kod_pocztowy" and b["wiersz"] == 2 for b in j["bledy"])
    assert api.post("/api/asystent/sprawdz", files={"plik": ("a.pdf", b"%PDF", "x")}).status_code == 400
    assert api.post("/api/asystent/sprawdz", files={"plik": ("a.csv", b"", "text/csv")}).status_code == 400


@pytest.mark.parametrize("profil,plik,woj,liczba", PLIKI_GMIN)
def test_konwersja_kazdego_profilu_gminy(api, profil, plik, woj, liczba):
    r = api.post("/api/asystent/konwertuj", data={"profil": profil},
                 files={"plik": (plik, (FIX / plik).read_bytes(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    j = r.json()
    wiersze = _wiersze(j["csv"])
    assert j["csv"].splitlines()[0].split(",") == schema.nazwy_pol()            # dokładnie kolumny wzorca
    assert len(wiersze) == liczba == j["raport"]["liczba_rekordow"]
    assert {w["wojewodztwo"] for w in wiersze} == {woj}
    assert all(w["id_aed"] for w in wiersze)
    # NIE zgadujemy: zabezpieczenie dostępu i dysponent nie występują w plikach gmin -> puste + raport
    assert all(w["czy_zamkniete"] == "" and w["nazwa_dysponenta"] == "" for w in wiersze)
    braki = {b["pole"]: b for b in j["raport"]["do_uzupelnienia"]}
    assert braki["czy_zamkniete"]["puste_wiersze"] == liczba
    assert braki["czy_zamkniete"]["komunikat"] == "do uzupełnienia przez dostawcę"
    assert {"nazwa_dysponenta", "identyfikator_dysponenta", "data_aktualizacji"} <= set(braki)
    assert j["raport"]["walidacja"]["bledne_wiersze"] == liczba                  # braki = błędy walidacji


def test_konwersja_z_danymi_dysponenta_z_formularza(api):
    form = {"profil": "legionowo", "nazwa_dysponenta": "Urząd Miasta Legionowo",
            "identyfikator_dysponenta": "000524832", "typ_dysponenta": "JST",
            "kontakt_dysponenta": "kancelaria@um.legionowo.pl", "data_aktualizacji": "2026-11-20T10:00:00Z"}
    j = api.post("/api/asystent/konwertuj", data=form, files={
        "plik": ("l.csv", (FIX / "legionowo_2625221.csv").read_bytes(), "text/csv")}).json()
    w = _wiersze(j["csv"])
    assert {x["nazwa_dysponenta"] for x in w} == {"Urząd Miasta Legionowo"}
    assert {x["data_aktualizacji"] for x in w} == {"2026-11-20T10:00:00Z"}
    braki = {b["pole"] for b in j["raport"]["do_uzupelnienia"]}
    assert "nazwa_dysponenta" not in braki and "czy_zamkniete" in braki


def test_konwersja_auto(api):
    def auto(plik):
        return api.post("/api/asystent/konwertuj", data={"profil": "auto"},
                        files={"plik": (plik, (FIX / plik).read_bytes(), "x")}).json()
    j = auto("legionowo_2625221.csv")
    assert j["raport"]["profil_wykryty"] == "legionowo" and j["nazwa_pliku"] == "dane_aed_legionowo.csv"
    # Krosno i Marki mają ten sam układ kolumn -> kolumny tak, obszar NIE (nie zgadujemy gminy)
    j = auto("krosno_3624.csv")
    assert j["raport"]["profil_wykryty"] is None
    assert any("krosno, marki" in o for o in j["raport"]["ostrzezenia_konwersji"])
    w = _wiersze(j["csv"])
    assert {x["wojewodztwo"] for x in w} == {""} and all(x["szerokosc_geo"] for x in w)


def test_konwersja_bledy_i_csv(api):
    plik = {"plik": ("k.csv", (FIX / "krosno_3624.csv").read_bytes(), "text/csv")}
    assert api.post("/api/asystent/konwertuj", data={"profil": "gdansk"}, files=plik).status_code == 422
    assert api.post("/api/asystent/konwertuj", files={"plik": ("a.txt", b"abc", "x")}).status_code == 400
    r = api.post("/api/asystent/konwertuj?format=csv", data={"profil": "krosno"}, files=plik)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="dane_aed_krosno.csv"' in r.headers["content-disposition"]


def _zip(r) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_pakiet_zip_z_xml_1_14(api):
    r = api.post("/api/asystent/pakiet", data={"nazwa_dostawcy": "Urząd m.st. Warszawy",
                                               "url_zasobu": "https://bip.example.pl/aed/dane_aed.csv"},
                 files={"plik": ("dane.csv", DEMO_CSV, "text/csv")})
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert r.headers["x-poprawne-wiersze"] == "3" and r.headers["x-bledne-wiersze"] == "0"
    pliki = _zip(r)
    assert set(pliki) == {"dane_aed.csv", "harvester_1_14.xml", "INSTRUKCJA.txt"}
    wersja, korzen = harvester.wczytaj_i_waliduj(pliki["harvester_1_14.xml"])       # XSD 1.14
    assert wersja == "1.14"
    zs = harvester.parsuj(korzen)[0].zasoby[0]
    assert zs.wykaz_typ == "AED" and zs.url == "https://bip.example.pl/aed/dane_aed.csv"
    assert len(_wiersze(pliki["dane_aed.csv"].decode())) == 3
    instr = pliki["INSTRUKCJA.txt"].decode()
    for fraza in ("Sposób A", "Sposób B", "Zasób wchodzi do Wykazu zbiorczego AED", "aggregatedListType",
                  "3 poprawnych", "112"):
        assert fraza in instr
    assert "ZAMIEŃ" not in instr


def test_pakiet_z_konwersja_i_adresem_zastepczym(api):
    r = api.post("/api/asystent/pakiet", data={"nazwa_dostawcy": "Urząd Miasta Krosna", "profil": "krosno"},
                 files={"plik": ("k.csv", (FIX / "krosno_3624.csv").read_bytes(), "text/csv")})
    assert r.status_code == 200
    pliki = _zip(r)
    assert harvester.wczytaj_i_waliduj(pliki["harvester_1_14.xml"])[0] == "1.14"
    instr = pliki["INSTRUKCJA.txt"].decode()
    assert "ZAMIEŃ" in instr and "6 z błędami" in instr and "NIE wejdzie do Wykazu" in instr
    assert b"<terytIdent>1861011</terytIdent>" in pliki["harvester_1_14.xml"]


def test_pakiet_walidacja_formularza(api):
    plik = {"plik": ("dane.csv", DEMO_CSV, "text/csv")}
    assert api.post("/api/asystent/pakiet", data={"nazwa_dostawcy": " "}, files=plik).status_code == 422
    assert api.post("/api/asystent/pakiet", data={"nazwa_dostawcy": "X", "url_zasobu": "http://a.pl/a.csv"},
                    files=plik).status_code == 422
    assert api.post("/api/asystent/pakiet", data={"nazwa_dostawcy": "X", "licencja": "ODbL 1.0"},
                    files=plik).status_code == 422
