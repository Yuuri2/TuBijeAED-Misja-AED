# Fixture'y dane.gov.pl (pobrane 2026-11-22, przycięte)

Prawdziwe odpowiedzi `https://api.dane.gov.pl/1.4` (`/search`, `/datasets/{id}`, `/datasets/{id}/resources`,
`/institutions/{id}`) – zostawione tylko pola używane przez `app/sources/danegov.py`.
Pliki danych = pierwsze wiersze zasobów:

| plik | zbiór | wydawca | licencja |
|---|---|---|---|
| `krosno_3624.csv` | 3624 | Urząd Miasta Krosna | CC0 1.0 |
| `przemysl_62093.geojson` (3 obiekty, skrócony opis) | 4581 | Urząd Miejski w Przemyślu | CC0 1.0 |
| `marki_4955.csv`, `marki_4955.xlsx` (całe) | 4955 | Urząd Miasta Marki | CC BY 4.0 |
| `legionowo_2625221.csv` | 40593 | Urząd Miasta Legionowo | CC0 1.0 |
| `warszawa_api_39512.json` | 39512 | Urząd m.st. Warszawy | CC BY 4.0 |

`warszawa_api_39512.json` = przykład odpowiedzi z dokumentacji API m.st. Warszawy
(`https://dane.um.warszawa.pl/files/scb_lokalizacja_defibrylatorow_pw.json`) – samo API wymaga tokena.
