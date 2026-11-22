# Koncepcja C a znak ISO 7010 E010 – uwagi i warianty do decyzji

Status: **do decyzji człowieka na koniec projektu.** W `static/brand/` nadal jest koncepcja C bez zmian kształtu.
Podgląd porównawczy: `podglad/warianty-iso.png`. Pliki wariantów: `warianty_iso/`. Generator: `generuj_final.py`
(funkcje `wariant_c1`, `wariant_c2`).

## Problem

ISO 7010 **E010** („Automatyczny defibrylator zewnętrzny”, zgodny z uniwersalnym znakiem ILCOR) to białe serce z
błyskawicą i białym krzyżem na zielonym polu znaku bezpieczeństwa. Koncepcja C to białe serce z zieloną błyskawicą na
zielonym kole. Ma ten sam rdzeń (serce i błyskawica, biel na zieleni), a różni się tylko kształtem pola (koło zamiast
kwadratu), brakiem krzyża i pierścieniami. Ryzyka:

1. **Na kapsule i ścianie przy AED** (naklejka Partnera) nasz znak może zostać wzięty za oficjalne oznakowanie albo
   je „rozmyć”. Znaki bezpieczeństwa wg ISO 7010 i PN-EN ISO 7010 mają ściśle określony wygląd i stosowanie.
2. **W małych rozmiarach** (16–24 px, odznaka 88×31) pierścienie zlewają się z kołem i zostaje praktycznie E010
   w kółku.
3. Komunikacyjnie znak mówi „tu jest defibrylator”. Kampania jest jednak skierowana do **dostawców danych**, a jej
   tematem są **dane i odpowiedzialność**, nie samo urządzenie.

## Wariant C1 – „Puls w sercu” (`warianty_iso/C1_puls_*.svg`)

Błyskawicę zastępuje **linia EKG (puls)** przecinająca serce. Pierścienie i zielone koło zostają.
- **Odróżnia od E010:** usuwa jego najbardziej charakterystyczny element (błyskawicę), więc znak nie jest już
  piktogramem defibrylatora, tylko „bijącym sercem”. Nazwa „Tu**Bije**” dostaje dosłowną ilustrację.
- **Zachowuje ideę C:** koło „tu jestem” z rozchodzącymi się falami, serce w centrum, te same kolory, ten sam
  logotyp.
- **Koszt:** słabsze skojarzenie z AED bez podpisu. Rekompensuje to „AED” w ExtraBold w logotypie. Motyw serca z EKG
  jest częsty w ochronie zdrowia.
- Czytelność: 24 px dobra, 16 px puls zamienia się w kreskę (jak błyskawica w obecnym C).

## Wariant C2 – „Fale nadawania” (`warianty_iso/C2_fale_*.svg`)

**Odwrócona polaryzacja:** zielone serce z białą błyskawicą, bez zielonego pola. Pełne pierścienie zastępują
**2 otwarte łuki** w prawym górnym rogu (jak symbol sygnału lub nadawania).
- **Odróżnia od E010:** E010 to białe serce na zielonym polu, a C2 to zielone serce bez pola. Sylwetka nie jest
  kwadratem ani kołem, tylko asymetrycznym sercem z falami, więc z daleka nie da się go wziąć za tabliczkę
  bezpieczeństwa. Łuki zajmują też miejsce, w którym E010 ma krzyż.
- **Zachowuje ideę C:** fale, czyli sygnał „tu jestem” i dane „nadawane” do otwartego portalu. Błyskawica zostaje,
  więc skojarzenie z AED jest nadal mocne.
- **Koszt:** traci „pulsującą kropkę” z map (pełne koncentryczne pierścienie), a w odznace 88×31 znak jest węższy.
  Jako znacznik mapy wymagałby osobnego tła (np. białej pinezki).
- Czytelność: dobra w 24–48 px, w 16 px łuki są cienkie (favicon: samo serce).

## Rekomendacja UI/UX

**C2** odróżnia znak od E010 najmocniej (inna polaryzacja i sylwetka) i dobrze pasuje do komunikacji „dane nadawane
do dane.gov.pl”. Jest to ważne zwłaszcza na **naklejce na kapsułę AED**, która wisi tuż obok oficjalnego znaku E010.
Jeśli zespół chce zostać bliżej obecnego C (koło z pierścieniami), wybierz **C1**. Niezależnie od wyboru proponuję
zasadę z księgi znaku: **naklejka #TuBijeAED nigdy nie zastępuje znaku E010 i nie jest umieszczana w jego miejscu**
(min. odstęp, opis „Partner – dane w dane.gov.pl”).

Pytanie do człowieka: C (bez zmian) / C1 / C2? Po decyzji podmiana zajmie kilka minut, bo w `generuj_final.py`
wystarczy podstawić inną funkcję sygnetu w `sygnet()` i `favicon_inner()`, a znaczniki mapy i odznaki przegenerują
się same.
