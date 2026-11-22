# Ograniczenia rozwiązania

## Prototyp (świadome uproszczenia)
- **Okrojony portal, uruchamiany lokalnie.** Prototyp odtwarza mechanikę wykazu zbiorczego, a nie cały portal: brak wyszukiwarki pełnotekstowej, CMS, RDF/DCAT-AP, kont użytkowników. Zamiast Postgres/Elasticsearch/Celery – SQLite i przetwarzanie w procesie aplikacji (scalanie kilkudziesięciu rekordów trwa ułamek sekundy).
- **Logowanie demonstracyjne** („Zaloguj jako…”, nagłówek `X-Demo-Konto`) bez haseł – w portalu zastępuje je istniejące uwierzytelnianie (w tym login.gov.pl).
- **Jedna aktualna wersja wykazu** – poprzednie pliki są usuwane po udanym scaleniu (jak w mechanizmie DGA); historia uruchomień jest zachowana.
- **Harvester pobiera pliki synchronicznie** (w portalu – zadania Celery). Ochrona SSRF opiera się na rozwiązywaniu DNS (nie chroni przed DNS rebinding).
- **XSD 1.14 to propozycja zespołu**, nie oficjalny schemat portalu (jedyna zmiana względem 1.13: opcjonalny element `aggregatedListType`).
- **Mapa wymaga internetu** (Leaflet z CDN, kafle OpenStreetMap). Bez sieci działają lista tekstowa i „najbliższe AED”.
- Brak geokodowania adresów – położenie użytkownika z geolokalizacji, wyboru miasta demo lub kliknięcia na mapie.

## Dane
- **Istniejące zbiory gmin nie spełniają wzorca** (brak informacji o zabezpieczeniu, dostępności, położeniu w budynku; błędne współrzędne w jednym zbiorze). Wzorzec celowo pozostaje ścisły – takie zasoby są odrzucane z raportem, a dostawca musi uzupełnić dane (asystent pokazuje braki). W danych demo dla Legionowa i Przemyśla (scenariusz „gmina przekonwertowała stary zasób w asystencie i uzupełniła braki”) braki uzupełniono przykładowymi wartościami, oznaczonymi „DANE DEMO”; Krosno i Marki pokazują odrzucenie z raportem błędów.
- Zbiór AED m.st. Warszawy w dane.gov.pl wskazuje na API miasta wymagające klucza – w prototypie Warszawa występuje jako dostawca, który „jeszcze nie dołączył”.
- **Dostawca ≠ dysponent.** Gmina może publikować AED należące do szkół czy aptek; wykaz rozróżnia dostawcę (odpowiada za dane) i dysponenta (właściciel urządzenia).
- Duplikaty między dostawcami (< 25 m) są tylko **raportowane**, nie usuwane – za swoje dane odpowiada dostawca.
- Parser godzin `opening_hours` obsługuje podzbiór składni (dni, przedziały, `off`, przez północ, `24/7`); święta i inne konstrukcje → „nie wiadomo” (bez zgadywania).
- Kody TERYT/SIMC w danych przykładowych wymagają weryfikacji z rejestrem TERYT.
- Dane OpenStreetMap (ODbL) nie mogą trafić do zbioru na licencji CC – są wyłącznie warstwą „do weryfikacji”.

## Program Partner #TuBijeAED
- Odznaka „zweryfikowane w dane.gov.pl” to **propozycja dla Ministerstwa Cyfryzacji** – w prototypie nie używamy nazwy ani znaków MC/dane.gov.pl.
- Status Partnera jest liczony automatycznie z danych wykazu (aktualność ≤ 12 mies., poprawność); nie obejmuje fizycznej weryfikacji urządzenia.
