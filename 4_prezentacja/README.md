# 4_prezentacja – prezentacja rozwiązania #TuBijeAED

| Plik | Co to jest |
|---|---|
| `TuBijeAED_prezentacja.pdf` | prezentacja do oddania, 17 slajdów 16:9 – wektorowy tekst, osadzony Poppins, `Lang=pl-PL`, ok. 1,8 MB |
| `TuBijeAED_prezentacja.pptx` | ta sama prezentacja w PowerPoint – edytowalny tekst, zrzuty jako obrazy (z tekstem alternatywnym), ok. 1,5 MB |
| `zrzuty/kadry/*.png` | **wejście generatora**: fragmenty zrzutów prototypu użyte na slajdach (1280 px CSS, gęstość ×2) |
| `zrzuty/20_xmllint.png`, `21_pytest.png`, `22_axe.png` | „zrzuty” terminala (prawdziwe wyniki poleceń) |
| `zrzuty/kadry.json`, `zrzuty/terminal.json` | położenie elementów na pełnych zrzutach (do kadrowania) i wyniki poleceń (np. liczba testów) |
| `zrzuty/pelne/` | (tylko lokalnie, poza repozytorium – `zrzuty/.gitignore`) pełne zrzuty z `zrzuty_generuj.py`, ok. 30 MB |

Slajdy: 1 tytuł · 2 problem · 3 rozwiązanie · 4 wzorzec danych · 5 zgodność z dane.gov.pl · 6–10 zrzuty prototypu
(dostawca, automatyzacja, administrator, mapa) · 11 akcja #TuBijeAED · 12 program Partner – co zyskuje uczestnik ·
13 rachunek opłacalności dla MC · 14–15 dowody (API, XSD, testy, WCAG) · 16 ograniczenia · 17 jak sprawdzić +
oświadczenie o AI. Liczby na slajdzie 13 pochodzą z `docs/PROGRAM_PARTNER.md` (kalkulator: `docs/kalkulator_oplacalnosci_AED.xlsx`)
– po zmianie założeń popraw je w `generuj_prezentacje.py` (sekcja „# 13”).

Prezentacja **nie zawiera kodu QR** (naklejka w wariancie `naklejka_kapsula_aed_bez_qr`); wersja z QR jest tylko
w Księdze znaku. Naklejka „Współpracujemy z Ministerstwem Cyfryzacji…” na slajdzie 12 jest oznaczona jako projekt
wymagający zgody MC.

## Nazwa zespołu
Stała `ZESPOL` na początku **`generuj_prezentacje.py`** (obecnie `"cMBtb"`; slajdy 1 i 17, oświadczenie o AI,
metadane PDF/PPTX). Hasło i teksty marki są pobierane z `3_branding/teksty_marki.py` – po zmianie hasła wystarczy krok 3.

## Jak przegenerować (z katalogu głównego repozytorium)
Zwykle wystarczy **krok 3** – generator działa na zapisanych kadrach. Kroki 1–2 tylko, gdy zmienił się wygląd prototypu.

1. **Zrzuty prototypu** (Firefox, ok. 2 min; potrzebny świeży serwer, bo scenariusz zmienia dane):
   ```bash
   rm -f /tmp/prez.sqlite
   DB_PATH=/tmp/prez.sqlite .venv/bin/python 4_prezentacja/serwer_zrzuty.py --port 8090 &   # zapamiętaj PID
   .venv/bin/python 4_prezentacja/zrzuty_generuj.py --url http://localhost:8090
   kill <PID>
   ```
   Pełne zrzuty trafiają do `zrzuty/pelne/` (nie do repozytorium). Przy kroku 3 generator wytnie z nich kadry na nowo
   (`zrzuty/kadry/`), potem `zrzuty/pelne/` można usunąć.
   `serwer_zrzuty.py` uruchamia aplikację bez zmian w kodzie, ustawiając tylko zegar „dostępny teraz” na środę
   25.11.2026, 12:00 (punkt podmiany `app.sources.godziny.teraz`, ten sam co w testach) – inaczej zrzut mapy zależy od
   pory generowania. Pojedyncze scenariusze: `--tylko wykaz,api,mapa,mapa_mobile,partner,asystent` (scenariusze
   `dostawca` i `admin` wymagają świeżej bazy). Mapa potrzebuje internetu (Leaflet, kafle OSM), `/docs` – CDN Swagger UI.
2. **Zrzuty terminala** (prawdziwe wyniki `xmllint` i `pytest` + fragment raportu axe z `docs/RAPORT_TESTOW.md`):
   ```bash
   .venv/bin/python 4_prezentacja/zrzuty_terminal.py
   ```
3. **Prezentacja** (PDF + PPTX):
   ```bash
   .venv/bin/python 4_prezentacja/generuj_prezentacje.py            # --podglad: także podglad/slajd-NN.png (40 dpi)
   pdffonts 4_prezentacja/TuBijeAED_prezentacja.pdf                 # tylko Poppins-*, emb = yes
   ```
   Skrypt ostrzega („UWAGA slajd N…”), gdy tekst nie mieści się w polu albo zawiera znak, którego nie ma w Poppins
   (np. strzałka „→”). Obrazy osadza jako JPEG (q = 85, bez podpróbkowania kolorów) w rozdzielczości 2 px na punkt
   slajdu (1920 px na całą szerokość) – PDF i PPTX mieszczą się w ok. 2 MB. Odznaki i naklejki są wektorowe
   (rysowane z `3_branding`), w PPTX jako PNG.

Zależności: `.venv` z `2_prototyp_kod/requirements-dev.txt` (reportlab, svglib, cairosvg, pillow, fonttools,
python-pptx), Firefox, `xmllint`, `pdftoppm` (poppler, tylko do podglądów).

## Uwagi
- PPTX używa czcionki **Poppins** (pliki: `3_branding/fonts/`, licencja OFL) – bez niej zainstalowanej
  PowerPoint podstawi inny krój i tekst może się przesunąć. Do oddania i pokazu używaj PDF.
- Zrzuty pokazują dane demo (gminy z dane.gov.pl + fikcyjne firmy oznaczone „demo”).
