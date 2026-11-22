"""Router sources – właściciel: API. Kontrakt: docs/API.md (sekcja „Źródła”).

Router tylko orkiestruje: adapter źródła (app/sources/*) zwraca czyste list[dict],
zapis i odczyt wyłącznie przez app.repo.
"""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse

from .. import repo
from ..sources import danegov, osm

router = APIRouter(tags=["źródła"])


@router.get("/zrodla", summary="Lista źródeł danych z liczbą rekordów i datą synchronizacji")
def lista_zrodel():
    return repo.lista_zrodel()


@router.post("/zrodla/dane-gov-pl/synchronizuj", summary="Import zbiorów AED z api.dane.gov.pl")
def synchronizuj_dane_gov_pl():
    wynik = danegov.synchronizuj()
    zbiory, udane, lacznie = [], 0, 0
    for z in wynik.zbiory:
        wpis = {
            "zbior_id": z.zbior_id,
            "zrodlo_id": z.zrodlo.id if z.zrodlo else None,
            "nazwa": z.zrodlo.nazwa if z.zrodlo else None,
            "licencja": z.zrodlo.licencja if z.zrodlo else None,
            "zasob_id": z.zasob_id,
            "format": z.format,
            "pobrano_rekordow": len(z.rekordy),
            "status": "ok",
            "blad": None,
            "ostrzezenia": list(z.ostrzezenia),
        }
        if z.blad or z.zrodlo is None:
            # nie zapisujemy pustej partii – zastap=True skasowałoby poprzednio pobrane dane
            wpis.update(status="blad", blad=z.blad or "nieznany błąd")
        else:
            repo.zarejestruj_zrodlo(z.zrodlo)
            zapis = repo.zapisz_rekordy(z.rekordy, z.zrodlo.id, zastap=True)
            wpis.update(dodano=zapis.dodano, zaktualizowano=zapis.zaktualizowano,
                        oznaczono_duplikaty=zapis.oznaczono_duplikaty)
            wpis["ostrzezenia"] += zapis.ostrzezenia
            udane += 1
            lacznie += zapis.dodano + zapis.zaktualizowano
        zbiory.append(wpis)
    tresc = {
        "message": f"Zsynchronizowano {udane} z {len(zbiory)} zbiorów AED z dane.gov.pl ({lacznie} rekordów).",
        "zsynchronizowano_zbiorow": udane,
        "zapisano_rekordow": lacznie,
        "zbiory": zbiory,
        "ostrzezenia": wynik.ostrzezenia,
    }
    if udane == 0:
        tresc["error"] = "Nie udało się pobrać żadnego zbioru z dane.gov.pl."
        return JSONResponse(status_code=502, content=tresc)
    return tresc


def _pobierz_osm(miasto: str) -> dict:
    try:
        rekordy, ostrzezenia, pobrano = osm.pobierz(miasto)
    except osm.BladNazwy as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except osm.BladOverpass as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    zrodlo = osm.zrodlo_dla(miasto)
    repo.zarejestruj_zrodlo(zrodlo)
    zapis = repo.zapisz_rekordy(rekordy, zrodlo.id, zastap=True)
    return {
        "zrodlo_id": zrodlo.id,
        "miasto": miasto.strip(),
        "pobrano": pobrano,
        "dodano": zapis.dodano,
        "zaktualizowano": zapis.zaktualizowano,
        "oznaczono_duplikaty": zapis.oznaczono_duplikaty,
        "licencja": osm.LICENCJA,
        "status_weryfikacji": "DO_WERYFIKACJI",
        "atrybucja": osm.ATRYBUCJA,
        "ostrzezenia": ostrzezenia + zapis.ostrzezenia,
    }


@router.post("/zrodla/osm/pobierz", summary="AED z OpenStreetMap dla miasta (warstwa „do weryfikacji”)")
def pobierz_osm(miasto: str = Form(...)):
    return _pobierz_osm(miasto)


@router.post("/harvest-osm", include_in_schema=False)
def harvest_osm_alias(city: str = Form("Sosnowiec")):
    """Alias kompatybilności dla starego static/index.html (pola: message, fetched, added, duplicates_skipped)."""
    w = _pobierz_osm(city)
    return {
        **w,
        "message": f"Zakończono pobieranie z OpenStreetMap dla miasta: {w['miasto']} (status: do weryfikacji, ODbL)",
        "fetched": w["pobrano"],
        "added": w["dodano"] + w["zaktualizowano"],
        "duplicates_skipped": w["oznaczono_duplikaty"],
    }
