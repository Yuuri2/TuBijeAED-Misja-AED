"""#TuBijeAED – pliki logotypu do oddania + zastosowania (koncepcja C, sygnet C2 „Fale nadawania”).

Uruchomienie (z katalogu repo):
    .venv/bin/python 3_branding/generuj_logotypy.py
(albo .venv/bin/python 3_branding/generuj_ksiege.py – przegeneruje też to i księgę znaku).

Teksty (nazwa, podpis pod logo, hasło, odznaka, naklejka, adres QR): 3_branding/teksty_marki.py.
Rysunek znaku (sygnet, logo, odznaki): 3_branding/final/generuj_final.py – ten skrypt najpierw go uruchamia,
więc static/brand/ zawsze zgadza się z plikami do oddania.

Zapisuje:
  3_branding/logotyp_tubijeaed_{poziomy,poziomy_negatyw,sygnet}.{svg,png,jpg,pdf}
      SVG  – format otwarty, tło przezroczyste, wbudowane pole ochronne (x = 1/4 wysokości sygnetu)
      PNG  – tło przezroczyste, 3000 px (logo) / 2000 px (sygnet) szerokości
      JPG  – tło białe (podstawowy, sygnet) lub granatowe (negatyw)
      PDF  – wektorowy (cairosvg z SVG), negatyw na granatowym tle
  3_branding/zastosowania/
      naklejka_kapsula_aed.{svg,pdf,png}  – naklejka 100×140 mm z prawdziwym kodem QR (segno)
      kafel_social_1080.{svg,png}         – kafel do mediów społecznościowych dla dostawców danych
      baner_www_1200x300.{svg,png}        – baner www
Tekst jest zamieniony na krzywe – pliki nie wymagają zainstalowanej czcionki.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import cairosvg
import segno
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final"))
import teksty_marki as TXT  # noqa: E402
import generuj_final as G  # noqa: E402

ZAST = ROOT / "zastosowania"
PREFIX = "logotyp_tubijeaed_"
F, T, runs, place, doc = G.F, G.T, G.runs, G.place, G.doc
GREEN, NAVY, GRAY, LGREEN, WHITE = G.GREEN, G.NAVY, G.GRAY, G.LGREEN, G.WHITE
GREEN_DARK, LGRAY = G.GREEN_DARK, G.LGRAY_ON_DARK
MINT = "#E8F5EE"

SYGNET_POLE = 160            # wysokość pola sygnetu w logo (jednostki SVG)
X_LOGO = SYGNET_POLE / 4     # moduł pola ochronnego logo = 1/4 wysokości sygnetu
X_SYGNET = 100 / 4           # to samo dla samego sygnetu (pole 100×100)


# ---------------------------------------------------------------- pomocnicze
def png(svg: str, width=None, height=None) -> Image.Image:
    data = cairosvg.svg2png(bytestring=svg.encode(), output_width=width, output_height=height)
    return Image.open(io.BytesIO(data)).convert("RGBA")


def bbox(inner: str, w: float, h: float, scale=8) -> tuple[float, float, float, float]:
    """Widoczny prostokąt rysunku (x0, y0, x1, y1) w jednostkach SVG – z rastra alfa (dokładność 1/scale)."""
    im = png(doc(w, h, inner, "bbox"), width=round(w * scale))
    k = im.width / w
    x0, y0, x1, y1 = im.getchannel("A").getbbox()
    return x0 / k, y0 / k, x1 / k, y1 / k


def z_polem(inner: str, w: float, h: float, x: float) -> tuple[str, float, float, tuple]:
    """Przesuwa rysunek tak, by wokół widocznego kształtu było dokładnie x pola ochronnego."""
    x0, y0, x1, y1 = bbox(inner, w, h)
    W, H = round(x1 - x0 + 2 * x, 1), round(y1 - y0 + 2 * x, 1)
    return f'<g transform="translate({x - x0:.2f} {x - y0:.2f})">{inner}</g>', W, H, (x0, y0, x1, y1)


def wrap(font: str, text: str, size: float, maxw: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and F[font].width(cand, size) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def para(font, text, x, y, size, maxw, fill, lh=1.25, max_lines=None, min_size=8, balance=False):
    """Akapit zawijany do maxw; jeśli nie mieści się w max_lines, zmniejsza czcionkę. y = linia bazowa 1. wiersza.
    balance=True – wyrównuje długości wierszy (bez „sierotki” typu jedno słowo w ostatnim wierszu)."""
    while True:
        lines = wrap(font, text, size, maxw)
        if max_lines is None or len(lines) <= max_lines or size <= min_size:
            break
        size *= 0.96
    if balance and len(lines) > 1:
        n, w = len(lines), maxw
        while w > 50 and len(wrap(font, text, size, w - 5)) == n:
            w -= 5
        lines = wrap(font, text, size, w)
    out = "".join(T(font, ln, x, y + i * size * lh, size, fill)[0] for i, ln in enumerate(lines))
    return out, size, len(lines)


def fit(font, text, size, maxw, track=0):
    while F[font].width(text, size, track) > maxw:
        size -= 0.25
    return size


def save_set(name: str, svg: str, w: float, px_width: int, jpg_bg: str, pdf_bg: str | None):
    svg_path = ROOT / f"{PREFIX}{name}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    im = png(svg, width=px_width)
    im.save(ROOT / f"{PREFIX}{name}.png", optimize=True)
    bg = Image.new("RGBA", im.size, jpg_bg)
    bg.alpha_composite(im)
    bg.convert("RGB").save(ROOT / f"{PREFIX}{name}.jpg", quality=95, subsampling=0)
    pdf_svg = svg
    if pdf_bg is not None:  # tło musi być pod rysunkiem – wstawiamy je zaraz po <title>…</title>
        head, rest = svg.split("</title>", 1)
        pdf_svg = f'{head}</title><rect x="-1" y="-1" width="{w + 2}" height="9999" fill="{pdf_bg}"/>{rest}'
    cairosvg.svg2pdf(bytestring=pdf_svg.encode(), write_to=str(ROOT / f"{PREFIX}{name}.pdf"))


# ---------------------------------------------------------------- logotypy do oddania
def logotypy() -> dict[str, str]:
    """Zwraca SVG (z polem ochronnym) – używa ich też księga znaku."""
    out = {}
    tytul = f"{TXT.NAZWA} – {TXT.PODPIS_LOGO.lower()}"
    for theme, name, jpg_bg, pdf_bg in (("light", "poziomy", WHITE, None), ("dark", "poziomy_negatyw", NAVY, NAVY)):
        inner, w, h = G.logo(theme)
        inner, W, H, _ = z_polem(inner, w, h, X_LOGO)
        svg = doc(W, H, inner, tytul)
        save_set(name, svg, W, 3000, jpg_bg, pdf_bg)
        out[name] = svg
    inner, W, H, _ = z_polem(G.sygnet("light"), 100, 100, X_SYGNET)
    svg = doc(W, H, inner, f"{TXT.NAZWA} – sygnet")
    save_set("sygnet", svg, W, 2000, WHITE, None)
    out["sygnet"] = svg
    return out


# ---------------------------------------------------------------- kod QR (segno → ścieżka SVG)
def qr_path(url: str, x: float, y: float, size: float, fill: str) -> str:
    qr = segno.make(url, error="m", micro=False)
    rows = [list(r) for r in qr.matrix]
    n = len(rows) + 8                      # strefa ciszy: 4 moduły z każdej strony
    m = size / n
    d = []
    for j, row in enumerate(rows):
        i = 0
        while i < len(row):
            if row[i]:
                k = i
                while k < len(row) and row[k]:
                    k += 1
                d.append(f"M{x + (i + 4) * m:.3f} {y + (j + 4) * m:.3f}h{(k - i) * m:.3f}v{m:.3f}h{-(k - i) * m:.3f}z")
                i = k
            else:
                i += 1
    return f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="#FFFFFF"/><path fill="{fill}" d="{"".join(d)}"/>'


# ---------------------------------------------------------------- naklejka na kapsułę AED (mm)
def naklejka() -> str:
    """100×140 mm. Bez zielonego pola z białym sercem (odróżnienie od ISO 7010 E010): pas w kolorze mięty."""
    W, H = 100, 140
    o = [f'<rect x="0.2" y="0.2" width="{W - 0.4}" height="{H - 0.4}" rx="6" fill="#FFFFFF" stroke="{G.LINE}" '
         'stroke-width="0.4"/>']
    o.append(place(G.sygnet("light"), 6, 6, 24))
    hs = fit("bold", TXT.NAZWA, 11, W - 33 - 6)
    o.append(runs([("bold", TXT.NAZWA_CZ1, NAVY), ("bold", TXT.NAZWA_CZ2, GREEN)], 33, 20.5, hs)[0])
    ns = fit("semi", TXT.NAKLEJKA_NAGLOWEK, 2.55, W - 33 - 5, 0.12)
    o.append(T("semi", TXT.NAKLEJKA_NAGLOWEK, 33, 26.2, ns, GRAY, track=0.12)[0])
    o.append(f'<rect x="0" y="34" width="{W}" height="16" fill="{MINT}"/>')
    ps = fit("bold", TXT.NAKLEJKA_PAS, 5.6, W - 12)
    o.append(T("bold", TXT.NAKLEJKA_PAS, W / 2, 44.2, ps, GREEN_DARK, anchor="middle")[0])
    qx, qy, qs = 5, 54, 42
    o.append(qr_path(TXT.QR_URL, qx, qy, qs, NAVY))
    tx = qx + qs + 3
    yy = qy + 9
    for i, t in enumerate(TXT.NAKLEJKA_QR_OPIS):
        f, s = ("bold", 4.2) if i == 0 else ("med", 3.6)
        o.append(T(f, t, tx, yy, min(s, fit(f, t, s, W - tx - 4)), NAVY)[0])
        yy += 6.2 if i == 0 else s * 1.45
    o.append(T("semi", TXT.NAKLEJKA_ID, tx, qy + qs - 5, fit("semi", TXT.NAKLEJKA_ID, 3, W - tx - 4), GRAY)[0])
    o.append(f'<path d="M0 102 H{W} V134 a6 6 0 0 1 -6 6 H6 a6 6 0 0 1 -6 -6 Z" fill="{NAVY}"/>')
    o.append(T("semi", "Nagłe zatrzymanie krążenia?", W / 2, 113, 4.4, WHITE, anchor="middle")[0])
    o.append(runs([("bold", "Dzwoń ", WHITE), ("xbold", "112", LGREEN), ("bold", " i użyj AED", WHITE)],
                  W / 2, 123.8, 6.6, anchor="middle")[0])
    o.append(T("med", "Urządzenie poprowadzi Cię głosem krok po kroku.", W / 2, 131.6, 3.05, LGRAY,
               anchor="middle")[0])
    svg = doc(W, H, "".join(o), f"Naklejka {TXT.NAZWA} na kapsułę AED")
    return svg.replace(f'width="{W}" height="{H}"', f'width="{W}mm" height="{H}mm"', 1)


# ---------------------------------------------------------------- kafel social 1080×1080
def fale_dekor(cx, cy, r0, color, op=0.12, n=3, sw=34):
    """Duże łuki fal (motyw z sygnetu) jako dekoracja tła – ćwiartki okręgu do wnętrza od narożnika (cx, cy)
    w prawym górnym rogu kadru."""
    out = []
    for i in range(n):
        r = r0 + i * sw * 2.1
        out.append(f'<path d="M{cx - r} {cy} A{r} {r} 0 0 0 {cx} {cy + r}" fill="none" stroke="{color}" '
                   f'stroke-width="{sw}" stroke-linecap="round" opacity="{op}"/>')
    return "".join(out)


def kafel() -> str:
    S = 1080
    o = [f'<rect width="{S}" height="{S}" fill="{NAVY}"/>', fale_dekor(1080, 0, 230, LGREEN, 0.10)]
    inner, w, h = G.logo("dark", kompakt=True)
    o.append(f'<g transform="translate(80 86) scale({70 / h:.4f})">{inner}</g>')
    hs_svg, hs, n = para("bold", TXT.HASLO, 80, 390, 104, 900, WHITE, lh=1.12, max_lines=3, balance=True)
    o.append(hs_svg)
    y = 390 + (n - 1) * hs * 1.12 + 92
    o.append(para("med", TXT.HASLO_PODTYTUL, 80, y, 38, 880, LGRAY, lh=1.4, max_lines=4)[0])
    o.append(f'<rect x="80" y="820" width="920" height="2" fill="#2C4A6B"/>')
    b = G.badge("dark", "pelna", date="22.11.2027")
    b_inner = b.split("</title>", 1)[1].rsplit("</svg>", 1)[0]
    o.append(f'<g transform="translate(80 862) scale(2)">{b_inner}</g>')
    cs = fit("semi", TXT.WEZWANIE, 34, 1000 - 520)
    o.append(T("semi", TXT.WEZWANIE, 1000, 925, cs, WHITE, anchor="end")[0])
    o.append(T("med", "dane.gov.pl", 1000, 972, 30, LGREEN, anchor="end")[0])
    return doc(S, S, "".join(o), f"{TXT.NAZWA} – {TXT.HASLO}", desc=TXT.HASLO_PODTYTUL)


# ---------------------------------------------------------------- baner www 1200×300
def baner() -> str:
    W, H = 1200, 300
    o = [f'<rect width="{W}" height="{H}" fill="{MINT}"/>',
         f'<rect x="0" y="{H - 8}" width="{W}" height="8" fill="{GREEN}"/>']
    o.append(place(G.sygnet("light"), 30, 50, 190))
    hs_svg, hs, n = para("bold", TXT.HASLO, 240, 100, 48, 560, NAVY, lh=1.12, max_lines=2, balance=True)
    o.append(hs_svg)
    y = 100 + (n - 1) * hs * 1.12 + 44
    o.append(para("med", TXT.HASLO_PODTYTUL, 240, y, 20, 560, GRAY, lh=1.4, max_lines=3)[0])
    b = G.badge("light", "pelna", date="22.11.2027")
    b_inner = b.split("</title>", 1)[1].rsplit("</svg>", 1)[0]
    o.append(f'<g transform="translate(850 58) scale(1.6)">{b_inner}</g>')
    cs = fit("semi", TXT.WEZWANIE, 21, 320 - 36)
    o.append(f'<rect x="850" y="176" width="320" height="58" rx="29" fill="{GREEN}"/>')
    o.append(T("semi", TXT.WEZWANIE, 1010, 212, cs, WHITE, anchor="middle")[0])
    return doc(W, H, "".join(o), f"{TXT.NAZWA} – {TXT.HASLO}", desc=TXT.HASLO_PODTYTUL)


def zastosowania() -> dict[str, str]:
    ZAST.mkdir(exist_ok=True)
    out = {"naklejka_kapsula_aed": naklejka(), "kafel_social_1080": kafel(), "baner_www_1200x300": baner()}
    for name, svg in out.items():
        (ZAST / f"{name}.svg").write_text(svg, encoding="utf-8")
    cairosvg.svg2pdf(bytestring=out["naklejka_kapsula_aed"].encode(), write_to=str(ZAST / "naklejka_kapsula_aed.pdf"))
    png(out["naklejka_kapsula_aed"], width=1200).save(ZAST / "naklejka_kapsula_aed.png", optimize=True)
    png(out["kafel_social_1080"], width=1080).convert("RGB").save(ZAST / "kafel_social_1080.png", optimize=True)
    png(out["baner_www_1200x300"], width=1200).convert("RGB").save(ZAST / "baner_www_1200x300.png", optimize=True)
    return out


def main(z_final=True):
    if z_final:
        G.main()
    lg = logotypy()
    zs = zastosowania()
    print(f"logotypy: {len(lg)} × (svg, png, jpg, pdf) w {ROOT}; zastosowania: {len(zs)} w {ZAST}")
    return lg, zs


if __name__ == "__main__":
    main()
