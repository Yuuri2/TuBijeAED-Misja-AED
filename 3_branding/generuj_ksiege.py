"""#TuBijeAED – Księga znaku (PDF, A4 poziomo, wektorowo, czcionka Poppins osadzona).

Uruchomienie (z katalogu repo) – JEDNO polecenie przegenerowuje wszystko:
    .venv/bin/python 3_branding/generuj_ksiege.py
Kolejno: final/generuj_final.py (static/brand), generuj_logotypy.py (pliki do oddania i zastosowania),
na końcu 3_branding/Ksiega_Znaku_TuBijeAED.pdf.
Opcja --podglad: dodatkowo podglądy PNG (3_branding/podglad_ksiegi/strona-NN.png, final/podglad/*.png) – domyślnie
nie są tworzone (nie należą do oddawanych plików).

Teksty (hasło, podpis pod logo, odznaka, opis koncepcji, adres QR): 3_branding/teksty_marki.py.
Zależności (.venv): reportlab, svglib (SVG → wektory reportlab), cairosvg, fonttools, pillow, segno.
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

from fontTools.ttLib import TTFont as FTFont
from PIL import Image
from reportlab.graphics import renderPDF, shapes
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final"))
import teksty_marki as TXT  # noqa: E402
import generuj_final as G  # noqa: E402
import generuj_logotypy as L  # noqa: E402

OUT = ROOT / "Ksiega_Znaku_TuBijeAED.pdf"
PODGLAD = ROOT / "podglad_ksiegi"
FONTS = G.FONTS   # 3_branding/fonts (Poppins, OFL)
SERIF = Path("/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf")   # tylko przykład „zmiany kroju”

GREEN, GREEN_DARK, NAVY, GRAY, LGREEN = G.GREEN, G.GREEN_DARK, G.NAVY, G.GRAY, G.LGREEN
WHITE, MINT, LGRAY, LINE, RED = "#FFFFFF", L.MINT, G.LGRAY_ON_DARK, "#D5DEE6", "#D90429"

PW, PH = landscape(A4)
M = 42                       # margines strony
CW = PW - 2 * M              # szerokość obszaru treści

# ---------------------------------------------------------------- czcionki (osadzane w PDF)
WAGI = {"Regular": "Poppins-Regular", "Medium": "Poppins-Medium", "SemiBold": "Poppins-SemiBold",
        "Bold": "Poppins-Bold", "ExtraBold": "Poppins-ExtraBold"}
for w, name in WAGI.items():
    pdfmetrics.registerFont(TTFont(name, str(FONTS / f"Poppins-{w}.ttf")))
pdfmetrics.registerFontFamily("Poppins", normal="Poppins-Regular", bold="Poppins-SemiBold",
                              italic="Poppins-Regular", boldItalic="Poppins-SemiBold")
REG, MED, SEMI, BOLD, XBOLD = WAGI.values()
# renderPDF ustawia domyślną czcionkę rysunku (Helvetica, nieosadzona) – zamieniamy ją na osadzaną Poppins
shapes.STATE_DEFAULTS["fontName"] = REG
CMAP = set(FTFont(str(FONTS / "Poppins-Regular.ttf")).getBestCmap())
BRAKI: set[str] = set()


def check(text: str):
    """Pilnuje, by każdy znak tekstu był w Poppins (inaczej w PDF byłby pusty kwadrat)."""
    plain = re.sub(r"<[^>]+>", "", text).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    BRAKI.update(ch for ch in plain if ord(ch) not in CMAP and ch not in "\n")


# ---------------------------------------------------------------- rysowanie
def Y(yt: float) -> float:
    return PH - yt


def hexc(c):
    return HexColor(c) if isinstance(c, str) else c


def txt(c, s, x, yt, font=REG, size=10, color=NAVY, anchor="l", track=0.0):
    check(s)
    c.setFillColor(hexc(color))
    w = pdfmetrics.stringWidth(s, font, size) + track * (len(s) - 1)
    if anchor == "c":
        x -= w / 2
    elif anchor == "r":
        x -= w
    t = c.beginText(x, Y(yt))
    t.setFont(font, size)
    t.setCharSpace(track)
    t.textOut(s)
    t.setCharSpace(0)          # Tc należy do stanu graficznego strony – zerujemy, by nie „rozciągał” kolejnych tekstów
    c.drawText(t)
    return w


def style(size=10, font=REG, color=NAVY, leading=None, align=0):
    return ParagraphStyle("p", fontName=font, fontSize=size, leading=leading or size * 1.45,
                          textColor=hexc(color), alignment=align)


def para(c, text, x, yt, w, size=10, font=REG, color=NAVY, leading=None, align=0):
    """Akapit (górna krawędź yt). Zwraca wysokość."""
    check(text)
    p = Paragraph(text, style(size, font, color, leading, align))
    _, h = p.wrap(w, 1000)
    p.drawOn(c, x, Y(yt) - h)
    return h


def bullets(c, items, x, yt, w, size=9.5, color=NAVY, gap=4, bullet_color=GREEN):
    for it in items:
        txt(c, "•", x, yt + size * 1.05, BOLD, size, bullet_color)
        yt += para(c, it, x + 11, yt, w - 11, size, color=color) + gap
    return yt


def rect(c, x, yt, w, h, fill=None, stroke=None, lw=0.6, r=0, dash=None):
    c.saveState()
    if fill:
        c.setFillColor(hexc(fill))
    if stroke:
        c.setStrokeColor(hexc(stroke))
        c.setLineWidth(lw)
    if dash:
        c.setDash(*dash)
    if r:
        c.roundRect(x, Y(yt + h), w, h, r, stroke=1 if stroke else 0, fill=1 if fill else 0)
    else:
        c.rect(x, Y(yt + h), w, h, stroke=1 if stroke else 0, fill=1 if fill else 0)
    c.restoreState()


def line(c, x1, y1t, x2, y2t, color=LINE, lw=0.6, dash=None):
    c.saveState()
    c.setStrokeColor(hexc(color))
    c.setLineWidth(lw)
    if dash:
        c.setDash(*dash)
    c.line(x1, Y(y1t), x2, Y(y2t))
    c.restoreState()


def drawing(svg: str):
    d = svg2rlg(io.BytesIO(svg.encode("utf-8")))
    if d is None:
        raise RuntimeError("svglib nie wczytał SVG")
    return d


def svg(c, s: str, x, yt, w=None, h=None, sx=None, sy=None, rotate=0.0):
    """Rysuje SVG wektorowo (svglib). Mieści w w×h z zachowaniem proporcji. Zwraca (szer., wys.) w pt."""
    d = drawing(s)
    dw, dh = d.width, d.height
    if sx is None:
        k = min(w / dw if w else 1e9, h / dh if h else 1e9)
        sx = sy = k
    d.scale(sx, sy)
    rw, rh = dw * sx, dh * sy
    if rotate:
        c.saveState()
        c.translate(x + rw / 2, Y(yt + rh / 2))
        c.rotate(rotate)
        renderPDF.draw(d, c, -rw / 2, -rh / 2)
        c.restoreState()
    else:  # svglib nie przycina do viewBox – robimy to sami
        c.saveState()
        clip(c, x, yt, rw, rh)
        renderPDF.draw(d, c, x, Y(yt) - rh)
        c.restoreState()
    return rw, rh


def svg_center(c, s, x, yt, w, h, fw, fh):
    """Wpisuje SVG w ramkę (x, yt, w, h) z marginesem: maks. fw×fh, wyśrodkowane."""
    d = drawing(s)
    k = min(fw / d.width, fh / d.height)
    rw, rh = d.width * k, d.height * k
    return svg(c, s, x + (w - rw) / 2, yt + (h - rh) / 2, sx=k, sy=k)


def clip(c, x, yt, w, h):
    p = c.beginPath()
    p.rect(x, Y(yt + h), w, h)
    c.clipPath(p, stroke=0, fill=0)


def image(c, im: Image.Image, x, yt, w, h):
    c.drawImage(ImageReader(im), x, Y(yt + h), w, h, mask="auto")


def inner_of(svg_doc: str) -> str:
    return svg_doc.split("</title>", 1)[1].rsplit("</svg>", 1)[0].split("</desc>", 1)[-1]


# ---------------------------------------------------------------- dane znaku
LOGO_IN, LOGO_W, LOGO_H = G.logo("light")
LOGO = G.doc(LOGO_W, LOGO_H, LOGO_IN, "logo")
LOGO_NEG = G.doc(LOGO_W, LOGO_H, G.logo("dark")[0], "logo")
KOMP_IN, KOMP_W, KOMP_H = G.logo("light", kompakt=True)
KOMP = G.doc(KOMP_W, KOMP_H, KOMP_IN, "logo")
SYG = G.doc(100, 100, G.sygnet("light"), "sygnet")
SYG_NEG = G.doc(100, 100, G.sygnet("dark"), "sygnet")
VIS = L.bbox(LOGO_IN, LOGO_W, LOGO_H)                 # widoczny prostokąt logo (jedn. SVG)
VIS_W = VIS[2] - VIS[0]
DATA_PRZYKLAD = "22.11.2027"

SEKCJE = ["Idea i koncepcja", "Budowa znaku", "Warianty znaku", "Kolorystyka", "Kontrast i dostępność",
          "Typografia", "Pole ochronne", "Minimalna wielkość", "Niedozwolone użycia", "Znak a ISO 7010 E010",
          "Odznaka Partnera", "Naklejka na kapsułę AED", "Media społecznościowe i www", "Pliki i licencje"]
TOTAL = len(SEKCJE) + 1


def logo_mono(color):
    i, w, h = G.logo("light", color=color)
    return G.doc(w, h, i, "logo")


def page_frame(c, n, lead=None):
    """Nagłówek sekcji n (1..14) + stopka. Zwraca yt początku treści."""
    sek = SEKCJE[n - 1]
    txt(c, f"{n:02d}  ·  {sek.upper()}", M, 40, SEMI, 8, GREEN, track=1.2)
    txt(c, sek, M, 70, BOLD, 23, NAVY)
    svg(c, SYG, PW - M - 26, 24, w=26)
    yt = 84
    if lead:
        yt += para(c, lead, M, 82, 640, 10, color=GRAY) + 2
    stopka(c, n + 1)
    return max(yt + 16, 108)


def stopka(c, page_no, dark=False):
    col = LGRAY if dark else GRAY
    line(c, M, PH - 30, PW - M, PH - 30, "#2C4A6B" if dark else LINE, 0.5)
    txt(c, f"{TXT.NAZWA} · Księga znaku · {TXT.KSIEGA_WERSJA}", M, PH - 18, REG, 7, col)
    txt(c, "Czcionka Poppins © 2020 The Poppins Project Authors – SIL Open Font License 1.1",
        PW / 2, PH - 18, REG, 7, col, anchor="c")
    txt(c, f"{page_no} / {TOTAL}", PW - M, PH - 18, SEMI, 7, col, anchor="r")


def label(c, s, x, yt, color=GREEN):
    txt(c, s.upper(), x, yt, SEMI, 7.5, color, track=1.0)


# ---------------------------------------------------------------- strony
def okladka(c):
    rect(c, 0, 0, PW, PH, fill=NAVY)
    svg(c, G.doc(PW, PH, L.fale_dekor(PW, 0, 150, LGREEN, 0.10, n=3, sw=26), "dekor"), 0, 0, w=PW)
    label(c, "Księga znaku", M + 8, 70, LGREEN)
    neg = L.logotypy_cache["poziomy_negatyw"]
    svg(c, neg, M - 6, 92, w=470)
    hy = 300
    h = para(c, TXT.HASLO, M + 8, hy, 480, 32, BOLD, WHITE, leading=38)
    para(c, TXT.HASLO_PODTYTUL, M + 8, hy + h + 10, 420, 11.5, REG, LGRAY, leading=17)
    txt(c, TXT.KSIEGA_WERSJA, M + 8, PH - 62, MED, 9, WHITE)
    txt(c, f"{TXT.KSIEGA_KONTEKST} · zadanie Ministerstwa Cyfryzacji (dane.gov.pl)", M + 8, PH - 48, REG, 8, LGRAY)
    # spis treści
    x0 = 560
    rect(c, x0 - 18, 140, PW - M - x0 + 18, 360, fill="#11305A", r=10)
    label(c, "Spis treści", x0, 168, LGREEN)
    y = 192
    for i, s in enumerate(SEKCJE, 1):
        txt(c, f"{i:02d}", x0, y, SEMI, 9, LGREEN)
        txt(c, s, x0 + 24, y, REG, 9, WHITE)
        txt(c, str(i + 1), PW - M - 14, y, REG, 9, LGRAY, anchor="r")
        y += 21.5
    stopka(c, 1, dark=True)


def s_idea(c):
    y = page_frame(c, 1, "Znak i hasło akcji promocyjnej skierowanej do dostawców danych o defibrylatorach.")
    lw = 410
    label(c, "Opis koncepcji", M, y + 6)
    h = para(c, " ".join(TXT.opis_koncepcji()), M, y + 16, lw, 11.2, REG, NAVY, leading=17.2)
    by = y + 16 + h + 18
    rect(c, M, by, lw, 104, fill=MINT, r=8)
    label(c, "Hasło akcji", M + 16, by + 22)
    hh = para(c, TXT.HASLO, M + 16, by + 28, lw - 32, 19, BOLD, NAVY, leading=23)
    para(c, TXT.HASLO_PODTYTUL, M + 16, by + 32 + hh, lw - 32, 8.8, REG, GRAY, leading=12.5)
    # elementy znaku
    x = 490
    w = PW - M - x
    label(c, "Elementy sygnetu", x, y + 6)
    ikony = [
        ("Serce", "pomoc, troska, życie – i odpowiedzialność, którą dostawca bierze za swoje dane.",
         f'<path d="{G.HEART}" fill="{GREEN}"/>'),
        ("Błyskawica", "defibrylacja – czytelny skrót „tu jest AED”, wycięty z serca (zawsze w kolorze tła).",
         f'<path d="{G.BOLT}" fill="{GREEN}" transform="translate(50 50) scale(1.45) translate(-50 -47)"/>'),
        ("Fale nadawania", "dane wysyłane od właściciela do otwartego portalu dane.gov.pl i dalej – sygnał "
         "„tu jestem” dla każdego, kto szuka pomocy.",
         f'<g transform="translate(-33 33)"><circle cx="57.2" cy="42.8" r="7" fill="{GREEN}"/>'
         f'<path d="M66 14 A30 30 0 0 1 86 34" fill="none" stroke="{GREEN}" stroke-width="7" stroke-linecap="round"/>'
         f'<path d="M70 3 A42 42 0 0 1 97 30" fill="none" stroke="{GREEN}" stroke-width="7" stroke-linecap="round" '
         'opacity=".55"/></g>'),
    ]
    yy = y + 16
    for tytul, opis, ik in ikony:
        rect(c, x, yy, w, 74, fill=MINT, r=8)
        svg(c, G.doc(100, 100, ik, "ikona"), x + 12, yy + 10, w=54)
        txt(c, tytul, x + 80, yy + 24, SEMI, 11, NAVY)
        para(c, opis, x + 80, yy + 30, w - 92, 8.6, REG, GRAY, leading=11.8)
        yy += 84
    label(c, "Do kogo mówimy", x, yy + 14)
    bullets(c, [
        "<b>Urzędy</b> – gminy, powiaty, instytucje państwowe, szkoły, szpitale.",
        "<b>Firmy</b> – galerie, dworce, sieci handlowe, obiekty sportowe, pracodawcy.",
        "<b>Problem:</b> dane o AED są rozproszone i niezweryfikowane – nikt nie bierze za nie odpowiedzialności.",
        f"<b>Odpowiedź:</b> program „{TXT.PROGRAM}”.",
    ], x, yy + 22, w, 8.8, gap=2)


def s_budowa(c):
    y = page_frame(c, 2, "Sygnet powstaje na siatce 10 × 10 jednostek (j). Wszystkie wymiary znaku wynikają z tej siatki.")
    S = 300
    x0, y0 = M + 4, y + 8
    k = S / 100
    rect(c, x0, y0, S, S, fill="#F6FAF8")
    for i in range(11):
        line(c, x0 + i * 10 * k, y0, x0 + i * 10 * k, y0 + S, "#D3E3DA", 0.5)
        line(c, x0, y0 + i * 10 * k, x0 + S, y0 + i * 10 * k, "#D3E3DA", 0.5)
    svg(c, SYG, x0, y0, w=S)
    fx, fy = G.FALE_SRODEK
    c.saveState()
    c.setStrokeColor(hexc(NAVY))
    c.setLineWidth(0.7)
    c.setDash(3, 2.5)
    for r in G.FALE_R:
        c.circle(x0 + fx * k, Y(y0 + fy * k), r * k, stroke=1, fill=0)
    c.setStrokeColor(hexc(GRAY))
    c.rect(x0 + 17.9 * k, Y(y0 + 83 * k), (70.1 - 17.9) * k, (83 - 29) * k, stroke=1, fill=0)
    c.restoreState()
    c.setFillColor(hexc(RED))
    c.circle(x0 + fx * k, Y(y0 + fy * k), 2.6, stroke=0, fill=1)
    txt(c, "F", x0 + fx * k + 5, y0 + fy * k - 4, BOLD, 9, RED)
    txt(c, "r1", x0 + 80 * k, y0 + 52 * k, SEMI, 8.5, NAVY)
    txt(c, "r2", x0 + 96 * k, y0 + 64 * k, SEMI, 8.5, NAVY, anchor="r")
    txt(c, "serce 5,2 × 5,4 j", x0 + 17.9 * k, y0 + 83 * k + 11, MED, 7.5, GRAY)
    txt(c, "10 j", x0 + S / 2, y0 + S + 13, SEMI, 8, NAVY, anchor="c")
    txt(c, "1 j = 1/10 wysokości pola sygnetu", x0, y0 + S + 28, REG, 7.5, GRAY)

    # proporcje logo
    lx = x0 + S + 36
    lw_ = PW - M - lx
    label(c, "Proporcje logo", lx, y + 14)
    ly = y + 44
    rw, rh = svg(c, LOGO, lx + 16, ly, w=lw_ - 16)
    s_ = rh / 160
    for lab, v in (("A", 0), ("B", 98), ("C", 138), ("D", 160)):
        line(c, lx + 10, ly + v * s_, PW - M, ly + v * s_, RED, 0.5, (2, 2))
        txt(c, lab, lx + 3, ly + v * s_ + 3, SEMI, 7, RED, anchor="c")
    ax1, ax2 = lx + 16 + 160 * s_, lx + 16 + 188 * s_
    line(c, ax1, ly - 8, ax2, ly - 8, NAVY, 0.6)
    line(c, ax1, ly - 11, ax1, ly - 5, NAVY, 0.6)
    line(c, ax2, ly - 11, ax2, ly - 5, NAVY, 0.6)
    txt(c, "1,75 j", (ax1 + ax2) / 2, ly - 13, MED, 7, NAVY, anchor="c")

    by = ly + rh + 26
    cw = (lw_ - 20) / 2
    label(c, "Konstrukcja sygnetu", lx, by)
    bullets(c, [
        "<b>Serce</b> 5,2 × 5,4 j, osadzone w lewym dolnym polu siatki.",
        "<b>Błyskawica</b> jest wycięta z serca – w każdej wersji ma kolor tła.",
        "<b>Fale</b>: dwa łuki o wspólnym środku <b>F</b> (w górnej części serca), promienie <b>r1 = 3,0 j</b> "
        "i <b>r2 = 4,2 j</b>, grubość 0,6 j, zaokrąglone końce.",
        "Drugi łuk ma krycie 55 % (w wersjach jednobarwnych 100 %).",
        "Brak tła i ramki – sylwetka sygnetu to samo serce z falami.",
    ], lx, by + 8, cw, 8.5, gap=3)
    nazwa_w = G.F["med"].width(TXT.NAZWA_CZ1, 78) + G.F["xbold"].width(TXT.NAZWA_CZ2, 78) + 78 * 0.03
    psize, ptrack = G.podpis_rozmiar(nazwa_w)
    px = lx + cw + 20
    label(c, "Wymiary logo", px, by)
    bullets(c, [
        "<b>A–D</b>: pole sygnetu = 10 j (A – góra, D – dół). Nazwa i podpis mieszczą się w tym polu.",
        "<b>B</b> – linia bazowa nazwy: 6,1 j od góry. Nazwa: Poppins Medium „"
        f"{TXT.NAZWA_CZ1}” + ExtraBold „{TXT.NAZWA_CZ2}”, stopień 4,9 j.",
        "<b>C</b> – linia bazowa podpisu: 8,6 j. Podpis: Poppins Medium, wersaliki, stopień "
        + f"{psize / 16:.2f}".replace(".", ",") + f" j, światło {ptrack / psize * 100:.0f} %.",
        "Odstęp sygnet – nazwa: 1,75 j. Podpis jest wyrównany do nazwy i nie jest od niej szerszy.",
    ], px, by + 8, cw, 8.5, gap=3)


def tile(c, x, yt, w, h, bg, s, cap, desc, fw=None, fh=None, border=False):
    rect(c, x, yt, w, h, fill=bg, stroke=LINE if border else None, r=6)
    svg_center(c, s, x, yt, w, h, fw or w - 44, fh or h - 50)
    txt(c, cap, x, yt + h + 15, SEMI, 9.5, NAVY)
    para(c, desc, x, yt + h + 20, w, 8, REG, GRAY, leading=11)


def s_warianty(c):
    y = page_frame(c, 3)
    gw, gh, gx = 20, 150, (CW - 40) / 3
    rows = [
        [(WHITE, LOGO, "Podstawowy", "Wersja główna – na bieli i jasnych tłach. Zawsze wybieraj ją w pierwszej kolejności.", True),
         (NAVY, LOGO_NEG, "Negatyw", "Na granacie #0B2545 i ciemnych, spokojnych zdjęciach. Fale i serce w zieleni sygnałowej.", False),
         (WHITE, KOMP, "Kompakt (bez podpisu)", "Nagłówki serwisu 32–56 px, telefony, małe formaty, gdzie podpis byłby nieczytelny.", True)],
        [(None, None, "Sygnet", "Awatar, ikona aplikacji, naklejka, odznaka. Na jasnym tle (lewo) i w negatywie (prawo).", True),
         (WHITE, logo_mono("#000000"), "Monochromatyczny", "Druk jednobarwny, grawer, pieczęć, faks. Oba łuki pełne, błyskawica wycięta.", True),
         ("#1F2933", logo_mono(WHITE), "Monochromatyczny – biały", "Nadruk białą farbą na ciemnym materiale (koszulki, torby, folia).", False)],
    ]
    for r, row in enumerate(rows):
        yt = y + r * (gh + 58)
        for i, (bg, s, cap, desc, border) in enumerate(row):
            x = M + i * (gx + gw)
            if s is None:
                rect(c, x, yt, gx / 2, gh, fill=WHITE, stroke=LINE, r=6)
                rect(c, x + gx / 2, yt, gx / 2, gh, fill=NAVY, r=6)
                rect(c, x + gx / 2, yt, 8, gh, fill=NAVY)
                svg_center(c, SYG, x, yt, gx / 2, gh, 84, 84)
                svg_center(c, SYG_NEG, x + gx / 2, yt, gx / 2, gh, 84, 84)
                txt(c, cap, x, yt + gh + 15, SEMI, 9.5, NAVY)
                para(c, desc, x, yt + gh + 20, gx, 8, REG, GRAY, leading=11)
            else:
                tile(c, x, yt, gx, gh, bg, s, cap, desc, fw=gx - 40, fh=60 if "Kompakt" in cap else 74, border=border)


KOLORY = [
    ("Zieleń AED", "kolor główny: sygnet, „AED”", GREEN, "0 · 132 · 61", "100 · 0 · 90 · 25", "348 C"),
    ("Granat nocny", "nazwa „#TuBije”, tekst, tło negatywu", NAVY, "11 · 37 · 69", "100 · 80 · 35 · 55", "289 C"),
    ("Biel", "tło podstawowe, wycięcie błyskawicy", WHITE, "255 · 255 · 255", "0 · 0 · 0 · 0", "– (papier)"),
    ("Zieleń sygnałowa", "TYLKO na granacie: znak i akcenty w negatywie", LGREEN, "95 · 211 · 141", "55 · 0 · 55 · 0", "≈ 353 C"),
    ("Grafit", "podpis pod logo, tekst pomocniczy", GRAY, "74 · 85 · 104", "70 · 55 · 35 · 30", "≈ 7545 C"),
    ("Mięta", "tła jasne, pas naklejki, karty", MINT, "232 · 245 · 238", "8 · 0 · 6 · 0", "10 % z 348 C"),
    ("Zieleń ciemna", "linki, tekst zielony na mięcie, hover", GREEN_DARK, "0 · 106 · 49", "100 · 15 · 95 · 45", "≈ 349 C"),
]


def s_kolory(c):
    y = page_frame(c, 4, "Paleta jest krótka: zieleń AED i granat niosą znak, biel daje mu oddech, "
                         "pozostałe kolory są pomocnicze.")
    gap = 16
    cw = (CW - 3 * gap) / 4
    for i, (nazwa, rola, hx, rgb, cmyk, pms) in enumerate(KOLORY):
        r, col = divmod(i, 4)
        x = M + col * (cw + gap)
        yt = y + r * 190
        rect(c, x, yt, cw, 70, fill=hx, stroke=LINE if hx in (WHITE, MINT) else None, r=6)
        txt(c, nazwa, x, yt + 88, SEMI, 10.5, NAVY)
        para(c, rola, x, yt + 93, cw, 7.8, REG, GRAY, leading=10)
        vy = yt + 124
        for lab, val in (("HEX", hx), ("RGB", rgb), ("CMYK", cmyk), ("Pantone", pms)):
            txt(c, lab, x, vy, SEMI, 7.5, GRAY)
            txt(c, val, x + 46, vy, MED, 8, NAVY)
            vy += 12
    # proporcje
    x = M + 3 * (cw + gap)
    yt = y + 190
    label(c, "Proporcje w materiałach", x, yt + 8)
    parts = [(WHITE, 0.55, "biel"), (NAVY, 0.25, "granat"), (GREEN, 0.15, "zieleń"), (MINT, 0.05, "")]
    xx = x
    for hx, p, lab in parts:
        rect(c, xx, yt + 16, cw * p, 30, fill=hx, stroke=LINE if hx == WHITE else None)
        xx += cw * p
    txt(c, "55 % biel · 25 % granat · 15 % zieleń · 5 % akcenty", x, yt + 60, REG, 7.5, GRAY)
    para(c, "Czerwień #D90429 jest kolorem komunikatów (112, błędy) w serwisie – <b>nigdy</b> w znaku ani w materiałach akcji.",
         x, yt + 70, cw, 7.8, REG, NAVY, leading=10.5)
    para(c, "Wartości CMYK i Pantone są orientacyjne (przeliczenie z RGB). Przed drukiem potwierdź je na wzorniku i proofie "
         "drukarni. Kolorem wzorcowym jest wartość HEX/RGB.", M, PH - 66, CW, 8, REG, GRAY)


def lum(hx):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def s_kontrast(c):
    y = page_frame(c, 5, "Kontrast liczony wg WCAG 2.2. Znak jako element graficzny wymaga co najmniej 3:1 (kryterium 1.4.11), "
                         "tekst – 4,5:1 (AA).")
    pary = [
        (NAVY, WHITE, "Granat na bieli", "nazwa, tekst główny"),
        (WHITE, NAVY, "Biel na granacie", "negatyw, tekst na ciemnym tle"),
        (GREEN, WHITE, "Zieleń AED na bieli", "sygnet, „AED”, tekst ≥ 14 px"),
        (WHITE, GREEN, "Biel na zieleni AED", "przyciski (tekst SemiBold)"),
        (GRAY, WHITE, "Grafit na bieli", "podpis pod logo, tekst pomocniczy"),
        (LGREEN, NAVY, "Zieleń sygnałowa na granacie", "sygnet i „AED” w negatywie"),
        (LGRAY, NAVY, "Szary jasny na granacie", "podpis pod logo w negatywie"),
        (GREEN_DARK, MINT, "Zieleń ciemna na mięcie", "tekst zielony na jasnym tle"),
        (NAVY, MINT, "Granat na mięcie", "hasło na banerze, naklejka"),
        (GREEN, MINT, "Zieleń AED na mięcie", "tylko grafika i duży tekst"),
        (GREEN, NAVY, "Zieleń AED na granacie", "zakaz w znaku – użyj zieleni sygnałowej"),
        (LGREEN, WHITE, "Zieleń sygnałowa na bieli", "zakaz – za niski kontrast"),
    ]
    cols = [("Próbka", 64), ("Kolor / tło", 190), ("HEX", 120), ("Kontrast", 70), ("Ocena WCAG 2.2", 150), ("Zastosowanie", 0)]
    xs, x = [], M
    for _, w in cols:
        xs.append(x)
        x += w
    rect(c, M, y, CW, 20, fill=NAVY, r=4)
    for (lab, _), x in zip(cols, xs):
        txt(c, lab, x + 8, y + 13.5, SEMI, 8, WHITE)
    yt = y + 20
    for i, (fg, bg, nazwa, uzycie) in enumerate(pary):
        rh = 25
        if i % 2:
            rect(c, M, yt, CW, rh, fill="#F5F8F7")
        r = ratio(fg, bg)
        zakaz = "zakaz" in uzycie
        if zakaz:
            ocena, oc = "niedozwolone", RED
        elif r >= 7:
            ocena, oc = "AAA – każdy tekst", GREEN_DARK
        elif r >= 4.5:
            ocena, oc = "AA – każdy tekst", GREEN_DARK
        elif r >= 3:
            ocena, oc = "AA – duży tekst, grafika", "#8A5A00"
        else:
            ocena, oc = "niedozwolone", RED
        rect(c, xs[0] + 8, yt + 4, 46, 17, fill=bg, stroke=LINE if bg in (WHITE, MINT) else None, r=3)
        txt(c, "Aa", xs[0] + 31, yt + 16.5, BOLD, 10, fg, anchor="c")
        txt(c, nazwa, xs[1] + 8, yt + 16, MED, 8.5, NAVY)
        txt(c, f"{fg} / {bg}", xs[2] + 8, yt + 16, REG, 8, GRAY)
        txt(c, f"{r:.2f}:1".replace(".", ","), xs[3] + 8, yt + 16, SEMI, 8.5, NAVY)
        txt(c, ocena, xs[4] + 8, yt + 16, SEMI, 8, oc)
        txt(c, uzycie, xs[5] + 8, yt + 16, REG, 8, NAVY)
        yt += rh
    para(c, "Progi: <b>4,5:1</b> – tekst (AA), <b>7:1</b> – tekst (AAA), <b>3:1</b> – duży tekst (≥ 24 px lub ≥ 18,66 px "
         "pogrubiony) i elementy graficzne. Kolor nigdy nie jest jedynym nośnikiem informacji: odznaka wygasła różni się "
         "od aktywnej także ramką (przerywana) i ikoną (zegar zamiast ptaszka).", M, yt + 12, CW, 8.5, REG, GRAY)


def s_typo(c):
    y = page_frame(c, 6)
    txt(c, "Aa", M - 4, y + 86, BOLD, 104, NAVY)
    txt(c, "Ąę", M + 150, y + 86, XBOLD, 104, GREEN)
    txt(c, "Poppins", M, y + 140, BOLD, 24, NAVY)
    para(c, "Geometryczny krój bezszeryfowy (Indian Type Foundry, Jonny Pinhorn). Pełne polskie znaki, 5 odmian "
         "w systemie znaku. Nowoczesny, czytelny na ekranie i w druku.", M, y + 148, 380, 9.5, REG, GRAY)
    yy = y + 212
    for s in ("AĄBCĆDEĘFGHIJKLŁMNŃOÓPRSŚTUWYZŹŻ", "aąbcćdeęfghijklłmnńoóprsśtuwyzźż", "0123456789 # @ – „” · % & ? ! ( )"):
        txt(c, s, M, yy, REG, 13.5, NAVY)
        yy += 23
    label(c, "Kroje zastępcze (tylko tekst, nigdy znak)", M, yy + 14)
    para(c, "system-ui, Segoe UI, Roboto, Arial. W znaku, odznakach i naklejce tekst jest zamieniony na krzywe, "
         "więc wygląda tak samo bez zainstalowanej czcionki.", M, yy + 20, 380, 8.8, REG, GRAY)

    x = 450
    w = PW - M - x
    label(c, "Odmiany i role", x, y + 6)
    rows = [(REG, "Regular 400", "tekst ciągły, opisy"),
            (MED, "Medium 500", f"nazwa „{TXT.NAZWA_CZ1}”, podpis pod logo (wersaliki, światło +11 %)"),
            (SEMI, "SemiBold 600", "etykiety, przyciski, „PARTNER”"),
            (BOLD, "Bold 700", "hasła, nagłówki"),
            (XBOLD, "ExtraBold 800", f"„{TXT.NAZWA_CZ2}” w nazwie – tylko w znaku")]
    yt = y + 16
    for f, nazwa, rola in rows:
        line(c, x, yt, PW - M, yt, LINE, 0.5)
        txt(c, "Zażółć gęślą jaźń", x, yt + 25, f, 17, NAVY)
        txt(c, nazwa, x + 190, yt + 16, SEMI, 8.5, GREEN)
        para(c, rola, x + 190, yt + 20, w - 190, 8, REG, GRAY, leading=10.5)
        yt += 44
    line(c, x, yt, PW - M, yt, LINE, 0.5)
    label(c, "Hierarchia", x, yt + 22)
    rect(c, x, yt + 30, w, 104, fill=MINT, r=8)
    txt(c, "ZOSTAŃ PARTNEREM", x + 16, yt + 50, SEMI, 7.5, GREEN_DARK, track=1.0)
    hh = para(c, TXT.HASLO, x + 16, yt + 56, w - 32, 20, BOLD, NAVY, leading=24)
    para(c, TXT.HASLO_PODTYTUL, x + 16, yt + 60 + hh, w - 32, 8.5, REG, GRAY, leading=12)
    para(c, "<b>Licencja:</b> SIL Open Font License 1.1 – czcionkę można bezpłatnie używać, osadzać w PDF i na stronach "
         "(pliki .woff w static/brand/fonts) oraz rozpowszechniać razem z materiałami. Nie wolno sprzedawać samej czcionki.",
         M, PH - 74, CW, 8.2, REG, GRAY)


def strefa(c, s_doc, x, yt, w, xmod_units, total_w_units):
    """Rysuje plik z wbudowanym polem ochronnym i zaznacza pole."""
    d = drawing(s_doc)
    rw, rh = w, d.height * w / d.width
    k = rw / total_w_units
    xm = xmod_units * k
    c.saveState()
    c.setFillColor(hexc(MINT))
    p = c.beginPath()
    p.rect(x, Y(yt + rh), rw, rh)
    p.rect(x + xm, Y(yt + rh - xm), rw - 2 * xm, rh - 2 * xm)
    c.drawPath(p, stroke=0, fill=1, fillMode=0)   # even-odd: wypełnia tylko ramkę pola ochronnego
    c.restoreState()
    svg(c, s_doc, x, yt, w=w)
    rect(c, x, yt, rw, rh, stroke=GREEN, lw=0.8)
    rect(c, x + xm, yt + xm, rw - 2 * xm, rh - 2 * xm, stroke=GREEN, lw=0.6, dash=(3, 2))
    for ax, ay in ((x + rw / 2 - xm / 2, yt), (x + rw / 2 - xm / 2, yt + rh - xm),
                   (x, yt + rh / 2 - xm / 2), (x + rw - xm, yt + rh / 2 - xm / 2)):
        rect(c, ax, ay, xm, xm, fill=GREEN)
        txt(c, "x", ax + xm / 2, ay + xm / 2 + 3.5, BOLD, 10, WHITE, anchor="c")
    return rw, rh


def s_pole(c):
    y = page_frame(c, 7, "Pole ochronne to wolna przestrzeń wokół znaku. Nie umieszczamy w nim tekstu, innych logotypów, "
                         "krawędzi kadru ani elementów zdjęcia.")
    lg = L.logotypy_cache["poziomy"]
    sg = L.logotypy_cache["sygnet"]
    wl = float(re.search(r'width="([\d.]+)"', lg).group(1))
    ws = float(re.search(r'width="([\d.]+)"', sg).group(1))
    rw, rh = strefa(c, lg, M, y + 8, 480, L.X_LOGO, wl)
    _, sh = strefa(c, sg, M + 530, y + 8, 170, L.X_SYGNET, ws)
    txt(c, "Logo podstawowe", M, y + 8 + rh + 16, SEMI, 9.5, NAVY)
    txt(c, "Sygnet", M + 530, y + 8 + sh + 16, SEMI, 9.5, NAVY)
    ty = y + 8 + max(rh, sh) + 52
    x_mm = L.X_LOGO / VIS_W * 60
    cw = (CW - 40) / 3
    bloki = [
        ("Moduł x", "<b>x = ¼ wysokości pola sygnetu</b> (ok. połowa wysokości serca). Ten sam moduł obowiązuje "
                    "w logo, wersji kompakt i w samym sygnecie."),
        ("Jak mierzyć", "Od skrajnych punktów znaku: zewnętrznego łuku fal, czubka serca i ostatniej litery. "
                        "Pliki logotyp_tubijeaed_* mają pole ochronne już wbudowane."),
        ("Przykłady", "Logo w nagłówku strony o wysokości 40 px: x = 10 px. Logo szerokie na 60 mm: x ≈ "
                      + f"{x_mm:.1f}".replace(".", ",") + " mm. Obok znaków innych instytucji zachowaj co najmniej 2x."),
    ]
    for i, (t, d) in enumerate(bloki):
        x = M + i * (cw + 20)
        label(c, t, x, ty)
        para(c, d, x, ty + 8, cw, 9, REG, NAVY, leading=13.5)


def s_minimum(c):
    y = page_frame(c, 8, "Poniżej tych wielkości elementy znaku przestają być czytelne. Dla małych formatów są osobne wersje.")
    rows = [("Logo podstawowe (z podpisem)", "60 mm szer.", "272 px szer. (64 px wys.)", "mniejsze – użyj wersji kompakt"),
            ("Logo kompakt", "30 mm szer.", "120 px szer. (24 px wys.)", "nagłówki 32–56 px"),
            ("Sygnet", "8 mm", "24 px", "oba łuki fal czytelne"),
            ("Favicon (uproszczony sygnet)", "–", "16 i 32 px", "jedyna wersja poniżej 24 px"),
            ("Odznaka Partnera – mała", "–", "88 × 31 px", "nie pomniejszać"),
            ("Odznaka Partnera – pełna", "40 mm szer.", "200 × 60 px", "HiDPI: 400 × 120 px"),
            ("Naklejka na kapsułę AED", "75 × 105 mm", "–", "zalecana 100 × 140 mm, QR ≥ 30 mm")]
    cols = [("Element", 150), ("Druk", 72), ("Ekran", 120), ("Uwagi", 128)]
    tw = sum(w for _, w in cols)
    rect(c, M, y, tw, 20, fill=NAVY, r=4)
    x = M
    for lab, w in cols:
        txt(c, lab, x + 7, y + 13.5, SEMI, 8, WHITE)
        x += w
    yt = y + 20
    for i, row in enumerate(rows):
        if i % 2:
            rect(c, M, yt, tw, 30, fill="#F5F8F7")
        x = M
        for (lab, w), v in zip(cols, row):
            para(c, v, x + 7, yt + 7, w - 10, 8, SEMI if lab == "Element" else REG, NAVY, leading=10)
            x += w
        yt += 30
    # rzeczywista wielkość
    x0 = M + tw + 30
    label(c, "Wielkość rzeczywista (druk 100 %)", x0, y + 6)
    k = 60 * mm / (VIS_W * 0.75)
    yy = y + 20
    svg(c, LOGO, x0 - VIS[0] * 0.75 * k, yy, sx=k, sy=k)
    txt(c, "60 mm", x0, yy + LOGO_H * 0.75 * k + 12, MED, 7.5, GRAY)
    yy += LOGO_H * 0.75 * k + 30
    kv = L.bbox(KOMP_IN, KOMP_W, KOMP_H)
    k = 30 * mm / ((kv[2] - kv[0]) * 0.75)
    svg(c, KOMP, x0 - kv[0] * 0.75 * k, yy, sx=k, sy=k)
    svg(c, SYG, x0 + 120, yy - 2, w=8 * mm)
    txt(c, "30 mm", x0, yy + KOMP_H * 0.75 * k + 12, MED, 7.5, GRAY)
    txt(c, "8 mm", x0 + 120, yy + KOMP_H * 0.75 * k + 12, MED, 7.5, GRAY)
    yy += KOMP_H * 0.75 * k + 40
    label(c, "Ekran (piksele, powiększenie 3×)", x0, yy)
    yy += 10
    fav = (ROOT.parent / "2_prototyp_kod" / "static" / "brand" / "favicon.svg").read_text(encoding="utf-8")
    xx = x0
    for s_, src, lab in ((24, SYG, "sygnet 24 px"), (32, fav, "favicon 32 px"), (16, fav, "favicon 16 px")):
        im = L.png(src, width=s_)
        bg = Image.new("RGBA", im.size, WHITE)
        bg.alpha_composite(im)
        z = bg.resize((s_ * 12, s_ * 12), Image.NEAREST)
        e = s_ * 3 * 0.75          # 3× wielkości ekranowej (1 px = 0,75 pt)
        image(c, z, xx, yy, e, e)
        rect(c, xx, yy, e, e, stroke=LINE, lw=0.4)
        txt(c, lab, xx, yy + e + 12, MED, 7.5, GRAY)
        xx += e + 18
    para(c, "Favicon to uproszczony sygnet: większe serce, grubsza błyskawica i jeden gruby łuk – w 16 px drugi łuk "
         "zlewa się z pierwszym.", M, y + 20 + 7 * 30 + 16, tw, 8.5, REG, GRAY)


def zakaz_tile(c, x, yt, w, h, fn, cap):
    rect(c, x, yt, w, h, fill="#F5F8F7", r=6)
    c.saveState()
    clip(c, x, yt, w, h)
    fn(x, yt, w, h)
    c.restoreState()
    line(c, x + 8, yt + 8, x + w - 8, yt + h - 8, RED, 1.6)
    c.setFillColor(hexc(RED))
    c.circle(x + w - 12, Y(yt + 12), 8, stroke=0, fill=1)
    line(c, x + w - 15.5, yt + 8.5, x + w - 8.5, yt + 15.5, WHITE, 1.6)
    line(c, x + w - 8.5, yt + 8.5, x + w - 15.5, yt + 15.5, WHITE, 1.6)
    para(c, cap, x, yt + h + 7, w, 8, REG, NAVY, leading=10.8)


def s_zakazy(c):
    y = page_frame(c, 9, "Znak używamy tylko z oryginalnych plików. Przykłady poniżej pokazują prawdziwy znak użyty błędnie.")
    gap = 14
    w = (CW - 3 * gap) / 4
    h = 108
    lw_ = w - 36
    lk = lw_ / (LOGO_W * 0.75)

    def stretch(x, yt, w_, h_):
        sx, sy = lk * 1.2, lk * 0.62
        rw, rh = LOGO_W * 0.75 * sx, LOGO_H * 0.75 * sy
        svg(c, LOGO, x + (w_ - rw) / 2, yt + (h_ - rh) / 2, sx=sx, sy=sy)

    def colors(x, yt, w_, h_):
        s = LOGO.replace(GREEN, "#D90429").replace(NAVY, "#7B2CBF").replace(GRAY, "#F59E0B")
        svg_center(c, s, x, yt, w_, h_, lw_, h_ - 30)

    def rotate(x, yt, w_, h_):
        rw, rh = LOGO_W * 0.75 * lk, LOGO_H * 0.75 * lk
        svg(c, LOGO, x + (w_ - rw) / 2, yt + (h_ - rh) / 2, sx=lk, sy=lk, rotate=16)

    def effects(x, yt, w_, h_):
        rw, rh = LOGO_W * 0.75 * lk, LOGO_H * 0.75 * lk
        x0, y0 = x + (w_ - rw) / 2, yt + (h_ - rh) / 2
        for off, col in ((4.5, "#C3CBD3"), (3, "#A7B1BB")):
            svg(c, logo_mono(col), x0 + off, y0 + off, sx=lk, sy=lk)
        svg(c, LOGO, x0, y0, sx=lk, sy=lk)

    def bad_bg(x, yt, w_, h_):
        rect(c, x, yt, w_, h_, fill=GREEN)
        for i in range(6):
            rect(c, x + i * w_ / 5 - 10, yt, w_ / 10, h_, fill="#2E9B5C")
        svg_center(c, LOGO, x, yt, w_, h_, lw_, h_ - 30)

    def font_layout(x, yt, w_, h_):
        fnt = G.Font(SERIF) if SERIF.exists() else G.F["reg"]
        size = 70
        tw = fnt.width(TXT.NAZWA, size)
        inner = (f'<path fill="{NAVY}" d="{fnt.path(TXT.NAZWA, 0, 90, size)}"/>'
                 + G.place(G.sygnet("light"), tw + 10, 0, 130))
        svg_center(c, G.doc(tw + 150, 135, inner, "zly"), x, yt, w_, h_, lw_, h_ - 30)

    def partner(x, yt, w_, h_):
        rect(c, x + 10, yt + 14, w_ - 20, h_ - 28, fill=WHITE, stroke=LINE, r=4)
        txt(c, "sklep-przyklad.pl", x + 20, yt + 32, SEMI, 7.5, NAVY)
        for i, ww in enumerate((70, 50, 60)):
            rect(c, x + 20, yt + 40 + i * 9, ww, 4, fill="#DCE3EA", r=2)
        svg(c, G.badge("light", "pelna", date="31.12.2099"), x + w_ - 20 - 92, yt + 40, w=92)
        txt(c, "brak wpisu w dane.gov.pl", x + w_ - 20, yt + 82, SEMI, 6.5, RED, anchor="r")

    def e010(x, yt, w_, h_):
        inner = (f'<rect x="2" y="2" width="96" height="96" rx="6" fill="{GREEN}"/>'
                 f'<g transform="translate(6 8) scale(0.88)">{G.sygnet("mono", WHITE)}</g>')
        svg_center(c, G.doc(100, 100, inner, "zly"), x, yt, w_, h_, 70, 70)

    tiles = [
        (stretch, "<b>Nie rozciągaj</b> ani nie ściskaj znaku – skaluj tylko proporcjonalnie."),
        (colors, "<b>Nie zmieniaj kolorów</b> – tylko wersje z palety (podstawowa, negatyw, jednobarwne)."),
        (rotate, "<b>Nie obracaj</b> znaku i nie ustawiaj go pionowo ani po skosie."),
        (effects, "<b>Nie dodawaj efektów</b>: cienia, poświaty, obrysu, gradientu, 3D."),
        (bad_bg, "<b>Nie stawiaj na tle o niskim kontraście</b> ani na niespokojnym zdjęciu – użyj negatywu lub jasnej plakietki."),
        (font_layout, "<b>Nie zmieniaj kroju ani układu</b> – nie przestawiaj sygnetu i nazwy, nie składaj nazwy inną czcionką."),
        (partner, "<b>Bez statusu Partnera</b> nie używaj odznaki ani dopisku „Partner”. Nie kopiuj odznaki i nie zmieniaj daty."),
        (e010, "<b>Nie zamieniaj sygnetu w znak bezpieczeństwa</b> (białe serce na zielonym polu) i nie stawiaj go w miejscu ISO 7010 E010."),
    ]
    for i, (fn, cap) in enumerate(tiles):
        r, col = divmod(i, 4)
        zakaz_tile(c, M + col * (w + gap), y + r * (h + 62), w, h, fn, cap)


def e010_svg():
    inner = ('<rect x="2" y="2" width="96" height="96" rx="4" fill="#00843D"/>'
             f'<g transform="translate(46 54) scale(0.95) translate(-50 -49)"><path d="{G.HEART}" fill="#fff"/>'
             f'<path d="{G.BOLT}" fill="#00843D" transform="translate(50 48) scale(0.78) translate(-50 -47)"/></g>'
             '<path d="M80 10 V30 M70 20 H90" stroke="#fff" stroke-width="6"/>')
    return G.doc(100, 100, inner, "E010 schemat")


def s_iso(c):
    y = page_frame(c, 10, "Naklejka #TuBijeAED wisi obok oficjalnego znaku defibrylatora. Dlatego sygnet celowo różni się "
                          "od piktogramu ISO 7010 E010 – i nigdy go nie zastępuje.")
    items = [(e010_svg(), "ISO 7010 E010", "schemat poglądowy, nie oryginał", NAVY),
             (G.doc(100, 100, G.sygnet_c_poprzedni("light"), "C"), "Koncepcja C (odrzucona)",
              "białe serce na zielonym kole – w 16–24 px wygląda jak E010", GRAY),
             (SYG, "C2 „Fale nadawania” – wybrany", "zielone serce bez pola, fale zamiast krzyża", GREEN_DARK)]
    cw = 150
    for i, (s, t, d, col) in enumerate(items):
        x = M + i * (cw + 28)
        rect(c, x, y, cw, cw, fill="#F5F8F7", r=8)
        svg_center(c, s, x, y, cw, cw, 110, 110)
        txt(c, t, x, y + cw + 16, SEMI, 9, col)
        para(c, d, x, y + cw + 21, cw, 7.8, REG, GRAY, leading=10.5)
    x = M + 3 * (cw + 28) + 6
    w = PW - M - x
    rect(c, x, y, w, 200, fill=MINT, r=8)
    label(c, "Zasady przy AED", x + 16, y + 22)
    bullets(c, [
        "Naklejka i sygnet <b>nie zastępują</b> znaku E010 i nie są umieszczane na nim ani w jego miejscu.",
        "Odstęp od znaku E010 – co najmniej <b>50 mm</b>.",
        "W materiałach przy AED nie używamy zielonego pola z białym sercem (pas naklejki ma kolor mięty).",
        "Opis zawsze wskazuje cel: „Partner – dane w dane.gov.pl”.",
    ], x + 16, y + 30, w - 32, 8.6, gap=3)
    ty = y + cw + 56
    cols = [("Cecha", 140), ("ISO 7010 E010", 290), ("#TuBijeAED – sygnet C2", 0)]
    rows = [("Polaryzacja", "białe serce na zielonym polu", "zielone serce, błyskawica wycięta, brak pola"),
            ("Sylwetka", "kwadrat – tabliczka bezpieczeństwa", "asymetryczne serce z falami, bez ramki"),
            ("Element dodatkowy", "biały krzyż (pomoc medyczna)", "dwa otwarte łuki – nadawanie danych"),
            ("Znaczenie", "„tu jest defibrylator”", "„dane o tym AED są otwarte i zweryfikowane”"),
            ("Status", "znak bezpieczeństwa (PN-EN ISO 7010)", "znak akcji – nie zastępuje oznakowania")]
    rect(c, M, ty, CW, 19, fill=NAVY, r=4)
    xs = [M, M + 140, M + 430]
    for (lab, _), xx in zip(cols, xs):
        txt(c, lab, xx + 8, ty + 13, SEMI, 8, WHITE)
    ty += 19
    for i, row in enumerate(rows):
        if i % 2:
            rect(c, M, ty, CW, 21, fill="#F5F8F7")
        for j, (v, xx) in enumerate(zip(row, xs)):
            txt(c, v, xx + 8, ty + 14, SEMI if j == 0 else REG, 8.3, NAVY)
        ty += 21


def s_odznaka(c):
    y = page_frame(c, 11, f"„{TXT.PROGRAM}” – odznaka do stopki strony dostawcy, który publikuje i aktualizuje dane "
                          "o swoim AED.")
    rows = [("light", "Jasna – na jasnych stopkach", DATA_PRZYKLAD),
            ("dark", "Ciemna – na granatowych i ciemnych stopkach", DATA_PRZYKLAD),
            ("expired", "Wygasła – dane nieaktualne ponad 12 miesięcy", "22.11.2026")]
    label(c, "Pełna 200 × 60 px (powiększenie)", M, y + 6)
    label(c, "Mała 88 × 31 px", M + 256, y + 6)
    yt = y + 14
    for theme, lab, d in rows:
        txt(c, lab, M, yt + 10, SEMI, 9, NAVY)
        fw, fh = svg(c, G.badge(theme, "pelna", date=d), M, yt + 18, w=230)
        svg(c, G.badge(theme, "mala", date=d), M + 256, yt + 18, w=132)
        yt += fh + 30
    label(c, "Wielkość rzeczywista (1 px = 0,75 pt)", M, yt + 12)
    svg(c, G.badge("light", "pelna", date=DATA_PRZYKLAD), M, yt + 20, w=150)
    svg(c, G.badge("light", "mala", date=DATA_PRZYKLAD), M + 166, yt + 20, w=66)
    x = 470
    w = PW - M - x
    label(c, "Zasady", x, y + 8)
    ny = bullets(c, [
        "Odznakę otrzymuje dostawca, którego zasób AED jest w wykazie dane.gov.pl, jest poprawny i aktualny "
        "(nie starszy niż 12 miesięcy).",
        "Datę ważności wstawia system – plik pobierany jest z API, nie edytujemy go ręcznie.",
        "Po terminie odznaka sama zmienia się na <b>wygasłą</b>: szara, z przerywaną ramką i zegarem zamiast ptaszka.",
        "Odznaka zawsze linkuje do publicznej strony weryfikacji Partnera.",
        "Tekst alternatywny: „" + TXT.PROGRAM + ", ważne do DD.MM.RRRR”.",
        "Nie zmieniamy treści, kolorów ani proporcji odznaki; nie pomniejszamy poniżej 88 × 31 px.",
    ], x, y + 16, w, 8.8, gap=3)
    rect(c, x, ny + 8, w, 70, fill=MINT, r=6)
    label(c, "Kod do stopki strony", x + 12, ny + 24, GREEN_DARK)
    para(c, '&lt;a href="…/partnerzy/{id}"&gt;&lt;img src="…/api/partnerzy/{id}/odznaka.svg?wariant=jasna&amp;rozmiar=pelna" '
         f'width="200" height="60" alt="{TXT.PROGRAM}, ważne do …"&gt;&lt;/a&gt;', x + 12, ny + 30, w - 24, 7.6, REG, NAVY,
         leading=10.5)


def s_naklejka(c):
    y = page_frame(c, 12)
    nak = L.zastosowania_cache["naklejka_kapsula_aed"]
    rw, rh = svg(c, nak, M + 4, y - 8, w=100 * mm)
    txt(c, "skala 1:1 (100 × 140 mm)", M + 4, y - 8 + rh + 12, MED, 7.5, GRAY)
    x = M + rw + 40
    w = PW - M - x
    label(c, "Specyfikacja", x, y + 4)
    ny = bullets(c, [
        "Format 100 × 140 mm, narożniki zaokrąglone r = 6 mm; folia winylowa, matowa, odporna na UV i wilgoć.",
        "Kod QR (poziom korekcji M) – min. 30 mm, tu 42 mm ze strefą ciszy. Prowadzi do karty AED: godziny dostępności, "
        "zgłoszenie usterki lub zmiany danych.",
        f"Adres kodu QR i treści ustawia się w teksty_marki.py (obecnie adres zastępczy: {TXT.QR_URL}).",
        "ID AED zgodny z identyfikatorem w wykazie dane.gov.pl.",
        "Pas „na mapie” ma kolor mięty – bez zielonego pola z białym tekstem, które przypomina znak bezpieczeństwa.",
        "Dolny pas na granacie: instrukcja „Dzwoń 112 i użyj AED” dla świadka zdarzenia.",
    ], x, y + 12, w, 8.8, gap=3)
    sy = ny + 14
    label(c, "Umieszczenie na kapsule", x, sy)
    bx, by, bw, bh = x, sy + 10, 150, 150
    rect(c, bx, by, bw, bh, fill="#F5F8F7", stroke="#9AA5B1", lw=1, r=10)
    rect(c, bx + 18, by + 30, 60, 100, fill=WHITE, stroke="#C3CBD3", r=6)
    txt(c, "AED", bx + 48, by + 85, BOLD, 10, "#9AA5B1", anchor="c")
    svg(c, e010_svg(), bx + 90, by + 16, w=42)
    svg(c, nak, bx + 92, by + 80, w=38)
    line(c, bx + 136, by + 58, bx + 136, by + 80, RED, 0.8)
    txt(c, "≥ 50 mm", bx + 140, by + 72, SEMI, 7, RED)
    para(c, "Naklejkę umieszczamy na kapsule lub obok niej, na wysokości wzroku, <b>pod lub obok</b> znaku E010 – "
         "nigdy na nim ani zamiast niego. Nie zasłania instrukcji producenta ani wyświetlacza stanu urządzenia.",
         bx + bw + 16, by + 4, w - bw - 16, 8.6, REG, NAVY, leading=12.5)


def s_media(c):
    y = page_frame(c, 13, "Materiały kampanii dla dostawców danych: hasło, korzyść (odznaka) i jedno wezwanie do działania.")
    zs = L.zastosowania_cache
    svg(c, zs["kafel_social_1080"], M, y, w=300)
    txt(c, "Kafel 1080 × 1080 px (Facebook, Instagram, LinkedIn)", M, y + 314, SEMI, 8.5, NAVY)
    x = M + 330
    w = PW - M - x
    _, bh = svg(c, zs["baner_www_1200x300"], x, y, w=w)
    txt(c, "Baner www 1200 × 300 px (strona urzędu lub firmy, portale branżowe)", x, y + bh + 14, SEMI, 8.5, NAVY)
    ny = bullets(c, [
        "Hasło zawsze w Poppins Bold, jednym kolorem: biel na granacie albo granat na mięcie lub bieli.",
        "Kafel: logo kompakt w negatywie u góry, hasło, podtytuł, odznaka jako przykład korzyści dla Partnera.",
        "Baner: sygnet, hasło i przycisk z wezwaniem do działania prowadzący do formularza Partnera.",
        "Nie zestawiamy znaku z logo dane.gov.pl ani Ministerstwa Cyfryzacji bez zgody ich właścicieli.",
    ], x, y + bh + 26, w, 8.8, gap=3)
    rect(c, x, ny + 8, w, 92, fill=MINT, r=6)
    label(c, "Przykładowy wpis", x + 12, ny + 24, GREEN_DARK)
    para(c, f"{TXT.HASLO} {TXT.HASLO_PODTYTUL} {TXT.WEZWANIE}: [link do formularza]. #TuBijeAED #OtwarteDane",
         x + 12, ny + 30, w - 24, 9, REG, NAVY, leading=13)


def s_pliki(c):
    y = page_frame(c, 14)
    rows = [("logotyp_tubijeaed_poziomy.svg / .pdf", "wektor; SVG – format otwarty", "wersja podstawowa – druk, dalsza obróbka"),
            ("logotyp_tubijeaed_poziomy.png / .jpg", "3000 px; PNG przezroczyste, JPG na bieli", "www, prezentacje, dokumenty"),
            ("logotyp_tubijeaed_poziomy_negatyw.*", "SVG, PNG przezroczyste; JPG, PDF na granacie", "ciemne tła"),
            ("logotyp_tubijeaed_sygnet.*", "SVG, PDF, PNG 2000 px, JPG", "awatar, ikona, małe formaty"),
            ("Ksiega_Znaku_TuBijeAED.pdf", "PDF wektorowy, czcionki osadzone", "ten dokument"),
            ("zastosowania/naklejka_kapsula_aed.pdf", "PDF wektorowy 100 × 140 mm", "druk naklejki"),
            ("zastosowania/naklejka_kapsula_aed_bez_qr.*", "SVG, PDF, PNG", "naklejka bez kodu QR (prezentacje)"),
            ("zastosowania/naklejka_wspolpraca_mc.*", "SVG, PDF, PNG – PROJEKT", "program Partner; wymaga zgody MC"),
            ("zastosowania/kafel_social_1080, baner_www_1200x300", "SVG i PNG", "kampania w sieci"),
            ("2_prototyp_kod/static/brand/", "SVG, PNG, CSS, WOFF", "serwis: logo-kompakt, favicon, odznaki, tokeny")]
    cols = [("Plik", 290), ("Format", 250), ("Zastosowanie", 0)]
    xs = [M, M + 290, M + 540]
    rect(c, M, y, CW, 20, fill=NAVY, r=4)
    for (lab, _), xx in zip(cols, xs):
        txt(c, lab, xx + 8, y + 13.5, SEMI, 8, WHITE)
    ty = y + 20
    for i, row in enumerate(rows):
        if i % 2:
            rect(c, M, ty, CW, 22, fill="#F5F8F7")
        for j, (v, xx) in enumerate(zip(row, xs)):
            txt(c, v, xx + 8, ty + 14.5, MED if j == 0 else REG, 8.3, NAVY)
        ty += 22
    ty += 18
    cw = (CW - 24) / 2
    rect(c, M, ty, cw, 120, fill=MINT, r=8)
    label(c, "Źródło i aktualizacja", M + 16, ty + 22, GREEN_DARK)
    para(c, "Wszystkie pliki i ta księga są generowane skryptem z jednego źródła:<br/>"
         "<b>.venv/bin/python 3_branding/generuj_ksiege.py</b><br/>"
         "Hasło, podpis pod logo, teksty odznaki i naklejki oraz adres kodu QR zmienia się w jednym pliku: "
         "<b>3_branding/teksty_marki.py</b>. Rysunek znaku: 3_branding/final/generuj_final.py.",
         M + 16, ty + 30, cw - 32, 8.8, REG, NAVY, leading=13)
    x = M + cw + 24
    rect(c, x, ty, cw, 120, fill="#F5F8F7", r=8)
    label(c, "Licencje i zastrzeżenia", x + 16, ty + 22)
    para(c, "Czcionka Poppins: Copyright 2020 The Poppins Project Authors, SIL Open Font License 1.1 (fonts/OFL.txt). "
         f"Znak {TXT.NAZWA} jest projektem konkursowym ({TXT.KSIEGA_KONTEKST}); nie jest oficjalnym znakiem Ministerstwa "
         "Cyfryzacji ani portalu dane.gov.pl. Piktogram ISO 7010 E010 pokazano wyłącznie schematycznie, do porównania.",
         x + 16, ty + 30, cw - 32, 8.8, REG, NAVY, leading=13)


STRONY = [s_idea, s_budowa, s_warianty, s_kolory, s_kontrast, s_typo, s_pole, s_minimum, s_zakazy, s_iso,
          s_odznaka, s_naklejka, s_media, s_pliki]


def build():
    c = canvas.Canvas(str(OUT), pagesize=(PW, PH), initialFontName=REG, initialFontSize=10)
    c.setTitle(f"{TXT.NAZWA} – Księga znaku")
    c.setAuthor(f"Zespół {TXT.KSIEGA_KONTEKST}")
    c.setSubject(f"Księga znaku akcji {TXT.NAZWA}: {TXT.HASLO}")
    okladka(c)
    c.showPage()
    for fn in STRONY:
        fn(c)
        c.showPage()
    c.save()


def podglady():
    if PODGLAD.exists():
        shutil.rmtree(PODGLAD)
    PODGLAD.mkdir()
    subprocess.run(["pdftoppm", "-r", "50", "-png", str(OUT), str(PODGLAD / "strona")], check=True)


def main():
    lg, zs = L.main()
    L.logotypy_cache, L.zastosowania_cache = lg, zs
    build()
    if BRAKI:
        raise SystemExit(f"BŁĄD: znaki spoza Poppins: {''.join(sorted(BRAKI))}")
    msg = f"Księga: {OUT} ({TOTAL} stron)"
    if G.PODGLADY:
        try:
            podglady()
            msg += f"; podglądy: {PODGLAD}"
        except FileNotFoundError:
            print("(brak pdftoppm – pomijam podglądy)")
    print(msg)


if __name__ == "__main__":
    main()
