"""Prezentacja #TuBijeAED (PDF + PPTX) – jedno źródło slajdów, dwa renderery.

Uruchomienie (z katalogu repo):
    .venv/bin/python 4_prezentacja/generuj_prezentacje.py
Wejście:  4_prezentacja/zrzuty/*.png (+ kadry.json, terminal.json) – patrz README.md,
          3_branding/teksty_marki.py (hasło i teksty marki), 3_branding/* (logo, zastosowania),
          fonty Poppins z 3_branding/koncepcje/fonts/.
Wynik:    4_prezentacja/TuBijeAED_prezentacja.pdf (wektorowy tekst, osadzone fonty),
          4_prezentacja/TuBijeAED_prezentacja.pptx (edytowalny tekst + obrazy),
          4_prezentacja/zrzuty/kadry/*.png (wykadrowane fragmenty zrzutów).
"""
import json
import os
import re
import sys
from xml.sax.saxutils import escape

from PIL import Image

TU = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TU)
sys.path.insert(0, os.path.join(REPO, "3_branding"))
import teksty_marki as TM  # noqa: E402  (hasło i teksty marki – jedno źródło)

# ====================================================================== DO UZUPEŁNIENIA PRZEZ ZESPÓŁ
ZESPOL = "[nazwa zespołu]"
# ======================================================================

ZRZUTY = os.path.join(TU, "zrzuty")
KADRY_DIR = os.path.join(ZRZUTY, "kadry")
FONTY = os.path.join(REPO, "3_branding", "koncepcje", "fonts")
BRAND = os.path.join(REPO, "3_branding")
STATIC_BRAND = os.path.join(REPO, "2_prototyp_kod", "static", "brand")
PDF_OUT = os.path.join(TU, "TuBijeAED_prezentacja.pdf")
PPTX_OUT = os.path.join(TU, "TuBijeAED_prezentacja.pptx")

W, H = 960.0, 540.0          # pt, 16:9 (13,333 × 7,5 cala)
M = 40.0                     # margines

# tokeny kolorów (2_prototyp_kod/static/brand/tokens.css)
GRANAT = "#0B2545"
ZIELEN = "#00843D"
ZIELEN_C = "#006A31"
MIETA = "#E8F5EE"
AKCENT = "#5FD38D"           # tylko na granacie
SZARY = "#4A5568"
SZARY_NA_C = "#C5D3E0"
ALARM = "#D90429"
TLO_ALARM = "#FDECEE"
OSTRZ = "#8A5A00"
TLO_OSTRZ = "#FFF6E0"
RAMKA = "#CBD5E0"
BIALY = "#FFFFFF"

WAGI = {"R": "Poppins-Regular", "M": "Poppins-Medium", "S": "Poppins-SemiBold", "B": "Poppins-Bold",
        "X": "Poppins-ExtraBold"}
# nazwy rodzin w PowerPoint (font zainstalowany w systemie)
WAGI_PPTX = {"R": ("Poppins", False), "M": ("Poppins Medium", False), "S": ("Poppins SemiBold", False),
             "B": ("Poppins", True), "X": ("Poppins ExtraBold", False)}


# ---------------------------------------------------------------------- elementy slajdu
class Tekst:
    def __init__(self, x, y, w, h, akapity, r=18, kolor=GRANAT, waga="R", wyr="L", punktory=False,
                 interlinia=1.3, odstep=0.35, nazwa=None):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.akapity = [akapity] if isinstance(akapity, str) else list(akapity)
        self.r, self.kolor, self.waga, self.wyr = r, kolor, waga, wyr
        self.punktory, self.interlinia, self.odstep, self.nazwa = punktory, interlinia, odstep, nazwa


class Prost:
    def __init__(self, x, y, w, h, wypelnienie=None, obrys=None, promien=8, grubosc=1.0, kreska=False):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.wypelnienie, self.obrys, self.promien, self.grubosc, self.kreska = wypelnienie, obrys, promien, grubosc, kreska


class Strzalka:
    """Strzałka w prawo (blokowa) wpisana w prostokąt."""

    def __init__(self, x, y, w, h, kolor=ZIELEN):
        self.x, self.y, self.w, self.h, self.kolor = x, y, w, h, kolor


class Obraz:
    """Obraz dopasowany do pola (proporcje zachowane), wyrównanie: góra-środek; opcjonalna ramka."""

    def __init__(self, x, y, w, h, plik, ramka=True, wyr="C", alt=""):
        self.plik, self.ramka, self.alt = plik, ramka, alt
        iw, ih = Image.open(plik).size
        s = min(w / iw, h / ih)
        self.w, self.h = iw * s, ih * s
        self.x = x + ((w - self.w) / 2 if wyr == "C" else (w - self.w if wyr == "R" else 0))
        self.y = y


class Svg:
    """Grafika wektorowa (PDF: svglib), w PPTX zastępowana PNG."""

    def __init__(self, x, y, w, h, svg, png):
        self.svg, self.png = svg, png
        iw, ih = Image.open(png).size
        s = min(w / iw, h / ih)
        self.w, self.h = iw * s, ih * s
        self.x, self.y = x, y


class Slajd:
    def __init__(self, tytul, tlo=BIALY, notatka=""):
        self.tytul, self.tlo, self.notatka = tytul, tlo, notatka
        self.el = []

    def add(self, *e):
        self.el.extend(e)
        return self


# ---------------------------------------------------------------------- kadry zrzutów
def kadry_json():
    p = os.path.join(ZRZUTY, "kadry.json")
    return json.load(open(p)) if os.path.exists(p) else {}


DPR = 1


def wytnij(nazwa, zrodlo, box, skala=None):
    """Wycina fragment zrzutu (x0, y0, x1, y1 w px CSS) → zrzuty/kadry/<nazwa>.png."""
    os.makedirs(KADRY_DIR, exist_ok=True)
    im = Image.open(os.path.join(ZRZUTY, zrodlo)).convert("RGB")
    x0, y0, x1, y1 = [int(v * DPR) for v in box]
    x1, y1 = min(x1, im.width), min(y1, im.height)
    k = im.crop((x0, y0, x1, y1))
    if skala:
        k = k.resize((int(k.width * skala), int(k.height * skala)), Image.LANCZOS)
    out = os.path.join(KADRY_DIR, nazwa + ".png")
    k.save(out, optimize=True)
    return out


def przygotuj_kadry():
    global DPR
    K = kadry_json()
    DPR = K.get("_dpr", 1)

    def r(z, css, dom):
        return K.get(z, {}).get(css, dom)

    k = {}
    zw = r("03_dostawca_bledy", "#zasob-wynik", [74, 2763, 1120, 1264])
    k["bledy"] = wytnij("bledy", "03_dostawca_bledy.png", (64, zw[1] - 4, 1204, zw[1] + 878))
    zw = r("04_dostawca_poprawny", "#zasob-wynik", [74, 2677, 1120, 408])
    k["poprawny"] = wytnij("poprawny", "04_dostawca_poprawny.png", (64, zw[1] - 4, 1204, zw[1] + zw[3] + 6))
    hs = r("04b_wykaz_po", "#h-stan", [74, 339, 1120, 44])
    ds = r("04b_wykaz_po", "#sekcja-dostawcy", [74, 593, 1120, 576])
    k["wykaz_po_stan"] = wytnij("wykaz_po_stan", "04b_wykaz_po.png", (64, hs[1] - 6, 1204, hs[1] + 170))
    k["wykaz_po_dostawcy"] = wytnij("wykaz_po_dostawcy", "04b_wykaz_po.png", (100, ds[1] + 205, 1170, ds[1] + ds[3] - 30))
    hx = r("05_harvester_xml", "#sekcja-harvester", [74, 2685, 1120, 510])
    k["xml"] = wytnij("xml", "05_harvester_xml.png", (64, hx[1] + 348, 1204, hx[1] + hx[3] + 4))
    zb = r("05_harvester_xml", "#sekcja-zbiory", [74, 480, 1120, 438])
    k["xml_zbiory"] = wytnij("xml_zbiory", "05_harvester_xml.png", (64, zb[1] + 60, 1204, zb[1] + zb[3] + 4))
    fk = r("12_asystent_konwersja", "#form-konwertuj", [74, 976, 1120, 460])
    kw = r("12_asystent_konwersja", "#konwertuj-wynik", [74, 1440, 1120, 5339])
    k["asystent"] = wytnij("asystent", "12_asystent_konwersja.png", (64, kw[1] - 4, 1204, kw[1] + 600))
    sa = r("06_admin_historia", "#sekcja-admin", [74, 480, 1120, 2249])
    k["admin"] = wytnij("admin", "06_admin_historia.png", (64, sa[1] - 4, 1204, sa[1] + 975))
    sp = r("01_wykaz", "#sekcja-pominiete", [74, 3218, 1120, 397])
    k["pominiete"] = wytnij("pominiete", "01_wykaz.png", (64, sp[1] - 4, 1204, sp[1] + sp[3] + 4))
    nw = r("07_mapa_desktop", "#najblizsze-wynik", [74, 691, 1120, 1395])
    k["mapa_karta"] = wytnij("mapa_karta", "07_mapa_desktop.png", (64, nw[1] - 4, 1204, nw[1] + 490))
    mp = r("07_mapa_desktop", "#mapa", [74, 2185, 736, 468])
    k["mapa_mapa"] = wytnij("mapa_mapa", "07_mapa_desktop.png", (64, mp[1] - 50, 1204, mp[1] + mp[3] + 4))
    k["mob_gora"] = wytnij("mob_gora", "08_mapa_mobile.png", (0, 0, 390, 780))
    k["partner"] = wytnij("partner", "11_partner_aktywny.png", (64, 160, 1204, 470))
    k["partner_wygasly"] = wytnij("partner_wygasly", "11b_partner_wygasly.png", (64, 160, 1204, 470))
    k["api_json"] = wytnij("api_json", "09_api_json.png", (0, 50, 720, 620))
    dk = r("10_api_docs", "api14", [28, 1177, 1212, 650])
    k["api_docs"] = wytnij("api_docs", "10_api_docs.png", (dk[0] - 6, dk[1] - 4, dk[0] + dk[2] + 6, dk[1] + dk[3] + 4))
    od = os.path.join(BRAND, "final", "podglad", "odznaki.png")
    im = Image.open(od).convert("RGB")
    for n, b in (("odznaka_aktywna", (6, 6, 414, 134)), ("odznaka_wygasla", (6, 346, 414, 474))):
        im.crop(b).save(os.path.join(KADRY_DIR, n + ".png"))
        k[n] = os.path.join(KADRY_DIR, n + ".png")
    for n in ("20_xmllint", "21_pytest", "22_axe"):
        k[n] = os.path.join(ZRZUTY, n + ".png")
    return k


# ---------------------------------------------------------------------- budowa slajdów
def naglowek(s, nr, n, tytul, ciemny=False):
    kol = BIALY if ciemny else GRANAT
    s.add(Tekst(M, 26, W - 2 * M - 60, 44, tytul, r=28, waga="B", kolor=kol, interlinia=1.15))
    s.add(Prost(M, 74, 56, 5, wypelnienie=AKCENT if ciemny else ZIELEN, promien=2))
    sv = "logotyp_tubijeaed_sygnet"
    if not ciemny:
        s.add(Svg(W - M - 34, 24, 34, 34, os.path.join(BRAND, sv + ".svg"), os.path.join(BRAND, sv + ".png")))
    s.add(Tekst(M, H - 26, 600, 18, f"{TM.NAZWA} · HackNation 2026 · Misja AED – Dane na ratunek", r=11,
                kolor=SZARY_NA_C if ciemny else SZARY))
    s.add(Tekst(W - M - 80, H - 26, 80, 18, f"{nr} / {n}", r=11, kolor=SZARY_NA_C if ciemny else SZARY, wyr="R"))


def podpis(s, x, y, w, h, tekst, tytul="Co widać na zrzucie"):
    """Ramka „co widać na zrzucie” (mięta, zielona krawędź)."""
    s.add(Prost(x, y, w, h, wypelnienie=MIETA, promien=8))
    s.add(Prost(x, y, 5, h, wypelnienie=ZIELEN, promien=2))
    s.add(Tekst(x + 16, y + 10, w - 26, 26, tytul, r=18, waga="S", kolor=ZIELEN_C))
    s.add(Tekst(x + 16, y + 38, w - 26, h - 44, tekst, r=18, interlinia=1.25))


def karta(s, x, y, w, h, tytul, tekst, r=18, kolor_tytulu=GRANAT, tlo=BIALY, obrys=RAMKA, akcent=ZIELEN):
    s.add(Prost(x, y, w, h, wypelnienie=tlo, obrys=obrys, promien=10))
    if akcent:
        s.add(Prost(x, y, w, 5, wypelnienie=akcent, promien=2))
    s.add(Tekst(x + 14, y + 14, w - 28, 30, tytul, r=r + 2, waga="B", kolor=kolor_tytulu, interlinia=1.15))
    s.add(Tekst(x + 14, y + 48, w - 28, h - 56, tekst, r=r, interlinia=1.25))


def zbuduj(k, term):
    S = []
    testy = term.get("pytest_passed") or 0

    # 1 ------------------------------------------------------------------ tytuł
    s = Slajd("Tytuł", tlo=GRANAT)
    neg = "logotyp_tubijeaed_poziomy_negatyw"
    s.add(Svg(M + 10, 50, 330, 103, os.path.join(BRAND, neg + ".svg"), os.path.join(BRAND, neg + ".png")))
    s.add(Tekst(M + 20, 190, 860, 110, f"{TM.NAZWA} – Wykaz zbiorczy defibrylatorów AED w dane.gov.pl",
                r=40, waga="B", kolor=BIALY, interlinia=1.15))
    s.add(Prost(M + 20, 312, 70, 6, wypelnienie=AKCENT, promien=2))
    s.add(Tekst(M + 20, 334, 860, 44, f"„{TM.HASLO}”", r=30, waga="S", kolor=AKCENT))
    s.add(Tekst(M + 20, 384, 700, 60, TM.HASLO_PODTYTUL, r=18, kolor=SZARY_NA_C))
    s.add(Tekst(M + 20, 462, 600, 28, ZESPOL, r=20, waga="S", kolor=BIALY, nazwa="zespol"))
    s.add(Tekst(M + 20, 492, 700, 24, "HackNation 2026 · Misja AED – Dane na ratunek (Ministerstwo Cyfryzacji)",
                r=14, kolor=SZARY_NA_C))
    S.append(s)

    # 2 ------------------------------------------------------------------ problem
    s = Slajd("Problem")
    s.add(Prost(M, 96, 420, 120, wypelnienie=TLO_ALARM, promien=10))
    s.add(Prost(M, 96, 5, 120, wypelnienie=ALARM, promien=2))
    s.add(Tekst(M + 18, 106, 390, 104,
                ["Warszawa, 3 marca. Zawał w centrum miasta. Świadkowie szukają defibrylatora – "
                 "**są w kilku miejscach, ale zamknięte na klucz.**"], r=18, interlinia=1.3))
    y = 232
    for t, o in (("Rozproszone", "osobne zbiory gmin, bazy społecznościowe, prywatne mapy"),
                 ("Niejednolite", "każdy dostawca publikuje inne kolumny i formaty"),
                 ("Niezweryfikowane", "nikt nie bierze odpowiedzialności za aktualność")):
        s.add(Tekst(M, y, 420, 26, t, r=20, waga="B", kolor=ALARM))
        s.add(Tekst(M, y + 28, 420, 50, o, r=18))
        y += 86
    X2 = 490
    s.add(Tekst(X2, 96, 430, 30, "5 zbiorów AED w dane.gov.pl = 5 układów", r=20, waga="B"))
    wiersze = [("Krosno", "CSV, 6 kolumn – bez dostępności i zabezpieczenia"),
               ("Marki", "cały wiersz w jednym polu CSV, zamienione współrzędne"),
               ("Legionowo", "CSV, 11 kolumn z TERC/SIMC – brak godzin"),
               ("Przemyśl", "GeoJSON z opisem w wolnym tekście"),
               ("Warszawa", "odnośnik do API miasta wymagającego klucza")]
    y = 132
    for i, (g, o) in enumerate(wiersze):
        s.add(Prost(X2, y, 430, 62, wypelnienie=MIETA if i % 2 == 0 else BIALY, obrys=RAMKA, promien=6))
        s.add(Tekst(X2 + 12, y + 8, 120, 26, g, r=18, waga="S"))
        s.add(Tekst(X2 + 128, y + 8, 292, 56, o, r=18, interlinia=1.2))
        y += 66
    s.add(Tekst(X2, y + 2, 430, 20, "Źródło: zasoby gmin w dane.gov.pl (kopie w danych demo).",
                r=14, kolor=SZARY))
    S.append(s)

    # 3 ------------------------------------------------------------------ rozwiązanie
    s = Slajd("Rozwiązanie")
    s.add(Tekst(M, 96, W - 2 * M, 80,
                ["Rozbudowujemy portal dane.gov.pl o **Wykaz zbiorczy AED**: dostawcy publikują dane wg jednego "
                 "wzorca na własnych kontach, a portal sam je sprawdza i scala w jeden ogólnopolski, otwarty zbiór."],
                r=20, interlinia=1.3))
    bw, gap, by, bh = 152, 30, 210, 210
    bloki = [("Dostawcy", "urzędy, firmy, spółdzielnie – każdy na swoim koncie", MIETA, GRANAT),
             ("Wzorzec + walidacja", "29 pól, raport błędów: wiersz / pole", MIETA, GRANAT),
             ("Zadanie scalające", "jak „Wykaz chronionych danych (DGA)”", GRANAT, BIALY),
             ("Wykaz zbiorczy AED", "XLSX · CSV · GeoJSON · API JSON", ZIELEN_C, BIALY),
             ("Użytkownicy", "mapa #TuBijeAED, służby, deweloperzy", MIETA, GRANAT)]
    x = M
    for i, (t, o, tlo, kol) in enumerate(bloki):
        s.add(Prost(x, by, bw, bh, wypelnienie=tlo, obrys=None if tlo != MIETA else RAMKA, promien=12))
        s.add(Tekst(x + 12, by + 16, bw - 24, 60, t, r=19, waga="B", kolor=kol, interlinia=1.15))
        s.add(Tekst(x + 12, by + 84, bw - 24, bh - 92, o, r=18, kolor=kol, interlinia=1.2))
        if i < 4:
            s.add(Strzalka(x + bw + 4, by + bh / 2 - 12, gap - 8, 24, kolor=ZIELEN))
        x += bw + gap
    s.add(Tekst(M, 440, W - 2 * M, 60,
                ["Dane społecznościowe (OpenStreetMap) **nie wchodzą** do wykazu – na mapie są tylko warstwą "
                 "„do weryfikacji”. Za każdy rekord odpowiada konkretny dostawca."], r=18, kolor=SZARY))
    S.append(s)

    # 4 ------------------------------------------------------------------ wzorzec
    s = Slajd("Wzorcowy zakres danych")
    kol = [("Kto odpowiada", "5 pól",
            ["dysponent: nazwa, NIP/REGON (suma kontrolna), typ, kontakt", "identyfikator AED"]),
           ("Gdzie dokładnie", "14 pól",
            ["adres, TERYT/SIMC, współrzędne WGS84", "kondygnacja, wewnątrz budynku, opis miejsca"]),
           ("Czy da się użyć teraz", "10 pól",
            ["godziny: opening_hours", "zabezpieczenie: klucz / kod / ochrona + instrukcja",
             "status, przegląd, elektrody dziecięce"])]
    cw = (W - 2 * M - 2 * 20) / 3
    for i, (t, n, pkt) in enumerate(kol):
        x = M + i * (cw + 20)
        s.add(Prost(x, 96, cw, 262, wypelnienie=BIALY, obrys=RAMKA, promien=10))
        s.add(Prost(x, 96, cw, 5, wypelnienie=ZIELEN, promien=2))
        s.add(Tekst(x + 14, 112, cw - 28, 30, t, r=21, waga="B"))
        s.add(Tekst(x + 14, 142, cw - 28, 26, n, r=18, waga="S", kolor=ZIELEN_C))
        s.add(Tekst(x + 14, 174, cw - 28, 180, pkt, r=18, punktory=True, interlinia=1.2, odstep=0.25))
    s.add(Prost(M, 372, W - 2 * M, 126, wypelnienie=MIETA, promien=10))
    s.add(Tekst(M + 18, 384, 540, 110,
                ["**29 pól:** 19 wymaganych, 3 zalecane, 2 warunk., 5 opcj.",
                 "słowniki, warunki między polami, sumy kontrolne",
                 "**kodów PIN nie publikujemy** – „kod podaje dyspozytor 112”"],
                r=18, punktory=True, interlinia=1.2, odstep=0.2))
    s.add(Tekst(M + 580, 384, 290, 110,
                ["**Pliki:** wzorzec_danych_aed.xlsx (listy rozwijane, instrukcja), .csv, aed_schema.json"],
                r=18, interlinia=1.25))
    S.append(s)

    # 5 ------------------------------------------------------------------ zgodność
    s = Slajd("Zgodność z dane.gov.pl")
    s.add(Tekst(M, 92, W - 2 * M, 54,
                ["Odtworzyliśmy mechanizm **„Wykazu chronionych danych (DGA)”** z kodu portalu "
                 "(backend mcod 2.63.0) – i uogólniliśmy go: kolejny wykaz = jeden wpis konfiguracji."], r=18))
    tab = [("Portal dane.gov.pl (mcod)", "Prototyp #TuBijeAED"),
           ("Resource.contains_protected_data", "zasoby.wykaz_typ = \"AED\""),
           ("ResourceForm.clean – walidacja pliku DGA", "waliduj_zasob_wykazu + raport wg wzorca"),
           ("get_dga_resource_for_institution", "jeden zasób AED na instytucję (409)"),
           ("create_main_dga_resource_task (Celery)", "utworz_wykaz_zbiorczy – te same 4 kroki"),
           ("/dga-aggregated, AggregatedDGAInfo", "/api/1.4/aed-aggregated, wykazy_info"),
           ("harvester XML: containsProtectedData", "XSD 1.14: aggregatedListType = AED")]
    y, tw, c1 = 148, W - 2 * M, 440
    for i, (a, b) in enumerate(tab):
        nag = i == 0
        tlo = GRANAT if nag else (MIETA if i % 2 else BIALY)
        s.add(Prost(M, y, tw, 36, wypelnienie=tlo, obrys=RAMKA, promien=0))
        s.add(Tekst(M + 10, y + 7, c1 - 16, 26, a, r=18 if not nag else 18, waga="S" if nag else "M",
                    kolor=BIALY if nag else GRANAT))
        s.add(Tekst(M + c1 + 10, y + 7, tw - c1 - 16, 26, b, r=18, waga="S" if nag else "R",
                    kolor=BIALY if nag else GRANAT))
        y += 36
    s.add(Tekst(M, y + 12, 430, 70,
                ["**Dostawca odpowiada** za dane", "Instytucja › Zbiór › Zasób"],
                r=18, punktory=True, interlinia=1.2, odstep=0.2))
    s.add(Tekst(M + 450, y + 12, 430, 70,
                ["Licencje CC (wykaz: CC BY 4.0)", "OSM (ODbL) **poza wykazem**"],
                r=18, punktory=True, interlinia=1.2, odstep=0.2))
    s.add(Tekst(M, H - 46, W - 2 * M, 18, "Pełne mapowanie funkcja po funkcji: docs/ZGODNOSC_Z_DANE_GOV_PL.md",
                r=12, kolor=SZARY))
    S.append(s)

    # 6 ------------------------------------------------------------------ krok: błędy
    s = Slajd("Dostawca: zasób z błędami")
    s.add(Obraz(M, 92, 560, 408, k["bledy"], alt="Raport błędów walidacji w panelu dostawcy"))
    X = 620
    s.add(Tekst(X, 92, W - X - M, 200,
                ["**Panel dostawcy**, „Zaloguj jako” Urząd m.st. Warszawy",
                 "Dodaj zasób: aed_z_bledami.csv",
                 "Zaznacz „Zasób wchodzi do Wykazu zbiorczego AED” i wyślij"],
                r=18, punktory=True, interlinia=1.2, odstep=0.3))
    podpis(s, X, 296, W - X - M, 204,
           "Zasób odrzucony z wykazu. Raport: wiersz, pole i komunikat po polsku (zły kod pocztowy, suma NIP, "
           "współrzędne poza Polską…).")
    S.append(s)

    # 7 ------------------------------------------------------------------ krok: poprawny
    s = Slajd("Dostawca: po poprawce wykaz przebudowuje się sam")
    s.add(Obraz(M, 92, 560, 196, k["poprawny"], alt="Komunikat: zasób włączony do wykazu"))
    s.add(Obraz(M, 300, 560, 200, k["wykaz_po_dostawcy"], alt="Lista dostawców w wykazie zbiorczym"))
    X = 620
    s.add(Tekst(X, 92, W - X - M, 150,
                ["Przy zasobie „Zaktualizuj”: aed_poprawny.csv",
                 "Walidacja OK: zasób **włączony**",
                 "Wykaz scala się **automatycznie**"],
                r=18, punktory=True, interlinia=1.2, odstep=0.3))
    podpis(s, X, 262, W - X - M, 238,
           "Góra: „Zasób włączony…”, scalono 19 rekordów od 5 dostawców. Dół: strona Wykazu AED – "
           "Urząd m.st. Warszawy na liście dostawców (4 rekordy).")
    S.append(s)

    # 8 ------------------------------------------------------------------ automatyzacja
    s = Slajd("Automatyzacja: harvester XML 1.14 i asystent")
    s.add(Tekst(M, 90, 430, 26, "Harvester XML (schemat 1.14)", r=19, waga="B"))
    s.add(Obraz(M, 120, 430, 80, k["xml"], alt="Wynik importu XML w panelu dostawcy"))
    s.add(Obraz(M, 206, 430, 160, k["xml_zbiory"], alt="Zbiór i zasób utworzone z pliku XML"))
    s.add(Tekst(M + 450, 90, 430, 26, "Asystent: konwersja pliku gminy", r=19, waga="B"))
    s.add(Obraz(M + 450, 120, 430, 246, k["asystent"], alt="Wynik konwersji pliku gminy"))
    podpis(s, M, 380, W - 2 * M, 120,
           "Lewo: import harvester_1_14_przyklad.xml – powstał zbiór i zasób wykazu AED z walidacją poprawną. "
           "Prawo: stary plik Krosna przekonwertowany do wzorca + lista pól do uzupełnienia.")
    S.append(s)

    # 9 ------------------------------------------------------------------ administrator
    s = Slajd("Administrator portalu: historia scaleń")
    s.add(Obraz(M, 92, 520, 408, k["admin"], alt="Historia uruchomień scalania wykazu"))
    X = 580
    s.add(Obraz(X, 92, W - X - M, 150, k["pominiete"], alt="Pominięte zasoby z powodem"))
    podpis(s, X, 262, W - X - M, 238,
           "Konto Administrator (MC): „Przebuduj wykaz”, historia uruchomień – kto uwzględniony, kto pominięty "
           "i dlaczego. Ten sam powód widzi publicznie strona wykazu (prawo, u góry).")
    S.append(s)

    # 10 ----------------------------------------------------------------- mapa
    s = Slajd("Mapa #TuBijeAED: najbliższy AED")
    s.add(Obraz(M, 92, 560, 250, k["mapa_karta"], alt="Najbliższy AED z odległością i dostępnością"))
    s.add(Obraz(M, 352, 330, 148, k["mapa_mapa"], wyr="L", alt="Mapa z legendą"))
    s.add(Tekst(640, 92, 280, 24, "Telefon (390 px)", r=16, waga="S", kolor=SZARY))
    s.add(Obraz(640, 118, 200, 382, k["mob_gora"], wyr="L", alt="Mapa na telefonie – przycisk Zadzwoń 112"))
    podpis(s, 382, 352, 238, 148, "Odległość, „Dostępny teraz” (śr. 12:00), dostawca, „Zadzwoń 112”.",
           tytul="Co widać")
    S.append(s)

    # 11 ----------------------------------------------------------------- akcja
    s = Slajd(f"Akcja {TM.NAZWA} dla dostawców danych")
    s.add(Prost(M, 92, 420, 176, wypelnienie=GRANAT, promien=12))
    s.add(Tekst(M + 20, 106, 380, 72, f"„{TM.HASLO}”", r=26, waga="B", kolor=AKCENT, interlinia=1.2))
    s.add(Tekst(M + 20, 184, 380, 80, TM.WEZWANIE + ": odznaka do stopki strony i naklejka na kapsułę AED.",
                r=18, kolor=BIALY, interlinia=1.25))
    s.add(Obraz(M, 282, 200, 62, k["odznaka_aktywna"], ramka=False, alt="Odznaka Partnera – aktywna"))
    s.add(Obraz(M + 220, 282, 200, 62, k["odznaka_wygasla"], ramka=False, alt="Odznaka Partnera – wygasła"))
    s.add(Tekst(M, 348, 200, 20, "aktywna (≤ 12 mies.)", r=14, kolor=SZARY, wyr="C"))
    s.add(Tekst(M + 220, 348, 200, 20, "wygasła – dane nieaktualne", r=14, kolor=SZARY, wyr="C"))
    s.add(Tekst(M, 380, 420, 120,
                ["**Dlaczego zachęca:** odznaka wygasa, gdy dane się starzeją – dostawca ma powód, by je "
                 "aktualizować, a nie wgrać raz."], r=18, interlinia=1.25))
    s.add(Obraz(484, 92, 150, 210, os.path.join(BRAND, "zastosowania", "naklejka_kapsula_aed.png"), ramka=False,
                alt="Naklejka na kapsułę AED z kodem QR"))
    s.add(Obraz(650, 92, 210, 210, os.path.join(BRAND, "zastosowania", "kafel_social_1080.png"), ramka=False,
                wyr="L", alt="Kafel do mediów społecznościowych"))
    s.add(Obraz(484, 314, 436, 120, k["partner"], alt="Strona weryfikacji Partnera – status aktywny"))
    podpis(s, 484, 440, 436, 60, "", tytul="Naklejka z QR · kafel social · weryfikacja")
    S.append(s)

    # 12 ----------------------------------------------------------------- formaty / API
    s = Slajd("Dowody: formaty maszynowe i API")
    s.add(Obraz(M, 92, 400, 326, k["api_json"], alt="Odpowiedź JSON /api/1.4/aed-aggregated"))
    s.add(Obraz(M + 420, 92, 460, 250, k["api_docs"], alt="Dokumentacja OpenAPI – API 1.4"))
    s.add(Tekst(M + 420, 350, 460, 70,
                ["Wykaz: **XLSX, CSV UTF-8, GeoJSON** (RFC 7946) i **API JSON:API** jak api.dane.gov.pl/1.4. "
                 "Żadnych PDF/DOC dla danych."], r=18, interlinia=1.25))
    podpis(s, M, 428, W - 2 * M, 72,
           "Lewo: JSON /api/1.4/aed-aggregated. Prawo: OpenAPI /docs – endpointy API 1.4.")
    S.append(s)

    # 13 ----------------------------------------------------------------- jakość
    s = Slajd("Dowody: XSD, testy, WCAG 2.1 AA, bezpieczeństwo")
    s.add(Obraz(M, 92, 430, 92, k["20_xmllint"], ramka=False, alt="xmllint: plik XML przechodzi walidację XSD"))
    s.add(Obraz(M, 196, 430, 104, k["21_pytest"], ramka=False, alt=f"pytest: {testy} testów zaliczonych"))
    s.add(Obraz(M + 450, 92, 430, 246, k["22_axe"], ramka=False, alt="axe-core: 0 naruszeń WCAG A/AA"))
    s.add(Tekst(M, 312, 430, 110,
                [f"**{testy} testów** zaliczonych (z e2e ścieżki jurora)",
                 "XML 1.14 zgodny z XSD (xmllint)",
                 "Bezpieczeństwo: XSS, formuły CSV, limity 5 MB, SSRF"],
                r=18, punktory=True, interlinia=1.2, odstep=0.2))
    s.add(Tekst(M + 450, 344, 430, 80,
                ["WCAG 2.1 AA: axe 0 naruszeń A/AA, klawiatura, focus, 320 px bez przewijania"],
                r=18, punktory=True, interlinia=1.2))
    podpis(s, M, 430, W - 2 * M, 70,
           "Prawdziwe wyniki poleceń (xmllint, pytest) i fragment raportu axe z docs/RAPORT_TESTOW.md.",
           tytul="Co widać")
    S.append(s)

    # 14 ----------------------------------------------------------------- ograniczenia
    s = Slajd("Ograniczenia")
    lewa = ["**Okrojony portal lokalnie:** SQLite zamiast Postgres/Elasticsearch/Celery, logowanie demo bez haseł",
            "**XSD 1.14 to propozycja** zespołu (1 nowy element), nie oficjalny schemat",
            "**Mapa wymaga internetu** (Leaflet, kafle OSM); bez sieci działa lista i „najbliższe”",
            "Brak geokodowania adresów"]
    prawa = ["**Zbiory gmin nie spełniają wzorca** – odrzucane z raportem; braki trzeba uzupełnić",
             "Duplikaty między dostawcami tylko raportowane",
             "Parser opening_hours: podzbiór składni; święta = „nie wiadomo”",
             "Odznaka Partnera – propozycja dla MC; bez fizycznej weryfikacji urządzenia"]
    s.add(Tekst(M, 92, 420, 30, "Prototyp", r=21, waga="B", kolor=ZIELEN_C))
    s.add(Tekst(M, 132, 420, 350, lewa, r=20, punktory=True, interlinia=1.2, odstep=0.45))
    s.add(Tekst(M + 460, 92, 420, 30, "Dane i program", r=21, waga="B", kolor=ZIELEN_C))
    s.add(Tekst(M + 460, 132, 420, 350, prawa, r=20, punktory=True, interlinia=1.2, odstep=0.45))
    s.add(Tekst(M, 486, W - 2 * M, 22, "Pełna lista: docs/OGRANICZENIA.md", r=14, kolor=SZARY))
    S.append(s)

    # 15 ----------------------------------------------------------------- jak sprawdzić
    s = Slajd("Jak sprawdzić", tlo=GRANAT)
    s.add(Prost(M, 100, 420, 190, wypelnienie="#071a33", promien=12))
    s.add(Tekst(M + 20, 116, 380, 30, "Uruchomienie (ok. 2 min)", r=20, waga="B", kolor=AKCENT))
    s.add(Tekst(M + 20, 152, 380, 130,
                ["./uruchom.sh  (Windows: uruchom.bat)", "otwórz http://localhost:8080/jury.html",
                 "Python ≥ 3.11, dane demo offline"], r=18, kolor=BIALY, interlinia=1.3, odstep=0.3))
    s.add(Tekst(M + 460, 100, 420, 200,
                ["**JURY.md** – 12 kroków: co kliknąć, co sprawdzić, które wymaganie",
                 "**docs/OPIS_PROJEKTU.md**, ZGODNOSC_Z_DANE_GOV_PL.md, RAPORT_TESTOW.md",
                 "**docs/OSWIADCZENIE_AI.md** – zakres użycia AI (Regulamin §2 ust. 8)"],
                r=18, kolor=BIALY, punktory=True, interlinia=1.25, odstep=0.35))
    s.add(Tekst(M, 330, W - 2 * M, 50, f"„{TM.HASLO}”", r=32, waga="B", kolor=AKCENT, wyr="C"))
    s.add(Tekst(M, 384, W - 2 * M, 30, TM.PROGRAM, r=18, kolor=SZARY_NA_C, wyr="C"))
    s.add(Tekst(M, 440, W - 2 * M, 30, ZESPOL, r=20, waga="S", kolor=BIALY, wyr="C", nazwa="zespol"))
    S.append(s)

    n = len(S)
    for i, s in enumerate(S, 1):
        if i == 1:
            continue
        el = s.el
        s.el = []
        naglowek(s, i, n, s.tytul, ciemny=(s.tlo == GRANAT))
        s.el.extend(el)
    return S


# ---------------------------------------------------------------------- znaczniki **pogrubienia**
def czesci(t):
    """'a **b** c' → [('a ', False), ('b', True), (' c', False)]"""
    out = []
    for i, c in enumerate(re.split(r"\*\*", t)):
        if c:
            out.append((c, i % 2 == 1))
    return out


# ====================================================================== PDF (reportlab)
def renderuj_pdf(S):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph
    from reportlab.graphics import renderPDF
    from svglib.svglib import svg2rlg

    for f in WAGI.values():
        pdfmetrics.registerFont(TTFont(f, os.path.join(FONTY, f + ".ttf")))
    from fontTools.ttLib import TTFont as FTFont
    global CMAP
    CMAP = set(FTFont(os.path.join(FONTY, WAGI["R"] + ".ttf")).getBestCmap())
    from reportlab.graphics import shapes as rl_shapes
    rl_shapes.STATE_DEFAULTS["fontName"] = WAGI["R"]  # svglib/renderPDF inaczej dołącza nieosadzoną Helveticę
    c = canvas.Canvas(PDF_OUT, pagesize=(W, H), pageCompression=1, initialFontName=WAGI["R"], lang="pl-PL")
    c.setTitle(f"{TM.NAZWA} – Wykaz zbiorczy defibrylatorów AED w dane.gov.pl")
    c.setAuthor(ZESPOL)
    c.setSubject("HackNation 2026 · Misja AED – Dane na ratunek – prezentacja rozwiązania")
    c.setKeywords("AED, defibrylatory, dane.gov.pl, wykaz zbiorczy, #TuBijeAED")
    c.setCreator("4_prezentacja/generuj_prezentacje.py")
    ostrzezenia = []

    def Y(y, h=0):
        return H - y - h

    for nr, s in enumerate(S, 1):
        c.setFont(WAGI["R"], 12)  # bez tego reportlab dołącza nieosadzoną Helveticę jako font domyślny
        c.setFillColor(HexColor(s.tlo))
        c.rect(0, 0, W, H, stroke=0, fill=1)
        for e in s.el:
            if isinstance(e, Prost):
                if e.wypelnienie:
                    c.setFillColor(HexColor(e.wypelnienie))
                if e.obrys:
                    c.setStrokeColor(HexColor(e.obrys))
                    c.setLineWidth(e.grubosc)
                c.setDash(4, 3) if e.kreska else c.setDash()
                if e.promien:
                    c.roundRect(e.x, Y(e.y, e.h), e.w, e.h, e.promien, stroke=1 if e.obrys else 0,
                                fill=1 if e.wypelnienie else 0)
                else:
                    c.rect(e.x, Y(e.y, e.h), e.w, e.h, stroke=1 if e.obrys else 0, fill=1 if e.wypelnienie else 0)
                c.setDash()
            elif isinstance(e, Strzalka):
                c.setFillColor(HexColor(e.kolor))
                p = c.beginPath()
                x, y, w, h = e.x, Y(e.y, e.h), e.w, e.h
                t = h * 0.3
                p.moveTo(x, y + t)
                p.lineTo(x + w * 0.55, y + t)
                p.lineTo(x + w * 0.55, y)
                p.lineTo(x + w, y + h / 2)
                p.lineTo(x + w * 0.55, y + h)
                p.lineTo(x + w * 0.55, y + h - t)
                p.lineTo(x, y + h - t)
                p.close()
                c.drawPath(p, stroke=0, fill=1)
            elif isinstance(e, Obraz):
                c.drawImage(e.plik, e.x, Y(e.y, e.h), e.w, e.h, mask="auto")
                if e.ramka:
                    c.setStrokeColor(HexColor(RAMKA))
                    c.setLineWidth(0.8)
                    c.rect(e.x, Y(e.y, e.h), e.w, e.h, stroke=1, fill=0)
            elif isinstance(e, Svg):
                d = svg2rlg(e.svg)
                sk = e.w / d.width
                d.scale(sk, sk)
                d.width, d.height = d.width * sk, d.height * sk
                renderPDF.draw(d, c, e.x, Y(e.y, d.height))
            elif isinstance(e, Tekst):
                st = ParagraphStyle(
                    "t", fontName=WAGI[e.waga], fontSize=e.r, leading=e.r * e.interlinia,
                    textColor=HexColor(e.kolor), spaceAfter=e.r * e.odstep,
                    alignment={"L": TA_LEFT, "C": TA_CENTER, "R": TA_RIGHT}[e.wyr],
                    leftIndent=e.r * 1.0 if e.punktory else 0, bulletIndent=0, bulletFontName=WAGI["B"],
                    bulletFontSize=e.r, bulletColor=HexColor(ZIELEN if e.kolor == GRANAT else AKCENT))
                for a in e.akapity:
                    brak = sorted({ch for ch in a if ord(ch) not in CMAP and ch not in "\n"})
                    if brak:
                        ostrzezenia.append(f"slajd {nr}: brak glifów w Poppins: {brak} w {a[:40]!r}")
                y = e.y
                for i, a in enumerate(e.akapity):
                    html = "".join(f'<font name="{WAGI["S"] if e.waga == "R" else WAGI["X"]}">{escape(t)}</font>'
                                   if b else escape(t) for t, b in czesci(a))
                    p = Paragraph(html, st, bulletText="•" if e.punktory else None)
                    _, ph = p.wrap(e.w, H)
                    p.drawOn(c, e.x, Y(y, ph))
                    y += ph + (st.spaceAfter if i < len(e.akapity) - 1 else 0)
                if y - e.y > e.h + 2:
                    ostrzezenia.append(f"slajd {nr}: tekst wychodzi poza pole o {y - e.y - e.h:.0f} pt: "
                                       f"{e.akapity[0][:50]!r}")
                if e.x + e.w > W - 10 or y > H - 4:
                    ostrzezenia.append(f"slajd {nr}: tekst poza slajdem: {e.akapity[0][:50]!r}")
        c.showPage()
    c.save()
    for o in ostrzezenia:
        print("  UWAGA", o)
    print("PDF:", PDF_OUT)
    return ostrzezenia


# ====================================================================== PPTX (python-pptx)
def renderuj_pptx(S):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
    from pptx.oxml.ns import qn
    from pptx.util import Pt, Emu

    def rgb(h):
        return RGBColor.from_string(h.lstrip("#").upper())

    P = Presentation()
    P.slide_width, P.slide_height = Pt(W), Pt(H)
    pusty = P.slide_layouts[6]
    P.core_properties.title = f"{TM.NAZWA} – Wykaz zbiorczy defibrylatorów AED w dane.gov.pl"
    P.core_properties.author = ZESPOL
    P.core_properties.language = "pl-PL"
    for s in S:
        sl = P.slides.add_slide(pusty)
        bg = sl.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(s.tlo)
        for e in s.el:
            if isinstance(e, Prost):
                ksz = MSO_SHAPE.ROUNDED_RECTANGLE if e.promien else MSO_SHAPE.RECTANGLE
                sh = sl.shapes.add_shape(ksz, Pt(e.x), Pt(e.y), Pt(e.w), Pt(e.h))
                if e.promien:
                    sh.adjustments[0] = min(0.5, e.promien / max(1, min(e.w, e.h)))
                if e.wypelnienie:
                    sh.fill.solid()
                    sh.fill.fore_color.rgb = rgb(e.wypelnienie)
                else:
                    sh.fill.background()
                if e.obrys:
                    sh.line.color.rgb = rgb(e.obrys)
                    sh.line.width = Pt(e.grubosc)
                else:
                    sh.line.fill.background()
                sh.shadow.inherit = False
            elif isinstance(e, Strzalka):
                sh = sl.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Pt(e.x), Pt(e.y), Pt(e.w), Pt(e.h))
                sh.fill.solid()
                sh.fill.fore_color.rgb = rgb(e.kolor)
                sh.line.fill.background()
                sh.shadow.inherit = False
            elif isinstance(e, (Obraz, Svg)):
                plik = e.plik if isinstance(e, Obraz) else e.png
                pic = sl.shapes.add_picture(plik, Pt(e.x), Pt(e.y), Pt(e.w), Pt(e.h))
                alt = getattr(e, "alt", "") or TM.NAZWA
                pic._element.nvPicPr.cNvPr.set("descr", alt)
                if isinstance(e, Obraz) and e.ramka:
                    pic.line.color.rgb = rgb(RAMKA)
                    pic.line.width = Pt(0.8)
            elif isinstance(e, Tekst):
                tb = sl.shapes.add_textbox(Pt(e.x), Pt(e.y), Pt(e.w), Pt(e.h))
                if e.nazwa:
                    tb.name = e.nazwa
                tf = tb.text_frame
                tf.word_wrap = True
                tf.auto_size = MSO_AUTO_SIZE.NONE
                tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Emu(0)
                tf.vertical_anchor = MSO_ANCHOR.TOP
                for i, a in enumerate(e.akapity):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.alignment = {"L": PP_ALIGN.LEFT, "C": PP_ALIGN.CENTER, "R": PP_ALIGN.RIGHT}[e.wyr]
                    p.line_spacing = Pt(e.r * e.interlinia)
                    p.space_after = Pt(e.r * e.odstep)
                    if e.punktory:
                        pPr = p._p.get_or_add_pPr()
                        pPr.set("marL", str(int(Pt(e.r * 1.0))))
                        pPr.set("indent", str(-int(Pt(e.r * 1.0))))
                        bf = pPr.makeelement(qn("a:buFont"), {"typeface": "Poppins"})
                        bc = pPr.makeelement(qn("a:buClr"), {})
                        sc = bc.makeelement(qn("a:srgbClr"), {"val": (ZIELEN if e.kolor == GRANAT else AKCENT).lstrip("#")})
                        bc.append(sc)
                        bu = pPr.makeelement(qn("a:buChar"), {"char": "•"})
                        pPr.append(bc)
                        pPr.append(bf)
                        pPr.append(bu)
                    for t, b in czesci(a):
                        run = p.add_run()
                        run.text = t
                        f = run.font
                        waga = ("S" if e.waga == "R" else "X") if b else e.waga
                        f.name, f.bold = WAGI_PPTX[waga]
                        f.size = Pt(e.r)
                        f.color.rgb = rgb(e.kolor)
                        rPr = run._r.get_or_add_rPr()
                        rPr.set("lang", "pl-PL")
        if s.notatka:
            sl.notes_slide.notes_text_frame.text = s.notatka
    P.save(PPTX_OUT)
    print("PPTX:", PPTX_OUT)


def main():
    term_p = os.path.join(ZRZUTY, "terminal.json")
    term = json.load(open(term_p)) if os.path.exists(term_p) else {}
    k = przygotuj_kadry()
    S = zbuduj(k, term)
    print("slajdów:", len(S))
    for i, s in enumerate(S, 1):
        print(f"  {i:2d}. {s.tytul}")
    renderuj_pdf(S)
    renderuj_pptx(S)
    # podglądy slajdów (40 dpi) do szybkiego przeglądu
    import glob
    import shutil
    import subprocess
    if shutil.which("pdftoppm"):
        pod = os.path.join(TU, "podglad")
        os.makedirs(pod, exist_ok=True)
        for f in glob.glob(os.path.join(pod, "slajd-*.png")):
            os.remove(f)
        subprocess.run(["pdftoppm", "-r", "40", "-png", PDF_OUT, os.path.join(pod, "slajd")], check=True)
        print("podglądy:", pod)


if __name__ == "__main__":
    main()
