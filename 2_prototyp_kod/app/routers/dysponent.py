"""Router dysponent – właściciel: Backend. Kontrakt: docs/API.md (Panel dysponenta).

POST /dysponent/walidacja   – walidacja pliku bez zapisu
POST /dysponent/zgloszenie  – zapis poprawnych wierszy jako ZGLOSZONY_PRZEZ_DYSPONENTA
POST /upload-institution    – alias wsteczny (stare nazwy pól form), do usunięcia w Sprincie 2
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from .. import config, repo, validation

router = APIRouter()

LICENCJA_ZGLOSZENIA = "CC BY 4.0"


def _blad(status: int, komunikat: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": komunikat, "detail": komunikat, **extra})


async def _wczytaj(file: UploadFile) -> bytes:
    # czytamy o 1 bajt więcej niż limit, żeby nie ładować do pamięci dowolnie dużego pliku
    return await file.read(config.MAX_FILE_BYTES + 1)


def _nadpisania(nazwa, identyfikator, typ) -> dict:
    return {
        "nazwa_dysponenta": (nazwa or "").strip() or None,
        "identyfikator_dysponenta": validation.normalizuj_identyfikator(identyfikator) if identyfikator else None,
        "typ_dysponenta": (typ or "").strip() or None,
    }


@router.post("/dysponent/walidacja")
async def walidacja(
    file: UploadFile = File(...),
    nazwa_dysponenta: str | None = Form(None),
    identyfikator_dysponenta: str | None = Form(None),
    typ_dysponenta: str | None = Form(None),
):
    """Waliduje plik i zwraca raport. Nic nie zapisuje.

    Pola dysponenta są opcjonalne (jeśli podane, nadpisują kolumny pliku tak samo jak przy zgłoszeniu).
    """
    zawartosc = await _wczytaj(file)
    try:
        raport = validation.waliduj_plik(zawartosc, file.filename or "", _nadpisania(nazwa_dysponenta, identyfikator_dysponenta, typ_dysponenta))
    except validation.BladPliku as e:
        return _blad(e.status, e.komunikat)
    return raport.jako_dict()


async def _zglos(file: UploadFile, nazwa: str | None, identyfikator: str | None, typ: str | None) -> JSONResponse | dict:
    nadp = _nadpisania(nazwa, identyfikator, typ)
    bledy_formularza = []
    for pole, etykieta in (("nazwa_dysponenta", "Nazwa dysponenta"),
                           ("identyfikator_dysponenta", "NIP lub REGON"),
                           ("typ_dysponenta", "Typ podmiotu")):
        if not nadp[pole]:
            bledy_formularza.append({"pole": pole, "kod": "required", "komunikat": f"Pole „{etykieta}” jest wymagane."})
    if not bledy_formularza:
        bledy_formularza = validation.waliduj_dysponenta(nadp["nazwa_dysponenta"], nadp["identyfikator_dysponenta"], nadp["typ_dysponenta"])
    if bledy_formularza:
        return _blad(422, "Formularz zawiera błędy – popraw dane dysponenta.", bledy_formularza=bledy_formularza)

    zawartosc = await _wczytaj(file)
    try:
        raport = validation.waliduj_plik(zawartosc, file.filename or "", nadp)
    except validation.BladPliku as e:
        return _blad(e.status, e.komunikat)

    ident = nadp["identyfikator_dysponenta"]
    nazwa_dysp = nadp["nazwa_dysponenta"]
    zrodlo_id = f"dysponent:{ident}"
    out = raport.jako_dict()
    out.update(zapisano=0, dodano=0, zaktualizowano=0, oznaczono_duplikaty=0, zrodlo_id=zrodlo_id)

    if raport.rekordy:
        zrodlo = repo.Zrodlo(id=zrodlo_id, typ="DYSPONENT", nazwa=f"Zgłoszenie dysponenta: {nazwa_dysp}",
                             url=None, licencja=LICENCJA_ZGLOSZENIA)
        repo.zarejestruj_zrodlo(zrodlo)
        rekordy = []
        for r in raport.rekordy:
            r = dict(r)
            r.update(zrodlo_typ="DYSPONENT", zrodlo_nazwa=zrodlo.nazwa, zrodlo_url=None, licencja=LICENCJA_ZGLOSZENIA,
                     status_weryfikacji="ZGLOSZONY_PRZEZ_DYSPONENTA", zrodlo_id=zrodlo_id)
            rekordy.append(r)
        # pełna synchronizacja (usunięcie wierszy, których już nie ma w pliku) tylko dla pliku bez błędów –
        # inaczej błędny wiersz skasowałby wcześniej zgłoszone, poprawne dane tego urządzenia
        wynik = repo.zapisz_rekordy(rekordy, zrodlo_id, zastap=raport.bledne_wiersze == 0)
        out.update(zapisano=wynik.dodano + wynik.zaktualizowano, dodano=wynik.dodano, zaktualizowano=wynik.zaktualizowano,
                   oznaczono_duplikaty=wynik.oznaczono_duplikaty)
        for o in wynik.ostrzezenia:
            out["ostrzezenia"].append({"wiersz": None, "pole": None, "kod": "duplikat", "komunikat": o})
    return out


@router.post("/dysponent/zgloszenie")
async def zgloszenie(
    file: UploadFile = File(...),
    nazwa_dysponenta: str | None = Form(None),
    identyfikator_dysponenta: str | None = Form(None),
    typ_dysponenta: str | None = Form(None),
):
    return await _zglos(file, nazwa_dysponenta, identyfikator_dysponenta, typ_dysponenta)


@router.post("/upload-institution")
async def upload_institution(
    file: UploadFile = File(...),
    nazwa_dysponenta: str | None = Form(None),
    nip_regon: str | None = Form(None),
    typ_dysponenta: str | None = Form("JST"),
):
    """Alias wsteczny – stare pola formularza; odpowiedź = raport + klucze `message`, `imported`, `warnings`."""
    wynik = await _zglos(file, nazwa_dysponenta, nip_regon, typ_dysponenta)
    if isinstance(wynik, JSONResponse):
        return wynik
    wynik["imported"] = wynik["zapisano"]
    wynik["message"] = (f"Zapisano {wynik['zapisano']} punktów AED dla podmiotu {nazwa_dysponenta}; "
                        f"wierszy z błędami: {wynik['bledne_wiersze']}.")
    wynik["warnings"] = [f"Wiersz {o['wiersz']}: {o['komunikat']}" if o.get("wiersz") else o["komunikat"]
                         for o in wynik["ostrzezenia"]] + \
                        [f"BŁĄD, wiersz {b['wiersz']}: {b['komunikat']}" for b in wynik["bledy"]]
    return wynik
