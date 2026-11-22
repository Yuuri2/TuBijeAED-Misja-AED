# 3_branding – znak #TuBijeAED (koncepcja C, sygnet C2 „Fale nadawania”)

Znak i hasło akcji promocyjnej dla **dostawców danych o AED** (urzędy, firmy), program
„Partner #TuBijeAED – zweryfikowane w dane.gov.pl”. Właściciel: UI/UX.

## Zmiana hasła lub podpisu pod logo (ok. 1 minuty)

1. Zmień tekst w **`3_branding/teksty_marki.py`**:
   `HASLO`, `HASLO_PODTYTUL`, `PODPIS_LOGO`, `WEZWANIE`, teksty odznaki i naklejki, `QR_URL` (cel kodu QR –
   obecnie adres zastępczy `.example`), `OPIS_KONCEPCJI` (3–5 zdań do księgi).
2. Uruchom z katalogu repo:

   ```bash
   .venv/bin/python 3_branding/generuj_ksiege.py
   ```

To jedno polecenie przegeneruje **wszystko**: `2_prototyp_kod/static/brand/`, pliki logotypu do oddania,
zastosowania i Księgę znaku z podglądami. Dłuższy podpis pod logo zmniejsza się sam do szerokości nazwy, hasło
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
| `naklejka_kapsula_aed.{svg,pdf,png}` | naklejka 100 × 140 mm na kapsułę AED, wariant C2, prawdziwy kod QR (segno) |
| `kafel_social_1080.{svg,png}` | kafel 1080 × 1080 px do mediów społecznościowych (hasło, odznaka, wezwanie) |
| `baner_www_1200x300.{svg,png}` | baner www 1200 × 300 px |

## Źródła i generatory

| Plik | Rola |
|---|---|
| `teksty_marki.py` | **jedno miejsce tekstów** (nazwa, podpis, hasło, odznaka, naklejka, QR, opis koncepcji) |
| `final/generuj_final.py` | rysunek znaku: sygnet C2, logo, kompakt, odznaki, favicon, znaczniki mapy → `2_prototyp_kod/static/brand/`, podglądy `final/podglad/`, warianty ISO `final/warianty_iso/` |
| `generuj_logotypy.py` | pliki do oddania `logotyp_tubijeaed_*` i `zastosowania/` (najpierw uruchamia `generuj_final.py`) |
| `generuj_ksiege.py` | `Ksiega_Znaku_TuBijeAED.pdf` + podglądy stron `podglad_ksiegi/strona-NN.png` (50 dpi) – uruchamia wszystko powyżej |
| `koncepcje/` | **historia projektu** (Sprint 1): koncepcje A/B/C, plansza porównawcza, czcionki Poppins (`koncepcje/fonts/`, OFL) – nie oddajemy, ale z `koncepcje/generuj_koncepcje.py` korzysta klasa `Font` |
| `final/UWAGI_C.md`, `final/HASLA.md` | uzasadnienie wyboru C2 (odróżnienie od ISO 7010 E010) i propozycje haseł |

Zależności (w `.venv`): reportlab, svglib, cairosvg, fonttools, pillow, segno; do podglądów `pdftoppm` (poppler).

Kontrola po wygenerowaniu:

```bash
pdffonts 3_branding/Ksiega_Znaku_TuBijeAED.pdf     # tylko Poppins-*, emb = yes
pdftotext 3_branding/Ksiega_Znaku_TuBijeAED.pdf - | grep -c ą   # polskie znaki są tekstem
```

## Licencje

Czcionka Poppins: Copyright 2020 The Poppins Project Authors, SIL Open Font License 1.1
(`koncepcje/fonts/OFL_Poppins.txt`, `2_prototyp_kod/static/brand/fonts/OFL.txt`). Znak #TuBijeAED jest projektem
konkursowym HackNation 2026; nie jest oficjalnym znakiem Ministerstwa Cyfryzacji ani portalu dane.gov.pl.
