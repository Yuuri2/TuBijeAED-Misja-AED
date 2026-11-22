# #TuBijeAED – założenia i plan sprintów

Zadanie: **Misja AED – Dane na ratunek** (HackNation 2026, Ministerstwo Cyfryzacji / dane.gov.pl).
Treść zadania i regulamin: `Dokumenty/`. Wytyczne mentorów: sekcja „Wytyczne mentorów” niżej.

## Wytyczne mentorów (2026-11-22) → co z nich wynika

| Wytyczna | Konsekwencja dla projektu |
|---|---|
| Problem: dane rozproszone i niezweryfikowane – **nikt nie bierze za nie odpowiedzialności** | Każdy rekord wykazu musi wskazywać **dostawcę** (instytucję/firmę z kontem w portalu). OSM nigdy nie trafia do wykazu – tylko warstwa „do weryfikacji” na mapie. |
| Nie wolno przebudować portalu tak, by każdy publikował; potrzebny dostawca | Dysponent publikuje zasób na **własnym koncie** w dane.gov.pl. Nasze narzędzia tylko mu w tym pomagają. |
| Dane mają być **zasobami w dane.gov.pl**, rozproszonymi po dostawcach → potrzebna **tabela zbiorcza – WYKAZ**; odtworzyć logikę istniejących wykazów na podstawie kodu | Wzorzec w kodzie portalu: **„Wykaz chronionych danych (DGA) – wykaz zbiorczy”** (`mcod/resources/dga_utils.py`, `dga_constants.py`, `tasks/dga.py`, model `AggregatedDGAInfo`, endpoint `/dga-aggregated`). Budujemy analogiczny **Wykaz defibrylatorów AED – wykaz zbiorczy**. |
| Najważniejsze: **dostosować i przebudować logikę i metody w portalu**, by wykazy pobierać i scalać w jedną standardową listę | Rdzeń rozwiązania = **logika wykazów zbiorczych na wzór mcod** (uogólnienie DGA, wykaz AED jako pierwsza instancja), pokazana w klikalnym prototypie portalu z mapowaniem 1:1 na pliki mcod (`docs/PROTOTYP.md`). |
| Postawić portal lokalnie (localhost = kopia dane.gov.pl), wejść do **panelu administracyjnego**, zrozumieć dodawanie zasobów i automatyzację | Okrojony klikalny prototyp portalu (decyzja zespołu): strony publiczne + panel administracyjny dostawcy, dodanie zasobu ręcznie i harvesterem XML. |
| Logotyp i hasło = **akcja promocyjna dla dostawców danych**, nie do pitchu | #TuBijeAED i program „Partner #TuBijeAED – zweryfikowane w dane.gov.pl” adresujemy do urzędów i firm. Hasła mówią do dostawcy. |
| **WCAG 2.1**, responsywność (PC, laptop, mobile), UX; wzorzec: www.gov.pl | Cel: WCAG 2.1 AA w naszych ekranach i w zmianach frontendu portalu. Audyt automatyczny + ręczny. |
| **Instrukcja dla jury** w ponumerowanych krokach | `JURY.md` (+ PDF): krok → plik/URL → które wymaganie spełnia. |
| **Klikalny prototyp**, bez konfiguracji po stronie jury | Hostowana wersja online (decyzja o hostingu – patrz „Decyzje otwarte”). |

## Architektura docelowa

```
 Dostawcy (JST, firmy)                    PORTAL dane.gov.pl (mcod) – NASZA MODYFIKACJA              Odbiorcy
 ─────────────────────                    ─────────────────────────────────────────────              ─────────────────────
 Asystent dostawcy (nasz FastAPI) ──┐     Zasób oznaczony „wykaz: AED” (formularz admina,           Mapa #TuBijeAED
  · walidacja wg wzorca             │     harvester XML 1.14, CKAN)                                  (czyta WYKAZ z API
  · konwersja starych plików gmin   ├──►  → walidacja kolumn i wartości wg wzorca AED          ──►   portalu; OSM tylko
  · pakiet CSV + XML do publikacji  │     → zadanie Celery: scalenie wszystkich zasobów AED          „do weryfikacji”)
 Panel admina portalu (ręcznie) ────┤       + kolumny „Nazwa dostawcy”, „Zasób źródłowy”          Służby, obywatele,
 Harvester XML/CKAN (automat) ──────┘     → zbiór „Wykaz defibrylatorów AED – wykaz zbiorczy”        deweloperzy (API)
                                            (właściciel: MC), API /aed-aggregated
```

Zasada: **scalanie odbywa się w portalu**. Nasza aplikacja niczego nie publikuje w imieniu dostawców.

## Decyzje zespołu
1. Nazwa akcji: **#TuBijeAED**.
2. Odznaka: **„Partner #TuBijeAED – zweryfikowane w dane.gov.pl”** (bez nazwy/znaku MC).
3. OSM: tylko warstwa „do weryfikacji” na mapie + osobny eksport ODbL; nigdy w wykazie.
4. Commity robi wyłącznie człowiek; po każdym sprincie weryfikacja.
5. Znak: **koncepcja C** („Puls – tu jestem”); ostatnie zmiany graficzne pod koniec.
6. Portal: **okrojony klikalny prototyp**, nie pełny mcod (Docker/RAM niepotrzebne).

## Decyzje otwarte
- Hasło główne, tekst odznaki, czcionka, cel kodu QR (znak: **koncepcja C** – wybrana; poprawki graficzne na koniec).
- Hosting klikalnego prototypu dla jury.
- Klucz API m.st. Warszawy (opcjonalnie).

## Zespół agentów
| Rola | Model / effort | Zakres |
|---|---|---|
| Manager (sesja główna) | Opus 5.5 | plan, kontrakty, integracja, przegląd |
| Backend | **Opus / high** (podniesione: modyfikacja Django/Celery portalu) | prototyp portalu: model, panel, walidacja zasobu, scalanie wykazu (wzór: DGA w mcod), Partner |
| API | Opus / high | harvester XML 1.14, publiczne API 1.4 + `/aed-aggregated`, mapa, asystent dostawcy |
| Frontend | Sonnet / high | strony klikalnego prototypu (portal, panel, wykaz, mapa, asystent) |
| UI/UX | Opus / high | finalny znak i księga znaku, odznaka, przegląd UX/WCAG obu interfejsów |
| Tester | Sonnet / medium | testy prototypu (pytest + ścieżka jurora), audyt WCAG 2.1, weryfikacja paczki dla jury |

## Sprint 0 – kontrakt ✅
`aed_schema.json`, `docs/API.md`, szkielet aplikacji, oficjalny XSD 1.13.

## Sprint 1 – fundament ✅ (do weryfikacji/commita)
Wzorzec danych + walidator, import i mapowanie 5 zbiorów gmin z dane.gov.pl, harvester XML 1.13 zgodny z XSD, koncepcje znaku.
**Nowa rola tych elementów:** walidator i mapowania gmin → „Asystent dostawcy” (konwersja istniejących zasobów do wzorca – ścieżka migracji dla gmin, które już publikują AED); generator XML → pakiet dla dostawcy; deduplikacja → tylko podgląd/kontrola jakości, nie źródło prawdy.

## Sprint 2 – klikalny prototyp portalu z Wykazem zbiorczym AED (w toku)
Decyzja (2026-11-22): **NIE stawiamy pełnego portalu mcod.** Budujemy bardzo okrojony klikalny prototyp, który wiernie odtwarza mechanikę wykazu zbiorczego DGA z kodu portalu i pokazuje realizację założeń. Kontrakt: **`docs/PROTOTYP.md`**.
Agenci równolegle: **Backend** (model portalu, panel, walidacja zasobu, scalanie wykazu, Partner), **API** (harvester XML 1.14, publiczne API 1.4 + `/aed-aggregated`, mapa, asystent dostawcy), **Frontend** (strony prototypu, WCAG 2.1 AA), **UI/UX** (koncepcja C → zasoby do `static/brand/`; ostatnie szlify graficzne na koniec projektu).
**Kryterium wyjścia:** opisane w `docs/PROTOTYP.md`.

## Sprint 3 – jakość i oddanie
- Tester: testy przekrojowe, audyt WCAG 2.1 (axe/pa11y + ręczny), test „ścieżki jurora”.
- Hosting klikalnego prototypu.
- `JURY.md`: ponumerowane kroki → plik/URL → wymaganie z treści zadania.
- Prezentacja (≥5 slajdów ze zrzutami, kroki użytkownika, ograniczenia), opis i tytuł projektu, oświadczenie o zakresie użycia AI, README.
