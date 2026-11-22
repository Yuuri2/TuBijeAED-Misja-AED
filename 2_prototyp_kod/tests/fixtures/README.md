# Fixtures

- `xml_import_otwarte_dane_1_13.xsd`, `harvester_example_1_13.xml` – oficjalny schemat i przykład importu XML
  z kodu źródłowego portalu dane.gov.pl (https://dane.gov.pl/source-code/backend_latest.zip,
  ścieżki `data/harvester/` i `data/test_samples/harvester/`, licencja GNU GPL v3, © KPRM/MC).
  Używane wyłącznie w testach do walidacji eksportu.

- `harvester/import_aed_1_14.xml` – przykład importu XML 1.14 (#TuBijeAED): zbiór Urzędu m.st. Warszawy z zasobem
  `aggregatedListType=AED` i zwykłym zasobem. Plik zasobu (`app/harvester/demo_pliki/warszawa_aed_demo.csv`) zawiera
  DANE FIKCYJNE oznaczone „[DEMO – dane fikcyjne]”; adres `https://demo.tubijeaed.example/…` (domena zastrzeżona
  RFC 2606) harvester prototypu czyta offline z katalogu demo. Waliduje się: `xmllint --noout --schema
  app/harvester/xsd/xml_import_otwarte_dane_1_14.xsd tests/fixtures/harvester/import_aed_1_14.xml`.
