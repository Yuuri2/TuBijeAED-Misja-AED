/* asystent.html – asystent dostawcy: wzorzec, sprawdzanie pliku, konwersja pliku gminy, pakiet do publikacji.
   API: /api/asystent/* (nic nie zapisuje w portalu; dostawca publikuje na własnym koncie). */
import { pobierz, wyslij, zapytanie, API_ASYSTENT } from "./api.js";
import {
  bladPola, $, el, wstaw, ladowanie, pokazBlad, komunikat, tekst, formatLiczba, plakietka, raportWalidacji, zbudujTabele, fokus, zapiszBlob,
} from "./ui.js";

function pole(id) { return document.getElementById(id); }

function sprawdzPlik(inputId, blokId) {
  const plik = pole(inputId).files[0];
  if (!plik) {
    bladPola(inputId, "Wybierz plik do przetworzenia.");
    pole(inputId).focus();
    return null;
  }
  bladPola(inputId, "");
  return plik;
}

function naglowekWyniku(kont, id, tytul) {
  const h = el("h3", { id, tabindex: "-1" }, tytul);
  wstaw(kont, h);
  return h;
}
function blok(typ, tytul, ...tresc) { return komunikat(document.createElement("div"), typ, tytul, ...tresc); }

/* ---------- Schemat: tabela pól ---------- */
async function wczytajSchemat() {
  const kont = $("#schemat-tabela");
  ladowanie(kont, "Wczytywanie opisu pól…");
  try {
    const s = await pobierz(`${API_ASYSTENT}/schemat.json`);
    const pola = Array.isArray(s.fields) ? s.fields : [];
    wstaw(kont, zbudujTabele({
      opis: "Pola wzorca danych AED",
      kolumny: [
        { naglowek: "Pole (nazwa kolumny)", naglowekWiersza: true, wartosc: (f) => el("code", {}, f.name) },
        { naglowek: "Nazwa", wartosc: (f) => tekst(f.title) },
        { naglowek: "Wymagane", wartosc: (f) => ({ TAK: "Tak", NIE: "Nie", ZALECANE: "Zalecane", WARUNKOWO: "Warunkowo" }[f["x-wymagane"]] || tekst(f["x-wymagane"])) },
        { naglowek: "Opis i dozwolone wartości", wartosc: (f) => [f.description, f["x-warunek"] ? `Warunek: ${f["x-warunek"]}.` : "",
          f.constraints && f.constraints.enum ? `Dozwolone: ${f.constraints.enum.join(", ")}.` : ""].filter(Boolean).join(" ") },
      ],
      wiersze: pola,
    }));
  } catch (e) { pokazBlad(kont, e, "Nie udało się wczytać opisu pól"); }
}

/* ---------- Sprawdź ---------- */
async function sprawdz(e) {
  e.preventDefault();
  const plik = sprawdzPlik("s-plik");
  if (!plik) return;
  const wynik = $("#sprawdz-wynik");
  ladowanie(wynik, "Sprawdzanie pliku…");
  const b = e.submitter; b.disabled = true;
  try {
    const fd = new FormData(); fd.set("plik", plik);
    const r = await wyslij(`${API_ASYSTENT}/sprawdz`, fd);
    const h = naglowekWyniku(wynik, "sprawdz-h", "Wynik sprawdzania");
    const ok = !(r.bledne_wiersze > 0);
    wynik.append(blok(ok ? "ok" : "blad", ok ? "Plik jest zgodny ze wzorcem" : "Plik zawiera błędy – popraw je przed publikacją",
      el("p", {}, ok ? "Możesz opublikować plik na swoim koncie w portalu jako zasób wykazu AED." : "Zasób z takimi błędami zostałby odrzucony z wykazu zbiorczego. Popraw wiersze i pola z tabeli poniżej.")),
      raportWalidacji(r));
    fokus(h);
  } catch (err) { pokazBlad(wynik, err, "Nie udało się sprawdzić pliku"); }
  finally { b.disabled = false; }
}

/* ---------- Konwertuj ---------- */
async function konwertuj(e) {
  e.preventDefault();
  const plik = sprawdzPlik("k-plik");
  if (!plik) return;
  const wynik = $("#konwertuj-wynik");
  ladowanie(wynik, "Konwertowanie pliku…");
  const b = e.submitter; b.disabled = true;
  try {
    const fd = new FormData();
    fd.set("plik", plik);
    fd.set("profil", $("#k-profil").value);
    for (const [id, nazwa] of [["k-nazwa", "nazwa_dysponenta"], ["k-id", "identyfikator_dysponenta"], ["k-typ", "typ_dysponenta"], ["k-kontakt", "kontakt_dysponenta"]]) {
      const v = pole(id).value.trim(); if (v) fd.set(nazwa, v);
    }
    const r = await wyslij(`${API_ASYSTENT}/konwertuj`, fd);
    const rap = r.raport || {};
    const h = naglowekWyniku(wynik, "konwertuj-h", "Wynik konwersji");
    const braki = Array.isArray(rap.do_uzupelnienia) ? rap.do_uzupelnienia : [];
    const ostrz = Array.isArray(rap.ostrzezenia_konwersji) ? rap.ostrzezenia_konwersji : [];
    const nazwaPliku = r.nazwa_pliku || "dane_aed.csv";
    wynik.append(
      blok(rap.walidacja && rap.walidacja.bledne_wiersze > 0 ? "uwaga" : "ok", "Plik przekonwertowany do wzorca",
        el("p", {}, `Rozpoznany profil: ${tekst(rap.profil_wykryty || rap.profil)}. Liczba rekordów: ${formatLiczba(rap.liczba_rekordow)}.`),
        el("p", {}, "Uzupełnij brakujące pola w pobranym pliku, zanim opublikujesz go na swoim koncie.")),
      el("p", {}, el("button", { type: "button", class: "przycisk", on: { click: () => zapiszBlob(new Blob([r.csv || ""], { type: "text/csv;charset=utf-8" }), nazwaPliku) } },
        "Pobierz CSV we wzorcu", el("span", { class: "tylko-czytniki" }, ` (${nazwaPliku})`))),
      ostrz.length ? el("div", {}, el("h4", {}, "Uwagi konwersji"), el("ul", {}, ostrz.map((o) => el("li", {}, String(o))))) : null,
      braki.length ? zbudujTabele({
        opis: "Pola do uzupełnienia przez dostawcę",
        kolumny: [
          { naglowek: "Pole", naglowekWiersza: true, wartosc: (x) => el("code", {}, x.pole) },
          { naglowek: "Nazwa", wartosc: (x) => tekst(x.tytul) },
          { naglowek: "Wymagane", wartosc: (x) => tekst(x.wymagane) },
          { naglowek: "Puste wiersze", klasa: "liczba", wartosc: (x) => formatLiczba(x.puste_wiersze) },
          { naglowek: "Co zrobić", wartosc: (x) => tekst(x.komunikat) },
        ],
        wiersze: braki,
      }) : el("p", {}, plakietka("Nie ma pól do uzupełnienia", "ok")),
      el("h4", {}, "Walidacja po konwersji"),
      raportWalidacji(rap.walidacja || {}));
    fokus(h);
  } catch (err) { pokazBlad(wynik, err, "Nie udało się przekonwertować pliku"); }
  finally { b.disabled = false; }
}

/* ---------- Pakiet ---------- */
async function pakiet(e) {
  e.preventDefault();
  const plik = sprawdzPlik("p-plik");
  const nazwa = $("#p-nazwa");
  let ok = !!plik;
  if (!nazwa.value.trim()) { bladPola(nazwa, "Podaj nazwę dostawcy (instytucji publikującej dane)."); if (plik) nazwa.focus(); ok = false; }
  else bladPola(nazwa, "");
  const url = $("#p-url");
  if (url.value.trim() && !url.value.trim().startsWith("https://")) {
    bladPola(url, "Adres musi zaczynać się od https://."); if (ok) url.focus(); ok = false;
  } else bladPola(url, "");
  if (!ok) return;
  const wynik = $("#pakiet-wynik");
  ladowanie(wynik, "Przygotowywanie pakietu…");
  const b = e.submitter; b.disabled = true;
  try {
    const fd = new FormData();
    fd.set("plik", plik);
    fd.set("nazwa_dostawcy", nazwa.value.trim());
    if (url.value.trim()) fd.set("url_zasobu", url.value.trim());
    fd.set("licencja", $("#p-licencja").value);
    if ($("#p-profil").value) fd.set("profil", $("#p-profil").value);
    const odp = await zapytanie(`${API_ASYSTENT}/pakiet`, { metoda: "POST", cialo: fd, odpowiedz: "surowa" });
    const poprawne = odp.headers.get("X-Poprawne-Wiersze");
    const bledne = odp.headers.get("X-Bledne-Wiersze");
    const cd = odp.headers.get("Content-Disposition") || "";
    const m = /filename="?([^";]+)"?/.exec(cd);
    const nazwaZip = m ? m[1] : "pakiet_aed.zip";
    const blob = await odp.blob();
    const h = naglowekWyniku(wynik, "pakiet-h", "Pakiet gotowy");
    wynik.append(blok(Number(bledne) > 0 ? "uwaga" : "ok", "Pakiet do publikacji jest gotowy",
      el("p", {}, `Wiersze poprawne: ${poprawne ?? "–"}, z błędami: ${bledne ?? "–"}.`),
      Number(bledne) > 0 ? el("p", {}, "Część wierszy ma błędy – użyj „Sprawdź plik”, aby je zobaczyć i poprawić przed publikacją.") : null,
      el("p", {}, "ZIP zawiera: dane_aed.csv, harvester_1_14.xml i INSTRUKCJA.txt. Opublikuj pliki na własnym koncie w portalu – asystent niczego nie publikuje za Ciebie.")),
      el("p", {}, el("button", { type: "button", class: "przycisk", on: { click: () => zapiszBlob(blob, nazwaZip) } }, "Pobierz pakiet ZIP", el("span", { class: "tylko-czytniki" }, ` (${nazwaZip})`))));
    fokus(h);
  } catch (err) { pokazBlad(wynik, err, "Nie udało się przygotować pakietu"); }
  finally { b.disabled = false; }
}

$("#form-sprawdz").addEventListener("submit", sprawdz);
$("#form-konwertuj").addEventListener("submit", konwertuj);
$("#form-pakiet").addEventListener("submit", pakiet);
wczytajSchemat();
