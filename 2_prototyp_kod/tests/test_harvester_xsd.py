"""XSD 1.14 (aggregatedListType) i zgodność wsteczna z 1.13 – bez sieci."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
from lxml import etree

from app import harvester
from app.exports import harvester_xml

FIX = Path(__file__).parent / "fixtures"
PRZYKLAD_114 = FIX / "harvester" / "import_aed_1_14.xml"
PRZYKLAD_113 = FIX / "harvester_example_1_13.xml"


def _xml(aggregated: str | None, ns: str = harvester.NS_114) -> bytes:
    el = f"<aggregatedListType>{aggregated}</aggregatedListType>" if aggregated is not None else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ns2:datasets xmlns:ns2="{ns}"><dataset><extIdent>z1</extIdent><title><polish>Z</polish></title>
<description><polish>Opis</polish></description><updateFrequency>monthly</updateFrequency>
<categories><category>HEAL</category></categories>
<resources><resource><extIdent>r1</extIdent><url>https://demo.tubijeaed.example/a.csv</url>
<title><polish>R</polish></title><description><polish>Opis</polish></description>{el}</resource></resources>
<tags><tag lang="pl">AED</tag></tags></dataset></ns2:datasets>""".encode()


def test_przyklad_114_waliduje_sie_lxml():
    wersja, _ = harvester.wczytaj_i_waliduj(PRZYKLAD_114.read_bytes())
    assert wersja == "1.14"


@pytest.mark.skipif(shutil.which("xmllint") is None, reason="brak xmllint")
def test_przyklad_114_waliduje_sie_xmllint():
    w = subprocess.run(["xmllint", "--noout", "--schema", str(harvester.PLIKI_XSD["1.14"]), str(PRZYKLAD_114)],
                       capture_output=True, text=True)
    assert w.returncode == 0 and "validates" in w.stderr


def test_plik_113_nadal_przyjmowany():
    wersja, korzen = harvester.wczytaj_i_waliduj(PRZYKLAD_113.read_bytes())
    assert wersja == "1.13"
    assert all(r.wykaz_typ is None for z in harvester.parsuj(korzen) for r in z.zasoby)


def test_kazdy_plik_113_po_zmianie_ns_jest_poprawnym_114():
    tresc = PRZYKLAD_113.read_bytes().replace(harvester.NS_113.encode(), harvester.NS_114.encode())
    assert harvester.wczytaj_i_waliduj(tresc)[0] == "1.14"


@pytest.mark.parametrize("wartosc", ["DGA", "aed", "", "AED AED"])
def test_zly_enum_odrzucony(wartosc):
    with pytest.raises(harvester.BladPliku) as e:
        harvester.wczytaj_i_waliduj(_xml(wartosc))
    assert e.value.kod == "xsd" and any("aggregatedListType" in s for s in e.value.szczegoly)


def test_aed_poprawny_i_opcjonalny():
    assert harvester.wczytaj_i_waliduj(_xml("AED"))[0] == "1.14"
    assert harvester.wczytaj_i_waliduj(_xml(None))[0] == "1.14"


def test_aggregated_list_type_niedozwolony_w_113():
    with pytest.raises(harvester.BladPliku) as e:
        harvester.wczytaj_i_waliduj(_xml("AED", ns=harvester.NS_113))
    assert e.value.kod == "xsd"


def test_kopia_xsd_113_identyczna_z_oficjalna():
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    assert sha(harvester.PLIKI_XSD["1.13"]) == sha(FIX / "xml_import_otwarte_dane_1_13.xsd")


def test_xsd_114_rozni_sie_tylko_ns_i_jednym_elementem():
    """Jedyna zmiana merytoryczna: aggregatedListType w resourceType (obok containsProtectedData)."""
    xs = "{http://www.w3.org/2001/XMLSchema}"
    s113 = etree.parse(str(harvester.PLIKI_XSD["1.13"])).getroot()
    s114 = etree.parse(str(harvester.PLIKI_XSD["1.14"])).getroot()
    assert s114.get("targetNamespace") == harvester.NS_114
    nowe = s114.findall(f".//{xs}element[@name='aggregatedListType']")
    assert len(nowe) == 1
    el = nowe[0]
    assert el.getparent().getparent().get("name") == "resourceType" and el.get("minOccurs") == "0"
    assert el.getprevious().get("name") == "containsProtectedData"
    assert [e.get("value") for e in el.iter(f"{xs}enumeration")] == ["AED"]
    el.getparent().remove(el)
    s114.set("targetNamespace", harvester.NS_113)
    t113 = etree.tostring(s113, method="c14n")
    t114 = etree.tostring(s114, method="c14n").replace(harvester.NS_114.encode(), harvester.NS_113.encode())
    assert t113 == t114


def test_rozpoznanie_wersji_i_bledy_pliku():
    for tresc, kod in ((b"", "pusty"), (b"<a>", "skladnia"), (b"<datasets xmlns='urn:inne'/>", "wersja"),
                       (b"<x xmlns='urn:otwarte-dane:harvester:1.14'/>", "wersja")):
        with pytest.raises(harvester.BladPliku) as e:
            harvester.wczytaj_i_waliduj(tresc)
        assert e.value.kod == kod


def test_xxe_nie_jest_rozwijane(tmp_path):
    tajny = tmp_path / "tajne.txt"
    tajny.write_text("SEKRET-123")
    tresc = _xml("AED").replace(b'<?xml version="1.0" encoding="UTF-8"?>',
                                f'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file://{tajny}">]>'.encode())
    tresc = tresc.replace(b"<polish>Z</polish>", b"<polish>&x;</polish>")
    with pytest.raises(harvester.BladPliku) as e:
        harvester.wczytaj_i_waliduj(tresc)
    assert e.value.kod == "dtd" and "SEKRET" not in e.value.komunikat


# ---------------------------------------------------------------------------------------------- generator 1.14

def test_generator_dostawcy_114_przechodzi_xsd():
    rek = [{"teryt_gmina": "1465011", "data_aktualizacji": "2026-11-20T10:00:00Z"}]
    xml = harvester_xml.zbuduj_xml_dostawcy(nazwa_dostawcy="Urząd Miasta Łódź – Bałuty", rekordy=rek,
                                            url_zasobu="http://bip.example.pl/aed.csv")
    wersja, korzen = harvester.wczytaj_i_waliduj(xml)
    assert wersja == "1.14"
    zs = harvester.parsuj(korzen)[0].zasoby
    assert len(zs) == 1 and zs[0].wykaz_typ == "AED" and zs[0].url == "https://bip.example.pl/aed.csv"
    assert korzen.find("dataset/resources/resource/regions/terytIdent").text == "1465011"
    assert all(len(e.text) <= 36 for e in korzen.iter("extIdent"))
    assert korzen.find("dataset/extIdent").text == "aed-urzad-miasta-lodz-baluty"


def test_generator_w_wersji_113_bez_elementu_aed():
    xml = harvester_xml.zbuduj_xml_dostawcy(nazwa_dostawcy="Gmina X", url_zasobu="https://x.example/a.csv",
                                            wersja="1.13")
    wersja, korzen = harvester.wczytaj_i_waliduj(xml)
    assert wersja == "1.13" and b"aggregatedListType" not in xml


def test_generator_dluga_nazwa_miesci_sie_w_limitach():
    xml = harvester_xml.zbuduj_xml_dostawcy(nazwa_dostawcy="Bardzo długa nazwa " * 40,
                                            url_zasobu="https://x.example/a.csv")
    assert harvester.wczytaj_i_waliduj(xml)[0] == "1.14"
