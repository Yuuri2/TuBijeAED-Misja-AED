# Schemat importu XML dane.gov.pl – zmiany 1.13 → 1.14 (#TuBijeAED)

## Pliki
| Plik | Pochodzenie |
|---|---|
| `xsd/xml_import_otwarte_dane_1_13.xsd` | kopia 1:1 oficjalnego schematu z kodu portalu dane.gov.pl (`backend/data/harvester/xml_import_otwarte_dane_1_13.xsd`, https://dane.gov.pl/source-code/backend_latest.zip, GNU GPL v3, © KPRM/MC). SHA-256 `15e2b5be70541097497aae7648e96b3a70466b77060920293710feff7028eb32` – identyczny z `tests/fixtures/xml_import_otwarte_dane_1_13.xsd`. |
| `xsd/xml_import_otwarte_dane_1_14.xsd` | 1.13 + jedna zmiana merytoryczna (niżej). Propozycja zespołu #TuBijeAED, nie jest oficjalnym schematem portalu. |

## Diff (pełny)
```diff
-<xs:schema … targetNamespace="urn:otwarte-dane:harvester:1.13" xmlns="urn:otwarte-dane:harvester:1.13">
+<xs:schema … targetNamespace="urn:otwarte-dane:harvester:1.14" xmlns="urn:otwarte-dane:harvester:1.14">
@@ resourceType (xs:all), zaraz po containsProtectedData
+            <xs:element name="aggregatedListType" maxOccurs="1" minOccurs="0">
+                <xs:annotation><xs:documentation>
+                    Rodzaj wykazu zbiorczego, do którego wchodzi zasób (1.14, #TuBijeAED). …
+                </xs:documentation></xs:annotation>
+                <xs:simpleType><xs:restriction base="xs:string">
+                    <xs:enumeration value="AED"> (Wykaz defibrylatorów AED - wykaz zbiorczy) </xs:enumeration>
+                </xs:restriction></xs:simpleType>
+            </xs:element>
```
Nic więcej się nie zmienia (typy, limity, słowniki, atrybuty `status` – bez zmian).

## Uzasadnienie
* **Wzorzec z portalu.** Wersja 1.13 dodała do zasobu `containsProtectedData` (bool) – flagę, dzięki której
  portal zbiera zasoby instytucji w „Wykaz chronionych danych (DGA) – wykaz zbiorczy”
  (`mcod/harvester/serializers.py` → `validate_contains_protected_data`, `mcod/resources/tasks/dga.py`).
  Wykaz AED działa tak samo, więc potrzebny jest analogiczny znacznik w imporcie automatycznym.
* **Enum zamiast kolejnej flagi bool.** `aggregatedListType` z wartością `AED` pozwala dodawać kolejne wykazy
  zbiorcze (np. przyszłe rejestry) przez dopisanie wartości do słownika – bez nowego elementu i nowej wersji
  struktury. W modelu prototypu odpowiada to kolumnie `zasoby.wykaz_typ` (`NULL` | `"AED"`).
* **Element opcjonalny (`minOccurs="0"`).** Brak elementu = zasób poza wykazami (jak `containsProtectedData=false`).
* **Położenie.** `resourceType` używa `xs:all`, więc kolejność elementów w pliku jest dowolna; w XSD element stoi
  obok `containsProtectedData`, bo pełni tę samą rolę.

## Zgodność wsteczna
* Wersja rozpoznawana jest po przestrzeni nazw korzenia (`urn:otwarte-dane:harvester:1.13` / `…:1.14`) i każda
  jest walidowana SWOIM schematem – pliki 1.13 dostawców importują się bez zmian (test:
  `tests/test_harvester_xsd.py::test_plik_113_nadal_przyjmowany`).
* Plik 1.13 nie może oznaczyć zasobu jako AED (element nie istnieje w 1.13 → błąd XSD), więc zasoby z 1.13 nigdy
  nie trafiają do wykazu przypadkiem; importer zwraca ostrzeżenie z podpowiedzią przejścia na 1.14.
* Każdy poprawny plik 1.13 po zamianie przestrzeni nazw na 1.14 jest poprawnym plikiem 1.14 (1.14 ⊃ 1.13).

## Reguły biznesowe po stronie importera (`app/harvester/__init__.py`), na wzór DGA
| DGA (mcod) | AED (prototyp) |
|---|---|
| >1 zasób z `containsProtectedData=true` w pliku → błąd (`get_dga_resources_info_from_xml_harvester_file`) | >1 zasób z `aggregatedListType=AED` w pliku → błąd dla tych zasobów, reszta importu działa |
| URL musi odpowiadać (`request_remote_dga`, timeout 3/5 s) | pobranie pliku (timeout 3/10 s, limit 10 MB, ochrona SSRF) |
| plik xls/xlsx/csv (`get_remote_extension_if_correct_dga_content_type`) | plik csv/xlsx |
| kolumny dokładnie jak `DGA_COLUMNS` (`validate_dga_file_columns`) | kolumny wzorca AED – walidacja w `repo_portal` (`BladWykazu` 422) |
| instytucja ma już zasób DGA z innego źródła → błąd (`get_dga_resource_for_institution`) | `BladWykazu` 409 z `repo_portal` |
| typ instytucji `private/other/developer` nie może mieć DGA | **brak ograniczenia** – firmy też są dysponentami/dostawcami AED |

## Weryfikacja
```
xmllint --noout --schema app/harvester/xsd/xml_import_otwarte_dane_1_14.xsd tests/fixtures/harvester/import_aed_1_14.xml
```
