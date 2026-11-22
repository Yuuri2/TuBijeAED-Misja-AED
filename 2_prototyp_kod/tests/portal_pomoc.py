"""Pomocnicze funkcje testów prototypu portalu (Backend). Bez sieci, baza tymczasowa z conftest.py."""
from __future__ import annotations

import csv
import io

from app import schema
from app.portal import repo_portal

from tests.test_validation import dobry


def plik_csv(wiersze: list[dict], kolumny: list[str] | None = None) -> bytes:
    kolumny = kolumny or schema.nazwy_pol()
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(kolumny)
    for r in wiersze:
        w.writerow(["" if r.get(k) is None else r.get(k) for k in kolumny])
    return buf.getvalue().encode("utf-8")


def aed(id_aed: str, lat: float = 52.2, lon: float = 21.0, **kw) -> dict:
    return dobry(id_aed=id_aed, szerokosc_geo=lat, dlugosc_geo=lon, **kw)


def portal_testowy() -> dict:
    """MC + 2 gminy + firma + deweloper; każda instytucja (poza MC) ma zbiór."""
    mc = repo_portal.utworz_instytucje(nazwa="Ministerstwo Cyfryzacji", typ="state")
    a = repo_portal.utworz_instytucje(nazwa="Urząd Miasta Alfa", typ="local", regon="000526989")
    b = repo_portal.utworz_instytucje(nazwa="Bank Beta S.A.", typ="private", regon="123456785")
    c = repo_portal.utworz_instytucje(nazwa="Ćma Gmina", typ="local", regon="000524832")
    dev = repo_portal.utworz_instytucje(nazwa="Deweloper Aplikacji", typ="developer")
    zb = {i["id"]: repo_portal.utworz_zbior(i["id"], tytul=f"AED – {i['nazwa']}", opis="")["id"] for i in (a, b, c, dev)}
    return {"mc": mc, "a": a, "b": b, "c": c, "dev": dev, "zbior": zb}


def dodaj_aed(zbior_id: int, wiersze: list[dict], **kw) -> dict:
    return repo_portal.dodaj_lub_zaktualizuj_zasob(zbior_id, tytul=kw.pop("tytul", "AED"), plik=plik_csv(wiersze),
                                                   nazwa_pliku=kw.pop("nazwa_pliku", "aed.csv"),
                                                   wykaz_typ=kw.pop("wykaz_typ", "AED"), **kw)
