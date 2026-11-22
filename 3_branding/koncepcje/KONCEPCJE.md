# #TuBijeAED – koncepcje znaku, hasła i odznaki (Sprint 1, do wyboru)

Plansza porównawcza: `plansza_koncepcji.png`. Wszystkie pliki SVG generuje `generuj_koncepcje.py`.
Tekst jest już **zamieniony na krzywe** (fontTools), więc SVG wyglądają tak samo w każdej przeglądarce
i nie zależą od czcionek zainstalowanych w systemie (to był problem starego znaku).
Czcionka źródłowa: **Poppins** (Regular / Medium / SemiBold / Bold / ExtraBold, SIL OFL 1.1, pełne polskie znaki),
pliki i licencja w `fonts/`.

## Trzy koncepcje

### A · Serce-pinezka (`koncepcja_A*.svg`)
Serce jest jednocześnie pinezką na mapie: jego ostry dolny czubek wskazuje miejsce („**Tu**”), a biała linia EKG
pokazuje, że serce „**bije**”. Hasztag ma jeden kolor dla „#TuBije” (granat) i drugi dla „AED” (zieleń AED), więc
słowa czyta się bez wysiłku. Sygnet może być bez zmian markerem na mapie w prototypie. Zielona pinezka Partnera to po prostu ten znak.
- **Plusy:** najłatwiej zrozumieć bez podpisu (serce + miejsce = „tu jest AED”), czytelny w 24 px, jeden kształt
  łączy mapę, kampanię i odznakę, dobrze wycina się jako naklejka.
- **Minusy:** serce z EKG to motyw często spotykany w ochronie zdrowia, więc kreatywność jest średnia. Rozpoznawalność
  zależy od proporcji pinezki. Na ciemnym tle zieleń ma tylko 3,2:1 (dla grafiki wystarcza, WCAG 1.4.11).

### B · Serce hashtagu (`koncepcja_B*.svg`)
Zielony kafel jak ikona aplikacji. W nim biały znak „#”, a w jego środkowym polu serce, czyli „serce akcji jest
w hasztagu”. W logotypie „AED” stoi na zielonej plakietce, która przypomina tabliczkę z oznakowania defibrylatorów,
a jednocześnie wyróżnia skrót. Ta koncepcja najbardziej pasuje do mediów społecznościowych i dobrze sprawdza się jako awatar.
- **Plusy:** najbardziej „kampanijna” i nowoczesna, ma największy potencjał promocyjny (awatar, nakładka na zdjęcia,
  naklejki, emoji). Sygnet jest wyrazisty w 48 px, a plakietka „AED” jest nośna.
- **Minusy:** bez podpisu słabiej mówi „defibrylator”, bo „#” to raczej social media niż ratownictwo. W 24 px serce
  w środku robi się bardzo małe. Odrzuciłem wariant z linią EKG wewnątrz „#”, bo w 48 px czytał się jak litera „N”.

### C · Puls „tu jestem” (`koncepcja_C*.svg`)
Serce z błyskawicą (nawiązanie do symbolu AED wg ILCOR/ISO 7010 E010) w centrum rozchodzących się fal, jak pulsująca
kropka „tu jesteś” w aplikacjach mapowych. Fale znaczą trzy rzeczy naraz: bicie serca, sygnał lokalizacji i dane
„nadawane” do otwartego portalu. Logotyp ma kontrast wag (Medium „#TuBije” + ExtraBold „AED”) i podpis
„DEFIBRYLATORY NA MAPIE · OTWARTE DANE”.
- **Plusy:** najmocniej i najszybciej kojarzy się z AED (błyskawica w sercu), wygląda nowocześnie i „cyfrowo”,
  a podpis od razu tłumaczy akcję.
- **Minusy:** jest zbyt blisko oficjalnego znaku bezpieczeństwa, więc może się z nim mylić na kapsule AED.
  Ma najwięcej elementów (3 pierścienie), więc w 24 px fale znikają. Wersja z podpisem jest szeroka.

### Rekomendacja: **A (Serce-pinezka)**, z opcjonalnym zapożyczeniem z B
A najlepiej spełnia kryteria jury „proste i zrozumiałe” oraz „zgodne z tematyką”, a przede wszystkim spina cały
system: ten sam kształt jest logo, markerem AED na mapie, zieloną pinezką Partnera, odznaką i naklejką. Do finalizacji
proponuję rozważyć hybrydę **A + plakietka „AED” z B**, bo dodałaby logotypowi A charakteru kampanii. B jest mocną
alternatywą, jeśli zespół stawia na promocję w social mediach. C odradzam ze względu na podobieństwo do znaku ISO 7010.

## Paleta

| Rola | Nazwa | HEX | RGB | CMYK* | Odniesienie druk |
|---|---|---|---|---|---|
| Główny | **Zieleń AED** | `#00843D` | 0 132 61 | 100 0 54 48 | Pantone 348 C (≈ RAL 6032) |
| Tekst / tło ciemne | **Granat nocny** | `#0B2545` | 11 37 69 | 84 46 0 73 | ≈ Pantone 289 C |
| Akcent na ciemnym (tylko ekran) | **Zieleń sygnałowa** | `#5FD38D` | 95 211 141 | 55 0 33 17 | – (kolor ekranowy) |
| Tło jasne | **Mięta** | `#E8F5EE` | 232 245 238 | 5 0 3 4 | – |
| Funkcyjny alarm (112, błędy w UI), **nie w znaku** | **Czerwień pulsu** | `#D90429` | 217 4 41 | 0 98 81 15 | ≈ Pantone 199 C / 185 C |
| Neutralny | Biel | `#FFFFFF` | 255 255 255 | 0 0 0 0 | – |
| Neutralny | Szary tekst | `#5B6770` | 91 103 112 | 19 8 0 56 | – |
| Neutralny (na ciemnym) | Szary jasny | `#C5D3E0` | 197 211 224 | 12 6 0 12 | – |
| Neutralny | Linia | `#C9D6CF` | 201 214 207 | 6 0 3 16 | – |

\* CMYK przeliczony matematycznie z sRGB, jest tylko orientacyjny. W Sprincie 2 trzeba go zweryfikować profilem
FOGRA39 (ISO Coated v2) albo użyć wzorników Pantone.

**Dlaczego `#00843D`.** Uniwersalny znak AED ILCOR (zbudowany wg ISO 7010, symbol E010) określa zieleń jako
**RAL 6032 „Signal green”**, równoważną **Pantone 348 C** (oraz DIN 6164 1.7:6.5:4). Oficjalnej wartości sRGB
nie ma. Źródła podają przybliżenia RAL 6032 jako `#237F52` (Wikipedia, ISO 3864) albo `#0F8558` (W3Schools,
„nieoficjalne”). Wybrałem `#00843D`, czyli sRGB publikowane dla Pantone 348 C: daje to identyfikowalne odniesienie
do druku i kontrast 4,81:1 z bielą. Poprzednia księga nazywała `#006B3F` „ISO AED” i to było błędne: jest to
ciemniejszy, nieznormalizowany odcień. W znaku nie kopiujemy samego symbolu E010 (piktogram bezpieczeństwa ma
swoje zasady stosowania), a jedynie nawiązujemy do jego zieleni.
Źródła: [ILCOR – AED sign letter](https://ilcor.org/data/AED_Sign_letter_ILCOR_AED_sign_final_V20101102.pdf),
[Resus AU – Universal ILCOR AED Sign](https://resus.org.au/?p=4200), [Wikipedia – ISO 7010](https://en.wikipedia.org/wiki/ISO_7010),
[Wikipedia – ISO 3864](https://en.wikipedia.org/wiki/ISO_3864), [W3Schools – RAL](https://www.w3schools.com/Colors/colors_ral.asp).

### Kontrasty (WCAG 2.2, policzone wzorem względnej luminancji)

| Tekst / element | Tło | Kontrast | Gdzie | Wynik |
|---|---|---|---|---|
| Granat `#0B2545` | Biel | **15,39:1** | „#TuBije”, odznaka jasna | AA/AAA ✓ |
| Zieleń AED `#00843D` | Biel | **4,81:1** | „AED”, „PARTNER” | AA ✓ (tekst normalny) |
| Biel | Zieleń AED | **4,81:1** | plakietka „AED” (B), pas naklejki | AA ✓ |
| Szary `#5B6770` | Biel | **5,80:1** | „zweryfikowane w dane.gov.pl”, podpis C | AA ✓ |
| Biel | Granat | **15,39:1** | negatyw, odznaka ciemna, pas 112 | AAA ✓ |
| Zieleń sygnałowa `#5FD38D` | Granat | **8,20:1** | „AED” w negatywie, „112” | AAA ✓ |
| Szary jasny `#C5D3E0` | Granat | **10,09:1** | teksty pomocnicze na ciemnym | AAA ✓ |
| Granat | Mięta | **13,72:1** | teksty na tle miętowym | AAA ✓ |
| Szary | Mięta | **5,17:1** | teksty pomocnicze na mięcie | AA ✓ |
| Czerwień `#D90429` | Biel | **5,25:1** | tylko UI (112, błędy) | AA ✓ |
| Zieleń AED | Mięta | 4,29:1 | **tylko tekst duży** (≥ 24 px lub 18,66 px bold) | AA-large ✓ |
| Sygnet zielony | Granat | 3,20:1 | grafika (WCAG 1.4.11 ≥ 3:1) | ✓ |
| Obramowanie odznaki `#C9D6CF` | Biel | dekoracyjne | – | n/d |
| ✗ Czerwień | Zieleń AED | **1,09:1** | **zakaz**: czerwień nigdy bezpośrednio na zieleni (np. czerwony EKG na zielonym sygnecie) | ✗ |
| ✗ Czerwień | Granat | 2,93:1 | zakaz dla tekstu | ✗ |

## Hasła kampanii (8–10 propozycji)

| # | Hasło główne | Możliwe rozwinięcie (podtytuł) |
|---|---|---|
| 1 | **Pokaż, gdzie bije pomoc.** | Udostępnij dane swojego AED w dane.gov.pl. |
| 2 | **Twój AED na mapie. Czyjeś serce w rytmie.** | Dodaj defibrylator do otwartych danych. |
| 3 | **AED pod kluczem nikogo nie uratuje.** | Pokaż, gdzie jest i kiedy jest dostępny. |
| 4 | Każda minuta bije. | Defibrylator na mapie to minuty dla życia. |
| 5 | Jeden wpis. Uratowane minuty. | Dodaj swój AED do dane.gov.pl. |
| 6 | Dane, które przywracają rytm. | Otwarta mapa defibrylatorów AED. |
| 7 | Zaznacz AED. Zdążymy razem. | – |
| 8 | Bądź tam, gdzie bije serce. | Twój defibrylator, wspólna mapa. |
| 9 | Nie wiesz, gdzie AED? Teraz już wiesz. | (wersja dla mieszkańców / aplikacji) |
| 10 | Tu bije serce Twojej okolicy. | (wersja lokalna dla JST) |

**TOP 3:**
1. **„Pokaż, gdzie bije pomoc.”** Domyka grę słów z nazwą (Tu-**bije**), jest krótkie (4 słowa) i mówi wprost do
   dysponenta, czego chcemy („pokaż” = opublikuj dane). Nie brzmi urzędowo, mieści się na banerze i w poście.
2. **„Twój AED na mapie. Czyjeś serce w rytmie.”** Paralela przyczyna → skutek pokazuje wartość danych w jednym
   zdaniu i ma wyraźny rytm, który łatwo zapamiętać. Dobre na plakaty i spoty.
3. **„AED pod kluczem nikogo nie uratuje.”** Najmocniejsze emocjonalnie, nawiązuje do historii z treści zadania
   (zamknięte defibrylatory). Uzasadnia, po co zbieramy dane o dostępności. Nadaje się do PR i mediów,
   na odznakę zbyt negatywne.

## Teksty do odznaki Partnera

Propozycja człowieka: „Firma przyjazna klientowi i nie tylko”. Problemy: „i nie tylko” jest niedopowiedziane i nie
mówi o AED, a „przyjazna klientowi” to frazes. Poprawiona idea w wariancie 1:

| # | Krótka (odznaka 200×60, zamiast linii „PARTNER”; 88×31 → tylko „PARTNER”) | Długa (stopka www, obok odznaki) |
|---|---|---|
| 1 | **Przyjaźni klientom. I ich sercom.** | Jesteśmy przyjaźni klientom – i ich sercom. Nasz defibrylator AED jest na publicznej mapie, a jego dane są zweryfikowane w dane.gov.pl. |
| 2 | **Nasz AED jest na mapie** | Mamy defibrylator AED dostępny dla każdego. Jego lokalizację i godziny dostępności znajdziesz w otwartych danych dane.gov.pl. |
| 3 | **Firma z sercem na mapie** | Firma z sercem – na mapie. Udostępniamy dane o naszym AED w dane.gov.pl, żeby pomoc zdążyła na czas. |
| 4 | Tu pomoc jest blisko | Tu pomoc jest blisko: nasz AED może użyć każdy, a jego dane są otwarte i aktualne w dane.gov.pl. |
| 5 | Pokazujemy, gdzie bije pomoc | Pokazujemy, gdzie bije pomoc – jesteśmy Partnerem akcji #TuBijeAED i publikujemy dane o naszym defibrylatorze. |

**TOP teksty odznaki:** 1 (poprawiona wersja pomysłu człowieka: ciepła, z puentą, nadal o firmie), 2 (najbardziej
konkretna i informacyjna, dobra dla urzędów i dworców), 3 (najkrótsza i marketingowa, dla firm).
W odznace 200×60 krótka wersja może mieć maks. ok. 28 znaków przy 9 px. Tekst alternatywny odznaki:
`alt="Partner #TuBijeAED – dane o defibrylatorze zweryfikowane w dane.gov.pl"`, link do strony weryfikacji Partnera.

## Odznaka i naklejka

- `odznaka_{A,B,C}_{jasna,ciemna}_{mala,pelna}.svg`: **mała 88×31** (sygnet + znaczek „zweryfikowane”, „PARTNER”,
  „#TuBijeAED”) i **pełna 200×60** („PARTNER”, „#TuBijeAED”, „✓ zweryfikowane w dane.gov.pl”). Pełny dopisek
  „zweryfikowane w dane.gov.pl” jest w wersji 200×60. W 88×31 zastępuje go zielone kółko z ptaszkiem, a pełna
  treść jest w `alt`/`title`. Na ekranach retina warto wstawiać grafikę w rozmiarze 2× (176×62 / 400×120).
- `naklejka_{A,B,C}.svg`: **100×140 mm**. Nagłówek ze znakiem, pas „Ten defibrylator jest na mapie”, miejsce na QR
  (pole 38 mm, sam kod min. 30×30 mm) z wezwaniem „Zeskanuj: sprawdź godziny dostępności, zgłoś usterkę lub zmianę
  danych”, ID AED i pas „Nagłe zatrzymanie krążenia? Dzwoń 112 i użyj AED”. Najmniejszy tekst ma ok. 2,6 mm
  wysokości kroju (do korekty w Sprincie 2 po wyborze).
- Bez nazwy, godła i logo Ministerstwa Cyfryzacji oraz bez logo dane.gov.pl. Adres „dane.gov.pl” występuje tylko
  jako zwykły tekst.

## Pliki

```
koncepcja_{A,B,C}.svg                 logo poziome, jasne tło (pole ochronne 40 px wliczone)
koncepcja_{A,B,C}_negatyw.svg         logo poziome na granacie
koncepcja_{A,B,C}_sygnet.svg          sam sygnet 100×100
koncepcja_{A,B,C}_sygnet_negatyw.svg  sygnet na granacie
odznaka_{A,B,C}_{jasna,ciemna}_{mala,pelna}.svg
naklejka_{A,B,C}.svg
plansza_koncepcji.png                 plansza porównawcza
generuj_koncepcje.py                  generator (wymaga fonttools)
fonts/Poppins-*.ttf, fonts/OFL_Poppins.txt
```
