# Program „Partner #TuBijeAED” – zachęty dla dostawców i rachunek opłacalności

> Adresat: **Ministerstwo Cyfryzacji** (właściciel portalu dane.gov.pl i Wykazu zbiorczego AED).
> Status: **propozycja zespołu cMBtb**. Kwoty to założenia do weryfikacji – edytowalny kalkulator: `docs/kalkulator_oplacalnosci_AED.xlsx`.

## 1. Co dostaje uczestnik programu

| Ścieżka | Dla kogo | Warunek | Co otrzymuje |
|---|---|---|---|
| **Partner** | instytucja lub firma, która **ma** AED | zasób AED opublikowany na własnym koncie w dane.gov.pl, poprawny wg wzorca, aktualizowany co najmniej raz na 12 mies. | **bezpłatny coroczny przegląd techniczny** i **pokrycie kosztów eksploatacji AED** (elektrody, bateria); odznaka do stopki strony i naklejka **„Współpracujemy z Ministerstwem Cyfryzacji w programie #TuBijeAED”**; zielona pinezka Partnera na mapie |
| **Nowy AED** | firma, która **nie ma** AED | zgłasza się do programu i zobowiązuje się opublikować dane nowego urządzenia w dane.gov.pl w ciągu 30 dni od montażu | **dofinansowanie zakupu AED** (propozycja: 50%), potem – jak Partner – przegląd i eksploatacja |

**Najważniejsza zasada: korzyści trwają tylko, dopóki dane są aktualne.** Gdy zasób nie jest aktualizowany przez 12 miesięcy, status Partnera wygasa (odznaka zmienia się na „wygasła”, co prototyp już pokazuje), a pokrycie kosztów eksploatacji jest wstrzymane. Państwo nie płaci za sprzęt, tylko za **aktualną, zweryfikowaną informację o sprzęcie**. Dla Ministerstwa Cyfryzacji to koszt utrzymania jakości danych.

Uwaga: naklejka i odznaka z nazwą Ministerstwa wymagają zgody MC. W prototypie używamy formuły „zweryfikowane w dane.gov.pl”, bez nazwy, logo i godła MC.

## 2. Rachunek opłacalności (wariant bazowy, 1 rok programu)

### Założenia
| Parametr | Wartość | Źródło / uzasadnienie |
|---|---|---|
| AED istniejące w programie (Partnerzy) | 1 000 | założenie skali pilotażu |
| Nowe AED z dofinansowaniem | 300 | założenie |
| Koszt eksploatacji AED (przegląd + elektrody + bateria) | 700 zł/rok | elektrody ok. 400 zł co 4 lata (okres ważności elektrod np. 4 lata – Stryker LIFEPAK CR2), bateria ok. 1 200 zł co 5 lat (ZOLL AED 3 – do 5 lat), przegląd ok. 300 zł → ~640 zł, zaokrąglone w górę |
| Cena AED | 8 000 zł | ceny rynkowe ok. 5–10 tys. zł |
| Dofinansowanie zakupu | 50% = 4 000 zł, amortyzacja 8 lat = 500 zł/rok | okres gwarancji popularnych modeli do 8 lat |
| Koszty obsługi programu (weryfikacja, kampania, obsługa) | 300 000 zł/rok | założenie |
| Prawdopodobieństwo użycia AED w roku | **5%** (konserwatywnie) | modele kosztowo-efektywnościowe przyjmują zwykle 20%, a 12% jako próg opłacalności (Cram i in. 2003) |
| Przeżywalność bez wczesnej defibrylacji | 10% | pozaszpitalne NZK w Europie: zwykle 2–12% |
| Przeżywalność z defibrylacją w 3–5 min | 50% | literatura podaje 49–75% |
| Koszt społeczny jednego zgonu | 2,05 mln zł | wycena KRBRD (ofiara śmiertelna, 2015), metoda kapitału ludzkiego |
| Koszt leczenia i opieki przy ciężkim stanie po NZK | 1 mln zł na pacjenta | **założenie zespołu do weryfikacji z NFZ/MZ** |

### Wynik
| | |
|---|---|
| **Koszt programu** | 1 000 × 700 + 300 × (700 + 500) + 300 000 = **1,36 mln zł/rok** |
| Użycia AED w roku | 1 300 × 5% = **65** |
| Dodatkowe przeżycia | 65 × (50% − 10%) = **26 osób/rok** |
| Wartość społeczna uratowanych osób | 26 × 2,05 mln zł = **53,3 mln zł/rok** |
| **Relacja korzyści do kosztów** | **≈ 39 : 1** |
| **Próg opłacalności** | program zwraca się, gdy uratuje **1 osobę w roku** (1,36 / 2,05 = 0,66) |

### Analiza wrażliwości (czy wynik się broni przy gorszych założeniach?)
| Scenariusz | Użycie AED / rok | Przeżywalność z AED | Dodatkowe przeżycia | Wartość | Korzyści : koszty |
|---|---|---|---|---|---|
| bazowy | 5% | 50% | 26 | 53,3 mln zł | 39 : 1 |
| ostrożny | 1% | 50% | 5,2 | 10,7 mln zł | 7,8 : 1 |
| bardzo ostrożny | 1% | 30% | 2,6 | 5,3 mln zł | 3,9 : 1 |
| jak w modelach naukowych | 20% | 50% | 104 | 213 mln zł | 157 : 1 |

### Ujęcie „1000 osób”
Na każde **1 000 osób z nagłym zatrzymaniem krążenia**, przy których AED zostanie użyty w ciągu kilku minut, przeżywa ok. **500 zamiast 100**. To **400 osób więcej**, czyli ok. **820 mln zł** kosztu społecznego zgonów, którego udaje się uniknąć.
Koszt leczenia **jednego** pacjenta w ciężkim stanie (założenie: 1 mln zł) to tyle, ile kosztuje eksploatacja **ok. 1 430 AED przez rok**.

Uczciwie trzeba dodać, że więcej przeżyć oznacza też więcej pacjentów wymagających leczenia szpitalnego. Wczesna defibrylacja (w ciągu minut) poprawia jednak rokowanie neurologiczne, a wynik programu jest dodatni nawet bez liczenia oszczędności na leczeniu – wystarczy wartość uratowanego życia.

## 3. Dlaczego to zadanie dla Ministerstwa Cyfryzacji
- **Ministerstwo płaci za dane, nie za sprzęt.** Pakiet przeglądu i eksploatacji jest „ceną” utrzymania aktualnego, zweryfikowanego rekordu AED w dane.gov.pl: ok. **1 050 zł rocznie za rekord**, licząc z obsługą programu (1,36 mln zł / 1 300 AED).
- **Wskaźniki (KPI) dla MC:** liczba dostawców w wykazie, odsetek rekordów aktualnych ≤ 12 mies., liczba nowych AED w wykazie, liczba pobrań i zapytań API.
- **Wykorzystanie danych w usługach cyfrowych państwa:** moduł „Najbliższy AED” w mObywatelu, przekazywanie danych dyspozytorom numeru 112 i systemom ratownictwa medycznego, aplikacje firm i organizacji pozarządowych korzystające z API.
- **Finansowanie (propozycja):** MC – platforma, weryfikacja danych i obsługa programu; sprzęt i eksploatacja we współfinansowaniu z MZ/NFZ, samorządami i partnerami prywatnymi (np. producentami AED i ubezpieczycielami).

## Źródła
- Częstość NZK, przeżywalność i wpływ czasu defibrylacji: [mp.pl – Medycyna Praktyczna](https://www.mp.pl/ratownictwo/algorytmy/163898,defibrylator-manualny-w-starciu-z-aed-czyli-kiedy-szybki-przyjazd-zespolu-moze-zmniejszyc-szanse-na-przezycie), [Kraków – Nagłe Zatrzymanie Krążenia](https://krakow.pl/3998,artykul,nagle-zatrzymanie-krazenia.html), [Polska Rada Resuscytacji (2013)](https://archiwum.dzierzoniow.pl/sites/default/files/pliki/informacjaprasowa2013.pdf), [Policja Katowice – AED](https://spkatowice.policja.gov.pl/download/363/280424/104AED.pdf)
- Koszty i eksploatacja AED: [swiatprzychodni.pl](https://swiatprzychodni.pl/artykuly/jakie-sa-rodzaje-defibrylatorow-aed-sprawdzamy/), [okazje.info.pl – Schiller FRED PA-1](https://www.okazje.info.pl/szukaj/schiller-aed-fred-pa-1-defibrylator-wersja-polautomatyczna-semi-auto/ceny.html), [Stryker LIFEPAK CR2 – katalog akcesoriów](https://www.stryker.com/content/dam/stryker/ems/products/lifepak-cr2/eu/resources/3329422_POLISH_LIFEPAK_CR2_Accessories_Catalog.pdf), [ZOLL AED 3](https://www.morele.net/masazer-zoll-defibrylator-automatyczny-prowadzi-ratownika-przez-caly-proces-rko-real-cpr-help-zoll-aed-3-fully-auto-15899675/)
- Koszt społeczny zgonu: [KRBRD – koszt zdarzeń drogowych 2015](https://www.krbrd.gov.pl/koszt-wszystkich-zdarzen-drogowych-w-polsce-w-2015-r-to-482-mld-zlotych/?print=pdf)
- Opłacalność dostępu publicznego do AED: [Cram i in. 2003](https://link.springer.com/article/10.1046/j.1525-1497.2003.21139.x), [Andersen i in. 2019 (PubMed)](https://www.pubmed.gov/30926453/), [HIQA – HTA of Public Access Defibrillation](https://www.hiqa.ie/sites/default/files/2017-01/HTA-of-Public-Access-Defibrillation.pdf)
