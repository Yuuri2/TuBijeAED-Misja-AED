"""Dane przykładowe (demo) – ładowane tylko do pustej bazy. Właściciel: Backend.

To NIE są dane z dane.gov.pl ani oficjalne dane wymienionych instytucji – służą wyłącznie
do pokazania działania prototypu i są wyraźnie oznaczone w polu `zrodlo_nazwa`.
"""
from __future__ import annotations

from . import repo

ZRODLO_ID = "dysponent:demo"
NAZWA_ZRODLA = "DANE PRZYKŁADOWE (demo)"

_WSPOLNE = {
    "zrodlo_typ": "DYSPONENT",
    "zrodlo_nazwa": NAZWA_ZRODLA,
    "licencja": "CC BY 4.0",
    "status_weryfikacji": "ZGLOSZONY_PRZEZ_DYSPONENTA",
    "zrodlo_id": ZRODLO_ID,
    "wewnatrz_budynku": "TAK",
    "status_urzadzenia": "sprawne",
}

REKORDY_PRZYKLADOWE = [
    {**_WSPOLNE,
     "id_aed": "UMW-AED-001", "nazwa_dysponenta": "Urząd Miasta Stołecznego Warszawy", "identyfikator_dysponenta": "5252248481",
     "typ_dysponenta": "JST", "kontakt_dysponenta": "+48 22 443 00 00",
     "wojewodztwo": "mazowieckie", "powiat": "Warszawa", "gmina": "Warszawa", "teryt_gmina": "1465011",
     "miejscowosc": "Warszawa", "simc": "0918123", "ulica": "pl. Bankowy", "nr_budynku": "3/5", "kod_pocztowy": "00-950",
     "szerokosc_geo": 52.24285, "dlugosc_geo": 21.00214, "lokalizacja_szczegolowa": "Wejście główne B, parter przy portierni",
     "kondygnacja": "0", "dostepnosc_typ": "godziny_otwarcia", "godziny_dostepnosci": "Mo-Fr 08:00-16:00",
     "czy_zamkniete": "NIE", "elektrody_pediatryczne": "TAK", "data_przegladu": "2026-09-15",
     "data_aktualizacji": "2026-11-21T12:00:00Z"},
    {**_WSPOLNE,
     "id_aed": "PKP-AED-104", "nazwa_dysponenta": "Polskie Koleje Państwowe S.A.", "identyfikator_dysponenta": "5250000251",
     "typ_dysponenta": "Przedsiebiorstwo", "kontakt_dysponenta": "+48 22 474 00 00",
     "wojewodztwo": "śląskie", "powiat": "Sosnowiec", "gmina": "Sosnowiec", "teryt_gmina": "2473011",
     "miejscowosc": "Sosnowiec", "simc": "0969928", "ulica": "ul. 3 Maja", "nr_budynku": "16", "kod_pocztowy": "41-200",
     "szerokosc_geo": 50.27852, "dlugosc_geo": 19.12684,
     "lokalizacja_szczegolowa": "Hala główna dworca kolejowego przy kasach biletowych",
     "kondygnacja": "0", "dostepnosc_typ": "24_7", "czy_zamkniete": "TAK_KOD",
     "instrukcja_dostepu": "Kod podaje dyspozytor numeru 112", "elektrody_pediatryczne": "BRAK_DANYCH",
     "data_przegladu": "2026-10-01", "data_aktualizacji": "2026-11-21T14:30:00Z"},
    {**_WSPOLNE,
     "id_aed": "KPRM-AED-002", "nazwa_dysponenta": "Kancelaria Prezesa Rady Ministrów", "identyfikator_dysponenta": "5261645000",
     "typ_dysponenta": "Administracja_rzadowa", "kontakt_dysponenta": "+48 22 694 60 00",
     "wojewodztwo": "mazowieckie", "powiat": "Warszawa", "gmina": "Warszawa", "teryt_gmina": "1465011",
     "miejscowosc": "Warszawa", "simc": "0918123", "ulica": "Al. Ujazdowskie", "nr_budynku": "1/3", "kod_pocztowy": "00-583",
     "szerokosc_geo": 52.21941, "dlugosc_geo": 21.02431, "lokalizacja_szczegolowa": "Biuro Przepustek przy wejściu głównym",
     "kondygnacja": "0", "dostepnosc_typ": "24_7", "czy_zamkniete": "TAK_OCHRONA",
     "instrukcja_dostepu": "Dostępne natychmiast u funkcjonariusza ochrony na stanowisku 24/7",
     "elektrody_pediatryczne": "NIE", "data_przegladu": "2026-10-20", "data_aktualizacji": "2026-11-21T15:00:00Z"},
]


def zasiej_jesli_pusta() -> int:
    """Zapisuje dane przykładowe, gdy w bazie nie ma żadnych rekordów. Zwraca liczbę zapisanych rekordów."""
    if not repo.czy_baza_pusta():
        return 0
    repo.zarejestruj_zrodlo(repo.Zrodlo(id=ZRODLO_ID, typ="DYSPONENT", nazwa=NAZWA_ZRODLA, url=None, licencja="CC BY 4.0"))
    wynik = repo.zapisz_rekordy(REKORDY_PRZYKLADOWE, ZRODLO_ID, zastap=True)
    return wynik.dodano
