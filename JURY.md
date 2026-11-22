# Instrukcja dla jury – #TuBijeAED (zespół cMBtb)

Każdy krok wskazuje **co otworzyć**, **jak to odczytać** i **które wymaganie z treści zadania** potwierdza. Prototyp działa lokalnie (bez internetu – poza podkładem mapy).

## A. Uruchomienie prototypu (ok. 2 min)
1. Wymagany Python ≥ 3.11. W katalogu głównym repozytorium uruchom:
   - Linux / macOS: `./uruchom.sh`
   - Windows: `uruchom.bat`
2. Skrypt utworzy środowisko, zainstaluje zależności, uruchomi serwer i otworzy **http://localhost:8080/jury.html** (ta sama ścieżka co niżej, w wersji klikalnej). Ponowne uruchomienie od czystych danych demo: `./uruchom.sh --reset` / `uruchom.bat reset`.

## B. Ścieżka w prototypie (klikalna wersja: `http://localhost:8080/jury.html`)
| Nr | Co zrobić | Co sprawdzić | Wymaganie zadania |
|---|---|---|---|
| 1 | Otwórz **Wykaz AED** (`/wykaz-aed.html`) | Jeden standardowy zbiór scalony z zasobów wielu dostawców; przy każdym rekordzie „Dostawca (odpowiada za dane)”; sekcja „Pominięte zasoby” z powodem (np. Krosno – braki w danych) | Integracja danych od wszystkich dysponentów w jednym zbiorze; dane zweryfikowane, z odpowiedzialnością |
| 2 | Na tej stronie kliknij **Pobierz XLSX / CSV / GeoJSON** oraz link **API** | Pliki i JSON w formatach maszynowych | Format odczytywalny maszynowo |
| 3 | Kliknij „Otwórz zbiór dostawcy” | Zasób oznaczony „Zasób wykazu AED”, status walidacji, instytucja odpowiedzialna | Zasady portalu: Instytucja → Zbiór → Zasób |
| 4 | **Panel dostawcy** (`/admin/`) → „Zaloguj jako” **Urząd m.st. Warszawy** → utwórz zbiór | Konto dostawcy bez zasobu AED | Panel administracyjny, odpowiedzialność dostawcy |
| 5 | Dodaj zasób: plik `static/przyklady/aed_z_bledami.csv` (link na stronie), zaznacz „Zasób wchodzi do Wykazu zbiorczego AED” | Zasób **odrzucony** z wykazu, tabela błędów: wiersz / pole / komunikat | Walidacja wg wzorcowego zakresu danych |
| 6 | Przy tym zasobie „Zaktualizuj” → plik `aed_poprawny.csv` | Zasób włączony, wykaz **przebudowany automatycznie** (nowy dostawca w kroku 1) | Mechanizm scalania wykazu (wzór: DGA w kodzie portalu) |
| 7 | (Alternatywa dla 5–6) **Import XML** – przykład `harvester_1_14_przyklad.xml` | Zbiór i zasób utworzone automatycznie | Automatyczne zasilanie – harvester dane.gov.pl |
| 8 | „Zaloguj jako” **Administrator portalu (MC)** → historia i „Przebuduj wykaz” | Kolejne scalenia, zasoby uwzględnione i pominięte | Utrzymanie wykazu przez właściciela |
| 9 | **Mapa** (`/mapa.html`) → „Znajdź najbliższy AED” (albo wpisz miasto / kliknij na mapie) | 3 najbliższe AED: odległość, „dostępny teraz”, jak dostać się do urządzenia, kto odpowiada; „Zadzwoń 112”; lista tekstowa; warstwa OSM tylko „do weryfikacji” | Użytkownik: służby i każdy z nas |
| 10 | **Dostawcy** → „Galeria Przykładowa” → status Partnera, odznaka, „Skopiuj kod do stopki”; porównaj „Spółdzielnia” (odznaka **wygasła**) | Program zachęt dla dostawców | Zachęcenie dysponentów do dzielenia się danymi |
| 11 | **Asystent** (`/asystent.html`) – sprawdź plik, przekonwertuj plik gminy (`gmina_stary_uklad_krosno.csv`), pobierz pakiet ZIP | Migracja istniejących zbiorów do wzorca, pakiet do publikacji | Zebranie danych z rozproszonych źródeł |
| 12 | Przetestuj na telefonie / wąskim oknie i klawiaturą (Tab) | Responsywność, skip link, widoczny focus | WCAG 2.1, responsywność, UX |

## C. Pliki do oceny
| Nr | Plik | Wymaganie |
|---|---|---|
| 13 | `docs/OPIS_PROJEKTU.md` | Tytuł i szczegółowy opis projektu |
| 14 | `4_prezentacja/` (PDF/PPTX) | Prezentacja: ≥ 5 slajdów ze zrzutami, kroki użytkownika, ograniczenia |
| 15 | `1_wzorzec_danych/wzorzec_danych_aed.xlsx` (arkusze: Instrukcja, Dane, Schemat_danych, Slowniki, Dane_przykladowe) + `aed_schema.json`, `wzorzec_danych_aed.csv` | Wzorcowy zakres danych (xlsx) |
| 16 | `docs/ZGODNOSC_Z_DANE_GOV_PL.md` | Zgodność z zasadami działania portalu – mapowanie na kod portalu funkcja po funkcji |
| 17 | `2_prototyp_kod/` (kod), `2_prototyp_kod/tests/` (testy: `../.venv/bin/python -m pytest -q`), `2_prototyp_kod/app/harvester/ZMIANY_XSD.md` | Kod źródłowy, prototyp |
| 18 | `3_branding/` – `logotyp_tubijeaed_*` (.svg, .png, .jpg, .pdf), `Ksiega_Znaku_TuBijeAED.pdf` | Logotyp (jpg/png/pdf + format otwarty SVG), księga znaku (kolorystyka, pole ochronne, minimalna wielkość, niedozwolone użycia, opis koncepcji 3–5 zdań) |
| 19 | `docs/RAPORT_TESTOW.md` | Wyniki testów i audytu WCAG 2.1 |
| 20 | `docs/OSWIADCZENIE_AI.md` | Zakres wykorzystania AI (Regulamin §2 ust. 8) |
| 21 | `docs/OGRANICZENIA.md` | Lista ograniczeń |
| 22 | `docs/PROGRAM_PARTNER.md` + `docs/kalkulator_oplacalnosci_AED.xlsx` | Program zachęt dla dostawców (przegląd i eksploatacja AED, dofinansowanie nowych AED, naklejka/odznaka) i rachunek opłacalności dla Ministerstwa Cyfryzacji – „zachęcenie dysponentów do dzielenia się danymi” |
