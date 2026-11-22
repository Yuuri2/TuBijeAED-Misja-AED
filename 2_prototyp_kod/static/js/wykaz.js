/* wykaz-aed.html – wykaz zbiorczy AED: stan, pliki, dostawcy, tabela z filtrem, pominięte zasoby. */
import { pobierz, API_14, lista, plaski } from "./api.js";
import {
  $, el, wstaw, ladowanie, pokazBlad, komunikat, formatData, formatLiczba, tekst, statystyka,
  zbudujTabele, paginacja, opcje, linkInstytucji, plakietka, adresRekordu, tytulStrony,
  DOSTEPNOSC_TYP, STATUS_URZADZENIA, tekstZeSlownika,
} from "./ui.js";

const NA_STRONE = 20;
let wszystkie = [];
let strona = 1;

const nazwaInst = (i) => (typeof i === "string" ? i : (i && (i.title || i.nazwa || i.name)) || "–");
const idInst = (i, obiekt) => (i && typeof i === "object" ? i.id : undefined) ?? obiekt?.instytucja_id;

async function start() {
  const stan = $("#wykaz-stan");
  ladowanie(stan, "Wczytywanie wykazu…");
  let wykaz;
  try {
    const odp = await pobierz(`${API_14}/aed-aggregated`);
    wykaz = plaski(odp.data ?? odp);
  } catch (e) {
    if (e.status === 404) {
      komunikat(stan, "uwaga", "Wykaz zbiorczy AED nie został jeszcze zbudowany",
        el("p", {}, "Wykaz powstaje automatycznie po opublikowaniu pierwszego poprawnego zasobu AED. Administrator może też uruchomić scalenie ręcznie w ",
          el("a", { href: "/admin/index.html" }, "panelu"), "."));
    } else pokazBlad(stan, e, "Nie udało się wczytać wykazu");
    ukryjSekcje();
    return;
  }
  renderStan(stan, wykaz);
  renderDostawcy(wykaz);
  renderPominiete(wykaz);
  await wczytajRekordy();
}

function ukryjSekcje() {
  for (const id of ["sekcja-dostawcy", "sekcja-rekordy", "sekcja-pominiete"]) { const s = document.getElementById(id); if (s) s.hidden = true; }
}

function renderStan(kont, w) {
  const pliki = w.pliki || {};
  const przyciski = [
    ["xlsx", "Pobierz XLSX", "Excel (.xlsx)"],
    ["csv", "Pobierz CSV", "CSV UTF-8"],
    ["geojson", "Pobierz GeoJSON", "GeoJSON"],
  ].filter(([k]) => pliki[k]).map(([k, t, opis]) =>
    el("a", { class: "przycisk przycisk--drugi", href: pliki[k], download: "" }, t, el("span", { class: "tylko-czytniki" }, ` – ${opis}`)));
  wstaw(kont,
    el("dl", { class: "statystyki" },
      statystyka("Rekordów w wykazie", w.liczba_rekordow),
      statystyka("Dostawców", w.liczba_dostawcow),
      el("div", { class: "statystyka" }, el("dt", {}, "Data scalenia"), el("dd", {}, formatData(w.utworzono, true)))),
    przyciski.length
      ? el("div", { class: "rzad", role: "group", "aria-label": "Pobieranie wykazu" }, przyciski)
      : el("p", { class: "tekst-drugorzedny" }, "Pliki wykazu nie są jeszcze dostępne do pobrania."));
}

function renderDostawcy(w) {
  const kont = $("#dostawcy-lista");
  const ul = Array.isArray(w.uwzglednione) ? w.uwzglednione : [];
  if (!ul.length) { wstaw(kont, el("p", {}, "Żaden dostawca nie jest jeszcze uwzględniony w wykazie.")); return; }
  wstaw(kont, zbudujTabele({
    opis: "Dostawcy uwzględnieni w wykazie zbiorczym",
    kolumny: [
      { naglowek: "Dostawca (odpowiada za dane)", naglowekWiersza: true, wartosc: (u) => linkInstytucji(idInst(u.instytucja, u), nazwaInst(u.instytucja)) },
      { naglowek: "Rekordy", klasa: "liczba", wartosc: (u) => formatLiczba(u.rekordy) },
      { naglowek: "Zbiór źródłowy", wartosc: (u) => odnosnikZbioru(u) },
    ],
    wiersze: ul,
  }));
}

function odnosnikZbioru(u) {
  if (u.zbior_id) return el("a", { href: `/zbior.html?id=${encodeURIComponent(u.zbior_id)}` }, "Otwórz zbiór dostawcy");
  if (u.zasob_id) return el("a", { href: `/zbior.html?zasob=${encodeURIComponent(u.zasob_id)}` }, `Zbiór (zasób nr ${u.zasob_id})`);
  return "–";
}

function renderPominiete(w) {
  const kont = $("#pominiete-lista");
  const p = Array.isArray(w.pominiete) ? w.pominiete : [];
  if (!p.length) { wstaw(kont, el("p", {}, plakietka("Żaden zasób nie został pominięty", "ok"))); return; }
  wstaw(kont,
    el("p", {}, "Poniższe zasoby oznaczono jako wykaz AED, ale nie weszły do wykazu. Dostawca widzi ten powód w swoim panelu i może poprawić dane."),
    zbudujTabele({
      opis: "Pominięte zasoby wykazu AED z powodem",
      kolumny: [
        { naglowek: "Dostawca", naglowekWiersza: true, wartosc: (x) => linkInstytucji(idInst(x.instytucja, x), nazwaInst(x.instytucja)) },
        { naglowek: "Zasób", wartosc: (x) => (x.zasob_id ? `nr ${x.zasob_id}` : "–") },
        { naglowek: "Powód pominięcia", wartosc: (x) => tekst(x.powod) },
      ],
      wiersze: p,
    }));
}

async function wczytajRekordy() {
  const kont = $("#tabela-wynik");
  ladowanie(kont, "Wczytywanie rekordów…");
  try {
    const odp = await pobierz(`${API_14}/aed-aggregated/rekordy`);
    wszystkie = lista(odp).map(plaski);
  } catch (e) { pokazBlad(kont, e, "Nie udało się wczytać rekordów wykazu"); return; }
  const woj = [...new Set(wszystkie.map((r) => r.wojewodztwo).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pl"));
  opcje($("#filtr-woj"), woj.map((x) => [x, x]), "Wszystkie województwa");
  const dost = new Map();
  for (const r of wszystkie) { const k = String(r.instytucja_id ?? r.nazwa_dostawcy ?? ""); if (k) dost.set(k, r.nazwa_dostawcy || k); }
  opcje($("#filtr-dost"), [...dost.entries()].sort((a, b) => a[1].localeCompare(b[1], "pl")), "Wszyscy dostawcy");
  strona = 1;
  rysujTabele();
}

function przefiltruj() {
  const q = $("#filtr-tekst").value.trim().toLocaleLowerCase("pl");
  const woj = $("#filtr-woj").value;
  const dost = $("#filtr-dost").value;
  return wszystkie.filter((r) => {
    if (woj && r.wojewodztwo !== woj) return false;
    if (dost && String(r.instytucja_id ?? r.nazwa_dostawcy ?? "") !== dost) return false;
    if (q) {
      const s = [r.miejscowosc, r.ulica, r.nr_budynku, r.nazwa_dysponenta, r.nazwa_dostawcy, r.lokalizacja_szczegolowa, r.gmina, r.powiat]
        .filter(Boolean).join(" ").toLocaleLowerCase("pl");
      if (!s.includes(q)) return false;
    }
    return true;
  });
}

function rysujTabele(przeniesFokus = false) {
  const kont = $("#tabela-wynik");
  const wyn = przefiltruj();
  const stron = Math.max(1, Math.ceil(wyn.length / NA_STRONE));
  if (strona > stron) strona = stron;
  const okno = wyn.slice((strona - 1) * NA_STRONE, strona * NA_STRONE);
  $("#tabela-licznik").textContent = wyn.length === wszystkie.length
    ? `Rekordów w wykazie: ${formatLiczba(wszystkie.length)}.`
    : `Znaleziono ${formatLiczba(wyn.length)} z ${formatLiczba(wszystkie.length)} rekordów.`;
  const tabela = zbudujTabele({
    opis: "Rekordy wykazu zbiorczego AED (wybrane kolumny – komplet w plikach do pobrania)",
    pusty: "Brak rekordów spełniających kryteria. Zmień filtry.",
    kolumny: [
      { naglowek: "Miejscowość", naglowekWiersza: true, wartosc: (r) => tekst(r.miejscowosc) },
      { naglowek: "Adres i miejsce urządzenia", wartosc: (r) => el("span", {}, adresRekordu(r) || "–", r.lokalizacja_szczegolowa ? el("br") : null,
        r.lokalizacja_szczegolowa ? el("span", { class: "maly tekst-drugorzedny" }, r.lokalizacja_szczegolowa) : null) },
      { naglowek: "Dysponent urządzenia", wartosc: (r) => tekst(r.nazwa_dysponenta) },
      { naglowek: "Dostawca danych", wartosc: (r) => linkInstytucji(r.instytucja_id, tekst(r.nazwa_dostawcy)) },
      { naglowek: "Dostępność", wartosc: (r) => (r.dostepnosc_typ === "24_7" ? "Całodobowo (24/7)" : [tekstZeSlownika(DOSTEPNOSC_TYP, r.dostepnosc_typ), r.godziny_dostepnosci].filter(Boolean).join(": ")) },
      { naglowek: "Status", wartosc: (r) => tekstZeSlownika(STATUS_URZADZENIA, r.status_urzadzenia ?? "nieznany") },
      { naglowek: "Aktualizacja", wartosc: (r) => formatData(r.data_aktualizacji) },
    ],
    wiersze: okno,
  });
  wstaw(kont, tabela, wyn.length > NA_STRONE
    ? paginacja({
      strona, naStrone: NA_STRONE, razem: wyn.length, nazwa: "Paginacja tabeli wykazu",
      naZmiane: (n) => { strona = n; rysujTabele(true); },
    }) : null);
  if (przeniesFokus) { const t = $("#tabela-wynik .tabela-opakowanie"); if (t) t.focus(); }
}

function init() {
  tytulStrony("Wykaz defibrylatorów AED – wykaz zbiorczy");
  $("#formularz-filtr").addEventListener("submit", (e) => { e.preventDefault(); strona = 1; rysujTabele(); });
  for (const id of ["#filtr-woj", "#filtr-dost"]) $(id).addEventListener("change", () => { strona = 1; rysujTabele(); });
  $("#filtr-tekst").addEventListener("input", () => { strona = 1; rysujTabele(); });
  $("#filtr-wyczysc").addEventListener("click", () => {
    $("#filtr-tekst").value = ""; $("#filtr-woj").value = ""; $("#filtr-dost").value = ""; strona = 1; rysujTabele();
  });
  start();
}
init();
