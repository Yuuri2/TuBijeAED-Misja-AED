"""Interfejs danych portalu (KONTRAKT Backend ↔ API, Sprint 2). Implementuje: Backend.

Odpowiednik w mcod: modele Organization / Dataset / Resource (mcod/organizations, mcod/datasets, mcod/resources)
oraz logika formularza zasobu w panelu admina (mcod/resources/forms.py: ResourceForm.clean – walidacja DGA,
`_remove_dga_flag_from_current_dga_resource_if_needed`) i sygnały uruchamiające `create_main_dga_resource_task`.
Agent API (harvester, publiczne API 1.4, mapa) korzysta WYŁĄCZNIE z funkcji poniżej oraz z
`app.portal.wykazy` (aktualny_wykaz, rekordy_wykazu) i `app.portal.partnerzy` (status_partnera).
Szczegóły modelu: docs/PROTOTYP.md. Sygnatury można ROZSZERZAĆ (nowe opcjonalne argumenty), nie zmieniać.

Błędy: `app.portal.wykazy.BladPortalu` (404/403/413/422) i jego podklasa `BladWykazu` (422/409 – reguły wykazu).
"""
from __future__ import annotations

import logging
import re
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse

from .. import config
from . import baza, wykazy
from .wykazy import BladPortalu, BladWykazu

logger = logging.getLogger("tubijeaed.portal")

TYPY_INSTYTUCJI = ("local", "state", "private", "other", "developer")
STATUSY = ("opublikowany", "szkic")
ZNANE_FORMATY = {"xlsx", "xls", "csv", "json", "geojson", "xml", "pdf", "zip", "ods", "txt", "html"}


# ---------------------------------------------------------------- pomocnicze

def _instytucja(w) -> dict:
    d = dict(w)
    return {k: d.get(k) for k in ("id", "nazwa", "regon", "nip", "typ", "email", "www", "utworzono")}


def _zbior(w, liczba_zasobow: int = 0, wykaz_typy: list[str] | None = None, instytucja: dict | None = None) -> dict:
    d = dict(w)
    return {
        "id": d["id"], "instytucja_id": d["instytucja_id"], "tytul": d["tytul"], "opis": d["opis"],
        "kategoria": d["kategoria"], "licencja": d["licencja"], "czestotliwosc": d["czestotliwosc"],
        "slowa_kluczowe": baza.z_json(d["slowa_kluczowe"], []), "status": d["status"], "zrodlo": d["zrodlo"],
        "ext_ident": d.get("ext_ident"), "utworzono": d["utworzono"], "zmodyfikowano": d["zmodyfikowano"],
        "liczba_zasobow": liczba_zasobow,
        "czy_wykaz_zbiorczy": bool(d.get("wykaz_zbiorczy")),
        "wykaz_zbiorczy": d.get("wykaz_zbiorczy"),
        "wykaz_typy": wykaz_typy or [],
        "instytucja": instytucja,
    }


def _zasob(w, *, pelny: bool = False) -> dict:
    d = dict(w)
    wynik = {
        "id": d["id"], "zbior_id": d["zbior_id"], "tytul": d["tytul"], "opis": d["opis"], "format": d["format"],
        "url_pobrania": f"/api/1.4/resources/{d['id']}/file" if d.get("plik_sciezka") else d.get("url"),
        "url": d.get("url"), "nazwa_pliku": d.get("nazwa_pliku"),
        "wykaz_typ": d.get("wykaz_typ"), "wykaz_zbiorczy": d.get("wykaz_zbiorczy"), "status": d["status"],
        "walidacja_status": d["walidacja_status"], "liczba_wierszy": d.get("liczba_wierszy"),
        "data_danych": d.get("data_danych"), "ext_ident": d.get("ext_ident"),
        "utworzono": d["utworzono"], "zmodyfikowano": d["zmodyfikowano"],
    }
    if pelny:
        p = baza.sciezka_absolutna(d.get("plik_sciezka"))
        wynik["plik_sciezka"] = str(p) if p else None
        wynik["walidacja_raport"] = baza.z_json(d.get("walidacja_raport"))
        if "instytucja_id" in d:
            wynik["instytucja_id"] = d["instytucja_id"]
    return wynik


def _bezpieczna_nazwa(nazwa: str | None, domyslna: str = "plik") -> str:
    nazwa = Path(nazwa or "").name
    rdzen, ext = Path(nazwa).stem, Path(nazwa).suffix.lower()
    rdzen = re.sub(r"[^A-Za-z0-9._-]+", "_", rdzen).strip("._")[:80] or domyslna
    ext = ext if re.fullmatch(r"\.[a-z0-9]{1,8}", ext or "") else ""
    return rdzen + ext


def _format(nazwa_pliku: str | None, url: str | None) -> str | None:
    for zrodlo in (nazwa_pliku, urlparse(url).path if url else None):
        ext = wykazy.rozszerzenie(zrodlo)
        if ext:
            return ext if ext in ZNANE_FORMATY else ext[:8]
    return "www" if url else None


def _pobierz_url(url: str) -> tuple[bytes, str]:
    """Pobranie pliku zasobu podanego linkiem (wzór: request_remote_dga). Tylko http(s), limit rozmiaru."""
    import httpx

    if urlparse(url).scheme not in ("http", "https"):
        raise BladPortalu(422, "Adres URL zasobu musi zaczynać się od http:// lub https://.", {"pole": "url"})
    try:
        with httpx.stream("GET", url, timeout=10.0, follow_redirects=True) as r:
            r.raise_for_status()
            dane = b""
            for kawalek in r.iter_bytes():
                dane += kawalek
                if len(dane) > config.MAX_FILE_BYTES:
                    raise BladPortalu(413, f"Plik pod adresem URL jest większy niż {config.MAX_FILE_BYTES // (1024 * 1024)} MB.")
    except httpx.HTTPError as e:
        raise BladPortalu(422, f"Nie udało się pobrać pliku z adresu URL ({e.__class__.__name__}).", {"pole": "url"}) from e
    return dane, Path(urlparse(url).path).name or "zasob"


# ---------------------------------------------------------------- instytucje
def lista_instytucji() -> list[dict]:
    """[{id, nazwa, regon, typ, email, www}]"""
    with baza.transakcja() as con:
        w = con.execute("SELECT * FROM instytucje").fetchall()
    return sorted((_instytucja(x) for x in w), key=lambda i: wykazy.klucz_sortowania_pl(i["nazwa"]))


def pobierz_instytucje(instytucja_id: int) -> dict | None:
    with baza.transakcja() as con:
        w = con.execute("SELECT * FROM instytucje WHERE id = ?", (instytucja_id,)).fetchone()
    return _instytucja(w) if w else None


def utworz_instytucje(*, nazwa: str, typ: str, regon: str | None = None, nip: str | None = None,
                      email: str | None = None, www: str | None = None) -> dict:
    """Dodaje instytucję (w prototypie: tylko seed; w mcod – panel administratora portalu)."""
    if typ not in TYPY_INSTYTUCJI:
        raise BladPortalu(422, f"Nieznany typ instytucji „{typ}”. Dozwolone: {', '.join(TYPY_INSTYTUCJI)}.")
    with baza.transakcja() as con:
        cur = con.execute("INSERT INTO instytucje (nazwa, regon, nip, typ, email, www, utworzono) VALUES (?,?,?,?,?,?,?)",
                          (nazwa, regon, nip, typ, email, www, baza.teraz_iso()))
        nowy = cur.lastrowid
    return pobierz_instytucje(nowy)


def czy_portal_pusty() -> bool:
    with baza.transakcja() as con:
        return con.execute("SELECT COUNT(*) FROM instytucje").fetchone()[0] == 0


# ---------------------------------------------------------------- zbiory
def utworz_zbior(instytucja_id: int, *, tytul: str, opis: str, licencja: str = "CC BY 4.0",
                 czestotliwosc: str = "irregular", slowa_kluczowe: list[str] | None = None,
                 status: str = "opublikowany", zrodlo: str = "panel", ext_ident: str | None = None,
                 kategoria: str = "HEAL") -> dict:
    """Tworzy zbiór (dla harvestera: upsert po (instytucja_id, ext_ident))."""
    if pobierz_instytucje(instytucja_id) is None:
        raise BladPortalu(404, f"Nie znaleziono instytucji o id {instytucja_id}.")
    if not (tytul or "").strip():
        raise BladPortalu(422, "Tytuł zbioru jest wymagany.", {"pole": "tytul"})
    if status not in STATUSY:
        raise BladPortalu(422, f"Nieprawidłowy status zbioru „{status}” (dozwolone: {', '.join(STATUSY)}).", {"pole": "status"})
    if zrodlo not in ("panel", "harvester", "system"):
        raise BladPortalu(422, f"Nieprawidłowe źródło zbioru „{zrodlo}”.")
    teraz = baza.teraz_iso()
    slowa = baza.do_json([s for s in (slowa_kluczowe or []) if str(s).strip()])
    with baza.transakcja() as con:
        istniejacy = None
        if ext_ident:
            istniejacy = con.execute("SELECT id FROM zbiory WHERE instytucja_id = ? AND ext_ident = ?",
                                     (instytucja_id, ext_ident)).fetchone()
        if istniejacy:
            con.execute("UPDATE zbiory SET tytul=?, opis=?, licencja=?, czestotliwosc=?, slowa_kluczowe=?, status=?, "
                        "zrodlo=?, kategoria=?, zmodyfikowano=? WHERE id=?",
                        (tytul.strip(), opis or "", licencja, czestotliwosc, slowa, status, zrodlo, kategoria, teraz,
                         istniejacy["id"]))
            zid = istniejacy["id"]
        else:
            cur = con.execute(
                "INSERT INTO zbiory (instytucja_id, tytul, opis, kategoria, licencja, czestotliwosc, slowa_kluczowe, "
                "status, zrodlo, ext_ident, utworzono, zmodyfikowano) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (instytucja_id, tytul.strip(), opis or "", kategoria, licencja, czestotliwosc, slowa, status, zrodlo,
                 ext_ident, teraz, teraz))
            zid = cur.lastrowid
    return pobierz_zbior(zid)


def _statystyki_zbiorow(con, ids: list[int], tylko_opublikowane: bool) -> tuple[dict, dict]:
    if not ids:
        return {}, {}
    znaki = ",".join("?" * len(ids))
    war = " AND status = 'opublikowany'" if tylko_opublikowane else ""
    liczby = {r[0]: r[1] for r in con.execute(
        f"SELECT zbior_id, COUNT(*) FROM zasoby WHERE zbior_id IN ({znaki}){war} GROUP BY zbior_id", ids)}
    typy: dict[int, list[str]] = {}
    for r in con.execute(f"SELECT DISTINCT zbior_id, wykaz_typ FROM zasoby WHERE zbior_id IN ({znaki}) "
                         f"AND wykaz_typ IS NOT NULL{war}", ids):
        typy.setdefault(r[0], []).append(r[1])
    return liczby, typy


def lista_zbiorow(*, instytucja_id: int | None = None, tylko_wykazy: bool = False, q: str | None = None,
                  tylko_opublikowane: bool = True, wykaz_typ: str | None = None) -> list[dict]:
    """[{id, instytucja_id, tytul, opis, kategoria, licencja, czestotliwosc, slowa_kluczowe, status, zrodlo,
         utworzono, zmodyfikowano, liczba_zasobow, czy_wykaz_zbiorczy}]  (+ wykaz_zbiorczy, wykaz_typy, instytucja)

    `tylko_wykazy` – tylko zbiory wykazów zbiorczych (czy_wykaz_zbiorczy);
    `wykaz_typ` – zbiory związane z wykazem danego typu: zbiór wykazu zbiorczego ORAZ zbiory z zasobami
    źródłowymi tego wykazu (np. 'AED').
    """
    sql = "SELECT zb.*, i.nazwa AS i_nazwa, i.typ AS i_typ FROM zbiory zb JOIN instytucje i ON i.id = zb.instytucja_id WHERE 1=1"
    args: list = []
    if instytucja_id is not None:
        sql += " AND zb.instytucja_id = ?"
        args.append(int(instytucja_id))
    if tylko_opublikowane:
        sql += " AND zb.status = 'opublikowany'"
    if q:
        sql += " AND (LOWER(zb.tytul) LIKE ? OR LOWER(zb.opis) LIKE ?)"
        args += [f"%{q.strip().lower()}%"] * 2
    with baza.transakcja() as con:
        wiersze = con.execute(sql + " ORDER BY zb.zmodyfikowano DESC, zb.id DESC", args).fetchall()
        liczby, typy = _statystyki_zbiorow(con, [w["id"] for w in wiersze], tylko_opublikowane)
    wynik = []
    for w in wiersze:
        t = typy.get(w["id"], [])
        if tylko_wykazy and not w["wykaz_zbiorczy"]:
            continue
        if wykaz_typ and wykaz_typ.upper() not in ([w["wykaz_zbiorczy"]] + t):
            continue
        wynik.append(_zbior(w, liczby.get(w["id"], 0), t, {"id": w["instytucja_id"], "nazwa": w["i_nazwa"], "typ": w["i_typ"]}))
    return wynik


def pobierz_zbior(zbior_id: int) -> dict | None:
    with baza.transakcja() as con:
        w = con.execute("SELECT zb.*, i.nazwa AS i_nazwa, i.typ AS i_typ FROM zbiory zb "
                        "JOIN instytucje i ON i.id = zb.instytucja_id WHERE zb.id = ?", (zbior_id,)).fetchone()
        if w is None:
            return None
        liczby, typy = _statystyki_zbiorow(con, [w["id"]], False)
    return _zbior(w, liczby.get(w["id"], 0), typy.get(w["id"], []),
                  {"id": w["instytucja_id"], "nazwa": w["i_nazwa"], "typ": w["i_typ"]})


# ---------------------------------------------------------------- zasoby
def _wiersz_zasobu(con, zasob_id: int):
    return con.execute("SELECT z.*, zb.instytucja_id FROM zasoby z JOIN zbiory zb ON zb.id = z.zbior_id "
                       "WHERE z.id = ?", (zasob_id,)).fetchone()


def _raport_braku(komunikat: str) -> dict:
    return {"poprawne_wiersze": 0, "bledne_wiersze": 0, "liczba_wierszy": 0, "arkusz": None, "ucieto": False,
            "bledy": [{"wiersz": None, "pole": "url", "kod": "required", "komunikat": komunikat}], "ostrzezenia": []}


def dodaj_lub_zaktualizuj_zasob(zbior_id: int, *, tytul: str, opis: str = "", plik: bytes | None = None,
                                nazwa_pliku: str | None = None, url: str | None = None,
                                wykaz_typ: str | None = None, status: str = "opublikowany",
                                data_danych: str | None = None, zasob_id: int | None = None,
                                ext_ident: str | None = None, potwierdz_zastapienie: bool = False,
                                przebuduj: bool = True) -> dict:
    """Zapisuje zasób, uruchamia walidację wykazu (gdy wykaz_typ) i – jeśli zasób dotyczy wykazu –
    przebudowę wykazu zbiorczego. Zwraca {zasob, walidacja, wykaz: {przebudowano, komunikat}}.
    Rzuca app.portal.wykazy.BladWykazu (kod 422/409, komunikat) przy naruszeniu reguł wykazu.

    Aktualizacja: `zasob_id` (panel) albo `ext_ident` w obrębie zbioru (harvester – upsert). Przy aktualizacji
    bez nowego pliku/URL zostaje dotychczasowy plik (i jest ponownie walidowany, jeśli zasób dotyczy wykazu).
    `potwierdz_zastapienie` – zdejmuje oznaczenie wykazu z innego opublikowanego zasobu instytucji zamiast 409.
    `przebuduj=False` – bez przebudowy wykazu (import wsadowy: wywołaj potem wykazy.utworz_wykaz_zbiorczy()).
    """
    wykaz_typ = (wykaz_typ or "").strip().upper() or None
    if wykaz_typ:
        wykaz_typ = wykazy.konfiguracja(wykaz_typ).typ
    if status not in STATUSY:
        raise BladPortalu(422, f"Nieprawidłowy status zasobu „{status}” (dozwolone: {', '.join(STATUSY)}).", {"pole": "status"})
    if not (tytul or "").strip():
        raise BladPortalu(422, "Tytuł zasobu jest wymagany.", {"pole": "tytul"})
    zbior = pobierz_zbior(zbior_id)
    if zbior is None:
        raise BladPortalu(404, f"Nie znaleziono zbioru o id {zbior_id}.")
    if zbior["zrodlo"] == "system":
        raise BladPortalu(403, "Zbiór wykazu zbiorczego jest tworzony automatycznie przez portal – nie można w nim "
                               "ręcznie dodawać ani zmieniać zasobów.")
    if status == "opublikowany" and zbior["status"] != "opublikowany":     # wzór: _validate_resource_status
        raise BladPortalu(422, "Nie można opublikować zasobu w zbiorze, który jest szkicem – najpierw opublikuj zbiór.",
                          {"pole": "status"})
    instytucja = pobierz_instytucje(zbior["instytucja_id"])

    with baza.transakcja() as con:
        stary = None
        if zasob_id is not None:
            stary = _wiersz_zasobu(con, zasob_id)
            if stary is None or stary["wykaz_zbiorczy"]:
                raise BladPortalu(404, f"Nie znaleziono zasobu o id {zasob_id}.")
            if stary["zbior_id"] != zbior_id:
                raise BladPortalu(422, "Zasób należy do innego zbioru.")
        elif ext_ident:
            stary = con.execute("SELECT z.*, ? AS instytucja_id FROM zasoby z WHERE zbior_id = ? AND ext_ident = ?",
                                (zbior["instytucja_id"], zbior_id, ext_ident)).fetchone()
    stary = dict(stary) if stary else None

    # ------------------------------------------------ treść do walidacji / zapisu
    nowy_plik: tuple[bytes, str] | None = None
    blad_pobrania: str | None = None
    if plik is not None:
        if len(plik) > config.MAX_FILE_BYTES:
            raise BladPortalu(413, f"Plik jest za duży ({len(plik) // 1024} KB). Maksymalny rozmiar to "
                                   f"{config.MAX_FILE_BYTES // (1024 * 1024)} MB.", {"pole": "plik"})
        if not plik:
            raise BladPortalu(422, "Wgrany plik jest pusty.", {"pole": "plik"})
        nowy_plik = (plik, nazwa_pliku or "plik")
        url = url or None
    elif url:
        zmiana_url = stary is None or url != stary.get("url") or not stary.get("plik_sciezka")
        if wykaz_typ and zmiana_url:
            try:
                nowy_plik = _pobierz_url(url)
            except BladPortalu as e:
                if e.kod_http == 413:
                    raise
                blad_pobrania = e.komunikat
        elif zmiana_url and stary and stary.get("plik_sciezka"):
            nowy_plik = None          # zasób zmienia się w link – stary plik zostanie usunięty
    elif stary is None:
        raise BladPortalu(422, "Podaj plik zasobu albo adres URL.", {"pole": "plik"})
    else:
        url = stary.get("url")

    zachowaj_stary_plik = bool(stary and stary.get("plik_sciezka") and nowy_plik is None
                               and (plik is None and (not url or url == stary.get("url"))))
    dane_do_walidacji: tuple[bytes, str] | None = nowy_plik
    if dane_do_walidacji is None and zachowaj_stary_plik:
        p = baza.sciezka_absolutna(stary["plik_sciezka"])
        if p and p.exists():
            dane_do_walidacji = (p.read_bytes(), stary.get("nazwa_pliku") or p.name)

    # ------------------------------------------------ walidacja wykazu (wzór: ResourceForm.clean)
    zdejmij_z = None
    if wykaz_typ:
        if dane_do_walidacji is None:
            konf = wykazy.konfiguracja(wykaz_typ)
            wykazy.sprawdz_typ_instytucji(konf, instytucja["typ"], instytucja["nazwa"])
            walidacja = {"walidacja_status": "BRAK", "liczba_wierszy": None,
                         "raport": _raport_braku(blad_pobrania or "Brak pliku zasobu do sprawdzenia zgodności z wzorcem.")}
        else:
            walidacja = wykazy.waliduj_zasob_wykazu(
                wykaz_typ, instytucja=instytucja, dane=dane_do_walidacji[0], nazwa_pliku=dane_do_walidacji[1],
                zasob_id=stary["id"] if stary else None, status=status, potwierdz_zastapienie=potwierdz_zastapienie)
            zdejmij_z = walidacja.get("zdejmij_flage_z")
    else:
        walidacja = {"walidacja_status": "NIE_DOTYCZY", "liczba_wierszy": None, "raport": None}

    # ------------------------------------------------ zapis
    teraz = baza.teraz_iso()
    nazwa_zap = _bezpieczna_nazwa(nowy_plik[1]) if nowy_plik else (stary.get("nazwa_pliku") if zachowaj_stary_plik else None)
    fmt = _format(nazwa_zap, url) if (nowy_plik or zachowaj_stary_plik) else _format(None, url)
    pola = dict(tytul=tytul.strip(), opis=opis or "", format=fmt, url=url, wykaz_typ=wykaz_typ, status=status,
                walidacja_status=walidacja["walidacja_status"],
                walidacja_raport=baza.do_json(walidacja["raport"]) if walidacja["raport"] is not None else None,
                liczba_wierszy=walidacja["liczba_wierszy"], data_danych=data_danych or (stary or {}).get("data_danych"),
                zmodyfikowano=teraz)
    stary_plik = stary.get("plik_sciezka") if stary else None
    zapisany_plik: Path | None = None
    with baza.transakcja() as con:
        if stary:
            zid = stary["id"]
            con.execute(f"UPDATE zasoby SET {', '.join(k + '=?' for k in pola)} WHERE id = ?", (*pola.values(), zid))
        else:
            pola_ins = {**pola, "zbior_id": zbior_id, "ext_ident": ext_ident, "utworzono": teraz}
            cur = con.execute(f"INSERT INTO zasoby ({', '.join(pola_ins)}) VALUES ({','.join('?' * len(pola_ins))})",
                              tuple(pola_ins.values()))
            zid = cur.lastrowid
        if nowy_plik:
            katalog = baza.katalog_media() / "zasoby" / str(zid)
            katalog.mkdir(parents=True, exist_ok=True)
            zapisany_plik = katalog / f"{teraz.replace(':', '').replace('-', '')}_{uuid.uuid4().hex[:8]}_{nazwa_zap}"
            zapisany_plik.write_bytes(nowy_plik[0])
            con.execute("UPDATE zasoby SET plik_sciezka = ?, nazwa_pliku = ? WHERE id = ?",
                        (baza.sciezka_wzgledna(zapisany_plik), nazwa_zap, zid))
        elif not zachowaj_stary_plik:
            con.execute("UPDATE zasoby SET plik_sciezka = NULL, nazwa_pliku = NULL WHERE id = ?", (zid,))
        if zdejmij_z:    # wzór: _remove_dga_flag_from_current_dga_resource_if_needed
            con.execute("UPDATE zasoby SET wykaz_typ = NULL, walidacja_status = 'NIE_DOTYCZY', zmodyfikowano = ? "
                        "WHERE id = ?", (teraz, zdejmij_z))
        con.execute("UPDATE zbiory SET zmodyfikowano = ? WHERE id = ?", (teraz, zbior_id))
    if stary_plik and (zapisany_plik is not None or not zachowaj_stary_plik) \
            and (zapisany_plik is None or baza.sciezka_wzgledna(zapisany_plik) != stary_plik):
        _usun_plik(stary_plik)

    # ------------------------------------------------ przebudowa wykazu (wzór: sygnał -> create_main_dga_resource_task)
    typy = {t for t in (wykaz_typ, (stary or {}).get("wykaz_typ")) if t}
    wykaz = _przebuduj(typy, przebuduj)
    with baza.transakcja() as con:
        zasob = _zasob(_wiersz_zasobu(con, zid), pelny=True)
    if zdejmij_z:
        wykaz["zdjeto_oznaczenie_z_zasobu"] = zdejmij_z
    return {"zasob": zasob, "walidacja": walidacja["raport"], "wykaz": wykaz}


def _przebuduj(typy: set[str], przebuduj: bool) -> dict:
    if not typy:
        return {"przebudowano": False, "komunikat": "Zasób nie dotyczy wykazu zbiorczego."}
    if not przebuduj:
        return {"przebudowano": False, "komunikat": "Przebudowa wykazu odroczona (import wsadowy)."}
    wynik = {"przebudowano": True, "komunikat": ""}
    komunikaty = []
    for t in sorted(typy):
        info = wykazy.utworz_wykaz_zbiorczy(t)
        wynik["przebudowano"] = wynik["przebudowano"] and info["status"] == "OK"
        wynik.setdefault("wykazy_info_id", info["id"])
        komunikaty.append(f"{wykazy.konfiguracja(t).tytul_zbioru}: {info['komunikat']}")
    wynik["komunikat"] = " ".join(komunikaty)
    return wynik


def _usun_plik(wzgl: str | None) -> None:
    p = baza.sciezka_absolutna(wzgl)
    try:
        if p and p.exists():
            p.unlink()
            if p.parent.exists() and not any(p.parent.iterdir()):
                p.parent.rmdir()
    except OSError as e:
        logger.error("Nie usunięto pliku %s: %s", p, e)


def lista_zasobow(zbior_id: int, *, tylko_opublikowane: bool = False) -> list[dict]:
    """[{id, zbior_id, tytul, opis, format, url_pobrania, wykaz_typ, status, walidacja_status,
         liczba_wierszy, data_danych, zmodyfikowano}]  (+ wykaz_zbiorczy, url, nazwa_pliku, ext_ident, utworzono)"""
    sql = "SELECT * FROM zasoby WHERE zbior_id = ?" + (" AND status = 'opublikowany'" if tylko_opublikowane else "")
    with baza.transakcja() as con:
        return [_zasob(w) for w in con.execute(sql + " ORDER BY id", (zbior_id,)).fetchall()]


def pobierz_zasob(zasob_id: int) -> dict | None:
    """Jak w lista_zasobow + `plik_sciezka` (absolutna), `walidacja_raport` i `instytucja_id`."""
    with baza.transakcja() as con:
        w = _wiersz_zasobu(con, zasob_id)
    return _zasob(w, pelny=True) if w else None


def usun_zasob(zasob_id: int) -> dict:
    """Usuwa zasób i jego plik; jeśli był zasobem wykazu – przebudowuje wykaz. Zwraca {usunieto, wykaz}."""
    with baza.transakcja() as con:
        w = _wiersz_zasobu(con, zasob_id)
        if w is None:
            raise BladPortalu(404, f"Nie znaleziono zasobu o id {zasob_id}.")
        if w["wykaz_zbiorczy"]:
            raise BladPortalu(403, "Zasoby wykazu zbiorczego są zarządzane automatycznie – nie można ich usunąć ręcznie.")
        con.execute("DELETE FROM zasoby WHERE id = ?", (zasob_id,))
        con.execute("UPDATE zbiory SET zmodyfikowano = ? WHERE id = ?", (baza.teraz_iso(), w["zbior_id"]))
    _usun_plik(w["plik_sciezka"])
    katalog = baza.katalog_media() / "zasoby" / str(zasob_id)
    if katalog.exists():
        shutil.rmtree(katalog, ignore_errors=True)
    return {"usunieto": zasob_id, "wykaz": _przebuduj({w["wykaz_typ"]} if w["wykaz_typ"] else set(), True)}


__all__ = ["BladPortalu", "BladWykazu", "lista_instytucji", "pobierz_instytucje", "utworz_instytucje", "utworz_zbior",
           "lista_zbiorow", "pobierz_zbior", "dodaj_lub_zaktualizuj_zasob", "lista_zasobow", "pobierz_zasob",
           "usun_zasob", "czy_portal_pusty"]
