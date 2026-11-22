"""Testy repo.py (SQLite): zapis, pełna synchronizacja, kompletność, uid, filtry."""
import pytest

from app import repo, schema


def rek(id_aed="A1", lat=52.0, lon=21.0, **zm):
    r = {
        "id_aed": id_aed, "nazwa_dysponenta": "Urząd X", "identyfikator_dysponenta": "5252248481", "typ_dysponenta": "JST",
        "kontakt_dysponenta": "x@y.pl", "wojewodztwo": "mazowieckie", "powiat": "P", "gmina": "G", "miejscowosc": "M",
        "nr_budynku": "1", "kod_pocztowy": "00-001", "szerokosc_geo": lat, "dlugosc_geo": lon,
        "lokalizacja_szczegolowa": "Hol", "wewnatrz_budynku": "TAK", "dostepnosc_typ": "24_7", "czy_zamkniete": "NIE",
        "status_urzadzenia": "sprawne", "data_aktualizacji": "2026-11-21T12:00:00Z",
    }
    r.update(zm)
    return r


@pytest.fixture
def zrodlo_dysp():
    z = repo.Zrodlo(id="dysponent:5252248481", typ="DYSPONENT", nazwa="Zgłoszenie X", url=None, licencja="CC BY 4.0")
    repo.zarejestruj_zrodlo(z)
    return z


def test_zapis_i_odczyt(zrodlo_dysp):
    w = repo.zapisz_rekordy([rek("A1"), rek("A2", lat=52.5)], zrodlo_dysp.id)
    assert (w.dodano, w.zaktualizowano) == (2, 0)
    lista = repo.lista_rekordow()
    assert [r["id_aed"] for r in lista] == ["A1", "A2"]
    r = lista[0]
    assert r["uid"] == "DYSPONENT:5252248481:A1"
    assert r["zrodlo_typ"] == "DYSPONENT" and r["licencja"] == "CC BY 4.0"
    assert r["status_weryfikacji"] == "ZGLOSZONY_PRZEZ_DYSPONENTA" and r["zrodlo_nazwa"] == "Zgłoszenie X"
    assert r["duplikat_z"] is None and r["data_pobrania"] and r["zrodlo_id"] == zrodlo_dysp.id
    assert set(schema.nazwy_wszystkich()) <= set(r)


def test_brakujace_wartosci_to_none_nie_nan(zrodlo_dysp):
    repo.zapisz_rekordy([rek(ulica="nan", producent_model="", kondygnacja=float("nan"))], zrodlo_dysp.id)
    r = repo.lista_rekordow()[0]
    assert r["ulica"] is None and r["producent_model"] is None and r["kondygnacja"] is None
    assert "nan" not in [v for v in r.values() if isinstance(v, str)]


def test_aktualizacja_i_pelna_synchronizacja(zrodlo_dysp):
    repo.zapisz_rekordy([rek("A1"), rek("A2", lat=52.5), rek("A3", lat=53.0)], zrodlo_dysp.id)
    w = repo.zapisz_rekordy([rek("A1", lokalizacja_szczegolowa="Nowy opis"), rek("A4", lat=53.5)], zrodlo_dysp.id, zastap=True)
    assert (w.dodano, w.zaktualizowano) == (1, 1)
    assert sorted(r["id_aed"] for r in repo.lista_rekordow()) == ["A1", "A4"]
    assert repo.pobierz_rekord("DYSPONENT:5252248481:A1")["lokalizacja_szczegolowa"] == "Nowy opis"


def test_bez_zastap_zachowuje_stare(zrodlo_dysp):
    repo.zapisz_rekordy([rek("A1"), rek("A2", lat=52.5)], zrodlo_dysp.id)
    repo.zapisz_rekordy([rek("A3", lat=53.0)], zrodlo_dysp.id, zastap=False)
    assert len(repo.lista_rekordow()) == 3


def test_zastap_dotyczy_tylko_swojego_zrodla(zrodlo_dysp):
    inne = repo.Zrodlo(id="dysponent:5250000251", typ="DYSPONENT", nazwa="Inne", url=None, licencja="CC BY 4.0")
    repo.zarejestruj_zrodlo(inne)
    repo.zapisz_rekordy([rek("A1", identyfikator_dysponenta="5250000251")], inne.id)
    repo.zapisz_rekordy([rek("A1", lat=53)], zrodlo_dysp.id)
    repo.zapisz_rekordy([rek("A9", lat=54)], zrodlo_dysp.id, zastap=True)
    assert sorted(r["uid"] for r in repo.lista_rekordow()) == ["DYSPONENT:5250000251:A1", "DYSPONENT:5252248481:A9"]


def test_kompletnosc_wyliczenie():
    pelny = {p["name"]: "x" for p in schema.pola()}
    pelny["dostepnosc_typ"] = "godziny_otwarcia"
    pelny["czy_zamkniete"] = "TAK_KLUCZ"
    assert schema.kompletnosc(pelny) == 1.0
    # wymagane TAK + ZALECANE (bez WARUNKOWO, bo 24_7 i NIE)
    r = {"dostepnosc_typ": "24_7", "czy_zamkniete": "NIE"}
    tak_zal = [p for p in schema.pola() if p["x-wymagane"] in ("TAK", "ZALECANE")]
    assert schema.kompletnosc(r) == pytest.approx(2 / len(tak_zal), abs=1e-3)
    # warunkowe liczą się dopiero gdy warunek aktywny
    r2 = {"dostepnosc_typ": "ograniczona", "czy_zamkniete": "TAK_KOD"}
    assert schema.kompletnosc(r2) == pytest.approx(2 / (len(tak_zal) + 2), abs=1e-3)
    assert schema.kompletnosc({}) == 0.0


def test_kompletnosc_zapisana_w_rekordzie(zrodlo_dysp):
    repo.zapisz_rekordy([rek("A1"), rek("A2", lat=52.5, teryt_gmina="1465011", simc="0918123", data_przegladu="2026-01-01")], zrodlo_dysp.id)
    a1, a2 = repo.lista_rekordow()
    assert 0 < a1["kompletnosc"] < a2["kompletnosc"] <= 1.0
    assert a2["kompletnosc"] == 1.0


def test_pomija_rekordy_bez_wspolrzednych_lub_id(zrodlo_dysp):
    w = repo.zapisz_rekordy([rek("A1"), rek("A2", lat=None), rek(id_aed=None, lat=51)], zrodlo_dysp.id)
    assert w.dodano == 1 and len(w.ostrzezenia) == 2


def test_filtry(zrodlo_dysp):
    osm = repo.Zrodlo(id="osm:Test", typ="OSM", nazwa="OSM Test", url=None, licencja="ODbL 1.0")
    repo.zarejestruj_zrodlo(osm)
    repo.zapisz_rekordy([rek("A1"), rek("A2", lat=50.0, lon=19.0, wojewodztwo="małopolskie")], zrodlo_dysp.id)
    repo.zapisz_rekordy([{"id_aed": "node/1", "szerokosc_geo": 51.0, "dlugosc_geo": 17.0}], osm.id)
    assert len(repo.lista_rekordow()) == 3
    assert len(repo.lista_rekordow(tylko_otwarte_licencje=True)) == 2
    assert [r["id_aed"] for r in repo.lista_rekordow(zrodlo_typ="OSM")] == ["node/1"]
    osm_rek = repo.lista_rekordow(zrodlo_typ="OSM")[0]
    assert osm_rek["licencja"] == "ODbL 1.0" and osm_rek["status_weryfikacji"] == "DO_WERYFIKACJI"
    assert osm_rek["uid"] == "OSM:Test:node/1"
    assert [r["id_aed"] for r in repo.lista_rekordow(wojewodztwo="małopolskie")] == ["A2"]
    assert len(repo.lista_rekordow(status_weryfikacji="DO_WERYFIKACJI")) == 1
    assert [r["id_aed"] for r in repo.lista_rekordow(bbox=(18.0, 49.0, 20.0, 51.0))] == ["A2"]
    assert len(repo.lista_rekordow(identyfikator_dysponenta="5252248481")) == 2


def test_lista_zrodel_i_statystyki(zrodlo_dysp):
    repo.zapisz_rekordy([rek("A1"), rek("A2", lat=52.5)], zrodlo_dysp.id)
    zr = repo.lista_zrodel()
    assert zr == [{"id": zrodlo_dysp.id, "typ": "DYSPONENT", "nazwa": "Zgłoszenie X", "url": None, "licencja": "CC BY 4.0",
                   "liczba_rekordow": 2, "ostatnia_synchronizacja": zr[0]["ostatnia_synchronizacja"]}]
    assert zr[0]["ostatnia_synchronizacja"].endswith("Z")
    s = repo.statystyki()
    assert s["razem"] == 2 and s["wg_zrodlo_typ"] == {"DYSPONENT": 2}
    assert s["wg_status_weryfikacji"] == {"ZGLOSZONY_PRZEZ_DYSPONENTA": 2} and s["wg_wojewodztwo"] == {"mazowieckie": 2}


def test_czy_baza_pusta(zrodlo_dysp):
    assert repo.czy_baza_pusta()
    repo.zapisz_rekordy([rek()], zrodlo_dysp.id)
    assert not repo.czy_baza_pusta()


def test_ten_sam_uid_w_innym_zrodle_nie_nadpisuje(zrodlo_dysp):
    inne = repo.Zrodlo(id="dysponent:inne", typ="DYSPONENT", nazwa="Inne", url=None, licencja="CC BY 4.0")
    repo.zarejestruj_zrodlo(inne)
    repo.zapisz_rekordy([rek("A1")], zrodlo_dysp.id)
    w = repo.zapisz_rekordy([rek("A1", lat=40.0)], inne.id)       # ten sam identyfikator dysponenta i id_aed
    assert w.dodano == 1 and len(repo.lista_rekordow()) == 2


def test_dedup_po_zapisie_i_ponowne_przeliczenie():
    gov = repo.Zrodlo(id="dane-gov-pl:1", typ="DANE_GOV_PL", nazwa="Gov", url=None, licencja="CC BY 4.0")
    osm = repo.Zrodlo(id="osm:W", typ="OSM", nazwa="OSM", url=None, licencja="ODbL 1.0")
    repo.zarejestruj_zrodlo(gov)
    repo.zarejestruj_zrodlo(osm)
    w = repo.zapisz_rekordy([{"id_aed": "node/1", "szerokosc_geo": 52.0, "dlugosc_geo": 21.0}], osm.id)
    assert w.oznaczono_duplikaty == 0
    w = repo.zapisz_rekordy([rek("G1", lat=52.00005, lon=21.0)], gov.id)     # ~5,5 m od punktu OSM
    assert w.oznaczono_duplikaty == 1
    osm_rek = repo.lista_rekordow(zrodlo_typ="OSM", uwzglednij_duplikaty=True)[0]
    assert osm_rek["duplikat_z"] == repo.lista_rekordow(zrodlo_typ="DANE_GOV_PL")[0]["uid"]
    assert repo.lista_rekordow(zrodlo_typ="OSM") == []
    # usunięcie rekordu nadrzędnego zdejmuje flagę duplikatu
    repo.zapisz_rekordy([], gov.id, zastap=True)
    assert repo.lista_rekordow(zrodlo_typ="OSM")[0]["duplikat_z"] is None
