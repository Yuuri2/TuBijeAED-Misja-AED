"""Import z dane.gov.pl – testy BEZ sieci (fixture'y: tests/fixtures/danegov/, przycięte prawdziwe odpowiedzi)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import schema
from app.sources import czytniki, danegov, wspolne
from app.sources.danegov import API_URL, BladZrodla

FIX = Path(__file__).parent / "fixtures" / "danegov"

PLIKI = {
    "https://api.dane.gov.pl/media/resources/20240219/Defibrylator_jAmxQcp.csv": "krosno_3624.csv",
    "https://api.dane.gov.pl/media/resources/20241106/1730818801_b50R6UVxPgoVdBbq.geojson": "przemysl_62093.geojson",
    "https://api.dane.gov.pl/media/resources/20250710/Defibrylator_GminaMiastoMarki_1.csv": "marki_4955.csv",
    "https://api.dane.gov.pl/media/resources/20260914/aed.csv": "legionowo_2625221.csv",
    "https://dane.um.warszawa.pl/api/action/get_scb_lokalizacja_defibrylatorow": "warszawa_api_39512.json",
}


class KlientFixture:
    """Udaje danegov.Klient: URL -> plik z tests/fixtures/danegov/."""

    def __init__(self, zepsute: set[str] | None = None):
        self.zepsute = zepsute or set()
        self.wywolania: list[tuple] = []

    def _plik(self, url: str, params: dict | None) -> Path:
        if url in self.zepsute:
            raise BladZrodla(f"przekroczono czas oczekiwania (30 s): {url}")
        if url == f"{API_URL}/search":
            return FIX / ("search_defibrylator.json" if params["q"] == "defibrylator" else "search_aed.json")
        rel = url.removeprefix(API_URL + "/")
        czesci = rel.split("/")
        if czesci[0] == "datasets" and len(czesci) == 2:
            return FIX / f"dataset_{czesci[1]}.json"
        if czesci[0] == "datasets" and czesci[2:] == ["resources"]:
            return FIX / f"resources_{czesci[1]}.json"
        if czesci[0] == "institutions":
            return FIX / f"institution_{czesci[1]}.json"
        if url in PLIKI:
            return FIX / PLIKI[url]
        raise BladZrodla(f"HTTP 404: {url}")

    def json(self, url, params=None):
        self.wywolania.append(("json", url, params))
        return json.loads(self._plik(url, params).read_text(encoding="utf-8"))

    def bajty(self, url, metoda="GET", headers=None):
        self.wywolania.append(("bajty", url, metoda, headers))
        return self._plik(url, None).read_bytes()


@pytest.fixture
def token_warszawy(monkeypatch):
    monkeypatch.setenv("WARSZAWA_API_KEY", "test-token")


def _wynik(token_warszawy=None, **kw):
    return danegov.synchronizuj(KlientFixture(**kw), data_pobrania="2026-11-22T10:00:00Z")


def _po_id(wynik):
    return {z.zbior_id: z for z in wynik.zbiory}


# ----------------------------------------------------------------------------- wyszukiwanie

def test_wyszukiwanie_odfiltrowuje_falszywe_trafienia():
    znalezione = danegov.wyszukaj_zbiory(KlientFixture())
    # ZTM Gdańsk (1803, „defibrylator” tylko w opisie) i „Wyniki badań” (3072, AED w opisie) odrzucone
    assert "1803" not in znalezione and "3072" not in znalezione
    assert {"3624", "4581", "4955", "39512", "40593"} <= set(znalezione)
    assert znalezione["3624"] is None                      # trafienie na poziomie zbioru
    assert znalezione["40593"] == {"2625221"}              # w zbiorze „Zdrowie” tylko zasób z AED


def test_wybor_formatu_geojson_przed_csv():
    zasoby = json.loads((FIX / "resources_4581.json").read_text(encoding="utf-8"))["data"]
    assert danegov.wybierz_zasob(zasoby, None, None)["attributes"]["format"] == "geojson"
    zasoby_marki = json.loads((FIX / "resources_4955.json").read_text(encoding="utf-8"))["data"]
    assert danegov.wybierz_zasob(zasoby_marki, None, None)["attributes"]["format"] == "csv"


# ----------------------------------------------------------------------------- pełna synchronizacja

def test_synchronizacja_wszystkich_zrodel(token_warszawy):
    zb = _po_id(_wynik())
    assert set(zb) == {"3624", "4581", "4955", "39512", "40593"}
    for z in zb.values():
        assert z.blad is None, (z.zbior_id, z.blad)
    assert {k: len(z.rekordy) for k, z in zb.items()} == {"3624": 6, "4581": 3, "4955": 8, "39512": 1, "40593": 7}
    assert zb["4581"].format == "geojson" and zb["3624"].format == "csv"
    assert zb["40593"].zasob_id == "2625221"


def test_rekordy_maja_komplet_pol_i_pola_systemowe(token_warszawy):
    wymagane = set(schema.nazwy_pol()) | set(danegov.POLA_SYSTEMOWE)
    for z in _wynik().zbiory:
        for r in z.rekordy:
            assert set(r) == wymagane
            assert r["zrodlo_typ"] == "DANE_GOV_PL"
            assert r["status_weryfikacji"] == "ZWERYFIKOWANY_DANE_GOV_PL"
            assert r["licencja"] in ("CC0 1.0", "CC BY 4.0")
            assert r["zrodlo_url"].startswith(f"https://dane.gov.pl/pl/dataset/{z.zbior_id},")
            assert r["data_pobrania"] == "2026-11-22T10:00:00Z"
            assert r["typ_dysponenta"] == "JST"
            assert wspolne.regon_poprawny(r["identyfikator_dysponenta"])
            for v in r.values():
                assert v not in ("", "nan", "None")


def test_krosno_rozbior_adresu():
    r = {x["id_aed"]: x for x in _po_id(_wynik())["3624"].rekordy}
    assert r["2"]["ulica"] == "ul. Stanisława Wyspiańskiego" and r["2"]["nr_budynku"] == "20"
    assert r["2"]["kod_pocztowy"] == "38-400" and r["2"]["miejscowosc"] == "Krosno"
    assert r["1"]["nr_budynku"] is None                    # „ul. Jasna, 38-400 Krosno” – brak numeru
    assert r["9"]["nr_budynku"] == "4"                     # „…Wielkiego 4, , 38-400” – pusty segment
    assert r["2"]["lokalizacja_szczegolowa"] == "Kampus Sportowo-dydaktyczny, portiernia"
    assert r["1"]["szerokosc_geo"] == pytest.approx(49.7188093) and r["1"]["dlugosc_geo"] == pytest.approx(21.720344)
    assert r["1"]["licencja"] == "CC0 1.0" and r["1"]["identyfikator_dysponenta"] == "000526989"
    assert r["1"]["teryt_gmina"] == "1861011" and r["1"]["wojewodztwo"] == "podkarpackie"
    assert r["1"]["data_aktualizacji"] == "2024-02-19T17:32:25Z"


def test_przemysl_geojson():
    r = {x["id_aed"]: x for x in _po_id(_wynik())["4581"].rekordy}
    a = r["744"]
    assert (a["szerokosc_geo"], a["dlugosc_geo"]) == (pytest.approx(49.7812096), pytest.approx(22.7750936))
    assert a["lokalizacja_szczegolowa"] == "ADM Centrum"   # bez „Defibrylator (AED 9485) w”
    assert a["zdjecie_url"].startswith("https://przemysl.skycms.com.pl/download/")
    assert a["kontakt_dysponenta"] == "mail@um.przemysl.pl"     # brak kontaktu w wierszu -> instytucja
    assert r["746"]["kontakt_dysponenta"] == "+48166779500"   # telefon z wiersza ma pierwszeństwo


def test_marki_zawiniety_csv_zamienione_wspolrzedne_i_punkt_odstajacy():
    z = _po_id(_wynik())["4955"]
    r = {x["id_aed"]: x for x in z.rekordy}
    assert r["1"]["szerokosc_geo"] == pytest.approx(52.326697) and r["1"]["dlugosc_geo"] == pytest.approx(21.107557)
    assert r["1"]["ulica"] == "al. Piłsudskiego" and r["1"]["nr_budynku"] == "95"
    assert r["1"]["licencja"] == "CC BY 4.0"
    # wiersz 7 ma współrzędne z Krosna – usunięte, nie zgadujemy
    assert r["7"]["szerokosc_geo"] is None and r["7"]["dlugosc_geo"] is None
    tekst = " ".join(z.ostrzezenia)
    assert "zamienione kolumny" in tekst and "AED 7" in tekst and "km od pozostałych" in tekst


def test_legionowo_tylko_zasob_aed_cecha_ulicy_simc():
    z = _po_id(_wynik())["40593"]
    r = z.rekordy[0]
    assert r["lokalizacja_szczegolowa"] == "Urząd Miasta Legionowo"
    assert r["ulica"] == "ul. Piłsudskiego" and r["nr_budynku"] == "41"
    assert r["simc"] == "0920806" and r["teryt_gmina"] == "1408011"
    assert all(x["id_aed"].startswith("LEGIONOWO-") for x in z.rekordy)
    assert len({x["id_aed"] for x in z.rekordy}) == len(z.rekordy)
    assert any(x["ulica"] == "al. 1 Dywizji Zmechanizowanej" for x in z.rekordy)


def test_legionowo_identyfikatory_stabilne_przy_zmianie_kolejnosci():
    a = {x["lokalizacja_szczegolowa"]: x["id_aed"] for x in _po_id(_wynik())["40593"].rekordy}
    wiersze = czytniki.czytaj((FIX / "legionowo_2625221.csv").read_bytes(), "csv")
    zbior = json.loads((FIX / "dataset_40593.json").read_text(encoding="utf-8"))["data"]
    inst = json.loads((FIX / "institution_297.json").read_text(encoding="utf-8"))["data"]
    rek, _ = danegov.normalizuj(list(reversed(wiersze)), zbior=zbior, instytucja=inst, zasob=None,
                                konfig=danegov.MAPOWANIA["40593"])
    assert {x["lokalizacja_szczegolowa"]: x["id_aed"] for x in rek} == a


def test_warszawa_api_z_tokenem(token_warszawy):
    klient = KlientFixture()
    wynik = danegov.synchronizuj(klient)
    r = _po_id(wynik)["39512"].rekordy[0]
    assert r["id_aed"] == "622"
    assert (r["szerokosc_geo"], r["dlugosc_geo"]) == (pytest.approx(52.2086171), pytest.approx(21.0148749))
    assert r["godziny_dostepnosci"] == "Mo 08:00-18:00; Tu-Fr 08:00-16:00"
    assert r["dostepnosc_typ"] == "godziny_otwarcia"
    assert r["wewnatrz_budynku"] == "TAK"
    assert r["producent_model"] == "Medtronic"
    assert r["status_urzadzenia"] == "sprawne"
    assert r["lokalizacja_szczegolowa"] == "Urząd Dzielnicy Mokotów m.st. Warszawy – Przy wejściu na półpiętrze."
    assert r["ulica"] == "Rakowiecka" and r["nr_budynku"] == "25/27" and r["kod_pocztowy"] == "02-517"
    assert r["identyfikator_dysponenta"] == "015259640"
    wywolanie = [w for w in klient.wywolania if w[0] == "bajty" and "warszawa" in w[1]][0]
    assert wywolanie[2] == "POST" and wywolanie[3] == {"Authorization": "test-token"}


def test_warszawa_bez_tokena_czytelny_blad_reszta_dziala(monkeypatch):
    monkeypatch.delenv("WARSZAWA_API_KEY", raising=False)
    zb = _po_id(_wynik())
    assert "WARSZAWA_API_KEY" in zb["39512"].blad and zb["39512"].rekordy == []
    assert zb["39512"].zrodlo is not None
    assert len(zb["3624"].rekordy) == 6


def test_zepsuty_zbior_nie_psuje_synchronizacji(token_warszawy):
    zepsute = {"https://api.dane.gov.pl/media/resources/20241106/1730818801_b50R6UVxPgoVdBbq.geojson",
               f"{API_URL}/datasets/4955"}
    zb = _po_id(_wynik(zepsute=zepsute))
    assert "przekroczono czas" in zb["4581"].blad and "przekroczono czas" in zb["4955"].blad
    assert len(zb["3624"].rekordy) == 6 and len(zb["40593"].rekordy) == 7


def test_awaria_wyszukiwarki_dziala_z_konfiguracji(token_warszawy):
    w = _wynik(zepsute={f"{API_URL}/search"})
    assert {z.zbior_id for z in w.zbiory} == {"3624", "4581", "4955", "39512", "40593"}
    assert any("Wyszukiwanie" in o for o in w.ostrzezenia)


def test_licencja_spoza_cc_odrzuca_zbior():
    zbior = {"id": "1", "attributes": {"license_name": "CC BY-NC 4.0", "slug": "x"}}
    with pytest.raises(BladZrodla, match="licencja"):
        danegov.normalizuj([{"a": 1}], zbior=zbior, instytucja={}, zasob=None, konfig=None)


def test_heurystyka_dla_nieznanego_zbioru_i_puwg1992():
    x, y = wspolne.wgs84_na_puwg1992(52.2297, 21.0122)
    wiersze = [{"Nazwa": "Hala sportowa", "Adres": "ul. Testowa 1, 00-001 Warszawa", "X": str(y), "Y": str(x)},
               {"Nazwa": "Szkoła", "Adres": "ul. Testowa 2, 00-001 Warszawa", "X": "21,0130", "Y": "52,2300"}]
    zbior = {"id": "999", "attributes": {"license_name": "CC BY 4.0", "slug": "aed", "modified": "2026-01-01T00:00:00Z"}}
    inst = {"attributes": {"title": "Gmina Testowa", "regon": "123456785", "institution_type": "local"}}
    rek, ostrz = danegov.normalizuj(wiersze, zbior=zbior, instytucja=inst, zasob=None, konfig=None)
    assert rek[0]["szerokosc_geo"] == pytest.approx(52.2297, abs=1e-6)
    assert rek[0]["dlugosc_geo"] == pytest.approx(21.0122, abs=1e-6)
    assert rek[1]["szerokosc_geo"] == pytest.approx(52.23)
    assert any("heurystycznie" in o for o in ostrz) and any("PUWG 1992" in o for o in ostrz)
    assert rek[0]["id_aed"].startswith("DGP999-")


def test_brak_regon_ostrzezenie_i_none():
    zbior = {"id": "1", "attributes": {"license_name": "CC0 1.0", "slug": "x"}}
    inst = {"attributes": {"title": "Fundacja X", "regon": None, "institution_type": "other"}}
    rek, ostrz = danegov.normalizuj([{"lat": "52.1", "lon": "21.0"}], zbior=zbior, instytucja=inst,
                                    zasob=None, konfig=None)
    assert rek[0]["identyfikator_dysponenta"] is None
    assert any("NIP ani poprawnego REGON" in o for o in ostrz)


# ----------------------------------------------------------------------------- czytniki i pomocnicze

def test_xlsx_marki_csv_w_komorce():
    wiersze = czytniki.czytaj((FIX / "marki_4955.xlsx").read_bytes(), "xlsx")
    assert len(wiersze) == 8
    assert wiersze[0]["Adres"] == "Al.. Piłsudskiego 95, 05-270 Marki"


def test_czytnik_odrzuca_strone_html():
    with pytest.raises(czytniki.BladFormatu, match="HTML"):
        czytniki.czytaj(b"<!DOCTYPE html><html><body>katalog</body></html>", "json")


def test_puwg1992_w_obie_strony():
    for lat, lon in [(52.2297, 21.0122), (49.7188, 21.7203), (54.35, 18.65), (52.0, 19.0)]:
        x, y = wspolne.wgs84_na_puwg1992(lat, lon)
        la, lo = wspolne.puwg1992_na_wgs84(x, y)
        assert la == pytest.approx(lat, abs=1e-7) and lo == pytest.approx(lon, abs=1e-7)
    x, y = wspolne.wgs84_na_puwg1992(52.0, 19.0)
    assert y == pytest.approx(500000.0, abs=1e-6)          # południk osiowy -> FE


@pytest.mark.parametrize("opis,osm", [
    ("Poniedziałek: godz. 8:00-18:00; Wtorek-Piątek: godz. 8:00-16:00", "Mo 08:00-18:00; Tu-Fr 08:00-16:00"),
    ("Pn-Pt 08:00-16:00; Sob 9.00-13.00", "Mo-Fr 08:00-16:00; Sa 09:00-13:00"),
    ("całodobowo", "24/7"),
    ("w godzinach pracy urzędu", None),
])
def test_godziny_pl_na_osm(opis, osm):
    assert wspolne.godziny_pl_na_osm(opis) == osm


def test_regon_nip():
    assert wspolne.regon_poprawny("000526989") and not wspolne.regon_poprawny("000526988")
    assert wspolne.nip_poprawny("5252248481") and not wspolne.nip_poprawny("5252248480")
