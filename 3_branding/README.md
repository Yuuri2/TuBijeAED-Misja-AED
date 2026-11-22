# 3_branding – znak #TuBijeAED (koncepcja C, sygnet C2 „Fale nadawania”)

Znak i hasło akcji promocyjnej dla **dostawców danych o AED** (urzędy, firmy), program
„Partner #TuBijeAED – zweryfikowane w dane.gov.pl”. Właściciel: UI/UX.

## Zmiana hasła lub podpisu pod logo (ok. 1 minuty)

1. Zmień tekst w **`3_branding/teksty_marki.py`**:
   `HASLO`, `HASLO_PODTYTUL`, `PODPIS_LOGO`, `WEZWANIE`, teksty odznaki i naklejek (`NAKLEJKA_*`, w tym
   `NAKLEJKA_MC*`), `QR_URL` (cel kodu QR – obecnie adres zastępczy `.example`), `OPIS_KONCEPCJI` (3–5 zdań do księgi).
2. Uruchom z katalogu repo:

   ```bash
   .venv/bin/python 3_branding/generuj_ksiege.py
   ```

To jedno polecenie przegeneruje **wszystko**: `2_prototyp_kod/static/brand/`, pliki logotypu do oddania,
zastosowania i Księgę znaku. Podglądy PNG (strony księgi w `podglad_ksiegi/`, plansze w `final/podglad/`) powstają
tylko z opcją `--podglad` – nie należą do oddawanych plików. Dłuższy podpis pod logo zmniejsza się sam do szerokości nazwy, hasło
zawija się z wyrównaniem wierszy. Skrypt przerywa pracę, jeśli w tekście jest znak, którego nie ma w Poppins.

## Pliki do oddania (wymagania zadania)

| Plik | Co to jest |
|---|---|
| `logotyp_tubijeaed_poziomy.{svg,png,jpg,pdf}` | logo podstawowe; SVG = format otwarty, PNG 3000 px z przezroczystym tłem, JPG na bieli, PDF wektorowy |
| `logotyp_tubijeaed_poziomy_negatyw.{svg,png,jpg,pdf}` | negatyw; SVG i PNG z przezroczystym tłem, JPG i PDF na granacie `#0B2545` |
| `logotyp_tubijeaed_sygnet.{svg,png,jpg,pdf}` | sam sygnet; PNG 2000 px, JPG na bieli |
| `Ksiega_Znaku_TuBijeAED.pdf` | księga znaku, 15 stron A4 poziomo, wektorowa, czcionka Poppins osadzona |

Pliki `logotyp_tubijeaed_*` mają wbudowane **pole ochronne** (x = 1/4 wysokości sygnetu). Tekst w znaku jest
zamieniony na krzywe – pliki nie wymagają czcionki. PDF-y logotypu powstają z SVG przez cairosvg (wektor, bez bitmap).

## Zastosowania (`zastosowania/`)

| Plik | Co to jest |
|---|---|
| `naklejka_kapsula_aed.{svg,pdf,png}` | naklejka 100 × 140 mm na kapsułę AED, wariant C2, prawdziwy kod QR (segno) – w księdze |
| `naklejka_kapsula_aed_bez_qr.{svg,pdf,png}` | ta sama naklejka **bez kodu QR** (pinezka Partnera i tekst „dane w dane.gov.pl”) – w prezentacji |
| `naklejka_wspolpraca_mc.{svg,pdf,png}` | **PROJEKT** naklejki 100 × 100 mm „Współpracujemy z Ministerstwem Cyfryzacji w programie #TuBijeAED” (bez logo i godła MC; użycie **wymaga zgody MC**) – program Partner, `docs/PROGRAM_PARTNER.md` |
| `kafel_social_1080.{svg,png}` | kafel 1080 × 1080 px do mediów społecznościowych (hasło, odznaka, wezwanie) |
| `baner_www_1200x300.{svg,png}` | baner www 1200 × 300 px |

## Źródła i generatory

| Plik | Rola |
|---|---|
| `teksty_marki.py` | **jedno miejsce tekstów** (nazwa, podpis, hasło, odznaka, naklejki, QR, opis koncepcji) |
| `fonty_svg.py` | tekst Poppins → krzywe SVG (klasa `Font`, kerning GPOS) – używają go wszystkie generatory |
| `fonts/` | czcionki Poppins (TTF) + licencja `OFL_Poppins.txt` – źródło dla znaku, księgi, `static/brand/fonts/` i prezentacji |
| `final/generuj_final.py` | rysunek znaku: sygnet C2, logo, kompakt, odznaki, favicon, znaczniki mapy → `2_prototyp_kod/static/brand/`; z `--podglad` także plansze PNG w `final/podglad/` (m.in. warianty C / C1 / C2 względem ISO 7010 E010, rysowane w locie) |
| `generuj_logotypy.py` | pliki do oddania `logotyp_tubijeaed_*` i `zastosowania/` (najpierw uruchamia `generuj_final.py`) |
| `generuj_ksiege.py` | `Ksiega_Znaku_TuBijeAED.pdf` – uruchamia wszystko powyżej; z `--podglad` także `podglad_ksiegi/strona-NN.png` (50 dpi) |
| `final/UWAGI_C.md`, `final/HASLA.md` | uzasadnienie wyboru C2 (odróżnienie od ISO 7010 E010) i propozycje haseł |

Koncepcje A/B/C ze Sprintu 1 (archiwum `koncepcje/`) usunięto z repozytorium – są w historii git (commit `5354392`).
Księga nadal pokazuje odrzucone warianty (C, C1) i porównanie z E010 – rysuje je w locie.

Zależności (w `.venv`): reportlab, svglib, cairosvg, fonttools, pillow, segno; do podglądów `pdftoppm` (poppler).

Kontrola po wygenerowaniu:

```bash
pdffonts 3_branding/Ksiega_Znaku_TuBijeAED.pdf     # tylko Poppins-*, emb = yes
pdftotext 3_branding/Ksiega_Znaku_TuBijeAED.pdf - | grep -c ą   # polskie znaki są tekstem
```

## Licencje

Czcionka Poppins: Copyright 2020 The Poppins Project Authors, SIL Open Font License 1.1
(`fonts/OFL_Poppins.txt`, `2_prototyp_kod/static/brand/fonts/OFL.txt`). Znak #TuBijeAED jest projektem
konkursowym HackNation 2026; nie jest oficjalnym znakiem Ministerstwa Cyfryzacji ani portalu dane.gov.pl.
