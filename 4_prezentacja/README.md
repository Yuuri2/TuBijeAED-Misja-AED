# 4_prezentacja – prezentacja rozwiązania #TuBijeAED

| Plik | Co to jest |
|---|---|
| `TuBijeAED_prezentacja.pdf` | prezentacja do oddania, 15 slajdów 16:9 – wektorowy tekst, osadzony Poppins, `Lang=pl-PL` |
| `TuBijeAED_prezentacja.pptx` | ta sama prezentacja w PowerPoint – edytowalny tekst, zrzuty jako obrazy (z tekstem alternatywnym) |
| `podglad/slajd-NN.png` | podglądy slajdów (40 dpi) |
| `zrzuty/*.png` | pełne zrzuty prototypu (1280 px CSS, telefon 390 px CSS, gęstość ×2) i „zrzuty” terminala |
| `zrzuty/kadry/*.png` | fragmenty zrzutów użyte na slajdach (wycinane automatycznie) |
| `zrzuty/kadry.json`, `zrzuty/terminal.json` | położenie elementów na zrzutach (do kadrowania) i wyniki poleceń (np. liczba testów) |

## Nazwa zespołu
Wpisz ją w **`generuj_prezentacje.py`**, stała `ZESPOL` na początku pliku (obecnie `"[nazwa zespołu]"`, pojawia się
na slajdach 1 i 15 oraz w metadanych PDF/PPTX), i przegeneruj prezentację (krok 3). Hasło i teksty marki są pobierane
z `3_branding/teksty_marki.py` – po zmianie hasła wystarczy krok 3.

## Jak przegenerować (z katalogu głównego repozytorium)
1. **Zrzuty prototypu** (Firefox, ok. 2 min; potrzebny świeży serwer, bo scenariusz zmienia dane):
   ```bash
   rm -f /tmp/prez.sqlite
   DB_PATH=/tmp/prez.sqlite .venv/bin/python 4_prezentacja/serwer_zrzuty.py --port 8090 &   # zapamiętaj PID
   .venv/bin/python 4_prezentacja/zrzuty_generuj.py --url http://localhost:8090
   kill <PID>
   ```
   `serwer_zrzuty.py` uruchamia aplikację bez zmian w kodzie, ustawiając tylko zegar „dostępny teraz” na środę
   25.11.2026, 12:00 (punkt podmiany `app.sources.godziny.teraz`, ten sam co w testach) – inaczej zrzut mapy zależy od
   pory generowania. Pojedyncze scenariusze: `--tylko wykaz,api,mapa,mapa_mobile,partner,asystent` (scenariusze
   `dostawca` i `admin` wymagają świeżej bazy). Mapa potrzebuje internetu (Leaflet, kafle OSM), `/docs` – CDN Swagger UI.
2. **Zrzuty terminala** (prawdziwe wyniki `xmllint` i `pytest` + fragment raportu axe z `docs/RAPORT_TESTOW.md`):
   ```bash
   .venv/bin/python 4_prezentacja/zrzuty_terminal.py
   ```
3. **Prezentacja** (PDF + PPTX + podglądy):
   ```bash
   .venv/bin/python 4_prezentacja/generuj_prezentacje.py
   pdffonts 4_prezentacja/TuBijeAED_prezentacja.pdf        # tylko Poppins-*, emb = yes
   ```
   Skrypt ostrzega („UWAGA slajd N…”), gdy tekst nie mieści się w polu albo zawiera znak, którego nie ma w Poppins
   (np. strzałka „→”).

Zależności: `.venv` z `2_prototyp_kod/requirements-dev.txt` (reportlab, svglib, pillow, fonttools, python-pptx),
Firefox, `xmllint`, `pdftoppm` (poppler).

## Uwagi
- PPTX używa czcionki **Poppins** (pliki: `3_branding/koncepcje/fonts/`, licencja OFL) – bez niej zainstalowanej
  PowerPoint podstawi inny krój i tekst może się przesunąć. Do oddania i pokazu używaj PDF.
- Zrzuty pokazują dane demo (gminy z dane.gov.pl + fikcyjne firmy oznaczone „demo”).
