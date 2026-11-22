/* partner.html?id= – publiczna weryfikacja odznaki Partnera #TuBijeAED. */
import { pobierz, API_PARTNERZY, API_14, lista, plaski } from "./api.js";
import { $, el, wstaw, ladowanie, pokazBlad, komunikat, param, tytulStrony, plakietkaPartnera, tekst, zbudujTabele, formatData } from "./ui.js";
import { kryteriaLista, opisWaznosci, adresOdznaki, ALT_ODZNAKI } from "./partner-wspolne.js";

async function nazwaInstytucji(id) {
  try {
    const odp = await pobierz(`${API_14}/institutions/${encodeURIComponent(id)}`);
    const i = plaski(odp.data ?? odp);
    return i.title || i.nazwa || `Instytucja ${id}`;
  } catch { return `Instytucja ${id}`; }
}

const idPartnera = (x) => (x.instytucja && typeof x.instytucja === "object" ? x.instytucja.id : undefined) ?? x.instytucja_id ?? x.id;
const nazwaPartnera = (x) => (x.instytucja && typeof x.instytucja === "object" ? x.instytucja.nazwa || x.instytucja.title : x.nazwa || x.title || x.instytucja) || `Instytucja ${idPartnera(x)}`;

async function szczegoly(kont, id) {
  let p;
  try { p = await pobierz(`${API_PARTNERZY}/${encodeURIComponent(id)}`); }
  catch (e) { pokazBlad(kont, e, e.status === 404 ? "Nie znaleziono takiej instytucji" : "Nie udało się zweryfikować statusu"); return; }
  const nazwa = (p.instytucja && (p.instytucja.nazwa || p.instytucja.title)) || await nazwaInstytucji(id);
  tytulStrony(`Weryfikacja Partnera: ${nazwa}`);
  $("#partner-okruszek").textContent = nazwa;
  const status = p.status || "BRAK";
  const wynik = {
    AKTYWNY: ["ok", "Status Partnera #TuBijeAED jest aktywny", "Dane AED tej instytucji są zweryfikowane w portalu dane.gov.pl."],
    "WYGASŁY": ["uwaga", "Status Partnera #TuBijeAED wygasł", "Odznaka wyświetlana na stronie tej instytucji jest nieaktualna."],
    BRAK: ["blad", "Ta instytucja nie jest Partnerem #TuBijeAED", "Nie spełnia kryteriów programu – odznaka na jej stronie nie ma pokrycia."],
  }[status] || ["info", `Status: ${status}`, ""];
  const wynikDiv = el("div", { role: "status" });
  komunikat(wynikDiv, wynik[0], wynik[1], el("p", {}, wynik[2], " ", opisWaznosci(p)));
  wstaw(kont,
    el("h1", {}, `Weryfikacja odznaki: ${nazwa}`),
    wynikDiv,
    status !== "BRAK" ? el("p", {}, el("img", { src: adresOdznaki(id, "jasna", "pelna"), alt: ALT_ODZNAKI })) : null,
    el("h2", {}, "Kryteria programu"),
    kryteriaLista(p.kryteria),
    el("p", {}, el("a", { class: "przycisk przycisk--drugi", href: `/instytucja.html?id=${encodeURIComponent(id)}` }, "Zobacz dostawcę i jego zbiory"),
      " ", el("a", { class: "przycisk przycisk--drugi", href: "/partner.html" }, "Wszyscy Partnerzy")));
}

async function wszyscy(kont) {
  tytulStrony("Partnerzy #TuBijeAED");
  $("#partner-okruszek").textContent = "Wszyscy Partnerzy";
  let odp;
  try { odp = await pobierz(API_PARTNERZY + "/"); }
  catch (e) { pokazBlad(kont, e, "Nie udało się wczytać listy Partnerów"); return; }
  const l = lista(odp).map(plaski);
  wstaw(kont,
    el("h1", {}, "Partnerzy #TuBijeAED"),
    el("p", { class: "lead" }, "Instytucje i firmy, których dane AED przeszły weryfikację w portalu dane.gov.pl. Odznaka Partnera na stronie dostawcy prowadzi do tej publicznej weryfikacji."),
    zbudujTabele({
      opis: "Lista Partnerów #TuBijeAED",
      pusty: "Na razie brak Partnerów.",
      kolumny: [
        { naglowek: "Instytucja", naglowekWiersza: true, wartosc: (x) => el("a", { href: `/partner.html?id=${encodeURIComponent(idPartnera(x))}` }, nazwaPartnera(x)) },
        { naglowek: "Status", wartosc: (x) => plakietkaPartnera(x.status || "BRAK") },
        { naglowek: "Ważny do", wartosc: (x) => formatData(x.wazny_do) },
      ],
      wiersze: l,
    }));
}

const id = param("id");
const kont = $("#partner-tresc");
ladowanie(kont);
(id ? szczegoly(kont, id) : wszyscy(kont));
