"""Ochrona przed wstrzykiwaniem formuł w eksportach CSV (B-01)."""
import csv
import io

import pytest

from app.exports.bezpieczne import bezpieczna_komorka
from app.sources import konwersja


@pytest.mark.parametrize("wej,wyj", [
    ('=HYPERLINK("http://evil","x")', '\'=HYPERLINK("http://evil","x")'),
    ("@SUM(1+1)", "'@SUM(1+1)"), ("+cmd|' /C calc'!A0", "'+cmd|' /C calc'!A0"),
    ("-2+3+cmd", "'-2+3+cmd"), ("\tx", "'\tx"), ("\rx", "'\rx"),
    ("-1", "-1"), ("-12.5", "-12.5"), ("+48", "+48"), ("zwykły tekst", "zwykły tekst"), ("", ""),
    (None, ""), (52.1, 52.1), (-1, -1), (float("nan"), ""),
])
def test_bezpieczna_komorka(wej, wyj):
    assert bezpieczna_komorka(wej) == wyj


def test_csv_konwersji_nie_zawiera_formul():
    kol = konwersja.schema.nazwy_pol()
    r = {k: None for k in kol}
    r.update(lokalizacja_szczegolowa='=HYPERLINK("http://evil","x")', instrukcja_dostepu="@SUM(1+1)",
             kondygnacja="-1", szerokosc_geo=52.2)
    wiersz = list(csv.DictReader(io.StringIO(konwersja.do_csv_wzorca([r]))))[0]
    assert wiersz["lokalizacja_szczegolowa"].startswith("'=")
    assert wiersz["instrukcja_dostepu"] == "'@SUM(1+1)"
    assert wiersz["kondygnacja"] == "-1" and wiersz["szerokosc_geo"] == "52.2"
