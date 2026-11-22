"""Asystent dostawcy – właściciel: API. Kontrakt: docs/PROTOTYP.md. Rejestracja (Backend): prefiks `/api/asystent`.

Pomaga dostawcy przygotować zasób do opublikowania NA JEGO WŁASNYM koncie w dane.gov.pl; niczego nie zapisuje
w portalu i niczego nie publikuje w jego imieniu.
  GET  /wzorzec.xlsx | /wzorzec.csv | /schemat.json   pliki wzorca z 1_wzorzec_danych/
  POST /sprawdz      walidacja pliku wzorcem (app/validation.py) – bez zapisu
  POST /konwertuj    plik gminy + profil -> CSV we wzorcu + raport („do uzupełnienia przez dostawcę”)
  POST /pakiet       ZIP: dane_aed.csv + harvester_1_14.xml (aggregatedListType=AED) + INSTRUKCJA.txt
Odpowiednik w mcod: walidacja kolumn jak validate_dga_df_columns (mcod/resources/dga_utils.py) – tu wykonywana
u dostawcy PRZED publikacją, żeby zasób nie został odrzucony przez portal.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response

from .. import config, validation
from ..sources import konwersja

router = APIRouter(tags=["asystent dostawcy"])

KATALOG_WZORCA = config.REPO_DIR / "1_wzorzec_danych"
LICENCJE = ("CC BY 4.0", "CC0 1.0")


async def _czytaj(plik: UploadFile) -> bytes:
    dane = await plik.read(config.MAX_FILE_BYTES + 1)
    if len(dane) > config.MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"Plik jest za duży (maks. {config.MAX_FILE_BYTES // 1024 // 1024} MB).")
    if not dane:
        raise HTTPException(status_code=400, detail="Plik jest pusty.")
    return dane


def _dysponent(nazwa, identyfikator, typ, kontakt) -> dict:
    return {"nazwa_dysponenta": nazwa, "identyfikator_dysponenta": identyfikator, "typ_dysponenta": typ,
            "kontakt_dysponenta": kontakt}


# ---------------------------------------------------------------------------------------------- pliki wzorca

@router.get("/wzorzec.xlsx", summary="Wzorzec danych AED (XLSX z instrukcją i przykładami)")
def wzorzec_xlsx():
    return FileResponse(KATALOG_WZORCA / "wzorzec_danych_aed.xlsx", filename="wzorzec_danych_aed.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/wzorzec.csv", summary="Wzorzec danych AED (CSV UTF-8)")
def wzorzec_csv():
    return FileResponse(KATALOG_WZORCA / "wzorzec_danych_aed.csv", filename="wzorzec_danych_aed.csv",
                        media_type="text/csv; charset=utf-8")


@router.get("/schemat.json", summary="Schemat wzorca (Frictionless Table Schema)")
def schemat_json():
    return FileResponse(KATALOG_WZORCA / "aed_schema.json", media_type="application/json")


# ---------------------------------------------------------------------------------------------- sprawdzanie

@router.post("/sprawdz", summary="Sprawdź plik (xlsx/csv) wzorcem – bez zapisu")
async def sprawdz(plik: UploadFile = File(...)):
    dane = await _czytaj(plik)
    try:
        return validation.waliduj_plik(dane, plik.filename or "").jako_dict()
    except validation.BladPliku as e:
        raise HTTPException(status_code=e.status, detail=e.komunikat) from e


# ---------------------------------------------------------------------------------------------- konwersja

@router.post("/konwertuj", summary="Konwersja pliku gminy do wzorca AED (+ raport braków)")
async def konwertuj(
    plik: UploadFile = File(...),
    profil: str = Form("auto"),
    nazwa_dysponenta: str | None = Form(None),
    identyfikator_dysponenta: str | None = Form(None),
    typ_dysponenta: str | None = Form(None),
    kontakt_dysponenta: str | None = Form(None),
    data_aktualizacji: str | None = Form(None),
    format: str = Query("json", pattern="^(json|csv)$"),
):
    dane = await _czytaj(plik)
    try:
        w = konwersja.konwertuj(dane, plik.filename or "", profil,
                                dysponent=_dysponent(nazwa_dysponenta, identyfikator_dysponenta, typ_dysponenta,
                                                     kontakt_dysponenta),
                                data_aktualizacji=data_aktualizacji)
    except konwersja.BladKonwersji as e:
        raise HTTPException(status_code=e.status, detail=e.komunikat) from e
    nazwa = f"dane_aed_{w.profil_wykryty or w.profil}.csv"
    if format == "csv":
        return Response(w.csv.encode("utf-8"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{nazwa}"'})
    return {"nazwa_pliku": nazwa, "csv": w.csv, "raport": w.raport()}


# ---------------------------------------------------------------------------------------------- pakiet

def _nazwa_zip(nazwa: str) -> str:
    return "pakiet_aed_" + (re.sub(r"[^A-Za-z0-9]+", "_", nazwa).strip("_")[:40] or "dostawca") + ".zip"


@router.post("/pakiet", summary="Pakiet do publikacji: dane_aed.csv + harvester_1_14.xml + INSTRUKCJA.txt (ZIP)")
async def pakiet(
    request: Request,
    plik: UploadFile = File(...),
    nazwa_dostawcy: str = Form(...),
    url_zasobu: str | None = Form(None),
    licencja: str = Form("CC BY 4.0"),
    profil: str | None = Form(None),
    nazwa_dysponenta: str | None = Form(None),
    identyfikator_dysponenta: str | None = Form(None),
    typ_dysponenta: str | None = Form(None),
    kontakt_dysponenta: str | None = Form(None),
    data_aktualizacji: str | None = Form(None),
):
    """Plik we wzorcu (csv/xlsx) – bez `profil`; plik gminy w starym układzie – z `profil` (krosno, …, auto)."""
    dane = await _czytaj(plik)
    nazwa_dostawcy = (nazwa_dostawcy or "").strip()
    if not nazwa_dostawcy or len(nazwa_dostawcy) > 250:
        raise HTTPException(status_code=422, detail="Podaj nazwę dostawcy (instytucji publikującej dane).")
    if licencja not in LICENCJE:
        raise HTTPException(status_code=422, detail=f"Licencja: {' lub '.join(LICENCJE)}.")
    url = (url_zasobu or "").strip()
    if url and (not url.startswith("https://") or len(url) > 2000):
        raise HTTPException(status_code=422, detail="Adres zasobu musi zaczynać się od https:// (wymóg schematu XML).")
    try:
        if profil:
            w = konwersja.konwertuj(dane, plik.filename or "", profil,
                                    dysponent=_dysponent(nazwa_dysponenta, identyfikator_dysponenta, typ_dysponenta,
                                                         kontakt_dysponenta),
                                    data_aktualizacji=data_aktualizacji)
            rekordy, raport = w.rekordy, w.walidacja
        else:
            rekordy, raport = konwersja.wzorzec_z_pliku(dane, plik.filename or "")
        baza = str(request.base_url).rstrip("/")
        zip_, _ = konwersja.zbuduj_pakiet(rekordy=rekordy, raport=raport, nazwa_dostawcy=nazwa_dostawcy,
                                          url_zasobu=url or None, base_url=baza, licencja=licencja)
    except konwersja.BladKonwersji as e:
        raise HTTPException(status_code=e.status, detail=e.komunikat) from e
    return Response(zip_, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{_nazwa_zip(nazwa_dostawcy)}"',
        "X-Poprawne-Wiersze": str(raport.get("poprawne_wiersze", 0)),
        "X-Bledne-Wiersze": str(raport.get("bledne_wiersze", 0)),
        "Access-Control-Expose-Headers": "X-Poprawne-Wiersze, X-Bledne-Wiersze, Content-Disposition",
    })
