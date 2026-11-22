/* #TuBijeAED – wspólny nagłówek, menu i stopka (wstrzykiwane; bez JS działają bloki <noscript> w każdej stronie).
   Pasek „Prototyp…” jest statycznym HTML w każdej stronie (uczciwość działa także bez JS). Właściciel: Frontend. */
import { el } from "./ui.js";

const POZYCJE = [
  { href: "/index.html", tekst: "Start", dopasuj: ["/", "/index.html"] },
  { href: "/zbiory.html", tekst: "Zbiory", dopasuj: ["/zbiory.html", "/zbior.html"] },
  { href: "/wykaz-aed.html", tekst: "Wykaz AED", dopasuj: ["/wykaz-aed.html"] },
  { href: "/mapa.html", tekst: "Mapa", dopasuj: ["/mapa.html"] },
  { href: "/asystent.html", tekst: "Asystent", dopasuj: ["/asystent.html"] },
  { href: "/instytucja.html", tekst: "Dostawcy", dopasuj: ["/instytucja.html", "/partner.html"] },
  { href: "/admin/index.html", tekst: "Panel dostawcy", dopasuj: ["/admin/", "/admin/index.html"] },
  { href: "/jury.html", tekst: "Dla jury", dopasuj: ["/jury.html"] },
];

function zbudujNaglowek() {
  const sciezka = location.pathname;
  const lista = el("ul", {}, POZYCJE.map((p) => {
    const aktywna = p.dopasuj.includes(sciezka);
    return el("li", {}, el("a", { href: p.href, "aria-current": aktywna ? "page" : null }, p.tekst));
  }));
  const nav = el("nav", { class: "nawigacja", id: "nawigacja-glowna", "aria-label": "Główna" }, lista);
  const przycisk = el("button", {
    type: "button", class: "nawigacja-przycisk", "aria-expanded": "false", "aria-controls": "nawigacja-glowna",
  }, el("span", { "aria-hidden": "true", text: "☰" }), el("span", { text: "Menu" }));

  const zwin = (zwinieta) => {
    nav.dataset.zwiniete = zwinieta ? "true" : "false";
    przycisk.setAttribute("aria-expanded", zwinieta ? "false" : "true");
  };
  zwin(true);
  przycisk.addEventListener("click", () => zwin(nav.dataset.zwiniete !== "true"));
  nav.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && nav.dataset.zwiniete === "false" && przycisk.offsetParent !== null) { zwin(true); przycisk.focus(); }
  });

  return el("div", { class: "naglowek__wnetrze" },
    el("a", { class: "logo", href: "/index.html" },
      el("img", { src: "/brand/logo-kompakt.svg", alt: "#TuBijeAED – strona główna prototypu", width: "196", height: "40" })),
    przycisk, nav);
}

function zbudujStopke() {
  return el("div", { class: "stopka__wnetrze" },
    el("div", {},
      el("h2", {}, "#TuBijeAED – prototyp"),
      el("p", {}, "Prototyp – modyfikacja portalu dane.gov.pl (HackNation 2026). Nie jest to oficjalny serwis."),
      el("p", {}, "Dane w prototypie są przykładowe i nie służą do ratowania życia. W nagłym wypadku dzwoń ",
        el("a", { href: "tel:112" }, "112"), ".")),
    el("div", {},
      el("h2", {}, "Na skróty"),
      el("ul", {},
        el("li", {}, el("a", { href: "/wykaz-aed.html" }, "Wykaz defibrylatorów AED")),
        el("li", {}, el("a", { href: "/mapa.html" }, "Mapa #TuBijeAED")),
        el("li", {}, el("a", { href: "/admin/index.html" }, "Panel dostawcy")),
        el("li", {}, el("a", { href: "/jury.html" }, "Ścieżka dla jury")))),
    el("div", {},
      el("h2", {}, "Dla deweloperów"),
      el("ul", {},
        el("li", {}, el("a", { href: "/api/1.4/aed-aggregated" }, "API: /api/1.4/aed-aggregated")),
        el("li", {}, el("a", { href: "/api/1.4/datasets" }, "API: /api/1.4/datasets")),
        el("li", {}, el("a", { href: "/docs" }, "Dokumentacja OpenAPI")))));
}

function start() {
  document.documentElement.classList.add("js");
  const g = document.getElementById("naglowek-wnetrze");
  if (g) g.replaceChildren(zbudujNaglowek());
  const s = document.getElementById("stopka");
  if (s) s.replaceChildren(zbudujStopke());
}
start();
