"""Eksport GeoJSON (RFC 7946: WGS84, kolejność [długość, szerokość]). Właściciel: API."""
from __future__ import annotations

from .kolumny import do_publikacji, kolumny_eksportu

ATRYBUCJA_OSM = "© OpenStreetMap contributors, ODbL 1.0"


def _cecha(r: dict, kolumny: list[str]) -> dict | None:
    lat, lon = r.get("szerokosc_geo"), r.get("dlugosc_geo")
    if lat is None or lon is None:
        return None                         # bez współrzędnych nie ma czego pokazać na mapie
    return {
        "type": "Feature",
        "id": r.get("uid") or r.get("id_aed"),
        "geometry": {"type": "Point", "coordinates": [round(float(lon), 7), round(float(lat), 7)]},
        "properties": {k: r.get(k) for k in kolumny},
    }


def _kolekcja(rekordy: list[dict], **dodatkowe) -> dict:
    kolumny = kolumny_eksportu()
    cechy = [c for c in (_cecha(r, kolumny) for r in rekordy) if c]
    return {"type": "FeatureCollection", **dodatkowe, "features": cechy}


def do_geojson(rekordy: list[dict]) -> dict:
    """Zbiór dla dane.gov.pl – wyłącznie CC0 / CC BY, bez OSM i duplikatów."""
    return _kolekcja(do_publikacji(rekordy), licencja="CC BY 4.0",
                     atrybucja="#TuBijeAED – integrator danych AED; źródła: dane.gov.pl i dysponenci")


def do_geojson_osm(rekordy: list[dict]) -> dict:
    """Osobny eksport rekordów z OpenStreetMap (ODbL 1.0) – NIE dla harvestera dane.gov.pl."""
    osm = [r for r in rekordy if r.get("zrodlo_typ") == "OSM" and not r.get("duplikat_z")]
    # RFC 7946 §6.1 dopuszcza dodatkowe pola („foreign members”) – tam atrybucja wymagana przez ODbL
    return _kolekcja(osm, licencja="ODbL 1.0", atrybucja=ATRYBUCJA_OSM,
                     atrybucja_url="https://www.openstreetmap.org/copyright",
                     uwaga="Dane społecznościowe DO WERYFIKACJI – nie są danymi urzędowymi.")
