"""Mapowania kolumn zbiorów AED z dane.gov.pl na wzorcowy zakres danych (aed_schema.json).

Jak dodać kolejną gminę (5 minut, bez zmian w kodzie):
  1. znajdź zbiór na dane.gov.pl i zapisz jego id (liczba w adresie /dataset/<id>,...),
  2. dopisz poniżej wpis MAPOWANIA["<id>"] z obszarem (TERYT) i słownikiem `kolumny`,
  3. uruchom synchronizację – wiersze bez dopasowania zgłoszą się w ostrzeżeniach.
Zbiory znalezione przez wyszukiwarkę, których tu nie ma, są mapowane heurystycznie
(SYNONIMY niżej) z ostrzeżeniem „brak dedykowanego mapowania”.

Słownik `kolumny`: {pole_schematu_lub_pseudopole: nazwa_kolumny_w_źródle}.
Nazwy kolumn porównujemy po normalizacji (wielkość liter, ogonki, spacje są bez znaczenia).

Pseudopola (zaczynają się od "_"; nie trafiają do rekordu, są przetwarzane):
  _adres            pełny adres do rozbioru, np. "ul. Jasna 5, 38-400 Krosno"
  _cecha_ulicy      "ulica" / "aleja" / "plac" – doklejana jako "ul." / "al." / "pl."
  _nazwa_obiektu    nazwa budynku/instytucji – początek pola lokalizacja_szczegolowa
  _telefon, _email  kontakt funkcyjny w miejscu AED -> kontakt_dysponenta
  _zdjecia          galeria [{url: ...}] -> zdjecie_url (pierwsze zdjęcie)
  _godziny_opis     godziny opisane po polsku -> godziny_dostepnosci (format OSM)
  _dostepnosc_opis  np. "Całodobowa" / "Ograniczona" -> dostepnosc_typ
  _dostep_publiczny np. "Publiczny" / "Niepubliczny" -> dostepnosc_typ
  _polozenie        np. "Wewnątrz budynku" / "Na zewnątrz" -> wewnatrz_budynku
Współrzędne: pola szerokosc_geo/dlugosc_geo albo geometria GeoJSON (wykrywana automatycznie).
Zamienione kolumny i układ PUWG 1992 (EPSG:2180) są rozpoznawane automatycznie.

`obszar` – stałe dla całego zbioru (zbiory są gminne). Kody TERC zweryfikowane z tagami
teryt:terc granic administracyjnych OSM (Nominatim) oraz kolumną kod_terc w zbiorze Legionowa.
"""
from __future__ import annotations

MAPOWANIA: dict[str, dict] = {
    # ------------------------------------------------------------------ Krosno (CC0 1.0)
    "3624": {
        "nazwa": "Krosno",
        "prefiks_id": "KROSNO",
        "obszar": {"wojewodztwo": "podkarpackie", "powiat": "Krosno", "gmina": "Krosno",
                   "teryt_gmina": "1861011", "miejscowosc": "Krosno"},
        "kolumny": {
            "dlugosc_geo": "Długość geograficzna",
            "szerokosc_geo": "Szerokość geograficzna",
            "_nazwa_obiektu": "Lokalizacja",      # kolumna "Nazwa" ma zawsze wartość "Defibrylator"
            "_adres": "Adres",
            "id_aed": "Numer Id",
        },
    },
    # ------------------------------------------------------------------ Przemyśl (CC0 1.0)
    "4581": {
        "nazwa": "Przemyśl",
        "prefiks_id": "PRZEMYSL",
        "obszar": {"wojewodztwo": "podkarpackie", "powiat": "Przemyśl", "gmina": "Przemyśl",
                   "teryt_gmina": "1862011", "miejscowosc": "Przemyśl"},
        # GeoJSON z CMS miasta; pole "description" to ogólny opis czym jest AED – pomijamy
        "kolumny": {
            "id_aed": "id",
            "_nazwa_obiektu": "name",
            "miejscowosc": "city",
            "ulica": "street",
            "nr_budynku": "home_number",
            "kod_pocztowy": "postcode",
            "_telefon": "phone",
            "_email": "email",
            "_zdjecia": "gallery",
        },
    },
    # ------------------------------------------------------------------ Marki (CC BY 4.0)
    "4955": {
        "nazwa": "Marki",
        "prefiks_id": "MARKI",
        "obszar": {"wojewodztwo": "mazowieckie", "powiat": "wołomiński", "gmina": "Marki",
                   "teryt_gmina": "1434021", "miejscowosc": "Marki"},
        # Uwaga: plik ma cały wiersz w jednej komórce CSV, a nagłówek deklaruje (dł., szer.),
        # choć dane są w kolejności (szer., dł.) – oba problemy naprawiane automatycznie.
        "kolumny": {
            "dlugosc_geo": "Długość geograficzna",
            "szerokosc_geo": "Szerokość geograficzna",
            "_nazwa_obiektu": "Lokalizacja",
            "_adres": "Adres",
            "id_aed": "Numer Id",
        },
    },
    # ------------------------------------------------------------------ Warszawa (CC BY 4.0)
    "39512": {
        "nazwa": "Warszawa",
        "prefiks_id": "WAW",
        "obszar": {"wojewodztwo": "mazowieckie", "powiat": "Warszawa", "gmina": "Warszawa",
                   "teryt_gmina": "1465011", "miejscowosc": "Warszawa"},
        # Zasób w dane.gov.pl wskazuje stronę katalogu „Otwarte dane Warszawy”; dane są w API
        # m.st. Warszawy, które wymaga bezpłatnego tokena (env WARSZAWA_API_KEY).
        "pobieranie": {
            "url": "https://dane.um.warszawa.pl/api/action/get_scb_lokalizacja_defibrylatorow",
            "metoda": "POST",
            "token_env": "WARSZAWA_API_KEY",
            "format": "json",
        },
        # opis zbioru: „Aktywne urządzenia AED na terenie Warszawy”
        "stale": {"status_urzadzenia": "sprawne"},
        "kolumny": {
            "id_aed": "defibrillator_id",
            "_nazwa_obiektu": "location_object_name",
            "lokalizacja_szczegolowa": "location_description",
            "ulica": "location_street",
            "nr_budynku": "location_building",
            "kod_pocztowy": "location_postcode",
            "miejscowosc": "location_city",
            "producent_model": "device_manufacturer",
            "_godziny_opis": "device_access_description",
            "_dostepnosc_opis": "device_availability",
            "_dostep_publiczny": "device_public_access",
            "_polozenie": "device_location",
        },
    },
    # ------------------------------------------------------------------ Legionowo (CC0 1.0)
    "40593": {
        "nazwa": "Legionowo",
        "prefiks_id": "LEGIONOWO",
        # zbiór „Zdrowie” zawiera też apteki – bierzemy tylko zasób z defibrylatorami
        "zasoby": ["2625221"],
        "obszar": {"wojewodztwo": "mazowieckie", "powiat": "legionowski", "gmina": "Legionowo",
                   "teryt_gmina": "1408011", "miejscowosc": "Legionowo"},
        "kolumny": {
            "_nazwa_obiektu": "nazwa",
            "_cecha_ulicy": "cecha_ulicy",
            "ulica": "nazwa_ulicy",
            "nr_budynku": "nr_budynku",
            "kod_pocztowy": "kod_pocztowy",
            "miejscowosc": "miejscowosc",
            "simc": "kod_simc",
            "szerokosc_geo": "szerokosc_geograficzna",
            "dlugosc_geo": "dlugosc_geograficzna",
        },
    },
}

# Heurystyka dla zbiorów bez wpisu w MAPOWANIA (znormalizowane nazwy kolumn, wg priorytetu).
SYNONIMY: dict[str, list[str]] = {
    "id_aed": ["id_aed", "numer_id", "id", "lp", "nr", "identyfikator"],
    "szerokosc_geo": ["szerokosc_geo", "szerokosc_geograficzna", "szerokosc", "lat", "latitude", "y"],
    "dlugosc_geo": ["dlugosc_geo", "dlugosc_geograficzna", "dlugosc", "lon", "lng", "longitude", "x"],
    "_nazwa_obiektu": ["nazwa_obiektu", "obiekt", "lokalizacja", "nazwa", "name", "miejsce"],
    "lokalizacja_szczegolowa": ["lokalizacja_szczegolowa", "opis_lokalizacji", "location_description", "opis_miejsca"],
    "_adres": ["adres", "address"],
    "ulica": ["ulica", "nazwa_ulicy", "street"],
    "nr_budynku": ["nr_budynku", "numer_budynku", "nr_domu", "home_number", "building"],
    "kod_pocztowy": ["kod_pocztowy", "postcode", "kod"],
    "miejscowosc": ["miejscowosc", "miasto", "city"],
    "godziny_dostepnosci": ["godziny_dostepnosci", "godziny", "opening_hours"],
    "_telefon": ["telefon", "tel", "phone"],
    "_email": ["email", "e_mail", "mail"],
    "simc": ["simc", "kod_simc"],
    "teryt_gmina": ["teryt", "teryt_gmina", "kod_terc"],
}

# Typ instytucji w API dane.gov.pl (institution_type) -> słownik typ_dysponenta.
TYP_INSTYTUCJI: dict[str, str] = {
    "local": "JST",
    "state": "Administracja_rzadowa",
    "private": "Przedsiebiorstwo",
    "other": "NGO_Inne",
    "developer": "Przedsiebiorstwo",
}
