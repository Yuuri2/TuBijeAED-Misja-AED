# Kontrakt API – integrator #TuBijeAED

Baza: `{BASE_URL}/api/v1` (`BASE_URL` z env, domyślnie `http://localhost:8080`). Odpowiedzi JSON w UTF-8.
Rekord AED = pola z `1_wzorzec_danych/aed_schema.json` (`fields`) + pola systemowe (`x-pola-systemowe`).
Kolumna „Sprint” mówi, kiedy endpoint ma działać. **Właściciel** = agent odpowiedzialny.

## Rekordy AED (Backend)
| Metoda | Ścieżka | Opis | Sprint |
|---|---|---|---|
| GET | `/aed` | `{count, items}`; filtry: `wojewodztwo`, `status_weryfikacji`, `zrodlo_typ`, `bbox=minLon,minLat,maxLon,maxLat`, `uwzglednij_duplikaty=false` | 1 |
| GET | `/aed/{uid}` | pojedynczy rekord | 1 |
| GET | `/aed/nearest?lat=&lon=&limit=3` | najbliższe sprawne AED + `odleglosc_m`, `dostepny_teraz` (`true/false/null`) | 2 |
| GET | `/schema` | zawartość `aed_schema.json` | 1 |
| GET | `/statystyki` | liczby wg `status_weryfikacji`, `zrodlo_typ`, `wojewodztwo` | 1 |

## Panel dysponenta (Backend)
| Metoda | Ścieżka | Opis | Sprint |
|---|---|---|---|
| POST | `/dysponent/walidacja` | multipart `file` (.xlsx/.csv). Nic nie zapisuje. Zwraca raport (niżej). | 1 |
| POST | `/dysponent/zgloszenie` | multipart `file`, `nazwa_dysponenta`, `identyfikator_dysponenta`, `typ_dysponenta`. Zapisuje poprawne wiersze jako `ZGLOSZONY_PRZEZ_DYSPONENTA`. Zwraca raport + `zapisano`. | 1 |
| GET | `/dysponent/{identyfikator}/pakiet.zip` | CSV + XML harvester 1.13 do publikacji na własnym koncie w dane.gov.pl (właściciel: API) | 2 |

Raport walidacji:
```json
{
  "poprawne_wiersze": 12, "bledne_wiersze": 1,
  "bledy":   [{"wiersz": 5, "pole": "kod_pocztowy", "kod": "pattern", "komunikat": "Kod pocztowy musi mieć format 00-000."}],
  "ostrzezenia": [{"wiersz": 3, "pole": "teryt_gmina", "kod": "zalecane", "komunikat": "Brak kodu TERYT – zalecane uzupełnienie."}]
}
```
`wiersz` = numer wiersza w arkuszu (nagłówek = 1). Kody: `required`, `enum`, `pattern`, `range`, `type`, `warunek`, `suma_kontrolna`, `zalecane`, `duplikat`.

## Źródła (API)
| Metoda | Ścieżka | Opis | Sprint |
|---|---|---|---|
| GET | `/zrodla` | lista źródeł: `{id, typ, nazwa, url, licencja, liczba_rekordow, ostatnia_synchronizacja}` | 1 |
| POST | `/zrodla/dane-gov-pl/synchronizuj` | pobiera zbiory AED z api.dane.gov.pl, mapuje, zapisuje jako `ZWERYFIKOWANY_DANE_GOV_PL` | 1 |
| POST | `/zrodla/osm/pobierz` | form `miasto`; Overpass → `DO_WERYFIKACJI`, licencja ODbL | 1 |

## Eksporty (API)
| Metoda | Ścieżka | Opis | Sprint |
|---|---|---|---|
| GET | `/export/csv` | CSV UTF-8, kolumny wg kolejności `fields` + `zrodlo_*`, `licencja`, `status_weryfikacji`; bez OSM i duplikatów | 1 |
| GET | `/export/geojson` | GeoJSON RFC 7946, to samo filtrowanie | 1 |
| GET | `/export/harvester.xml` | XML zgodny z `xml_import_otwarte_dane_1_13.xsd` | 1 |
| GET | `/export/osm-odbl.geojson` | wyłącznie rekordy OSM, z atrybucją ODbL | 1 |

## Program Partner #TuBijeAED (Backend)
| Metoda | Ścieżka | Opis | Sprint |
|---|---|---|---|
| GET | `/partnerzy` | instytucje spełniające kryteria | 2 |
| GET | `/partnerzy/{identyfikator}` | status, kryteria, data ważności | 2 |
| GET | `/partnerzy/{identyfikator}/odznaka.svg` | odznaka do stopki (ważna/wygasła) | 2 |

Kryteria Partnera (Sprint 2): ≥1 rekord `ZWERYFIKOWANY_DANE_GOV_PL`, `data_aktualizacji` ≤ 12 mies., średnia `kompletnosc` ≥ 0.8.

## Kompatybilność wsteczna (Sprint 1, do usunięcia w Sprincie 2)
`POST /api/v1/harvest-osm`, `POST /api/v1/upload-institution`, `GET /api/v1/export/harvester-xml` – aliasy, aby stary `static/index.html` działał do czasu nowego frontendu.
