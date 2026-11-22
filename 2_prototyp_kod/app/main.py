"""Punkt wejścia FastAPI (#TuBijeAED). Właściciel: Backend.

Każdy router żyje w osobnym pliku należącym do jednego agenta (patrz docs/SPRINTY.md).
Uruchomienie (z katalogu 2_prototyp_kod):  ../.venv/bin/uvicorn app.main:app --port 8080 --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config, db, seed
from .routers import aed, dysponent, export, sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    seed.zasiej_jesli_pusta()
    yield


app = FastAPI(title="#TuBijeAED – integrator danych o defibrylatorach AED", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(StarletteHTTPException)
async def _http_blad(request, exc: StarletteHTTPException):
    """Błędy HTTP z polskim komunikatem w `error` (i `detail` – zgodnie z konwencją FastAPI)."""
    tresc = {"detail": exc.detail}
    if isinstance(exc.detail, str):
        tresc["error"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=tresc, headers=getattr(exc, "headers", None))


# Backend: aed, dysponent  |  API: sources, export
for r in (aed, dysponent, sources, export):
    app.include_router(r.router, prefix="/api/v1")

# Statyczny frontend – musi być zamontowany jako ostatni (łapie wszystkie pozostałe ścieżki)
app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
