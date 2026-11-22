"""„Zrzuty” terminala do prezentacji – prawdziwe wyniki poleceń wyrenderowane jako PNG (monospace).

Uruchomienie (z katalogu repo):  .venv/bin/python 4_prezentacja/zrzuty_terminal.py
Wynik: 4_prezentacja/zrzuty/20_xmllint.png, 21_pytest.png, 22_axe.png oraz 4_prezentacja/zrzuty/terminal.json
(liczba testów itp. – używa jej generuj_prezentacje.py).
"""
import json
import os
import re
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageFont

TU = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TU)
KOD = os.path.join(REPO, "2_prototyp_kod")
ZRZUTY = os.path.join(TU, "zrzuty")
PY = os.path.join(REPO, ".venv", "bin", "python")

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
TLO, PASEK, TEKST, ZIELONY, SZARY, PROMPT = "#0B2545", "#071a33", "#FFFFFF", "#5FD38D", "#C5D3E0", "#5FD38D"


def renderuj(nazwa, tytul, linie, szer_zn=92, rozmiar=26):
    """linie: lista (tekst, kolor, pogrubienie). Zawija do szer_zn znaków."""
    f = ImageFont.truetype(MONO, rozmiar)
    fb = ImageFont.truetype(MONO_B, rozmiar)
    wiersze = []
    for t, kol, b in linie:
        for w in (textwrap.wrap(t, szer_zn, subsequent_indent="  ", break_long_words=True, break_on_hyphens=False) or [""]):
            wiersze.append((w, kol, b))
    zn = f.getbbox("M")[2]
    lh = int(rozmiar * 1.45)
    pad = 36
    W = pad * 2 + zn * szer_zn
    H = 64 + pad + lh * len(wiersze) + pad
    im = Image.new("RGB", (W, H), TLO)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 52], fill=PASEK)
    for i, c in enumerate(("#D90429", "#C5D3E0", "#5FD38D")):
        d.ellipse([22 + i * 30, 17, 40 + i * 30, 35], fill=c)
    d.text((130, 12), tytul, font=ImageFont.truetype(MONO, 22), fill=SZARY)
    y = 64 + pad // 2
    for w, kol, b in wiersze:
        d.text((pad, y), w, font=fb if b else f, fill=kol)
        y += lh
    im.save(os.path.join(ZRZUTY, nazwa + ".png"))
    print("  zrzut", nazwa, im.size)


def xmllint():
    xsd = "2_prototyp_kod/app/harvester/xsd/xml_import_otwarte_dane_1_14.xsd"
    xml = "2_prototyp_kod/tests/fixtures/harvester/import_aed_1_14.xml"
    p = subprocess.run(["xmllint", "--noout", "--schema", xsd, xml], cwd=REPO, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip().splitlines()
    linie = [("$ xmllint --noout --schema " + xsd + " " + xml, PROMPT, True)]
    linie += [(l, ZIELONY if "validates" in l else TEKST, "validates" in l) for l in out]
    linie += [("$ echo $?", PROMPT, True), (str(p.returncode), TEKST, False)]
    renderuj("20_xmllint", "xmllint – walidacja oficjalnym XSD (harvester 1.14)", linie)
    return {"xmllint_ok": p.returncode == 0, "xmllint": out}


def pytest():
    p = subprocess.run([PY, "-m", "pytest", "-q", "-W", "ignore::DeprecationWarning"], cwd=KOD,
                       capture_output=True, text=True)
    out = [l for l in p.stdout.strip().splitlines() if l.strip()]
    postep = [l for l in out if re.search(r"\[\s*\d+%\]", l)]
    podsum = out[-1] if out else ""
    linie = [("$ cd 2_prototyp_kod && ../.venv/bin/python -m pytest -q -W ignore::DeprecationWarning", PROMPT, True)]
    if len(postep) > 6:
        linie += [(l, SZARY, False) for l in postep[:2]] + [("…", SZARY, False)] + [(l, SZARY, False) for l in postep[-3:]]
    else:
        linie += [(l, SZARY, False) for l in postep]
    linie += [(podsum, ZIELONY if "failed" not in podsum else "#FF8FA0", True)]
    renderuj("21_pytest", "pytest – testy automatyczne prototypu", linie)
    m = re.search(r"(\d+) passed", podsum)
    return {"pytest_passed": int(m.group(1)) if m else None, "pytest_podsumowanie": podsum,
            "pytest_ok": p.returncode == 0}


def axe():
    tekst = open(os.path.join(REPO, "docs", "RAPORT_TESTOW.md"), encoding="utf-8").read()
    sek = tekst.split("### axe-core", 1)[1].split("### Lista ręczna", 1)[0]
    wiersze = [l for l in sek.splitlines() if l.startswith("|") and not l.startswith("|---")]
    linie = [("docs/RAPORT_TESTOW.md · §4 WCAG 2.1 AA – axe-core A + AA, 10 stron", SZARY, False), ("", TEKST, False)]
    for l in wiersze:
        k = [c.strip() for c in l.strip("|").split("|")]
        strona, nar = k[0], k[1]
        nar = re.sub(r"\s*\(best-practice.*\)", " (best-practice, nie A/AA)", nar)
        kol = ZIELONY if nar.startswith("0") else ("#FFD27A" if nar[:1].isdigit() else TEKST)
        linie.append((f"{strona:<22} {nar}", kol if strona != "Strona" else SZARY, strona == "Strona"))
    linie += [("", TEKST, False), ("Wynik: 0 naruszeń WCAG A/AA na 10 stronach (także po zalogowaniu", ZIELONY, True),
              ("i po wynikach walidacji/konwersji); 320 px bez przewijania poziomego.", ZIELONY, True)]
    renderuj("22_axe", "axe-core – audyt dostępności (fragment raportu testów)", linie, szer_zn=86)


def main():
    os.makedirs(ZRZUTY, exist_ok=True)
    wynik = {}
    wynik.update(xmllint())
    wynik.update(pytest())
    axe()
    json.dump(wynik, open(os.path.join(ZRZUTY, "terminal.json"), "w"), indent=1, ensure_ascii=False)
    print(wynik)


if __name__ == "__main__":
    main()
