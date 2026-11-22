# static/brand – zasoby #TuBijeAED (koncepcja C, sygnet C2 „Fale nadawania”)

**Decyzja: C2.** Sygnet to zielone serce z wyciętą błyskawicą (prześwituje tło), bez zielonego pola, z dwoma otwartymi łukami sygnału
(odróżnia znak od ISO 7010 E010, uzasadnienie w `3_branding/final/UWAGI_C.md`). Nazwy plików, tokeny, placeholder
`DD.MM.RRRR` i kotwice znaczników się nie zmieniły.

Właściciel: UI/UX. Pliki SVG generuje `3_branding/final/generuj_final.py` (nie edytuj ich ręcznie, tylko zmień generator
i uruchom go ponownie: `.venv/bin/python 3_branding/final/generuj_final.py`, a najlepiej całość: `.venv/bin/python 3_branding/generuj_ksiege.py`). Teksty (podpis pod logo, hasło, napisy odznaki) są w `3_branding/teksty_marki.py` – opis w `3_branding/README.md`. Każdy SVG ma `role="img"`, `aria-label`
i `<title>`, nie zawiera skryptów ani zewnętrznych odwołań, a tekst jest zamieniony na krzywe. Wyjątkiem jest data
ważności odznaki (opis niżej). Aplikacja serwuje `static/` pod `/`, więc adresy plików to `/brand/<plik>`.

## Pliki

| Plik | Rozmiar (viewBox) | Użycie |
|---|---|---|
| `logo.svg` | 681×160 | logo poziome z podpisem „DEFIBRYLATORY NA MAPIE · OTWARTE DANE”, jasne tło; wysokość w UI **≥ 64 px** (żeby podpis był czytelny) |
| `logo-negatyw.svg` | 681×160 | to samo na granacie `--kolor-tlo-ciemne` (tło przezroczyste; serce i fale w `#5FD38D`, błyskawica wycięta – ma kolor tła) |
| `logo-kompakt.svg`, `logo-kompakt-negatyw.svg` | 783×160 | bez podpisu, do nagłówka 32–56 px i na telefony |
| `sygnet.svg` | 100×100 | sam znak C2 (awatar, kafle, ikona ≥ 24 px); przezroczyste tło, tylko na jasnym podłożu |
| `favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` | 100×100 / 32 / 180 | uproszczony C2 (większe serce, grubsza błyskawica, jeden gruby łuk), czytelny w 16/32 px na jasnej i ciemnej karcie |
| `odznaka-{jasna,ciemna}-pelna.svg` | 200×60 | odznaka Partnera z datą ważności |
| `odznaka-{jasna,ciemna}-mala.svg` | 88×31 | mała odznaka (data tylko w `title`/`aria-label`) |
| `odznaka-wygasla-{pelna,mala}.svg` | 200×60 / 88×31 | odznaka wygasła: szara, **przerywana ramka** i ikona zegara zamiast ptaszka (różni się nie tylko kolorem) |
| `marker-wykaz.svg`, `marker-partner.svg`, `marker-osm.svg` | 32×40 / 32×40 / 32×32 | znaczniki mapy, patrz niżej |
| `tokens.css` | – | tokeny i `@font-face` |
| `fonts/Poppins-{Regular,Medium,SemiBold,Bold,ExtraBold}.woff`, `fonts/OFL.txt` | – | Poppins (SIL OFL 1.1), podzbiór: łacina + polskie znaki + typografia, ok. 11 kB na krój |

Nagłówek HTML:

```html
<link rel="icon" href="/brand/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/brand/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/brand/apple-touch-icon.png">
<link rel="stylesheet" href="/brand/tokens.css">
...
<a href="/" class="logo"><img src="/brand/logo-kompakt.svg" alt="#TuBijeAED – strona główna" height="40"></a>
```

**Pole ochronne** logo: wokół znaku zostaw wolne miejsce równe 1/4 wysokości sygnetu (w nagłówku 40 px = 10 px).
Pliki mają ciasny `viewBox` bez wbudowanego marginesu. Logo nie zastępuje paska „Prototyp – … Nie jest to oficjalny
serwis.” i nie może stać obok logo dane.gov.pl, MC ani godła.

## Odznaka Partnera – data ważności (kontrakt z Backendem)

Każda odznaka zawiera placeholder **`DD.MM.RRRR`** w `<title>`, w `aria-label` i w wersji pełnej w elemencie:

```xml
<text id="wazny-do" ...>do DD.MM.RRRR</text>        <!-- odznaka-jasna/ciemna-pelna -->
<text id="wazny-do" ...>wygasła DD.MM.RRRR</text>   <!-- odznaka-wygasla-pelna -->
```

Backend (`GET /api/partnerzy/{id}/odznaka.svg?wariant=jasna|ciemna&rozmiar=mala|pelna`) czyta plik i podmienia
**wszystkie** wystąpienia placeholdera:

```python
nazwa = "odznaka-wygasla" if status == "WYGASŁY" else f"odznaka-{wariant}"
svg = (BRAND / f"{nazwa}-{rozmiar}.svg").read_text(encoding="utf-8")
svg = svg.replace("DD.MM.RRRR", wazny_do.strftime("%d.%m.%Y"))   # np. 22.11.2027
# Content-Type: image/svg+xml; charset=utf-8
```

- Wariant wygasły jest tylko jasny: dla `status == "WYGASŁY"` parametr `wariant` jest ignorowany.
- Data jest żywym tekstem z `text-anchor="end"` w wersji aktywnej, więc nie najedzie na „PARTNER” nawet z czcionką
  zastępczą. W `<img>` przeglądarka nie ładuje Poppins i użyje Segoe UI/Roboto/Arial, co jest celowe.
- Format daty: `DD.MM.RRRR` (10 znaków). Dłuższy tekst (np. nazwa miesiąca) się nie zmieści.
- Kod do stopki strony Partnera (pokazywany w `instytucja.html`):

```html
<a href="https://<host>/partner.html?id=12">
  <img src="https://<host>/api/partnerzy/12/odznaka.svg?wariant=jasna&rozmiar=pelna" width="200" height="60"
       alt="Partner #TuBijeAED – dane o defibrylatorze zweryfikowane w dane.gov.pl, ważne do 22.11.2027">
</a>
```

Na ekranach o dużej gęstości odznaka jest ostra w każdym rozmiarze (SVG). Mała odznaka 88×31 ma tekst ok. 7–10 px,
więc pełną treść niesie `alt`. Jeśli miejsce pozwala, używaj odznaki pełnej.

## Znaczniki mapy (WCAG 1.4.1 – różnią się kształtem, nie tylko kolorem)

| Plik | Kształt | Kolor | Znaczenie | Leaflet |
|---|---|---|---|---|
| `marker-wykaz.svg` | **okrągła pinezka (kropla)** z sercem i błyskawicą | zieleń AED, granatowy obrys | AED z **wykazu zbiorczego** w dane.gov.pl | `iconSize:[32,40], iconAnchor:[16,39], popupAnchor:[0,-34]` |
| `marker-partner.svg` | **kwadratowy dymek** z sercem + kółko z **ptaszkiem ✓** w rogu | granat + zieleń sygnałowa | AED z wykazu, którego dostawca jest **Partnerem #TuBijeAED** (`properties.partner == true`) | `iconSize:[32,40], iconAnchor:[16,38], popupAnchor:[0,-34]` |
| `marker-osm.svg` | **romb z przerywaną krawędzią** i znakiem **„?”** | biały + szary | punkt z **OpenStreetMap „do weryfikacji”** (ODbL, nie jest w wykazie) | `iconSize:[28,28], iconAnchor:[14,14], popupAnchor:[0,-14]` |

Znaczniki nie zawierają sygnetu (to piktogram serca z błyskawicą w pinezce), więc wybór C2 ich nie zmienił.
Czytelne w 28–36 px (podgląd: `3_branding/final/podglad/markery.png`). Każdy kształt ma obrys, który oddziela go od
podkładu (zieleń na tle OSM `#F2EFE9` ma 4,19:1, granat 13,41:1, szary 6,56:1, czyli ≥ 3:1 wg WCAG 1.4.11).

```js
const ikona = (plik, w, h, ax, ay) => L.icon({ iconUrl: `/brand/${plik}`, iconSize: [w, h],
  iconAnchor: [ax, ay], popupAnchor: [0, -(h - 6)] });
const IKONY = { wykaz: ikona('marker-wykaz.svg', 32, 40, 16, 39),
                partner: ikona('marker-partner.svg', 32, 40, 16, 38),
                osm: ikona('marker-osm.svg', 28, 28, 14, 14) };
// L.marker(latlng, { icon: p.partner ? IKONY.partner : IKONY.wykaz, alt: 'AED: ' + p.nazwa, keyboard: true })
```

Legenda w HTML (pokazuje kształt **i** tekst): `<img src="/brand/marker-partner.svg" alt="" width="24"> AED Partnera
#TuBijeAED (zweryfikowany)`. `alt=""` jest tu poprawne, bo obok stoi tekst. Mapa ma też alternatywę w postaci listy
tekstowej.

## Przegląd kontrastów tokenów (WCAG 2.1, wzór względnej luminancji)

Próg AA: tekst normalny ≥ 4,5:1, tekst duży (≥ 24 px albo ≥ 18,66 px bold) ≥ 3:1, elementy UI i grafika ≥ 3:1.

| Tekst / element | Tło | Kontrast | AA | Uwagi |
|---|---|---|---|---|
| `--kolor-tekst` #0B2545 | `--kolor-tlo` #FFF | 15,39:1 | tak | |
| `--kolor-tekst` | `--kolor-tlo-jasne` #E8F5EE | 13,72:1 | tak | |
| `--kolor-tekst-drugorzedny` #4A5568 | biel | 7,53:1 | tak | |
| `--kolor-tekst-drugorzedny` | mięta | 6,71:1 | tak | |
| `--kolor-glowny` #00843D | biel | 4,81:1 | tak | linki, „AED”, „PARTNER” |
| `--kolor-glowny` | mięta | **4,29:1** | **tylko tekst duży** | na mięcie dla zwykłego tekstu i linków użyj `--kolor-glowny-ciemny` |
| `--kolor-glowny-ciemny` #006A31 | mięta | 6,03:1 | tak | |
| `--kolor-glowny-ciemny` | biel | 6,76:1 | tak | |
| `--kolor-tekst-na-glownym` #FFF | `--kolor-glowny` | 4,81:1 | tak | przycisk główny |
| biel | `--kolor-glowny-ciemny` (hover) | 6,76:1 | tak | |
| `--kolor-alarm` #D90429 | biel | 5,25:1 | tak | 112, błędy |
| biel | `--kolor-alarm` | 5,25:1 | tak | przycisk „Zadzwoń 112” |
| `--kolor-alarm` | mięta | 4,68:1 | tak | |
| `--kolor-alarm` | `--kolor-tlo-alarm` #FDECEE | 4,60:1 | tak | komunikat błędu |
| `--kolor-ostrzezenie` #8A5A00 | biel | 5,93:1 | tak | |
| `--kolor-ostrzezenie` | `--kolor-tlo-ostrzezenie` #FFF6E0 | 5,51:1 | tak | |
| `--kolor-ostrzezenie` | mięta | 5,29:1 | tak | |
| `--kolor-tekst-na-ciemnym` #FFF | `--kolor-tlo-ciemne` #0B2545 | 15,39:1 | tak | nagłówek/stopka |
| `--kolor-akcent-na-ciemnym` #5FD38D | granat | 8,20:1 | tak | „AED” w negatywie, linki na ciemnym |
| `--kolor-tekst-drugorzedny-na-ciemnym` #C5D3E0 | granat | 10,09:1 | tak | |
| `--kolor-fokus` #0B2545 (obrys 3 px) | biel / mięta | 15,39 / 13,72:1 | tak | 1.4.11 / 2.4.7 |
| `--kolor-fokus-na-ciemnym` #5FD38D | granat | 8,20:1 | tak | fokus w nagłówku ciemnym |
| `--kolor-obramowanie-pola` #7A8794 | biel | 3,67:1 | tak (UI) | krawędź input/select/checkbox |
| `--kolor-obramowanie-pola` | mięta | 3,27:1 | tak (UI) | |
| `--kolor-obramowanie` #CBD5E0 | biel | 1,49:1 | **nie** | **tylko dekoracyjnie** (karty, separatory), nigdy jako jedyna krawędź pola formularza |
| `--kolor-akcent-na-ciemnym` | biel | 1,88:1 | **nie** | zakaz na jasnym tle |
| `--kolor-glowny` | granat | 3,20:1 | tylko grafika | nie tekst; sygnet na granacie używa `#5FD38D` (8,20:1) |
| `--kolor-alarm` | granat | 2,93:1 | **nie** | zakaz |
| `--kolor-alarm` | `--kolor-glowny` | 1,09:1 | **nie** | zakaz (czerwień nigdy na zieleni) |

Wnioski UX:
1. Wartości tokenów z kontraktu **nie wymagały zmian**. Wszystkie pary używane w UI spełniają AA. Jedyne pułapki to
   zielony tekst na mięcie (używaj `--kolor-glowny-ciemny`) i `--kolor-obramowanie` jako krawędź pola formularza
   (używaj nowego `--kolor-obramowanie-pola`).
2. Fokus: `outline: var(--szerokosc-fokusu) solid var(--kolor-fokus); outline-offset: var(--odstep-fokusu)`, a na
   granacie `--kolor-fokus-na-ciemnym`. Nie używaj czerwieni jako koloru fokusu (stary `index.html` tak robił).
3. Status (OK / błąd / ostrzeżenie / Partner / wygasła) zawsze pokazuj ikoną lub tekstem, nie samym kolorem (1.4.1).
4. Animacje (np. pulsowanie pierścieni sygnetu) tylko z `var(--czas-animacji)`, który przy
   `prefers-reduced-motion: reduce` wynosi 0.
5. Cele dotyku (przycisk „Znajdź najbliższy AED”, „Zadzwoń 112”) mają co najmniej `--cel-dotyku` (44 px).
