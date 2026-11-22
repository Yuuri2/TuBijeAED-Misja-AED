"""Partner #TuBijeAED: status (aktywny / wygasły / brak), API i odznaka SVG."""
from __future__ import annotations

from datetime import date

import pytest

from app.portal import partnerzy
from tests.portal_pomoc import aed, dodaj_aed, portal_testowy


@pytest.fixture
def p():
    p = portal_testowy()
    dodaj_aed(p["zbior"][p["a"]["id"]], [aed("A1", data_przegladu="2026-01-01")], data_danych="2026-03-01")
    dodaj_aed(p["zbior"][p["b"]["id"]], [aed("B1", kod_pocztowy="zly")], data_danych="2026-03-01")
    return p


def test_status_aktywny_wygasly_brak(p):
    a = p["a"]["id"]
    s = partnerzy.status_partnera(a, teraz=date(2026, 11, 22))
    assert s["status"] == "AKTYWNY" and s["wazny_do"] == "2027-03-01"
    assert all(k["spelnione"] for k in s["kryteria"]) and len(s["kryteria"]) == 4

    s = partnerzy.status_partnera(a, teraz=date(2027, 3, 2))
    assert s["status"] == "WYGASŁY" and s["wazny_do"] == "2027-03-01"
    assert [k["nazwa"] for k in s["kryteria"] if not k["spelnione"]] == ["aktualnosc_12_miesiecy"]

    s = partnerzy.status_partnera(p["b"]["id"], teraz=date(2026, 11, 22))     # zasób z błędami
    assert s["status"] == "BRAK" and s["wazny_do"] is None
    assert {k["nazwa"] for k in s["kryteria"] if not k["spelnione"]} >= {"zasob_w_wykazie", "bez_bledow_walidacji"}

    assert partnerzy.status_partnera(p["c"]["id"])["status"] == "BRAK"       # bez zasobu


def test_kompletnosc_ponad_minimum_to_brak(p):
    # rekord poprawny, ale bez żadnych pól zalecanych/opcjonalnych -> 0% „ponad minimum” (poniżej progu 50%)
    gole = dict(teryt_gmina=None, simc=None, data_przegladu=None, ulica=None, kondygnacja=None,
                elektrody_pediatryczne=None, producent_model=None, zdjecie_url=None)
    c = p["c"]["id"]
    dodaj_aed(p["zbior"][c], [aed("C1", **gole)])
    s = partnerzy.status_partnera(c)
    assert s["status"] == "BRAK" and s["kompletnosc"] < partnerzy.PROG_KOMPLETNOSCI
    assert [k["nazwa"] for k in s["kryteria"] if not k["spelnione"]] == ["kompletnosc_80"]
    assert "ponad" in next(k["opis"] for k in s["kryteria"] if k["nazwa"] == "kompletnosc_80")


def test_kompletnosc_ponad_minimum_wyliczenie():
    assert partnerzy.kompletnosc_ponad_minimum({}) == 0.0
    r = {"teryt_gmina": "1", "simc": "2", "data_przegladu": "2026-01-01", "ulica": "x"}
    assert partnerzy.kompletnosc_ponad_minimum(r) == pytest.approx(4 / 8)


def test_api_partnerzy_i_odznaka(client, p):
    a = p["a"]["id"]
    lista = client.get("/api/partnerzy").json()
    assert [x["instytucja"]["id"] for x in lista] == [a]
    j = client.get(f"/api/partnerzy/{a}").json()
    assert j["status"] == "AKTYWNY" and j["link"].endswith(f"/partner.html?id={a}")
    assert f"/api/partnerzy/{a}/odznaka.svg" in j["kod_osadzenia"]
    assert client.get("/api/partnerzy/9999").status_code == 404

    for wariant in ("jasna", "ciemna"):
        for rozmiar in ("pelna", "mala"):
            r = client.get(f"/api/partnerzy/{a}/odznaka.svg?wariant={wariant}&rozmiar={rozmiar}")
            assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
            assert "01.03.2027" in r.text and "DD.MM.RRRR" not in r.text
            assert "<script" not in r.text.lower() and " on" not in r.text.split("<svg", 1)[1].split(">", 1)[0].lower()
    assert client.get(f"/api/partnerzy/{p['b']['id']}/odznaka.svg").status_code == 404
    assert client.get(f"/api/partnerzy/{a}/odznaka.svg?wariant=zielona").status_code == 422


def test_odznaka_wygasla_szara(p):
    s = partnerzy.status_partnera(p["a"]["id"], teraz=date(2028, 1, 1))
    svg = partnerzy.odznaka_svg(s, wariant="ciemna", rozmiar="pelna")
    assert "wygasła 01.03.2027" in svg
    assert 'stroke-dasharray' in svg        # wariant wygasły (różni się nie tylko kolorem)


def test_oczyszczanie_svg():
    brudny = '<svg onload="alert(1)"><script>alert(2)</script><a href="javascript:x()">t</a></svg>'
    czysty = partnerzy._oczysc_svg(brudny)
    assert "script" not in czysty and "onload" not in czysty and "javascript" not in czysty
