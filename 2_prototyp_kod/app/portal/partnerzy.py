"""Program Partner #TuBijeAED (implementuje Backend). Szczegóły: docs/PROTOTYP.md.

Nie ma odpowiednika w mcod – to akcja promocyjna dla dostawców danych, liczona WYŁĄCZNIE z danych portalu
(zasób dostawcy + aktualny wykaz zbiorczy). Kryteria:
  1. opublikowany zasób wykazu AED uwzględniony w aktualnym wykazie zbiorczym,
  2. 0 błędów walidacji tego zasobu,
  3. zasób zaktualizowany nie dawniej niż 12 miesięcy temu (`data_danych`, a gdy brak – data modyfikacji),
  4. „dane ponad minimum”: średni odsetek wypełnionych pól ZALECANYCH i OPCJONALNYCH wzorca (x-wymagane ∈
     {ZALECANE, NIE}) w rekordach dostawcy w wykazie ≥ 0,5. Pola wymagane (TAK) są zawsze wypełnione w poprawnym
     rekordzie, więc nie różnicują – liczy się to, co dostawca podał ponad obowiązkowe minimum.
Status: AKTYWNY – wszystkie kryteria; WYGASŁY – spełnione 1, 2, 4, ale dane są starsze niż 12 miesięcy
(odznaka wygasa, dopóki dostawca nie potwierdzi danych); BRAK – w pozostałych przypadkach.
`wazny_do` = data aktualizacji zasobu + 12 miesięcy.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

from .. import config
from . import baza, wykazy

TYP_WYKAZU = "AED"
MIESIECY_WAZNOSCI = 12
PROG_KOMPLETNOSCI = 0.5          # próg „danych ponad minimum” (odsetek pól ZALECANYCH i opcjonalnych)
POZIOMY_PONAD_MINIMUM = ("ZALECANE", "NIE")


def kompletnosc_ponad_minimum(rekord: dict) -> float:
    """Odsetek wypełnionych pól o x-wymagane ∈ {ZALECANE, NIE} (pola „ponad minimum”)."""
    from .. import schema

    pola = [p["name"] for p in schema.pola() if p.get("x-wymagane") in POZIOMY_PONAD_MINIMUM]
    if not pola:
        return 0.0
    return sum(1 for n in pola if schema.pole_wypelnione(rekord.get(n))) / len(pola)


def _dodaj_miesiace(d: date, n: int) -> date:
    rok, mies = divmod(d.month - 1 + n, 12)
    rok, mies = d.year + rok, mies + 1
    for dzien in (d.day, 30, 29, 28):
        try:
            return date(rok, mies, min(d.day, dzien))
        except ValueError:
            continue
    return date(rok, mies, 28)


def _na_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _dzis(teraz: datetime | date | None) -> date:
    if teraz is None:
        return datetime.now(timezone.utc).date()
    return teraz.date() if isinstance(teraz, datetime) else teraz


def status_partnera(instytucja_id: int, *, teraz: datetime | date | None = None) -> dict:
    """{status: 'AKTYWNY'|'WYGASŁY'|'BRAK', kryteria: [{nazwa, spelnione, opis}], wazny_do: str|None}
    (+ instytucja_id, zasob_id, kompletnosc). `teraz` – wstrzykiwany „dzisiaj” (testy)."""
    dzis = _dzis(teraz)
    zasob = wykazy.zasob_wykazu_instytucji(TYP_WYKAZU, int(instytucja_id))
    pelny = None
    if zasob:
        with baza.transakcja() as con:
            pelny = dict(con.execute("SELECT * FROM zasoby WHERE id = ?", (zasob["id"],)).fetchone())
    wykaz = wykazy.aktualny_wykaz(TYP_WYKAZU)
    w_wykazie = bool(pelny and wykaz and any(u["zasob_id"] == pelny["id"] for u in wykaz["uwzglednione"]))

    raport = baza.z_json(pelny.get("walidacja_raport"), {}) if pelny else {}
    bledy = len((raport or {}).get("bledy") or []) if pelny else None
    bez_bledow = bool(pelny and pelny["walidacja_status"] == "OK" and bledy == 0)

    data_akt = _na_date((pelny or {}).get("data_danych") or (pelny or {}).get("zmodyfikowano"))
    wazny_do = _dodaj_miesiace(data_akt, MIESIECY_WAZNOSCI) if data_akt else None
    swiezy = bool(wazny_do and dzis <= wazny_do)

    rekordy = wykazy.rekordy_wykazu(TYP_WYKAZU, instytucja_id=int(instytucja_id)) if w_wykazie else []
    konf = wykazy.konfiguracja(TYP_WYKAZU)
    kompletnosc = round(sum(kompletnosc_ponad_minimum(r) for r in rekordy) / len(rekordy), 3) if rekordy else None
    kompletny = kompletnosc is not None and kompletnosc >= PROG_KOMPLETNOSCI

    kryteria = [
        {"nazwa": "zasob_w_wykazie", "spelnione": w_wykazie,
         "opis": "Opublikowany zasób oznaczony jako zasób Wykazu AED jest uwzględniony w aktualnym wykazie zbiorczym."
                 + ("" if pelny else " Brak opublikowanego zasobu wykazu AED.")},
        {"nazwa": "bez_bledow_walidacji", "spelnione": bez_bledow,
         "opis": "Zasób nie ma błędów walidacji wzorca AED."
                 + (f" Liczba błędów: {bledy}." if bledy else "")},
        {"nazwa": "aktualnosc_12_miesiecy", "spelnione": swiezy,
         "opis": f"Dane zaktualizowane w ciągu ostatnich {MIESIECY_WAZNOSCI} miesięcy"
                 + (f" (ostatnia aktualizacja: {data_akt.isoformat()})." if data_akt else ".")},
        {"nazwa": "kompletnosc_80", "spelnione": kompletny,
         "opis": "Dane ponad obowiązkowe minimum: średnio co najmniej "
                 f"{int(PROG_KOMPLETNOSCI * 100)}% pól zalecanych i opcjonalnych wzorca (np. kondygnacja, ulica, "
                 "producent i model, elektrody pediatryczne, data przeglądu, zdjęcie) jest wypełnionych"
                 + (f" (obecnie: {round(kompletnosc * 100)}%)." if kompletnosc is not None else ".")},
    ]
    if w_wykazie and bez_bledow and kompletny:
        status = "AKTYWNY" if swiezy else "WYGASŁY"
    else:
        status = "BRAK"
    return {"instytucja_id": int(instytucja_id), "status": status, "kryteria": kryteria,
            "wazny_do": wazny_do.isoformat() if (wazny_do and status != "BRAK") else None,
            "zasob_id": pelny["id"] if pelny else None, "kompletnosc": kompletnosc,
            "liczba_rekordow": len(rekordy)}


def lista_partnerow(*, teraz: datetime | date | None = None, z_wygaslymi: bool = True) -> list[dict]:
    """Instytucje ze statusem AKTYWNY (i – domyślnie – WYGASŁY), posortowane po nazwie."""
    from . import repo_portal

    wynik = []
    for inst in repo_portal.lista_instytucji():
        s = status_partnera(inst["id"], teraz=teraz)
        if s["status"] == "AKTYWNY" or (z_wygaslymi and s["status"] == "WYGASŁY"):
            wynik.append({"instytucja": {k: inst[k] for k in ("id", "nazwa", "typ", "regon")}, **s})
    return wynik


# ---------------------------------------------------------------------------- odznaka SVG

_NIEBEZPIECZNE = [
    re.compile(r"<script\b.*?</script\s*>", re.I | re.S),
    re.compile(r"<script\b[^>]*/>", re.I),
    re.compile(r"<foreignObject\b.*?</foreignObject\s*>", re.I | re.S),
    re.compile(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*')", re.I),
    re.compile(r"\s(xlink:)?href\s*=\s*(\"\s*javascript:[^\"]*\"|'\s*javascript:[^']*')", re.I),
]


def _oczysc_svg(svg: str) -> str:
    """Szablony są nasze, ale odznaka trafia na cudze strony – usuwamy wszystko, co mogłoby się wykonać."""
    for wz in _NIEBEZPIECZNE:
        svg = wz.sub("", svg)
    return svg


def _szablon(nazwa: str, rozmiar: str) -> str:
    """Pliki UI/UX `static/brand/<nazwa>-<rozmiar>.svg` (placeholder DD.MM.RRRR – patrz static/brand/README.md)."""
    p: Path = config.BRAND_DIR / f"{nazwa}-{rozmiar}.svg"
    if p.exists():
        return p.read_text(encoding="utf-8")
    # awaryjnie (brak plików UI/UX): prosta odznaka tekstowa
    w, h = (200, 60) if rozmiar == "pelna" else (88, 31)
    wyg = nazwa.endswith("wygasla")
    ciemna = nazwa.endswith("ciemna")
    tlo, txt = ("#0B2545", "#FFFFFF") if ciemna else ("#FFFFFF", "#5B6770" if wyg else "#0B2545")
    kreska = ' stroke-dasharray="4 2.5"' if wyg else ""
    tytul = ("Odznaka Partnera #TuBijeAED wygasła DD.MM.RRRR" if wyg
             else "Partner #TuBijeAED – zweryfikowane w dane.gov.pl, ważne do DD.MM.RRRR")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{tytul}"><title>{tytul}</title><rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="5" '
            f'fill="{tlo}" stroke="#5B6770"{kreska}/>'
            f'<text x="{w / 2}" y="{h / 2 + 3}" font-family="Arial, sans-serif" font-size="{9 if w > 100 else 7}" '
            f'fill="{txt}" text-anchor="middle">{"wygasła DD.MM.RRRR" if wyg else "PARTNER #TuBijeAED"}</text></svg>')


def odznaka_svg(status: dict, *, wariant: str = "jasna", rozmiar: str = "pelna") -> str:
    """SVG odznaki dla statusu z `status_partnera` (AKTYWNY lub WYGASŁY). Wygasła – zawsze wariant szary."""
    wariant = wariant if wariant in ("jasna", "ciemna") else "jasna"
    rozmiar = rozmiar if rozmiar in ("pelna", "mala") else "pelna"
    nazwa = "odznaka-wygasla" if status["status"] == "WYGASŁY" else f"odznaka-{wariant}"
    data = _na_date(status.get("wazny_do"))
    svg = _szablon(nazwa, rozmiar).replace("DD.MM.RRRR", data.strftime("%d.%m.%Y") if data else "—")
    return _oczysc_svg(svg)
