"""Wykaz zbiorczy AED: walidacja zasobu (wzór: DGA w ResourceForm) i scalanie (wzór: create_main_dga_resource_task)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app import schema
from app.portal import repo_portal, wykazy
from app.portal.wykazy import BladWykazu
from tests.portal_pomoc import aed, dodaj_aed, plik_csv, portal_testowy


@pytest.fixture
def p():
    return portal_testowy()


# ----------------------------------------------------------------------------- walidacja zasobu

def test_konfiguracja_aed_kolumny_wynikowe():
    k = wykazy.WYKAZY["AED"]
    assert k.kolumny == tuple(schema.nazwy_pol())
    assert k.kolumny_wynikowe[:6] == ("nazwa_dostawcy", "regon_dostawcy", "typ_dostawcy", "id_zasobu_zrodlowego",
                                      "url_zasobu_zrodlowego", "data_aktualizacji_zasobu")
    assert k.wlasciciel == "Ministerstwo Cyfryzacji" and k.rozszerzenia == ("xlsx", "csv")
    assert set(k.dozwolone_typy_instytucji) == {"local", "state", "private", "other"}


def test_brak_kolumn_wzorca_422_i_zasob_niezapisany(p):
    kolumny = [k for k in schema.nazwy_pol() if k not in ("czy_zamkniete", "status_urzadzenia")]
    with pytest.raises(BladWykazu) as e:
        repo_portal.dodaj_lub_zaktualizuj_zasob(p["zbior"][p["a"]["id"]], tytul="AED", plik=plik_csv([aed("A1")], kolumny),
                                                nazwa_pliku="aed.csv", wykaz_typ="AED")
    assert e.value.kod_http == 422
    assert set(e.value.szczegoly["brakujace_kolumny"]) == {"czy_zamkniete", "status_urzadzenia"}
    assert repo_portal.lista_zasobow(p["zbior"][p["a"]["id"]]) == []


def test_kolejnosc_kolumn_dowolna(p):
    kolumny = list(reversed(schema.nazwy_pol()))
    w = repo_portal.dodaj_lub_zaktualizuj_zasob(p["zbior"][p["a"]["id"]], tytul="AED", plik=plik_csv([aed("A1")], kolumny),
                                                nazwa_pliku="aed.csv", wykaz_typ="AED")
    assert w["zasob"]["walidacja_status"] == "OK" and w["wykaz"]["przebudowano"]


def test_zly_format_pliku_422(p):
    with pytest.raises(BladWykazu) as e:
        repo_portal.dodaj_lub_zaktualizuj_zasob(p["zbior"][p["a"]["id"]], tytul="AED", plik=b"{}", nazwa_pliku="aed.json",
                                                wykaz_typ="AED")
    assert e.value.kod_http == 422


def test_bledy_wierszy_zapis_ze_statusem_bledy_i_poza_wykazem(p):
    dodaj_aed(p["zbior"][p["a"]["id"]], [aed("A1")])
    w = dodaj_aed(p["zbior"][p["b"]["id"]], [aed("B1"), aed("B2", kod_pocztowy="123")])
    assert w["zasob"]["walidacja_status"] == "BLEDY"
    assert {(b["wiersz"], b["pole"], b["kod"]) for b in w["walidacja"]["bledy"]} == {(3, "kod_pocztowy", "pattern")}
    wyk = wykazy.aktualny_wykaz()
    assert [u["instytucja"] for u in wyk["uwzglednione"]] == ["Urząd Miasta Alfa"]
    pom = {x["zasob_id"]: x["powod"] for x in wyk["pominiete"]}
    assert "walidacji" in pom[w["zasob"]["id"]]
    assert {r["id_aed"] for r in wykazy.rekordy_wykazu()} == {"A1"}


def test_drugi_opublikowany_zasob_instytucji_409_i_potwierdzenie(p):
    zb = p["zbior"][p["a"]["id"]]
    pierwszy = dodaj_aed(zb, [aed("A1")])["zasob"]
    drugi_zbior = repo_portal.utworz_zbior(p["a"]["id"], tytul="Inny zbiór", opis="")["id"]
    with pytest.raises(BladWykazu) as e:
        dodaj_aed(drugi_zbior, [aed("A2")])
    assert e.value.kod_http == 409 and "zaktualizuj istniejący zasób" in e.value.komunikat
    assert e.value.szczegoly["istniejacy_zasob_id"] == pierwszy["id"]
    # szkic nie narusza reguły
    assert dodaj_aed(drugi_zbior, [aed("A2")], status="szkic")["zasob"]["status"] == "szkic"
    # aktualizacja tego samego zasobu – dozwolona
    dodaj_aed(zb, [aed("A1"), aed("A3", lat=52.3)], zasob_id=pierwszy["id"])
    # potwierdzone zastąpienie zdejmuje flagę z poprzedniego (wzór: _remove_dga_flag_from_current_dga_resource_if_needed)
    w = dodaj_aed(drugi_zbior, [aed("A9")], potwierdz_zastapienie=True)
    assert w["wykaz"]["zdjeto_oznaczenie_z_zasobu"] == pierwszy["id"]
    assert repo_portal.pobierz_zasob(pierwszy["id"])["wykaz_typ"] is None
    assert {r["id_aed"] for r in wykazy.rekordy_wykazu()} == {"A9"}


def test_niedozwolony_typ_instytucji_422(p):
    with pytest.raises(BladWykazu) as e:
        dodaj_aed(p["zbior"][p["dev"]["id"]], [aed("D1")])
    assert e.value.kod_http == 422 and e.value.szczegoly["typ_instytucji"] == "developer"


def test_zasob_bez_wykazu_nie_jest_walidowany(p):
    w = repo_portal.dodaj_lub_zaktualizuj_zasob(p["zbior"][p["a"]["id"]], tytul="Regulamin", plik=b"%PDF-1.4",
                                                nazwa_pliku="regulamin.pdf")
    assert w["zasob"]["walidacja_status"] == "NIE_DOTYCZY" and w["zasob"]["format"] == "pdf"
    assert w["wykaz"]["przebudowano"] is False and wykazy.aktualny_wykaz() is None


def test_upsert_po_ext_ident(p):
    zb = p["zbior"][p["a"]["id"]]
    a = dodaj_aed(zb, [aed("A1")], ext_ident="h-1")["zasob"]
    b = dodaj_aed(zb, [aed("A1"), aed("A2", lat=52.4)], ext_ident="h-1")["zasob"]
    assert a["id"] == b["id"] and b["liczba_wierszy"] == 2
    assert len(repo_portal.lista_zasobow(zb)) == 1
    z1 = repo_portal.utworz_zbior(p["a"]["id"], tytul="X", opis="", zrodlo="harvester", ext_ident="ds-1")
    z2 = repo_portal.utworz_zbior(p["a"]["id"], tytul="Y", opis="", zrodlo="harvester", ext_ident="ds-1")
    assert z1["id"] == z2["id"] and z2["tytul"] == "Y"


# ----------------------------------------------------------------------------- scalanie

def _trzech_dostawcow(p):
    dodaj_aed(p["zbior"][p["c"]["id"]], [aed("C1", lat=50.0, lon=19.0, wojewodztwo="małopolskie")])
    dodaj_aed(p["zbior"][p["b"]["id"]], [aed("B1", lat=52.1, lon=21.1), aed("B2", lat=52.2001, lon=21.0001)])
    dodaj_aed(p["zbior"][p["a"]["id"]], [aed("A1", lat=52.2, lon=21.0)])


def test_scalanie_wielu_dostawcow_kolumny_kolejnosc_i_pliki(p):
    _trzech_dostawcow(p)
    w = wykazy.aktualny_wykaz()
    k = wykazy.WYKAZY["AED"]
    assert w["status"] == "OK" and w["liczba_dostawcow"] == 3 and w["liczba_rekordow"] == 4
    # kolejność dostawców wg polskiego alfabetu (Ć po C, przed D) – jak order_by organization title
    assert [u["instytucja"] for u in w["uwzglednione"]] == ["Bank Beta S.A.", "Ćma Gmina", "Urząd Miasta Alfa"]

    wb = load_workbook(w["pliki"]["xlsx"])
    ws = wb["Arkusz 1"]
    naglowek = [c.value for c in ws[1]]
    assert naglowek == list(k.kolumny_wynikowe)
    assert ws.freeze_panes == "A2" and ws.max_row == 5
    pierwszy = dict(zip(naglowek, [c.value for c in ws[2]]))
    assert pierwszy["nazwa_dostawcy"] == "Bank Beta S.A." and pierwszy["typ_dostawcy"] == "private"
    assert pierwszy["regon_dostawcy"] == "123456785" and pierwszy["url_zasobu_zrodlowego"].endswith(
        f"/api/1.4/resources/{pierwszy['id_zasobu_zrodlowego']}")

    with open(w["pliki"]["csv"], encoding="utf-8") as f:
        cz = list(csv.reader(f))
    assert cz[0] == list(k.kolumny_wynikowe) and len(cz) == 5

    geo = json.loads(Path(w["pliki"]["geojson"]).read_text(encoding="utf-8"))
    assert geo["type"] == "FeatureCollection" and len(geo["features"]) == 4
    f0 = geo["features"][0]
    assert f0["geometry"]["coordinates"] == [f0["properties"]["dlugosc_geo"], f0["properties"]["szerokosc_geo"]]

    # zasoby wykazu w zbiorze MC
    zb = repo_portal.pobierz_zbior(w["zbior_id"])
    assert zb["instytucja_id"] == p["mc"]["id"] and zb["czy_wykaz_zbiorczy"] and zb["zrodlo"] == "system"
    assert zb["tytul"] == "Wykaz defibrylatorów AED – wykaz zbiorczy"
    assert {z["format"] for z in repo_portal.lista_zasobow(w["zbior_id"])} == {"xlsx", "csv", "geojson"}
    assert all(z["walidacja_status"] == "OK" for z in repo_portal.lista_zasobow(w["zbior_id"]))
    assert repo_portal.lista_zbiorow(tylko_wykazy=True)[0]["id"] == w["zbior_id"]

    # raport jakości: B2 jest ~13 m od A1 (inni dostawcy) – tylko informacja, oba rekordy zostają
    dupl = w["raport_jakosci"]["potencjalne_duplikaty"]
    assert len(dupl) == 1 and {dupl[0]["a"]["id_aed"], dupl[0]["b"]["id_aed"]} == {"A1", "B2"}
    assert {r["id_aed"] for r in wykazy.rekordy_wykazu()} == {"A1", "B1", "B2", "C1"}


def test_filtry_rekordow(p):
    _trzech_dostawcow(p)
    assert {r["id_aed"] for r in wykazy.rekordy_wykazu(wojewodztwo="Małopolskie")} == {"C1"}
    assert {r["id_aed"] for r in wykazy.rekordy_wykazu(instytucja_id=p["b"]["id"])} == {"B1", "B2"}
    assert {r["id_aed"] for r in wykazy.rekordy_wykazu(bbox=(20.9, 52.15, 21.05, 52.25))} == {"A1", "B2"}
    r = wykazy.rekordy_wykazu(instytucja_id=p["a"]["id"])[0]
    assert r["instytucja_id"] == p["a"]["id"] and r["nazwa_dostawcy"] == "Urząd Miasta Alfa"


def test_pominiety_zasob_z_powodem_gdy_plik_nieczytelny(p):
    _trzech_dostawcow(p)
    z = repo_portal.lista_zasobow(p["zbior"][p["c"]["id"]])[0]
    Path(repo_portal.pobierz_zasob(z["id"])["plik_sciezka"]).write_bytes(b"")    # uszkodzenie pliku na dysku
    info = wykazy.utworz_wykaz_zbiorczy("AED")
    assert info["status"] == "OK" and info["liczba_dostawcow"] == 2
    assert [x["powod"] for x in info["pominiete"] if x["zasob_id"] == z["id"]][0].startswith("nie można odczytać")


def test_przebudowa_po_zmianie_i_usunieciu_zasobu(p):
    _trzech_dostawcow(p)
    stary = wykazy.aktualny_wykaz()
    z = repo_portal.lista_zasobow(p["zbior"][p["a"]["id"]])[0]
    w = dodaj_aed(p["zbior"][p["a"]["id"]], [aed("A1"), aed("A5", lat=52.5)], zasob_id=z["id"])
    assert w["wykaz"]["przebudowano"]
    nowy = wykazy.aktualny_wykaz()
    assert nowy["id"] != stary["id"] and nowy["liczba_rekordow"] == 5
    # poprzednie pliki i zasoby wykazu usunięte (krok 4)
    assert not Path(stary["pliki"]["xlsx"]).exists() and repo_portal.pobierz_zasob(stary["zasob_id"]) is None
    assert len(repo_portal.lista_zasobow(nowy["zbior_id"])) == 3

    # zdjęcie oznaczenia wykazu -> dostawca znika z wykazu
    dodaj_aed(p["zbior"][p["a"]["id"]], [aed("A1")], zasob_id=z["id"], wykaz_typ=None)
    assert {u["instytucja"] for u in wykazy.aktualny_wykaz()["uwzglednione"]} == {"Bank Beta S.A.", "Ćma Gmina"}

    zb = repo_portal.lista_zasobow(p["zbior"][p["b"]["id"]])[0]
    wynik = repo_portal.usun_zasob(zb["id"])
    assert wynik["wykaz"]["przebudowano"]
    assert [u["instytucja"] for u in wykazy.aktualny_wykaz()["uwzglednione"]] == ["Ćma Gmina"]
    assert len(wykazy.historia()) == 6 and wykazy.historia()[0]["aktualny"]


def test_blad_scalania_nie_niszczy_poprzedniego_wykazu(p, monkeypatch):
    _trzech_dostawcow(p)
    stary = wykazy.aktualny_wykaz()
    rekordy_przed = wykazy.rekordy_wykazu()

    def awaria(*a, **kw):
        raise RuntimeError("symulowana awaria weryfikacji")

    monkeypatch.setattr(wykazy, "_zweryfikuj_wynik", awaria)
    info = wykazy.utworz_wykaz_zbiorczy("AED")
    assert info["status"] == "BLAD" and "symulowana awaria" in info["komunikat"]
    akt = wykazy.aktualny_wykaz()
    assert akt["id"] == stary["id"] and Path(akt["pliki"]["xlsx"]).exists()
    assert wykazy.rekordy_wykazu() == rekordy_przed
    # sprzątanie: brak osieroconych zasobów wykazu (wzór: clean_up_after_main_dga_resource_creation)
    assert len(repo_portal.lista_zasobow(stary["zbior_id"])) == 3
    katalogi = list((Path(stary["pliki"]["xlsx"]).parents[1]).iterdir())
    assert len(katalogi) == 1
    assert [h["status"] for h in wykazy.historia()][:2] == ["BLAD", "OK"]


def test_blad_pierwszego_scalania_bez_wlasciciela(p):
    # brak MC -> wpis BLAD, brak wykazu (jak ObjectDoesNotExist w create_main_dga_dataset)
    from app.portal import baza
    with baza.transakcja() as con:
        con.execute("UPDATE instytucje SET nazwa = 'MC (zmieniona)' WHERE id = ?", (p["mc"]["id"],))
    w = dodaj_aed(p["zbior"][p["a"]["id"]], [aed("A1")])
    assert w["wykaz"]["przebudowano"] is False and "właściciela" in w["wykaz"]["komunikat"]
    assert wykazy.aktualny_wykaz() is None
    assert repo_portal.lista_zbiorow(tylko_wykazy=True) == []


def test_pusty_wykaz_tworzony_jak_w_dga(p):
    info = wykazy.utworz_wykaz_zbiorczy("AED")
    assert info["status"] == "OK" and info["liczba_rekordow"] == 0
    assert wykazy.rekordy_wykazu() == []
