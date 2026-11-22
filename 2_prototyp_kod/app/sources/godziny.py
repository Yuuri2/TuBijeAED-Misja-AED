"""Podzbiór składni OSM `opening_hours` -> „czy AED jest dostępny teraz”. Właściciel: API.

Brak odpowiednika w mcod (portal nie interpretuje danych zasobów) – moduł służy mapie #TuBijeAED.

Obsługiwane (wystarcza dla wzorca AED – pole `godziny_dostepnosci`):
  24/7
  Mo-Fr 08:00-16:00          zakres dni + przedział
  Mo,We,Fr 08:00-12:00       lista dni
  Sa 09:00-13:00; Su off     wiele reguł po „;”, `off`/`closed` = zamknięte
  Mo-Fr 08:00-12:00,13:00-16:00   kilka przedziałów
  08:00-20:00                bez dni = codziennie
  Fr 22:00-02:00             przez północ (część po północy liczy się w następnym dniu)
Reguła późniejsza zastępuje wcześniejszą dla tych samych dni (semantyka OSM).
Wszystko inne (PH, SH, miesiące, „sunrise”, komentarze) -> None = „nie wiadomo” (nie zgadujemy).
Czas zawsze w strefie Europe/Warsaw.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

STREFA = ZoneInfo("Europe/Warsaw")
DNI = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_PRZEDZIAL = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$")
_DNI_RE = re.compile(r"^(Mo|Tu|We|Th|Fr|Sa|Su)(-(Mo|Tu|We|Th|Fr|Sa|Su))?$")


class BladSkladni(ValueError):
    """Wyrażenie spoza obsługiwanego podzbioru."""


def teraz() -> datetime:
    """Bieżący czas w Warszawie (punkt podmiany w testach)."""
    return datetime.now(STREFA)


def _dni(selektor: str) -> list[int]:
    wynik: list[int] = []
    for czesc in selektor.split(","):
        m = _DNI_RE.match(czesc.strip())
        if not m:
            raise BladSkladni(f"nieobsługiwany selektor dni „{czesc}”")
        a = DNI.index(m.group(1))
        b = DNI.index(m.group(3)) if m.group(3) else a
        i = a
        while True:                       # zakres może się zawijać: Sa-Mo
            wynik.append(i)
            if i == b:
                break
            i = (i + 1) % 7
    return wynik


def _przedzialy(tekst: str) -> list[tuple[int, int]]:
    """'08:00-12:00,13:00-16:00' -> [(480, 720), (780, 960)] w minutach; koniec może być > 1440 (przez północ)."""
    if tekst.lower() in ("off", "closed"):
        return []
    wynik = []
    for czesc in tekst.split(","):
        m = _PRZEDZIAL.match(czesc.strip())
        if not m:
            raise BladSkladni(f"nieobsługiwany przedział „{czesc}”")
        g1, m1, g2, m2 = (int(x) for x in m.groups())
        if g1 > 24 or g2 > 24 or m1 > 59 or m2 > 59:
            raise BladSkladni(f"niepoprawna godzina „{czesc}”")
        od, do = g1 * 60 + m1, g2 * 60 + m2
        if do <= od:
            do += 24 * 60                 # przez północ
        wynik.append((od, do))
    return wynik


def rozklad(wyrazenie: str) -> dict[int, list[tuple[int, int]]]:
    """Wyrażenie -> {dzień 0=Mo..6=Su: [(od, do)]}. Rzuca BladSkladni."""
    s = (wyrazenie or "").strip()
    if not s:
        raise BladSkladni("puste wyrażenie")
    if s == "24/7":
        return {d: [(0, 24 * 60)] for d in range(7)}
    tydzien: dict[int, list[tuple[int, int]]] = {d: [] for d in range(7)}
    for regula in [r.strip() for r in s.split(";") if r.strip()]:
        czesci = regula.split(None, 1)
        if len(czesci) == 1:
            if czesci[0] == "24/7":
                dni, czasy = list(range(7)), [(0, 24 * 60)]
            elif _PRZEDZIAL.match(czesci[0].split(",")[0]):
                dni, czasy = list(range(7)), _przedzialy(czesci[0])
            else:
                raise BladSkladni(f"reguła bez godzin „{regula}”")
        else:
            dni = _dni(czesci[0])
            czasy = _przedzialy(czesci[1].strip())
        for d in dni:
            tydzien[d] = list(czasy)      # późniejsza reguła zastępuje wcześniejszą
    return tydzien


def czy_otwarte(wyrazenie: str, chwila: datetime) -> bool:
    """Rzuca BladSkladni dla nieobsługiwanej składni."""
    t = rozklad(wyrazenie)
    chwila = chwila.astimezone(STREFA) if chwila.tzinfo else chwila.replace(tzinfo=STREFA)
    dzien, minuta = chwila.weekday(), chwila.hour * 60 + chwila.minute
    if any(od <= minuta < do for od, do in t[dzien]):
        return True
    wczoraj = (chwila - timedelta(days=1)).weekday()
    return any(do > 24 * 60 and minuta < do - 24 * 60 for _, do in t[wczoraj])


def dostepny_teraz(godziny: str | None, dostepnosc_typ: str | None = None, status_urzadzenia: str | None = None,
                   chwila: datetime | None = None) -> bool | None:
    """True / False / None („nie wiadomo” – brak lub nieobsługiwana składnia godzin).

    * status `w_serwisie` lub `wycofane` -> False (urządzenie nie nadaje się do użycia);
    * dostepnosc_typ `24_7` bez godzin -> True;
    * godziny w podzbiorze składni -> wynik wg czasu w Warszawie.
    """
    if status_urzadzenia in ("w_serwisie", "wycofane"):
        return False
    chwila = chwila or teraz()
    g = (godziny or "").strip()
    if not g:
        return True if dostepnosc_typ == "24_7" else None
    try:
        return czy_otwarte(g, chwila)
    except BladSkladni:
        return None
