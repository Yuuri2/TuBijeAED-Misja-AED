"""Punkt wejścia FastAPI – klikalny prototyp „dane.gov.pl + Wykaz zbiorczy AED” (#TuBijeAED). Właściciel: Backend.

Każdy router żyje w osobnym pliku należącym do jednego agenta (patrz docs/PROTOTYP.md).
Uruchomienie (z katalogu 2_prototyp_kod):  ../.venv/bin/uvicorn app.main:app --port 8080 --reload
Przy starcie: tabele portalu + seed danych demo (gdy baza portalu pusta; env SEED_PORTAL=0 wyłącza).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
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


_TYPY_BLEDOW = {
    "int_parsing": "musi być liczbą całkowitą", "int_type": "musi być liczbą całkowitą",
    "int_from_float": "musi być liczbą całkowitą", "float_parsing": "musi być liczbą",
    "float_type": "musi być liczbą", "missing": "jest wymagany", "greater_than_equal": "jest za mały",
    "greater_than": "jest za mały", "less_than_equal": "jest za duży", "less_than": "jest za duży",
    "bool_parsing": "musi być wartością logiczną (true/false)", "string_too_short": "jest za krótki",
    "string_too_long": "jest za długi", "json_invalid": "zawiera niepoprawny JSON",
    "enum": "ma niedozwoloną wartość", "literal_error": "ma niedozwoloną wartość",
    "string_pattern_mismatch": "ma niepoprawny format", "value_error": "ma niepoprawną wartość",
}


@app.exception_handler(RequestValidationError)
async def _blad_parametrow(request, exc: RequestValidationError):
    """422 z polskim opisem (zamiast surowych komunikatów pydantic po angielsku)."""
    szczegoly = []
    for e in exc.errors():
        lok = [str(x) for x in e.get("loc", ()) if x not in ("query", "path", "body", "header", "cookie", "form")]
        nazwa = ".".join(lok) or "żądanie"
        opis = _TYPY_BLEDOW.get(e.get("type", ""), "ma niepoprawną wartość")
        if e.get("type") in ("greater_than_equal", "greater_than", "less_than_equal", "less_than"):
            gr = (e.get("ctx") or {}).get("ge", (e.get("ctx") or {}).get("gt", (e.get("ctx") or {}).get("le", (e.get("ctx") or {}).get("lt"))))
            if gr is not None:
                opis += f" (granica: {gr})"
        szczegoly.append({"parametr": nazwa, "komunikat": f"Parametr „{nazwa}” {opis}."})
    glowny = szczegoly[0]["komunikat"] if szczegoly else "Nieprawidłowe parametry żądania."
    return JSONResponse(status_code=422, content={"error": glowny, "szczegoly": szczegoly})


portal_admin.obsluz_bledy(app)     # BladPortalu / BladWykazu -> {"error": ...} z kodem 4xx

# Backend: panel portalu, Partner  |  API: publiczne API 1.4, mapa, asystent dostawcy
app.include_router(portal_admin.router, prefix="/api/admin")
app.include_router(partnerzy.router, prefix="/api/partnerzy")
app.include_router(api_14.router, prefix="/api/1.4")
app.include_router(mapa.router, prefix="/api/mapa")
app.include_router(asystent.router, prefix="/api/asystent")

# Statyczny frontend – musi być zamontowany jako ostatni (łapie wszystkie pozostałe ścieżki)
app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
