"""Deduplikacja rekordów między źródłami. Właściciel: Backend.

Reguły (zob. docs/SPRINTY.md, aed_schema.json -> x-priorytet-zrodel):
* porównujemy wyłącznie rekordy z RÓŻNYCH typów źródeł – dwa urządzenia z tego samego
  źródła (np. dwa AED w jednym budynku) nigdy nie są łączone;
* kandydat na duplikat: odległość < 25 m ORAZ (podobny adres LUB ten sam dysponent LUB
  jeden z rekordów pochodzi z OSM); rekordy na różnych kondygnacjach nie są duplikatami;
* rekord o niższym priorytecie źródła dostaje `duplikat_z` = uid rekordu nadrzędnego
  (nie jest usuwany); dopasowanie jest „jeden do jednego” (najbliższe pary najpierw),
  więc dwa urządzenia OSM w jednym budynku nie zapadną się w jedno urządzenie dane.gov.pl;
* indeks siatkowy zamiast O(n²).
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict

from . import schema

PROMIEN_M = 25.0
_KOMORKA_STOPNIE = 0.0005     # ~35-55 m, więcej niż promień w obu osiach dla szerokości Polski

_PREFIKSY_ULICY = re.compile(r"^(ulica|ul|aleje|aleja|al|plac|pl|osiedle|os|rondo|rynek)\b\.?\s*")


def odleglosc_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bez_diakrytykow(s: str) -> str:
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _norm(s) -> str:
    if s is None:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", _bez_diakrytykow(str(s)).lower()).strip()


def _ulica_norm(s) -> str:
    t = _norm(s)
    return _PREFIKSY_ULICY.sub("", t).strip()


def _nr_norm(s) -> str:
    return re.sub(r"[^a-z0-9/]", "", _bez_diakrytykow(str(s or "")).lower())


def adres_podobny(a: dict, b: dict) -> bool:
    ua, ub = _ulica_norm(a.get("ulica")), _ulica_norm(b.get("ulica"))
    na, nb = _nr_norm(a.get("nr_budynku")), _nr_norm(b.get("nr_budynku"))
    if not (na and nb and na == nb):
        return False
    if ua and ub:
        return ua == ub
    # jedna strona bez ulicy (np. wieś bez ulic) – wystarczy ta sama miejscowość i numer
    ma, mb = _norm(a.get("miejscowosc")), _norm(b.get("miejscowosc"))
    return bool(ma and ma == mb)


def ten_sam_dysponent(a: dict, b: dict) -> bool:
    ia, ib = (a.get("identyfikator_dysponenta") or "").strip(), (b.get("identyfikator_dysponenta") or "").strip()
    if ia and ib and ia == ib:
        return True
    na, nb = _norm(a.get("nazwa_dysponenta")), _norm(b.get("nazwa_dysponenta"))
    return bool(na and nb and (na == nb or na in nb or nb in na))


def _inna_kondygnacja(a: dict, b: dict) -> bool:
    ka, kb = _norm(a.get("kondygnacja")), _norm(b.get("kondygnacja"))
    return bool(ka and kb and ka != kb)


def _kandydat(a: dict, b: dict) -> bool:
    if _inna_kondygnacja(a, b):
        return False
    if "OSM" in (a.get("zrodlo_typ"), b.get("zrodlo_typ")):
        return True
    return adres_podobny(a, b) or ten_sam_dysponent(a, b)


def znajdz_duplikaty(rekordy: list[dict], promien_m: float = PROMIEN_M) -> dict[str, str]:
    """Zwraca {uid_duplikatu: uid_rekordu_nadrzędnego} dla całego zbioru rekordów.

    Rekord wejściowy: dict z kluczami uid, zrodlo_typ, szerokosc_geo, dlugosc_geo oraz
    (opcjonalnie) ulica, nr_budynku, miejscowosc, kondygnacja, identyfikator_dysponenta, nazwa_dysponenta.
    """
    kolejnosc = schema.priorytet_zrodel()
    ranga = {t: i for i, t in enumerate(kolejnosc)}

    def r(rek: dict) -> int:
        return ranga.get(rek.get("zrodlo_typ"), len(kolejnosc))

    siatka: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, rek in enumerate(rekordy):
        lat, lon = rek.get("szerokosc_geo"), rek.get("dlugosc_geo")
        if lat is None or lon is None:
            continue
        siatka[(math.floor(lat / _KOMORKA_STOPNIE), math.floor(lon / _KOMORKA_STOPNIE))].append(i)

    pary: list[tuple[float, int, int]] = []     # (odległość, nadrzędny, podrzędny)
    for (cy, cx), idxs in siatka.items():
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                sasiedzi = siatka.get((cy + dy, cx + dx))
                if not sasiedzi:
                    continue
                for i in idxs:
                    for j in sasiedzi:
                        if i == j:
                            continue
                        a, b = rekordy[i], rekordy[j]
                        # każdą parę rozpatrujemy raz: i = rekord o wyższym priorytecie
                        if r(a) >= r(b):
                            continue
                        d = odleglosc_m(a["szerokosc_geo"], a["dlugosc_geo"], b["szerokosc_geo"], b["dlugosc_geo"])
                        if d < promien_m and _kandydat(a, b):
                            pary.append((d, i, j))

    pary.sort(key=lambda p: (p[0], rekordy[p[1]]["uid"], rekordy[p[2]]["uid"]))
    rodzic: dict[int, int] = {}
    zajete: set[tuple[int, str]] = set()
    for d, i, j in pary:
        if j in rodzic:
            continue
        klucz = (i, rekordy[j].get("zrodlo_typ"))
        if klucz in zajete:
            continue
        rodzic[j] = i
        zajete.add(klucz)

    def korzen(j: int) -> int:
        while j in rodzic:        # rangi rosną ściśle, więc nie ma cykli
            j = rodzic[j]
        return j

    return {rekordy[j]["uid"]: rekordy[korzen(j)]["uid"] for j in rodzic}
