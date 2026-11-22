"""#TuBijeAED – JEDNO miejsce konfiguracji tekstów marki.

Zmień tekst tutaj i uruchom ponownie (z katalogu repo):
    .venv/bin/python 3_branding/generuj_ksiege.py
To jedno polecenie przegeneruje wszystko: static/brand/ (logo, odznaki, favicon), pliki logotypu do oddania,
zastosowania (naklejka, kafel, baner) i Księgę znaku PDF.

Z tego modułu korzystają: final/generuj_final.py, generuj_logotypy.py, generuj_ksiege.py.
"""

# ---------------------------------------------------------------- znak
NAZWA = "#TuBijeAED"
NAZWA_CZ1 = "#TuBije"          # Poppins Medium, granat
NAZWA_CZ2 = "AED"              # Poppins ExtraBold, zieleń AED
# Podpis pod logo (wersja podstawowa). Dłuższy tekst zostanie automatycznie zmniejszony do szerokości nazwy.
PODPIS_LOGO = "DEFIBRYLATORY NA MAPIE · OTWARTE DANE"

# ---------------------------------------------------------------- hasło akcji (dla dostawców danych)
HASLO = "Podpisz się pod swoim AED."
HASLO_PODTYTUL = ("Opublikuj dane swojego defibrylatora w dane.gov.pl i dbaj, by były aktualne. "
                  "Zweryfikujemy je i oznaczymy odznaką Partnera.")
WEZWANIE = "Zostań Partnerem #TuBijeAED"

# ---------------------------------------------------------------- program Partnera / odznaka
PROGRAM = "Partner #TuBijeAED – zweryfikowane w dane.gov.pl"
ODZNAKA_ETYKIETA = "PARTNER"
ODZNAKA_WERYFIKACJA = "zweryfikowane w dane.gov.pl"
ODZNAKA_WYGASLA = "WYGASŁA"

# ---------------------------------------------------------------- naklejka na kapsułę AED
NAKLEJKA_NAGLOWEK = "PARTNER · ZWERYFIKOWANE W DANE.GOV.PL"
NAKLEJKA_PAS = "Ten defibrylator jest na mapie"
NAKLEJKA_QR_OPIS = ["Zeskanuj:", "sprawdź godziny", "dostępności,", "zgłoś usterkę", "lub zmianę danych."]
NAKLEJKA_ID = "ID AED: PL-0000-0000"
# Wariant naklejki BEZ kodu QR (prezentacja, druk przed ustaleniem adresu) – tekst zamiast kodu.
NAKLEJKA_BEZ_QR_OPIS = ["Dane tego AED są", "w dane.gov.pl.", "Godziny dostępności", "i zgłoszenie usterki:",
                        "mapa #TuBijeAED."]
# Naklejka programu Partner z nazwą Ministerstwa – PROJEKT: bez logo i godła MC, użycie wymaga zgody MC.
NAKLEJKA_MC = "Współpracujemy z Ministerstwem Cyfryzacji w programie #TuBijeAED"
NAKLEJKA_MC_PODPIS = "Dane naszego AED są aktualne i zweryfikowane w dane.gov.pl"
NAKLEJKA_MC_UWAGA = "PROJEKT – wymaga zgody Ministerstwa Cyfryzacji"
# Cel kodu QR – do ustalenia na koniec projektu (domena .example jest zastępcza, RFC 2606).
QR_URL = "https://tubijeaed.example/aed/PL-0000-0000"

# ---------------------------------------------------------------- opis koncepcji (księga, 3–5 zdań)
# {HASLO} i {PROGRAM} są podstawiane automatycznie.
OPIS_KONCEPCJI = [
    "#TuBijeAED to znak akcji skierowanej do urzędów i firm, które mają defibrylatory AED i mogą publikować "
    "o nich dane w dane.gov.pl.",
    "Sygnet łączy zielone serce z błyskawicą – czytelny skrót „tu jest AED” – z dwiema falami nadawania: dane "
    "o urządzeniu wychodzą od jego właściciela do otwartego portalu i dalej do każdego, kto szuka pomocy.",
    "Hasło „{HASLO}” odpowiada na główny problem: dane o defibrylatorach są rozproszone i niezweryfikowane, "
    "bo nikt nie bierze za nie odpowiedzialności.",
    "Dostawca, który publikuje i aktualizuje dane, otrzymuje odznakę „{PROGRAM}” do stopki strony oraz naklejkę "
    "na kapsułę AED – widoczny podpis pod swoimi danymi.",
    "Spokojna, nowoczesna forma (Poppins, zieleń AED i granat) pasuje zarówno do komunikacji urzędu, jak "
    "i marki komercyjnej.",
]


def opis_koncepcji() -> list[str]:
    return [z.format(HASLO=HASLO, PROGRAM=PROGRAM) for z in OPIS_KONCEPCJI]


# ---------------------------------------------------------------- metryczka księgi
KSIEGA_WERSJA = "wersja 1.0 · listopad 2026"
KSIEGA_KONTEKST = "HackNation 2026 · Misja AED – Dane na ratunek"
