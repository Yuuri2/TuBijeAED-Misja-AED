"""Generator koncepcji znaku #TuBijeAED (Sprint 1, do wyboru przez człowieka).

Tworzy w tym katalogu:
  koncepcja_{A,B,C}.svg            – logo poziome (jasne tło)
  koncepcja_{A,B,C}_negatyw.svg    – logo poziome na ciemnym tle
  koncepcja_{A,B,C}_sygnet.svg     – sam sygnet (ikona)
  odznaka_{A,B,C}_{jasna,ciemna}_{mala,pelna}.svg – odznaka Partnera (88x31 i 200x60)
  naklejka_{A,B,C}.svg             – szkic naklejki na kapsułę AED (100x140 mm, miejsce na QR)
  plansza_koncepcji.png            – plansza porównawcza

Tekst jest od razu zamieniany na krzywe (fontTools) – SVG wyglądają identycznie
w każdej przeglądarce i nie wymagają zainstalowanej czcionki.
Czcionka: Poppins (SIL OFL 1.1), pliki w ./fonts.

Uruchomienie (fontTools jest w .venv projektu):
  .venv/bin/python 3_branding/koncepcje/generuj_koncepcje.py

Sprint 2: wybrano koncepcję C. Zasoby finalne (static/brand/, warianty ISO, podglądy) generuje
3_branding/final/generuj_final.py, który korzysta z klasy Font z tego modułu.
"""
from __future__ import annotations

import io
from pathlib import Path

import cairosvg
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"

# ---------------------------------------------------------------- paleta
P = {
    "green": "#00843D",   # Zieleń AED  ~ Pantone 348 C / RAL 6032 (zieleń znaków ewakuacyjnych/AED)
    "navy": "#0B2545",    # Granat nocny – tekst
    "red": "#D90429",     # Czerwień pulsu – tylko akcent na białym
    "lgreen": "#5FD38D",  # Zieleń sygnałowa – tekst/akcent na ciemnym tle
    "mint": "#E8F5EE",    # Mięta – tła jasne
    "white": "#FFFFFF",
    "gray": "#5B6770",    # Szary tekst pomocniczy
    "line": "#C9D6CF",    # obramowania
    "dark": "#0B2545",
}


# ---------------------------------------------------------------- tekst -> krzywe
class Font:
    def __init__(self, path: Path):
        self.f = TTFont(str(path))
        self.gs = self.f.getGlyphSet()
        self.cmap = self.f.getBestCmap()
        self.upm = self.f["head"].unitsPerEm
        self.hmtx = self.f["hmtx"]
        self.pairs: dict[tuple[str, str], int] = {}
        self.class_tables = []
        self._load_kern()

    def _load_kern(self):
        if "GPOS" not in self.f:
            return
        gpos = self.f["GPOS"].table
        idx = set()
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "kern":
                idx.update(fr.Feature.LookupListIndex)
        for li in sorted(idx):
            lk = gpos.LookupList.Lookup[li]
            for st in lk.SubTable:
                if lk.LookupType == 9:
                    st = st.ExtSubTable
                if getattr(st, "LookupType", 2) != 2 and not hasattr(st, "PairSet") and not hasattr(st, "Class1Record"):
                    continue
                if getattr(st, "Format", None) == 1 and hasattr(st, "PairSet"):
                    cov = st.Coverage.glyphs
                    for i, ps in enumerate(st.PairSet):
                        for pvr in ps.PairValueRecord:
                            v = pvr.Value1
                            xa = getattr(v, "XAdvance", 0) if v else 0
                            if xa:
                                self.pairs.setdefault((cov[i], pvr.SecondGlyph), xa)
                elif getattr(st, "Format", None) == 2 and hasattr(st, "Class1Record"):
                    self.class_tables.append(st)

    def kern(self, a: str, b: str) -> int:
        if (a, b) in self.pairs:
            return self.pairs[(a, b)]
        for st in self.class_tables:
            if a not in st.Coverage.glyphs:
                continue
            c1 = st.ClassDef1.classDefs.get(a, 0)
            c2 = st.ClassDef2.classDefs.get(b, 0)
            v = st.Class1Record[c1].Class2Record[c2].Value1
            xa = getattr(v, "XAdvance", 0) if v else 0
            if xa:
                return xa
        return 0

    def glyphs(self, text):
        return [self.cmap[ord(c)] for c in text]

    def width(self, text: str, size: float, track: float = 0) -> float:
        g = self.glyphs(text)
        units = sum(self.hmtx[n][0] for n in g) + sum(self.kern(a, b) for a, b in zip(g, g[1:]))
        return units * size / self.upm + track * (len(g) - 1)

    def path(self, text: str, x: float, y: float, size: float, track: float = 0) -> str:
        s = size / self.upm
        g = self.glyphs(text)
        cur = 0.0
        parts = []
        for i, n in enumerate(g):
            pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
            tp = TransformPen(pen, (s, 0, 0, -s, x + cur, y))
            self.gs[n].draw(tp)
            parts.append(pen.getCommands())
            cur += self.hmtx[n][0] * s + track
            if i + 1 < len(g):
                cur += self.kern(n, g[i + 1]) * s
        return " ".join(p for p in parts if p)


F = {
    "reg": Font(FONTS / "Poppins-Regular.ttf"),
    "med": Font(FONTS / "Poppins-Medium.ttf"),
    "semi": Font(FONTS / "Poppins-SemiBold.ttf"),
    "bold": Font(FONTS / "Poppins-Bold.ttf"),
    "xbold": Font(FONTS / "Poppins-ExtraBold.ttf"),
}


def T(font: str, text: str, x: float, y: float, size: float, fill: str, track: float = 0, anchor: str = "start"):
    """Tekst jako ścieżka. Zwraca (svg, szerokość)."""
    f = F[font]
    w = f.width(text, size, track)
    if anchor == "middle":
        x -= w / 2
    elif anchor == "end":
        x -= w
    d = f.path(text, x, y, size, track)
    return f'<path fill="{fill}" d="{d}"><title>{text}</title></path>', w


def runs(parts, x, y, size, anchor="start", gap=0.0):
    """Ciąg fragmentów [(font, tekst, kolor)] w jednej linii, z kerningiem tylko wewnątrz fragmentu."""
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


def svg_doc(w, h, inner, bg=None, title="", unit=""):
    bgr = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    size = f'width="{w}{unit}" height="{h}{unit}"'
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" {size} viewBox="0 0 {w} {h}" role="img" aria-label="{title}">'
            f'<title>{title}</title>{bgr}{inner}</svg>\n')


# ---------------------------------------------------------------- sygnety (układ 0..100)
HEART = ("M50 86 C47 80 12 60 12 35 C12 20 23 10 36 10 C43 10 48 14 50 19 "
         "C52 14 57 10 64 10 C77 10 88 20 88 35 C88 60 53 80 50 86 Z")


def sygnet_A(theme="light"):
    """Serce, które jest pinezką: ostry czubek wskazuje miejsce (TU), linia EKG (BIJE)."""
    shadow = P["mint"] if theme == "light" else "#1C4A3A"
    heart_pin = ("M50 92 C45 79 11 60 11 34 C11 19 22 8 36 8 C43 8 48 12 50 17 "
                 "C52 12 57 8 64 8 C78 8 89 19 89 34 C89 60 55 79 50 92 Z")
    return (f'<ellipse cx="50" cy="94" rx="15" ry="3.6" fill="{shadow}"/>'
            f'<path d="{heart_pin}" fill="{P["green"]}"/>'
            f'<polyline points="21,40 35,40 41,27 50,56 57,33 62,40 79,40" fill="none" stroke="#FFFFFF" '
            f'stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/>')


def sygnet_B(theme="light"):
    """Hashtag z sercem w samym środku – zielony kafel jak ikona aplikacji / znak AED.
    (Wariant z linią EKG wewnątrz „#” odrzucony: przy 48 px czytał się jak litera „N”.)"""
    heart = ("M50 79 C47 74 21 58 21 38 C21 27 29 19 39 19 C44 19 48 22 50 26 "
             "C52 22 56 19 61 19 C71 19 79 27 79 38 C79 58 53 74 50 79 Z")
    g = P["green"]
    return (f'<rect x="2" y="2" width="96" height="96" rx="24" fill="{g}"/>'
            '<g stroke="#FFFFFF" stroke-width="9" stroke-linecap="round">'
            '<line x1="38" y1="16" x2="32" y2="84"/>'
            '<line x1="68" y1="16" x2="62" y2="84"/>'
            '<line x1="15" y1="36" x2="85" y2="36"/>'
            '<line x1="15" y1="64" x2="85" y2="64"/>'
            '</g>'
            f'<g transform="translate(50 50) scale(0.56) translate(-50 -49.5)">'
            f'<path d="{heart}" fill="#FFFFFF" stroke="{g}" stroke-width="9" stroke-linejoin="round"/></g>')


def sygnet_C(theme="light"):
    """Puls „tu jestem”: fale rozchodzące się od serca z błyskawicą (symbol AED)."""
    r1, r2 = ("#D3EDDD", "#8CCCA6") if theme == "light" else ("#173D33", "#1F6B48")
    bolt = "M53 22 L37 50 L48 50 L42 72 L63 41 L52 41 L58 22 Z"
    heart = ("M50 79 C47 74 21 58 21 38 C21 27 29 19 39 19 C44 19 48 22 50 26 "
             "C52 22 56 19 61 19 C71 19 79 27 79 38 C79 58 53 74 50 79 Z")
    return (f'<circle cx="50" cy="50" r="49" fill="{r1}"/>'
            f'<circle cx="50" cy="50" r="40" fill="{r2}"/>'
            f'<circle cx="50" cy="50" r="31" fill="{P["green"]}"/>'
            f'<g transform="translate(50 50) scale(0.62) translate(-50 -49)">'
            f'<path d="{heart}" fill="#FFFFFF"/>'
            f'<path d="{bolt}" fill="{P["green"]}" transform="translate(50 48) scale(0.78) translate(-50 -47)"/>'
            '</g>')


SYGNET = {"A": sygnet_A, "B": sygnet_B, "C": sygnet_C}


def place(sygnet_svg, x, y, size):
    return f'<g transform="translate({x:.2f} {y:.2f}) scale({size / 100:.4f})">{sygnet_svg}</g>'


# ---------------------------------------------------------------- logo poziome
def logo(concept, theme="light"):
    """Zwraca (inner_svg, w, h). Margines = pole ochronne (wysokość „A” w AED ≈ x)."""
    navy = P["navy"] if theme == "light" else P["white"]
    green_t = P["green"] if theme == "light" else P["lgreen"]
    pad = 40
    if concept == "A":
        s = 150
        size = 82
        txt, tw = runs([("bold", "#TuBije", navy), ("bold", "AED", green_t)], 0, 0, size)
        h = s + 2 * pad
        x_t = pad + s + 26
        base = pad + s / 2 + size * 0.36
        txt, tw = runs([("bold", "#TuBije", navy), ("bold", "AED", green_t)], x_t, base, size, gap=size * 0.02)
        w = x_t + tw + pad
        return place(sygnet_A(theme), pad, pad, s) + txt, w, h
    if concept == "B":
        s = 140
        size = 80
        h = s + 2 * pad
        x_t = pad + s + 28
        base = pad + s / 2 + size * 0.36
        t1, w1 = T("xbold", "#TuBije", x_t, base, size, navy)
        aw = F["xbold"].width("AED", size)
        px = x_t + w1 + 10
        ph_top = base - size * 0.74
        pill_w = aw + 34
        pill_h = size * 0.98
        pill = (f'<rect x="{px:.1f}" y="{ph_top:.1f}" width="{pill_w:.1f}" height="{pill_h:.1f}" '
                f'rx="{pill_h * 0.28:.1f}" fill="{P["green"]}"/>')
        t2, _ = T("xbold", "AED", px + 17, base, size, "#FFFFFF")
        w = px + pill_w + pad
        return place(sygnet_B(theme), pad, pad, s) + t1 + pill + t2, w, h
    if concept == "C":
        s = 160
        size = 78
        h = s + 2 * pad
        x_t = pad + s + 28
        base = pad + 98
        txt, tw = runs([("med", "#TuBije", navy), ("xbold", "AED", green_t)], x_t, base, size, gap=size * 0.03)
        sub_c = P["gray"] if theme == "light" else "#C5D3E0"
        sub, sw = T("med", "DEFIBRYLATORY NA MAPIE · OTWARTE DANE", x_t + 3, base + 40, 19.5, sub_c, track=2.2)
        w = x_t + max(tw, sw + 3) + pad
        return place(sygnet_C(theme), pad, pad, s) + txt + sub, w, h
    raise ValueError(concept)


# ---------------------------------------------------------------- odznaki Partnera
def check_icon(x, y, d, bg, fg="#FFFFFF"):
    r = d / 2
    return (f'<circle cx="{x + r:.2f}" cy="{y + r:.2f}" r="{r:.2f}" fill="{bg}"/>'
            f'<polyline points="{x + d * .27:.2f},{y + d * .52:.2f} {x + d * .44:.2f},{y + d * .68:.2f} {x + d * .74:.2f},{y + d * .35:.2f}" '
            f'fill="none" stroke="{fg}" stroke-width="{d * .14:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')


def badge(concept, theme="light", size="pelna"):
    light = theme == "light"
    bg = "#FFFFFF" if light else P["navy"]
    border = P["line"] if light else "#2C4A6B"
    t_main = P["navy"] if light else "#FFFFFF"
    t_green = P["green"] if light else P["lgreen"]
    t_sub = P["gray"] if light else "#C5D3E0"
    syg = SYGNET[concept](theme)
    if size == "mala":
        W, H = 88, 31
        inner = f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="4" fill="{bg}" stroke="{border}"/>'
        inner += place(syg, 3.5, 3.5, 24)
        inner += check_icon(19.5, 18.5, 10, t_green if not light else P["green"], bg)
        x0 = 31
        avail = W - x0 - 3
        fs = 10.5
        while F["bold"].width("#TuBijeAED", fs) > avail:
            fs -= 0.1
        inner += T("semi", "PARTNER", x0, 12.2, 7.6, t_green, track=0.55)[0]
        inner += runs([("bold", "#TuBije", t_main), ("bold", "AED", t_green)], x0, 24.5, fs)[0]
        title = "Partner #TuBijeAED – zweryfikowane w dane.gov.pl"
        return svg_doc(W, H, inner, title=title), W, H
    W, H = 200, 60
    inner = f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="7" fill="{bg}" stroke="{border}"/>'
    inner += place(syg, 7, 8, 44)
    x0 = 58
    avail = W - x0 - 7
    inner += T("semi", "PARTNER", x0, 17.5, 9, t_green, track=1.1)[0]
    fs = 18
    while F["bold"].width("#TuBijeAED", fs) > avail:
        fs -= 0.1
    inner += runs([("bold", "#TuBije", t_main), ("bold", "AED", t_green)], x0, 36, fs)[0]
    fs2 = 9
    label = "zweryfikowane w dane.gov.pl"
    while F["med"].width(label, fs2) + 12 > avail:
        fs2 -= 0.05
    inner += check_icon(x0, 42.2, 9, P["green"] if light else P["lgreen"], bg)
    inner += T("med", label, x0 + 12, 49.6, fs2, t_sub)[0]
    title = "Partner #TuBijeAED – zweryfikowane w dane.gov.pl"
    return svg_doc(W, H, inner, title=title), W, H


# ---------------------------------------------------------------- naklejka na kapsułę AED (mm)
def sticker(concept):
    W, H = 100, 140
    o = [f'<rect x="0" y="0" width="{W}" height="{H}" rx="6" fill="#FFFFFF" stroke="{P["line"]}" stroke-width="0.4"/>']
    # nagłówek: sygnet + nazwa
    o.append(place(SYGNET[concept]("light"), 8, 8, 20))
    hdr, hw = runs([("bold", "#TuBije", P["navy"]), ("bold", "AED", P["green"])], 32, 21.5, 10.5)
    o.append(hdr)
    o.append(T("semi", "PARTNER · ZWERYFIKOWANE W DANE.GOV.PL", 32, 26.6, 2.55, P["gray"], track=0.12)[0])
    # pas zielony
    o.append(f'<rect x="0" y="34" width="{W}" height="17" fill="{P["green"]}"/>')
    o.append(T("bold", "Ten defibrylator jest na mapie", W / 2, 44.6, 5.6, "#FFFFFF", anchor="middle")[0])
    # QR + opis
    qx, qy, qs = 8, 58, 38
    o.append(f'<rect x="{qx}" y="{qy}" width="{qs}" height="{qs}" rx="1.5" fill="#FFFFFF" stroke="{P["navy"]}" '
             f'stroke-width="0.5" stroke-dasharray="2 1.5"/>')
    for (cx, cy) in [(qx + 3, qy + 3), (qx + qs - 11, qy + 3), (qx + 3, qy + qs - 11)]:
        o.append(f'<rect x="{cx}" y="{cy}" width="8" height="8" fill="none" stroke="{P["navy"]}" stroke-width="1.6"/>'
                 f'<rect x="{cx + 2.6}" y="{cy + 2.6}" width="2.8" height="2.8" fill="{P["navy"]}"/>')
    o.append(T("semi", "KOD QR", qx + qs / 2, qy + qs / 2 + 0.5, 3.6, P["gray"], anchor="middle")[0])
    o.append(T("reg", "min. 30 × 30 mm", qx + qs / 2, qy + qs / 2 + 5, 2.6, P["gray"], anchor="middle")[0])
    tx = qx + qs + 5
    lines = [("bold", "Zeskanuj:", P["navy"], 4.2),
             ("med", "sprawdź godziny", P["navy"], 3.6),
             ("med", "dostępności,", P["navy"], 3.6),
             ("med", "zgłoś usterkę", P["navy"], 3.6),
             ("med", "lub zmianę danych.", P["navy"], 3.6)]
    yy = qy + 6
    for f, t, c, s in lines:
        o.append(T(f, t, tx, yy, s, c)[0])
        yy += s * 1.45 if f != "bold" else 6.2
    o.append(T("semi", "ID AED: PL-0000-0000", tx, qy + qs - 1.5, 3, P["gray"])[0])
    # pas granatowy – 112
    o.append(f'<path d="M0 104 H{W} V134 a6 6 0 0 1 -6 6 H6 a6 6 0 0 1 -6 -6 Z" fill="{P["navy"]}"/>')
    o.append(T("semi", "Nagłe zatrzymanie krążenia?", W / 2, 114.2, 4.4, "#FFFFFF", anchor="middle")[0])
    o.append(runs([("bold", "Dzwoń ", "#FFFFFF"), ("xbold", "112", P["lgreen"]), ("bold", " i użyj AED", "#FFFFFF")],
                  W / 2, 124.8, 6.6, anchor="middle")[0])
    o.append(T("med", "Urządzenie poprowadzi Cię głosem krok po kroku.", W / 2, 132.4, 3.05, "#C5D3E0", anchor="middle")[0])
    return svg_doc(W, H, "".join(o), title=f"Naklejka #TuBijeAED – koncepcja {concept}", unit="mm")


# ---------------------------------------------------------------- render
def png(svg: str, width=None, height=None) -> Image.Image:
    data = cairosvg.svg2png(bytestring=svg.encode(), output_width=width, output_height=height)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def main():
    out = {}
    for c in "ABC":
        for theme, suffix, bg in [("light", "", None), ("dark", "_negatyw", P["navy"])]:
            inner, w, h = logo(c, theme)
            out[f"koncepcja_{c}{suffix}.svg"] = svg_doc(round(w), h, inner, bg=bg, title="#TuBijeAED")
        out[f"koncepcja_{c}_sygnet.svg"] = svg_doc(100, 100, SYGNET[c]("light"), title="#TuBijeAED – sygnet")
        out[f"koncepcja_{c}_sygnet_negatyw.svg"] = svg_doc(100, 100, SYGNET[c]("dark"), bg=P["navy"],
                                                            title="#TuBijeAED – sygnet")
        for theme, tn in [("light", "jasna"), ("dark", "ciemna")]:
            for sz in ("mala", "pelna"):
                out[f"odznaka_{c}_{tn}_{sz}.svg"] = badge(c, theme, sz)[0]
        out[f"naklejka_{c}.svg"] = sticker(c)
    for name, s in out.items():
        (ROOT / name).write_text(s, encoding="utf-8")
    build_board(out)
    print(f"zapisano {len(out)} plików SVG + plansza_koncepcji.png")


def build_board(out):
    W = 2400
    col_w = 760
    margin = 40
    gutter = (W - 2 * margin - 3 * col_w) // 2
    bold = ImageFont.truetype(str(FONTS / "Poppins-Bold.ttf"), 40)
    semi = ImageFont.truetype(str(FONTS / "Poppins-SemiBold.ttf"), 22)
    reg = ImageFont.truetype(str(FONTS / "Poppins-Regular.ttf"), 20)
    titleF = ImageFont.truetype(str(FONTS / "Poppins-Bold.ttf"), 52)

    names = {"A": "A · Serce-pinezka", "B": "B · Serce hashtagu", "C": "C · Puls „tu jestem”"}
    H = 3030
    board = Image.new("RGB", (W, H), "#F3F6F4")
    d = ImageDraw.Draw(board)
    d.text((margin, 30), "#TuBijeAED – koncepcje znaku do wyboru (Sprint 1)", font=titleF, fill=P["navy"])
    d.text((margin, 100), "Czcionka: Poppins (OFL) zamieniona na krzywe · zieleń AED #00843D (~Pantone 348 C / RAL 6032) · "
           "każda koncepcja: logo jasne i negatyw, sygnet 128/48/24 px, odznaka 88×31 i 200×60, naklejka 100×140 mm",
           font=reg, fill=P["gray"])
    for i, c in enumerate("ABC"):
        x = margin + i * (col_w + gutter)
        y = 160
        d.text((x, y), names[c], font=bold, fill=P["navy"])
        y += 70
        # logo jasne
        for theme, bg in [("light", "#FFFFFF"), ("dark", P["navy"])]:
            box_h = 240
            d.rounded_rectangle([x, y, x + col_w, y + box_h], 16, fill=bg,
                                outline=P["line"] if theme == "light" else None)
            inner, w, h = logo(c, theme)
            sc = min((col_w - 40) / w, (box_h - 30) / h)
            im = png(svg_doc(round(w), h, inner, title="x"), width=int(w * sc))
            board.paste(im, (x + (col_w - im.width) // 2, y + (box_h - im.height) // 2), im)
            y += box_h + 16
        # sygnety
        lab_y = y
        d.text((x, lab_y), "Sygnet: 128 px · 48 px · 24 px · 15 mm @ 150 dpi (≈ 89 px)", font=semi, fill=P["gray"])
        y += 36
        for theme, bg in [("light", "#FFFFFF"), ("dark", P["navy"])]:
            d.rounded_rectangle([x, y, x + col_w, y + 160], 16, fill=bg, outline=P["line"] if theme == "light" else None)
            sx = x + 20
            for s in (128, 48, 24, 89):
                im = png(svg_doc(100, 100, SYGNET[c](theme), title="x"), width=s)
                board.paste(im, (sx, y + (160 - s) // 2), im)
                sx += s + 40
            y += 176
        # odznaki
        d.text((x, y), "Odznaka Partnera: 200×60 (pow. 2×) · 88×31 (pow. 2× i 1:1)", font=semi, fill=P["gray"])
        y += 36
        for theme in ("light", "dark"):
            bg = "#FFFFFF" if theme == "light" else "#E1E7E4"
            d.rounded_rectangle([x, y, x + col_w, y + 150], 16, fill="#FFFFFF" if theme == "light" else "#DCE3DF",
                                outline=P["line"])
            s_full, W2, H2 = badge(c, theme, "pelna")
            im = png(s_full, width=W2 * 2)
            board.paste(im, (x + 16, y + 15), im)
            s_small, W3, H3 = badge(c, theme, "mala")
            im = png(s_small, width=W3 * 2)
            board.paste(im, (x + 16 + 400 + 24, y + 15), im)
            im = png(s_small, width=W3)
            board.paste(im, (x + 16 + 400 + 24, y + 15 + 62 + 16), im)
            y += 166
        # naklejka
        d.text((x, y), "Naklejka na kapsułę AED (100×140 mm, szkic)", font=semi, fill=P["gray"])
        y += 36
        sh = 600
        im = png(out[f"naklejka_{c}.svg"], height=sh)
        d.rounded_rectangle([x, y, x + col_w, y + sh + 40], 16, fill="#DCE3DF")
        board.paste(im, (x + (col_w - im.width) // 2, y + 20), im)
        y += sh + 60
    board = board.crop((0, 0, W, y))
    board.save(ROOT / "plansza_koncepcji.png", optimize=True)


if __name__ == "__main__":
    main()
