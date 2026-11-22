"""Mapa #TuBijeAED – właściciel: API. Kontrakt: docs/PROTOTYP.md. Rejestracja (Backend): prefiks `/api/mapa`.

Źródło prawdy: WYŁĄCZNIE aktualny Wykaz defibrylatorów AED – wykaz zbiorczy (app.portal.wykazy).
Odpowiednik w mcod: brak (portal udostępnia plik wykazu; mapa jest odbiorcą danych z API).

Zasady bezpieczeństwa informacji (ratownictwo):
  * `wycofane` – nie pokazujemy (urządzenie nie istnieje / nie działa);
  * status null / „nieznany” – POKAZUJEMY, z oznaczeniem `status_nieznany: true` (lepiej wiedzieć, że gdzieś
    może być AED, niż go ukryć; frontend opisuje to tekstem, nie tylko kolorem);
  * `dostepny_teraz` – true/false/null (null = brak godzin albo składnia spoza podzbioru – „nie wiadomo”).
Warstwa OSM: dane społecznościowe ODbL 1.0, status DO_WERYFIKACJI, NIGDY nie trafiają do wykazu – trzymane
w tabeli `rekordy` z Sprintu 1 (zrodlo_typ='OSM'), osobno od portalu.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Query

from .. import repo
from ..exports import eksport_geojson
from ..portal import partnerzy
from ..sources import godziny, osm
from ..sources.wspolne import odleglosc_m
from .api_14 import aktualny_wykaz_lub_404, parsuj_bbox, rekordy_aed

router = APIRouter(tags=["mapa #TuBijeAED"])

MAKS_LIMIT = 20


def _partnerzy_cache():
    cache: dict = {}

    def czy_partner(instytucja_id) -> bool:
        if instytucja_id not in cache:
            try:
                cache[instytucja_id] = (partnerzy.status_partnera(int(instytucja_id)) or {}).get("status") == "AKTYWNY"
            except (NotImplementedError, ValueError, TypeError, LookupError):
                cache[instytucja_id] = False
        return cache[instytucja_id]
    return czy_partner


def _wzbogac(r: dict, chwila: datetime, czy_partner) -> dict:
    status = r.get("status_urzadzenia")
    return {
        **r,
        "partner": czy_partner(r.get("instytucja_id")),
        "status_nieznany": status in (None, "", "nieznany"),
        "dostepny_teraz": godziny.dostepny_teraz(r.get("godziny_dostepnosci"), r.get("dostepnosc_typ"), status, chwila),
    }


def _widoczny(r: dict) -> bool:
    return r.get("status_urzadzenia") != "wycofane" and r.get("szerokosc_geo") is not None \
        and r.get("dlugosc_geo") is not None


def _wykaz_lub_pusty() -> bool:
    try:
        aktualny_wykaz_lub_404()
        return True
    except HTTPException:
        return False


@router.get("/aed", summary="GeoJSON AED z Wykazu zbiorczego (bez wycofanych; properties.partner)")
def mapa_aed(wojewodztwo: str | None = None, dostawca: int | None = None, bbox: str | None = None):
    if not _wykaz_lub_pusty():
        parsuj_bbox(bbox)
        return {"type": "FeatureCollection", "features": [], "wykaz": None}
    chwila, czy_partner = godziny.teraz(), _partnerzy_cache()
    cechy = []
    for r in rekordy_aed(wojewodztwo, dostawca, bbox):
        if not _widoczny(r):
            continue
        p = _wzbogac(r, chwila, czy_partner)
        cechy.append({
            "type": "Feature",
            "id": f"{r.get('instytucja_id')}:{r.get('id_aed')}",
            "geometry": {"type": "Point", "coordinates": [round(float(r["dlugosc_geo"]), 7),
                                                          round(float(r["szerokosc_geo"]), 7)]},
            "properties": p,
        })
    return {"type": "FeatureCollection", "features": cechy,
            "wykaz": {"typ": "AED", "czas_sprawdzenia_dostepnosci": chwila.isoformat(timespec="minutes")}}


@router.get("/najblizsze", summary="Najbliższe AED z Wykazu zbiorczego (odległość, dostępność teraz)")
def najblizsze(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
               limit: int = Query(3, ge=1, le=MAKS_LIMIT)):
    chwila = godziny.teraz()
    if not _wykaz_lub_pusty():
        return {"items": [], "meta": {"count": 0, "czas": chwila.isoformat(timespec="minutes"),
                                      "strefa": "Europe/Warsaw", "komunikat": "Wykaz AED nie jest jeszcze dostępny."}}
    czy_partner = _partnerzy_cache()
    kandydaci = []
    for r in rekordy_aed():
        if not _widoczny(r):
            continue
        try:
            d = odleglosc_m(lat, lon, float(r["szerokosc_geo"]), float(r["dlugosc_geo"]))
        except (TypeError, ValueError):
            continue
        kandydaci.append((d, r))
    kandydaci.sort(key=lambda x: x[0])
    items = []
    for d, r in kandydaci[:limit]:
        p = _wzbogac(r, chwila, czy_partner)
        p["odleglosc_m"] = round(d)
        p["nawigacja_url"] = (f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route="
                              f"{lat:.6f}%2C{lon:.6f}%3B{float(r['szerokosc_geo']):.6f}%2C{float(r['dlugosc_geo']):.6f}")
        items.append(p)
    return {"items": items, "meta": {"count": len(items), "czas": chwila.isoformat(timespec="minutes"),
                                     "strefa": "Europe/Warsaw"}}


# ---------------------------------------------------------------------------------------------- warstwa OSM

@router.get("/osm", summary="Warstwa OpenStreetMap „do weryfikacji” (ODbL 1.0, poza wykazem)")
def warstwa_osm(bbox: str | None = None):
    b = parsuj_bbox(bbox)
    gj = eksport_geojson.do_geojson_osm(repo.lista_rekordow(zrodlo_typ="OSM", bbox=b))
    for c in gj["features"]:
        c["properties"]["status_weryfikacji"] = "DO_WERYFIKACJI"
        c["properties"]["w_wykazie"] = False
    return gj


@router.post("/osm/pobierz", summary="Pobierz AED z OpenStreetMap dla miasta (warstwa „do weryfikacji”)")
def pobierz_osm(miasto: str = Form(...)):
    try:
        rekordy, ostrzezenia, pobrano = osm.pobierz(miasto)
    except osm.BladNazwy as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except osm.BladOverpass as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    zrodlo = osm.zrodlo_dla(miasto)
    repo.zarejestruj_zrodlo(zrodlo)
    zapis = repo.zapisz_rekordy(rekordy, zrodlo.id, zastap=True)
    return {
        "miasto": miasto.strip(),
        "pobrano": pobrano,
        "zapisano": zapis.dodano + zapis.zaktualizowano,
        "licencja": osm.LICENCJA,
        "atrybucja": osm.ATRYBUCJA,
        "status_weryfikacji": "DO_WERYFIKACJI",
        "w_wykazie": False,
        "komunikat": f"Pobrano {pobrano} punktów z OpenStreetMap ({miasto.strip()}). To dane społecznościowe "
                     "do weryfikacji – nie wchodzą do Wykazu zbiorczego AED.",
        "ostrzezenia": ostrzezenia + zapis.ostrzezenia,
    }
