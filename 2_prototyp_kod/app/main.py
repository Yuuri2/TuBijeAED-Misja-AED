"""Punkt wejścia FastAPI (#TuBijeAED). Właściciel: Backend.

Każdy router żyje w osobnym pliku należącym do jednego agenta (patrz docs/SPRINTY.md).
Uruchomienie (z katalogu 2_prototyp_kod):  ../.venv/bin/uvicorn app.main:app --port 8080 --reload
"""
from fastapi import FastAPI

app = FastAPI(title="#TuBijeAED – integrator danych o defibrylatorach AED")

# Backend: app/routers/aed.py, app/routers/dysponent.py
# API:     app/routers/sources.py, app/routers/export.py
# for r in (aed, dysponent, sources, export): app.include_router(r.router, prefix="/api/v1")
# Statyczny frontend: app.mount("/", StaticFiles(directory=STATIC_DIR, html=True))
