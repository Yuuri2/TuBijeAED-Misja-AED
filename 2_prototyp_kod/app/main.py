"""Punkt wejścia FastAPI – klikalny prototyp „dane.gov.pl + Wykaz zbiorczy AED” (#TuBijeAED). Właściciel: Backend.

Każdy router żyje w osobnym pliku należącym do jednego agenta (patrz docs/PROTOTYP.md).
Uruchomienie (z katalogu 2_prototyp_kod):  ../.venv/bin/uvicorn app.main:app --port 8080 --reload
Przy starcie: tabele portalu + seed danych demo (gdy baza portalu pusta; env SEED_PORTAL=0 wyłącza).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config, db
from .portal import baza, seed_portal
from .routers import api_14, asystent, mapa, partnerzy, portal_admin

logger = logging.getLogger("tubijeaed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    baza.init_portal()
    if config.seed_wlaczony():
        try:
            seed_portal.zasiej_jesli_pusty()
        except Exception:  # noqa: BLE001 – brak danych demo nie może blokować startu portalu
            logger.exception("Seed danych demo portalu nie powiódł się")
    yield


app = FastAPI(title="#TuBijeAED – prototyp dane.gov.pl z Wykazem zbiorczym AED", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(StarletteHTTPException)
async def _http_blad(request, exc: StarletteHTTPException):
    """Błędy HTTP z polskim komunikatem w `error` (i `detail` – zgodnie z konwencją FastAPI)."""
    tresc = {"detail": exc.detail}
    if isinstance(exc.detail, str):
        tresc["error"] = exc.detail
    elif isinstance(exc.detail, dict) and "error" in exc.detail:
        tresc = exc.detail
    return JSONResponse(status_code=exc.status_code, content=tresc, headers=getattr(exc, "headers", None))


portal_admin.obsluz_bledy(app)     # BladPortalu / BladWykazu -> {"error": ...} z kodem 4xx

# Backend: panel portalu, Partner  |  API: publiczne API 1.4, mapa, asystent dostawcy
app.include_router(portal_admin.router, prefix="/api/admin")
app.include_router(partnerzy.router, prefix="/api/partnerzy")
app.include_router(api_14.router, prefix="/api/1.4")
app.include_router(mapa.router, prefix="/api/mapa")
app.include_router(asystent.router, prefix="/api/asystent")

# Statyczny frontend – musi być zamontowany jako ostatni (łapie wszystkie pozostałe ścieżki)
app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
