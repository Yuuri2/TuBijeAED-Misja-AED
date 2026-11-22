"""Router export – właściciel: API. Kontrakt: docs/API.md (sekcja „Eksporty”).

Eksporty dla dane.gov.pl biorą wyłącznie `repo.lista_rekordow(tylko_otwarte_licencje=True)`
(bez OSM/ODbL i bez duplikatów). Dane OSM – osobno, w /export/osm-odbl.geojson.
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter
from fastapi.responses import Response

from .. import config, repo
from ..exports import eksport_csv, eksport_geojson, harvester_xml

router = APIRouter(tags=["eksporty"])


def _base_url() -> str:
    # czytane przy każdym żądaniu – zmiana env nie wymaga restartu w testach
    return os.environ.get("BASE_URL", config.BASE_URL).rstrip("/")


def _plik(tresc: bytes, typ: str, nazwa: str, pobierz: bool = True) -> Response:
    tryb = "attachment" if pobierz else "inline"
    return Response(content=tresc, media_type=typ, headers={"Content-Disposition": f'{tryb}; filename="{nazwa}"'})


def _json(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@router.get("/export/csv", summary="Rejestr AED – CSV (UTF-8) dla dane.gov.pl")
def export_csv():
    rekordy = repo.lista_rekordow(tylko_otwarte_licencje=True)
    return _plik(eksport_csv.do_csv(rekordy).encode("utf-8"), "text/csv; charset=utf-8", "rejestr_aed_tubijeaed.csv")


@router.get("/export/geojson", summary="Rejestr AED – GeoJSON (RFC 7946) dla dane.gov.pl")
def export_geojson():
    rekordy = repo.lista_rekordow(tylko_otwarte_licencje=True)
    return _plik(_json(eksport_geojson.do_geojson(rekordy)), "application/geo+json",
                 "rejestr_aed_tubijeaed.geojson", pobierz=False)


@router.get("/export/harvester.xml", summary="Metadane do importu XML dane.gov.pl (schemat 1.13)")
def export_harvester_xml():
    rekordy = repo.lista_rekordow(tylko_otwarte_licencje=True)
    xml = harvester_xml.zbuduj_harvester_xml(rekordy, _base_url())
    return _plik(xml, "application/xml", "harvester_aed_1_13.xml")


@router.get("/export/harvester-xml", include_in_schema=False)
def export_harvester_xml_alias():
    """Alias kompatybilności dla starego static/index.html (do usunięcia w Sprincie 2)."""
    return export_harvester_xml()


@router.get("/export/osm-odbl.geojson", summary="AED z OpenStreetMap (ODbL 1.0) – poza harvesterem")
def export_osm_odbl():
    rekordy = repo.lista_rekordow(zrodlo_typ="OSM")
    return _plik(_json(eksport_geojson.do_geojson_osm(rekordy)), "application/geo+json",
                 "aed_osm_odbl.geojson", pobierz=False)
