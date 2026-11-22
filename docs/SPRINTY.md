# #TuBijeAED – plan sprintów

Zadanie: **Misja AED – Dane na ratunek** (HackNation 2026, Ministerstwo Cyfryzacji / dane.gov.pl).
Treść zadania i regulamin: `Dokumenty/`.

## Decyzje zespołu (2026-11-22)
1. Nazwa akcji: **#TuBijeAED**.
2. Program dla firm/instytucji: status **Partnera #TuBijeAED** z dopiskiem **„zweryfikowane w dane.gov.pl”** (bez używania nazwy/znaku MC w prototypie).
3. Dane OSM (ODbL): na mapie wyłącznie jako warstwa **„do weryfikacji”**; nie trafiają do eksportu dla dane.gov.pl (harvester przyjmuje tylko CC0/CC BY*). Dostępny osobny eksport ODbL poza harvesterem.
4. Agenci tylko wprowadzają zmiany w plikach – **commity robi wyłącznie człowiek** po weryfikacji sprintu.

## Zespół agentów
| Rola | Model / effort | Własność plików |
|---|---|---|
| Manager (sesja główna) | Opus 5.5 | `docs/`, `1_wzorzec_danych/aed_schema.json`, integracja, przegląd |
| API (dane.gov.pl) | Opus / high | `2_prototyp_kod/app/sources/`, `app/exports/`, `app/routers/sources.py`, `app/routers/export.py` |
| Backend | Sonnet / high | `2_prototyp_kod/app/` (pozostałe), `1_wzorzec_danych/generuj_wzorzec.py` |
| UI/UX | Opus / high | `3_branding/`, (Sprint 2) przegląd UX `static/` |
| Frontend | Sonnet / high | `2_prototyp_kod/static/` |
| Tester | Sonnet / medium | `2_prototyp_kod/tests/` (testy przekrojowe), `docs/RAPORT_TESTOW.md` |

## Sprint 0 – kontrakt (Manager) ✅
- `1_wzorzec_danych/aed_schema.json` – wzorcowy zakres danych (Table Schema).
- `docs/API.md` – kontrakt REST.
- Szkielet `2_prototyp_kod/app/`, środowisko `.venv`, oficjalny XSD 1.13 w `tests/fixtures/`.

## Sprint 1 – fundament + zgodność z dane.gov.pl + koncepcja znaku
Agenci: **API, Backend, UI/UX**.
- API: harvester XML 1.13 przechodzi walidację oficjalnym XSD; import 5 zbiorów AED z api.dane.gov.pl (Warszawa, Przemyśl, Krosno, Marki, Legionowo) z mapowaniem na schemat; OSM jako „do weryfikacji”; eksporty CSV/GeoJSON z licencjami.
- Backend: pakiet `app/`, SQLite, walidacja wg `aed_schema.json` (słowniki, pola warunkowe, NIP/REGON), raport walidacji per wiersz, deduplikacja z priorytetem źródeł, nowy wzorzec xlsx (listy rozwijane), naprawa XSS i `nan`.
- UI/UX: 3 koncepcje logo #TuBijeAED + warianty hasła + koncepcja odznaki Partnera → **wybór przez człowieka**.

**Kryterium wyjścia:** `pytest` zielony, `xmllint` OK, serwer startuje, dane z 5 JST na mapie, koncepcje znaku gotowe do wyboru.

## Sprint 2 – użytkownik i kampania
Agenci: **Frontend, UI/UX, Backend, API**.
- Frontend: nowy interfejs (tryb „Najbliższy AED” + 112, panel dysponenta krok po kroku, strona Partnerów, WCAG 2.2 AA, mobile).
- UI/UX: finalny znak (wektor, krzywe), księga znaku PDF, odznaka, `tokens.css`, przegląd UX.
- Backend: `/aed/nearest` z „dostępny teraz”, logika Partnera, odznaka SVG + strona weryfikacji.
- API: pakiet dla dysponenta (CSV + XML do własnego konta na dane.gov.pl).

## Sprint 3 – jakość i oddanie
Agenci: **Tester**, poprawki przez właściwych agentów, Manager.
- Testy przekrojowe, audyt WCAG, weryfikacja plików do oddania.
- Prezentacja (≥5 slajdów ze zrzutami), opis projektu, ograniczenia, oświadczenie o użyciu AI, README.
