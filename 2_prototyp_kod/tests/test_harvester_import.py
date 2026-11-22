"""Import XML harvestera (1.13 / 1.14) – z podmienionym repo_portal (jednostkowe) i z prawdziwym (integracyjne).

Testy integracyjne są pomijane, dopóki Backend nie zaimplementuje app/portal (NotImplementedError).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import harvester
from app.exports import harvester_xml
from app.portal import repo_portal
from app.portal.wykazy import BladWykazu

FIX = Path(__file__).parent / "fixtures"
PRZYKLAD_114 = (FIX / "harvester" / "import_aed_1_14.xml").read_bytes()
PRZYKLAD_113 = (FIX / "harvester_example_1_13.xml").read_bytes()
DEMO_CSV = (harvester.KATALOG_DEMO / "warszawa_aed_demo.csv").read_bytes()


class RepoFake:
    """Minimalna atrapa repo_portal: upsert po ext_ident, reguły wykazu jak w kontrakcie (422 / 409)."""

    def __init__(self):
        self.zbiory: dict[str, dict] = {}
        self.zasoby: dict[str, dict] = {}
        self.wywolania: list[dict] = []
        self.aed_instytucji: dict[int, str] = {}

    def utworz_zbior(self, instytucja_id, *, tytul, opis, licencja="CC BY 4.0", czestotliwosc="irregular",
                     slowa_kluczowe=None, status="opublikowany", zrodlo="panel", ext_ident=None):
        z = self.zbiory.setdefault(ext_ident, {"id": len(self.zbiory) + 1})
        z.update(instytucja_id=instytucja_id, tytul=tytul, opis=opis, licencja=licencja,
                 czestotliwosc=czestotliwosc, slowa_kluczowe=slowa_kluczowe, status=status, zrodlo=zrodlo)
        return z

    def dodaj_lub_zaktualizuj_zasob(self, zbior_id, *, tytul, opis="", plik=None, nazwa_pliku=None, url=None,
                                    wykaz_typ=None, status="opublikowany", data_danych=None, zasob_id=None,
                                    ext_ident=None):
        self.wywolania.append(dict(zbior_id=zbior_id, tytul=tytul, plik=plik, nazwa_pliku=nazwa_pliku, url=url,
                                   wykaz_typ=wykaz_typ, status=status, data_danych=data_danych, ext_ident=ext_ident))
        walidacja = "NIE_DOTYCZY"
        if wykaz_typ == "AED":
            if b"id_aed" not in (plik or b"").split(b"\n", 1)[0]:
                raise BladWykazu(422, "Plik zasobu wykazu AED nie zawiera kolumn wzorca.")
            inst = next(z["instytucja_id"] for z in self.zbiory.values() if z["id"] == zbior_id)
            if self.aed_instytucji.get(inst, ext_ident) != ext_ident:
                raise BladWykazu(409, "Dostawca ma już w portalu zasób wykazu AED – zaktualizuj istniejący zasób.")
            self.aed_instytucji[inst] = ext_ident
            walidacja = "BLEDY" if b",x," in plik else "OK"
        zs = self.zasoby.setdefault(ext_ident, {"id": len(self.zasoby) + 100})
        zs.update(zbior_id=zbior_id, wykaz_typ=wykaz_typ, walidacja_status=walidacja)
        return {"zasob": zs, "walidacja": {}, "wykaz": {"przebudowano": wykaz_typ == "AED", "komunikat": ""}}


@pytest.fixture
def repo(monkeypatch):
    r = RepoFake()
    monkeypatch.setattr(repo_portal, "utworz_zbior", r.utworz_zbior)
    monkeypatch.setattr(repo_portal, "dodaj_lub_zaktualizuj_zasob", r.dodaj_lub_zaktualizuj_zasob)
    return r


class Pobieracz:
    def __init__(self, pliki: dict[str, bytes] | None = None):
        self.pliki, self.adresy = pliki or {}, []

    def __call__(self, url):
        self.adresy.append(url)
        if url in self.pliki:
            return self.pliki[url], Path(url).name
        raise harvester.BladPobierania("HTTP 404")


# ---------------------------------------------------------------------------------------------- jednostkowe

def test_import_114_tworzy_zbior_i_zasoby_z_flaga_aed(repo):
    w = harvester.importuj_xml(PRZYKLAD_114, 7)   # domyślny pobieracz: host demo -> plik lokalny (offline)
    assert w["wersja"] == "1.14" and w["bledy"] == [], w
    assert (w["zbiory_utworzone"], w["zasoby_utworzone"]) == (1, 2)
    z = repo.zbiory["waw-defibrylatory-aed"]
    assert z["instytucja_id"] == 7 and z["zrodlo"] == "harvester" and z["licencja"] == "CC BY 4.0"
    assert z["czestotliwosc"] == "monthly" and z["slowa_kluczowe"] == ["AED", "defibrylator", "#TuBijeAED"]
    aed, zwykly = repo.wywolania
    assert aed["wykaz_typ"] == "AED" and aed["plik"] == DEMO_CSV and aed["nazwa_pliku"] == "warszawa_aed_demo.csv"
    assert aed["ext_ident"] == "waw-aed-csv" and aed["data_danych"] == "2026-11-20" and aed["status"] == "opublikowany"
    assert zwykly["wykaz_typ"] is None and zwykly["plik"] is None              # availability=remote -> tylko link
    assert zwykly["url"] == "https://demo.tubijeaed.example/zasady_aed.txt"
    assert [z["wykaz_typ"] for z in w["zasoby"]] == ["AED", None]
    assert w["zasoby"][0]["walidacja_status"] == "OK"


def test_ponowny_import_aktualizuje_po_ext_ident(repo):
    harvester.importuj_xml(PRZYKLAD_114, 7)
    w = harvester.importuj_xml(PRZYKLAD_114, 7)
    assert w["bledy"] == [] and len(repo.zbiory) == 1 and len(repo.zasoby) == 2


def test_import_113_bez_wykazu_z_ostrzezeniami(repo):
    pob = Pobieracz()
    w = harvester.importuj_xml(PRZYKLAD_113, 3, pobieracz=pob)
    assert w["wersja"] == "1.13" and w["zbiory_utworzone"] == 1 and w["zasoby_utworzone"] >= 1
    assert all(c["wykaz_typ"] is None for c in repo.wywolania)
    assert any("1.13" in o for o in w["ostrzezenia"])
    assert any("containsProtectedData" in o for o in w["ostrzezenia"])


def _plik_z_zasobami(*zasoby: tuple[str, str, str | None]) -> bytes:
    rs = "".join(
        f"<resource><extIdent>{e}</extIdent><url>{u}</url><title><polish>{e}</polish></title>"
        f"<description><polish>o</polish></description><availability>local</availability>"
        + (f"<aggregatedListType>{a}</aggregatedListType>" if a else "") + "</resource>"
        for e, u, a in zasoby)
    return f"""<ns2:datasets xmlns:ns2="{harvester.NS_114}"><dataset><extIdent>z</extIdent>
<title><polish>Zbiór</polish></title><description><polish>o</polish></description>
<updateFrequency>daily</updateFrequency><categories><category>HEAL</category></categories>
<resources>{rs}</resources><tags><tag lang="pl">AED</tag></tags></dataset></ns2:datasets>""".encode()


def test_wiecej_niz_jeden_zasob_aed_w_pliku_jak_dga(repo):
    pob = Pobieracz({"https://x.example/a.csv": DEMO_CSV, "https://x.example/b.csv": DEMO_CSV,
                     "https://x.example/c.csv": b"a,b\n1,2\n"})
    w = harvester.importuj_xml(_plik_z_zasobami(("a", "https://x.example/a.csv", "AED"),
                                                ("b", "https://x.example/b.csv", "AED"),
                                                ("c", "https://x.example/c.csv", None)), 1, pobieracz=pob)
    assert {b["zasob"] for b in w["bledy"]} == {"a", "b"}
    assert all(b["kod"] == "wiele_zasobow_aed" and "więcej niż 1" in b["komunikat"] for b in w["bledy"])
    assert w["zasoby_utworzone"] == 1 and repo.wywolania[0]["ext_ident"] == "c"


def test_bledy_per_zasob_nie_przerywaja_importu(repo):
    pob = Pobieracz({"https://x.example/zle_kolumny.csv": b"kol1,kol2\n1,2\n",
                     "https://x.example/dane.json": b"[]",
                     "https://x.example/inne.csv": b"a\n1\n"})
    w = harvester.importuj_xml(_plik_z_zasobami(
        ("nie-ma", "https://x.example/brak.csv", None),          # zwykły zasób: brak pliku -> zapis jako link
        ("zly-format", "https://x.example/dane.json", None),
        ("inne", "https://x.example/inne.csv", None)), 1, pobieracz=pob)
    assert w["bledy"] == [] and w["zasoby_utworzone"] == 3
    assert any("nie-ma" in o and "link" in o for o in w["ostrzezenia"])

    for ext, url, kod in (("aed-404", "https://x.example/brak.csv", "url_niedostepny"),
                          ("aed-json", "https://x.example/dane.json", "format"),
                          ("aed-422", "https://x.example/zle_kolumny.csv", "wykaz_422")):
        r = RepoFake()
        for nazwa in ("utworz_zbior", "dodaj_lub_zaktualizuj_zasob"):
            setattr(repo_portal, nazwa, getattr(r, nazwa))
        w = harvester.importuj_xml(_plik_z_zasobami((ext, url, "AED"), ("inne", "https://x.example/inne.csv", None)),
                                   1, pobieracz=pob)
        assert [(b["zasob"], b["kod"], b["poziom"]) for b in w["bledy"]] == [(ext, kod, "zasob")], w
        assert w["zasoby_utworzone"] == 1 and w["zbiory_utworzone"] == 1


def test_blad_wykazu_409_trafia_do_bledow(repo):
    repo.aed_instytucji[1] = "inny-zasob"
    pob = Pobieracz({"https://x.example/a.csv": DEMO_CSV})
    w = harvester.importuj_xml(_plik_z_zasobami(("a", "https://x.example/a.csv", "AED")), 1, pobieracz=pob)
    assert w["bledy"][0]["kod"] == "wykaz_409" and "zaktualizuj" in w["bledy"][0]["komunikat"]


def test_zasob_aed_z_bledami_wierszy_ostrzezenie(repo):
    pob = Pobieracz({"https://x.example/a.csv": DEMO_CSV + b"Z,x,x\n"})
    w = harvester.importuj_xml(_plik_z_zasobami(("a", "https://x.example/a.csv", "AED")), 1, pobieracz=pob)
    assert w["bledy"] == [] and w["zasoby"][0]["walidacja_status"] == "BLEDY"
    assert any("nie wejdzie do wykazu" in o for o in w["ostrzezenia"])


def test_blad_zapisu_zbioru_nie_przerywa(repo, monkeypatch):
    def zly(*a, **k):
        raise RuntimeError("baza zablokowana")
    monkeypatch.setattr(repo_portal, "utworz_zbior", zly)
    w = harvester.importuj_xml(PRZYKLAD_114, 1)
    assert w["zbiory_utworzone"] == 0 and w["bledy"][0]["poziom"] == "zbior"


@pytest.mark.parametrize("tresc,kod", [(b"nie xml", "skladnia"), (b"", "pusty"),
                                       (PRZYKLAD_114.replace(b"<category>HEAL", b"<category>XXXX"), "xsd")])
def test_bledny_plik_zwraca_blad_poziomu_pliku(repo, tresc, kod):
    w = harvester.importuj_xml(tresc, 1)
    assert (w["zbiory_utworzone"], w["zasoby_utworzone"]) == (0, 0)
    assert w["bledy"][0]["poziom"] == "plik" and w["bledy"][0]["kod"] == kod and not repo.wywolania


def test_pakiet_dostawcy_z_generatora_importuje_sie(repo):
    xml = harvester_xml.zbuduj_xml_dostawcy(nazwa_dostawcy="Gmina Demo",
                                            url_zasobu="https://demo.tubijeaed.example/warszawa_aed_demo.csv")
    w = harvester.importuj_xml(xml, 5)
    assert w["bledy"] == [] and w["zasoby"][0]["wykaz_typ"] == "AED"


# ---------------------------------------------------------------------------------------------- pobieranie

def test_pobierz_plik_demo_offline():
    dane, nazwa = harvester.pobierz_plik("https://demo.tubijeaed.example/warszawa_aed_demo.csv")
    assert dane == DEMO_CSV and nazwa == "warszawa_aed_demo.csv"
    for zly in ("https://demo.tubijeaed.example/../__init__.py", "https://demo.tubijeaed.example/brak.csv"):
        with pytest.raises(harvester.BladPobierania):
            harvester.pobierz_plik(zly)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x.example/a.csv", "gopher://x", "",
                                 "http://127.0.0.1:8080/api", "http://localhost/a.csv", "http://10.0.0.1/a.csv",
                                 "http://[::1]/a.csv", "http://169.254.169.254/latest/meta-data"])
def test_pobierz_plik_odrzuca_niedozwolone_adresy(url, monkeypatch):
    monkeypatch.delenv("HARVESTER_ZEZWOL_LOKALNE", raising=False)
    with pytest.raises(harvester.BladPobierania):
        harvester.pobierz_plik(url)


def test_pobierz_plik_limit_rozmiaru_i_nazwa(monkeypatch):
    import requests

    class Odp:
        def __init__(self, dane, status=200, headers=None):
            self.status_code, self.headers = status, headers or {}
            self.is_redirect = status in (301, 302)
            self.raw = type("R", (), {"read": lambda s, n, decode_content=True: dane[:n]})()

    odpowiedzi = {"https://a.example/plik": Odp(b"", 302, {"location": "/pobierz?id=1"}),
                  "https://a.example/pobierz?id=1": Odp(b"x,y\n", 200, {"content-type": "text/csv; charset=utf-8"}),
                  "https://a.example/duzy.csv": Odp(b"x" * (harvester.MAKS_ROZMIAR_PLIKU + 10))}
    monkeypatch.setattr(requests.Session, "get", lambda self, url, **k: odpowiedzi[url])
    monkeypatch.setattr(harvester, "_sprawdz_host", lambda host: None)
    assert harvester.pobierz_plik("https://a.example/plik") == (b"x,y\n", "pobierz.csv")
    with pytest.raises(harvester.BladPobierania, match="większy"):
        harvester.pobierz_plik("https://a.example/duzy.csv")


# ---------------------------------------------------------------------------------------------- integracyjne

def backend_gotowy() -> bool:
    """Backend gotowy = istnieje seed portalu (app/portal/seed_portal.py) i repo_portal nie rzuca NotImplementedError."""
    import importlib.util

    if importlib.util.find_spec("app.portal.seed_portal") is None:
        return False
    try:
        repo_portal.lista_instytucji()
    except NotImplementedError:
        return False
    except Exception:  # noqa: BLE001 – np. brak tabel przed seedem
        pass
    return True


def instytucja_demo(fragment: str) -> dict:
    """Instytucja z seeda (po uruchomieniu lifespan) – pomija test, jeśli seed jej nie tworzy."""
    inst = next((i for i in repo_portal.lista_instytucji() if fragment in (i.get("nazwa") or "")), None)
    if inst is None:
        pytest.skip(f"seed portalu nie zawiera instytucji „{fragment}”")
    return inst


@pytest.mark.skipif(not backend_gotowy(), reason="app/portal jeszcze niezaimplementowany (Backend)")
def test_integracja_import_114_z_prawdziwym_repo():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.portal import wykazy

    with TestClient(app):                         # lifespan: init bazy + seed portalu
        inst = instytucja_demo("Warszaw")
        w = harvester.importuj_xml(PRZYKLAD_114, inst["id"])
        assert w["bledy"] == [], w
        assert w["zbiory_utworzone"] == 1 and w["zasoby_utworzone"] == 2
        aed = next(z for z in w["zasoby"] if z["wykaz_typ"] == "AED")
        assert aed["walidacja_status"] == "OK"
        zs = repo_portal.pobierz_zasob(aed["id"])
        assert zs["wykaz_typ"] == "AED" and zs["status"] == "opublikowany"
        assert any(u.get("zasob_id") == aed["id"] for u in (wykazy.aktualny_wykaz("AED") or {}).get("uwzglednione", []))
        # drugi import tego samego pliku = aktualizacja, nie 409
        assert harvester.importuj_xml(PRZYKLAD_114, inst["id"])["bledy"] == []
