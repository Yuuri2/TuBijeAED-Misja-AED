"""Testy deduplikacji (app/dedup.py)."""
import time

from app import dedup


def r(uid, typ, lat, lon, **zm):
    d = {"uid": uid, "zrodlo_typ": typ, "szerokosc_geo": lat, "dlugosc_geo": lon}
    d.update(zm)
    return d


ULICA = {"ulica": "ul. Testowa", "nr_budynku": "5", "miejscowosc": "Kraków"}
M = 1 / 111320     # 1 metr w stopniach szerokości


def test_odleglosc():
    assert dedup.odleglosc_m(52.0, 21.0, 52.0 + 10 * M, 21.0) == __import__("pytest").approx(10, abs=0.2)


def test_priorytet_dane_gov_nad_dysponent_nad_osm():
    rekordy = [
        r("osm", "OSM", 52.0, 21.0),
        r("dysp", "DYSPONENT", 52.0 + 3 * M, 21.0, **ULICA),
        r("gov", "DANE_GOV_PL", 52.0 + 6 * M, 21.0, **ULICA),
    ]
    wynik = dedup.znajdz_duplikaty(rekordy)
    assert wynik == {"dysp": "gov", "osm": "gov"}            # łańcuch rozwiązany do korzenia


def test_osm_vs_dane_gov_wystarczy_bliskosc():
    wynik = dedup.znajdz_duplikaty([r("g", "DANE_GOV_PL", 50.0, 19.0, ulica="Inna", nr_budynku="1"), r("o", "OSM", 50.0 + 10 * M, 19.0)])
    assert wynik == {"o": "g"}


def test_daleko_to_nie_duplikat():
    assert dedup.znajdz_duplikaty([r("g", "DANE_GOV_PL", 50.0, 19.0), r("o", "OSM", 50.0 + 30 * M, 19.0)]) == {}
    assert dedup.znajdz_duplikaty([r("g", "DANE_GOV_PL", 50.0, 19.0), r("o", "OSM", 50.0 + 24 * M, 19.0)]) == {"o": "g"}


def test_blisko_ale_rozne_adresy_i_dysponenci_bez_osm_to_nie_duplikat():
    a = r("g", "DANE_GOV_PL", 50.0, 19.0, ulica="ul. A", nr_budynku="1", nazwa_dysponenta="Szpital Alfa", identyfikator_dysponenta="5252248481")
    b = r("d", "DYSPONENT", 50.0 + 5 * M, 19.0, ulica="ul. B", nr_budynku="9", nazwa_dysponenta="Bank Beta", identyfikator_dysponenta="5250000251")
    assert dedup.znajdz_duplikaty([a, b]) == {}


def test_podobny_adres_lub_dysponent_dla_zrodel_nie_osm():
    a = r("g", "DANE_GOV_PL", 50.0, 19.0, ulica="Al. Testowa", nr_budynku="5", miejscowosc="Kraków")
    b = r("d", "DYSPONENT", 50.0 + 5 * M, 19.0, ulica="ul. Testowa", nr_budynku="5", miejscowosc="Kraków")      # inny prefiks ulicy
    assert dedup.znajdz_duplikaty([a, b]) == {"d": "g"}
    c = r("d2", "DYSPONENT", 50.0 + 5 * M, 19.0, identyfikator_dysponenta="5252248481")
    e = r("g2", "DANE_GOV_PL", 50.0, 19.0, identyfikator_dysponenta="5252248481")
    assert dedup.znajdz_duplikaty([c, e]) == {"d2": "g2"}


def test_dwa_urzadzenia_z_tego_samego_zrodla_w_jednym_budynku_nie_sa_laczone():
    rekordy = [r("g1", "DANE_GOV_PL", 50.0, 19.0, **ULICA), r("g2", "DANE_GOV_PL", 50.0 + 4 * M, 19.0, **ULICA)]
    assert dedup.znajdz_duplikaty(rekordy) == {}
    rekordy = [r("o1", "OSM", 50.0, 19.0), r("o2", "OSM", 50.0 + 4 * M, 19.0)]
    assert dedup.znajdz_duplikaty(rekordy) == {}


def test_dwa_osm_przy_jednym_dane_gov_tylko_jeden_duplikat():
    rekordy = [r("g1", "DANE_GOV_PL", 50.0, 19.0, **ULICA), r("o1", "OSM", 50.0 + 2 * M, 19.0), r("o2", "OSM", 50.0 + 20 * M, 19.0)]
    assert dedup.znajdz_duplikaty(rekordy) == {"o1": "g1"}      # o2 to prawdopodobnie osobne urządzenie


def test_dwa_urzadzenia_w_budynku_parowane_najblizszym():
    rekordy = [
        r("g1", "DANE_GOV_PL", 50.0, 19.0, **ULICA), r("g2", "DANE_GOV_PL", 50.0 + 12 * M, 19.0, **ULICA),
        r("o1", "OSM", 50.0 + 1 * M, 19.0), r("o2", "OSM", 50.0 + 11 * M, 19.0),
    ]
    assert dedup.znajdz_duplikaty(rekordy) == {"o1": "g1", "o2": "g2"}


def test_rozne_kondygnacje_nie_sa_duplikatami():
    a = r("g", "DANE_GOV_PL", 50.0, 19.0, kondygnacja="0", **ULICA)
    b = r("d", "DYSPONENT", 50.0, 19.0, kondygnacja="2", **ULICA)
    assert dedup.znajdz_duplikaty([a, b]) == {}


def test_wydajnosc_kilku_tysiecy_punktow():
    import random
    random.seed(1)
    rekordy = [r(f"u{i}", ("DANE_GOV_PL", "DYSPONENT", "OSM")[i % 3], 49.5 + random.random() * 5, 14.5 + random.random() * 9.5)
               for i in range(6000)]
    t = time.time()
    dedup.znajdz_duplikaty(rekordy)
    assert time.time() - t < 3
