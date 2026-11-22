/* #TuBijeAED – wspólne funkcje interfejsu. Właściciel: Frontend.
   ZASADA BEZPIECZEŃSTWA: dane z API trafiają do DOM wyłącznie przez textContent / createTextNode / atrybuty
   ustawiane przez setAttribute (z walidacją adresów). Nigdy innerHTML z danymi. */

/* ---------- Budowanie DOM ---------- */
const DOZWOLONE_SCHEMATY = /^(https?:|tel:|mailto:|geo:|\/|#|\.\/|\.\.\/|\?)/i;

/** Bezpieczny adres: tylko http(s), tel, mailto, geo, ścieżki względne. Inaczej "#". */
export function bezpiecznyAdres(u) {
  const s = String(u ?? "").trim();
  return DOZWOLONE_SCHEMATY.test(s) ? s : "#";
}

/** el("a", {class:"x", href:"/y", on:{click: fn}}, "tekst", node, ...) */
export function el(tag, atrybuty = {}, ...dzieci) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(atrybuty || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k === "on") for (const [z, f] of Object.entries(v)) n.addEventListener(z, f);
    else if (k === "href" || k === "src" || k === "action") n.setAttribute(k, bezpiecznyAdres(v));
    else if (k === "dataset") Object.assign(n.dataset, v);
    else if (v === true) n.setAttribute(k, "");
    else n.setAttribute(k, String(v));
  }
  dolacz(n, dzieci);
  return n;
}

function dolacz(rodzic, dzieci) {
  for (const d of dzieci.flat(Infinity)) {
    if (d === null || d === undefined || d === false) continue;
    rodzic.append(d instanceof Node ? d : document.createTextNode(String(d)));
  }
}

export function wyczysc(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
export function wstaw(n, ...dzieci) { wyczysc(n); dolacz(n, dzieci); return n; }

export const $ = (s, k = document) => k.querySelector(s);
export const $$ = (s, k = document) => [...k.querySelectorAll(s)];

export function param(nazwa) { return new URLSearchParams(location.search).get(nazwa); }

export function tytulStrony(tekst) { document.title = `${tekst} – #TuBijeAED (prototyp)`; }

/* ---------- Komunikaty (aria-live) ---------- */
/** Kontener `kont` powinien mieć aria-live (role=status lub alert) już w HTML. */
export function komunikat(kont, typ, tytul, ...tresc) {
  const klasy = { ok: "komunikat--ok", blad: "komunikat--blad", uwaga: "komunikat--uwaga", info: "" }[typ] ?? "";
  const symbol = { ok: "✔ ", blad: "✖ ", uwaga: "⚠ ", info: "ℹ " }[typ] ?? "";
  const n = el("div", { class: `komunikat ${klasy}` },
    tytul ? el("strong", { class: "komunikat__tytul", text: symbol + tytul }) : null,
    tresc.length ? el("div", {}, ...tresc) : null);
  wstaw(kont, n);
  return n;
}
export function ladowanie(kont, tekst = "Wczytywanie…") {
  wstaw(kont, el("p", { class: "wczytywanie" }, tekst));
}
export function pokazBlad(kont, e, tytul = "Nie udało się wczytać danych") {
  const status = e && e.status;
  const tresc = [el("p", { text: (e && e.message) || "Nieznany błąd." })];
  if (status === 404 || status === 501) {
    tresc.push(el("p", { class: "maly" }, "Dane pochodzą z API prototypu – jeśli to demo dopiero się uruchamia, spróbuj ponownie za chwilę."));
  }
  return komunikat(kont, "blad", tytul, ...tresc);
}

/* ---------- Formatowanie ---------- */
export function formatData(iso, zCzasem = false) {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const opcje = zCzasem
    ? { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }
    : { year: "numeric", month: "2-digit", day: "2-digit" };
  return d.toLocaleString("pl-PL", opcje);
}
export function formatLiczba(n) { return Number.isFinite(Number(n)) ? Number(n).toLocaleString("pl-PL") : "–"; }
export function formatOdleglosc(m) {
  if (!Number.isFinite(Number(m))) return "–";
  m = Number(m);
  if (m < 1000) return `${Math.round(m / 10) * 10 || Math.round(m)} m`;
  return `${(m / 1000).toLocaleString("pl-PL", { maximumFractionDigits: 1 })} km`;
}
export function tekst(v, domyslny = "–") { return v === null || v === undefined || v === "" ? domyslny : String(v); }

/* ---------- Słowniki etykiet (wartości z aed_schema.json i kontraktu) ---------- */
export const TYP_INSTYTUCJI = {
  local: "Jednostka samorządu terytorialnego", state: "Administracja państwowa",
  private: "Podmiot prywatny", other: "Inny podmiot", developer: "Deweloper / wydawca",
};
export const TYP_DYSPONENTA = {
  JST: "Jednostka samorządu terytorialnego", Administracja_rzadowa: "Administracja rządowa",
  Podmiot_leczniczy: "Podmiot leczniczy", Sluzby_mundurowe: "Służby mundurowe",
  Przedsiebiorstwo: "Przedsiębiorstwo", NGO_Inne: "Organizacja pozarządowa / inne",
};
export const DOSTEPNOSC_TYP = { "24_7": "Całodobowo (24/7)", godziny_otwarcia: "W godzinach otwarcia", ograniczona: "Ograniczona" };
export const ZABEZPIECZENIE = {
  NIE: "Bez zabezpieczenia – urządzenie dostępne od razu",
  TAK_KLUCZ: "Zamknięte na klucz", TAK_KOD: "Zamknięte na kod", TAK_OCHRONA: "Dostęp przez ochronę / obsługę",
};
export const STATUS_URZADZENIA = { sprawne: "Sprawne", w_serwisie: "W serwisie", wycofane: "Wycofane", nieznany: "Status nieznany" };
export const STATUS_WALIDACJI = { OK: "Walidacja poprawna", BLEDY: "Błędy walidacji", BRAK: "Nie walidowano", NIE_DOTYCZY: "Nie dotyczy" };
export const STATUS_PARTNERA = { AKTYWNY: "Aktywny Partner", "WYGASŁY": "Status wygasł", BRAK: "Brak statusu Partnera" };
export const CZESTOTLIWOSC = {
  daily: "codziennie", weekly: "co tydzień", monthly: "co miesiąc", quarterly: "co kwartał",
  yearly: "co rok", irregular: "nieregularnie", never: "jednorazowo",
};

export function tekstZeSlownika(slownik, klucz) { return slownik[klucz] ?? tekst(klucz); }

/* ---------- Plakietki (symbol + tekst – informacja nie tylko kolorem) ---------- */
export function plakietka(tresc, rodzaj = "neutralna", opis) {
  const symbol = { ok: "✔", blad: "✖", uwaga: "⚠", info: "ℹ", neutralna: "•" }[rodzaj] ?? "•";
  return el("span", { class: `plakietka plakietka--${rodzaj}`, title: opis },
    el("span", { "aria-hidden": "true", text: symbol }), el("span", {}, tresc));
}
export function plakietkaWalidacji(status) {
  const rodzaj = { OK: "ok", BLEDY: "blad", BRAK: "uwaga", NIE_DOTYCZY: "neutralna" }[status] ?? "neutralna";
  return plakietka(tekstZeSlownika(STATUS_WALIDACJI, status), rodzaj);
}
export function plakietkaPartnera(status) {
  const rodzaj = { AKTYWNY: "ok", "WYGASŁY": "uwaga", BRAK: "neutralna" }[status] ?? "neutralna";
  return plakietka(tekstZeSlownika(STATUS_PARTNERA, status), rodzaj);
}

/** Dostępność „teraz” (true/false/null z API mapy). */
export function plakietkaDostepnosci(v) {
  if (v === true) return plakietka("Dostępny teraz", "ok");
  if (v === false) return plakietka("Zamknięty o tej porze", "blad");
  return plakietka("Dostępność nieznana", "uwaga");
}

/* ---------- Tabele ---------- */
/** zbudujTabele({opis, kolumny:[{naglowek, wartosc(w)->string|Node, klasa, naglowekWiersza}], wiersze, etykieta, klasa}) */
export function zbudujTabele({ opis, kolumny, wiersze, klasa = "", pusty = "Brak danych." }) {
  if (!wiersze.length) return el("p", { class: "tekst-drugorzedny" }, pusty);
  const thead = el("thead", {}, el("tr", {}, kolumny.map((k) => el("th", { scope: "col", class: k.klasa }, k.naglowek))));
  const tbody = el("tbody", {}, wiersze.map((w, i) => el("tr", {},
    kolumny.map((k) => {
      const wart = k.wartosc(w, i);
      return k.naglowekWiersza
        ? el("th", { scope: "row", class: k.klasa }, wart)
        : el("td", { class: k.klasa }, wart);
    }))));
  const tab = el("table", { class: klasa }, el("caption", {}, opis), thead, tbody);
  return el("div", { class: "tabela-opakowanie", role: "region", "aria-label": `Tabela: ${opis}`, tabindex: "0" }, tab);
}

/* ---------- Raport walidacji (admin + asystent) ---------- */
export function raportWalidacji(raport, { maksWierszy = 300 } = {}) {
  const r = raport || {};
  const bledy = Array.isArray(r.bledy) ? r.bledy : [];
  const ostrz = Array.isArray(r.ostrzezenia) ? r.ostrzezenia : [];
  const wez = (t) => t.slice(0, maksWierszy);
  const kol = [
    { naglowek: "Wiersz", wartosc: (b) => tekst(b.wiersz), klasa: "liczba" },
    { naglowek: "Pole", wartosc: (b) => el("code", {}, tekst(b.pole)) },
    { naglowek: "Komunikat", wartosc: (b) => tekst(b.komunikat) },
  ];
  const kont = el("div", { class: "raport" });
  kont.append(el("dl", { class: "statystyki" },
    stat("Wiersze poprawne", r.poprawne_wiersze),
    stat("Wiersze z błędami", r.bledne_wiersze),
    stat("Ostrzeżenia", ostrz.length)));
  if (bledy.length) {
    kont.append(el("h4", {}, `Błędy (${bledy.length})`));
    kont.append(zbudujTabele({ opis: "Błędy walidacji – wiersz, pole, komunikat", kolumny: kol, wiersze: wez(bledy), klasa: "tabela-raport" }));
    if (bledy.length > maksWierszy) kont.append(el("p", { class: "maly tekst-drugorzedny" }, `Pokazano pierwsze ${maksWierszy} z ${bledy.length} błędów.`));
  } else {
    kont.append(el("p", {}, plakietka("Brak błędów walidacji", "ok")));
  }
  if (ostrz.length) {
    kont.append(el("h4", {}, `Ostrzeżenia (${ostrz.length}) – nie blokują publikacji`));
    kont.append(zbudujTabele({ opis: "Ostrzeżenia walidacji – wiersz, pole, komunikat", kolumny: kol, wiersze: wez(ostrz), klasa: "tabela-raport" }));
    if (ostrz.length > maksWierszy) kont.append(el("p", { class: "maly tekst-drugorzedny" }, `Pokazano pierwsze ${maksWierszy} z ${ostrz.length} ostrzeżeń.`));
  }
  return kont;
}
function stat(nazwa, wart) {
  return el("div", { class: "statystyka" }, el("dt", {}, nazwa), el("dd", {}, formatLiczba(wart ?? 0)));
}
export { stat as statystyka };

/* ---------- Paginacja ---------- */
/** paginacja({strona, naStrone, razem, naZmiane(nowaStrona)}) -> Node */
export function paginacja({ strona, naStrone, razem, naZmiane, nazwa = "Paginacja" }) {
  const stron = Math.max(1, Math.ceil(razem / naStrone));
  const od = razem ? (strona - 1) * naStrone + 1 : 0;
  const do_ = Math.min(razem, strona * naStrone);
  const poprz = el("button", { type: "button", class: "przycisk przycisk--drugi przycisk--maly", on: { click: () => naZmiane(strona - 1) } }, "‹ Poprzednia");
  const nast = el("button", { type: "button", class: "przycisk przycisk--drugi przycisk--maly", on: { click: () => naZmiane(strona + 1) } }, "Następna ›");
  if (strona <= 1) poprz.disabled = true;
  if (strona >= stron) nast.disabled = true;
  return el("nav", { class: "paginacja", "aria-label": nazwa },
    poprz,
    el("span", { class: "paginacja__info" }, `Wyniki ${od}–${do_} z ${formatLiczba(razem)} (strona ${strona} z ${stron})`),
    nast);
}

/* ---------- Schowek ---------- */
export async function kopiuj(tekstDoSkopiowania, kontStatus, polePomocnicze) {
  let ok = false;
  try {
    await navigator.clipboard.writeText(tekstDoSkopiowania);
    ok = true;
  } catch {
    try {
      if (polePomocnicze) { polePomocnicze.select(); ok = document.execCommand("copy"); }
    } catch { ok = false; }
  }
  if (kontStatus) {
    kontStatus.textContent = ok ? "Skopiowano do schowka." : "Nie udało się skopiować – zaznacz kod i skopiuj ręcznie (Ctrl+C).";
  }
  return ok;
}

/* ---------- Pobieranie pliku z Blob ---------- */
export function zapiszBlob(blob, nazwaPliku) {
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: nazwaPliku });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/* ---------- Rekordy AED ---------- */
export function adresRekordu(r) {
  const ulica = [r.ulica, r.nr_budynku].filter(Boolean).join(" ");
  return [ulica, [r.kod_pocztowy, r.miejscowosc].filter(Boolean).join(" ")].filter(Boolean).join(", ");
}
export function wspolrzedne(r) {
  const lat = Number(r.szerokosc_geo ?? r.lat);
  const lon = Number(r.dlugosc_geo ?? r.lon);
  return Number.isFinite(lat) && Number.isFinite(lon) ? [lat, lon] : null;
}
export function nazwaDostawcy(r) { return r.nazwa_dostawcy || r.dostawca || ""; }

export function linkInstytucji(id, nazwa) {
  return id !== undefined && id !== null && id !== ""
    ? el("a", { href: `/instytucja.html?id=${encodeURIComponent(id)}` }, nazwa)
    : document.createTextNode(nazwa);
}

/** Pole <select> z opcjami (tekst-wartosc). */
export function opcje(select, pozycje, pierwsza) {
  wyczysc(select);
  if (pierwsza) select.append(el("option", { value: "" }, pierwsza));
  for (const [wartosc, etykieta] of pozycje) select.append(el("option", { value: wartosc }, etykieta));
}

/** Przenosi fokus na element (np. nagłówek wyniku), by czytniki ekranu ogłosiły zmianę. */
export function fokus(n) {
  if (!n) return;
  if (!n.hasAttribute("tabindex")) n.setAttribute("tabindex", "-1");
  n.focus({ preventScroll: false });
}
