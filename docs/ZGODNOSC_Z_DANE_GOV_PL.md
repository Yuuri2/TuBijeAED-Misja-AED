# Zgodność z zasadami działania portalu dane.gov.pl

Rozwiązanie nie buduje „równoległego rejestru” obok portalu. Rozbudowuje **logikę samego portalu** o mechanizm *wykazów zbiorczych*, odtworzony 1:1 z mechanizmu, który portal już stosuje dla **„Wykazu chronionych danych (DGA) – wykaz zbiorczy”**. Kod źródłowy portalu analizowaliśmy na podstawie oficjalnego archiwum `https://dane.gov.pl/source-code/backend_latest.zip` (backend 2.63.0, Django „mcod”, licencja GPL v3).

## Zasady portalu, których przestrzegamy

| Zasada portalu | Jak ją realizujemy |
|---|---|
| Za zbiór odpowiada **dostawca** (instytucja z kontem); nie każdy może publikować | Każdy zasób w wykazie pochodzi z konta konkretnej instytucji; wykaz pokazuje „Dostawca (odpowiada za dane)” przy każdym rekordzie. Dane społecznościowe (OpenStreetMap) **nigdy** nie trafiają do wykazu – są tylko warstwą „do weryfikacji” na mapie. |
| Hierarchia Instytucja → Zbiór → Zasób | Ten sam model w prototypie (`instytucje`, `zbiory`, `zasoby`). |
| Typy instytucji `local`, `state`, `private`, `other`, `developer` | Te same wartości; wykaz AED dopuszcza także podmioty prywatne (`private`) – to firmy są adresatem akcji #TuBijeAED. |
| Licencje otwarte (CC0 1.0, CC BY 4.0 …) | Wykaz publikowany na CC BY 4.0; zasoby źródłowe z licencją zgodną z XSD; ODbL (OSM) wyłączona z wykazu. |
| Format odczytywalny maszynowo | Wykaz: **XLSX** (jak wykaz DGA), **CSV UTF-8**, **GeoJSON** (RFC 7946); API w kształcie JSON:API jak `api.dane.gov.pl/1.4`. |
| Automatyczne zasilanie – harvester XML | Oficjalny schemat **1.13** obsługiwany bez zmian; propozycja **1.14** = 1.13 + jeden opcjonalny element `aggregatedListType` (enum `AED`) obok `containsProtectedData`. Walidacja `xmllint` oficjalnym XSD – OK. Szczegóły: `2_prototyp_kod/app/harvester/ZMIANY_XSD.md`. |
| Kategorie DCAT | Zbiory AED w kategorii `HEAL` (Zdrowie). |

## Mapowanie: mechanizm DGA w mcod → Wykaz zbiorczy AED w prototypie

| mcod (oryginał) | prototyp (`2_prototyp_kod/app/`) |
|---|---|
| `resources/dga_constants.py`: `DGA_COLUMNS`, `MAIN_DGA_COLUMNS`, `ALLOWED_DGA_INSTITUTIONS`, `DGA_RESOURCE_EXTENSIONS`; `settings/base.py`: `MAIN_DGA_*` | `portal/wykazy.py`: `KonfiguracjaWykazu`, `WYKAZY["AED"]` – **uogólnienie**: kolejny wykaz (np. apteki) = nowy wpis konfiguracji |
| `Resource.contains_protected_data` (bool) | `zasoby.wykaz_typ` (`NULL` / `"AED"`) |
| `resources/forms.py` `ResourceForm.clean` (walidacja pliku DGA, typ instytucji, zastąpienie poprzedniego zasobu, `confirm_save`) | `wykazy.waliduj_zasob_wykazu` (422/409, `potwierdz_zastapienie`) |
| `validate_dga_df_columns` / `validate_dga_file_columns` | `wykazy.sprawdz_kolumny` + walidacja wartości każdego wiersza wg `aed_schema.json` (`validation.py`) |
| `get_dga_resource_for_institution` (jeden zasób na instytucję) | `wykazy.zasob_wykazu_instytucji` |
| `validate_institution_type_for_contains_protected_data` | `wykazy.sprawdz_typ_instytucji` |
| `get_all_dga_resources_sorted_by_organizations` (tylko `published` + walidacje `SUCCESS`) | `wykazy._zasoby_zrodlowe` (tylko `opublikowany` + `walidacja_status=OK`) |
| `get_main_dga_source_df` + wyjątki `MainDGA*Error` | `wykazy._wczytaj_zasob_zrodlowy` + `BladZasobuZrodlowego` → lista „pominięte” z powodem |
| `create_main_dga_df`, `add_style_to_main_dga_excel_file`, `create_main_dga_file` | `wykazy._zbuduj_wykaz`, `_styl_xlsx`, `_zapisz_pliki` (XLSX + CSV + GeoJSON) |
| `create_main_dga_dataset`, `create_main_dga_resource_with_dataset` (właściciel: `MAIN_DGA_DATASET_OWNER_ORGANIZATION_PK`) | `wykazy._utworz_zasoby_wykazu` (właściciel: instytucja „Ministerstwo Cyfryzacji”) |
| `check_all_resource_validations_status` | `wykazy._zweryfikuj_wynik` |
| `update_or_create_aggr_dga_info_and_delete_old_main_dga` | `wykazy._zapisz_info_i_usun_poprzedni` |
| `clean_up_after_main_dga_resource_creation` | `wykazy._posprzataj` (błąd nie niszczy poprzedniego wykazu) |
| Celery `tasks/dga.py::create_main_dga_resource_task` (4 kroki) | `wykazy.utworz_wykaz_zbiorczy` (te same 4 kroki; uruchamiany po każdej zmianie zasobu wykazu + ręcznie przez administratora) |
| model `AggregatedDGAInfo` | tabela `wykazy_info` (+ historia uruchomień) |
| widok `AggregatedDGAInfoView`, trasa `/dga-aggregated` | `routers/api_14.py`: `/api/1.4/aed-aggregated` (+ `/rekordy`, `/plik/{xlsx,csv,geojson}`) |
| harvester XML `containsProtectedData`, `get_dga_resources_info_from_xml_harvester_file`, `request_remote_dga` | `harvester/`: `aggregatedListType=AED`, `zasoby_aed_w_pliku`, `pobierz_plik` (timeout, limit, ochrona SSRF) |

## Co jest uproszczone w prototypie (świadomie)
Zamiast Postgres/Elasticsearch/Celery/RabbitMQ – SQLite i przetwarzanie w procesie aplikacji; logowanie demonstracyjne bez haseł („Zaloguj jako…”); brak wyszukiwarki pełnotekstowej, CMS, RDF. Mechanika wykazu (reguły, kroki scalania, walidacje, harvester, API) jest odwzorowana wiernie i opisana funkcja po funkcji powyżej, tak aby wdrożenie w mcod polegało na przeniesieniu logiki do istniejących modułów `resources/*`.
