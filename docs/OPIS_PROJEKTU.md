# #TuBijeAED – Wykaz zbiorczy defibrylatorów AED w portalu dane.gov.pl

**Zadanie:** Misja AED – Dane na ratunek (HackNation 2026, Ministerstwo Cyfryzacji).

## Problem
Przy nagłym zatrzymaniu krążenia liczy się każda minuta, a defibrylatora AED może użyć każdy – pod warunkiem, że wie, gdzie jest najbliższe urządzenie, czy jest dostępne i czy działa. Dziś dane o AED są **rozproszone** (osobne zbiory gmin, bazy społecznościowe, prywatne mapy), **niejednolite** (każda gmina publikuje inne kolumny – sprawdziliśmy 5 zbiorów AED w dane.gov.pl: Krosno, Przemyśl, Marki, Legionowo, Warszawa) i **niezweryfikowane** – nikt nie bierze za nie odpowiedzialności.

## Rozwiązanie
1. **Wzorcowy zakres danych o AED** (`1_wzorzec_danych/`) – 29 pól w trzech grupach: kto odpowiada (dysponent), gdzie dokładnie jest urządzenie (adres, TERYT, współrzędne WGS84, kondygnacja, opis miejsca), czy da się go użyć teraz (dostępność w formacie maszynowym `opening_hours`, zabezpieczenie: klucz/kod/ochrona, instrukcja dostępu, status techniczny, przegląd). Słowniki, warunki między polami, sumy kontrolne NIP/REGON, zalecenie, by nie publikować kodów PIN („kod podaje dyspozytor 112”). Postać: XLSX z listami rozwijanymi i instrukcją, CSV, schemat maszynowy (Frictionless Table Schema).
2. **Wykaz zbiorczy AED w logice portalu** – rozbudowa mechanizmu, który portal już ma dla „Wykazu chronionych danych (DGA)”: dostawca oznacza swój zasób jako „wchodzi do Wykazu zbiorczego AED”, portal waliduje go wzorcem (raport błędów z numerem wiersza i pola), a zadanie scalające łączy wszystkie poprawne zasoby w jeden zbiór „Wykaz defibrylatorów AED – wykaz zbiorczy” (XLSX, CSV, GeoJSON, API) z kolumnami wskazującymi dostawcę i zasób źródłowy. Mechanizm jest uogólniony – kolejny wykaz to jeden wpis konfiguracji. Szczegóły i mapowanie funkcja-po-funkcji na kod portalu: `docs/ZGODNOSC_Z_DANE_GOV_PL.md`.
3. **Automatyczne zasilanie** – harvester XML (oficjalny schemat 1.13 + propozycja 1.14 z jednym nowym elementem `aggregatedListType`).
4. **Asystent dostawcy** – sprawdzenie pliku, konwersja istniejących zbiorów gmin do wzorca (ścieżka migracji), pakiet do publikacji na własnym koncie (CSV + XML + instrukcja).
5. **Mapa #TuBijeAED** – dla obywatela i służb: „Znajdź najbliższy AED” z odległością i informacją „dostępny teraz”, stały przycisk „Zadzwoń 112”, lista tekstowa jako alternatywa mapy; warstwa OpenStreetMap wyłącznie jako „do weryfikacji”.
6. **Akcja #TuBijeAED dla dostawców danych** – znak, hasło i program **„Partner #TuBijeAED – zweryfikowane w dane.gov.pl”**: instytucja lub firma, której zasób jest w wykazie, poprawny i aktualny (≤ 12 mies.), otrzymuje odznakę do stopki strony z publiczną weryfikacją i naklejkę na kapsułę AED. Odznaka **wygasa**, gdy dane przestają być aktualizowane – to zachęta do utrzymywania danych, nie jednorazowego wgrania.

## Użytkownicy i kroki
- **Dostawca danych (urząd, firma):** pobiera wzorzec → wypełnia lub konwertuje swój plik w asystencie → w panelu dostawcy dodaje zasób z zaznaczeniem „Wykaz zbiorczy AED” (lub przez harvester) → dostaje raport walidacji → po poprawie zasób trafia do wykazu → otrzymuje status Partnera i odznakę.
- **Administrator portalu (MC):** widzi historię scaleń, zasoby uwzględnione i pominięte z powodem, może przebudować wykaz.
- **Obywatel / służby:** mapa i lista najbliższych AED; deweloperzy: pliki i API wykazu.

## Prototyp
Klikalny prototyp okrojonego portalu, uruchamiany lokalnie jednym skryptem (`uruchom.sh` / `uruchom.bat`), z danymi demo działającymi bez internetu (prawdziwe zasoby 4 gmin z dane.gov.pl + fikcyjne, wyraźnie oznaczone firmy). Ścieżka dla jury: `JURY.md` i strona `http://localhost:8080/jury.html`.

## Zgodność z wymaganiami technicznymi
Formaty maszynowe (XLSX, CSV, GeoJSON, JSON, XML); zgodność z zasadami portalu (dostawca odpowiada za dane, licencje CC, model Instytucja–Zbiór–Zasób, harvester zgodny z XSD); WCAG 2.1 AA i responsywność (od 320 px) – wyniki audytu: `docs/RAPORT_TESTOW.md`.
