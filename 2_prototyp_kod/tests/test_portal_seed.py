"""Seed portalu (dane demo bez sieci) i start aplikacji."""
from __future__ import annotations

from app.portal import partnerzy, repo_portal, seed_portal, wykazy


def test_seed_buduje_wykaz_z_co_najmniej_3_dostawcami_i_pokazuje_odrzucenie():
    s = seed_portal.zasiej()
    w = wykazy.aktualny_wykaz()
    assert s["wykaz"]["status"] == "OK" and w["liczba_dostawcow"] >= 4
    uwz = {u["instytucja"] for u in w["uwzglednione"]}
    pom = {x["instytucja"] for x in w["pominiete"]}
    assert {"Urząd Miasta Legionowo", "Urząd Miejski w Przemyślu"} <= uwz       # migracja gmin (scenariusz demo)
    assert {r["wojewodztwo"] for r in wykazy.rekordy_wykazu("AED")} >= {"mazowieckie", "podkarpackie"}
    assert any("fikcyjna" in n and "błędami" in n for n in pom)                # firma z błędami odrzucona
    assert {"Urząd Miasta Krosna", "Urząd Miasta Marki"} <= pom
    assert w["raport_jakosci"]["liczba_potencjalnych_duplikatow"] >= 1

    nazwy = {i["nazwa"]: i for i in repo_portal.lista_instytucji()}
    assert nazwy["Ministerstwo Cyfryzacji"]["typ"] == "state"
    assert nazwy["Urząd Miasta Krosna"]["regon"] == "000526989"
    warszawa = nazwy["Urząd m.st. Warszawy"]
    assert repo_portal.lista_zbiorow(instytucja_id=warszawa["id"]) == []      # „jeszcze nie dołączył”
    assert w["zbior_id"] in {z["id"] for z in repo_portal.lista_zbiorow(instytucja_id=nazwy["Ministerstwo Cyfryzacji"]["id"])}

    statusy = {n: partnerzy.status_partnera(i["id"])["status"] for n, i in nazwy.items()}
    assert statusy[seed_portal.PARTNER["nazwa"]] == "AKTYWNY"
    assert statusy[seed_portal.SPOLDZIELNIA["nazwa"]] == "WYGASŁY"
    assert statusy["Urząd Miasta Legionowo"] == "BRAK"      # dane gminy: tylko 3 z 8 pól „ponad minimum” (<50%)
    assert statusy["Urząd m.st. Warszawy"] == "BRAK"


def test_seed_nie_ukrywa_brakow_gmin():
    rekordy, *_ = seed_portal.konwertuj_gmine("3624")              # Krosno – bez uzupełnień demo
    assert all(r["status_urzadzenia"] == "nieznany" for r in rekordy)   # słownik dopuszcza „nieznany”
    assert all(r["czy_zamkniete"] is None and r["dostepnosc_typ"] is None for r in rekordy)
    legionowo, *_ = seed_portal.konwertuj_gmine("40593")
    assert all(r["instrukcja_dostepu"] == seed_portal.ZNACZNIK_DEMO for r in legionowo)
    przemysl, *_ = seed_portal.konwertuj_gmine("4581")
    assert all(r["instrukcja_dostepu"] == seed_portal.ZNACZNIK_DEMO for r in przemysl)
    assert all(r["wojewodztwo"] == "podkarpackie" for r in przemysl)


def test_seed_firmy_fikcyjne_z_poprawnymi_identyfikatorami():
    from app.validation import czy_poprawny_identyfikator
    for d in (seed_portal.PARTNER, seed_portal.SPOLDZIELNIA, seed_portal.SKLEP):
        assert "fikcyjn" in d["nazwa"]
        assert all(czy_poprawny_identyfikator(x) for x in (d["nip"], d["regon"]) if x)
    for r in seed_portal._rekordy_partnera("2026-11-22T00:00:00Z"):
        assert r["godziny_dostepnosci"] and "PIN" not in (r.get("instrukcja_dostepu") or "")


def test_start_aplikacji_zasiewa_portal_raz():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        konta = c.get("/api/admin/konta").json()
        assert len(konta) == 10 and konta[-1]["id"] == "admin"
    with TestClient(app) as c:                                       # drugi start – bez duplikatów
        assert len(c.get("/api/admin/konta").json()) == 10
