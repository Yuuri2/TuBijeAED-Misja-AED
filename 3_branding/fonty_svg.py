"""Tekst Poppins → krzywe SVG (fontTools), z kerningiem GPOS – wspólne dla generatorów znaku i prezentacji.

Wydzielone ze Sprintu 1 (dawne archiwum 3_branding/koncepcje/, usunięte). Czcionki: 3_branding/fonts/ (Poppins, SIL OFL 1.1).
Z modułu korzystają: final/generuj_final.py (F, Font), generuj_ksiege.py (Font), 4_prezentacja/generuj_prezentacje.py (FONTS).
"""
from __future__ import annotations

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parent / "fonts"


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
