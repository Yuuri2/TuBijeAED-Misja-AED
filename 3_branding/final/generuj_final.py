"""Generator zasobów finalnych #TuBijeAED – koncepcja C, sygnet w wariancie C2 „Fale nadawania” (decyzja: C2, Sprint 2).

Zapisuje:
  2_prototyp_kod/static/brand/
    logo.svg, logo-negatyw.svg, sygnet.svg, favicon.svg, favicon-32.png, apple-touch-icon.png
    odznaka-{jasna,ciemna}-{pelna,mala}.svg, odznaka-wygasla-{pelna,mala}.svg
    marker-wykaz.svg, marker-partner.svg, marker-osm.svg
    fonts/Poppins-*.woff (podzbiór łaciński + polski) + OFL.txt
  3_branding/final/
    warianty_iso/*.svg               – warianty odróżniające znak od ISO 7010 E010 (do decyzji)
    podglad/*.png                    – podglądy PNG (cairosvg)

Tekst w znaku i odznakach jest zamieniony na krzywe (fontTools). Wyjątek: data ważności
odznaki (`<text id="wazny-do">`) jest żywym tekstem, bo podmienia ją Backend
(placeholder `DD.MM.RRRR`, opis w static/brand/README.md).

Teksty (nazwa, podpis pod logo, napisy odznaki) pochodzą z 3_branding/teksty_marki.py.
Pliki do oddania (logotyp_tubijeaed_*), zastosowania i Księgę znaku tworzą 3_branding/generuj_logotypy.py
i 3_branding/generuj_ksiege.py – ten drugi uruchamia też ten skrypt.

Uruchomienie (z katalogu repo):
  .venv/bin/python 3_branding/final/generuj_final.py      # tylko static/brand
  .venv/bin/python 3_branding/generuj_ksiege.py           # wszystko
"""
from __future__ import annotations

import io
import re
import shutil
import sys
from pathlib import Path

import cairosvg
from fontTools import subset
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
BRAND = REPO / "2_prototyp_kod" / "static" / "brand"
PODGLAD = ROOT / "podglad"
WARIANTY = ROOT / "warianty_iso"
FONTS = ROOT.parent / "koncepcje" / "fonts"

sys.path.insert(0, str(ROOT.parent / "koncepcje"))
sys.path.insert(0, str(ROOT.parent))
import generuj_koncepcje as K  # noqa: E402  (klasa Font + kerning z Sprintu 1)
import teksty_marki as TXT  # noqa: E402  (JEDNO miejsce tekstów: nazwa, podpis, hasło, odznaka)

F = K.F

# ---------------------------------------------------------------- paleta (= tokens.css)
GREEN = "#00843D"        # --kolor-glowny
GREEN_DARK = "#006A31"   # --kolor-glowny-ciemny
NAVY = "#0B2545"         # --kolor-tekst
GRAY = "#4A5568"         # --kolor-tekst-drugorzedny
LGREEN = "#5FD38D"       # --kolor-akcent-na-ciemnym
LGRAY_ON_DARK = "#C5D3E0"
WHITE = "#FFFFFF"
LINE = "#C9D6CF"
LINE_DARK = "#2C4A6B"
# szarości odznaki wygasłej
X_TEXT = "#4A5568"       # 7,53:1 na bieli
X_SUB = "#5B6770"        # 5,80:1 na bieli
X_CORE = "#6B7785"       # 4,56:1 z bielą (biały znak na szarym)
X_RING1, X_RING2 = "#EDF0F3", "#C3CBD3"

FONT_STACK = "Poppins, 'Segoe UI', Roboto, Arial, sans-serif"
PLACEHOLDER = "DD.MM.RRRR"
TITLE_BADGE = TXT.PROGRAM


# ---------------------------------------------------------------- pomocnicze
def T(font: str, text: str, x: float, y: float, size: float, fill: str, track: float = 0, anchor: str = "start"):
    """Tekst jako ścieżka (bez <title> w środku – opis ma tylko korzeń SVG). Zwraca (svg, szerokość)."""
    f = F[font]
    w = f.width(text, size, track)
    if anchor == "middle":
        x -= w / 2
    elif anchor == "end":
        x -= w
    return f'<path fill="{fill}" d="{f.path(text, x, y, size, track)}"/>', w


def runs(parts, x, y, size, gap=0.0, anchor="start"):
    widths = [F[f].width(t, size) for f, t, _ in parts]
    total = sum(widths) + gap * (len(parts) - 1)
    if anchor == "middle":
        x -= total / 2
    elif anchor == "end":
        x -= total
    out = []
    for (f, t, c), w in zip(parts, widths):
        out.append(T(f, t, x, y, size, c)[0])
        x += w + gap
    return "".join(out), total


def doc(w, h, inner, title, desc="", bg=None):
    """SVG z role=img, <title> (i opcjonalnie <desc>); bez skryptów i zewnętrznych odwołań."""
    d = f"<desc>{desc}</desc>" if desc else ""
    bgr = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{d}{bgr}{inner}</svg>\n')


def place(svg, x, y, size):
    return f'<g transform="translate({x:.2f} {y:.2f}) scale({size / 100:.4f})">{svg}</g>'


# ---------------------------------------------------------------- sygnet C (układ 0..100)
HEART = ("M50 79 C47 74 21 58 21 38 C21 27 29 19 39 19 C44 19 48 22 50 26 "
         "C52 22 56 19 61 19 C71 19 79 27 79 38 C79 58 53 74 50 79 Z")
BOLT = "M53 22 L37 50 L48 50 L42 72 L63 41 L52 41 L58 22 Z"


def sygnet_c_poprzedni(theme="light"):
    """Koncepcja C z Sprintu 1 (białe serce na zielonym kole) – zastąpiona przez C2, zostaje do porównania."""
    rings = {"light": ("#D3EDDD", "#8CCCA6", GREEN),
             "dark": ("#173D33", "#1F6B48", GREEN),
             "expired": (X_RING1, X_RING2, X_CORE)}[theme]
    r1, r2, core = rings
    return (f'<circle cx="50" cy="50" r="49" fill="{r1}"/>'
            f'<circle cx="50" cy="50" r="40" fill="{r2}"/>'
            f'<circle cx="50" cy="50" r="31" fill="{core}"/>'
            f'<g transform="translate(50 50) scale(0.62) translate(-50 -49)">'
            f'<path d="{HEART}" fill="#FFFFFF"/>'
            f'<path d="{BOLT}" fill="{core}" transform="translate(50 48) scale(0.78) translate(-50 -47)"/>'
            '</g>')


def tpath(d: str, fn) -> str:
    """Przekształca ścieżkę złożoną z bezwzględnych M/L/C/Z punkt po punkcie (fn: (x, y) -> (x, y))."""
    out, nums = [], []
    for tok in re.findall(r"[MLCZ]|-?\d+(?:\.\d+)?", d):
        if tok.isalpha():
            out.append(tok)
        else:
            nums.append(float(tok))
            if len(nums) == 2:
                x, y = fn(*nums)
                out.append(f"{x:.3f} {y:.3f}")
                nums = []
    return " ".join(out)


def _heart_xy(x, y):
    return 44 + 0.9 * (x - 50), 56 + 0.9 * (y - 49)


def _bolt_xy(x, y):
    return _heart_xy(50 + 0.78 * (x - 50), 48 + 0.78 * (y - 47))


# Serce z błyskawicą WYCIĘTĄ (fill-rule evenodd) – błyskawica ma zawsze kolor podłoża, na każdym tle.
HEART_C2 = tpath(HEART, _heart_xy) + " " + tpath(BOLT, _bolt_xy)
# Środek fal (wspólny dla obu łuków) i promienie – siatka konstrukcyjna w księdze znaku.
FALE_SRODEK, FALE_R = (57.2, 42.8), (30, 42)


def sygnet(theme="light", color=None):
    """DECYZJA: C2 „Fale nadawania” – zielone serce z wyciętą błyskawicą, bez zielonego pola,
    + 2 otwarte łuki sygnału w prawym górnym rogu (odróżnia znak od ISO 7010 E010).
    theme: light (jasne tło) | dark (granat) | expired (szary, odznaka wygasła) | mono (color=…, oba łuki pełne)."""
    if color or theme == "mono":
        heart = arc = color or NAVY
        op = ""
    else:
        heart = arc = {"light": GREEN, "dark": LGREEN, "expired": X_CORE}[theme]
        op = ' opacity=".55"'
    return (f'<path d="{HEART_C2}" fill="{heart}" fill-rule="evenodd"/>'
            f'<path d="M66 14 A30 30 0 0 1 86 34" fill="none" stroke="{arc}" stroke-width="6" stroke-linecap="round"/>'
            f'<path d="M70 3 A42 42 0 0 1 97 30" fill="none" stroke="{arc}" stroke-width="6" stroke-linecap="round"{op}/>')


def favicon_inner():
    """Uproszczony C2 do 16/32 px: większe serce, grubsza błyskawica, jeden gruby łuk (drugi znika w 16 px)."""
    bolt = "M55 18 L33 53 L46 53 L39 82 L68 41 L54 41 L62 18 Z"
    return (f'<g transform="translate(40 60) scale(1.12) translate(-50 -49)">'
            f'<path d="{HEART}" fill="{GREEN}"/>'
            f'<path d="{bolt}" fill="#FFFFFF" transform="translate(50 49) scale(0.74) translate(-50 -49)"/></g>'
            f'<path d="M64 8 A30 30 0 0 1 92 36" fill="none" stroke="{GREEN}" stroke-width="11" stroke-linecap="round"/>')


# ---------------------------------------------------------------- logo poziome
def podpis_rozmiar(tw: float, size=19.5, track=2.2) -> tuple[float, float]:
    """Rozmiar i światło podpisu: domyślnie 19,5/2,2; dłuższy podpis zmniejszamy do szerokości nazwy."""
    sw = F["med"].width(TXT.PODPIS_LOGO, size, track)
    if sw + 3 > tw:
        k = (tw - 3) / sw
        size, track = size * k, track * k
    return size, track


def logo(theme="light", sygnet_fn=None, kompakt=False, pad=0, color=None, podpis=True):
    """Logo poziome. Domyślnie BEZ wbudowanego pola ochronnego (ciasny viewBox – łatwiej skalować w UI);
    pole ochronne = 1/4 wysokości sygnetu, opis w README. kompakt=True – bez podpisu (nagłówki < 64 px).
    theme: light | dark; color="#000000" itp. – wersja monochromatyczna (jeden kolor, pełne łuki).
    Teksty: teksty_marki.NAZWA_CZ1/NAZWA_CZ2/PODPIS_LOGO."""
    if color:
        navy = green_t = sub_c = color
        syg = sygnet("mono", color)
    else:
        navy = NAVY if theme == "light" else WHITE
        green_t = GREEN if theme == "light" else LGREEN
        sub_c = GRAY if theme == "light" else LGRAY_ON_DARK
        syg = (sygnet_fn or sygnet)(theme)
    s = 160
    h = s + 2 * pad
    x_t = pad + s + 28
    name = [("med", TXT.NAZWA_CZ1, navy), ("xbold", TXT.NAZWA_CZ2, green_t)]
    if kompakt:
        size = 100
        base = pad + s / 2 + F["med"].f["OS/2"].sCapHeight * size / F["med"].upm / 2
        txt, tw = runs(name, x_t, base, size, gap=size * 0.03)
        w = round(x_t + tw + pad + 2)
        return place(syg, pad, pad, s) + txt, w, h
    size = 78
    base = pad + 98
    txt, tw = runs(name, x_t, base, size, gap=size * 0.03)
    sub = ""
    if podpis:
        ssize, strack = podpis_rozmiar(tw)
        sub, _ = T("med", TXT.PODPIS_LOGO, x_t + 3, base + 40, ssize, sub_c, track=strack)
    w = round(x_t + tw + pad + 2)
    return place(syg, pad, pad, s) + txt + sub, w, h


# ---------------------------------------------------------------- odznaki
def check_icon(x, y, d, bg, fg):
    r = d / 2
    return (f'<circle cx="{x + r:.2f}" cy="{y + r:.2f}" r="{r:.2f}" fill="{bg}"/>'
            f'<polyline points="{x + d * .27:.2f},{y + d * .52:.2f} {x + d * .44:.2f},{y + d * .68:.2f} '
            f'{x + d * .74:.2f},{y + d * .35:.2f}" fill="none" stroke="{fg}" stroke-width="{d * .14:.2f}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def clock_icon(x, y, d, bg, fg):
    """Ikona „wygasło” (zegar) – inny kształt niż ptaszek, nie tylko inny kolor."""
    r = d / 2
    cx, cy = x + r, y + r
    return (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{bg}"/>'
            f'<polyline points="{cx:.2f},{cy - r * .55:.2f} {cx:.2f},{cy:.2f} {cx + r * .45:.2f},{cy + r * .3:.2f}" '
            f'fill="none" stroke="{fg}" stroke-width="{d * .13:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')


def live_text_el(text, x, y, size, fill, anchor="start", weight=500):
    """Żywy tekst do podmiany przez Backend (id="wazny-do")."""
    return (f'<text id="wazny-do" x="{x}" y="{y}" font-family="{FONT_STACK}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{text}</text>')


def badge(theme="light", size="pelna", date=None):
    """theme: light | dark | expired. date="22.11.2027" – data wstawiona od razu jako krzywe (podglądy, księga);
    domyślnie żywy tekst z placeholderem DD.MM.RRRR do podmiany przez Backend."""
    def live_text(text, x, y, size, fill, anchor="start", weight=500):
        if date is None:
            return live_text_el(text, x, y, size, fill, anchor, weight)
        return T("med", text.replace(PLACEHOLDER, date), x, y, size, fill, anchor=anchor)[0]

    expired = theme == "expired"
    light = theme in ("light", "expired")
    bg = WHITE if light else NAVY
    border = (X_SUB if expired else LINE) if light else LINE_DARK
    t_main = X_TEXT if expired else (NAVY if light else WHITE)
    t_green = X_SUB if expired else (GREEN if light else LGREEN)
    t_sub = X_SUB if expired else (GRAY if light else LGRAY_ON_DARK)
    dash = ' stroke-dasharray="4 2.5"' if expired else ""
    syg = sygnet("expired" if expired else theme)
    if expired:
        title = f"Odznaka Partnera #TuBijeAED wygasła {PLACEHOLDER} – dane wymagają ponownej weryfikacji w dane.gov.pl"
    else:
        title = f"{TITLE_BADGE}, ważne do {PLACEHOLDER}"

    if size == "mala":
        W, H = 88, 31
        inner = (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="4" fill="{bg}" '
                 f'stroke="{border}"{dash}/>')
        inner += place(syg, 2.5, 3, 24)  # C2: serce w lewym dolnym rogu, ptaszek obok czubka
        icon = clock_icon if expired else check_icon
        inner += icon(20, 19.5, 9.5, X_SUB if expired else (GREEN if light else LGREEN), bg)
        x0 = 31
        fs = 10.5
        while F["bold"].width("#TuBijeAED", fs) > W - x0 - 3:
            fs -= 0.1
        lab = TXT.ODZNAKA_WYGASLA if expired else TXT.ODZNAKA_ETYKIETA
        ls = 7.6
        while F["semi"].width(lab, ls, 0.55) > W - x0 - 3:
            ls -= 0.1
        inner += T("semi", lab, x0, 12.2, ls, t_green, track=0.55)[0]
        inner += runs([("bold", TXT.NAZWA_CZ1, t_main), ("bold", TXT.NAZWA_CZ2, t_green)], x0, 24.5, fs)[0]
        return doc(W, H, inner, title)

    W, H = 200, 60
    inner = (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="7" fill="{bg}" '
             f'stroke="{border}"{dash}/>')
    inner += place(syg, 7, 8, 44)
    x0 = 58
    avail = W - x0 - 7
    inner += T("semi", TXT.ODZNAKA_ETYKIETA, x0, 17.5, 9, t_green, track=1.1)[0]
    fs = 18
    while F["bold"].width("#TuBijeAED", fs) > avail:
        fs -= 0.1
    inner += runs([("bold", TXT.NAZWA_CZ1, t_main), ("bold", TXT.NAZWA_CZ2, t_green)], x0, 36, fs)[0]
    if expired:
        inner += clock_icon(x0, 42.2, 9, X_SUB, bg)
        inner += live_text(f"wygasła {PLACEHOLDER}", x0 + 12, 49.6, 8.6, t_sub)
    else:
        # data ważności w prawym górnym rogu, wyrównana do prawej (odporna na inną czcionkę zastępczą)
        inner += live_text(f"do {PLACEHOLDER}", W - 7, 17.5, 8, t_sub, anchor="end")
        label = TXT.ODZNAKA_WERYFIKACJA
        fs2 = 9
        while F["med"].width(label, fs2) + 12 > avail:
            fs2 -= 0.05
        inner += check_icon(x0, 42.2, 9, GREEN if light else LGREEN, bg)
        inner += T("med", label, x0 + 12, 49.6, fs2, t_sub)[0]
    return doc(W, H, inner, title)


# ---------------------------------------------------------------- markery mapy (viewBox 32×40 / 32×32)
PIN = "M16 39 C14.6 34.6 3 26.5 3 15.5 C3 8.3 8.8 2.5 16 2.5 C23.2 2.5 29 8.3 29 15.5 C29 26.5 17.4 34.6 16 39 Z"
BUBBLE = "M7 2.5 H25 A4.5 4.5 0 0 1 29.5 7 V25 A4.5 4.5 0 0 1 25 29.5 H20.5 L16 38.5 L11.5 29.5 H7 A4.5 4.5 0 0 1 2.5 25 V7 A4.5 4.5 0 0 1 7 2.5 Z"


def heart_bolt(cx, cy, scale, bolt_fill):
    return (f'<g transform="translate({cx} {cy}) scale({scale}) translate(-50 -49)">'
            f'<path d="{HEART}" fill="#FFFFFF"/>'
            f'<path d="{BOLT}" fill="{bolt_fill}" transform="translate(50 48) scale(0.8) translate(-50 -47)"/></g>')


def marker_wykaz():
    """Okrągła pinezka (kropla) – AED z wykazu zbiorczego."""
    inner = (f'<path d="{PIN}" fill="{GREEN}" stroke="{NAVY}" stroke-width="3.2" stroke-linejoin="round"/>'
             f'<path d="{PIN}" fill="{GREEN}" stroke="#FFFFFF" stroke-width="1.4" stroke-linejoin="round"/>'
             + heart_bolt(16, 16.2, 0.36, GREEN))
    return doc(32, 40, inner, "AED z wykazu zbiorczego",
               "Znacznik w kształcie okrągłej pinezki: defibrylator z wykazu zbiorczego AED w dane.gov.pl")


def marker_partner():
    """Kwadratowy dymek ze wstążką ✓ – AED Partnera #TuBijeAED (też z wykazu)."""
    inner = (f'<path d="{BUBBLE}" fill="{NAVY}" stroke="{NAVY}" stroke-width="3.2" stroke-linejoin="round"/>'
             f'<path d="{BUBBLE}" fill="{NAVY}" stroke="#FFFFFF" stroke-width="1.4" stroke-linejoin="round"/>'
             + heart_bolt(14.6, 17.4, 0.33, NAVY)
             + f'<circle cx="24.2" cy="8" r="6.3" fill="{LGREEN}" stroke="{NAVY}" stroke-width="1.4"/>'
             f'<polyline points="21.3,8.1 23.4,10.2 27.1,6" fill="none" stroke="{NAVY}" stroke-width="2" '
             f'stroke-linecap="round" stroke-linejoin="round"/>')
    return doc(32, 40, inner, "AED Partnera #TuBijeAED (zweryfikowany)",
               "Znacznik w kształcie kwadratowego dymku z ptaszkiem: defibrylator z wykazu, "
               "którego dostawca jest Partnerem #TuBijeAED")


def marker_osm():
    """Romb z przerywaną krawędzią i „?” – punkt z OpenStreetMap do weryfikacji (nie w wykazie)."""
    q, _ = T("bold", "?", 16, 21.6, 15, "#4A5568", anchor="middle")
    inner = ('<path d="M16 1.5 L30.5 16 L16 30.5 L1.5 16 Z" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="3.5" '
             'stroke-linejoin="round"/>'
             '<path d="M16 2.5 L29.5 16 L16 29.5 L2.5 16 Z" fill="#FFFFFF" stroke="#4A5568" stroke-width="2" '
             'stroke-dasharray="3.4 2.2" stroke-linejoin="round"/>' + q)
    return doc(32, 32, inner, "Punkt AED z OpenStreetMap – do weryfikacji",
               "Znacznik w kształcie rombu z przerywaną krawędzią i znakiem zapytania: punkt z OpenStreetMap "
               "(licencja ODbL), nie jest częścią wykazu")


# ---------------------------------------------------------------- warianty względem ISO 7010 E010
EKG = "M24 47 H37 L42 37 L49 60 L55 31 L60 47 H76"


def wariant_c1(theme="light"):
    """C1 „Puls w sercu”: błyskawicę (rdzeń E010) zastępuje linia EKG wychodząca poza serce w fale."""
    r1, r2 = ("#D3EDDD", "#8CCCA6") if theme == "light" else ("#173D33", "#1F6B48")
    return (f'<circle cx="50" cy="50" r="49" fill="{r1}"/>'
            f'<circle cx="50" cy="50" r="40" fill="{r2}"/>'
            f'<circle cx="50" cy="50" r="31" fill="{GREEN}"/>'
            f'<g transform="translate(50 50) scale(0.62) translate(-50 -49)"><path d="{HEART}" fill="#FFFFFF"/></g>'
            f'<polyline points="33,50 39,50 43.5,42 49,59 54.5,37 58.5,50 67,50" fill="none" stroke="{GREEN}" '
            'stroke-width="4.6" stroke-linecap="round" stroke-linejoin="round"/>')


def wariant_c2(theme="light"):
    """C2 „Fale nadawania” – od Sprintu 2 to jest sygnet() (decyzja: C2)."""
    return sygnet(theme)


def logo_variant(sygnet_fn, theme="light"):
    return logo(theme, sygnet_fn=sygnet_fn)


# ---------------------------------------------------------------- czcionki (podzbiór woff)
UNICODES = ("U+0020-007E,U+00A0-00FF,U+0104-0107,U+0118-0119,U+0141-0144,U+015A-015B,U+0179-017C,"
            "U+00D3,U+00F3,U+2013-2014,U+2018-201E,U+2022,U+2026,U+20AC,U+2116,U+2190-2193")


def build_fonts():
    out = BRAND / "fonts"
    out.mkdir(parents=True, exist_ok=True)
    try:
        import brotli  # noqa: F401
        flavor, ext = "woff2", "woff2"
    except ImportError:
        flavor, ext = "woff", "woff"   # woff (zlib) – bez dodatkowych zależności, wspierany przez wszystkie przeglądarki
    for name in ("Regular", "Medium", "SemiBold", "Bold", "ExtraBold"):
        opts = subset.Options()
        opts.flavor = flavor
        opts.layout_features = ["kern", "liga", "calt", "locl", "tnum", "lnum"]
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        font = subset.load_font(str(FONTS / f"Poppins-{name}.ttf"), opts)
        s = subset.Subsetter(opts)
        s.populate(unicodes=subset.parse_unicodes(UNICODES))
        s.subset(font)
        subset.save_font(font, str(out / f"Poppins-{name}.{ext}"), opts)
    shutil.copy(FONTS / "OFL_Poppins.txt", out / "OFL.txt")
    return ext


# ---------------------------------------------------------------- render
def png(svg: str, width=None, height=None) -> Image.Image:
    data = cairosvg.svg2png(bytestring=svg.encode(), output_width=width, output_height=height)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def on_bg(im: Image.Image, bg: str, pad=16) -> Image.Image:
    base = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), bg)
    base.alpha_composite(im, (pad, pad))
    return base


def zoom(im: Image.Image, f: int) -> Image.Image:
    return im.resize((im.width * f, im.height * f), Image.NEAREST)


def main():
    BRAND.mkdir(parents=True, exist_ok=True)
    PODGLAD.mkdir(parents=True, exist_ok=True)
    WARIANTY.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    for theme, suf in (("light", ""), ("dark", "-negatyw")):
        inner, w, h = logo(theme)
        files[f"logo{suf}.svg"] = doc(w, h, inner, f"{TXT.NAZWA} – {TXT.PODPIS_LOGO.lower()}")
        inner, w, h = logo(theme, kompakt=True)
        files[f"logo-kompakt{suf}.svg"] = doc(w, h, inner, "#TuBijeAED")
    files["sygnet.svg"] = doc(100, 100, sygnet("light"), "#TuBijeAED")
    files["favicon.svg"] = doc(100, 100, favicon_inner(), "#TuBijeAED")
    for theme, tn in (("light", "jasna"), ("dark", "ciemna"), ("expired", "wygasla")):
        for sz in ("pelna", "mala"):
            files[f"odznaka-{tn}-{sz}.svg"] = badge(theme, sz)
    files["marker-wykaz.svg"] = marker_wykaz()
    files["marker-partner.svg"] = marker_partner()
    files["marker-osm.svg"] = marker_osm()
    for name, s in files.items():
        (BRAND / name).write_text(s, encoding="utf-8")
    png(files["favicon.svg"], 32).save(BRAND / "favicon-32.png", optimize=True)
    touch = Image.new("RGBA", (180, 180), WHITE)
    touch.alpha_composite(png(files["favicon.svg"], 150), (15, 15))
    touch.convert("RGB").save(BRAND / "apple-touch-icon.png", optimize=True)
    ext = build_fonts()

    # warianty ISO
    var = {
        "C1_puls_sygnet.svg": doc(100, 100, wariant_c1("light"), "#TuBijeAED – wariant C1"),
        "C1_puls_sygnet_negatyw.svg": doc(100, 100, wariant_c1("dark"), "#TuBijeAED – wariant C1", bg=NAVY),
        "C2_fale_sygnet.svg": doc(100, 100, wariant_c2("light"), "#TuBijeAED – wariant C2"),
        "C2_fale_sygnet_negatyw.svg": doc(100, 100, wariant_c2("dark"), "#TuBijeAED – wariant C2", bg=NAVY),
    }
    for key, fn in (("C1_puls", wariant_c1), ("C2_fale", wariant_c2)):
        inner, w, h = logo_variant(fn, "light")
        var[f"{key}_logo.svg"] = doc(w, h, inner, "#TuBijeAED")
    for name, s in var.items():
        (WARIANTY / name).write_text(s, encoding="utf-8")

    build_previews(files, var)
    print(f"static/brand: {len(files)} SVG + favicon PNG + fonty .{ext}; warianty_iso: {len(var)}; podglądy w {PODGLAD}")


def build_previews(files, var):
    navy = NAVY
    # logo
    on_bg(png(files["logo.svg"], 760), WHITE, 20).save(PODGLAD / "logo.png")
    on_bg(png(files["logo-negatyw.svg"], 760), navy, 20).save(PODGLAD / "logo-negatyw.png")
    # logo w nagłówku (48 px wysokości) – czy podpis jest czytelny
    # nagłówek 48 px: logo z podpisem, kompakt jasny i negatyw
    hdr = Image.new("RGBA", (620, 230), WHITE)
    hdr.alpha_composite(png(files["logo.svg"], height=48), (12, 12))
    hdr.alpha_composite(png(files["logo-kompakt.svg"], height=48), (12, 84))
    nb = Image.new("RGBA", (620, 72), NAVY)
    nb.alpha_composite(png(files["logo-kompakt-negatyw.svg"], height=48), (12, 12))
    nb.alpha_composite(png(files["logo-negatyw.svg"], height=48), (300, 12))
    hdr.alpha_composite(nb, (0, 152))
    hdr.save(PODGLAD / "logo-naglowek.png")
    # sygnet + favicon w małych rozmiarach: wiersz 1 sygnet 16/24/32/48 (×4, NEAREST),
    # wiersz 2 favicon 16/32 (×4), wiersz 3 favicon 1:1 na jasnej i ciemnej karcie przeglądarki
    row = Image.new("RGBA", (900, 330), WHITE)
    x = 10
    for s in (16, 24, 32, 48):
        row.alpha_composite(zoom(png(files["sygnet.svg"], s), 4), (x, 10))
        x += s * 4 + 20
    x = 10
    for s in (16, 32):
        row.alpha_composite(zoom(png(files["favicon.svg"], s), 4), (x, 220 - s * 4 + 10))
        x += s * 4 + 20
    for i, tab in enumerate(("#F1F3F4", "#202124")):
        tx = x + 20 + i * 150
        ImageDraw.Draw(row).rounded_rectangle([tx, 180, tx + 130, 230], 8, fill=tab)
        row.alpha_composite(png(files["favicon.svg"], 16), (tx + 12, 197))
        row.alpha_composite(png(files["favicon.svg"], 32), (tx + 50, 189))
    row.alpha_composite(png(files["sygnet.svg"], 64), (x + 20, 250))
    row.save(PODGLAD / "sygnet-favicon-male.png")
    # odznaki: 2× i 1:1
    sheet = Image.new("RGBA", (980, 520), "#E9EEF0")
    y = 10
    for tn in ("jasna", "ciemna", "wygasla"):
        full = files[f"odznaka-{tn}-pelna.svg"].replace(PLACEHOLDER, "22.11.2027")
        small = files[f"odznaka-{tn}-mala.svg"].replace(PLACEHOLDER, "22.11.2027")
        sheet.alpha_composite(png(full, 400), (10, y))
        sheet.alpha_composite(png(full, 200), (430, y))
        sheet.alpha_composite(png(small, 176), (650, y))
        sheet.alpha_composite(png(small, 88), (850, y))
        y += 140 + 30
    sheet.save(PODGLAD / "odznaki.png")
    # markery na tle przypominającym kafelki OSM, w 28/32/36 px + legenda ×3
    tile = Image.new("RGBA", (620, 300), "#F2EFE9")
    d = ImageDraw.Draw(tile)
    d.rectangle([0, 120, 620, 140], fill="#FFFFFF")
    d.rectangle([300, 0, 316, 300], fill="#F7D8A5")
    d.rectangle([420, 170, 600, 290], fill="#C8E6C0")
    x = 20
    for name in ("marker-wykaz", "marker-partner", "marker-osm"):
        for s in (28, 32, 36):
            im = png(files[f"{name}.svg"], width=s)
            tile.alpha_composite(im, (x, 40))
            x += s + 12
        x += 20
    x = 20
    for name in ("marker-wykaz", "marker-partner", "marker-osm"):
        im = png(files[f"{name}.svg"], width=96)
        tile.alpha_composite(im, (x, 160))
        x += 140
    tile.save(PODGLAD / "markery.png")
    # warianty ISO – plansza
    board = Image.new("RGBA", (1500, 760), WHITE)
    dr = ImageDraw.Draw(board)
    fnt = ImageFont.truetype(str(FONTS / "Poppins-SemiBold.ttf"), 26)
    fsm = ImageFont.truetype(str(FONTS / "Poppins-Regular.ttf"), 20)
    cols = [("C (poprzedni)", doc(100, 100, sygnet_c_poprzedni("light"), "x"),
             doc(100, 100, sygnet_c_poprzedni("dark"), "x", bg=NAVY), None),
            ("C1 „Puls w sercu”", var["C1_puls_sygnet.svg"], var["C1_puls_sygnet_negatyw.svg"], var["C1_puls_logo.svg"]),
            ("C2 „Fale nadawania” – WYBRANY", var["C2_fale_sygnet.svg"], var["C2_fale_sygnet_negatyw.svg"], var["C2_fale_logo.svg"])]
    for i, (lab, light, dark, lg) in enumerate(cols):
        x = 30 + i * 490
        dr.text((x, 20), lab, font=fnt, fill=NAVY)
        board.alpha_composite(png(light, 180), (x, 70))
        board.alpha_composite(png(dark, 180), (x + 200, 70))
        xs = x
        for s in (48, 32, 24, 16):
            board.alpha_composite(png(light, s), (xs, 280))
            xs += s + 14
        if lg:
            board.alpha_composite(png(lg, 440), (x, 360))
    dr.text((30, 520), "Porównanie z ISO 7010 E010 (schemat): zielone pole, białe serce, błyskawica, biały krzyż.",
            font=fsm, fill=GRAY)
    e010 = ('<rect x="2" y="2" width="96" height="96" rx="4" fill="#00843D"/>'
            f'<g transform="translate(46 54) scale(0.95) translate(-50 -49)"><path d="{HEART}" fill="#fff"/>'
            f'<path d="{BOLT}" fill="#00843D" transform="translate(50 48) scale(0.78) translate(-50 -47)"/></g>'
            '<path d="M80 10 V30 M70 20 H90" stroke="#fff" stroke-width="6"/>')
    board.alpha_composite(png(doc(100, 100, e010, "E010 schemat"), 160), (30, 560))
    dr.text((210, 620), "Schemat poglądowy, nie oryginalny piktogram.", font=fsm, fill=GRAY)
    board.save(PODGLAD / "warianty-iso.png")


if __name__ == "__main__":
    main()
