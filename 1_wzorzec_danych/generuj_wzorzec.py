import pandas as pd

# 1. Arkusz: Schemat danych (metadane wzorca)
schemat = [
    {"kolumna": "id_aed", "nazwa_przyjazna": "Identyfikator AED", "typ": "String", "wymagane": "TAK", "opis": "Unikalny kod nadany przez dysponenta (np. UMW-AED-001)"},
    {"kolumna": "nazwa_dysponenta", "nazwa_przyjazna": "Nazwa dysponenta", "typ": "String", "wymagane": "TAK", "opis": "Pełna nazwa instytucji lub firmy odpowiedzialnej za urządzenie"},
    {"kolumna": "identyfikator_dysponenta", "nazwa_przyjazna": "NIP lub REGON", "typ": "String (9/10/14 cyfr)", "wymagane": "TAK", "opis": "Numer NIP lub REGON potwierdzający tożsamość podmiotu"},
    {"kolumna": "typ_dysponenta", "nazwa_przyjazna": "Typ podmiotu", "typ": "Słownik", "wymagane": "TAK", "opis": "Wartość ze słownika (JST, Administracja_rzadowa, Podmiot_leczniczy, Sluzby_mundurowe, Przedsiebiorstwo, NGO_Inne)"},
    {"kolumna": "wojewodztwo", "nazwa_przyjazna": "Województwo", "typ": "Słownik", "wymagane": "TAK", "opis": "Nazwa województwa małymi literami zgodnie z TERYT (np. mazowieckie, slaskie)"},
    {"kolumna": "powiat", "nazwa_przyjazna": "Powiat", "typ": "String", "wymagane": "TAK", "opis": "Nazwa powiatu lub miasta na prawach powiatu"},
    {"kolumna": "gmina", "nazwa_przyjazna": "Gmina", "typ": "String", "wymagane": "TAK", "opis": "Nazwa gminy"},
    {"kolumna": "miejscowosc", "nazwa_przyjazna": "Miejscowość", "typ": "String", "wymagane": "TAK", "opis": "Nazwa miejscowości"},
    {"kolumna": "ulica", "nazwa_przyjazna": "Ulica", "typ": "String", "wymagane": "NIE", "opis": "Nazwa ulicy (jeśli występuje)"},
    {"kolumna": "nr_budynku", "nazwa_przyjazna": "Numer budynku", "typ": "String", "wymagane": "TAK", "opis": "Numer porządkowy budynku lub lokalizacja obiektu (np. Peron 1)"},
    {"kolumna": "kod_pocztowy", "nazwa_przyjazna": "Kod pocztowy", "typ": "String (XX-XXX)", "wymagane": "TAK", "opis": "Kod pocztowy w formacie 00-000"},
    {"kolumna": "szerokosc_geo", "nazwa_przyjazna": "Szerokość geograficzna (Lat)", "typ": "Float (WGS84)", "wymagane": "TAK", "opis": "Współrzędna N dla Polski (49.00000 - 54.90000)"},
    {"kolumna": "dlugosc_geo", "nazwa_przyjazna": "Długość geograficzna (Lon)", "typ": "Float (WGS84)", "wymagane": "TAK", "opis": "Współrzędna E dla Polski (14.10000 - 24.20000)"},
    {"kolumna": "lokalizacja_szczegolowa", "nazwa_przyjazna": "Dokładne miejsce w obiekcie", "typ": "String", "wymagane": "TAK", "opis": "Opis ułatwiający szybkie odnalezienie (np. Parter, hol główny przy recepcji)"},
    {"kolumna": "dostepnosc_typ", "nazwa_przyjazna": "Typ dostępności", "typ": "Słownik", "wymagane": "TAK", "opis": "Wartość ze słownika: 24_7, godziny_otwarcia, ograniczona"},
    {"kolumna": "godziny_dostepnosci", "nazwa_przyjazna": "Godziny dostępności", "typ": "String", "wymagane": "WARUNKOWO", "opis": "Wymagane gdy dostepnosc_typ != 24_7 (np. Pn-Pt 07:30-15:30)"},
    {"kolumna": "czy_zamkniete", "nazwa_przyjazna": "Wymagany klucz / kod / zgoda", "typ": "Słownik", "wymagane": "TAK", "opis": "Wartość ze słownika: NIE, TAK_KLUCZ, TAK_KOD, TAK_OCHRONA"},
    {"kolumna": "instrukcja_dostepu", "nazwa_przyjazna": "Instrukcja otwarcia", "typ": "String", "wymagane": "WARUNKOWO", "opis": "Wymagane gdy czy_zamkniete != NIE (np. Kod do kapsuły: 1122 lub Klucz na portierni)"},
    {"kolumna": "status_urzadzenia", "nazwa_przyjazna": "Status techniczny", "typ": "Słownik", "wymagane": "TAK", "opis": "Wartość ze słownika: sprawne, w_serwisie, wycofane"},
    {"kolumna": "data_przegladu", "nazwa_przyjazna": "Data ostatniego przeglądu", "typ": "Date (YYYY-MM-DD)", "wymagane": "NIE", "opis": "Data ostatniej kontroli baterii i elektrod"},
    {"kolumna": "kontakt_dysponenta", "nazwa_przyjazna": "Telefon kontaktowy", "typ": "String", "wymagane": "TAK", "opis": "Numer telefonu do osoby/punktu odpowiedzialnego za AED"},
    {"kolumna": "data_aktualizacji", "nazwa_przyjazna": "Data aktualizacji rekordu", "typ": "DateTime (ISO 8601)", "wymagane": "TAK", "opis": "Znacznik czasu ostatniego potwierdzenia danych przez dysponenta"}
]

# 2. Arkusz: Słowniki
slowniki = [
    {"pole": "typ_dysponenta", "wartosc_dozwolona": "JST", "znaczenie": "Jednostka Samorządu Terytorialnego (Urząd Miasta, Gminy, Starostwo)"},
    {"pole": "typ_dysponenta", "wartosc_dozwolona": "Administracja_rzadowa", "znaczenie": "Ministerstwa, urzędy wojewódzkie, instytucje państwowe"},
    {"pole": "typ_dysponenta", "wartosc_dozwolona": "Podmiot_leczniczy", "znaczenie": "Szpitale, przychodnie, stacje ratownictwa"},
    {"pole": "typ_dysponenta", "wartosc_dozwolona": "Sluzby_mundurowe", "znaczenie": "PSP, OSP, Policja, Straż Miejska"},
    {"pole": "typ_dysponenta", "wartosc_dozwolona": "Przedsiebiorstwo", "znaczenie": "Firmy prywatne, galerie handlowe, dworce, zakłady pracy"},
    {"pole": "typ_dysponenta", "wartosc_dozwolona": "NGO_Inne", "znaczenie": "Fundacje, stowarzyszenia, uczelnie, wspólnoty mieszkaniowe"},
    {"pole": "dostepnosc_typ", "wartosc_dozwolona": "24_7", "znaczenie": "Dostępny całą dobę, 7 dni w tygodniu"},
    {"pole": "dostepnosc_typ", "wartosc_dozwolona": "godziny_otwarcia", "znaczenie": "Dostępny wyłącznie w godzinach otwarcia obiektu"},
    {"pole": "dostepnosc_typ", "wartosc_dozwolona": "ograniczona", "znaczenie": "Dostępny tylko dla pracowników/klientów/pasażerów po wejściu na teren"},
    {"pole": "czy_zamkniete", "wartosc_dozwolona": "NIE", "znaczenie": "Kapsuła otwarta lub otwierana bez klucza/kodu (może mieć alarm dźwiękowy)"},
    {"pole": "czy_zamkniete", "wartosc_dozwolona": "TAK_KLUCZ", "znaczenie": "Wymagany klucz fizyczny od ochrony/obsługi"},
    {"pole": "czy_zamkniete", "wartosc_dozwolona": "TAK_KOD", "znaczenie": "Wymagane wpisanie kodu PIN na kapsule"},
    {"pole": "czy_zamkniete", "wartosc_dozwolona": "TAK_OCHRONA", "znaczenie": "Urządzenie przechowywane bezpośrednio w pomieszczeniu ochrony/recepcji"},
    {"pole": "status_urzadzenia", "wartosc_dozwolona": "sprawne", "znaczenie": "Urządzenie gotowe do użycia"},
    {"pole": "status_urzadzenia", "wartosc_dozwolona": "w_serwisie", "znaczenie": "Urządzenie czasowo niedostępne (wymiana baterii/elektrod)"},
    {"pole": "status_urzadzenia", "wartosc_dozwolona": "wycofane", "znaczenie": "Urządzenie trwale zlikwidowane z danej lokalizacji"}
]

# 3. Arkusz: Dane przykładowe (wzorcowe)
dane_przykladowe = [
    {
        "id_aed": "UMW-AED-001",
        "nazwa_dysponenta": "Urząd Miasta Stołecznego Warszawy",
        "identyfikator_dysponenta": "5252248481",
        "typ_dysponenta": "JST",
        "wojewodztwo": "mazowieckie",
        "powiat": "Warszawa",
        "gmina": "Warszawa",
        "miejscowosc": "Warszawa",
        "ulica": "pl. Bankowy",
        "nr_budynku": "3/5",
        "kod_pocztowy": "00-950",
        "szerokosc_geo": 52.24285,
        "dlugosc_geo": 21.00214,
        "lokalizacja_szczegolowa": "Wejście główne B, parter przy portierni",
        "dostepnosc_typ": "godziny_otwarcia",
        "godziny_dostepnosci": "Pn-Pt 08:00-16:00",
        "czy_zamkniete": "NIE",
        "instrukcja_dostepu": "",
        "status_urzadzenia": "sprawne",
        "data_przegladu": "2026-09-15",
        "kontakt_dysponenta": "+48 22 443 00 00",
        "data_aktualizacji": "2026-11-21T12:00:00Z"
    },
    {
        "id_aed": "PKP-AED-104",
        "nazwa_dysponenta": "Polskie Koleje Państwowe S.A.",
        "identyfikator_dysponenta": "5250000251",
        "typ_dysponenta": "Przedsiebiorstwo",
        "wojewodztwo": "slaskie",
        "powiat": "Sosnowiec",
        "gmina": "Sosnowiec",
        "miejscowosc": "Sosnowiec",
        "ulica": "ul. 3 Maja",
        "nr_budynku": "16",
        "kod_pocztowy": "41-200",
        "szerokosc_geo": 50.27852,
        "dlugosc_geo": 19.12684,
        "lokalizacja_szczegolowa": "Hala główna dworca kolejowego przy kasach biletowych",
        "dostepnosc_typ": "24_7",
        "godziny_dostepnosci": "",
        "czy_zamkniete": "NIE",
        "instrukcja_dostepu": "",
        "status_urzadzenia": "sprawne",
        "data_przegladu": "2026-10-01",
        "kontakt_dysponenta": "+48 22 474 00 00",
        "data_aktualizacji": "2026-11-21T14:30:00Z"
    },
    {
        "id_aed": "KPRM-AED-002",
        "nazwa_dysponenta": "Kancelaria Prezesa Rady Ministrów",
        "identyfikator_dysponenta": "5261645000",
        "typ_dysponenta": "Administracja_rzadowa",
        "wojewodztwo": "mazowieckie",
        "powiat": "Warszawa",
        "gmina": "Warszawa",
        "miejscowosc": "Warszawa",
        "ulica": "Al. Ujazdowskie",
        "nr_budynku": "1/3",
        "kod_pocztowy": "00-583",
        "szerokosc_geo": 52.21941,
        "dlugosc_geo": 21.02431,
        "lokalizacja_szczegolowa": "Biuro Przepustek przy wejściu głównym",
        "dostepnosc_typ": "24_7",
        "godziny_dostepnosci": "",
        "czy_zamkniete": "TAK_OCHRONA",
        "instrukcja_dostepu": "Dostępne natychmiast u funkcjonariusza SOP na stanowisku ochrony 24/7",
        "status_urzadzenia": "sprawne",
        "data_przegladu": "2026-10-20",
        "kontakt_dysponenta": "+48 22 694 60 00",
        "data_aktualizacji": "2026-11-21T15:00:00Z"
    }
]

with pd.ExcelWriter("wzorzec_danych_aed.xlsx", engine="openpyxl") as writer:
    pd.DataFrame(schemat).to_excel(writer, sheet_name="Schemat_danych", index=False)
    pd.DataFrame(slowniki).to_excel(writer, sheet_name="Slowniki", index=False)
    pd.DataFrame(dane_przykladowe).to_excel(writer, sheet_name="Dane_przykladowe", index=False)

print("Gotowe! Utworzono wzorzec_danych_aed.xlsx")