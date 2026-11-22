"""Pobieranie AED z OpenStreetMap (Overpass API). Właściciel: API.

Dane OSM są społecznościowe i na licencji ODbL 1.0, dlatego:
  * status_weryfikacji = DO_WERYFIKACJI, status_urzadzenia = nieznany,
  * NIE trafiają do eksportu dla dane.gov.pl (harvester przyjmuje tylko CC0 / CC BY),
  * są dostępne osobno w /export/osm-odbl.geojson z atrybucją „© OpenStreetMap contributors”.
"""
from __future__ import annotations

import os
import re

from ..repo import Zrodlo
from .wspolne import bezpieczny_id, kod_pocztowy, popraw_ulice, tekst, teraz_utc_iso, ustal_wspolrzedne

DOMYSLNE_SERWERY = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
TIMEOUT_S = 30
LICENCJA = "ODbL 1.0"
ATRYBUCJA = "© OpenStreetMap contributors, ODbL 1.0"
MAKS_DL_NAZWY = 100


class BladOverpass(RuntimeError):
    """Overpass niedostępny / zła odpowiedź – czytelny komunikat dla użytkownika (HTTP 502)."""


class BladNazwy(BladOverpass):
    """Niepoprawna nazwa miejscowości (HTTP 422)."""


def serwery() -> list[str]:
    env = os.environ.get("OVERPASS_URL")
    return [u.strip() for u in env.split(",") if u.strip()] if env else list(DOMYSLNE_SERWERY)


def escapuj(miasto: str) -> str:
    """Bezpieczne wstawienie nazwy do literału Overpass QL ("...").

    Odrzuca znaki sterujące (w tym nowe linie – nimi dałoby się dokleić własne instrukcje),
    escapuje backslash i cudzysłów. Nawiasy, średniki itp. wewnątrz cudzysłowu są nieszkodliwe.
    """
    m = (miasto or "").strip()
    if not m:
        raise BladNazwy("Podaj nazwę miejscowości.")
    if len(m) > MAKS_DL_NAZWY:
        raise BladNazwy(f"Nazwa miejscowości jest za długa (maks. {MAKS_DL_NAZWY} znaków).")
    if re.search(r"[\x00-\x1f\x7f]", m):
        raise BladNazwy("Nazwa miejscowości zawiera niedozwolone znaki sterujące.")
    return m.replace("\\", "\\\\").replace('"', '\\"')


def zbuduj_zapytanie(miasto: str) -> str:
    nazwa = escapuj(miasto)
    return (
        f"[out:json][timeout:{TIMEOUT_S - 5}];\n"
        f'area["name"="{nazwa}"]["boundary"="administrative"]["admin_level"~"^(6|7|8)$"]->.obszar;\n'
        'nwr["emergency"="defibrillator"](area.obszar);\n'
        "out center meta;\n"
    )


def _tak_nie(v: str | None) -> str | None:
    v = (tekst(v) or "").lower()
    return "TAK" if v == "yes" else "NIE" if v == "no" else None


def normalizuj_elementy(elementy: list[dict], miasto: str, data_pobrania: str | None = None) -> tuple[list[dict], list[str]]:
    """Elementy Overpass -> rekordy wg aed_schema.json (czysta funkcja)."""
    from .. import schema

    data_pobrania = data_pobrania or teraz_utc_iso()
    pola = schema.nazwy_pol()
    rekordy, ostrzezenia, pominiete = [], [], 0
    for el in elementy:
        t = el.get("tags") or {}
        if t.get("emergency") != "defibrillator":
            continue
        c = el.get("center") or {}
        lat, lon, _ = ustal_wspolrzedne(el.get("lat", c.get("lat")), el.get("lon", c.get("lon")), "lat_lon")
        if lat is None:
            pominiete += 1
            continue
        typ, oid = el.get("type", "node"), el.get("id")
        r = {p: None for p in pola}

        godziny = tekst(t.get("opening_hours"))
        dostep = (tekst(t.get("access")) or "").lower()
        if dostep in ("private", "no", "customers", "permit"):
            dostepnosc = "ograniczona"
        elif godziny == "24/7":
            dostepnosc = "24_7"
        elif godziny:
            dostepnosc = "godziny_otwarcia"
        else:
            dostepnosc = None

        zamkniete = (tekst(t.get("locked")) or "").lower()
        czy_zamkniete, instrukcja = None, None
        if zamkniete == "no":
            czy_zamkniete = "NIE"
        elif zamkniete == "yes":
            # OSM nie mówi JAK jest zabezpieczone (klucz/kod/ochrona) – nie zgadujemy
            instrukcja = "Urządzenie zabezpieczone (OSM: locked=yes) – sposób dostępu do potwierdzenia."

        zdjecie = tekst(t.get("image"))
        r.update(
            id_aed=bezpieczny_id(f"OSM-{typ[0]}{oid}"),
            nazwa_dysponenta=tekst(t.get("operator")),
            kontakt_dysponenta=tekst(t.get("phone") or t.get("contact:phone") or t.get("email") or t.get("contact:email")),
            miejscowosc=tekst(t.get("addr:city")) or miasto.strip(),
            ulica=popraw_ulice(t.get("addr:street")),
            nr_budynku=tekst(t.get("addr:housenumber")),
            kod_pocztowy=kod_pocztowy(t.get("addr:postcode")),
            szerokosc_geo=lat,
            dlugosc_geo=lon,
            lokalizacja_szczegolowa=tekst(t.get("defibrillator:location") or t.get("defibrillator:location:pl")
                                          or t.get("description")),
            kondygnacja=tekst(t.get("level")),
            wewnatrz_budynku=_tak_nie(t.get("indoor")),
            dostepnosc_typ=dostepnosc,
            godziny_dostepnosci=godziny,
            czy_zamkniete=czy_zamkniete,
            instrukcja_dostepu=instrukcja,
            producent_model=tekst(" ".join(x for x in (t.get("manufacturer"), t.get("model")) if x)),
            zdjecie_url=zdjecie if zdjecie and zdjecie.startswith(("http://", "https://")) else None,
            status_urzadzenia="nieznany",
            data_aktualizacji=tekst(el.get("timestamp")) or data_pobrania,
            zrodlo_typ="OSM",
            zrodlo_nazwa=f"OpenStreetMap (Overpass API) – {miasto.strip()}",
            zrodlo_url=f"https://www.openstreetmap.org/{typ}/{oid}",
            licencja=LICENCJA,
            status_weryfikacji="DO_WERYFIKACJI",
            data_pobrania=data_pobrania,
        )
        rekordy.append(r)
    if pominiete:
        ostrzezenia.append(f"Pominięto {pominiete} element(ów) OSM bez współrzędnych w Polsce.")
    return rekordy, ostrzezenia


def zrodlo_dla(miasto: str) -> Zrodlo:
    m = miasto.strip()
    return Zrodlo(id=f"osm:{m}", typ="OSM", nazwa=f"OpenStreetMap – {m}",
                  url="https://www.openstreetmap.org/copyright", licencja=LICENCJA)


def pobierz(miasto: str, session=None) -> tuple[list[dict], list[str], int]:
    """-> (rekordy, ostrzeżenia, liczba elementów zwróconych przez Overpass). Rzuca BladOverpass."""
    import requests

    zapytanie = zbuduj_zapytanie(miasto)
    s = session or requests.Session()
    bledy = []
    for url in serwery():
        try:
            r = s.post(url, data={"data": zapytanie}, timeout=(5, TIMEOUT_S),
                       headers={"User-Agent": "TuBijeAED-integrator/0.1 (+hackathon prototype)"})
        except requests.Timeout:
            bledy.append(f"{url}: brak odpowiedzi w {TIMEOUT_S} s")
            continue
        except requests.RequestException as e:
            bledy.append(f"{url}: {e.__class__.__name__}")
            continue
        if r.status_code in (429, 502, 503, 504):
            bledy.append(f"{url}: serwer przeciążony (HTTP {r.status_code})")
            continue
        if r.status_code != 200:
            bledy.append(f"{url}: HTTP {r.status_code}")
            continue
        try:
            dane = r.json()
        except ValueError:
            bledy.append(f"{url}: odpowiedź nie jest JSON-em")
            continue
        elementy = dane.get("elements", [])
        rekordy, ostrz = normalizuj_elementy(elementy, miasto)
        if dane.get("remark"):
            ostrz.append(f"Overpass: {dane['remark']}")
        if not elementy:
            ostrz.append(f"Nie znaleziono AED w OSM dla „{miasto.strip()}” – sprawdź pisownię "
                         "(nazwa gminy/miasta jak na mapie, np. „Sosnowiec”).")
        return rekordy, ostrz, len(elementy)
    raise BladOverpass("Nie udało się pobrać danych z OpenStreetMap (Overpass API): " + "; ".join(bledy)
                       + ". Spróbuj ponownie za chwilę.")
