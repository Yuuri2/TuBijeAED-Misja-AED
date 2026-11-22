"""Program Partner #TuBijeAED (prefiks /api/partnerzy). Właściciel: Backend. Kontrakt: docs/PROTOTYP.md.

Logika: app/portal/partnerzy.py. Odznaka: szablony UI/UX `static/brand/odznaka-*.svg` z datą ważności.
"""
from __future__ import annotations

import os
from html import escape

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from .. import config
from ..portal import partnerzy, repo_portal

router = APIRouter(tags=["Partner #TuBijeAED"])


def _base_url() -> str:
    return os.environ.get("BASE_URL", config.BASE_URL).rstrip("/")


def _instytucja(instytucja_id: int) -> dict:
    inst = repo_portal.pobierz_instytucje(instytucja_id)
    if inst is None:
        raise HTTPException(404, f"Nie znaleziono instytucji o id {instytucja_id}.")
    return inst


def _alt(inst: dict, s: dict) -> str:
    data = s.get("wazny_do") or ""
    if s["status"] == "WYGASŁY":
        return f"Odznaka Partnera #TuBijeAED instytucji {inst['nazwa']} wygasła {data} – dane wymagają ponownej weryfikacji"
    return f"Partner #TuBijeAED – dane o defibrylatorach zweryfikowane w dane.gov.pl, ważne do {data}"


@router.get("", summary="Lista Partnerów #TuBijeAED (aktywnych i z wygasłą odznaką)")
@router.get("/", include_in_schema=False)
def lista():
    return partnerzy.lista_partnerow()


@router.get("/{instytucja_id}", summary="Status Partnera instytucji z kryteriami")
def status(instytucja_id: int):
    inst = _instytucja(instytucja_id)
    s = partnerzy.status_partnera(instytucja_id)
    base = _base_url()
    wynik = {"instytucja": {k: inst[k] for k in ("id", "nazwa", "typ", "regon")}, **s,
             "link": f"{base}/partner.html?id={instytucja_id}"}
    if s["status"] != "BRAK":
        odznaka = f"{base}/api/partnerzy/{instytucja_id}/odznaka.svg?wariant=jasna&rozmiar=pelna"
        wynik["odznaka_url"] = odznaka
        wynik["kod_osadzenia"] = (f'<a href="{escape(wynik["link"])}"><img src="{escape(odznaka)}" width="200" height="60" '
                                  f'alt="{escape(_alt(inst, s))}"></a>')
    return wynik


@router.get("/{instytucja_id}/odznaka.svg", summary="Odznaka Partnera (SVG) z datą ważności")
def odznaka(instytucja_id: int,
            wariant: str = Query("jasna", pattern="^(jasna|ciemna)$"),
            rozmiar: str = Query("pelna", pattern="^(pelna|mala)$")):
    _instytucja(instytucja_id)
    s = partnerzy.status_partnera(instytucja_id)
    if s["status"] == "BRAK":
        raise HTTPException(404, "Ta instytucja nie jest Partnerem #TuBijeAED – odznaka niedostępna.")
    svg = partnerzy.odznaka_svg(s, wariant=wariant, rozmiar=rozmiar)
    return Response(content=svg.encode("utf-8"), media_type="image/svg+xml; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=3600",
                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
                             "X-Content-Type-Options": "nosniff"})
