/* zbiory.html – lista zbiorów (GET /api/1.4/datasets) z filtrem: tytuł, instytucja, tylko wykazy. */
import { pobierz, API_14, lista, plaski, liczbaWszystkich } from "./api.js";
import { $, el, wstaw, ladowanie, pokazBlad, komunikat, param, formatData, tekst, plakietka, opcje, paginacja, linkInstytucji, formatLiczba, TYP_INSTYTUCJI } from "./ui.js";

const NA_STRONE = 10;
let strona = 1;

async function wczytajInstytucje() {
  try {
    const odp = await pobierz(`${API_14}/institutions`, { per_page: 100 });
    const poz = lista(odp).map(plaski).map((i) => [String(i.id), i.title || i.nazwa || `Instytucja ${i.id}`])
      .sort((a, b) => a[1].localeCompare(b[1], "pl"));
    opcje($("#f-instytucja"), poz, "Wszystkie instytucje");
    const w = param("instytucja");
    if (w) $("#f-instytucja").value = w;
  } catch { /* filtr instytucji jest opcjonalny – lista zbiorów działa bez niego */ }
}

function karta(z) {
  const inst = z.institution || {};
  return el("li", {},
    el("h3", {}, el("a", { href: `/zbior.html?id=${encodeURIComponent(z.id)}` }, tekst(z.title, `Zbiór ${z.id}`))),
    z.is_aggregated_list ? el("p", {}, plakietka("Wykaz zbiorczy AED", "ok")) : null,
    z.notes ? el("p", { class: "tekst-drugorzedny" }, String(z.notes).slice(0, 220) + (String(z.notes).length > 220 ? "…" : "")) : null,
    el("p", { class: "maly" },
      "Dostawca: ", inst.id !== undefined ? linkInstytucji(inst.id, tekst(inst.title)) : tekst(inst.title),
      inst.type ? ` (${TYP_INSTYTUCJI[inst.type] || inst.type})` : "",
      " · Zasoby: ", formatLiczba(z.resources_count ?? 0),
      " · Zmodyfikowano: ", formatData(z.modified),
      z.license ? ` · Licencja: ${z.license}` : ""));
}

async function szukaj(przeniesFokus) {
  const wynik = $("#zbiory-wynik");
  ladowanie(wynik);
  const parametry = {
    q: $("#f-q").value.trim(), instytucja: $("#f-instytucja").value,
    wykaz: $("#f-wykaz").checked ? "AED" : "", page: strona, per_page: NA_STRONE,
  };
  let odp;
  try { odp = await pobierz(`${API_14}/datasets`, parametry); }
  catch (e) { pokazBlad(wynik, e, "Nie udało się wczytać listy zbiorów"); return; }
  const zbiory = lista(odp).map(plaski);
  const razem = liczbaWszystkich(odp);
  const jestNastepna = odp && odp.links && odp.links.next ? true : zbiory.length === NA_STRONE;
  $("#zbiory-licznik").textContent = zbiory.length
    ? `Znaleziono zbiorów: ${razem ?? (strona - 1) * NA_STRONE + zbiory.length}${razem === null && jestNastepna ? "+" : ""}.`
    : "Nie znaleziono zbiorów spełniających kryteria.";
  if (!zbiory.length) { wstaw(wynik, komunikat(document.createElement("div"), "info", "Brak wyników", "Zmień kryteria wyszukiwania.")); return; }
  const stronicowanie = razem !== null
    ? (razem > NA_STRONE ? paginacja({ strona, naStrone: NA_STRONE, razem, naZmiane: (n) => { strona = n; szukaj(true); }, nazwa: "Paginacja listy zbiorów" }) : null)
    : el("nav", { class: "paginacja", "aria-label": "Paginacja listy zbiorów" },
      el("button", { type: "button", class: "przycisk przycisk--drugi przycisk--maly", disabled: strona <= 1, on: { click: () => { strona--; szukaj(true); } } }, "‹ Poprzednia"),
      el("span", { class: "paginacja__info" }, `Strona ${strona}`),
      el("button", { type: "button", class: "przycisk przycisk--drugi przycisk--maly", disabled: !jestNastepna, on: { click: () => { strona++; szukaj(true); } } }, "Następna ›"));
  wstaw(wynik, el("ul", { class: "lista-czysta lista-karty" }, zbiory.map(karta)), stronicowanie);
  if (przeniesFokus) $("#zbiory-licznik").scrollIntoView({ block: "start" });
}

async function init() {
  $("#f-q").value = param("q") || "";
  $("#f-wykaz").checked = param("wykaz") === "AED";
  $("#formularz-zbiory").addEventListener("submit", (e) => { e.preventDefault(); strona = 1; szukaj(); });
  await wczytajInstytucje();
  szukaj();
}
init();
