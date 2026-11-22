# Dane demo seeda portalu (app/portal/dane_demo/)

Prawdziwe, przycięte odpowiedzi API dane.gov.pl (`https://api.dane.gov.pl/1.4`) i pliki zasobów gmin.
Źródło: portal dane.gov.pl; data pobrania: 2026-11-22. Seed (`seed_portal.py`) czyta WYŁĄCZNIE ten katalog
(działa bez sieci, niezależnie od `tests/`). Pozostawiono tylko pola używane przez `app/sources/danegov.py`.

| plik danych | zbiór | wydawca | licencja |
|---|---|---|---|
| `krosno_3624.csv` | 3624 | Urząd Miasta Krosna | CC0 1.0 |
| `przemysl_62093.geojson` (3 obiekty) | 4581 | Urząd Miejski w Przemyślu | CC0 1.0 |
| `marki_4955.csv` | 4955 | Urząd Miasta Marki | CC BY 4.0 |
| `legionowo_2625221.csv` | 40593 | Urząd Miasta Legionowo | CC0 1.0 |

Pliki `dataset_*.json`, `resources_*.json`, `institution_*.json` – metadane tych zbiorów oraz instytucji
(w tym m.st. Warszawy, id 7621, CC BY 4.0). Przy ponownym wykorzystaniu zachowaj atrybucję zgodnie z licencją zbioru.
Podmioty „Galeria”, „Spółdzielnia”, „Sklep” są FIKCYJNE i generowane w kodzie seeda.
