"""Czyste funkcje pomocnicze dla adapterów źródeł (dane.gov.pl, OSM). Właściciel: API.

Bez sieci i bez bazy – wszystko tu jest testowalne na sucho.
"""
from __future__ import annotations

import hashlib
import html
import math
import re
import statistics
import unicodedata
from datetime import datetime, timezone

# Zasięg Polski (zgodny z ograniczeniami pól szerokosc_geo / dlugosc_geo w aed_schema.json).
LAT_MIN, LAT_MAX = 49.0, 54.9
LON_MIN, LON_MAX = 14.1, 24.2

_PUSTE = {"", "nan", "none", "null", "nat", "-", "brak", "brak danych", "n/d"}


def teraz_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tekst(v) -> str | None:
    """Wartość -> przycięty tekst albo None (puste, „nan”, „-” itp.)."""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return None
        v = str(int(v)) if v.is_integer() else repr(v)
    s = re.sub(r"\s+", " ", str(v)).strip()
    return None if s.lower() in _PUSTE else s


def liczba(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    s = tekst(v)
    if s is None:
        return None
    s = s.replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        f = float(s)
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def bez_html(s: str | None) -> str | None:
    if s is None:
        return None
    s = re.sub(r"<[^>]+>", " ", s)
    return tekst(html.unescape(s))


def klucz_kolumny(nazwa: str) -> str:
    """Normalizacja nazwy kolumny: małe litery, bez polskich znaków i spacji.

    ' Szerokość geograficzna' -> 'szerokosc_geograficzna'. Dzięki temu mapowania w
    mapowania_danegov.py są odporne na spacje wiodące, wielkość liter i ogonki.
    """
    s = unicodedata.normalize("NFKD", str(nazwa).replace("ł", "l").replace("Ł", "L"))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def stabilny_id(prefiks: str, *czesci) -> str:
    """Identyfikator niezależny od kolejności wierszy (dla źródeł bez własnego ID)."""
    h = hashlib.sha1("|".join(str(c or "") for c in czesci).encode("utf-8")).hexdigest()[:8]
    return f"{prefiks}-{h}"


def bezpieczny_id(s: str | None) -> str | None:
    """Dopasowanie do wzorca id_aed ^[A-Za-z0-9._\\-/]+$ (max 64 znaki)."""
    s = tekst(s)
    if s is None:
        return None
    s = re.sub(r"[^A-Za-z0-9._\-/]+", "-", s).strip("-")
    return s[:64] or None


# --------------------------------------------------------------------------- adresy

_CECHY = {"ulica": "ul.", "ul": "ul.", "aleja": "al.", "aleje": "al.", "al": "al.", "plac": "pl.", "pl": "pl.",
          "osiedle": "os.", "os": "os.", "rondo": "rondo", "skwer": "skwer", "bulwar": "bulw.", "wybrzeze": "wyb."}
_KOD = re.compile(r"(\d{2})\s*-\s*(\d{3})")
_NR = re.compile(r"^(?P<ulica>.*?\D)\s+(?P<nr>\d+[A-Za-z]?(?:\s*[/-]\s*\d+[A-Za-z]?)?)$")


def cecha_ulicy(cecha: str | None) -> str | None:
    c = tekst(cecha)
    if c is None:
        return None
    return _CECHY.get(klucz_kolumny(c), c)


def popraw_ulice(ulica: str | None, cecha: str | None = None) -> str | None:
    """'Al.. Piłsudskiego' -> 'al. Piłsudskiego'; cecha 'ulica' + 'Piłsudskiego' -> 'ul. Piłsudskiego'."""
    u = tekst(ulica)
    if u is None:
        return None
    u = re.sub(r"^(ul|al|pl|os)\.+\s*", lambda m: m.group(1).lower() + ". ", u, flags=re.I)
    c = cecha_ulicy(cecha)
    if c and not re.match(r"^(ul|al|pl|os|rondo|skwer|bulw|wyb)\b", u, re.I):
        u = f"{c} {u}"
    return u


def kod_pocztowy(s: str | None) -> str | None:
    s = tekst(s)
    if s is None:
        return None
    m = _KOD.search(s)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def rozbierz_adres(adres: str | None) -> dict:
    """'ul. Stanisława Wyspiańskiego 20, 38-400 Krosno' -> ulica / nr_budynku / kod_pocztowy / miejscowosc.

    Odporne na puste segmenty ('ul. X 4, , 38-400 Krosno') i brak numeru ('ul. Jasna, 38-400 Krosno').
    """
    wynik = {"ulica": None, "nr_budynku": None, "kod_pocztowy": None, "miejscowosc": None}
    a = tekst(adres)
    if not a:
        return wynik
    segmenty = [s.strip() for s in a.split(",") if s.strip()]
    reszta = []
    for seg in segmenty:
        m = _KOD.search(seg)
        if m and wynik["kod_pocztowy"] is None:
            wynik["kod_pocztowy"] = f"{m.group(1)}-{m.group(2)}"
            wynik["miejscowosc"] = tekst(seg[m.end():]) or wynik["miejscowosc"]
        else:
            reszta.append(seg)
    if reszta:
        pierwszy = reszta[0]
        m = _NR.match(pierwszy)
        if m:
            wynik["ulica"] = popraw_ulice(m.group("ulica"))
            wynik["nr_budynku"] = re.sub(r"\s+", "", m.group("nr"))
        else:
            wynik["ulica"] = popraw_ulice(pierwszy)
    return wynik


# --------------------------------------------------------------------------- współrzędne

def w_polsce(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def odleglosc_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# PUWG 1992 (EPSG:2180): odwzorowanie Gaussa-Krügera na elipsoidzie GRS80,
# południk osiowy 19°E, k0 = 0,9993, FE = 500 000 m, FN = -5 300 000 m.
_A = 6378137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_K0 = 0.9993
_LON0 = math.radians(19.0)
_FE, _FN = 500000.0, -5300000.0


def _luk_poludnika(phi: float) -> float:
    e2, e4, e6 = _E2, _E2 ** 2, _E2 ** 3
    return _A * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
                 - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                 + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi)
                 - (35 * e6 / 3072) * math.sin(6 * phi))


def wgs84_na_puwg1992(lat: float, lon: float) -> tuple[float, float]:
    """(lat, lon) -> (x = northing, y = easting). Używane głównie w testach (sprawdzenie w obie strony)."""
    phi, lam = math.radians(lat), math.radians(lon)
    n = _A / math.sqrt(1 - _E2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = _EP2 * math.cos(phi) ** 2
    a = (lam - _LON0) * math.cos(phi)
    m = _luk_poludnika(phi)
    y = _FE + _K0 * n * (a + (1 - t + c) * a ** 3 / 6 + (5 - 18 * t + t * t + 72 * c - 58 * _EP2) * a ** 5 / 120)
    x = _FN + _K0 * (m + n * math.tan(phi) * (a * a / 2 + (5 - t + 9 * c + 4 * c * c) * a ** 4 / 24
                                               + (61 - 58 * t + t * t + 600 * c - 330 * _EP2) * a ** 6 / 720))
    return x, y


def puwg1992_na_wgs84(x: float, y: float) -> tuple[float, float]:
    """EPSG:2180 (x = northing, y = easting) -> (lat, lon) WGS84. Dokładność ~1 cm (szereg Snydera)."""
    m = (x - _FN) / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    c1 = _EP2 * math.cos(phi1) ** 2
    t1 = math.tan(phi1) ** 2
    n1 = _A / math.sqrt(1 - _E2 * math.sin(phi1) ** 2)
    r1 = _A * (1 - _E2) / (1 - _E2 * math.sin(phi1) ** 2) ** 1.5
    d = (y - _FE) / (n1 * _K0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d * d / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * _EP2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * _EP2 - 3 * c1 * c1) * d ** 6 / 720)
    lon = _LON0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
                   + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * _EP2 + 24 * t1 * t1) * d ** 5 / 120) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)


def ustal_wspolrzedne(a, b, kolejnosc: str = "lat_lon") -> tuple[float | None, float | None, str | None]:
    """Rozpoznaje współrzędne w różnych formach -> (lat, lon, uwaga).

    * stopnie WGS84 w dowolnej kolejności – zakresy dla Polski się nie nakładają
      (szer. 49–54,9 vs dł. 14,1–24,2), więc zamianę kolumn wykrywamy jednoznacznie;
    * metry PUWG 1992 (EPSG:2180) – przeliczane do WGS84;
    * `kolejnosc` = deklaracja źródła ('lat_lon' albo 'lon_lat').
    `uwaga` != None oznacza, że coś poprawiono albo odrzucono (trafia do ostrzeżeń).
    """
    x, y = liczba(a), liczba(b)
    if x is None or y is None:
        return None, None, None
    lat, lon = (x, y) if kolejnosc == "lat_lon" else (y, x)
    if w_polsce(lat, lon):
        return round(lat, 7), round(lon, 7), None
    if w_polsce(lon, lat):
        return round(lon, 7), round(lat, 7), "zamienione kolumny szerokości i długości – poprawiono"
    if abs(x) > 1000 and abs(y) > 1000:
        for northing, easting in ((x, y), (y, x)):
            la, lo = puwg1992_na_wgs84(northing, easting)
            if w_polsce(la, lo):
                return round(la, 7), round(lo, 7), "współrzędne w PUWG 1992 (EPSG:2180) – przeliczono do WGS84"
        return None, None, f"współrzędne metryczne ({x}, {y}) w nieznanym układzie – pominięto"
    return None, None, f"współrzędne ({x}, {y}) poza Polską – pominięto"


def wspolrzedne_z_geometrii(geom) -> tuple[float | None, float | None, str | None]:
    """GeoJSON Point: [lon, lat]; toleruje zagnieżdżenie [[lon, lat]] (API m.st. Warszawy)."""
    if not isinstance(geom, dict):
        return None, None, None
    c = geom.get("coordinates")
    while isinstance(c, list) and c and isinstance(c[0], list):
        c = c[0]
    if not isinstance(c, list) or len(c) < 2:
        return None, None, None
    return ustal_wspolrzedne(c[0], c[1], kolejnosc="lon_lat")


def odrzuc_odstajace(rekordy: list[dict], prog_km: float = 25.0) -> list[str]:
    """Zeruje współrzędne punktów odległych o > prog_km od mediany zbioru (zbiory gminne).

    Przykład z życia: w zbiorze Marki (4955) jeden wiersz ma współrzędne skopiowane z Krosna
    (~270 km dalej). Błędna pinezka na mapie AED jest groźniejsza niż jej brak.
    """
    pkt = [(r["szerokosc_geo"], r["dlugosc_geo"]) for r in rekordy
           if r.get("szerokosc_geo") is not None and r.get("dlugosc_geo") is not None]
    if len(pkt) < 3:
        return []
    mlat = statistics.median(p[0] for p in pkt)
    mlon = statistics.median(p[1] for p in pkt)
    uwagi = []
    for r in rekordy:
        if r.get("szerokosc_geo") is None or r.get("dlugosc_geo") is None:
            continue
        d = odleglosc_m(mlat, mlon, r["szerokosc_geo"], r["dlugosc_geo"]) / 1000
        if d > prog_km:
            uwagi.append(f"AED {r.get('id_aed')}: współrzędne ({r['szerokosc_geo']}, {r['dlugosc_geo']}) "
                         f"leżą {d:.0f} km od pozostałych punktów zbioru – usunięto jako błędne.")
            r["szerokosc_geo"] = r["dlugosc_geo"] = None
    return uwagi


# --------------------------------------------------------------------------- godziny otwarcia

_DNI = [("pon", "Mo"), ("pn", "Mo"), ("wt", "Tu"), ("sr", "We"), ("czw", "Th"), ("pt", "Fr"), ("pia", "Fr"),
        ("sob", "Sa"), ("so", "Sa"), ("niedz", "Su"), ("nd", "Su")]
_GODZ = r"(\d{1,2})[:.](\d{2})"
_SEGMENT = re.compile(
    rf"^(?P<dni>[^\d:]+?)\s*:?\s*(?:godz\.?|w godz\.?)?\s*{_GODZ}\s*[-–]\s*{_GODZ}$", re.I)


def _dzien(s: str) -> str | None:
    k = klucz_kolumny(s)
    for prefiks, kod in _DNI:
        if k.startswith(prefiks):
            return kod
    return None


def godziny_pl_na_osm(opis: str | None) -> str | None:
    """'Poniedziałek: godz. 8:00-18:00; Wtorek-Piątek: godz. 8:00-16:00' -> 'Mo 08:00-18:00; Tu-Fr 08:00-16:00'.

    Zwraca None, gdy opisu nie da się przełożyć jednoznacznie (wtedy nie zgadujemy).
    """
    s = tekst(opis)
    if s is None:
        return None
    if re.search(r"24\s*/\s*7|24\s*h|całodob|calodob", s, re.I):
        return "24/7"
    wynik = []
    for seg in [x.strip() for x in re.split(r"[;\n]", s) if x.strip()]:
        m = _SEGMENT.match(seg)
        if not m:
            return None
        dni = [d.strip() for d in re.split(r"\s*[-–]\s*", m.group("dni").strip(" :,")) if d.strip()]
        kody = [_dzien(d) for d in dni]
        if not kody or None in kody or len(kody) > 2:
            return None
        g1, m1, g2, m2 = (int(m.group(i)) for i in (2, 3, 4, 5))
        wynik.append(f"{'-'.join(kody)} {g1:02d}:{m1:02d}-{g2:02d}:{m2:02d}")
    return "; ".join(wynik) or None


# --------------------------------------------------------------------------- identyfikatory

def regon_poprawny(s: str | None) -> bool:
    s = tekst(s)
    if not s or not s.isdigit() or len(s) not in (9, 14):
        return False
    wagi = [8, 9, 2, 3, 4, 5, 6, 7] if len(s) == 9 else [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
    k = sum(int(c) * w for c, w in zip(s, wagi)) % 11
    return (0 if k == 10 else k) == int(s[-1])


def nip_poprawny(s: str | None) -> bool:
    s = re.sub(r"\D", "", tekst(s) or "")
    if len(s) != 10:
        return False
    k = sum(int(c) * w for c, w in zip(s, [6, 5, 7, 2, 3, 4, 5, 6, 7])) % 11
    return k != 10 and k == int(s[-1])


def telefon(s: str | None) -> str | None:
    """'0048134743001' -> '+48134743001'; inne formaty zostawia (po przycięciu)."""
    s = tekst(s)
    if s is None:
        return None
    if re.fullmatch(r"0048\d{9}", s):
        return "+" + s[2:]
    return s
