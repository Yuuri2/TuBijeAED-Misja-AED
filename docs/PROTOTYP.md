# Klikalny prototyp „dane.gov.pl + Wykaz zbiorczy AED” – kontrakt Sprintu 2

**Cel:** bardzo okrojony, klikalny prototyp portalu dane.gov.pl pokazujący WYŁĄCZNIE mechanikę, o którą prosi zadanie i mentorzy:
dostawcy publikują zasoby AED na swoich kontach → portal waliduje je wg wzorca → portal scala je w **Wykaz defibrylatorów AED – wykaz zbiorczy** → wykaz jest dostępny (pliki, API, mapa #TuBijeAED).
To NIE jest pełny portal: brak wyszukiwarki pełnotekstowej, CMS, forum, kont użytkowników, RDF itd.

Logika ma **wiernie odwzorowywać** mechanizm istniejący w kodzie portalu – „Wykaz chronionych danych (DGA) – wykaz zbiorczy”:
| mcod (oryginał) | prototyp |
|---|---|
| `Organization.institution_type` (`local`, `state`, `private`, `other`, `developer`) | `instytucje.typ` – te same wartości |
| `Resource.contains_protected_data` (bool) | `zasoby.wykaz_typ` (`NULL` lub `"AED"`) – uogólnienie na wiele wykazów |
| `DGA_COLUMNS` / `validate_dga_df_columns` | `WYKAZY["AED"].kolumny` = `fields` z `aed_schema.json` + walidacja wierszy (`app/validation.py`) |
| `MAIN_DGA_COLUMNS` (+ „Nazwa dysponenta zasobu”) | `WYKAZY["AED"].kolumny_wynikowe` = kolumny dostawcy + pola wzorca |
| jeden zasób DGA na instytucję (`get_dga_resource_for_institution`) | jeden opublikowany zasób z `wykaz_typ="AED"` na instytucję |
| tylko zasoby `published` + `data_tasks_last_status == SUCCESS` | tylko zasoby `opublikowany` + `walidacja_status == "OK"` |
| Celery `create_main_dga_resource_task` (4 kroki, cleanup przy błędzie) | `utworz_wykaz_zbiorczy("AED")` – te same 4 kroki; uruchamiany automatycznie po zmianie zasobu AED + przycisk w panelu admina |
| zbiór właściciela `MAIN_DGA_DATASET_OWNER_ORGANIZATION_PK` (MC) | zbiór instytucji „Ministerstwo Cyfryzacji” (seed) |
| `AggregatedDGAInfo` (singleton) | tabela `wykazy_info` (jedna aktualna pozycja na typ + historia uruchomień) |
| endpoint `/dga-aggregated` | `/api/1.4/aed-aggregated` |
| harvester XML 1.13 `containsProtectedData` | harvester XML **1.14** – element `aggregatedListType` (enum: `AED`) w `resource` |

Każdy moduł prototypu w docstringu wskazuje odpowiadający plik/funkcję mcod.

## Rozróżnienie pojęć (ważne merytorycznie)
- **Dostawca** – instytucja z kontem w portalu, publikuje zasób i **odpowiada za dane** (np. Urząd Miasta Krosna).
- **Dysponent** – właściciel urządzenia AED (kolumny `nazwa_dysponenta`, `identyfikator_dysponenta` we wzorcu); może być inny niż dostawca (gmina publikuje AED szkoły, apteki).

## Moduły i właściciele (katalog `2_prototyp_kod/`)
| Ścieżka | Właściciel |
|---|---|
| `app/portal/__init__.py`, `app/portal/baza.py` (tabele portalu), `app/portal/repo_portal.py` (CRUD), `app/portal/wykazy.py` (konfiguracja wykazów, walidacja zasobu, scalanie), `app/portal/partnerzy.py`, `app/portal/seed_portal.py` | Backend |
| `app/routers/portal_admin.py` (panel dostawcy i admina MC), `app/routers/partnerzy.py` | Backend |
| `app/harvester/` (import XML 1.14), `app/harvester/xsd/xml_import_otwarte_dane_1_14.xsd` | API |
| `app/routers/api_14.py` (publiczne API w stylu api.dane.gov.pl), `app/routers/mapa.py` (mapa, najbliższe AED, warstwa OSM), `app/routers/asystent.py` (asystent dostawcy) | API |
| istniejące `app/sources/*`, `app/exports/*` | API |
| istniejące `app/validation.py`, `app/schema.py`, `app/config.py`, `app/db.py`, `app/main.py`, `app/dedup.py` | Backend |
| `static/**` oprócz `static/brand/` | Frontend |
| `static/brand/` (tokens.css, logo, favicon, odznaki), `3_branding/` | UI/UX |

Stare endpointy `/api/v1/aed`, `/api/v1/dysponent/*`, `/api/v1/zrodla/*`, `/api/v1/export/*` z Sprintu 1 – właściciele mogą je usunąć lub przenieść do nowych routerów; nic z frontendu ich nie używa po Sprincie 2. Tabela `rekordy` przestaje być źródłem prawdy (źródłem prawdy jest wykaz zbiorczy).

## Model danych (SQLite, `DB_PATH`)
- `instytucje(id INTEGER PK, nazwa, regon, typ, email, www, utworzono)`
- `zbiory(id INTEGER PK, instytucja_id, tytul, opis, kategoria DEFAULT 'HEAL', licencja, czestotliwosc, slowa_kluczowe JSON, status 'opublikowany'|'szkic', zrodlo 'panel'|'harvester'|'system', utworzono, zmodyfikowano)`
- `zasoby(id INTEGER PK, zbior_id, tytul, opis, format, plik_sciezka NULL, url NULL, wykaz_typ NULL|'AED', status 'opublikowany'|'szkic', walidacja_status 'OK'|'BLEDY'|'BRAK'|'NIE_DOTYCZY', walidacja_raport JSON, liczba_wierszy, data_danych, utworzono, zmodyfikowano)`
- `wykazy_info(id INTEGER PK, typ, zbior_id, zasob_id, utworzono, liczba_rekordow, liczba_dostawcow, uwzglednione JSON, pominiete JSON, status 'OK'|'BLAD', komunikat)`
- `osm_warstwa(...)` – punkty OSM „do weryfikacji” (właściciel: API; może zostać tabela `rekordy` z Sprintu 1 filtrowana po `zrodlo_typ='OSM'`).
Pliki wgrane i wygenerowane: `data/media/` (w `.gitignore`).

## Kolumny wykazu zbiorczego (kolejność)
`nazwa_dostawcy, regon_dostawcy, typ_dostawcy, id_zasobu_zrodlowego, url_zasobu_zrodlowego, data_aktualizacji_zasobu,` + wszystkie `fields` z `aed_schema.json` w kolejności ze schematu.
Formaty wyniku: **XLSX** (jak DGA), **CSV UTF-8**, **GeoJSON**. Duplikaty między dostawcami (<25 m, `app/dedup.py`) NIE są usuwane – tylko raportowane w `wykazy_info.pominiete`/raporcie jakości (dostawca odpowiada za swoje dane).

## Uwierzytelnianie (demo)
Brak haseł. Nagłówek `X-Demo-Konto: <instytucja_id>` albo `X-Demo-Konto: admin` (administrator portalu / MC). Frontend trzyma wybór w `sessionStorage` („Zaloguj jako…”). Brak nagłówka na endpointach admina → 401 `{"error": "..."}`.

## REST – panel (Backend), prefiks `/api/admin`
| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/konta` | lista kont demo: `[{"id": 3, "nazwa": "Urząd Miasta Krosna", "typ": "local"}, ..., {"id": "admin", "nazwa": "Administrator portalu (MC)"}]` (bez nagłówka) |
| GET | `/moje-zbiory` | zbiory zalogowanej instytucji z zasobami |
| POST | `/zbiory` | JSON `{tytul, opis, licencja, czestotliwosc, slowa_kluczowe}` → zbiór |
| POST | `/zbiory/{id}/zasoby` | multipart: `plik` (xlsx/csv) LUB `url`, `tytul`, `opis`, `wykaz_typ` (`""`/`AED`), `status` → `{zasob, walidacja: <raport>, wykaz: {przebudowano: bool, komunikat}}`; dla `wykaz_typ=AED`: 422 jeśli brak kolumn wzorca; zasób z błędami wierszy zapisuje się z `walidacja_status=BLEDY` i NIE wchodzi do wykazu; 409 jeśli instytucja ma już inny opublikowany zasób AED (komunikat jak w DGA + podpowiedź „zaktualizuj istniejący zasób”) |
| PUT | `/zasoby/{id}` | multipart jak wyżej (podmiana pliku / zmiana flagi / status) |
| DELETE | `/zasoby/{id}` | usunięcie → przebudowa wykazu |
| POST | `/harvester/xml` | multipart `plik` (XML 1.13/1.14) → `{zbiory_utworzone, zasoby_utworzone, bledy: [...]}`. Route w `portal_admin.py` (Backend) woła `app.harvester.importuj_xml(tresc: bytes, instytucja_id: int) -> dict` (API), który zapisuje przez `repo_portal` |
| POST | `/wykazy/AED/przebuduj` | tylko `admin` → `wykazy_info` |
| GET | `/wykazy/AED/historia` | tylko `admin` → lista uruchomień |

Raport walidacji:
```json
{
  "poprawne_wiersze": 12, "bledne_wiersze": 1,
  "bledy":   [{"wiersz": 5, "pole": "kod_pocztowy", "kod": "pattern", "komunikat": "Kod pocztowy musi mieć format 00-000."}],
  "ostrzezenia": [{"wiersz": 3, "pole": "teryt_gmina", "kod": "zalecane", "komunikat": "Brak kodu TERYT – zalecane uzupełnienie."}]
}
```
`wiersz` = numer wiersza w arkuszu (nagłówek = 1). Kody: `required`, `enum`, `pattern`, `range`, `type`, `warunek`, `suma_kontrolna`, `zalecane`, `duplikat`.

## REST – publiczne (API), prefiks `/api/1.4` (kształt JSON:API jak api.dane.gov.pl: `{data, links, meta}`)
| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/datasets?q=&instytucja=&wykaz=AED&page=1&per_page=20` | lista zbiorów; `data[].attributes`: `title, notes, institution{id,title,type}, categories, license, modified, resources_count, is_aggregated_list` |
| GET | `/datasets/{id}` | zbiór + `relationships.resources` |
| GET | `/datasets/{id}/resources` | zasoby: `title, format, download_url, aggregated_list_type, validation_status, modified` |
| GET | `/resources/{id}` / `/resources/{id}/file` | metadane / pobranie pliku |
| GET | `/institutions` / `/institutions/{id}` | instytucje (+ `partner: {status, wazny_do}`) |
| GET | `/aed-aggregated` | `{data: {zbior_id, zasob_id, utworzono, liczba_rekordow, liczba_dostawcow, pliki: {xlsx, csv, geojson}, uwzglednione: [{instytucja, zasob_id, rekordy}], pominiete: [{instytucja, zasob_id, powod}]}}`; 404 gdy brak wykazu (jak DGA) |
| GET | `/aed-aggregated/rekordy?wojewodztwo=&dostawca=&bbox=` | rekordy wykazu jako JSON (`items`) – źródło dla mapy i tabeli |

## REST – mapa i asystent (API)
| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/api/mapa/aed` | GeoJSON z wykazu (+ `properties.partner: bool`) |
| GET | `/api/mapa/najblizsze?lat=&lon=&limit=3` | najbliższe AED z wykazu: `odleglosc_m`, `dostepny_teraz` (true/false/null z `godziny_dostepnosci` OSM opening_hours – wystarczy podzbiór składni: `24/7`, `Mo-Fr 08:00-16:00`, `Sa`, `Su`, `;`), nie ukrywać `status_urzadzenia` = null/„nieznany” (oznaczyć), ukryć `wycofane` |
| GET | `/api/mapa/osm?bbox=` / POST `/api/mapa/osm/pobierz` (form `miasto`) | warstwa OSM „do weryfikacji” (ODbL, nigdy w wykazie) |
| GET | `/api/asystent/wzorzec.xlsx`, `/api/asystent/wzorzec.csv`, `/api/asystent/schemat.json` | pliki wzorca |
| POST | `/api/asystent/sprawdz` | multipart `plik` → raport walidacji (bez zapisu) |
| POST | `/api/asystent/konwertuj` | multipart `plik` + `profil` (`krosno`, `przemysl`, `marki`, `legionowo`, `warszawa`, `auto`) → plik CSV we wzorcu + raport (migracja istniejących zasobów gmin) |
| POST | `/api/asystent/pakiet` | multipart `plik` + dane dostawcy → ZIP: `dane_aed.csv` + `harvester_1_14.xml` (z `aggregatedListType=AED`) + `INSTRUKCJA.txt` |

## Partner #TuBijeAED (Backend), prefiks `/api/partnerzy`
| GET | `/` | lista partnerów |
| GET | `/{instytucja_id}` | `{status: 'AKTYWNY'|'WYGASŁY'|'BRAK', kryteria: [{nazwa, spelnione, opis}], wazny_do}` |
| GET | `/{instytucja_id}/odznaka.svg?wariant=jasna|ciemna&rozmiar=mala|pelna` | odznaka (SVG koncepcji C) z datą ważności; wygasła = szara z napisem „wygasła” |
Kryteria: opublikowany zasób AED uwzględniony w aktualnym wykazie; 0 błędów walidacji; zasób zaktualizowany ≤ 12 mies.; średnia kompletność rekordów ≥ 0,8. Odznaka linkuje do `/partner.html?id=<instytucja_id>`.

## Strony (Frontend, `static/`, czysty HTML + CSS + JS, bez frameworków build-time)
Wspólny nagłówek: znak #TuBijeAED (koncepcja C) + wyraźny pasek **„Prototyp – modyfikacja portalu dane.gov.pl (HackNation 2026). Nie jest to oficjalny serwis.”** Nie kopiujemy logo/godła dane.gov.pl ani MC.
1. `index.html` – start: czym jest wykaz, 3 kafle (Wykaz AED, Mapa #TuBijeAED, Panel dostawcy), link „Ścieżka dla jury”.
2. `zbiory.html` – lista zbiorów z filtrem (instytucja, tylko wykazy) + wyszukiwanie po tytule.
3. `zbior.html?id=` – zbiór: metadane, zasoby (format, status walidacji, oznaczenie „Zasób wykazu AED”), pobieranie.
4. `wykaz-aed.html` – wykaz zbiorczy: data scalenia, liczby, pobierz XLSX/CSV/GeoJSON, link do API, tabela z filtrem (województwo, dostawca), lista dostawców uwzględnionych/pominiętych z powodem.
5. `instytucja.html?id=` – instytucja, jej zbiory, status Partnera, kod odznaki do stopki (kopiuj).
6. `partner.html?id=` – publiczna weryfikacja odznaki.
7. `mapa.html` – #TuBijeAED: duży przycisk **„Znajdź najbliższy AED”** (geolokalizacja, fallback: wpisz miasto/kliknij na mapie), stały przycisk **„Zadzwoń 112”** (`tel:112`), 3 najbliższe z odległością, dostępnością teraz, instrukcją dostępu i linkiem nawigacji; legenda kształtem + kolorem; przełącznik warstwy OSM „do weryfikacji”; **lista tekstowa jako alternatywa mapy**.
8. `admin/index.html` – panel: „Zaloguj jako…” (konta demo), moje zbiory, dodaj zbiór, dodaj/aktualizuj zasób (checkbox „Zasób wchodzi do Wykazu zbiorczego AED”, link do wzorca, raport walidacji per wiersz z numerem wiersza i polem), import XML harvestera; dla `admin`: przebudowa wykazu i historia uruchomień.
9. `asystent.html` – asystent dostawcy: pobierz wzorzec, sprawdź plik, konwertuj plik gminy, pobierz pakiet do publikacji.
10. `jury.html` – ścieżka jurora w ponumerowanych krokach (linki do powyższych stron) – szkic, treść finalna w Sprincie 3.

Wymagania: **WCAG 2.1 AA** (skip link, landmarki, nagłówki, etykiety, focus, kontrast z `tokens.css`, `aria-live` dla wyników, brak informacji przekazywanej tylko kolorem, obsługa klawiaturą, `prefers-reduced-motion`), responsywność 320 px – desktop, polski język (`lang="pl"`), escapowanie danych (`textContent`). Leaflet 1.9.4 z unpkg dozwolony; Tailwind CDN – nie.

## Tokeny (UI/UX, `static/brand/tokens.css`) – nazwy stałe, wartości UI/UX może dopracować
`--kolor-glowny, --kolor-glowny-ciemny, --kolor-tekst, --kolor-tekst-drugorzedny, --kolor-tlo, --kolor-tlo-jasne, --kolor-akcent-na-ciemnym, --kolor-alarm, --kolor-ostrzezenie, --kolor-obramowanie, --kolor-fokus, --czcionka, --promien, --cien`.
Pliki: `static/brand/logo.svg`, `logo-negatyw.svg`, `sygnet.svg`, `favicon.svg`, `odznaka-*.svg`, `fonts/`.

## Dane demo (seed, działa BEZ sieci)
- Instytucje: „Ministerstwo Cyfryzacji” (state, właściciel wykazu), Urząd Miasta Krosna, Urząd Miejski w Przemyślu, Urząd Miasta Marki, Urząd Miasta Legionowo (local, REGON-y z `tests/fixtures/danegov/institution_*.json`), Urząd m.st. Warszawy (local, bez zasobu AED – „jeszcze nie dołączył”), 1–2 firmy demo (private, wyraźnie fikcyjne nazwy, np. „Galeria Przykładowa sp. z o.o.” z NIP/REGON testowym spełniającym sumę kontrolną) – jedna jako Partner, jedna z zasobem z błędami walidacji (pokazuje odrzucenie).
- Zasoby gmin: pliki z `tests/fixtures/danegov/` przekonwertowane do wzorca istniejącym kodem z `app/sources/` (pokazuje migrację), oznaczone `wykaz_typ=AED`.
- Po seedzie automatycznie budowany jest wykaz zbiorczy.

## Kryterium wyjścia Sprintu 2
Jedna komenda `cd 2_prototyp_kod && ../.venv/bin/uvicorn app.main:app --port 8080` → przechodzę w przeglądarce: panel → dodaję zasób AED (poprawny i błędny) → wykaz przebudowuje się → widzę go w `wykaz-aed.html`, API i na mapie; import XML 1.14 działa; `pytest` zielony; XSD 1.14 waliduje przykładowy plik.
