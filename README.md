# #TuBijeAED – Wykaz zbiorczy defibrylatorów AED w dane.gov.pl

Rozwiązanie zadania **„Misja AED – Dane na ratunek”** (HackNation 2026, Ministerstwo Cyfryzacji).
Dostawcy danych publikują zasoby o defibrylatorach na swoich kontach w portalu dane.gov.pl według wspólnego wzorca, a portal scala je w jeden **Wykaz defibrylatorów AED – wykaz zbiorczy** – na wzór istniejącego w kodzie portalu „Wykazu chronionych danych (DGA)”. Akcja **#TuBijeAED** zachęca urzędy i firmy do udziału (status „Partner – zweryfikowane w dane.gov.pl”).

**Zespół:** cMBtb  
**Dla jury: zacznij od [`JURY.md`](JURY.md).**

## Program „Partner #TuBijeAED”
Firma lub instytucja, która publikuje i aktualizuje dane swojego AED w dane.gov.pl, dostaje **bezpłatny przegląd i pokrycie kosztów eksploatacji AED**, odznakę i naklejkę „Współpracujemy z Ministerstwem Cyfryzacji w programie #TuBijeAED” (propozycja wymagająca zgody MC). Firma, która nie ma AED, może dostać **dofinansowanie zakupu** w zamian za opublikowanie danych nowego urządzenia. Korzyści trwają tylko, dopóki dane są aktualne.
W wariancie bazowym (1 300 AED) program kosztuje ok. **1,36 mln zł rocznie** i zwraca się, gdy uratuje **jedną osobę w roku**. Szczegóły, źródła i analiza wrażliwości: [`docs/PROGRAM_PARTNER.md`](docs/PROGRAM_PARTNER.md), kalkulator: `docs/kalkulator_oplacalnosci_AED.xlsx`.

## Szybki start (lokalnie)
```bash
./uruchom.sh          # Linux / macOS  (Windows: uruchom.bat)
# → http://localhost:8080/jury.html
```
Testy: `cd 2_prototyp_kod && ../.venv/bin/python -m pytest -q`

## Struktura
| Katalog | Zawartość |
|---|---|
| `1_wzorzec_danych/` | Wzorcowy zakres danych: `wzorzec_danych_aed.xlsx`, `.csv`, schemat `aed_schema.json`, generator |
| `2_prototyp_kod/` | Klikalny prototyp (FastAPI + HTML/CSS/JS): logika wykazu (`app/portal/`), harvester XML (`app/harvester/`), API 1.4, mapa, asystent; testy |
| `3_branding/` | Logotyp #TuBijeAED (SVG/PNG/JPG/PDF), księga znaku PDF, odznaki, generatory |
| `4_prezentacja/` | Prezentacja |
| `docs/` | Opis projektu, zgodność z dane.gov.pl, raport testów, ograniczenia, oświadczenie o AI, kontrakty (API, prototyp), plan sprintów |
| `Dokumenty/` | Treść zadania i regulamin |

## Oświadczenie o wykorzystaniu AI
Zespół **cMBtb** korzystał z narzędzi sztucznej inteligencji (Claude Code, model Claude firmy Anthropic) jako wsparcia przy:
- analizie zadania i kodu portalu dane.gov.pl;
- wersjach roboczych kodu prototypu, testów, wzorca danych i grafik;
- dokumentacji i wyliczeniach.

Kierunek rozwiązania, nazwę i znak akcji, program zachęt, zakres prototypu oraz weryfikację i zatwierdzanie wszystkich zmian zapewnił zespół, który ma pełnię praw do rozwiązania. Pełna treść: [`docs/OSWIADCZENIE_AI.md`](docs/OSWIADCZENIE_AI.md) (Regulamin §2 ust. 8).

## Licencje i źródła
Dane demonstracyjne: publiczne zbiory AED z dane.gov.pl (Krosno, Przemyśl, Marki – CC0 1.0 / CC BY 4.0; Legionowo – CC0 1.0) oraz wyraźnie oznaczone dane fikcyjne. Czcionka Poppins – SIL Open Font License. Schemat XSD harvestera 1.13 – z kodu źródłowego portalu dane.gov.pl (GPL v3), użyty do walidacji. Podkład mapy © OpenStreetMap contributors.
