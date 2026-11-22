"""Import zbiorów o defibrylatorach AED z API dane.gov.pl (v1.4, JSON:API). Właściciel: API.

Przepływ (każdy krok to osobna, testowalna funkcja):
  wyszukaj_zbiory()  – /1.4/search?q=defibrylator|AED, odfiltrowanie fałszywych trafień
  przetworz_zbior()  – metadane zbioru + instytucji, wybór zasobu (geojson > csv > json > xlsx),
                       pobranie pliku, odczyt (czytniki.py), mapowanie (mapowania_danegov.py)
  normalizuj()       – CZYSTA funkcja: surowe wiersze -> rekordy wg aed_schema.json
  synchronizuj()     – wszystko razem; błąd jednego zbioru nie przerywa pozostałych.

Router (app/routers/sources.py) zapisuje wynik wyłącznie przez app.repo.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from ..repo import Zrodlo
from . import czytniki
from .mapowania_danegov import MAPOWANIA, SYNONIMY, TYP_INSTYTUCJI
from .wspolne import (bez_html, bezpieczny_id, godziny_pl_na_osm, klucz_kolumny, kod_pocztowy,
                      nip_poprawny, odrzuc_odstajace, popraw_ulice, regon_poprawny, rozbierz_adres,
                      stabilny_id, tekst, telefon, teraz_utc_iso, ustal_wspolrzedne,
                      wspolrzedne_z_geometrii)

API_URL = os.environ.get("DANE_GOV_API_URL", "https://api.dane.gov.pl/1.4")
PORTAL_URL = "https://dane.gov.pl/pl/dataset"
ZAPYTANIA = ("defibrylator", "AED")
# Tytuł zbioru/zasobu musi mówić o defibrylatorach. Opis nie wystarcza – np. „Baza pojazdów ZTM
# w Gdańsku” wspomina w opisie pole „defibrylator”, a „Wyniki badań” (zbiór 3072) skrót AED.
FILTR_TYTULU = re.compile(r"defibry[lz]|\bAED\b", re.I)
KOLEJNOSC_FORMATOW = ("geojson", "csv", "json", "xlsx")
OTWARTE_LICENCJE = {"CC0 1.0": "CC0 1.0", "CC BY 4.0": "CC BY 4.0", "CC0": "CC0 1.0", "CC-BY-4.0": "CC BY 4.0"}
MAKS_ROZMIAR = 20 * 1024 * 1024
POLA_SYSTEMOWE = ("zrodlo_typ", "zrodlo_nazwa", "zrodlo_url", "licencja", "status_weryfikacji", "data_pobrania")


class BladZrodla(RuntimeError):
    """Problem z pojedynczym zbiorem/zasobem (sieć, format, licencja)."""


# --------------------------------------------------------------------------- HTTP

class Klient:
    """Cienka warstwa HTTP (requests). W testach podmieniana na klienta czytającego fixture'y."""

    def __init__(self, timeout: tuple[float, float] = (5, 30), session=None):
        import requests
        self.timeout = timeout
        self.s = session or requests.Session()
        self.s.headers.update({"User-Agent": "TuBijeAED-integrator/0.1 (+hackathon prototype)"})

    def _zadanie(self, url, metoda="GET", params=None, headers=None):
        import requests
        try:
            r = self.s.request(metoda, url, params=params, headers=headers, timeout=self.timeout,
                               stream=True, allow_redirects=True)
        except requests.Timeout as e:
            raise BladZrodla(f"przekroczono czas oczekiwania ({self.timeout[1]} s): {url}") from e
        except requests.RequestException as e:
            raise BladZrodla(f"błąd połączenia: {url} ({e.__class__.__name__})") from e
        if r.status_code >= 400:
            raise BladZrodla(f"HTTP {r.status_code}: {url}")
        dane = r.raw.read(MAKS_ROZMIAR + 1, decode_content=True)
        if len(dane) > MAKS_ROZMIAR:
            raise BladZrodla(f"zasób większy niż {MAKS_ROZMIAR // 1024 // 1024} MB: {url}")
        return dane

    def json(self, url: str, params: dict | None = None) -> Any:
        import json
        dane = self._zadanie(url, params=params, headers={"Accept": "application/vnd.api+json, application/json"})
        try:
            return json.loads(dane.decode("utf-8"))
        except ValueError as e:
            raise BladZrodla(f"odpowiedź nie jest JSON-em: {url}") from e

    def bajty(self, url: str, metoda: str = "GET", headers: dict | None = None) -> bytes:
        return self._zadanie(url, metoda=metoda, headers=headers)


# --------------------------------------------------------------------------- wyniki

@dataclass
class WynikZbioru:
    zbior_id: str
    zrodlo: Zrodlo | None = None
    rekordy: list[dict] = field(default_factory=list)
    ostrzezenia: list[str] = field(default_factory=list)
    blad: str | None = None
    zasob_id: str | None = None
    format: str | None = None
    zasob_url: str | None = None


@dataclass
class WynikSynchronizacji:
    zbiory: list[WynikZbioru] = field(default_factory=list)
    ostrzezenia: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- wyszukiwanie

def _czysty_tytul(s: str | None) -> str:
    return bez_html(s) or ""   # API wstawia <mark>…</mark> wokół trafień


def wyszukaj_zbiory(klient, ostrzezenia: list[str] | None = None) -> dict[str, set[str] | None]:
    """Zwraca {id_zbioru: None (cały zbiór o AED) | {id_zasobu, ...} (tylko te zasoby)}."""
    ostrzezenia = ostrzezenia if ostrzezenia is not None else []
    wynik: dict[str, set[str] | None] = {}
    for q in ZAPYTANIA:
        try:
            odp = klient.json(f"{API_URL}/search", params={"q": q, "per_page": 100})
        except BladZrodla as e:
            ostrzezenia.append(f"Wyszukiwanie „{q}” nieudane: {e}")
            continue
        for hit in odp.get("data", []):
            a = hit.get("attributes", {})
            model = a.get("model") or hit.get("type")
            if not FILTR_TYTULU.search(_czysty_tytul(a.get("title"))):
                continue
            if model == "dataset":
                wynik[str(hit["id"])] = None
            elif model == "resource":
                ds = ((hit.get("relationships") or {}).get("dataset") or {}).get("data") or {}
                if not ds.get("id"):
                    continue
                ds_id = str(ds["id"])
                if ds_id in wynik and wynik[ds_id] is None:
                    continue
                wynik.setdefault(ds_id, set()).add(str(hit["id"]))
    return wynik


def wybierz_zasob(zasoby: list[dict], dozwolone: set[str] | None, konfig: dict | None) -> dict | None:
    """Najlepszy zasób zbioru: geojson > csv > json > xlsx (pliki maszynowe, z danymi tabelarycznymi)."""
    kandydaci = zasoby
    przypiete = (konfig or {}).get("zasoby")
    if przypiete:
        kandydaci = [z for z in zasoby if str(z["id"]) in przypiete]
    elif dozwolone:
        kandydaci = [z for z in zasoby if str(z["id"]) in dozwolone]
    else:
        pasujace = [z for z in zasoby if FILTR_TYTULU.search(_czysty_tytul(z["attributes"].get("title")))]
        kandydaci = pasujace or zasoby

    def ranga(z):
        f = (z["attributes"].get("format") or "").lower()
        return KOLEJNOSC_FORMATOW.index(f) if f in KOLEJNOSC_FORMATOW else len(KOLEJNOSC_FORMATOW)

    kandydaci = [z for z in kandydaci if ranga(z) < len(KOLEJNOSC_FORMATOW)]
    return min(kandydaci, key=ranga) if kandydaci else None


# --------------------------------------------------------------------------- normalizacja

def _indeks_kolumn(wiersz: dict) -> dict[str, str]:
    return {klucz_kolumny(k): k for k in wiersz if k != "_geometria"}


def _ustal_mapowanie(wiersze: list[dict], konfig: dict | None) -> tuple[dict[str, str], list[str]]:
    """Zwraca {pole: nazwa_kolumny_w_wierszu} + ostrzeżenia o brakujących kolumnach."""
    if not wiersze:
        return {}, []
    indeks = _indeks_kolumn(wiersze[0])
    uwagi = []
    mapa: dict[str, str] = {}
    if konfig and konfig.get("kolumny"):
        for pole, kolumna in konfig["kolumny"].items():
            k = indeks.get(klucz_kolumny(kolumna))
            if k is None:
                uwagi.append(f"Brak kolumny „{kolumna}” (dla pola {pole}) – źródło zmieniło strukturę?")
            else:
                mapa[pole] = k
    else:
        for pole, synonimy in SYNONIMY.items():
            for s in synonimy:
                if s in indeks and indeks[s] not in mapa.values():
                    mapa[pole] = indeks[s]
                    break
        uwagi.append("Brak dedykowanego mapowania – kolumny dopasowano heurystycznie: "
                     + ", ".join(f"{k}←{v}" for k, v in mapa.items()))
    return mapa, uwagi


_PREFIKS_NAZWY = re.compile(r"^\s*defibrylator\w*\s*(\(\s*AED\s*\d*\s*\))?\s*[-–:]?\s*(w\s+)?", re.I)


def _czysta_nazwa_obiektu(s: str | None) -> str | None:
    """'Defibrylator (AED 9485) w ADM Centrum' -> 'ADM Centrum'; 'Defibrylator' -> None."""
    s = tekst(s)
    if s is None:
        return None
    oczyszczona = tekst(_PREFIKS_NAZWY.sub("", s))
    return oczyszczona if oczyszczona else (None if s.lower().startswith("defibrylator") else s)


def _dostepnosc(opis: str | None, publiczny: str | None, godziny: str | None) -> str | None:
    o, p = (tekst(opis) or "").lower(), (tekst(publiczny) or "").lower()
    if p.startswith("niepubl") or "ograniczony" in p:
        return "ograniczona"
    if re.search(r"ca[łl]odob|24\s*(/\s*7|h\b)", o) or godziny == "24/7":
        return "24_7"
    if o or godziny:
        return "godziny_otwarcia"
    return None


def _polozenie(s: str | None) -> str | None:
    s = (tekst(s) or "").lower()
    if "wewn" in s:
        return "TAK"
    if "zewn" in s:
        return "NIE"
    return None


def _pierwsze_zdjecie(galeria) -> str | None:
    if isinstance(galeria, list):
        for g in galeria:
            url = g.get("url") if isinstance(g, dict) else g
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                return url
    return None


def _dysponent(instytucja: dict, ostrzezenia: list[str]) -> dict:
    a = (instytucja or {}).get("attributes", {})
    nazwa = tekst(a.get("title"))
    ident = None
    for kandydat, test, opis in ((a.get("nip"), nip_poprawny, "NIP"), (a.get("regon"), regon_poprawny, "REGON")):
        k = re.sub(r"\D", "", tekst(kandydat) or "")
        if k and test(k):
            ident = k
            break
        if k:
            ostrzezenia.append(f"{opis} instytucji „{nazwa}” ({k}) ma niepoprawną sumę kontrolną – pominięto.")
    if ident is None:
        ostrzezenia.append(f"API dane.gov.pl nie zwróciło NIP ani poprawnego REGON instytucji „{nazwa}” "
                           "– identyfikator_dysponenta pusty.")
    typ = TYP_INSTYTUCJI.get(a.get("institution_type") or "")
    if typ is None:
        ostrzezenia.append(f"Nieznany typ instytucji „{a.get('institution_type')}” – typ_dysponenta pusty.")
    kontakt = tekst(a.get("email")) or telefon(a.get("tel"))
    return {"nazwa_dysponenta": nazwa, "identyfikator_dysponenta": ident, "typ_dysponenta": typ,
            "kontakt_dysponenta": kontakt}


def normalizuj(
    wiersze: list[dict], *, zbior: dict, instytucja: dict, zasob: dict | None, konfig: dict | None,
    data_pobrania: str | None = None,
) -> tuple[list[dict], list[str]]:
    """Surowe wiersze jednego zasobu -> rekordy zgodne z aed_schema.json (pola fields + systemowe).

    Brakujące pola = None. Nie zgadujemy wartości, których źródło nie podaje (np. czy_zamkniete).
    """
    from .. import schema   # lista pól wprost z aed_schema.json (jedno źródło prawdy)

    ostrzezenia: list[str] = []
    data_pobrania = data_pobrania or teraz_utc_iso()
    za = zbior.get("attributes", {})
    zbior_id = str(zbior.get("id"))
    licencja = OTWARTE_LICENCJE.get(tekst(za.get("license_name")) or "")
    if licencja is None:
        raise BladZrodla(f"licencja zbioru „{za.get('license_name')}” spoza CC0 1.0 / CC BY 4.0 – pominięto zbiór")
    dysponent = _dysponent(instytucja, ostrzezenia)
    obszar = (konfig or {}).get("obszar", {})
    stale = (konfig or {}).get("stale", {})
    prefiks = (konfig or {}).get("prefiks_id") or f"DGP{zbior_id}"
    zasob_attr = (zasob or {}).get("attributes", {})
    data_aktualizacji = tekst(zasob_attr.get("modified")) or tekst(za.get("modified"))
    zrodlo_nazwa = f"{dysponent['nazwa_dysponenta'] or 'dane.gov.pl'} – dane.gov.pl, zbiór {zbior_id}"
    zrodlo_url = f"{PORTAL_URL}/{zbior_id},{za.get('slug') or ''}".rstrip(",")

    mapa, uwagi = _ustal_mapowanie(wiersze, konfig)
    ostrzezenia += uwagi
    pola = schema.nazwy_pol()

    def v(wiersz, pole):
        k = mapa.get(pole)
        return wiersz.get(k) if k else None

    rekordy, uzyte_id = [], set()
    uwagi_wsp: dict[str, list[str]] = {}   # ta sama uwaga dla wielu wierszy -> jedno ostrzeżenie
    for nr, w in enumerate(wiersze, start=2):
        r = {p: None for p in pola}
        r.update({k: obszar.get(k) for k in ("wojewodztwo", "powiat", "gmina", "teryt_gmina", "miejscowosc")})
        r.update(dysponent)

        # adres
        if "_adres" in mapa:
            adr = rozbierz_adres(v(w, "_adres"))
            r.update({k: x for k, x in adr.items() if x})
        cecha = tekst(v(w, "_cecha_ulicy"))
        if tekst(v(w, "ulica")):
            r["ulica"] = popraw_ulice(v(w, "ulica"), cecha)
        if tekst(v(w, "nr_budynku")):
            r["nr_budynku"] = tekst(v(w, "nr_budynku"))
        if v(w, "kod_pocztowy") is not None:
            r["kod_pocztowy"] = kod_pocztowy(v(w, "kod_pocztowy")) or r["kod_pocztowy"]
        r["miejscowosc"] = tekst(v(w, "miejscowosc")) or r["miejscowosc"]
        for pole in ("simc", "teryt_gmina"):
            x = tekst(v(w, pole))
            if x and re.fullmatch(r"\d{7}", x):
                r[pole] = x

        # współrzędne: geometria GeoJSON albo kolumny
        if w.get("_geometria") is not None and not ("szerokosc_geo" in mapa and "dlugosc_geo" in mapa):
            lat, lon, uwaga = wspolrzedne_z_geometrii(w["_geometria"])
        else:
            lat, lon, uwaga = ustal_wspolrzedne(v(w, "szerokosc_geo"), v(w, "dlugosc_geo"), "lat_lon")
        r["szerokosc_geo"], r["dlugosc_geo"] = lat, lon

        # opis miejsca
        obiekt = _czysta_nazwa_obiektu(v(w, "_nazwa_obiektu"))
        opis = tekst(v(w, "lokalizacja_szczegolowa"))
        r["lokalizacja_szczegolowa"] = " – ".join(x for x in (obiekt, opis) if x) or None

        # dostępność
        godz_opis = v(w, "_godziny_opis")
        godziny = tekst(v(w, "godziny_dostepnosci")) or godziny_pl_na_osm(godz_opis)
        if godz_opis and godziny is None:
            ostrzezenia.append(f"Wiersz {nr}: nie przełożono godzin „{tekst(godz_opis)}” na format OSM.")
        r["godziny_dostepnosci"] = godziny
        r["dostepnosc_typ"] = _dostepnosc(v(w, "_dostepnosc_opis"), v(w, "_dostep_publiczny"), godziny) \
            if ("_dostepnosc_opis" in mapa or godziny) else None
        r["wewnatrz_budynku"] = _polozenie(v(w, "_polozenie"))
        r["producent_model"] = tekst(v(w, "producent_model"))
        r["zdjecie_url"] = _pierwsze_zdjecie(v(w, "_zdjecia"))

        kontakt = tekst(v(w, "_telefon")) or tekst(v(w, "_email"))
        if kontakt:
            r["kontakt_dysponenta"] = telefon(kontakt)

        # identyfikator urządzenia
        id_aed = bezpieczny_id(v(w, "id_aed"))
        if id_aed is None:
            id_aed = stabilny_id(prefiks, r["lokalizacja_szczegolowa"], r["ulica"], r["nr_budynku"], lat, lon)
        if id_aed in uzyte_id:
            ostrzezenia.append(f"Wiersz {nr}: powtórzony identyfikator „{id_aed}” – dodano sufiks.")
            id_aed = f"{id_aed}-{nr}"
        uzyte_id.add(id_aed)
        r["id_aed"] = id_aed
        if uwaga:
            uwagi_wsp.setdefault(uwaga, []).append(id_aed)

        r.update(stale)
        r["data_aktualizacji"] = data_aktualizacji
        r.update(zrodlo_typ="DANE_GOV_PL", zrodlo_nazwa=zrodlo_nazwa, zrodlo_url=zrodlo_url, licencja=licencja,
                 status_weryfikacji="ZWERYFIKOWANY_DANE_GOV_PL", data_pobrania=data_pobrania)
        rekordy.append(r)

    for uwaga, ids in uwagi_wsp.items():
        lista = ", ".join(ids[:10]) + (" …" if len(ids) > 10 else "")
        ostrzezenia.append(f"Współrzędne: {uwaga} ({len(ids)} rek.: AED {lista}).")
    ostrzezenia += odrzuc_odstajace(rekordy)
    bez = sum(1 for r in rekordy if r["szerokosc_geo"] is None)
    if bez:
        ostrzezenia.append(f"{bez} rekord(ów) bez poprawnych współrzędnych – nie pojawią się na mapie.")
    return rekordy, ostrzezenia


# --------------------------------------------------------------------------- jeden zbiór

def _pobierz_dane_zasobu(klient, zasob: dict | None, konfig: dict | None) -> tuple[bytes, str, str]:
    """-> (bajty, format, url). Obsługuje nadpisanie źródła pobierania z konfiguracji (Warszawa)."""
    pob = (konfig or {}).get("pobieranie")
    if pob:
        token = os.environ.get(pob.get("token_env", ""), "")
        if pob.get("token_env") and not token:
            raise BladZrodla(
                f"dane zbioru są w zewnętrznym API ({pob['url']}), które wymaga tokena – "
                f"ustaw zmienną środowiskową {pob['token_env']} (bezpłatna rejestracja u wydawcy)")
        naglowki = {"Authorization": token} if token else None
        return klient.bajty(pob["url"], metoda=pob.get("metoda", "GET"), headers=naglowki), pob["format"], pob["url"]
    if zasob is None:
        raise BladZrodla("brak zasobu w obsługiwanym formacie (geojson/csv/json/xlsx)")
    a = zasob["attributes"]
    # Najpierw kopia pliku w dane.gov.pl (to ją „zweryfikował” portal), potem oryginał u wydawcy.
    adresy = list(dict.fromkeys(u for u in (a.get("file_url"), a.get("link"), a.get("download_url")) if u))
    if not adresy:
        raise BladZrodla(f"zasób {zasob['id']} nie ma adresu pliku")
    bledy = []
    for url in adresy:
        try:
            return klient.bajty(url), (a.get("format") or "").lower(), url
        except BladZrodla as e:
            bledy.append(str(e))
    raise BladZrodla("; ".join(bledy))


def przetworz_zbior(klient, zbior_id: str, dozwolone_zasoby: set[str] | None = None,
                    data_pobrania: str | None = None) -> WynikZbioru:
    wynik = WynikZbioru(zbior_id=str(zbior_id))
    konfig = MAPOWANIA.get(str(zbior_id))
    try:
        zbior = klient.json(f"{API_URL}/datasets/{zbior_id}")["data"]
        za = zbior["attributes"]
        inst_id = (((zbior.get("relationships") or {}).get("institution") or {}).get("data") or {}).get("id")
        instytucja = {}
        if inst_id:
            try:
                instytucja = klient.json(f"{API_URL}/institutions/{inst_id}")["data"]
            except BladZrodla as e:
                wynik.ostrzezenia.append(f"Nie pobrano danych instytucji {inst_id}: {e}")
        zasoby = klient.json(f"{API_URL}/datasets/{zbior_id}/resources", params={"per_page": 100}).get("data", [])
        zasob = wybierz_zasob(zasoby, dozwolone_zasoby, konfig)
        licencja = OTWARTE_LICENCJE.get(tekst(za.get("license_name")) or "")
        nazwa_inst = tekst(instytucja.get("attributes", {}).get("title")) if instytucja else None
        wynik.zrodlo = Zrodlo(
            id=f"dane-gov-pl:{zbior_id}", typ="DANE_GOV_PL",
            nazwa=f"{nazwa_inst or _czysty_tytul(za.get('title'))} – dane.gov.pl, zbiór {zbior_id}",
            url=f"{PORTAL_URL}/{zbior_id},{za.get('slug') or ''}".rstrip(","),
            licencja=licencja or str(za.get("license_name")))
        if zasob is not None:
            wynik.zasob_id = str(zasob["id"])
        dane, fmt, url = _pobierz_dane_zasobu(klient, zasob, konfig)
        wynik.format, wynik.zasob_url = fmt, url
        try:
            wiersze = czytniki.czytaj(dane, fmt)
        except czytniki.BladFormatu as e:
            raise BladZrodla(f"nie można odczytać zasobu ({fmt}): {e}") from e
        if not wiersze:
            raise BladZrodla("zasób nie zawiera żadnych wierszy")
        rekordy, uwagi = normalizuj(wiersze, zbior=zbior, instytucja=instytucja, zasob=zasob, konfig=konfig,
                                    data_pobrania=data_pobrania)
        wynik.rekordy = rekordy
        wynik.ostrzezenia += uwagi
    except BladZrodla as e:
        wynik.blad = str(e)
    except (KeyError, TypeError, ValueError) as e:   # nieoczekiwana struktura odpowiedzi
        wynik.blad = f"nieoczekiwana struktura danych: {e.__class__.__name__}: {e}"
    return wynik


def synchronizuj(klient=None, data_pobrania: str | None = None) -> WynikSynchronizacji:
    """Pełna synchronizacja: wyszukane zbiory ∪ zbiory ze skonfigurowanym mapowaniem."""
    klient = klient or Klient()
    data_pobrania = data_pobrania or teraz_utc_iso()
    wynik = WynikSynchronizacji()
    znalezione = wyszukaj_zbiory(klient, wynik.ostrzezenia)
    for zid in MAPOWANIA:
        if zid not in znalezione:
            znalezione[zid] = None
            wynik.ostrzezenia.append(f"Zbiór {zid} ({MAPOWANIA[zid]['nazwa']}) nie pojawił się w wyszukiwarce "
                                     "– pobrano wg konfiguracji.")
    for zid in sorted(znalezione, key=int):
        wynik.zbiory.append(przetworz_zbior(klient, zid, znalezione[zid], data_pobrania))
    return wynik
