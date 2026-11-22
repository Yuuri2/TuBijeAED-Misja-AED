"""Dane demo prototypu portalu (działa BEZ sieci). Właściciel: Backend. Kontrakt: docs/PROTOTYP.md („Dane demo”).

Co powstaje:
* Ministerstwo Cyfryzacji (state) – właściciel zbioru „Wykaz defibrylatorów AED – wykaz zbiorczy”.
* 4 urzędy gmin (local) z zasobami AED zmigrowanymi z PRAWDZIWYCH plików dane.gov.pl
  (`app/portal/dane_demo/`, przycięte) istniejącym kodem `app/sources/danegov.py` + `mapowania_danegov.py`
  -> CSV wg wzorca -> zasób z `wykaz_typ="AED"`.
* Urząd m.st. Warszawy (local) – bez zasobu AED („jeszcze nie dołączył”).
* Podmioty FIKCYJNE (nazwy jawnie przykładowe, NIP/REGON testowe z poprawną sumą kontrolną):
  Partner (komplet danych, godziny OSM, bez PIN-ów), spółdzielnia (dane starsze niż 12 mies. -> odznaka wygasła;
  jeden AED 15 m od AED Legionowa -> raport potencjalnych duplikatów) i sklep z zasobem z błędami (odrzucenie).

Uczciwość danych gmin (decyzja Backendu do akceptacji Managera):
Źródła gmin nie podają pól wymaganych przez wzorzec: `wewnatrz_budynku`, `dostepnosc_typ`, `czy_zamkniete`,
`status_urzadzenia`. Konwersja NIE zgaduje tych wartości. Ustawia wartość „nieznana” wyłącznie tam, gdzie słownik
w aed_schema.json ją przewiduje (dziś tylko `status_urzadzenia = "nieznany"`; jeśli schemat dostanie wartość
`BRAK_DANYCH` w innych słownikach – kod użyje jej automatycznie). Pozostałe braki zostają brakami, więc zasoby
Krosna i Marek (oraz zasoby gmin bez scenariusza uzupełnienia) są odrzucane z raportem per wiersz (dodatkowo mają prawdziwe usterki: brak numeru
budynku, w Markach współrzędne skopiowane z Krosna).
Aby wykaz miał ≥ 4 dostawców i ≥ 2 województwa, Legionowo (mazowieckie) i Przemyśl (podkarpackie) odgrywają scenariusz „urząd uzupełnił braki
w asystencie dostawcy”: brakujące pola dostępu dostają wartości ZACHOWAWCZE, jawnie oznaczone jako demo
(tytuł i opis zasobu, `instrukcja_dostepu` = „DANE DEMO …”). To jedyne miejsce, gdzie seed dopisuje wartości.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone

from .. import config, schema
from . import repo_portal, wykazy

logger = logging.getLogger("tubijeaed.seed")

NAZWA_MC = "Ministerstwo Cyfryzacji"

# zbiór dane.gov.pl -> (plik z danymi, format, id instytucji w plikach demo)
GMINY = {
    "3624": ("krosno_3624.csv", "csv", "229"),
    "4581": ("przemysl_62093.geojson", "geojson", "145"),
    "4955": ("marki_4955.csv", "csv", "537"),
    "40593": ("legionowo_2625221.csv", "csv", "297"),
}
WARSZAWA_INSTYTUCJA = "7621"

# Scenariusz demo „dostawca uzupełnił braki w asystencie” – TYLKO dla wymienionych zbiorów i tylko puste pola.
ZNACZNIK_DEMO = "DANE DEMO: sposób dostępu nie pochodzi z zasobu urzędu – zapytaj w obiekcie lub zadzwoń 112."
UZUPELNIENIA_DEMO: dict[str, dict] = {
    "40593": {
        "wewnatrz_budynku": "TAK",
        "dostepnosc_typ": "godziny_otwarcia",
        "godziny_dostepnosci": "Mo-Fr 08:00-16:00",
        "czy_zamkniete": "TAK_OCHRONA",
        "instrukcja_dostepu": ZNACZNIK_DEMO,
    },
    # Przemyśl (podkarpackie): ten sam scenariusz – gmina przekonwertowała stary zasób i uzupełniła braki.
    "4581": {
        "wewnatrz_budynku": "NIE",
        "dostepnosc_typ": "24_7",
        "godziny_dostepnosci": "24/7",
        "czy_zamkniete": "NIE",
        "instrukcja_dostepu": ZNACZNIK_DEMO,
    },
}
# Dodatkowo ręcznie poprawiane usterki źródła (zbiór -> id_aed -> pola), też jawnie jako demo.
POPRAWKI_DEMO: dict[str, dict[str, dict]] = {
    "4581": {"753": {"nr_budynku": "19"}},   # numer budynku jest w opisie lokalizacji źródła
}
WARTOSCI_NIEZNANE = ("nieznany", "BRAK_DANYCH")

DOMYSLNE = {"wojewodztwo": "mazowieckie", "teryt_gmina": "1465011", "simc": "0918123", "data_aktualizacji": None}

PARTNER = {
    "nazwa": "Galeria Przykładowa sp. z o.o. (firma fikcyjna – demo)", "typ": "private",
    "nip": "1234563218", "regon": "123456785", "email": "recepcja@galeria-przykladowa.example",
    "www": "https://galeria-przykladowa.example",
}
SPOLDZIELNIA = {
    "nazwa": "Przykładowa Spółdzielnia Mieszkaniowa „Osiedle Demo” (fikcyjna)", "typ": "other",
    "nip": None, "regon": "234567895", "email": "administracja@sm-demo.example", "www": None,
}
SKLEP = {
    "nazwa": "Sklep Przykładowy „Demo” (firma fikcyjna – zasób z błędami)", "typ": "private",
    "nip": "5556667776", "regon": "345678901", "email": "kontakt@sklep-demo.example", "www": None,
}


def _rekord(**kw) -> dict:
    r = {p: None for p in schema.nazwy_pol()}
    r.update(kw)
    return r


def _rekordy_partnera(teraz: str) -> list[dict]:
    wspolne = dict(nazwa_dysponenta=PARTNER["nazwa"], identyfikator_dysponenta=PARTNER["nip"],
                   typ_dysponenta="Przedsiebiorstwo", kontakt_dysponenta="+48 22 000 00 00 (ochrona obiektu)",
                   wojewodztwo="mazowieckie", powiat="Warszawa", gmina="Warszawa", teryt_gmina="1465011",
                   miejscowosc="Warszawa", simc="0918123", ulica="ul. Przykładowa", nr_budynku="1", kod_pocztowy="00-001",
                   elektrody_pediatryczne="TAK", status_urzadzenia="sprawne", data_przegladu="2026-10-15",
                   producent_model="Philips HeartStart FRx", data_aktualizacji=teraz)
    return [
        _rekord(**wspolne, id_aed="GP-AED-01", szerokosc_geo=52.23170, dlugosc_geo=21.00590,
                lokalizacja_szczegolowa="Parter, hol główny przy punkcie informacji, na lewo od wind", kondygnacja="0",
                wewnatrz_budynku="TAK", dostepnosc_typ="godziny_otwarcia",
                godziny_dostepnosci="Mo-Sa 09:00-21:00; Su 10:00-20:00", czy_zamkniete="NIE"),
        _rekord(**wspolne, id_aed="GP-AED-02", szerokosc_geo=52.23205, dlugosc_geo=21.00655,
                lokalizacja_szczegolowa="Poziom 1, strefa restauracyjna, przy toaletach", kondygnacja="1",
                wewnatrz_budynku="TAK", dostepnosc_typ="godziny_otwarcia",
                godziny_dostepnosci="Mo-Sa 09:00-21:00; Su 10:00-20:00", czy_zamkniete="NIE"),
        _rekord(**wspolne, id_aed="GP-AED-03", szerokosc_geo=52.23140, dlugosc_geo=21.00540,
                lokalizacja_szczegolowa="Kapsuła na elewacji przy wejściu od ul. Przykładowej (całodobowo)", kondygnacja="0",
                wewnatrz_budynku="NIE", dostepnosc_typ="24_7", godziny_dostepnosci="24/7", czy_zamkniete="NIE"),
    ]


def _rekordy_spoldzielni() -> list[dict]:
    wspolne = dict(nazwa_dysponenta=SPOLDZIELNIA["nazwa"], identyfikator_dysponenta=SPOLDZIELNIA["regon"],
                   typ_dysponenta="NGO_Inne", kontakt_dysponenta="administracja@sm-demo.example",
                   wojewodztwo="mazowieckie", powiat="legionowski", gmina="Legionowo", teryt_gmina="1408011",
                   miejscowosc="Legionowo", simc="0920806", kod_pocztowy="05-120", status_urzadzenia="sprawne",
                   elektrody_pediatryczne="NIE", data_przegladu="2025-05-20", data_aktualizacji="2025-06-30T10:00:00Z")
    return [
        # ~15 m od AED „Urząd Miasta Legionowo” z zasobu gminy -> potencjalny duplikat w raporcie jakości
        _rekord(**wspolne, id_aed="SMD-1", ulica="ul. Piłsudskiego", nr_budynku="41A",
                szerokosc_geo=52.395333, dlugosc_geo=20.931382, wewnatrz_budynku="NIE",
                lokalizacja_szczegolowa="Kapsuła AED na ścianie pawilonu administracji osiedla", dostepnosc_typ="24_7",
                godziny_dostepnosci="24/7", czy_zamkniete="NIE"),
        _rekord(**wspolne, id_aed="SMD-2", ulica="ul. Przykładowa", nr_budynku="7",
                szerokosc_geo=52.40110, dlugosc_geo=20.92480, wewnatrz_budynku="TAK", kondygnacja="0",
                lokalizacja_szczegolowa="Klatka B, parter, przy skrzynkach pocztowych", dostepnosc_typ="godziny_otwarcia",
                godziny_dostepnosci="Mo-Fr 07:00-19:00", czy_zamkniete="TAK_KLUCZ",
                instrukcja_dostepu="Klucz u gospodarza domu (tel. na tablicy w klatce)"),
    ]


def _rekordy_sklepu() -> list[dict]:
    wspolne = dict(nazwa_dysponenta=SKLEP["nazwa"], typ_dysponenta="Przedsiebiorstwo",
                   kontakt_dysponenta="kontakt@sklep-demo.example", wojewodztwo="mazowieckie", powiat="Warszawa",
                   gmina="Warszawa", miejscowosc="Warszawa", ulica="ul. Demonstracyjna", nr_budynku="5",
                   kod_pocztowy="00-002", wewnatrz_budynku="TAK", status_urzadzenia="sprawne",
                   data_aktualizacji="2026-11-01T09:00:00Z")
    return [
        _rekord(**wspolne, id_aed="SD-1", identyfikator_dysponenta="5556667777",          # zła suma kontrolna NIP
                szerokosc_geo=52.2400, dlugosc_geo=21.0100, lokalizacja_szczegolowa="Przy kasach",
                dostepnosc_typ="godziny_otwarcia", godziny_dostepnosci="Pn-Pt 8-16", czy_zamkniete="NIE"),
        _rekord(**wspolne, id_aed="SD-2", identyfikator_dysponenta=SKLEP["nip"],
                szerokosc_geo=21.0100, dlugosc_geo=52.2400,                                # zamienione współrzędne
                lokalizacja_szczegolowa="Zaplecze", dostepnosc_typ="24_7", czy_zamkniete="NIE"),
        _rekord(**wspolne, id_aed="SD-3", identyfikator_dysponenta=SKLEP["nip"],
                szerokosc_geo=52.2401, dlugosc_geo=21.0102, lokalizacja_szczegolowa="Biuro",
                dostepnosc_typ="ograniczona", czy_zamkniete="TAK_KOD"),                    # brak godzin i instrukcji
    ]


def do_csv(rekordy: list[dict]) -> bytes:
    """Rekordy -> CSV UTF-8 w układzie wzorca (kolumny i kolejność z aed_schema.json)."""
    kolumny = schema.nazwy_pol()
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(kolumny)
    for r in rekordy:
        w.writerow(["" if r.get(k) is None else r.get(k) for k in kolumny])
    return buf.getvalue().encode("utf-8")


def _uzupelnij_nieznane(r: dict) -> None:
    """Pusta wartość wymaganego pola słownikowego -> wartość „nieznana”, ale TYLKO jeśli słownik ją przewiduje."""
    for p in schema.pola():
        enum = (p.get("constraints") or {}).get("enum")
        if r.get(p["name"]) is None and p.get("x-wymagane") == "TAK" and enum:
            znana = next((v for v in WARTOSCI_NIEZNANE if v in enum), None)
            if znana:
                r[p["name"]] = znana


def konwertuj_gmine(zbior_id: str) -> tuple[list[dict], dict, dict, dict]:
    """Plik gminy z plików demo -> rekordy wzorca (istniejące app/sources/danegov.normalizuj).
    Zwraca (rekordy, atrybuty zbioru, atrybuty instytucji, zasób dane.gov.pl)."""
    from ..sources import czytniki, danegov
    from ..sources.mapowania_danegov import MAPOWANIA

    plik, fmt, inst = GMINY[zbior_id]
    fix = config.DANEGOV_FIXTURES_DIR
    zbior = json.loads((fix / f"dataset_{zbior_id}.json").read_text(encoding="utf-8"))["data"]
    instytucja = json.loads((fix / f"institution_{inst}.json").read_text(encoding="utf-8"))["data"]
    zasoby = json.loads((fix / f"resources_{zbior_id}.json").read_text(encoding="utf-8"))["data"]
    konfig = MAPOWANIA[zbior_id]
    zasob = danegov.wybierz_zasob(zasoby, set(konfig.get("zasoby") or []) or None, konfig)
    wiersze = czytniki.czytaj((fix / plik).read_bytes(), fmt)
    rekordy, _ = danegov.normalizuj(wiersze, zbior=zbior, instytucja=instytucja, zasob=zasob, konfig=konfig,
                                    data_pobrania="2026-11-22T00:00:00Z")
    pola = schema.nazwy_pol()
    wynik = []
    for r in rekordy:
        r = {k: r.get(k) for k in pola}            # pola systemowe integratora nie należą do zasobu dostawcy
        _uzupelnij_nieznane(r)
        for k, v in UZUPELNIENIA_DEMO.get(zbior_id, {}).items():
            if r.get(k) is None:
                r[k] = v
        for k, v in POPRAWKI_DEMO.get(zbior_id, {}).get(str(r.get("id_aed")), {}).items():
            if r.get(k) is None:
                r[k] = v
        wynik.append(r)
    return wynik, zbior["attributes"], instytucja["attributes"], zasob or {}


def _instytucja_z_demo(inst_id: str) -> dict:
    a = json.loads((config.DANEGOV_FIXTURES_DIR / f"institution_{inst_id}.json").read_text(encoding="utf-8"))["data"]["attributes"]
    return repo_portal.utworz_instytucje(nazwa=a["title"], typ=a.get("institution_type") or "local", regon=a.get("regon"),
                                         nip=a.get("nip"), email=a.get("email"), www=a.get("website"))


def zasiej() -> dict:
    """Tworzy dane demo w (pustej) bazie portalu i buduje wykaz zbiorczy. Zwraca podsumowanie."""
    teraz = datetime.now(timezone.utc)
    teraz_iso = teraz.strftime("%Y-%m-%dT%H:%M:%SZ")
    podsumowanie: dict = {"instytucje": 0, "zasoby": []}

    repo_portal.utworz_instytucje(nazwa=NAZWA_MC, typ="state", www="https://www.gov.pl/web/cyfryzacja")
    podsumowanie["instytucje"] += 1

    # ---- gminy: migracja prawdziwych zasobów dane.gov.pl do wzorca
    for zid in GMINY:
        rekordy, za, _, zasob = konwertuj_gmine(zid)
        inst = _instytucja_z_demo(GMINY[zid][2])
        podsumowanie["instytucje"] += 1
        demo = zid in UZUPELNIENIA_DEMO
        zb = repo_portal.utworz_zbior(
            inst["id"], tytul=za.get("title") or "Defibrylatory AED",
            opis=(f"Zbiór zaimportowany do prototypu z dane.gov.pl (zbiór {zid}). Zasób AED przekonwertowano do "
                  "wzorcowego zakresu danych istniejącym modułem migracji (asystent dostawcy)."),
            licencja=za.get("license_name") or "CC BY 4.0", czestotliwosc="irregular",
            slowa_kluczowe=["AED", "defibrylator"], zrodlo="harvester", ext_ident=f"dane.gov.pl:{zid}")
        tytul = "Defibrylatory AED – dane wg wzorca" + (" (uzupełnione – DANE DEMO)" if demo else "")
        opis = (f"Zasób {zasob.get('id', '')} z dane.gov.pl przekonwertowany do wzorca AED. Pola, których źródło nie "
                "podaje, pozostawiono puste (status urządzenia: „nieznany”).")
        if demo:
            opis += (" SCENARIUSZ DEMO: brakujące pola dostępu (wewnątrz budynku, typ dostępności, godziny, "
                     "zabezpieczenie) uzupełniono w prototypie wartościami przykładowymi – nie pochodzą od urzędu.")
        data_danych = ((zasob.get("attributes") or {}).get("modified") or za.get("modified") or "")[:10] or None
        w = repo_portal.dodaj_lub_zaktualizuj_zasob(
            zb["id"], tytul=tytul, opis=opis, plik=do_csv(rekordy), nazwa_pliku=f"aed_{zid}_wzorzec.csv",
            wykaz_typ="AED", data_danych=data_danych, ext_ident=f"dane.gov.pl:{zid}:aed", przebuduj=False)
        podsumowanie["zasoby"].append((inst["nazwa"], w["zasob"]["walidacja_status"]))

    _instytucja_z_demo(WARSZAWA_INSTYTUCJA)            # bez zasobu AED – „jeszcze nie dołączył”
    podsumowanie["instytucje"] += 1

    # ---- podmioty fikcyjne
    for dane, rekordy, data_danych, tytul_zb in (
        (PARTNER, _rekordy_partnera(teraz_iso), teraz_iso[:10], "Defibrylatory AED w Galerii Przykładowej"),
        (SPOLDZIELNIA, _rekordy_spoldzielni(), "2025-06-30", "Defibrylatory AED na osiedlu"),
        (SKLEP, _rekordy_sklepu(), "2026-11-01", "Defibrylator w sklepie"),
    ):
        inst = repo_portal.utworz_instytucje(**dane)
        podsumowanie["instytucje"] += 1
        zb = repo_portal.utworz_zbior(inst["id"], tytul=tytul_zb,
                                      opis="DANE PRZYKŁADOWE (podmiot fikcyjny) – do demonstracji prototypu.",
                                      slowa_kluczowe=["AED", "defibrylator", "demo"])
        w = repo_portal.dodaj_lub_zaktualizuj_zasob(
            zb["id"], tytul="Lokalizacje AED (wzorzec #TuBijeAED)", opis="DANE PRZYKŁADOWE (podmiot fikcyjny).",
            plik=do_csv(rekordy), nazwa_pliku="aed.csv", wykaz_typ="AED", data_danych=data_danych, przebuduj=False)
        podsumowanie["zasoby"].append((inst["nazwa"], w["zasob"]["walidacja_status"]))

    info = wykazy.utworz_wykaz_zbiorczy("AED")
    podsumowanie["wykaz"] = {k: info.get(k) for k in ("status", "liczba_rekordow", "liczba_dostawcow", "komunikat")}
    logger.info("Seed portalu: %s", podsumowanie)
    return podsumowanie


def zasiej_jesli_pusty() -> dict | None:
    """Seed przy starcie aplikacji – tylko gdy w bazie portalu nie ma żadnej instytucji."""
    if not repo_portal.czy_portal_pusty():
        if wykazy.aktualny_wykaz("AED") is None:          # np. pliki media usunięte – odtwórz wykaz
            wykazy.utworz_wykaz_zbiorczy("AED")
        return None
    return zasiej()
