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

def test_harvester_xml_przechodzi_oficjalny_xsd(rekordy_gov, rekordy_osm, xsd, tmp_path):
    xml = harvester_xml.zbuduj_harvester_xml(rekordy_gov + rekordy_osm, "http://localhost:8080",
                                             teraz=datetime(2026, 11, 22, 12, tzinfo=timezone.utc))
    doc = etree.fromstring(xml)
    assert xsd.validate(doc), xsd.error_log
    (tmp_path / "harvester.xml").write_bytes(xml)

    assert doc.tag == "{urn:otwarte-dane:harvester:1.13}datasets" and doc.prefix == "ns2"
    ds = doc.find("dataset")                                   # dzieci BEZ przestrzeni nazw
    assert ds is not None and ds.findtext("extIdent") == "tubijeaed-rejestr-aed"
    assert ds.findtext("categories/category") == "HEAL" and ds.findtext("updateFrequency") == "daily"
    assert ds.findtext("conditions/dbOrCopyrightedLicenseChosen") == "CC BY 4.0"
    assert ds.findtext("hasHighValueDataFromEuropeanCommissionList") == "false"
    tagi = [t.text for t in ds.findall("tags/tag")]
    assert {"AED", "defibrylator", "pierwsza pomoc", "ratownictwo", "#TuBijeAED"} <= set(tagi)
    assert all(t.get("lang") == "pl" for t in ds.findall("tags/tag"))
    urle = [r.findtext("url") for r in ds.findall("resources/resource")]
    assert urle == ["https://localhost:8080/api/v1/export/csv", "https://localhost:8080/api/v1/export/geojson"]
    assert all(r.findtext("description/polish") for r in ds.findall("resources/resource"))
    assert [t.text for t in ds.find("resources/resource/regions")] == ["1408011", "1434021", "1861011", "1862011"]
    assert ds.findtext("lastUpdateDate") == "2026-09-21T08:31:31Z"   # najnowsza data_aktualizacji (Legionowo)
    assert b"ODbL" in xml and b"ODbL 1.0</" not in xml          # ODbL tylko w opisie, nie jako licencja


def test_harvester_xml_bez_rekordow_i_z_wieloma_gminami(xsd):
    teraz = datetime(2026, 11, 22, tzinfo=timezone.utc)
    pusty = etree.fromstring(harvester_xml.zbuduj_harvester_xml([], "https://aed.example.pl", teraz=teraz))
    assert xsd.validate(pusty), xsd.error_log
    assert pusty.find("dataset/resources/resource/regions") is None
    wiele = [{"licencja": "CC0 1.0", "zrodlo_typ": "DANE_GOV_PL", "teryt_gmina": f"{w:02d}{g:02d}011"}
             for w in (2, 4, 6) for g in range(1, 9)]
    doc = etree.fromstring(harvester_xml.zbuduj_harvester_xml(wiele, "https://aed.example.pl", teraz=teraz))
    assert xsd.validate(doc), xsd.error_log
    assert [t.text for t in doc.find("dataset/resources/resource/regions")] == ["02", "04", "06"]


def test_stary_eksport_z_domyslnym_xmlns_nie_przechodzi_xsd(xsd):
    """Dokumentuje błąd starego prototypu (domyślny xmlns) – nasz eksport go nie powtarza."""
    zly = etree.fromstring(
        b'<datasets xmlns="urn:otwarte-dane:harvester:1.13"><dataset><extIdent>x</extIdent></dataset></datasets>')
    assert not xsd.validate(zly)


# ----------------------------------------------------------------------------- przez API (repo SQLite)

def test_endpointy_eksportu(client, rekordy_gov, rekordy_osm, xsd, monkeypatch):
    from app import repo

    repo.zarejestruj_zrodlo(repo.Zrodlo("dane-gov-pl:3624", "DANE_GOV_PL", "Krosno", None, "CC0 1.0"))
    repo.zapisz_rekordy([r for r in rekordy_gov if r["zrodlo_url"].split("/")[-1].startswith("3624,")],
                        "dane-gov-pl:3624")
    repo.zarejestruj_zrodlo(osm.zrodlo_dla("Sosnowiec"))
    repo.zapisz_rekordy(rekordy_osm, "osm:Sosnowiec")
    monkeypatch.setenv("BASE_URL", "https://aed.example.pl")

    r = client.get("/api/v1/export/csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    wiersze = list(csv.reader(io.StringIO(r.content.decode("utf-8"))))
    assert wiersze[0] == kolumny_eksportu() and len(wiersze) == 7 and "ODbL" not in r.text

    gj = client.get("/api/v1/export/geojson").json()
    assert len(gj["features"]) == 6

    for sciezka in ("/api/v1/export/harvester.xml", "/api/v1/export/harvester-xml"):
        x = client.get(sciezka)
        assert x.status_code == 200 and x.headers["content-type"].startswith("application/xml")
        doc = etree.fromstring(x.content)
        assert xsd.validate(doc), xsd.error_log
        assert doc.find("dataset/resources/resource/url").text == "https://aed.example.pl/api/v1/export/csv"

    o = client.get("/api/v1/export/osm-odbl.geojson").json()
    assert o["atrybucja"].startswith("© OpenStreetMap") and len(o["features"]) == 4
