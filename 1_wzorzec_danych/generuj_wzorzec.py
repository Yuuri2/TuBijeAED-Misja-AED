"""Generator wzorca danych AED (#TuBijeAED) – wszystko jest generowane Z aed_schema.json.

Uruchomienie:  python generuj_wzorzec.py   (wymaga: openpyxl)
Wynik (w tym katalogu): wzorzec_danych_aed.xlsx, wzorzec_danych_aed.csv

Arkusze: Instrukcja, Dane (pusty, z listami rozwijanymi), Schemat_danych, Slowniki, Dane_przykladowe.
Zmiana zakresu danych = zmiana WYŁĄCZNIE w aed_schema.json (oraz ewentualnie opisów słownikowych poniżej).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

KATALOG = Path(__file__).resolve().parent
SCHEMA = json.loads((KATALOG / "aed_schema.json").read_text(encoding="utf-8"))
POLA = SCHEMA["fields"]
LICZBA_WIERSZY_DANE = 1000          # tyle wierszy arkusza „Dane” ma listy rozwijane i formaty

# Znaczenie wartości słownikowych (schema zawiera tylko same wartości). Brak wpisu = puste znaczenie.
ZNACZENIA = {
    "typ_dysponenta": {
        "JST": "Jednostka samorządu terytorialnego (urząd miasta, gminy, starostwo)",
        "Administracja_rzadowa": "Ministerstwa, urzędy wojewódzkie, instytucje państwowe",
        "Podmiot_leczniczy": "Szpitale, przychodnie, stacje ratownictwa",
        "Sluzby_mundurowe": "PSP, OSP, Policja, Straż Miejska",
        "Przedsiebiorstwo": "Firmy prywatne, galerie handlowe, dworce, zakłady pracy",
        "NGO_Inne": "Fundacje, stowarzyszenia, uczelnie, wspólnoty mieszkaniowe",
    },
    "wewnatrz_budynku": {"TAK": "Urządzenie w budynku", "NIE": "Urządzenie na zewnątrz (np. kapsuła na elewacji)"},
    "dostepnosc_typ": {
        "24_7": "Dostępny całą dobę, 7 dni w tygodniu",
        "godziny_otwarcia": "Dostępny wyłącznie w godzinach otwarcia obiektu",
        "ograniczona": "Dostępny tylko dla uprawnionych osób (pracownicy, klienci, pasażerowie)",
    },
    "czy_zamkniete": {
        "NIE": "Urządzenie otwarte lub otwierane bez klucza/kodu (może mieć alarm dźwiękowy)",
        "TAK_KLUCZ": "Wymagany klucz fizyczny od ochrony/obsługi",
        "TAK_KOD": "Wymagane wpisanie kodu PIN na kapsule (kodu NIE wpisujemy do danych)",
        "TAK_OCHRONA": "Urządzenie wydaje ochrona lub recepcja",
    },
    "elektrody_pediatryczne": {"TAK": "Ma elektrody lub tryb dla dzieci", "NIE": "Nie ma", "BRAK_DANYCH": "Nie wiadomo"},
    "status_urzadzenia": {
        "sprawne": "Urządzenie gotowe do użycia",
        "w_serwisie": "Urządzenie czasowo niedostępne (wymiana baterii/elektrod)",
        "wycofane": "Urządzenie trwale usunięte z lokalizacji (rekord do archiwum)",
        "nieznany": "Stan techniczny nieznany",
    },
}

# Dane przykładowe – fikcyjne zgłoszenia ilustrujące format (bez publikowania kodów PIN).
PRZYKLADY = [
    {
        "id_aed": "UMW-AED-001", "nazwa_dysponenta": "Urząd Miasta Stołecznego Warszawy", "identyfikator_dysponenta": "5252248481",
        "typ_dysponenta": "JST", "kontakt_dysponenta": "+48 22 443 00 00",
        "wojewodztwo": "mazowieckie", "powiat": "Warszawa", "gmina": "Warszawa", "teryt_gmina": "1465011",
        "miejscowosc": "Warszawa", "simc": "0918123", "ulica": "pl. Bankowy", "nr_budynku": "3/5", "kod_pocztowy": "00-950",
        "szerokosc_geo": 52.24285, "dlugosc_geo": 21.00214, "lokalizacja_szczegolowa": "Wejście główne B, parter przy portierni",
        "kondygnacja": "0", "wewnatrz_budynku": "TAK", "dostepnosc_typ": "godziny_otwarcia", "godziny_dostepnosci": "Mo-Fr 08:00-16:00",
        "czy_zamkniete": "NIE", "instrukcja_dostepu": "", "elektrody_pediatryczne": "TAK", "status_urzadzenia": "sprawne",
        "data_przegladu": "2026-09-15", "producent_model": "Philips HeartStart FRx", "zdjecie_url": "",
        "data_aktualizacji": "2026-11-21T12:00:00Z",
    },
    {
        "id_aed": "PKP-AED-104", "nazwa_dysponenta": "Polskie Koleje Państwowe S.A.", "identyfikator_dysponenta": "5250000251",
        "typ_dysponenta": "Przedsiebiorstwo", "kontakt_dysponenta": "+48 22 474 00 00",
        "wojewodztwo": "śląskie", "powiat": "Sosnowiec", "gmina": "Sosnowiec", "teryt_gmina": "2473011",
        "miejscowosc": "Sosnowiec", "simc": "0969928", "ulica": "ul. 3 Maja", "nr_budynku": "16", "kod_pocztowy": "41-200",
        "szerokosc_geo": 50.27852, "dlugosc_geo": 19.12684, "lokalizacja_szczegolowa": "Hala główna dworca kolejowego przy kasach biletowych",
        "kondygnacja": "0", "wewnatrz_budynku": "TAK", "dostepnosc_typ": "24_7", "godziny_dostepnosci": "",
        "czy_zamkniete": "TAK_KOD", "instrukcja_dostepu": "Kod podaje dyspozytor numeru 112", "elektrody_pediatryczne": "BRAK_DANYCH",
        "status_urzadzenia": "sprawne", "data_przegladu": "2026-10-01", "producent_model": "", "zdjecie_url": "",
        "data_aktualizacji": "2026-11-21T14:30:00Z",
    },
    {
        "id_aed": "KPRM-AED-002", "nazwa_dysponenta": "Kancelaria Prezesa Rady Ministrów", "identyfikator_dysponenta": "5261645000",
        "typ_dysponenta": "Administracja_rzadowa", "kontakt_dysponenta": "+48 22 694 60 00",
        "wojewodztwo": "mazowieckie", "powiat": "Warszawa", "gmina": "Warszawa", "teryt_gmina": "1465011",
        "miejscowosc": "Warszawa", "simc": "0918123", "ulica": "Al. Ujazdowskie", "nr_budynku": "1/3", "kod_pocztowy": "00-583",
        "szerokosc_geo": 52.21941, "dlugosc_geo": 21.02431, "lokalizacja_szczegolowa": "Biuro Przepustek przy wejściu głównym",
        "kondygnacja": "0", "wewnatrz_budynku": "TAK", "dostepnosc_typ": "24_7", "godziny_dostepnosci": "",
        "czy_zamkniete": "TAK_OCHRONA", "instrukcja_dostepu": "Dostępne natychmiast u funkcjonariusza ochrony na stanowisku 24/7",
        "elektrody_pediatryczne": "NIE", "status_urzadzenia": "sprawne", "data_przegladu": "2026-10-20",
        "producent_model": "", "zdjecie_url": "", "data_aktualizacji": "2026-11-21T15:00:00Z",
    },
]

KOLORY = {"TAK": "C0392B", "WARUNKOWO": "D68910", "ZALECANE": "2471A3", "NIE": "7F8C8D"}
ETYKIETY_WYMAGALNOSCI = {"TAK": "wymagane", "WARUNKOWO": "warunkowo wymagane", "ZALECANE": "zalecane", "NIE": "opcjonalne"}
CIENKA = Side(style="thin", color="BFBFBF")
RAMKA = Border(left=CIENKA, right=CIENKA, top=CIENKA, bottom=CIENKA)


def _typ_czytelny(p: dict) -> str:
    t = p.get("type", "string")
    return {"string": "tekst", "number": "liczba (WGS84)", "date": "data (RRRR-MM-DD)",
            "datetime": "data i czas ISO 8601 (UTC)"}.get(t, t)


def _ograniczenia(p: dict) -> str:
    c, czesci = p.get("constraints", {}), []
    if "enum" in c:
        czesci.append("wartość ze słownika")
    if "pattern" in c:
        czesci.append(f"wzorzec: {c['pattern']}")
    if "minimum" in c or "maximum" in c:
        czesci.append(f"zakres {c.get('minimum')}–{c.get('maximum')}")
    if "maxLength" in c:
        czesci.append(f"maks. {c['maxLength']} znaków")
    if p.get("x-warunek"):
        czesci.append(p["x-warunek"])
    if p.get("x-walidacja"):
        czesci.append(p["x-walidacja"])
    if p.get("x-format"):
        czesci.append(f"format: {p['x-format']}")
    return "; ".join(czesci)


def arkusz_instrukcja(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "Instrukcja"
    wiersze = [
        ("#TuBijeAED – wzorzec danych o defibrylatorach AED", "tytul"),
        (f"Wersja schematu: {SCHEMA['version']}  |  kodowanie: {SCHEMA['x-kodowanie']}  |  układ współrzędnych: {SCHEMA['x-uklad-wspolrzednych']}", "opis"),
        ("", None),
        ("Jak wypełnić", "naglowek"),
        ("1. Dane wpisuj w arkuszu „Dane” – jeden wiersz = jedno urządzenie AED. Nagłówków kolumn nie zmieniaj ani nie usuwaj.", None),
        ("2. Kolor nagłówka: czerwony = wymagane, pomarańczowy = wymagane warunkowo, niebieski = zalecane, szary = opcjonalne. Najedź kursorem na nagłówek, aby zobaczyć opis.", None),
        ("3. Pola słownikowe wybieraj z listy rozwijanej (wartości i ich znaczenie: arkusz „Slowniki”).", None),
        ("4. Współrzędne w stopniach dziesiętnych WGS84, min. 5 miejsc po przecinku (np. 52,24285). Polskie współrzędne: szerokość 49–54,9; długość 14,1–24,2.", None),
        ("5. Godziny dostępności zapisz w formacie OSM, np. „Mo-Fr 08:00-16:00; Sa 09:00-13:00” lub „24/7”. Pole jest wymagane, gdy typ dostępności ≠ 24_7.", None),
        ("6. NIE publikuj kodów PIN do kapsuł. Gdy urządzenie jest zamknięte, w instrukcji dostępu wpisz np. „Kod podaje dyspozytor 112”.", None),
        ("7. W polu kontaktowym podaj telefon lub e-mail funkcyjny (portiernia, sekretariat) – bez danych osobowych.", None),
        ("8. Arkusz „Dane_przykladowe” pokazuje poprawnie wypełnione wiersze (dane fikcyjne, ilustracyjne). Nie wgrywaj ich jako własnych.", None),
        ("9. Identyfikator dysponenta to NIP (10 cyfr) lub REGON (9/14 cyfr) bez myślników; numer jest sprawdzany pod kątem sumy kontrolnej.", None),
        ("", None),
        ("Licencja", "naglowek"),
        (f"Zalecana licencja danych: {SCHEMA['x-licencja-zalecana']}. Portal dane.gov.pl przyjmuje do harvestowania wyłącznie zbiory na licencjach CC0 lub CC BY.", None),
        ("", None),
        ("Jak opublikować dane na dane.gov.pl", "naglowek"),
        ("1. Sprawdź plik w panelu dysponenta #TuBijeAED (walidacja pokaże błędy w konkretnych wierszach i polach) i popraw uwagi.", None),
        ("2. Zaloguj się do panelu dostawcy danych na dane.gov.pl (konto instytucji) i dodaj nowy zbiór danych z kategorii „Zdrowie”.", None),
        ("3. Dołącz plik CSV (lub XLSX) z arkusza „Dane”, wskaż licencję CC BY 4.0 i zaznacz zbiór jako zawierający dane dynamiczne (częstotliwość aktualizacji).", None),
        ("4. Opcjonalnie: #TuBijeAED przygotuje plik XML do harvestowania (zgodny z oficjalnym schematem 1.13) – eksport w panelu integratora.", None),
        ("5. Pamiętaj o cyklicznej aktualizacji – pole „data_aktualizacji” powinno odzwierciedlać ostatnie potwierdzenie danych.", None),
    ]
    for i, (tekst, styl) in enumerate(wiersze, start=1):
        c = ws.cell(row=i, column=1, value=tekst)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if styl == "tytul":
            c.font = Font(size=16, bold=True, color="1F3A5F")
        elif styl == "naglowek":
            c.font = Font(size=12, bold=True, color="C0392B")
        elif styl == "opis":
            c.font = Font(italic=True, color="595959")
    ws.column_dimensions["A"].width = 130
    ws.sheet_view.showGridLines = False


def arkusz_dane(wb: Workbook, slownik_zakresy: dict[str, str]) -> None:
    ws = wb.create_sheet("Dane")
    nazwa_kolumny = {}
    for i, p in enumerate(POLA, start=1):
        nazwa_kolumny[p["name"]] = i
        c = ws.cell(row=1, column=i, value=p["name"])
        poziom = p.get("x-wymagane", "NIE")
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=KOLORY.get(poziom, "7F8C8D"))
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = RAMKA
        opis = f"{p.get('title', p['name'])} [{ETYKIETY_WYMAGALNOSCI.get(poziom, poziom)}]\n{p.get('description', '')}"
        extra = _ograniczenia(p)
        if extra:
            opis += f"\n{extra}"
        kom = Comment(opis, "#TuBijeAED")
        kom.width, kom.height = 360, 170
        c.comment = kom
        ws.column_dimensions[get_column_letter(i)].width = min(max(len(p["name"]) + 4, 16), 46) if p["name"] not in (
            "lokalizacja_szczegolowa", "instrukcja_dostepu", "nazwa_dysponenta") else 46
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(POLA))}{LICZBA_WIERSZY_DANE + 1}"

    ostatni = LICZBA_WIERSZY_DANE + 1
    for p in POLA:
        kol = get_column_letter(nazwa_kolumny[p["name"]])
        zakres = f"{kol}2:{kol}{ostatni}"
        c = p.get("constraints", {})
        if "enum" in c:
            dv = DataValidation(type="list", formula1=slownik_zakresy[p["name"]], allow_blank=True,
                                showErrorMessage=True, errorTitle="Wartość spoza słownika",
                                error="Wybierz wartość z listy rozwijanej (zob. arkusz Slowniki).",
                                showInputMessage=True, promptTitle=p.get("title", p["name"]), prompt=p.get("description", "")[:250])
            ws.add_data_validation(dv)
            dv.add(zakres)
        elif p.get("type") == "number" and ("minimum" in c or "maximum" in c):
            dv = DataValidation(type="decimal", operator="between", formula1=str(c["minimum"]), formula2=str(c["maximum"]),
                                allow_blank=True, showErrorMessage=True, errorTitle="Poza zakresem",
                                error=f"Podaj liczbę z zakresu {c['minimum']}–{c['maximum']} (współrzędne WGS84 dla Polski).")
            ws.add_data_validation(dv)
            dv.add(zakres)
        elif p.get("type") == "date":
            dv = DataValidation(type="date", operator="greaterThan", formula1="36526", allow_blank=True,
                                showErrorMessage=True, errorTitle="Nieprawidłowa data", error="Podaj datę w formacie RRRR-MM-DD.")
            ws.add_data_validation(dv)
            dv.add(zakres)
        # kolumny tekstowe jako tekst, aby Excel nie obcinał zer wiodących (TERYT, REGON, kod pocztowy)
        if p.get("type", "string") == "string":
            for r in range(2, ostatni + 1):
                ws.cell(row=r, column=nazwa_kolumny[p["name"]]).number_format = "@"


def arkusz_schemat(wb: Workbook) -> None:
    ws = wb.create_sheet("Schemat_danych")
    naglowki = ["kolumna", "nazwa_przyjazna", "typ", "wymagane", "ograniczenia", "opis"]
    ws.append(naglowki)
    for p in POLA:
        ws.append([p["name"], p.get("title", ""), _typ_czytelny(p), ETYKIETY_WYMAGALNOSCI.get(p.get("x-wymagane", "NIE")),
                   _ograniczenia(p), p.get("description", "")])
    _styl_tabeli(ws, [26, 34, 24, 20, 60, 90])
    for w in ws.iter_rows(min_row=2):
        w[3].font = Font(bold=True, color=KOLORY.get(next(k for k, v in ETYKIETY_WYMAGALNOSCI.items() if v == w[3].value), "000000"))


def arkusz_slowniki(wb: Workbook) -> dict[str, str]:
    """Slowniki w układzie „długim” (pole, wartość, znaczenie); zwraca zakresy dla DataValidation."""
    ws = wb.create_sheet("Slowniki")
    ws.append(["pole", "wartosc_dozwolona", "znaczenie"])
    zakresy: dict[str, str] = {}
    r = 2
    for p in POLA:
        wartosci = p.get("constraints", {}).get("enum")
        if not wartosci:
            continue
        start = r
        for w in wartosci:
            ws.append([p["name"], w, ZNACZENIA.get(p["name"], {}).get(w, "")])
            r += 1
        zakresy[p["name"]] = f"Slowniki!$B${start}:$B${r - 1}"
    _styl_tabeli(ws, [28, 30, 90])
    return zakresy


def arkusz_przyklady(wb: Workbook) -> None:
    ws = wb.create_sheet("Dane_przykladowe")
    nazwy = [p["name"] for p in POLA]
    ws.append(nazwy)
    for rek in PRZYKLADY:
        ws.append([rek.get(n) if rek.get(n) != "" else None for n in nazwy])
    _styl_tabeli(ws, [min(max(len(n) + 4, 16), 46) for n in nazwy])
    ws.freeze_panes = "A2"
    for kolumna in ("lokalizacja_szczegolowa", "instrukcja_dostepu", "nazwa_dysponenta"):
        ws.column_dimensions[get_column_letter(nazwy.index(kolumna) + 1)].width = 46
    for w in ws.iter_rows(min_row=2):
        for c in w:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    # tekstowe kolumny jako tekst (TERYT, kod pocztowy z zerami)
    for p in POLA:
        if p.get("type", "string") == "string":
            for r in range(2, len(PRZYKLADY) + 2):
                ws.cell(row=r, column=nazwy.index(p["name"]) + 1).number_format = "@"


def _styl_tabeli(ws, szerokosci: list[int]) -> None:
    for i, w in enumerate(szerokosci, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3A5F")
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    for w in ws.iter_rows(min_row=2):
        for c in w:
            c.alignment = Alignment(vertical="top", wrap_text=True)


def zapisz_csv(sciezka: Path) -> None:
    nazwy = [p["name"] for p in POLA]
    with open(sciezka, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=SCHEMA.get("x-separator-csv", ","), lineterminator="\n")
        w.writerow(nazwy)
        for rek in PRZYKLADY:
            w.writerow(["" if rek.get(n) is None else rek[n] for n in nazwy])


def main() -> None:
    brakujace = [(p["name"], v) for p in POLA for v in p.get("constraints", {}).get("enum", [])
                 if v not in ZNACZENIA.get(p["name"], {}) and p["name"] != "wojewodztwo"]
    if brakujace:
        print("UWAGA: brak opisu znaczenia dla wartości słownika:", brakujace)
    wb = Workbook()
    arkusz_instrukcja(wb)
    arkusz_schemat(wb)
    zakresy = arkusz_slowniki(wb)             # „Dane” potrzebuje zakresów słowników, więc powstaje po nich
    arkusz_przyklady(wb)
    arkusz_dane(wb, zakresy)
    # docelowa kolejność: Instrukcja, Dane, Schemat_danych, Slowniki, Dane_przykladowe
    wb.move_sheet("Dane", offset=-(len(wb.sheetnames) - 2))
    wb.save(KATALOG / "wzorzec_danych_aed.xlsx")
    zapisz_csv(KATALOG / "wzorzec_danych_aed.csv")
    print("Gotowe! Utworzono wzorzec_danych_aed.xlsx i wzorzec_danych_aed.csv; arkusze:", wb.sheetnames)


if __name__ == "__main__":
    main()
