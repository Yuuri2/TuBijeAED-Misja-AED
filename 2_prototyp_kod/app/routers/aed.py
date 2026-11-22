"""Router aed – właściciel: Backend. Kontrakt: docs/API.md (Rekordy AED).

Uwaga dla Sprintu 2: `GET /aed/nearest` trzeba zadeklarować PRZED `GET /aed/{uid:path}`.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import repo, schema

router = APIRouter()


def _parsuj_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox.split(","))
    except ValueError:
        raise HTTPException(422, "Parametr bbox musi mieć format minLon,minLat,maxLon,maxLat (cztery liczby oddzielone przecinkami).")
    if min_lon > max_lon or min_lat > max_lat:
        raise HTTPException(422, "Parametr bbox: wartości minimalne muszą być mniejsze od maksymalnych.")
    return min_lon, min_lat, max_lon, max_lat


@router.get("/aed")
def lista_aed(
    wojewodztwo: str | None = None,
    status_weryfikacji: str | None = None,
    zrodlo_typ: str | None = None,
    bbox: str | None = Query(None, description="minLon,minLat,maxLon,maxLat"),
    uwzglednij_duplikaty: bool = False,
):
    items = repo.lista_rekordow(
        zrodlo_typ=zrodlo_typ,
        uwzglednij_duplikaty=uwzglednij_duplikaty,
        wojewodztwo=wojewodztwo,
        status_weryfikacji=status_weryfikacji,
        bbox=_parsuj_bbox(bbox),
    )
    return {"count": len(items), "items": items}


@router.get("/aed/{uid:path}")
def pojedynczy_aed(uid: str):
    rekord = repo.pobierz_rekord(uid)
    if rekord is None:
        raise HTTPException(404, f"Nie znaleziono rekordu AED o identyfikatorze „{uid}”.")
    return rekord


@router.get("/schema")
def pobierz_schemat():
    return schema.get_schema()


@router.get("/statystyki")
def statystyki():
    return repo.statystyki()
