/* Wspólne elementy Partnera #TuBijeAED: kryteria, adres odznaki, kod do stopki. */
import { el, plakietka, formatData, tekst } from "./ui.js";
import { API_PARTNERZY } from "./api.js";

export const ALT_ODZNAKI = "Partner #TuBijeAED – dane AED zweryfikowane w dane.gov.pl";

export function adresOdznaki(id, wariant = "jasna", rozmiar = "mala") {
  return `${API_PARTNERZY}/${encodeURIComponent(id)}/odznaka.svg?wariant=${wariant}&rozmiar=${rozmiar}`;
}

/** Kod HTML do wklejenia w stopce strony dostawcy (adresy bezwzględne). */
export function kodStopki(id, wariant = "jasna", rozmiar = "mala") {
  const baza = location.origin;
  const wsk = wariant === "jasna" && rozmiar === "mala" ? "" : `?wariant=${wariant}&rozmiar=${rozmiar}`;
  return `<a href="${baza}/partner.html?id=${encodeURIComponent(id)}"><img src="${baza}${API_PARTNERZY}/${encodeURIComponent(id)}/odznaka.svg${wsk}" alt="${ALT_ODZNAKI}"></a>`;
}

const NAZWY_KRYTERIOW = {
  zasob_w_wykazie: "Zasób uwzględniony w aktualnym wykazie zbiorczym",
  bez_bledow_walidacji: "Brak błędów walidacji",
  aktualnosc_12_miesiecy: "Dane aktualne (do 12 miesięcy)",
  kompletnosc_80: "Kompletność rekordów co najmniej 80%",
};

export function kryteriaLista(kryteria) {
  const k = Array.isArray(kryteria) ? kryteria : [];
  if (!k.length) return el("p", { class: "tekst-drugorzedny" }, "Brak informacji o kryteriach.");
  return el("ul", { class: "kryteria" }, k.map((c) => el("li", {},
    plakietka(c.spelnione ? "Spełnione" : "Niespełnione", c.spelnione ? "ok" : "blad"),
    el("span", {}, el("strong", {}, NAZWY_KRYTERIOW[c.nazwa] || tekst(c.nazwa)), c.opis ? el("br") : null, c.opis ? el("span", { class: "tekst-drugorzedny" }, c.opis) : null))));
}

export function opisWaznosci(p) {
  if (!p) return "";
  if (p.status === "AKTYWNY") return `Status ważny do ${formatData(p.wazny_do)}.`;
  if (p.status === "WYGASŁY") return `Status wygasł ${formatData(p.wazny_do)}. Zaktualizuj zasób, aby odnowić.`;
  return "Instytucja nie spełnia jeszcze kryteriów Partnera.";
}
