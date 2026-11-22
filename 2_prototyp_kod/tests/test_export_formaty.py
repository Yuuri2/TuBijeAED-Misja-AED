"""Eksporty CSV / GeoJSON / harvester XML 1.13 – testy na czystych funkcjach + przez API (repo SQLite)."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from lxml import etree

from app import schema
from app.exports import eksport_csv, eksport_geojson, harvester_xml
from app.exports.kolumny import KOLUMNY_ZRODLA, kolumny_eksportu
from app.sources import czytniki, danegov, osm

FIX = Path(__file__).parent / "fixtures"
XSD = FIX / "xml_import_otwarte_dane_1_13.xsd"


def _zbior(nr: str, plik: str, inst: str, fmt: str = "csv") -> list[dict]:
    d = FIX / "danegov"
    wiersze = czytniki.czytaj((d / plik).read_bytes(), fmt)
    zbior = json.loads((d / f"dataset_{nr}.json").read_text(encoding="utf-8"))["data"]
    instytucja = json.loads((d / f"institution_{inst}.json").read_text(encoding="utf-8"))["data"]
    rek, _ = danegov.normalizuj(wiersze, zbior=zbior, instytucja=instytucja, zasob=None,
                                konfig=danegov.MAPOWANIA[nr], data_pobrania="2026-11-22T10:00:00Z")
    return rek


@pytest.fixture(scope="module")
def rekordy_gov() -> list[dict]:
    return (_zbior("3624", "krosno_3624.csv", "229") + _zbior("4955", "marki_4955.csv", "537")
            + _zbior("40593", "legionowo_2625221.csv", "297")
            + _zbior("4581", "przemysl_62093.geojson", "145", "geojson"))


@pytest.fixture(scope="module")
def rekordy_osm() -> list[dict]:
    el = json.loads((FIX / "osm" / "overpass_sosnowiec.json").read_text(encoding="utf-8"))["elements"]
    return osm.normalizuj_elementy(el, "Sosnowiec")[0]


@pytest.fixture(scope="module")
def xsd():
    return etree.XMLSchema(etree.parse(str(XSD)))


# ----------------------------------------------------------------------------- CSV

def test_csv_naglowki_i_brak_odbl(rekordy_gov, rekordy_osm):
    tekst = eksport_csv.do_csv(rekordy_gov + rekordy_osm)
    wiersze = list(csv.reader(io.StringIO(tekst)))
    assert wiersze[0] == schema.nazwy_pol() + KOLUMNY_ZRODLA
    assert wiersze[0][-5:] == ["zrodlo_typ", "zrodlo_nazwa", "zrodlo_url", "licencja", "status_weryfikacji"]
    assert len(wiersze) - 1 == len(rekordy_gov)
    assert "ODbL" not in tekst and "OSM" not in {w[-5] for w in wiersze[1:]}
    assert "nan" not in tekst and "None" not in tekst
    i = wiersze[0].index("szerokosc_geo")
    assert wiersze[1][i] == "49.7188093"


def test_csv_pomija_duplikaty_i_pusty_ma_naglowek(rekordy_gov):
    dup = dict(rekordy_gov[0], duplikat_z="DANE_GOV_PL:x:1")
    assert eksport_csv.do_csv([dup]).strip() == ",".join(kolumny_eksportu())


# ----------------------------------------------------------------------------- GeoJSON

def test_geojson_lon_lat_rfc7946(rekordy_gov, rekordy_osm):
    gj = eksport_geojson.do_geojson(rekordy_gov + rekordy_osm)
    assert gj["type"] == "FeatureCollection"
    bez_wsp = sum(1 for r in rekordy_gov if r["szerokosc_geo"] is None)   # Marki – wiersz 7
    assert bez_wsp == 1 and len(gj["features"]) == len(rekordy_gov) - bez_wsp
    for f in gj["features"]:
        lon, lat = f["geometry"]["coordinates"]
        assert 14.1 <= lon <= 24.2 and 49.0 <= lat <= 54.9
        assert f["properties"]["licencja"] != "ODbL 1.0"
        assert lon == pytest.approx(f["properties"]["dlugosc_geo"]) and lat == pytest.approx(f["properties"]["szerokosc_geo"])
    json.dumps(gj, allow_nan=False)   # poprawny JSON (bez NaN)


def test_geojson_osm_z_atrybucja(rekordy_gov, rekordy_osm):
    gj = eksport_geojson.do_geojson_osm(rekordy_gov + rekordy_osm)
    assert gj["atrybucja"] == "© OpenStreetMap contributors, ODbL 1.0" and gj["licencja"] == "ODbL 1.0"
    assert len(gj["features"]) == 4
    assert all(f["properties"]["status_weryfikacji"] == "DO_WERYFIKACJI" for f in gj["features"])
    assert gj["features"][0]["geometry"]["coordinates"] == [19.12684, 50.27852]


# ----------------------------------------------------------------------------- harvester XML 1.13

def test_kody_teryt_zwijane_do_wojewodztw_powyzej_limitu():
    """XSD 1.13/1.14: regions/terytIdent maxOccurs=20 – przy wielu gminach kody zwijane do województw."""
    wiele = [{"teryt_gmina": f"{w:02d}{g:02d}011"} for w in (2, 4, 6) for g in range(1, 9)]
    assert harvester_xml.kody_teryt(wiele) == ["02", "04", "06"]


def test_stary_eksport_z_domyslnym_xmlns_nie_przechodzi_xsd(xsd):
    """Dokumentuje błąd starego prototypu (domyślny xmlns) – nasz eksport go nie powtarza."""
    zly = etree.fromstring(
        b'<datasets xmlns="urn:otwarte-dane:harvester:1.13"><dataset><extIdent>x</extIdent></dataset></datasets>')
    assert not xsd.validate(zly)
