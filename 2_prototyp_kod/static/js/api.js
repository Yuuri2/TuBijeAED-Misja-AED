/* #TuBijeAED – klient API (fetch + obsługa błędów `{error}` + nagłówek X-Demo-Konto).
   Właściciel: Frontend. Kontrakt: docs/PROTOTYP.md. */

const KLUCZ_KONTO = "demoKonto";
const KLUCZ_NAZWA = "demoKontoNazwa";

export const API_ADMIN = "/api/admin";
export const API_14 = "/api/1.4";
export const API_MAPA = "/api/mapa";
export const API_ASYSTENT = "/api/asystent";
export const API_PARTNERZY = "/api/partnerzy";

/* ---------- „Zaloguj jako…” (sessionStorage; może być niedostępny) ---------- */
export function konto() {
  try {
    const id = sessionStorage.getItem(KLUCZ_KONTO);
    return id ? { id, nazwa: sessionStorage.getItem(KLUCZ_NAZWA) || id } : null;
  } catch { return null; }
}
export function ustawKonto(id, nazwa) {
  try {
    sessionStorage.setItem(KLUCZ_KONTO, String(id));
    sessionStorage.setItem(KLUCZ_NAZWA, nazwa || String(id));
  } catch { /* tryb prywatny – wybór ważny tylko do przeładowania strony */ pamiecKonta = { id: String(id), nazwa }; }
}
export function wyloguj() {
  pamiecKonta = null;
  try { sessionStorage.removeItem(KLUCZ_KONTO); sessionStorage.removeItem(KLUCZ_NAZWA); } catch { /* nic */ }
}
let pamiecKonta = null;
export function kontoAktywne() { return konto() || pamiecKonta; }

/* ---------- Błąd API ---------- */
export class BladApi extends Error {
  constructor(komunikat, status, dane) {
    super(komunikat);
    this.name = "BladApi";
    this.status = status;
    this.dane = dane;
  }
}

function komunikatZOdpowiedzi(status, dane, tekst) {
  let m = null;
  if (dane && typeof dane === "object") {
    if (typeof dane.error === "string") m = dane.error;
    else if (typeof dane.detail === "string") m = dane.detail;
    else if (Array.isArray(dane.detail)) {
      m = dane.detail.map((d) => (d && d.msg ? `${(d.loc || []).slice(1).join(".")}: ${d.msg}` : String(d))).join("; ");
    } else if (dane.detail && typeof dane.detail === "object" && typeof dane.detail.error === "string") m = dane.detail.error;
  }
  if (m) return m;
  if (status === 401) return "Wymagane zalogowanie – wybierz konto w panelu dostawcy („Zaloguj jako…”).";
  if (status === 403) return "To konto nie ma uprawnień do tej operacji.";
  if (status === 404) return "Nie znaleziono zasobu (404). Funkcja może nie być jeszcze dostępna na serwerze.";
  if (status === 501) return "Ta funkcja nie jest jeszcze zaimplementowana na serwerze (501).";
  if (status >= 500) return `Błąd serwera (${status}). Spróbuj ponownie za chwilę.`;
  return tekst ? tekst.slice(0, 200) : `Błąd żądania (${status}).`;
}

function zbudujUrl(sciezka, parametry) {
  if (!parametry) return sciezka;
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(parametry)) {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `${sciezka}${sciezka.includes("?") ? "&" : "?"}${s}` : sciezka;
}

/** Wspólna funkcja zapytań.
 *  opcje: {metoda, parametry, cialo (FormData | obiekt JSON), odpowiedz: "json" | "blob" | "tekst" | "surowa"} */
export async function zapytanie(sciezka, opcje = {}) {
  const { metoda = "GET", parametry, cialo, odpowiedz = "json", naglowki = {}, sygnal } = opcje;
  const h = { Accept: odpowiedz === "json" ? "application/json" : "*/*", ...naglowki };
  const k = kontoAktywne();
  if (k) h["X-Demo-Konto"] = k.id;
  const init = { method: metoda, headers: h, signal: sygnal };
  if (cialo instanceof FormData) init.body = cialo;
  else if (cialo !== undefined) { init.body = JSON.stringify(cialo); h["Content-Type"] = "application/json"; }

  let odp;
  try {
    odp = await fetch(zbudujUrl(sciezka, parametry), init);
  } catch (e) {
    if (e && e.name === "AbortError") throw e;
    throw new BladApi("Brak połączenia z serwerem. Sprawdź połączenie i spróbuj ponownie.", 0, null);
  }
  if (!odp.ok) {
    let dane = null, tekst = "";
    try { tekst = await odp.text(); dane = JSON.parse(tekst); } catch { /* nie-JSON */ }
    throw new BladApi(komunikatZOdpowiedzi(odp.status, dane, tekst), odp.status, dane);
  }
  if (odpowiedz === "surowa") return odp;
  if (odpowiedz === "blob") return odp.blob();
  if (odpowiedz === "tekst") return odp.text();
  if (odp.status === 204) return null;
  try { return await odp.json(); }
  catch { throw new BladApi("Serwer zwrócił odpowiedź w nieoczekiwanym formacie.", odp.status, null); }
}

export const pobierz = (sciezka, parametry, opcje = {}) => zapytanie(sciezka, { ...opcje, parametry });
export const wyslij = (sciezka, cialo, metoda = "POST", opcje = {}) => zapytanie(sciezka, { ...opcje, metoda, cialo });

/* ---------- Normalizacja odpowiedzi (tolerancja na drobne różnice kształtu) ---------- */

/** Zwraca tablicę z odpowiedzi: [], {items}, {data: []}, {features}, {zbiory}, {zasoby}… */
export function lista(odp) {
  if (Array.isArray(odp)) return odp;
  if (!odp || typeof odp !== "object") return [];
  for (const k of ["items", "data", "features", "results", "zbiory", "zasoby", "konta", "instytucje", "partnerzy", "historia", "rekordy"]) {
    if (Array.isArray(odp[k])) return odp[k];
  }
  return [];
}

/** Rekord JSON:API {id, attributes, relationships} → płaski obiekt. */
export function plaski(x) {
  if (!x || typeof x !== "object") return {};
  const a = x.attributes && typeof x.attributes === "object" ? x.attributes : {};
  const p = x.properties && typeof x.properties === "object" ? x.properties : {};
  const o = { ...x, ...a, ...p };
  if (x.geometry && Array.isArray(x.geometry.coordinates)) {
    o.dlugosc_geo = o.dlugosc_geo ?? x.geometry.coordinates[0];
    o.szerokosc_geo = o.szerokosc_geo ?? x.geometry.coordinates[1];
  }
  if (o.id === undefined && x.id !== undefined) o.id = x.id;
  return o;
}

/** Dane stronicowania z odpowiedzi JSON:API (różne warianty meta). */
export function liczbaWszystkich(odp) {
  const m = (odp && odp.meta) || {};
  const kandydaci = [m.count, m.total, m.total_count, m.pagination && m.pagination.count, m.pagination && m.pagination.total, m.aggs && m.aggs.count];
  for (const c of kandydaci) if (Number.isFinite(Number(c)) && c !== null && c !== undefined) return Number(c);
  return null;
}
