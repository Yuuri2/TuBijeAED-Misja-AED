"""Serwer prototypu do zrzutów ekranu prezentacji.

Uruchamia aplikację bez zmian w kodzie, z jedną różnicą: zegar „dostępny teraz” na mapie jest ustawiony na
stały moment (domyślnie środa 25.11.2026, 12:00 czasu warszawskiego), aby zrzuty nie zależały od pory
generowania (np. w nocy wszystkie AED w godzinach pracy urzędu są „zamknięte o tej porze”).
Korzysta z punktu podmiany `app.sources.godziny.teraz` (ten sam używają testy).

Użycie (z katalogu repo):
    DB_PATH=/tmp/prez.sqlite .venv/bin/python 4_prezentacja/serwer_zrzuty.py [--port 8090] [--czas 2026-11-25T12:00]
"""
import argparse
import os
import sys
from datetime import datetime

TU = os.path.dirname(os.path.abspath(__file__))
KOD = os.path.join(os.path.dirname(TU), "2_prototyp_kod")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--czas", default="2026-11-25T12:00")
    a = ap.parse_args()
    os.chdir(KOD)
    sys.path.insert(0, KOD)
    from app.sources import godziny  # noqa: E402

    stala = datetime.fromisoformat(a.czas).replace(tzinfo=godziny.STREFA)
    godziny.teraz = lambda: stala
    import uvicorn  # noqa: E402
    from app.main import app  # noqa: E402

    uvicorn.run(app, host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
