"""Testy walidacji (app/validation.py) – kody błędów, NIP/REGON, warunki, puste komórki, pliki."""
import csv
import io
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from app import config, validation as v

WZORZEC = Path(__file__).resolve().parents[2] / "1_wzorzec_danych"


def dobry(**zmiany) -> dict:
    w = {
        "id_aed": "TEST-001", "nazwa_dysponenta": "Urząd Testowy", "identyfikator_dysponenta": "5252248481",
        "typ_dysponenta": "JST", "kontakt_dysponenta": "sekretariat@urzad.example", "wojewodztwo": "mazowieckie",
        "powiat": "Warszawa", "gmina": "Warszawa", "teryt_gmina": "1465011", "miejscowosc": "Warszawa", "simc": "0918123",
        "ulica": "ul. Testowa", "nr_budynku": "1", "kod_pocztowy": "00-001", "szerokosc_geo": 52.2, "dlugosc_geo": 21.0,
        "lokalizacja_szczegolowa": "Hol główny", "wewnatrz_budynku": "TAK", "dostepnosc_typ": "24_7",
        "czy_zamkniete": "NIE", "status_urzadzenia": "sprawne", "data_przegladu": "2026-09-15",
        "data_aktualizacji": "2026-11-21T12:00:00Z",
    }
    w.update(zmiany)
    return w


def kody(bledy, pole=None):
    return {b["kod"] for b in bledy if pole is None or b["pole"] == pole}


def test_poprawny_wiersz_bez_bledow():
    rek, bledy, ostrz = v.waliduj_wiersz(dobry())
    assert bledy == [] and ostrz == []
    assert rek["szerokosc_geo"] == 52.2 and rek["ulica"] == "ul. Testowa"


def test_required():
    rek, bledy, _ = v.waliduj_wiersz(dobry(miejscowosc=None, kod_pocztowy=""))
    assert kody(bledy, "miejscowosc") == {"required"} and kody(bledy, "kod_pocztowy") == {"required"}
    assert all("wiersz" in b and b["komunikat"] for b in bledy)


def test_enum():
    _, bledy, _ = v.waliduj_wiersz(dobry(typ_dysponenta="Firma", czy_zamkniete="MOZE"))
    assert kody(bledy, "typ_dysponenta") == {"enum"} and kody(bledy, "czy_zamkniete") == {"enum"}
    assert "Dozwolone" in bledy[0]["komunikat"]


def test_enum_tolerancja_wielkosci_liter_i_polskich_znakow():
    rek, bledy, _ = v.waliduj_wiersz(dobry(wojewodztwo="Slaskie", czy_zamkniete="nie"))
    assert bledy == []
    assert rek["wojewodztwo"] == "śląskie" and rek["czy_zamkniete"] == "NIE"


def test_pattern():
    _, bledy, _ = v.waliduj_wiersz(dobry(kod_pocztowy="00001", teryt_gmina="123", id_aed="ma spacje!"))
    assert kody(bledy, "kod_pocztowy") == {"pattern"}
    assert kody(bledy, "teryt_gmina") == {"pattern"}
    assert kody(bledy, "id_aed") == {"pattern"}


def test_range_wspolrzednych_i_dlugosci():
    _, bledy, _ = v.waliduj_wiersz(dobry(szerokosc_geo=21.0, dlugosc_geo=52.2, nr_budynku="1" * 30))
    assert kody(bledy, "szerokosc_geo") == {"range"} and kody(bledy, "dlugosc_geo") == {"range"}
    assert kody(bledy, "nr_budynku") == {"range"}


def test_type_liczba_data_datetime():
    _, bledy, _ = v.waliduj_wiersz(dobry(szerokosc_geo="abc", data_przegladu="15.09.2026", data_aktualizacji="wczoraj"))
    assert kody(bledy, "szerokosc_geo") == {"type"}
    assert kody(bledy, "data_przegladu") == {"type"}
    assert kody(bledy, "data_aktualizacji") == {"type"}


def test_liczby_z_przecinkiem_sa_normalizowane():
    rek, bledy, _ = v.waliduj_wiersz(dobry(szerokosc_geo="52,12345", dlugosc_geo=" 21,5 "))
    assert bledy == []
    assert rek["szerokosc_geo"] == pytest.approx(52.12345) and rek["dlugosc_geo"] == pytest.approx(21.5)


def test_daty_z_excela_sa_normalizowane():
    from datetime import date, datetime
    rek, bledy, _ = v.waliduj_wiersz(dobry(data_przegladu=datetime(2026, 9, 15), data_aktualizacji=datetime(2026, 11, 21, 12, 0)))
    assert bledy == []
    assert rek["data_przegladu"] == "2026-09-15" and rek["data_aktualizacji"] == "2026-11-21T12:00:00Z"
    rek, _, _ = v.waliduj_wiersz(dobry(data_przegladu=date(2026, 1, 2)))
    assert rek["data_przegladu"] == "2026-01-02"


def test_uri():
    _, bledy, _ = v.waliduj_wiersz(dobry(zdjecie_url="nie-adres"))
    assert kody(bledy, "zdjecie_url") == {"pattern"}
    _, bledy, _ = v.waliduj_wiersz(dobry(zdjecie_url="https://example.org/a.jpg"))
    assert bledy == []


def test_warunek_godziny_gdy_nie_24_7():
    _, bledy, _ = v.waliduj_wiersz(dobry(dostepnosc_typ="godziny_otwarcia"))
    assert kody(bledy, "godziny_dostepnosci") == {"warunek"}
    _, bledy, _ = v.waliduj_wiersz(dobry(dostepnosc_typ="godziny_otwarcia", godziny_dostepnosci="Mo-Fr 08:00-16:00"))
    assert bledy == []
    _, bledy, _ = v.waliduj_wiersz(dobry(dostepnosc_typ="24_7"))
    assert bledy == []


def test_warunek_instrukcja_gdy_zamkniete():
    for typ in ("TAK_KLUCZ", "TAK_KOD", "TAK_OCHRONA"):
        _, bledy, _ = v.waliduj_wiersz(dobry(czy_zamkniete=typ))
        assert kody(bledy, "instrukcja_dostepu") == {"warunek"}, typ
    _, bledy, _ = v.waliduj_wiersz(dobry(czy_zamkniete="TAK_KOD", instrukcja_dostepu="Kod podaje dyspozytor 112"))
    assert bledy == []


def test_zalecane_to_ostrzezenie_nie_blad():
    _, bledy, ostrz = v.waliduj_wiersz(dobry(teryt_gmina=None, simc=None, data_przegladu=None))
    assert bledy == []
    assert {o["pole"] for o in ostrz} == {"teryt_gmina", "simc", "data_przegladu"}
    assert {o["kod"] for o in ostrz} == {"zalecane"}


def test_ostrzezenie_o_kodzie_pin():
    _, bledy, ostrz = v.waliduj_wiersz(dobry(czy_zamkniete="TAK_KOD", instrukcja_dostepu="Kod do kapsuły: 1122"))
    assert bledy == []
    assert any(o["pole"] == "instrukcja_dostepu" and "PIN" in o["komunikat"] for o in ostrz)
    _, _, ostrz = v.waliduj_wiersz(dobry(czy_zamkniete="TAK_KLUCZ", instrukcja_dostepu="Klucz na portierni, tel. 22 443 00 00"))
    assert not any(o["pole"] == "instrukcja_dostepu" for o in ostrz)


def test_ostrzezenie_godziny_po_polsku():
    _, bledy, ostrz = v.waliduj_wiersz(dobry(dostepnosc_typ="godziny_otwarcia", godziny_dostepnosci="Pn-Pt 08:00-16:00"))
    assert bledy == [] and any(o["pole"] == "godziny_dostepnosci" for o in ostrz)


# --- NIP / REGON

@pytest.mark.parametrize("nip", ["5252248481", "5250000251", "5261645000", "6443453672"])
def test_nip_poprawny(nip):
    assert v.czy_nip(nip) and v.czy_poprawny_identyfikator(nip)


@pytest.mark.parametrize("nip", ["5252248482", "1234567890", "0000000000", "525224848", "52522484810"])
def test_nip_bledny(nip):
    assert not v.czy_nip(nip)


def test_regon9_i_regon14():
    assert v.czy_regon9("123456785") and v.czy_regon14("12345678512347")
    assert v.czy_poprawny_identyfikator("123456785") and v.czy_poprawny_identyfikator("12345678512347")
    assert not v.czy_regon9("123456786") and not v.czy_regon14("12345678512348")
    assert not v.czy_regon14("12345678612347")     # zła suma części 9-cyfrowej


def test_suma_kontrolna_w_wierszu():
    _, bledy, _ = v.waliduj_wiersz(dobry(identyfikator_dysponenta="5252248482"))
    assert kody(bledy, "identyfikator_dysponenta") == {"suma_kontrolna"}
    _, bledy, _ = v.waliduj_wiersz(dobry(identyfikator_dysponenta="123456786"))
    assert kody(bledy, "identyfikator_dysponenta") == {"suma_kontrolna"}
    _, bledy, _ = v.waliduj_wiersz(dobry(identyfikator_dysponenta="123456785"))
    assert bledy == []
    _, bledy, _ = v.waliduj_wiersz(dobry(identyfikator_dysponenta="12345"))     # zły wzorzec
    assert kody(bledy, "identyfikator_dysponenta") == {"pattern"}


def test_identyfikator_z_myslnikami_i_liczba_z_excela():
    rek, bledy, _ = v.waliduj_wiersz(dobry(identyfikator_dysponenta="525-224-84-81"))
    assert bledy == [] and rek["identyfikator_dysponenta"] == "5252248481"
    rek, bledy, _ = v.waliduj_wiersz(dobry(identyfikator_dysponenta=5252248481.0))
    assert bledy == [] and rek["identyfikator_dysponenta"] == "5252248481"


def test_zera_wiodace_przywracane_dla_liczb_z_excela():
    rek, _, _ = v.waliduj_wiersz(dobry(teryt_gmina=201011, simc=918123))
    assert rek["teryt_gmina"] == "0201011" and rek["simc"] == "0918123"


def test_waliduj_dysponenta_formularz():
    assert v.waliduj_dysponenta("Urząd", "5252248481", "JST") == []
    b = v.waliduj_dysponenta("", "5252248482", "Cokolwiek")
    assert {(e["pole"], e["kod"]) for e in b} == {("nazwa_dysponenta", "required"), ("identyfikator_dysponenta", "suma_kontrolna"),
                                                 ("typ_dysponenta", "enum")}


# --- "nan" i puste komórki

@pytest.mark.parametrize("pusta", [None, "", "  ", "nan", "NaN", "None", "NaT", float("nan")])
def test_puste_wartosci_to_none_nigdy_nan(pusta):
    rek, _, _ = v.waliduj_wiersz(dobry(ulica=pusta, kondygnacja=pusta, producent_model=pusta))
    assert rek["ulica"] is None and rek["kondygnacja"] is None and rek["producent_model"] is None
    assert all(x != "nan" for x in rek.values())


# --- pliki

def zrob_csv(wiersze, naglowki=None, sep=",", bom=False):
    naglowki = naglowki or list(dobry().keys())
    bufor = io.StringIO()
    w = csv.writer(bufor, delimiter=sep)
    w.writerow(naglowki)
    for r in wiersze:
        w.writerow([("" if r.get(h) is None else r.get(h)) for h in naglowki])
    return (("﻿" if bom else "") + bufor.getvalue()).encode("utf-8")


@pytest.mark.parametrize("sep,bom", [(",", False), (";", False), (",", True), (";", True)])
def test_csv_separatory_i_bom(sep, bom):
    raport = v.waliduj_plik(zrob_csv([dobry()], sep=sep, bom=bom), "x.csv")
    assert raport.bledy == [] and raport.poprawne_wiersze == 1


def test_csv_z_przecinkiem_dziesietnym_w_srednikowym():
    raport = v.waliduj_plik(zrob_csv([dobry(szerokosc_geo="52,2", dlugosc_geo="21,0")], sep=";"), "x.csv")
    assert raport.bledy == [] and raport.rekordy[0]["szerokosc_geo"] == pytest.approx(52.2)


def test_csv_cp1250():
    dane = zrob_csv([dobry(lokalizacja_szczegolowa="Żółć")]).decode("utf-8").encode("cp1250")
    raport = v.waliduj_plik(dane, "x.csv")
    assert raport.bledy == [] and raport.rekordy[0]["lokalizacja_szczegolowa"] == "Żółć"


def test_numery_wierszy_naglowek_to_1():
    raport = v.waliduj_plik(zrob_csv([dobry(), dobry(id_aed="B", miejscowosc=""), dobry(id_aed="C")]), "x.csv")
    assert raport.poprawne_wiersze == 2 and raport.bledne_wiersze == 1
    assert [(b["wiersz"], b["pole"]) for b in raport.bledy] == [(3, "miejscowosc")]


def test_brak_wymaganej_kolumny_to_jeden_blad_naglowka():
    naglowki = [h for h in dobry().keys() if h != "kod_pocztowy"]
    raport = v.waliduj_plik(zrob_csv([dobry(), dobry(id_aed="B")], naglowki=naglowki), "x.csv")
    assert [b for b in raport.bledy if b["pole"] == "kod_pocztowy"] == [
        {"wiersz": 1, "pole": "kod_pocztowy", "kod": "required", "komunikat": raport.bledy[0]["komunikat"]}]
    assert raport.poprawne_wiersze == 0 and raport.bledne_wiersze == 2


def test_brak_kolumn_zalecanych_to_jedno_ostrzezenie():
    naglowki = [h for h in dobry().keys() if h != "teryt_gmina"]
    raport = v.waliduj_plik(zrob_csv([dobry(), dobry(id_aed="B")], naglowki=naglowki), "x.csv")
    assert raport.bledy == []
    assert len([o for o in raport.ostrzezenia if o["pole"] == "teryt_gmina"]) == 1


def test_nieznana_kolumna_ostrzezenie():
    raport = v.waliduj_plik(zrob_csv([dobry(dziwna="x")], naglowki=list(dobry().keys()) + ["dziwna"]), "x.csv")
    assert raport.bledy == [] and any(o["pole"] == "dziwna" for o in raport.ostrzezenia)


def test_duplikat_id_w_pliku():
    raport = v.waliduj_plik(zrob_csv([dobry(), dobry()]), "x.csv")
    assert raport.poprawne_wiersze == 1 and raport.bledne_wiersze == 1
    assert kody(raport.bledy) == {"duplikat"} and raport.bledy[0]["wiersz"] == 3


def test_nadpisania_z_formularza():
    w = dobry(nazwa_dysponenta="Inna nazwa", identyfikator_dysponenta="5250000251")
    raport = v.waliduj_plik(zrob_csv([w]), "x.csv", {"nazwa_dysponenta": "Z formularza", "identyfikator_dysponenta": "5252248481", "typ_dysponenta": "NGO_Inne"})
    assert raport.bledy == []
    r = raport.rekordy[0]
    assert (r["nazwa_dysponenta"], r["identyfikator_dysponenta"], r["typ_dysponenta"]) == ("Z formularza", "5252248481", "NGO_Inne")
    assert any("formularza" in o["komunikat"] for o in raport.ostrzezenia)


def test_kolumny_dysponenta_moga_pochodzic_z_formularza():
    naglowki = [h for h in dobry().keys() if h not in ("nazwa_dysponenta", "identyfikator_dysponenta", "typ_dysponenta")]
    dane = zrob_csv([dobry()], naglowki=naglowki)
    assert v.waliduj_plik(dane, "x.csv").poprawne_wiersze == 0
    nadp = {"nazwa_dysponenta": "X", "identyfikator_dysponenta": "5252248481", "typ_dysponenta": "JST"}
    assert v.waliduj_plik(dane, "x.csv", nadp).poprawne_wiersze == 1


def test_zly_format_i_puste_pliki():
    with pytest.raises(v.BladPliku) as e:
        v.wczytaj_plik(b"abc", "x.txt")
    assert e.value.status == 400
    with pytest.raises(v.BladPliku):
        v.wczytaj_plik(b"", "x.csv")
    with pytest.raises(v.BladPliku):
        v.wczytaj_plik(b"to nie jest zip", "x.xlsx")


def test_limit_rozmiaru_pliku(monkeypatch):
    monkeypatch.setattr(config, "MAX_FILE_BYTES", 100)
    with pytest.raises(v.BladPliku) as e:
        v.wczytaj_plik(b"a" * 101, "x.csv")
    assert e.value.status == 413


def test_limit_liczby_wierszy(monkeypatch):
    monkeypatch.setattr(config, "MAX_ROWS", 2)
    with pytest.raises(v.BladPliku) as e:
        v.waliduj_plik(zrob_csv([dobry(id_aed=str(i)) for i in range(3)]), "x.csv")
    assert e.value.status == 413


def test_plik_z_samym_naglowkiem():
    raport = v.waliduj_plik(zrob_csv([]), "x.csv")
    assert raport.poprawne_wiersze == 0 and raport.bledy and "nie zawiera wierszy" in raport.bledy[0]["komunikat"]


def test_wzorzec_csv_waliduje_sie_bez_bledow():
    raport = v.waliduj_plik((WZORZEC / "wzorzec_danych_aed.csv").read_bytes(), "wzorzec_danych_aed.csv")
    assert raport.bledy == [] and raport.poprawne_wiersze == 3


def test_wzorzec_xlsx_arkusz_dane_pusty_jest_zglaszany():
    raport = v.waliduj_plik((WZORZEC / "wzorzec_danych_aed.xlsx").read_bytes(), "wzorzec_danych_aed.xlsx")
    assert raport.poprawne_wiersze == 0 and "Dane_przykladowe" in raport.bledy[0]["komunikat"]


def xlsx_z_arkuszami(**arkusze):
    wb = Workbook()
    wb.remove(wb.active)
    for nazwa, (naglowki, wiersze) in arkusze.items():
        ws = wb.create_sheet(nazwa)
        ws.append(naglowki)
        for w in wiersze:
            ws.append(w)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_xlsx_wybor_arkusza_i_puste_komorki():
    naglowki = list(dobry().keys())
    wiersz = [dobry().get(h) for h in naglowki]
    dane = xlsx_z_arkuszami(Inny=(["a"], [["b"]]), Dane_przykladowe=(naglowki, [wiersz]))
    raport = v.waliduj_plik(dane, "x.xlsx")
    assert raport.arkusz == "Dane_przykladowe" and raport.bledy == []
    assert raport.rekordy[0]["ulica"] == "ul. Testowa" and raport.rekordy[0]["producent_model"] is None
    dane = xlsx_z_arkuszami(Pierwszy=(naglowki, [wiersz]), Drugi=(["a"], [["b"]]))
    assert v.waliduj_plik(dane, "x.xlsx").arkusz == "Pierwszy"
    dane = xlsx_z_arkuszami(Dane=(naglowki, [wiersz]), Dane_przykladowe=(["a"], [["b"]]))
    assert v.waliduj_plik(dane, "x.xlsx").arkusz == "Dane"


def test_xlsx_z_wzorca_przyklady_zero_bledow():
    wb = load_workbook(WZORZEC / "wzorzec_danych_aed.xlsx")
    del wb["Dane"]
    bio = io.BytesIO()
    wb.save(bio)
    raport = v.waliduj_plik(bio.getvalue(), "w.xlsx")
    assert raport.arkusz == "Dane_przykladowe"
    assert raport.bledy == [] and raport.poprawne_wiersze == 3
    assert all(isinstance(r["szerokosc_geo"], float) for r in raport.rekordy)
    assert all(x != "nan" for r in raport.rekordy for x in r.values())
