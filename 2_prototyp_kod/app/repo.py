"""Wspólny interfejs dostępu do danych (KONTRAKT między agentami Backend i API).

Właściciel implementacji: agent Backend.
Agent API korzysta WYŁĄCZNIE z funkcji poniżej (nie importuje bezpośrednio db.py).

Rekord = dict z polami `fields` + `x-pola-systemowe` z 1_wzorzec_danych/aed_schema.json
(oraz dodatkowo `zrodlo_id` – identyfikator źródła, z którego pochodzi rekord).
Brakujące wartości = None (nigdy "nan", "" ani "None").

Rozszerzenia względem pierwotnych sygnatur (zgodne wstecz – tylko nowe, opcjonalne argumenty
i nowe funkcje): `lista_rekordow(..., wojewodztwo, status_weryfikacji, bbox)`, `pobierz_rekord`,
`statystyki`, `czy_baza_pusta`.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Iterable

from . import db, dedup, schema

OTWARTE_LICENCJE = ("CC0 1.0", "CC BY 4.0")
_DOMYSLNY_STATUS = {
    "DANE_GOV_PL": "ZWERYFIKOWANY_DANE_GOV_PL",
    "DYSPONENT": "ZGLOSZONY_PRZEZ_DYSPONENTA",
    "OSM": "DO_WERYFIKACJI",
}
_DOMYSLNA_LICENCJA = {"OSM": "ODbL 1.0"}
_PUSTE = {"", "nan", "none", "nat", "null"}
_PREFIKS_TYPU = {"dane-gov-pl": "DANE_GOV_PL", "dysponent": "DYSPONENT", "osm": "OSM"}


@dataclass
class Zrodlo:
    id: str                 # np. "dane-gov-pl:3624", "dysponent:5252248481", "osm:Sosnowiec"
    typ: str                # DANE_GOV_PL | DYSPONENT | OSM
    nazwa: str
    url: str | None
    licencja: str           # "CC0 1.0" | "CC BY 4.0" | "ODbL 1.0"


@dataclass
class WynikZapisu:
    dodano: int = 0
    zaktualizowano: int = 0
    oznaczono_duplikaty: int = 0
    ostrzezenia: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------- pomocnicze

def _czysta(v):
    """Puste/„nan” -> None; teksty obcięte z białych znaków."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        return None if s.lower() in _PUSTE else s
    return v


def _liczba(v):
    v = _czysta(v)
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    try:
        f = float(str(v).replace(",", ".").replace(" ", "").replace(" ", ""))
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def _sufiks_zrodla(zrodlo_id: str) -> str:
    return zrodlo_id.split(":", 1)[1] if ":" in zrodlo_id else zrodlo_id


def _typ_z_id(zrodlo_id: str) -> str | None:
    return _PREFIKS_TYPU.get(zrodlo_id.split(":", 1)[0].lower())


def _pobierz_zrodlo(con, zrodlo_id: str) -> dict | None:
    w = con.execute("SELECT * FROM zrodla WHERE id = ?", (zrodlo_id,)).fetchone()
    return dict(w) if w else None


def _normalizuj(rek: dict, zrodlo_id: str, zr: dict | None, wynik: WynikZapisu, nr: int) -> dict | None:
    znane = set(schema.nazwy_wszystkich()) | {"zrodlo_id"}
    obce = sorted(k for k in rek if k not in znane)
    if obce and not any("nieznane pola" in o for o in wynik.ostrzezenia):
        wynik.ostrzezenia.append(f"Pominięto nieznane pola: {', '.join(obce)}.")

    out: dict = {}
    for p in schema.pola():
        n = p["name"]
        v = _czysta(rek.get(n))
        if p.get("type") == "number":
            v = _liczba(v)
        elif v is not None and not isinstance(v, str):
            v = str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
        out[n] = v

    lat, lon = out["szerokosc_geo"], out["dlugosc_geo"]
    if lat is None or lon is None:
        wynik.ostrzezenia.append(f"Rekord nr {nr} ({rek.get('id_aed') or '?'}): brak współrzędnych – pominięto.")
        return None
    if out["id_aed"] is None:
        wynik.ostrzezenia.append(f"Rekord nr {nr}: brak id_aed – pominięto.")
        return None

    typ = _czysta(rek.get("zrodlo_typ")) or (zr or {}).get("typ") or _typ_z_id(zrodlo_id) or "DYSPONENT"
    out["zrodlo_typ"] = typ
    out["zrodlo_nazwa"] = _czysta(rek.get("zrodlo_nazwa")) or (zr or {}).get("nazwa")
    out["zrodlo_url"] = _czysta(rek.get("zrodlo_url")) or (zr or {}).get("url")
    out["licencja"] = _czysta(rek.get("licencja")) or (zr or {}).get("licencja") or _DOMYSLNA_LICENCJA.get(typ)
    out["status_weryfikacji"] = _czysta(rek.get("status_weryfikacji")) or _DOMYSLNY_STATUS.get(typ)
    out["data_pobrania"] = _czysta(rek.get("data_pobrania")) or db.teraz_iso()
    out["uid"] = _czysta(rek.get("uid")) or (
        f"{typ}:{out['identyfikator_dysponenta'] or _sufiks_zrodla(zrodlo_id)}:{out['id_aed']}"
    )
    out["kompletnosc"] = schema.kompletnosc(out)
    out["duplikat_z"] = None
    return out


def _wiersz_do_rekordu(w) -> dict:
    dane = json.loads(w["dane"])
    rek = {n: dane.get(n) for n in schema.nazwy_wszystkich()}
    rek["kompletnosc"] = w["kompletnosc"]
    rek["duplikat_z"] = w["duplikat_z"]
    rek["zrodlo_id"] = w["zrodlo_id"]
    return rek


def _przelicz_duplikaty(con, uid_zapisane: set[str]) -> int:
    """Przelicza `duplikat_z` w całej bazie; zwraca liczbę rekordów nowo oznaczonych w tym wywołaniu."""
    wiersze = con.execute("SELECT uid, zrodlo_typ, szerokosc_geo, dlugosc_geo, duplikat_z, dane FROM rekordy").fetchall()
    rekordy = []
    for w in wiersze:
        d = json.loads(w["dane"])
        d.update(uid=w["uid"], zrodlo_typ=w["zrodlo_typ"], szerokosc_geo=w["szerokosc_geo"], dlugosc_geo=w["dlugosc_geo"])
        rekordy.append(d)
    nowe = dedup.znajdz_duplikaty(rekordy)
    obecne = {w["uid"]: w["duplikat_z"] for w in wiersze}
    zmiany = []
    nowo = 0
    for uid, stary in obecne.items():
        cel = nowe.get(uid)
        if cel != stary:
            zmiany.append((cel, uid))
            if cel is not None and stary is None:
                nowo += 1
    con.executemany("UPDATE rekordy SET duplikat_z = ? WHERE uid = ?", zmiany)
    return nowo


# ----------------------------------------------------------------------------- API repo

def zarejestruj_zrodlo(zrodlo: Zrodlo) -> None:
    """Upsert źródła; ustawia ostatnia_synchronizacja = teraz (UTC)."""
    with db.transakcja() as con:
        con.execute(
            """INSERT INTO zrodla (id, typ, nazwa, url, licencja, ostatnia_synchronizacja)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET typ=excluded.typ, nazwa=excluded.nazwa, url=excluded.url,
                   licencja=excluded.licencja, ostatnia_synchronizacja=excluded.ostatnia_synchronizacja""",
            (zrodlo.id, zrodlo.typ, zrodlo.nazwa, zrodlo.url, zrodlo.licencja, db.teraz_iso()),
        )


def zapisz_rekordy(rekordy: Iterable[dict], zrodlo_id: str, zastap: bool = True) -> WynikZapisu:
    """Zapisuje znormalizowane rekordy źródła.

    - zastap=True: usuwa wcześniejsze rekordy tego źródła, których nie ma w nowej partii (pełna synchronizacja).
      Uwaga: pusta partia przy zastap=True usuwa wszystkie rekordy źródła.
    - Wylicza `kompletnosc`, `uid` (jeśli brak), uruchamia deduplikację wg `x-priorytet-zrodel`.
    - Rekordy bez współrzędnych lub bez `id_aed` są pomijane (z ostrzeżeniem w wyniku).
    - `oznaczono_duplikaty` = liczba rekordów w całej bazie nowo oznaczonych jako duplikat po tym zapisie.
    """
    wynik = WynikZapisu()
    with db.transakcja() as con:
        zr = _pobierz_zrodlo(con, zrodlo_id)
        if zr is None:
            wynik.ostrzezenia.append(f"Źródło „{zrodlo_id}” nie było zarejestrowane – typ ustalono z identyfikatora.")
        istniejace = {w["uid"]: w["zrodlo_id"] for w in con.execute("SELECT uid, zrodlo_id FROM rekordy")}
        widziane: set[str] = set()

        for nr, rek in enumerate(rekordy, start=1):
            n = _normalizuj(rek, zrodlo_id, zr, wynik, nr)
            if n is None:
                continue
            uid = n["uid"]
            if uid in istniejace and istniejace[uid] != zrodlo_id:
                wynik.ostrzezenia.append(f"uid „{uid}” istnieje już w innym źródle – nadano uid z sufiksem źródła.")
                uid = n["uid"] = f"{uid}#{zrodlo_id}"
            if uid in widziane:
                wynik.ostrzezenia.append(f"Powtórzony uid „{uid}” w partii – użyto ostatniego rekordu.")
            if uid in istniejace or uid in widziane:
                if uid not in widziane:
                    wynik.zaktualizowano += 1
            else:
                wynik.dodano += 1
            widziane.add(uid)
            istniejace.setdefault(uid, zrodlo_id)
            dane = {k: v for k, v in n.items() if k not in ("duplikat_z", "kompletnosc", "uid")}
            dane["uid"] = uid
            con.execute(
                """INSERT INTO rekordy (uid, zrodlo_id, zrodlo_typ, status_weryfikacji, licencja,
                       identyfikator_dysponenta, wojewodztwo, szerokosc_geo, dlugosc_geo, kompletnosc, duplikat_z, dane)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                   ON CONFLICT(uid) DO UPDATE SET zrodlo_id=excluded.zrodlo_id, zrodlo_typ=excluded.zrodlo_typ,
                       status_weryfikacji=excluded.status_weryfikacji, licencja=excluded.licencja,
                       identyfikator_dysponenta=excluded.identyfikator_dysponenta, wojewodztwo=excluded.wojewodztwo,
                       szerokosc_geo=excluded.szerokosc_geo, dlugosc_geo=excluded.dlugosc_geo,
                       kompletnosc=excluded.kompletnosc, duplikat_z=NULL, dane=excluded.dane""",
                (uid, zrodlo_id, n["zrodlo_typ"], n["status_weryfikacji"], n["licencja"],
                 n["identyfikator_dysponenta"], n["wojewodztwo"], n["szerokosc_geo"], n["dlugosc_geo"],
                 n["kompletnosc"], json.dumps(dane, ensure_ascii=False)),
            )

        if zastap:
            stare = [(u,) for u, z in istniejace.items() if z == zrodlo_id and u not in widziane]
            con.executemany("DELETE FROM rekordy WHERE uid = ?", stare)
        if zr is not None:
            con.execute("UPDATE zrodla SET ostatnia_synchronizacja = ? WHERE id = ?", (db.teraz_iso(), zrodlo_id))

        wynik.oznaczono_duplikaty = _przelicz_duplikaty(con, widziane)
    return wynik


def lista_rekordow(
    *,
    tylko_otwarte_licencje: bool = False,   # True => bez ODbL (eksport dla dane.gov.pl)
    zrodlo_typ: str | None = None,
    uwzglednij_duplikaty: bool = False,
    identyfikator_dysponenta: str | None = None,
    wojewodztwo: str | None = None,
    status_weryfikacji: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,   # (minLon, minLat, maxLon, maxLat)
) -> list[dict]:
    warunki, par = [], []
    if tylko_otwarte_licencje:
        warunki.append(f"licencja IN ({','.join('?' * len(OTWARTE_LICENCJE))})")
        par += list(OTWARTE_LICENCJE)
    if zrodlo_typ:
        warunki.append("zrodlo_typ = ?")
        par.append(zrodlo_typ)
    if not uwzglednij_duplikaty:
        warunki.append("duplikat_z IS NULL")
    if identyfikator_dysponenta:
        warunki.append("identyfikator_dysponenta = ?")
        par.append(identyfikator_dysponenta)
    if wojewodztwo:
        warunki.append("wojewodztwo = ?")
        par.append(wojewodztwo)
    if status_weryfikacji:
        warunki.append("status_weryfikacji = ?")
        par.append(status_weryfikacji)
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        warunki.append("dlugosc_geo BETWEEN ? AND ? AND szerokosc_geo BETWEEN ? AND ?")
        par += [min_lon, max_lon, min_lat, max_lat]
    sql = "SELECT * FROM rekordy" + (" WHERE " + " AND ".join(warunki) if warunki else "") + " ORDER BY uid"
    with db.transakcja() as con:
        return [_wiersz_do_rekordu(w) for w in con.execute(sql, par).fetchall()]


def pobierz_rekord(uid: str) -> dict | None:
    with db.transakcja() as con:
        w = con.execute("SELECT * FROM rekordy WHERE uid = ?", (uid,)).fetchone()
        return _wiersz_do_rekordu(w) if w else None


def lista_zrodel() -> list[dict]:
    """[{id, typ, nazwa, url, licencja, liczba_rekordow, ostatnia_synchronizacja}]"""
    with db.transakcja() as con:
        wiersze = con.execute(
            """SELECT z.id, z.typ, z.nazwa, z.url, z.licencja, z.ostatnia_synchronizacja,
                      (SELECT COUNT(*) FROM rekordy r WHERE r.zrodlo_id = z.id) AS liczba_rekordow
               FROM zrodla z ORDER BY z.id"""
        ).fetchall()
    return [
        {k: w[k] for k in ("id", "typ", "nazwa", "url", "licencja", "liczba_rekordow", "ostatnia_synchronizacja")}
        for w in wiersze
    ]


def czy_baza_pusta() -> bool:
    with db.transakcja() as con:
        return con.execute("SELECT 1 FROM rekordy LIMIT 1").fetchone() is None


def statystyki() -> dict:
    """Liczby rekordów (bez duplikatów) wg status_weryfikacji, zrodlo_typ, wojewodztwo + liczba duplikatów."""
    def grupuj(con, kol):
        return {
            (w[0] if w[0] is not None else "brak_danych"): w[1]
            for w in con.execute(
                f"SELECT {kol}, COUNT(*) FROM rekordy WHERE duplikat_z IS NULL GROUP BY {kol} ORDER BY 2 DESC"
            )
        }

    with db.transakcja() as con:
        razem = con.execute("SELECT COUNT(*) FROM rekordy WHERE duplikat_z IS NULL").fetchone()[0]
        dup = con.execute("SELECT COUNT(*) FROM rekordy WHERE duplikat_z IS NOT NULL").fetchone()[0]
        sr = con.execute("SELECT AVG(kompletnosc) FROM rekordy WHERE duplikat_z IS NULL").fetchone()[0]
        return {
            "razem": razem,
            "duplikaty": dup,
            "srednia_kompletnosc": round(sr, 4) if sr is not None else None,
            "wg_status_weryfikacji": grupuj(con, "status_weryfikacji"),
            "wg_zrodlo_typ": grupuj(con, "zrodlo_typ"),
            "wg_wojewodztwo": grupuj(con, "wojewodztwo"),
        }
