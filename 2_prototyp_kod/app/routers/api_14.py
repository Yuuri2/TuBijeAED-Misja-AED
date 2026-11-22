"""Publiczne API w stylu api.dane.gov.pl (wersja 1.4, JSON:API) – właściciel: API. Kontrakt: docs/PROTOTYP.md.

Rejestracja (Backend, app/main.py): prefiks `/api/1.4`.

Odpowiedniki w mcod:
  /datasets, /datasets/{id}, /datasets/{id}/resources  -> mcod/datasets/views.py (DatasetSearchApiView, DatasetApiView,
                                                           DatasetResourceSearchApiView)
  /resources/{id}, /resources/{id}/file                -> mcod/resources/views.py (ResourceView, ResourceFileDownloadView)
  /institutions, /institutions/{id}                    -> mcod/organizations/views.py (InstitutionSearchView, InstitutionApiView)
  /aed-aggregated                                      -> mcod/resources/views.py AggregatedDGAInfoView + routes.py
                                                          `/dga-aggregated` (404 gdy brak wykazu lub zasób nieopublikowany)
  /aed-aggregated/rekordy, /aed-aggregated/plik/{fmt}  -> brak w mcod (DGA udostępnia tylko plik zasobu); dodane
                                                          na potrzeby mapy i tabeli wykazu.
Koperta odpowiedzi: {data, links: {self, …}, meta: {count, …}, jsonapi: {version: "1.4"}}; identyfikatory jako
napisy (JSON:API); paginacja `page` / `per_page` (maks. 100) jak w api.dane.gov.pl.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse

from ..portal import partnerzy, repo_portal, wykazy

router = APIRouter(tags=["API 1.4 (dane.gov.pl)"])

PREFIKS = "/api/1.4"
JSONAPI = {"version": "1.4"}
MAKS_PER_PAGE = 100
KATEGORIE = {"HEAL": "Zdrowie", "REGI": "Regiony i miasta", "SOCI": "Ludność i społeczeństwo",
             "GOVE": "Rząd i sektor publiczny"}
TYPY_PLIKOW = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "geojson": "application/geo+json",
}


# ---------------------------------------------------------------------------------------------- pomocnicze

def baza(request: Request) -> str:
    return str(request.base_url).rstrip("/") + PREFIKS


def _nie_znaleziono(co: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Nie znaleziono: {co}.")


def _lista_slow(v) -> list[str]:
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return [s.strip() for s in v.split(",") if s.strip()]
    return list(v or [])


def stronicuj(request: Request, elementy: list, page: int, per_page: int) -> tuple[list, dict, dict]:
    """-> (strona, links, meta) w stylu api.dane.gov.pl."""
    liczba = len(elementy)
    ostatnia = max(1, math.ceil(liczba / per_page))
    strona = elementy[(page - 1) * per_page: page * per_page]
    url = str(request.url).split("?")[0]
    parametry = {k: v for k, v in request.query_params.items() if k not in ("page", "per_page")}

    def link(p: int) -> str:
        return f"{url}?{urlencode({**parametry, 'page': p, 'per_page': per_page})}"

    links = {"self": link(page), "first": link(1), "last": link(ostatnia)}
    if page > 1:
        links["prev"] = link(min(page - 1, ostatnia))
    if page < ostatnia:
        links["next"] = link(page + 1)
    return strona, links, {"count": liczba, "page": page, "per_page": per_page}


def _instytucje() -> dict:
    return {i["id"]: i for i in repo_portal.lista_instytucji()}


def _partner(instytucja_id) -> dict | None:
    try:
        s = partnerzy.status_partnera(int(instytucja_id))
    except (NotImplementedError, ValueError, TypeError, LookupError):
        return None
    return {"status": s.get("status"), "wazny_do": s.get("wazny_do")} if s else None


def _zbior_publiczny(zbior_id: int) -> dict:
    z = repo_portal.pobierz_zbior(zbior_id)
    if not z or z.get("status") != "opublikowany":
        raise _nie_znaleziono(f"zbiór {zbior_id}")
    return z


def _zasob_publiczny(zasob_id: int) -> dict:
    zs = repo_portal.pobierz_zasob(zasob_id)
    if not zs or zs.get("status") != "opublikowany":
        raise _nie_znaleziono(f"zasób {zasob_id}")
    _zbior_publiczny(zs["zbior_id"])
    return zs


# ---------------------------------------------------------------------------------------------- serializacja

def zbior_json(z: dict, instytucje: dict, b: str) -> dict:
    inst = instytucje.get(z.get("instytucja_id")) or {}
    kat = z.get("kategoria") or "HEAL"
    return {
        "id": str(z["id"]),
        "type": "dataset",
        "attributes": {
            "title": z.get("tytul"),
            "notes": z.get("opis"),
            "institution": {"id": str(inst.get("id", z.get("instytucja_id"))), "title": inst.get("nazwa"),
                            "type": inst.get("typ")},
            "categories": [{"code": kat, "title": KATEGORIE.get(kat, kat)}],
            "license": z.get("licencja"),
            "update_frequency": z.get("czestotliwosc"),
            "keywords": _lista_slow(z.get("slowa_kluczowe")),
            "source_type": z.get("zrodlo"),
            "created": z.get("utworzono"),
            "modified": z.get("zmodyfikowano"),
            "resources_count": z.get("liczba_zasobow"),
            "is_aggregated_list": bool(z.get("czy_wykaz_zbiorczy")),
        },
        "relationships": {
            "institution": {"data": {"type": "institution", "id": str(z.get("instytucja_id"))},
                            "links": {"related": f"{b}/institutions/{z.get('instytucja_id')}"}},
            "resources": {"links": {"related": f"{b}/datasets/{z['id']}/resources"},
                          "meta": {"count": z.get("liczba_zasobow")}},
        },
        "links": {"self": f"{b}/datasets/{z['id']}"},
    }


def zasob_json(zs: dict, b: str, szczegoly: bool = False) -> dict:
    ma_plik = bool(zs.get("plik_sciezka") or zs.get("url_pobrania") or zs.get("url"))
    atr = {
        "title": zs.get("tytul"),
        "description": zs.get("opis"),
        "format": zs.get("format"),
        "download_url": f"{b}/resources/{zs['id']}/file" if ma_plik else None,
        "link": zs.get("url"),
        "aggregated_list_type": zs.get("wykaz_typ"),
        "validation_status": zs.get("walidacja_status"),
        "rows": zs.get("liczba_wierszy"),
        "data_date": zs.get("data_danych"),
        "modified": zs.get("zmodyfikowano"),
    }
    if szczegoly:
        raport = zs.get("walidacja_raport")
        if isinstance(raport, str):
            try:
                raport = json.loads(raport)
            except ValueError:
                raport = None
        atr["validation_report"] = raport
    return {
        "id": str(zs["id"]),
        "type": "resource",
        "attributes": atr,
        "relationships": {"dataset": {"data": {"type": "dataset", "id": str(zs.get("zbior_id"))},
                                      "links": {"related": f"{b}/datasets/{zs.get('zbior_id')}"}}},
        "links": {"self": f"{b}/resources/{zs['id']}"},
    }


def instytucja_json(i: dict, b: str, liczba_zbiorow: int | None = None) -> dict:
    return {
        "id": str(i["id"]),
        "type": "institution",
        "attributes": {
            "title": i.get("nazwa"),
            "regon": i.get("regon"),
            "institution_type": i.get("typ"),
            "email": i.get("email"),
            "website": i.get("www"),
            "datasets_count": liczba_zbiorow,
            "partner": _partner(i["id"]),
        },
        "relationships": {"datasets": {"links": {"related": f"{b}/datasets?instytucja={i['id']}"},
                                       "meta": {"count": liczba_zbiorow}}},
        "links": {"self": f"{b}/institutions/{i['id']}"},
    }


# ---------------------------------------------------------------------------------------------- zbiory

@router.get("/datasets", summary="Lista opublikowanych zbiorów (filtr: q, instytucja, wykaz=AED)")
def lista_zbiorow(request: Request, q: str | None = None, instytucja: int | None = None,
                  wykaz: str | None = Query(None, pattern="^AED$"),
                  page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=MAKS_PER_PAGE)):
    zbiory = repo_portal.lista_zbiorow(instytucja_id=instytucja, tylko_wykazy=wykaz == "AED",
                                       q=(q or "").strip() or None)
    strona, links, meta = stronicuj(request, zbiory, page, per_page)
    inst, b = _instytucje(), baza(request)
    return {"data": [zbior_json(z, inst, b) for z in strona], "links": links, "meta": meta, "jsonapi": JSONAPI}


@router.get("/datasets/{zbior_id}", summary="Zbiór z relacją do zasobów")
def zbior(request: Request, zbior_id: int):
    z = _zbior_publiczny(zbior_id)
    b = baza(request)
    dane = zbior_json(z, _instytucje(), b)
    zasoby = [zs for zs in repo_portal.lista_zasobow(zbior_id) if zs.get("status") == "opublikowany"]
    dane["relationships"]["resources"]["data"] = [{"type": "resource", "id": str(zs["id"])} for zs in zasoby]
    dane["relationships"]["resources"]["meta"] = {"count": len(zasoby)}
    return {"data": dane, "links": {"self": f"{b}/datasets/{zbior_id}"}, "meta": {}, "jsonapi": JSONAPI}


@router.get("/datasets/{zbior_id}/resources", summary="Opublikowane zasoby zbioru")
def zasoby_zbioru(request: Request, zbior_id: int, page: int = Query(1, ge=1),
                  per_page: int = Query(20, ge=1, le=MAKS_PER_PAGE)):
    _zbior_publiczny(zbior_id)
    zasoby = [zs for zs in repo_portal.lista_zasobow(zbior_id) if zs.get("status") == "opublikowany"]
    strona, links, meta = stronicuj(request, zasoby, page, per_page)
    b = baza(request)
    return {"data": [zasob_json(zs, b) for zs in strona], "links": links, "meta": meta, "jsonapi": JSONAPI}


# ---------------------------------------------------------------------------------------------- zasoby

@router.get("/resources/{zasob_id}", summary="Metadane zasobu (z raportem walidacji)")
def zasob(request: Request, zasob_id: int):
    zs = _zasob_publiczny(zasob_id)
    b = baza(request)
    return {"data": zasob_json(zs, b, szczegoly=True), "links": {"self": f"{b}/resources/{zasob_id}"}, "meta": {},
            "jsonapi": JSONAPI}


@router.get("/resources/{zasob_id}/file", summary="Pobranie pliku zasobu (lub przekierowanie do źródła)")
def plik_zasobu(zasob_id: int):
    zs = _zasob_publiczny(zasob_id)
    sciezka = zs.get("plik_sciezka")
    if sciezka and Path(sciezka).is_file():
        return FileResponse(sciezka, filename=Path(sciezka).name)
    url = zs.get("url")
    if url and url.startswith(("http://", "https://")):
        return RedirectResponse(url, status_code=302)
    raise _nie_znaleziono(f"plik zasobu {zasob_id}")


# ---------------------------------------------------------------------------------------------- instytucje

def _liczby_zbiorow() -> dict:
    wynik: dict = {}
    for z in repo_portal.lista_zbiorow():
        wynik[z.get("instytucja_id")] = wynik.get(z.get("instytucja_id"), 0) + 1
    return wynik


@router.get("/institutions", summary="Instytucje (dostawcy) ze statusem Partnera #TuBijeAED")
def lista_instytucji(request: Request, page: int = Query(1, ge=1),
                     per_page: int = Query(20, ge=1, le=MAKS_PER_PAGE)):
    inst = repo_portal.lista_instytucji()
    strona, links, meta = stronicuj(request, inst, page, per_page)
    liczby, b = _liczby_zbiorow(), baza(request)
    return {"data": [instytucja_json(i, b, liczby.get(i["id"], 0)) for i in strona], "links": links, "meta": meta,
            "jsonapi": JSONAPI}


@router.get("/institutions/{instytucja_id}", summary="Instytucja ze statusem Partnera #TuBijeAED")
def instytucja(request: Request, instytucja_id: int):
    i = repo_portal.pobierz_instytucje(instytucja_id)
    if not i:
        raise _nie_znaleziono(f"instytucja {instytucja_id}")
    b = baza(request)
    liczba = len(repo_portal.lista_zbiorow(instytucja_id=instytucja_id))
    return {"data": instytucja_json(i, b, liczba), "links": {"self": f"{b}/institutions/{instytucja_id}"},
            "meta": {}, "jsonapi": JSONAPI}


# ---------------------------------------------------------------------------------------------- wykaz zbiorczy AED

def aktualny_wykaz_lub_404() -> dict:
    """Jak AggregatedDGAInfoView._get_data: 404 gdy brak wpisu, brak zasobu wykazu albo zasób nieopublikowany."""
    w = wykazy.aktualny_wykaz("AED")
    if not w or w.get("zasob_id") is None:
        raise _nie_znaleziono("Wykaz defibrylatorów AED – wykaz zbiorczy (jeszcze nie utworzono)")
    zs = repo_portal.pobierz_zasob(w["zasob_id"])
    if not zs or zs.get("status") != "opublikowany":
        raise _nie_znaleziono("Wykaz defibrylatorów AED – wykaz zbiorczy (zasób nieopublikowany)")
    return w


@router.get("/aed-aggregated", summary="Wykaz defibrylatorów AED – wykaz zbiorczy (odpowiednik /dga-aggregated)")
def aed_aggregated(request: Request):
    w = aktualny_wykaz_lub_404()
    b = baza(request)
    pliki = {fmt: f"{b}/aed-aggregated/plik/{fmt}" for fmt in TYPY_PLIKOW if (w.get("pliki") or {}).get(fmt)}
    dane = {
        "zbior_id": w.get("zbior_id"),
        "zasob_id": w.get("zasob_id"),
        "dataset_id": w.get("zbior_id"),          # nazwy pól jak w AggregatedDGAInfoApiResponse (mcod)
        "resource_id": w.get("zasob_id"),
        "utworzono": w.get("utworzono"),
        "liczba_rekordow": w.get("liczba_rekordow"),
        "liczba_dostawcow": w.get("liczba_dostawcow"),
        "pliki": pliki,
        "uwzglednione": w.get("uwzglednione") or [],
        "pominiete": w.get("pominiete") or [],
    }
    return {"data": dane,
            "links": {"self": f"{b}/aed-aggregated", "rekordy": f"{b}/aed-aggregated/rekordy",
                      "dataset": f"{b}/datasets/{w.get('zbior_id')}", "resource": f"{b}/resources/{w.get('zasob_id')}"},
            "meta": {}, "jsonapi": JSONAPI}


def parsuj_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    """'minLon,minLat,maxLon,maxLat' (kolejność jak Leaflet toBBoxString / GeoJSON) -> krotka; 422 przy błędzie."""
    if not bbox:
        return None
    try:
        a = [float(x) for x in bbox.split(",")]
    except ValueError:
        a = []
    if len(a) != 4 or not all(math.isfinite(x) for x in a) or a[0] > a[2] or a[1] > a[3]:
        raise HTTPException(status_code=422, detail="Parametr bbox: oczekiwano „minLon,minLat,maxLon,maxLat”.")
    return a[0], a[1], a[2], a[3]


def w_bbox(r: dict, bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return True
    lat, lon = r.get("szerokosc_geo"), r.get("dlugosc_geo")
    try:
        return bbox[0] <= float(lon) <= bbox[2] and bbox[1] <= float(lat) <= bbox[3]
    except (TypeError, ValueError):
        return False


def rekordy_aed(wojewodztwo: str | None = None, dostawca: int | None = None, bbox: str | None = None) -> list[dict]:
    """Rekordy aktualnego wykazu z filtrami. bbox filtrujemy tutaj (jedna, udokumentowana kolejność współrzędnych)."""
    b = parsuj_bbox(bbox)
    rek = wykazy.rekordy_wykazu("AED", wojewodztwo=wojewodztwo or None, instytucja_id=dostawca)
    return [r for r in rek if w_bbox(r, b)]


@router.get("/aed-aggregated/rekordy", summary="Rekordy wykazu AED jako JSON (filtry: wojewodztwo, dostawca, bbox)")
def aed_aggregated_rekordy(request: Request, wojewodztwo: str | None = None, dostawca: int | None = None,
                           bbox: str | None = None):
    aktualny_wykaz_lub_404()
    items = rekordy_aed(wojewodztwo, dostawca, bbox)
    return {"items": items, "links": {"self": str(request.url)}, "meta": {"count": len(items)}, "jsonapi": JSONAPI}


@router.get("/aed-aggregated/plik/{fmt}", summary="Plik wykazu zbiorczego AED (xlsx, csv, geojson)")
def aed_aggregated_plik(fmt: str):
    if fmt not in TYPY_PLIKOW:
        raise _nie_znaleziono(f"format „{fmt}” (dostępne: xlsx, csv, geojson)")
    w = aktualny_wykaz_lub_404()
    sciezka = (w.get("pliki") or {}).get(fmt)
    if not sciezka or not Path(sciezka).is_file():
        raise _nie_znaleziono(f"plik wykazu w formacie {fmt}")
    return FileResponse(sciezka, media_type=TYPY_PLIKOW[fmt], filename=f"wykaz_aed_zbiorczy.{fmt}")
