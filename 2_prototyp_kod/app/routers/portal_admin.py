"""Panel dostawcy i administratora portalu (prefiks /api/admin). Właściciel: Backend. Kontrakt: docs/PROTOTYP.md.

Odpowiednik w mcod: panel administracyjny Django (mcod/datasets/admin.py, mcod/resources/admin.py + ResourceForm),
import XML harvestera (mcod/harvester) i ręczne uruchomienie zadania create_main_dga_resource_task.

Uwierzytelnianie DEMO (bez haseł): nagłówek `X-Demo-Konto: <id instytucji>` albo `X-Demo-Konto: admin`.
Uprawnienia: instytucja widzi i zmienia tylko własne zbiory/zasoby; `admin` – wszystko, w tym przebudowa
i historia wykazu. Zbiór wykazu zbiorczego (zrodlo='system') nie jest edytowalny ręcznie.
Błędy: {"error": "<komunikat po polsku>", ...}.
"""
from __future__ import annotations

from typing import Union

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import config
from ..portal import repo_portal, wykazy
from ..portal.wykazy import BladPortalu

router = APIRouter(tags=["panel portalu (demo)"])

ADMIN = "admin"
Konto = Union[int, str]


def _blad(status: int, komunikat: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": komunikat, **extra})


class BladHttp(Exception):
    def __init__(self, status: int, komunikat: str, **extra):
        self.status, self.komunikat, self.extra = status, komunikat, extra


def obsluz_bledy(app) -> None:
    """Rejestruje obsługę BladPortalu/BladHttp w aplikacji (wywoływane z app.main)."""
    @app.exception_handler(BladPortalu)
    async def _bp(request, exc: BladPortalu):
        return _blad(exc.kod_http, exc.komunikat, **exc.szczegoly)

    @app.exception_handler(BladHttp)
    async def _bh(request, exc: BladHttp):
        return _blad(exc.status, exc.komunikat, **exc.extra)


def konto(x_demo_konto: str | None = Header(None, alias="X-Demo-Konto")) -> Konto:
    """Zalogowane konto demo: 'admin' albo id instytucji (int)."""
    if not x_demo_konto or not x_demo_konto.strip():
        raise BladHttp(401, "Brak zalogowanego konta. Wybierz konto w „Zaloguj jako…” (nagłówek X-Demo-Konto).")
    v = x_demo_konto.strip()
    if v.lower() == ADMIN:
        return ADMIN
    try:
        inst_id = int(v)
    except ValueError:
        raise BladHttp(401, f"Nieznane konto demo „{v}”.")
    if repo_portal.pobierz_instytucje(inst_id) is None:
        raise BladHttp(401, f"Nie ma instytucji o id {inst_id} – wybierz konto z listy /api/admin/konta.")
    return inst_id


def tylko_admin(k: Konto = Depends(konto)) -> Konto:
    if k != ADMIN:
        raise BladHttp(403, "Ta operacja jest dostępna tylko dla administratora portalu (MC).")
    return k


def _sprawdz_zbior(k: Konto, zbior_id: int) -> dict:
    zb = repo_portal.pobierz_zbior(zbior_id)
    if zb is None:
        raise BladHttp(404, f"Nie znaleziono zbioru o id {zbior_id}.")
    if k != ADMIN and zb["instytucja_id"] != k:
        raise BladHttp(403, "Możesz zmieniać tylko zbiory własnej instytucji.")
    if zb["zrodlo"] == "system":
        raise BladHttp(403, "Zbiór wykazu zbiorczego jest tworzony automatycznie przez portal – nie można go edytować.")
    return zb


def _sprawdz_zasob(k: Konto, zasob_id: int) -> dict:
    z = repo_portal.pobierz_zasob(zasob_id)
    if z is None:
        raise BladHttp(404, f"Nie znaleziono zasobu o id {zasob_id}.")
    if z.get("wykaz_zbiorczy"):
        raise BladHttp(403, "Zasoby wykazu zbiorczego są zarządzane automatycznie – nie można ich zmieniać ręcznie.")
    if k != ADMIN and z.get("instytucja_id") != k:
        raise BladHttp(403, "Możesz zmieniać tylko zasoby własnej instytucji.")
    return z


def _publiczny(zasob: dict) -> dict:
    """Zasób do odpowiedzi API – bez ścieżki pliku na serwerze."""
    return {k: v for k, v in zasob.items() if k != "plik_sciezka"}


async def _wczytaj(plik: UploadFile | None, limit: int) -> tuple[bytes | None, str | None]:
    if plik is None or not (plik.filename or ""):
        return None, None
    dane = await plik.read(limit + 1)
    if len(dane) > limit:
        raise BladHttp(413, f"Plik jest za duży. Maksymalny rozmiar to {limit // (1024 * 1024)} MB.")
    return dane, plik.filename


def _bool(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "tak", "on", "yes")


# ----------------------------------------------------------------------------- konta

@router.get("/konta", summary="Konta demo do „Zaloguj jako…”")
def konta():
    wynik = [{"id": i["id"], "nazwa": i["nazwa"], "typ": i["typ"]} for i in repo_portal.lista_instytucji()]
    wynik.append({"id": ADMIN, "nazwa": "Administrator portalu (MC)", "typ": "admin"})
    return wynik


@router.get("/ja", summary="Zalogowane konto demo")
def ja(k: Konto = Depends(konto)):
    if k == ADMIN:
        return {"id": ADMIN, "nazwa": "Administrator portalu (MC)", "typ": "admin"}
    return repo_portal.pobierz_instytucje(k)


# ----------------------------------------------------------------------------- zbiory

@router.get("/moje-zbiory", summary="Zbiory zalogowanej instytucji z zasobami (admin: wszystkie)")
def moje_zbiory(k: Konto = Depends(konto)):
    zbiory = repo_portal.lista_zbiorow(instytucja_id=None if k == ADMIN else k, tylko_opublikowane=False)
    for zb in zbiory:
        zb["zasoby"] = [_publiczny(repo_portal.pobierz_zasob(z["id"])) for z in repo_portal.lista_zasobow(zb["id"])]
        zb["edytowalny"] = zb["zrodlo"] != "system"
    return zbiory


class NowyZbior(BaseModel):
    tytul: str = Field(..., min_length=1, max_length=300)
    opis: str = ""
    licencja: str = "CC BY 4.0"
    czestotliwosc: str = "irregular"
    slowa_kluczowe: list[str] = []
    status: str = "opublikowany"
    instytucja_id: int | None = None          # tylko admin


@router.post("/zbiory", status_code=201, summary="Nowy zbiór danych")
def nowy_zbior(dane: NowyZbior, k: Konto = Depends(konto)):
    inst = k
    if k == ADMIN:
        if dane.instytucja_id is None:
            raise BladHttp(422, "Administrator musi wskazać instytucję (pole instytucja_id).")
        inst = dane.instytucja_id
    return repo_portal.utworz_zbior(inst, tytul=dane.tytul, opis=dane.opis, licencja=dane.licencja,
                                    czestotliwosc=dane.czestotliwosc, slowa_kluczowe=dane.slowa_kluczowe,
                                    status=dane.status, zrodlo="panel")


# ----------------------------------------------------------------------------- zasoby

@router.post("/zbiory/{zbior_id}/zasoby", status_code=201, summary="Dodaj zasób (plik xlsx/csv lub URL)")
async def dodaj_zasob(
    zbior_id: int,
    plik: UploadFile | None = File(None),
    url: str | None = Form(None),
    tytul: str = Form(...),
    opis: str = Form(""),
    wykaz_typ: str = Form(""),
    status: str = Form("opublikowany"),
    data_danych: str | None = Form(None),
    potwierdz_zastapienie: str | None = Form(None),
    k: Konto = Depends(konto),
):
    _sprawdz_zbior(k, zbior_id)
    dane, nazwa = await _wczytaj(plik, config.MAX_FILE_BYTES)
    if dane is None and not (url or "").strip():
        raise BladHttp(422, "Dodaj plik zasobu albo podaj adres URL.", pole="plik")
    wynik = repo_portal.dodaj_lub_zaktualizuj_zasob(
        zbior_id, tytul=tytul, opis=opis, plik=dane, nazwa_pliku=nazwa, url=(url or "").strip() or None,
        wykaz_typ=wykaz_typ or None, status=status, data_danych=(data_danych or "").strip() or None,
        potwierdz_zastapienie=_bool(potwierdz_zastapienie))
    wynik["zasob"] = _publiczny(wynik["zasob"])
    return wynik


@router.get("/zasoby/{zasob_id}", summary="Zasób z raportem walidacji")
def pobierz_zasob(zasob_id: int, k: Konto = Depends(konto)):
    return _publiczny(_sprawdz_zasob(k, zasob_id))


@router.put("/zasoby/{zasob_id}", summary="Aktualizuj zasób (podmiana pliku / flaga wykazu / status)")
async def aktualizuj_zasob(
    zasob_id: int,
    plik: UploadFile | None = File(None),
    url: str | None = Form(None),
    tytul: str | None = Form(None),
    opis: str | None = Form(None),
    wykaz_typ: str | None = Form(None),
    status: str | None = Form(None),
    data_danych: str | None = Form(None),
    potwierdz_zastapienie: str | None = Form(None),
    k: Konto = Depends(konto),
):
    """Pola pominięte zostają bez zmian; `wykaz_typ=""` zdejmuje oznaczenie wykazu."""
    z = _sprawdz_zasob(k, zasob_id)
    dane, nazwa = await _wczytaj(plik, config.MAX_FILE_BYTES)
    wynik = repo_portal.dodaj_lub_zaktualizuj_zasob(
        z["zbior_id"], zasob_id=zasob_id,
        tytul=tytul if tytul is not None else z["tytul"],
        opis=opis if opis is not None else z["opis"],
        plik=dane, nazwa_pliku=nazwa,
        url=(url.strip() or None) if url is not None else z.get("url"),
        wykaz_typ=wykaz_typ if wykaz_typ is not None else z.get("wykaz_typ"),
        status=status or z["status"],
        data_danych=(data_danych or "").strip() or None,
        potwierdz_zastapienie=_bool(potwierdz_zastapienie))
    wynik["zasob"] = _publiczny(wynik["zasob"])
    return wynik


@router.delete("/zasoby/{zasob_id}", summary="Usuń zasób (przebudowa wykazu, jeśli dotyczył wykazu)")
def usun_zasob(zasob_id: int, k: Konto = Depends(konto)):
    _sprawdz_zasob(k, zasob_id)
    return repo_portal.usun_zasob(zasob_id)


# ----------------------------------------------------------------------------- harvester

@router.post("/harvester/xml", summary="Import XML harvestera (schemat 1.13/1.14)")
async def harvester_xml(plik: UploadFile = File(...), instytucja_id: int | None = Form(None),
                        k: Konto = Depends(konto)):
    inst = k
    if k == ADMIN:
        if instytucja_id is None:
            raise BladHttp(422, "Administrator musi wskazać instytucję, do której importuje (pole instytucja_id).")
        if repo_portal.pobierz_instytucje(instytucja_id) is None:
            raise BladHttp(404, f"Nie ma instytucji o id {instytucja_id}.")
        inst = instytucja_id
    tresc, nazwa = await _wczytaj(plik, config.MAX_XML_BYTES)
    if not tresc:
        raise BladHttp(422, "Plik XML jest pusty.", pole="plik")
    if not (nazwa or "").lower().endswith(".xml"):
        raise BladHttp(400, "Harvester przyjmuje plik .xml (schemat importu otwartych danych 1.13 lub 1.14).", pole="plik")
    from .. import harvester
    try:
        return harvester.importuj_xml(tresc, inst)
    except NotImplementedError:
        raise BladHttp(501, "Import XML harvestera nie jest jeszcze dostępny w tej wersji prototypu.")


# ----------------------------------------------------------------------------- wykazy (admin)

@router.post("/wykazy/{typ}/przebuduj", summary="Przebuduj wykaz zbiorczy (admin)")
def przebuduj(typ: str, k: Konto = Depends(tylko_admin)):
    info = wykazy.utworz_wykaz_zbiorczy(wykazy.konfiguracja(typ).typ)
    if info["status"] != "OK":
        return _blad(500, info.get("komunikat") or "Scalenie wykazu nie powiodło się.", wykaz=info)
    return info


@router.get("/wykazy/{typ}/historia", summary="Historia uruchomień scalania (admin)")
def historia(typ: str, limit: int = 50, k: Konto = Depends(tylko_admin)):
    return wykazy.historia(wykazy.konfiguracja(typ).typ, limit=max(1, min(limit, 500)))
