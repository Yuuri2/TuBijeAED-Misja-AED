"""Walidacja danych dysponenta wg aed_schema.json + wczytywanie plików xlsx/csv. Właściciel: Backend.

Reguły (required, enum, pattern, zakresy, typy, warunki WARUNKOWO, ZALECANE, suma kontrolna NIP/REGON)
są czytane ze schematu – moduł nie zawiera zahardkodowanej listy pól. Wyjątki to wyłącznie
algorytmy, których nie da się opisać w JSON (sumy kontrolne) oraz heurystyki ostrzeżeń (PIN, godziny OSM).

Kody błędów: required, enum, pattern, range, type, warunek, suma_kontrolna, zalecane, duplikat.
(„range” obejmuje też przekroczenie maksymalnej długości tekstu; „pattern” – nieprawidłowy URL.)
"""
from __future__ import annotations

import csv
import io
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from . import config, schema

DOZWOLONE_ROZSZERZENIA = (".xlsx", ".csv")
_PUSTE = {"", "nan", "none", "nat", "null"}


class BladPliku(ValueError):
    """Plik nie nadaje się do przetworzenia (zły format, za duży, uszkodzony, pusty)."""

    def __init__(self, komunikat: str, status: int = 400):
        super().__init__(komunikat)
        self.komunikat = komunikat
        self.status = status


# ----------------------------------------------------------------------------- NIP / REGON

def _tylko_cyfry(s: str) -> bool:
    return bool(re.fullmatch(r"\d+", s or ""))


def czy_nip(s: str) -> bool:
    if not (_tylko_cyfry(s) and len(s) == 10) or set(s) == {"0"}:
        return False
    w = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    suma = sum(int(c) * k for c, k in zip(s[:9], w)) % 11
    return suma != 10 and suma == int(s[9])


def czy_regon9(s: str) -> bool:
    if not (_tylko_cyfry(s) and len(s) == 9) or set(s) == {"0"}:
        return False
    w = (8, 9, 2, 3, 4, 5, 6, 7)
    suma = sum(int(c) * k for c, k in zip(s[:8], w)) % 11
    return (0 if suma == 10 else suma) == int(s[8])


def czy_regon14(s: str) -> bool:
    if not (_tylko_cyfry(s) and len(s) == 14) or not czy_regon9(s[:9]):
        return False
    w = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)
    suma = sum(int(c) * k for c, k in zip(s[:13], w)) % 11
    return (0 if suma == 10 else suma) == int(s[13])


def czy_poprawny_identyfikator(s: str) -> bool:
    """NIP (10 cyfr) albo REGON (9 / 14 cyfr) z poprawną sumą kontrolną."""
    return czy_nip(s) or czy_regon9(s) or czy_regon14(s)


# ----------------------------------------------------------------------------- normalizacja wartości

def _pusta(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str):
        return v.strip().lower() in _PUSTE
    try:                                  # pandas.NaT / NA
        return v != v  # noqa: PLR0124
    except Exception:
        return False


def _bez_diakrytykow(s: str) -> str:
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _na_tekst(v) -> str:
    if isinstance(v, bool):
        return "TAK" if v else "NIE"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v).strip()


def _na_liczbe(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    try:
        f = float(str(v).strip().replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def _na_date(v) -> str | None:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return date.fromisoformat(s).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ]00:00(:00)?(\.0+)?Z?", s)    # data zapisana jako datetime
    if m:
        return _na_date(m.group(1))
    return None


def _na_datetime(v) -> str | None:
    if isinstance(v, datetime):
        dt = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    elif isinstance(v, date):
        dt = datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
    else:
        s = str(v).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            s += "T00:00:00"
        s = s.replace(" ", "T", 1).replace("Z", "+00:00").replace("z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dopasuj_slownik(v: str, dozwolone: list[str]) -> str | None:
    """Wartość dokładna albo (jednoznacznie) po zignorowaniu wielkości liter i polskich znaków."""
    if v in dozwolone:
        return v
    klucz = _bez_diakrytykow(v).lower().strip()
    trafienia = [d for d in dozwolone if _bez_diakrytykow(d).lower() == klucz]
    return trafienia[0] if len(trafienia) == 1 else None


def normalizuj_identyfikator(v) -> str:
    """NIP/REGON zapisany z myślnikami, spacjami lub prefiksem PL -> same cyfry."""
    s = re.sub(r"[\s\-]", "", _na_tekst(v))
    return s[2:] if s[:2].upper() == "PL" else s


def _uzupelnij_zera(p: dict, v):
    """Excel obcina zera wiodące z liczb (TERYT 0201011, REGON 012345678) – przywracamy je."""
    if p["name"] == "identyfikator_dysponenta" and isinstance(v, str):
        return normalizuj_identyfikator(v)
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return v
    s = _na_tekst(v)
    if p["name"] == "identyfikator_dysponenta":
        return s.zfill(9) if len(s) == 8 else s.zfill(14) if len(s) == 13 else s
    m = re.fullmatch(r"\^\\d\{(\d+)\}\$", (p.get("constraints") or {}).get("pattern", ""))
    return s.zfill(int(m.group(1))) if m and len(s) < int(m.group(1)) else s


# ----------------------------------------------------------------------------- walidacja jednego wiersza

def _komunikat(typ: str, p: dict, **kw) -> str:
    tytul = p.get("title", p["name"])
    opis = p.get("description", "")
    if typ == "required":
        return f"Pole „{tytul}” jest wymagane – uzupełnij je."
    if typ == "enum":
        return f"Pole „{tytul}”: wartość „{kw['v']}” jest niedozwolona. Dozwolone wartości: {', '.join(kw['dozwolone'])}."
    if typ == "pattern":
        return f"Pole „{tytul}”: wartość „{kw['v']}” ma nieprawidłowy format. {opis}".strip()
    if typ == "type":
        return {
            "number": f"Pole „{tytul}”: „{kw['v']}” nie jest liczbą (np. 52,12345 lub 52.12345).",
            "date": f"Pole „{tytul}”: „{kw['v']}” nie jest datą w formacie RRRR-MM-DD (np. 2026-09-15).",
            "datetime": f"Pole „{tytul}”: „{kw['v']}” nie jest datą i czasem ISO 8601 (np. 2026-11-21T12:00:00Z).",
        }.get(p.get("type"), f"Pole „{tytul}”: nieprawidłowy typ wartości „{kw['v']}”.")
    raise ValueError(typ)


def waliduj_wiersz(wiersz: dict, numer: int = 2, *, pomin_wymagane: frozenset[str] | set[str] = frozenset(),
                   pomin_zalecane: frozenset[str] | set[str] = frozenset()) -> tuple[dict, list[dict], list[dict]]:
    """Waliduje jeden wiersz (dict nazwa_pola -> wartość surowa).

    Zwraca (rekord_znormalizowany, bledy, ostrzezenia). Rekord ma wszystkie pola schematu (brak = None).
    `pomin_wymagane` / `pomin_zalecane` – pola, których brak kolumny zgłoszono już na poziomie pliku.
    """
    bledy: list[dict] = []
    ostrz: list[dict] = []
    rek: dict = {}

    def blad(p, kod, komunikat):
        bledy.append({"wiersz": numer, "pole": p["name"], "kod": kod, "komunikat": komunikat})

    def ostrzez(p, kod, komunikat):
        ostrz.append({"wiersz": numer, "pole": p["name"], "kod": kod, "komunikat": komunikat})

    pola = schema.pola()
    # --- przebieg 1: normalizacja, typ, słownik, wzorzec, zakres
    for p in pola:
        nazwa = p["name"]
        c = p.get("constraints", {})
        surowa = wiersz.get(nazwa)
        if _pusta(surowa):
            rek[nazwa] = None
            continue
        surowa = _uzupelnij_zera(p, surowa)
        typ = p.get("type", "string")
        wartosc = None
        if typ == "number":
            wartosc = _na_liczbe(surowa)
            if wartosc is None:
                blad(p, "type", _komunikat("type", p, v=_na_tekst(surowa)))
                rek[nazwa] = None
                continue
            lo, hi = c.get("minimum"), c.get("maximum")
            if (lo is not None and wartosc < lo) or (hi is not None and wartosc > hi):
                blad(p, "range", f"Pole „{p.get('title', nazwa)}”: wartość {str(wartosc).replace('.', ',')} jest poza "
                                 f"dozwolonym zakresem ({str(lo).replace('.', ',')}–{str(hi).replace('.', ',')}). "
                                 "Sprawdź, czy współrzędne nie są zamienione miejscami lub zapisane w innym formacie.")
        elif typ == "date":
            wartosc = _na_date(surowa)
            if wartosc is None:
                blad(p, "type", _komunikat("type", p, v=_na_tekst(surowa)))
        elif typ == "datetime":
            wartosc = _na_datetime(surowa)
            if wartosc is None:
                blad(p, "type", _komunikat("type", p, v=_na_tekst(surowa)))
        else:
            wartosc = _na_tekst(surowa)
            if "enum" in c:
                dop = _dopasuj_slownik(wartosc, c["enum"])
                if dop is None:
                    blad(p, "enum", _komunikat("enum", p, v=wartosc, dozwolone=c["enum"]))
                else:
                    wartosc = dop
            wzorzec_ok = True
            if "pattern" in c and not re.fullmatch(c["pattern"], wartosc):
                wzorzec_ok = False
                blad(p, "pattern", _komunikat("pattern", p, v=wartosc))
            if "maxLength" in c and len(wartosc) > c["maxLength"]:
                blad(p, "range", f"Pole „{p.get('title', nazwa)}” jest za długie ({len(wartosc)} znaków; "
                                 f"maksimum {c['maxLength']}).")
            if p.get("format") == "uri" and not re.match(r"^https?://\S+$", wartosc):
                blad(p, "pattern", f"Pole „{p.get('title', nazwa)}”: „{wartosc}” nie jest adresem URL "
                                   "(powinien zaczynać się od http:// lub https://).")
            if wzorzec_ok and "suma kontrolna" in (p.get("x-walidacja") or "") and re.fullmatch(r"\d+", wartosc):
                if not czy_poprawny_identyfikator(wartosc):
                    rodzaj = {10: "NIP", 9: "REGON", 14: "REGON"}.get(len(wartosc), "NIP/REGON")
                    blad(p, "suma_kontrolna", f"Numer {rodzaj} „{wartosc}” ma nieprawidłową sumę kontrolną – "
                                              "sprawdź, czy nie ma literówki.")
        rek[nazwa] = wartosc

    # --- przebieg 2: wymagane / warunkowe / zalecane (po normalizacji, bo warunki zależą od wartości)
    for p in pola:
        nazwa = p["name"]
        poziom = p.get("x-wymagane")
        if rek.get(nazwa) is not None:
            continue
        # pole, które miało wartość, ale nie przeszło typu/zakresu, ma już błąd – nie dokładamy „brak wartości”
        if any(b["pole"] == nazwa for b in bledy):
            continue
        if poziom == "TAK" or p.get("constraints", {}).get("required"):
            if nazwa not in pomin_wymagane:
                blad(p, "required", _komunikat("required", p))
        elif poziom == "WARUNKOWO" and schema.warunek_aktywny(p, rek):
            w = schema.warunek(p)
            blad(p, "warunek", _komunikat_warunku(p, w, rek))
        elif poziom == "ZALECANE" and nazwa not in pomin_zalecane:
            ostrzez(p, "zalecane", f"Brak wartości w polu „{p.get('title', nazwa)}” – zalecane uzupełnienie.")

    # --- ostrzeżenia heurystyczne
    instr = rek.get("instrukcja_dostepu")
    if instr and re.search(r"(?<![\d.,-])\d{4,6}(?![\d.,-])", instr):
        p = schema.pole("instrukcja_dostepu")
        ostrzez(p, "zalecane", "Instrukcja dostępu wygląda na zawierającą kod PIN. Nie publikuj kodu w otwartych danych – "
                               "wpisz np. „Kod podaje dyspozytor 112”.")
    godz = rek.get("godziny_dostepnosci")
    if godz and re.search(r"\b(Pn|Wt|Śr|Sr|Cz|Pt|So|Nd|Pon|Wto|Czw|Sob|Niedz)\b", godz):
        ostrzez(schema.pole("godziny_dostepnosci"), "pattern",
                f"Godziny „{godz}” zapisano po polsku. Użyj formatu OSM z angielskimi skrótami dni, "
                "np. „Mo-Fr 08:00-16:00; Sa 09:00-13:00” lub „24/7”.")
    return rek, bledy, ostrz


def _komunikat_warunku(p: dict, w: tuple[str, str, str], rek: dict) -> str:
    tytul = p.get("title", p["name"])
    zrodlo = schema.pole(w[0]) or {"title": w[0]}
    return (f"Pole „{tytul}” jest wymagane, gdy „{zrodlo.get('title', w[0])}” ma wartość inną niż „{w[2]}” "
            f"(obecnie: „{rek.get(w[0])}”).") if w[1] == "!=" else (
            f"Pole „{tytul}” jest wymagane, gdy „{zrodlo.get('title', w[0])}” = „{w[2]}”.")


def waliduj_dysponenta(nazwa: str | None, identyfikator: str | None, typ: str | None) -> list[dict]:
    """Walidacja pól formularza dysponenta (nazwa, NIP/REGON, typ). Zwraca listę błędów (puste = OK)."""
    bledy: list[dict] = []
    tmp = {"nazwa_dysponenta": nazwa, "identyfikator_dysponenta": identyfikator, "typ_dysponenta": typ}
    wiersz = {k: v for k, v in tmp.items()}
    _, b, _ = waliduj_wiersz(wiersz, numer=0, pomin_zalecane={p["name"] for p in schema.pola()})
    for e in b:
        if e["pole"] in tmp:
            bledy.append({"pole": e["pole"], "kod": e["kod"], "komunikat": e["komunikat"]})
    return bledy


# ----------------------------------------------------------------------------- wczytywanie plików

def _wartosc_komorki(v):
    if isinstance(v, str):
        v = v.strip()
    return None if _pusta(v) else v


def _wczytaj_xlsx(dane: bytes) -> tuple[list[str], list[tuple[int, dict]], str]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(dane), read_only=True, data_only=True)
    except Exception as e:  # noqa: BLE001 – uszkodzony / nie-xlsx
        raise BladPliku("Nie udało się otworzyć pliku .xlsx – plik jest uszkodzony lub nie jest skoroszytem Excel.") from e
    nazwy = wb.sheetnames
    arkusz = next((n for n in ("Dane", "Dane_przykladowe") if n in nazwy), nazwy[0] if nazwy else None)
    if arkusz is None:
        raise BladPliku("Skoroszyt nie zawiera żadnych arkuszy.")
    ws = wb[arkusz]
    wiersze = ws.iter_rows(values_only=True)
    try:
        naglowek = next(wiersze)
    except StopIteration:
        return [], [], arkusz
    naglowki = ["" if _pusta(h) else str(h).strip() for h in naglowek]
    wynik: list[tuple[int, dict]] = []
    for nr, w in enumerate(wiersze, start=2):
        if nr - 1 > config.MAX_ROWS:
            raise BladPliku(f"Plik ma więcej niż {config.MAX_ROWS} wierszy – podziel go na mniejsze części.", 413)
        komorki = [_wartosc_komorki(c) for c in w]
        if all(c is None for c in komorki):
            continue
        wynik.append((nr, {h: komorki[i] if i < len(komorki) else None for i, h in enumerate(naglowki) if h}))
    wb.close()
    return naglowki, wynik, arkusz


def _dekoduj_csv(dane: bytes) -> str:
    for kodowanie in ("utf-8-sig", "cp1250"):
        try:
            return dane.decode(kodowanie)
        except UnicodeDecodeError:
            continue
    raise BladPliku("Nie udało się odczytać kodowania pliku CSV – zapisz go jako UTF-8.")


def _wczytaj_csv(dane: bytes) -> tuple[list[str], list[tuple[int, dict]], str]:
    tekst = _dekoduj_csv(dane)
    pierwsza = tekst.split("\n", 1)[0]
    sep = ";" if pierwsza.count(";") > pierwsza.count(",") else ","
    czytnik = csv.reader(io.StringIO(tekst, newline=""), delimiter=sep)
    try:
        naglowek = next(czytnik)
    except StopIteration:
        return [], [], "csv"
    naglowki = [h.strip() for h in naglowek]
    wynik: list[tuple[int, dict]] = []
    for nr, w in enumerate(czytnik, start=2):
        if nr - 1 > config.MAX_ROWS:
            raise BladPliku(f"Plik ma więcej niż {config.MAX_ROWS} wierszy – podziel go na mniejsze części.", 413)
        komorki = [_wartosc_komorki(c) for c in w]
        if all(c is None for c in komorki):
            continue
        wynik.append((nr, {h: komorki[i] if i < len(komorki) else None for i, h in enumerate(naglowki) if h}))
    return naglowki, wynik, "csv"


def wczytaj_plik(dane: bytes, nazwa_pliku: str) -> tuple[list[str], list[tuple[int, dict]], str]:
    """Zwraca (nagłówki, [(numer_wiersza, {kolumna: wartość|None})], nazwa_arkusza). Puste komórki = None."""
    if len(dane) > config.MAX_FILE_BYTES:
        raise BladPliku(f"Plik jest za duży ({len(dane) // 1024} KB). Maksymalny rozmiar to "
                        f"{config.MAX_FILE_BYTES // (1024 * 1024)} MB.", 413)
    if not dane:
        raise BladPliku("Plik jest pusty.")
    nazwa = (nazwa_pliku or "").lower()
    if nazwa.endswith(".xlsx"):
        return _wczytaj_xlsx(dane)
    if nazwa.endswith(".csv"):
        return _wczytaj_csv(dane)
    raise BladPliku("Dozwolone formaty plików odczytywalnych maszynowo: .xlsx lub .csv.", 400)


# ----------------------------------------------------------------------------- raport

@dataclass
class Raport:
    liczba_wierszy: int = 0
    poprawne_wiersze: int = 0
    bledne_wiersze: int = 0
    bledy: list[dict] = field(default_factory=list)
    ostrzezenia: list[dict] = field(default_factory=list)
    rekordy: list[dict] = field(default_factory=list)          # tylko poprawne, znormalizowane
    arkusz: str | None = None
    ucieto: bool = False

    def jako_dict(self) -> dict:
        """Raport w formacie z docs/API.md (+ pola dodatkowe: liczba_wierszy, arkusz, ucieto)."""
        return {
            "poprawne_wiersze": self.poprawne_wiersze,
            "bledne_wiersze": self.bledne_wiersze,
            "bledy": self.bledy,
            "ostrzezenia": self.ostrzezenia,
            "liczba_wierszy": self.liczba_wierszy,
            "arkusz": self.arkusz,
            "ucieto": self.ucieto,
        }


def waliduj_plik(dane: bytes, nazwa_pliku: str, nadpisania: dict | None = None) -> Raport:
    """Waliduje cały plik. `nadpisania` (np. pola dysponenta z formularza) zastępują kolumny pliku."""
    naglowki, wiersze, arkusz = wczytaj_plik(dane, nazwa_pliku)
    nadpisania = {k: v for k, v in (nadpisania or {}).items() if not _pusta(v)}
    raport = Raport(arkusz=arkusz if (nazwa_pliku or "").lower().endswith(".xlsx") else None)
    limit = config.MAX_RAPORT_POZYCJI

    def dodaj(lista: list, pozycja: dict):
        if len(lista) < limit:
            lista.append(pozycja)
        else:
            raport.ucieto = True

    if not wiersze:
        komunikat = ("Plik nie zawiera wierszy z danymi."
                     + (f" Wypełnij arkusz „{arkusz}” (przykłady są w arkuszu „Dane_przykladowe”)." if arkusz == "Dane" else ""))
        dodaj(raport.bledy, {"wiersz": 1, "pole": None, "kod": "required", "komunikat": komunikat})
        return raport

    znane = {p["name"] for p in schema.pola()}
    lower = {n.lower(): n for n in znane}
    # normalizacja nazw kolumn (wielkość liter, spacje)
    mapa_kolumn = {h: lower[h.lower()] for h in naglowki if h and h.lower() in lower}
    obecne = set(mapa_kolumn.values()) | set(nadpisania)
    for h in naglowki:
        if h and h not in mapa_kolumn:
            dodaj(raport.ostrzezenia, {"wiersz": 1, "pole": h, "kod": "pattern",
                                       "komunikat": f"Nieznana kolumna „{h}” – zostanie pominięta."})
    brak_wymaganych: set[str] = set()
    brak_zalecanych: set[str] = set()
    for p in schema.pola():
        if p["name"] in obecne:
            continue
        if p.get("x-wymagane") == "TAK":
            brak_wymaganych.add(p["name"])
            dodaj(raport.bledy, {"wiersz": 1, "pole": p["name"], "kod": "required",
                                 "komunikat": f"Brak kolumny „{p['name']}” ({p.get('title', '')}) – kolumna jest wymagana."})
        elif p.get("x-wymagane") == "ZALECANE":
            brak_zalecanych.add(p["name"])
            dodaj(raport.ostrzezenia, {"wiersz": 1, "pole": p["name"], "kod": "zalecane",
                                       "komunikat": f"Brak kolumny „{p['name']}” ({p.get('title', '')}) – zalecane uzupełnienie."})

    klucz = schema.klucz_glowny()
    widziane: dict[tuple, int] = {}
    nadpisane_roznice: dict[str, int] = {}
    raport.liczba_wierszy = len(wiersze)

    for nr, surowy in wiersze:
        wiersz = {mapa_kolumn[h]: v for h, v in surowy.items() if h in mapa_kolumn}
        for k, v in nadpisania.items():
            stary = wiersz.get(k)
            if not _pusta(stary) and _na_tekst(stary) != _na_tekst(v):
                nadpisane_roznice[k] = nadpisane_roznice.get(k, 0) + 1
            wiersz[k] = v
        rek, bledy, ostrz = waliduj_wiersz(wiersz, nr, pomin_wymagane=brak_wymaganych, pomin_zalecane=brak_zalecanych)

        if all(rek.get(k) is not None for k in klucz):
            k = tuple(rek[x] for x in klucz)
            if k in widziane:
                bledy.append({"wiersz": nr, "pole": "id_aed", "kod": "duplikat",
                              "komunikat": f"Powtórzony identyfikator AED „{rek.get('id_aed')}” dla tego dysponenta "
                                           f"(pierwszy raz w wierszu {widziane[k]}). Każde urządzenie musi mieć unikalne id_aed."})
            else:
                widziane[k] = nr

        for b in bledy:
            dodaj(raport.bledy, b)
        for o in ostrz:
            dodaj(raport.ostrzezenia, o)
        if bledy or brak_wymaganych:
            raport.bledne_wiersze += 1
        else:
            raport.poprawne_wiersze += 1
            raport.rekordy.append(rek)

    for k, ile in nadpisane_roznice.items():
        p = schema.pole(k)
        dodaj(raport.ostrzezenia, {"wiersz": 1, "pole": k, "kod": "pattern",
                                   "komunikat": f"W {ile} wierszach wartość pola „{p.get('title', k)}” z pliku różniła się od "
                                                "wartości z formularza – użyto wartości z formularza."})
    return raport
