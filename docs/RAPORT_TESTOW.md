# Raport testów – prototyp #TuBijeAED (Sprint 2)

Data: 2026-11-22. Tester. Środowisko: Linux, Python 3.13, Firefox headless (Marionette), axe-core 4.x (wstrzyknięty do strony), serwer `uvicorn` na świeżej bazie, bez zmian w kodzie aplikacji.

## 1. Podsumowanie
| Obszar | Wynik |
|---|---|
| pytest (całość, z nowym e2e) | **277 passed**, 0 failed (po poprawkach Sprintu 3b; w audycie: 256) |
| e2e ścieżki jurora (`tests/test_e2e_jury.py`) | 2 testy: ścieżka jurora + idempotentny seed/restart – **zielone** |
| Ręczne przejście Firefox (klik) kroków 1–11 z `jury.html` | wykonalne w całości; 0 błędów JS w konsoli na 10 stronach; 0 martwych linków (ok. 350 linków) |
| axe-core (WCAG 2.0/2.1 A+AA + best-practice), 10 stron | 1 naruszenie łącznie (best-practice, strona startowa); 0 naruszeń A/AA; 2 strony z „incomplete” kontrastu (mapa, jury) |
| 320 / 390 / 640 px (zoom 200 %) | brak przewijania poziomego na żadnej stronie |
| Klawiatura | brak pułapek, focus zawsze widoczny, skip link działa |
| Błędy zgłoszone | P0: 0, P1: 3, P2: 8 |
| Poprawka „pustych Błąd:” | **potwierdzona** (`.pole-blad[hidden]` + `:empty`, 0 widocznych pustych etykiet) |

## 2. Wyniki pytest i e2e
- `pytest -q`: 277 passed po poprawkach (256 w chwili audytu), 1 ostrzeżenie (deprecacja anyio w Starlette – nieistotne).
- `test_sciezka_jurora`: wykaz po seedzie (12 rekordów, 3 dostawców, pominięci z powodem; pliki XLSX/CSV/GeoJSON pobieralne) → wszystkie strony i pliki z `static/przyklady` zwracają 200 → logowanie jako Urząd m.st. Warszawy → zbiór → `aed_z_bledami.csv` zapisany jako `BLEDY` z raportem (wiersz/pole/komunikat), nie wchodzi do wykazu → `aed_poprawny.csv` przez PUT → `OK`, wykaz przebudowany (+1 dostawca), rekordy w `/aed-aggregated/rekordy`, w CSV i w GeoJSON mapy → drugi zasób AED = 409 z podpowiedzią „zaktualizuj” → usunięcie → import `harvester_1_14_przyklad.xml` → partner AKTYWNY/WYGASŁY i odznaka SVG → asystent (wzorzec, sprawdź, konwertuj, pakiet ZIP z `dane_aed.csv`, `harvester_1_14.xml` z `aggregatedListType`, `INSTRUKCJA.txt`) → admin: przebudowa, historia; 403 dla dostawcy, 401 bez nagłówka.
- `test_seed_idempotentny`: ponowny start na tej samej bazie i ponowne wywołanie `zasiej_jesli_pusty()` nie dubluje danych.

## 3. Tabela błędów
| ID | Prio | Strona / endpoint | Opis + kroki | Oczekiwane | Właściciel |
|---|---|---|---|---|---|
| B-01 | P1 | Eksport wykazu: `/api/1.4/aed-aggregated/plik/xlsx` i `/csv` | **Wstrzyknięcie formuł (CSV/XLSX injection).** Dostawca wgrywa CSV z `=HYPERLINK("http://evil","x")` w `lokalizacja_szczegolowa` i `@SUM(1+1)` w `instrukcja_dostepu` (walidacja przechodzi, status OK). W XLSX wykazu komórka ma typ `f` (żywa formuła), w CSV wartość zaczyna się od `=`. Plik pobierają publicznie urzędy/aplikacje. | Wartości zaczynające się od `= + - @` (tab, CR) zapisywać jako tekst (prefiks `'` w CSV; `data_type='s'` w openpyxl) albo odrzucać w walidacji. | API (exports) / Backend (wykazy.py) |
| B-02 | P1 | Seed demo / `wykaz-aed.html`, mapa | Po seedzie wykaz zawiera tylko 12 rekordów, 3 dostawców i **tylko woj. mazowieckie**: zasoby Krosna, Przemyśla i Marek (a to one pokazują „migrację istniejących zasobów gmin”) są **pominięte** z powodu błędów walidacji (6/3/8 wierszy). Filtr „Województwo” ma 1 opcję, a mapa dla Krosna jest pusta. Wygląda to jak wada produktu, nie celowy przykład. | Zasoby gmin w seedzie przechodzą walidację (po konwersji + uzupełnieniu pól) i są w wykazie; błędny pozostaje tylko „Sklep Przykładowy”. Wtedy „Krosno ma już zasób AED” (jury.html) jest prawdą z poprawnym zasobem. | Backend (seed_portal / dane_demo) |
| B-03 | P1 | `jury.html` krok 11 vs `POST /api/admin/harvester/xml` | Tekst: „Import na koncie, które ma już zasób AED, kończy się czytelnym komunikatem o konflikcie”. Faktycznie powtórny import tego samego pliku (ten sam `extIdent`) kończy się „✔ Import zakończony powodzeniem – utworzone zbiory: 1, zasoby: 1”, choć nic nie utworzono (aktualizacja istniejącego). Wprowadza w błąd. Konflikt wystąpi tylko przy innym `extIdent`. | Odpowiedź rozróżnia „utworzono / zaktualizowano”; tekst jury.html zgodny z zachowaniem. | API (harvester) + Frontend (jury.html) |
| B-04 | P2 | `admin/index.html` – „Usuń” | Usuwa zasób natychmiast, bez potwierdzenia (i ew. przebudowuje wykaz). Łatwo przez pomyłkę usunąć zasób przed dowodem dla jury. | Potwierdzenie (dialog) albo „cofnij”. | Frontend |
| B-05 | P2 | `admin/index.html` po wysłaniu błędnego zasobu | Obok czerwonego „Zasób odrzucony” pojawia się zielony ✔ „Wykaz zbiorczy przebudowany: scalono 12 rekordów…”. Dwa przeciwstawne komunikaty; nie mówi, że przebudowa nie zmieniła wykazu. | Dla zasobu `BLEDY`: „Wykaz bez zmian – zasób pominięty” (neutralnie). | Frontend / Backend (treść `wykaz.komunikat`) |
| B-06 | P2 | `instytucja.html?id=abc` | Pokazuje surowy komunikat pydantic po angielsku: „instytucja_id: Input should be a valid integer…”. | Polski komunikat „Nieprawidłowy identyfikator” / 404. | API (api_14) / Frontend |
| B-07 | P2 | Wykaz CSV/XLSX, kolumna `url_zasobu_zrodlowego`; `jury.html` | Adresy zasobów w pliku wykazu są zapisywane z bazą `http://localhost:8080` z momentu scalania (Host). Przy uruchomieniu na innym porcie linki w pliku nie działają; odznaka używa Host z żądania (poprawnie). | Link względny lub budowany z `Host` przy pobieraniu; w dokumentacji jasne, że port to 8080. | API / Backend |
| B-08 | P2 | `index.html` (axe `landmark-complementary-is-top-level`) | `<aside>` zagnieżdżony w innym landmarku (best-practice, nie WCAG A/AA). | `<aside>` na najwyższym poziomie albo `<section>`. | Frontend |
| B-09 | P2 | `mapa.html` – nawigacja klawiaturą | 15 markerów Leaflet to osobne tabstopy (82 Tab na stronie); skip link „Pomiń mapę” jest, ale po skoku dalej jest długa lista. W trybie offline markery znikają, więc nie dotyczy. | Akceptowalne; opcjonalnie `keyboard:false` dla markerów (lista tekstowa jest alternatywą). | Frontend |
| B-10 | P2 | Nagłówek `X-Demo-Konto` | Akceptuje „ADMIN” i „ admin ” (case/space-insensitive). Zgodne z założeniem demo (brak haseł) – odnotowane. | Bez zmian (demo); zapisane w ograniczeniach. | Backend |
| B-11 | P2 | Brak `4_prezentacja/` | README linkuje katalog, którego nie ma (brak prezentacji – wymóg formalny §4). | Katalog + prezentacja min. 5 slajdów. | Zespół |

Nie znaleziono P0. Wszystkie kroki ścieżki jurora działają; błędy walidacji i konflikty (409) są czytelne po polsku.

### Status po poprawkach (Sprint 3b, 2026-11-22)
| ID | Status |
|---|---|
| B-01 | ✅ Naprawiony – wartości wyglądające na formułę zapisywane jako tekst (XLSX `data_type='s'`, CSV prefiks `'`) w wykazie i plikach asystenta; ostrzeżenie walidacji; testy. |
| B-02 | ✅ Naprawiony – seed: 4 dostawców, 2 województwa (Przemyśl i Legionowo – „DANE DEMO” po konwersji w asystencie), Krosno i Marki celowo odrzucone z raportem. |
| B-03 | ✅ Naprawiony – import XML rozróżnia `*_utworzone` / `*_zaktualizowane`; opis w `jury.html` poprawiony. |
| B-04 | ✅ Potwierdzenie przed usunięciem (natywny dialog). |
| B-05 | ✅ Neutralny komunikat „Wykaz odświeżony – Twój zasób nie został w nim uwzględniony”. |
| B-06 | ✅ Polski komunikat 422 dla błędnych parametrów + obsługa w UI. |
| B-07 | ⚪ Pozostawione – adresy w plikach wykazu z `BASE_URL` (domyślnie `http://localhost:8080`); opisane w ograniczeniach. |
| B-08 | ✅ `<aside>` zastąpiony grupą z etykietą. |
| B-09 | ✅ Markery z `keyboard:false`; alternatywą jest lista tekstowa i skip link. |
| B-10 | ⚪ Pozostawione – założenie demo (logowanie bez haseł). |
| B-11 | ✅ Prezentacja w `4_prezentacja/` (PDF + PPTX, 15 slajdów). |

## 4. WCAG 2.1 AA
### axe-core (10 stron, stan po załadowaniu danych)
| Strona | Naruszenia | Uwagi |
|---|---|---|
| index.html | 1 (best-practice: landmark-complementary-is-top-level) | B-08 |
| zbiory.html | 0 | |
| zbior.html?id=5 | 0 | tytuł strony dynamiczny „Zbiór: …” |
| wykaz-aed.html | 0 | |
| instytucja.html?id=7 | 0 | |
| partner.html?id=7 | 0 | |
| mapa.html | 0 | „incomplete”: color-contrast (14) – nakładki mapy; ręcznie zgodne z tokenami |
| admin/index.html | 0 | także po zalogowaniu, po raporcie błędów i na koncie administratora: 0 |
| asystent.html | 0 | także po wynikach sprawdzania/konwersji/pakietu: 0 |
| jury.html | 0 | „incomplete”: color-contrast (15) |
Każda strona: `lang="pl"`, dokładnie jeden `h1`, unikalny tytuł „… – #TuBijeAED (prototyp)”, skip link jako pierwszy tabstop (działa: fokus na `#tresc`).

### Lista ręczna
| Kryterium | Wynik |
|---|---|
| Klawiatura / kolejność Tab | OK na 10 stronach: skip link → logo → menu → treść → stopka; brak pułapek, brak „zapętlenia” poza naturalnym |
| Widoczność fokusu | OK – każdy element ma obrys/cień (sprawdzone na wszystkich tabstopach) |
| Nagłówki / landmarki | OK (1× h1, hierarchia; axe bez uwag poza B-08) |
| Etykiety pól | OK (axe label/aria 0); błędy pól `aria-describedby`, puste `.pole-blad` ukryte |
| `aria-live` / `role=status` | wyniki panelu, asystenta, mapy ogłaszane (`aria-live=polite`, `#status-logowania`) |
| Kontrast | tokeny zgodne z deklaracją (tekst 15,4:1, drugorzędny 7,5:1, zielony 4,8–6:1, alarm 5,25:1); axe 0 naruszeń; własny skrypt nieudany (fałszywe dane) – bez wniosków |
| Informacja nie tylko kolorem | OK – statusy z ikoną i tekstem (✔/✖/⚠), markery mapy różne kształtem, legenda |
| 320 px | brak przewijania poziomego (zmierzone iframe 320/390/640 px, 10 stron); tabele w kontenerze `tabela-opakowanie` (fokusowalny) |
| Zoom 200 % / 400 % | odpowiada szerokości 640/320 px – bez przewijania poziomego |
| `prefers-reduced-motion` | obsłużone w `portal.css` i `tokens.css` (nie testowane interaktywnie) |
| Mapa | `role=region` + `aria-label`, link „Pomiń mapę”, pełna lista tekstowa, przycisk „Zadzwoń 112” stale widoczny |
| Tryb ciemny | brak (nie wymagany) |

## 5. Bezpieczeństwo
| Test | Wynik |
|---|---|
| XSS z danych pliku (`<img src=x onerror=alert(1)>`, `"><script>`, `<svg onload>` w nazwie dysponenta, lokalizacji, instrukcji, ulicy; w tytule zbioru i zasobu, opisie) | OK – wszystko wyświetlane jako tekst na wykazie (także po filtrze), mapie (lista, najbliższe, popupy), zbiorach, instytucji, partnerze; brak wykonania skryptu. Kod: brak `innerHTML` w `static/js`, adresy przez `bezpiecznyAdres` |
| `javascript:` w `zdjecie_url` | odrzucone walidacją |
| Formuły w CSV/XLSX | **podatne – B-01** |
| Path traversal (`/resources/..%2f../file`, `plik/..%2f..`, `%2e%2e`, `%00`, `/data/aed.sqlite`, `/app/main.py`) | 404 we wszystkich próbach |
| Limit rozmiaru | plik 6 MB: panel, asystent i harvester → 413 z polskim komunikatem (limit 5 MB) |
| Cudzy zasób (`X-Demo-Konto` = inna instytucja) | GET/PUT/DELETE cudzego zasobu → 403; dodanie zasobu do cudzego zbioru → 403; harvester jako dostawca z cudzym `instytucja_id` – pole ignorowane (import na własne konto) |
| Nagłówek konta | nieznany/niepoprawny/SQL → 401; admin-only (`przebuduj`, `historia`) – 403 dla dostawcy, 401 bez nagłówka |
| SSRF przez URL zasobu | URL nie jest pobierany (status `BRAK`) – brak SSRF |
| CORS | `*` (demo; API publiczne, zapisy wymagają nagłówka) |

## 6. Odporność
- **Offline** (Firefox z proxy blokującym internet): mapa pokazuje „⚠ Mapa jest niedostępna … Wszystkie funkcje działają dalej”, przycisk „Znajdź najbliższy AED” i wyszukiwanie miasta działają, lista tekstowa i 3 najbliższe AED poprawne; pozostałe strony bez błędów w konsoli. Leaflet i kafle OSM tylko z internetu – zgodnie z założeniem.
- **Restart serwera**: 15 rekordów / 4 dostawców / 10 kont / pliki wykazu i zasobów – bez zmian.
- **Ponowny seed**: nie dubluje (test automatyczny + restart).
- Seed działa bez sieci.

## 7. Lista kontrolna oddania (sekcje 4–5 zadania)
| Wymóg | Stan |
|---|---|
| Szczegółowy opis i tytuł projektu | jest: `docs/OPIS_PROJEKTU.md` (25 linii), `README.md`, `JURY.md` |
| Prezentacja (min. 5 slajdów ze zrzutami, kroki użytkownika, ograniczenia) | **BRAK** – katalog `4_prezentacja/` nie istnieje (zrzuty z testów: scratchpad `shots/`) |
| Lista ograniczeń | jest: `docs/OGRANICZENIA.md` (do wpisania w prezentacji) |
| Prototyp | jest, `./uruchom.sh` / `uruchom.bat`, jury.html |
| Wzorzec danych xlsx | jest: `1_wzorzec_danych/wzorzec_danych_aed.xlsx` (+ csv, schema JSON) |
| Kod źródłowy | jest (`2_prototyp_kod/`, testy, `requirements*.txt`); w git część plików niezacommitowana (`app/portal/dane_demo/`, `requirements-dev.txt`, nowa księga znaku, test e2e) |
| Logotyp .jpg .png .pdf + format otwarty | jest: `3_branding/logotyp_tubijeaed_poziomy*` i `_sygnet` w jpg/png/pdf/svg (także negatyw), wszystkie z 04:41 |
| Księga znaku .pdf (nowa wersja) | jest: `3_branding/Ksiega_Znaku_TuBijeAED.pdf`, 15 stron (stara `Ksiega_Znaku_Otwarte_AED.pdf` usunięta w working tree) – do sprawdzenia merytorycznego przez UI/UX |
| Oświadczenie o AI | jest: `docs/OSWIADCZENIE_AI.md` |
| Formaty maszynowo odczytywalne | XLSX/CSV/GeoJSON/JSON API – OK; pdf tylko logotyp i księga |
| Zgodność z zasadami dane.gov.pl | `docs/ZGODNOSC_Z_DANE_GOV_PL.md` + testy XSD 1.14 |
| WCAG / responsywność | patrz §4 |
| Raport testów | ten plik |

Uwaga środowiskowa: do `.venv` doinstalowano `axe-selenium-python` (tylko do testów; nie ma go w `requirements*.txt`).
