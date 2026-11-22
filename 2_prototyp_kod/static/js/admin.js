/* admin/index.html – panel dostawcy (konta demo, zbiory, zasoby, wykaz AED, harvester XML) i admina portalu.
   Kontrakt: docs/PROTOTYP.md (REST – panel). Dane w DOM tylko przez textContent (ui.js). */
import { pobierz, wyslij, zapytanie, API_ADMIN, lista, plaski, konto, ustawKonto, wyloguj } from "./api.js";
import {
  $, $$, el, wstaw, wyczysc, ladowanie, pokazBlad, komunikat, tekst, formatData, formatLiczba, plakietka,
  plakietkaWalidacji, raportWalidacji, zbudujTabele, fokus, opcje, TYP_INSTYTUCJI, statystyka,
} from "./ui.js";

let aktualne = null;          // {id, nazwa}
let zbiory = [];              // moje zbiory
let edytowanyZasob = null;    // zasób w trybie aktualizacji (PUT)

const jestAdmin = () => aktualne && String(aktualne.id) === "admin";

/* ======================= Logowanie demo ======================= */
async function wczytajKonta() {
  const kont = $("#konta-lista");
  ladowanie(kont, "Wczytywanie kont demo…");
  try {
    const odp = await pobierz(`${API_ADMIN}/konta`);
    const konta = lista(odp).map(plaski);
    if (!konta.length) { komunikat(kont, "uwaga", "Brak kont demo", "Serwer nie zwrócił żadnych kont demo."); return; }
    wstaw(kont, el("ul", { class: "konta" }, konta.map((k) => el("li", {},
      el("button", { type: "button", class: "przycisk przycisk--drugi", on: { click: () => zaloguj(k) } },
        el("span", {}, "Zaloguj jako ", el("strong", {}, k.nazwa)),
        k.typ ? el("span", { class: "tylko-czytniki" }, ` (${TYP_INSTYTUCJI[k.typ] || k.typ})`) : null)))));
  } catch (e) { pokazBlad(kont, e, "Nie udało się wczytać kont demo"); }
}

function zaloguj(k) {
  ustawKonto(k.id, k.nazwa);
  aktualne = { id: String(k.id), nazwa: k.nazwa };
  pokazPanel(true);
}

function wylogujKlik() {
  wyloguj();
  aktualne = null;
  zbiory = [];
  edytowanyZasob = null;
  pokazPanel(false);
  $("#status-logowania").textContent = "Wylogowano z konta demo.";
  fokus($("#h-logowanie"));
}

async function pokazPanel(czyFokus) {
  const k = aktualne;
  $("#sekcja-logowanie").hidden = !!k;
  $("#panel").hidden = !k;
  if (!k) return;
  const admin = jestAdmin();
  $("#zalogowany-nazwa").textContent = k.nazwa;
  for (const n of $$(".js-konto-nazwa")) n.textContent = k.nazwa;
  $("#zalogowany-rola").textContent = admin
    ? "Administrator portalu – może przebudować wykaz zbiorczy i oglądać historię uruchomień."
    : "Dostawca danych – publikuje zasoby i odpowiada za ich zawartość.";
  for (const id of ["sekcja-zbiory", "sekcja-nowy-zbior", "sekcja-zasob", "sekcja-harvester"]) $("#" + id).hidden = admin;
  $("#sekcja-admin").hidden = !admin;
  $("#spis-dostawca").hidden = admin;
  $("#spis-admin").hidden = !admin;
  $("#status-logowania").textContent = `Zalogowano jako: ${k.nazwa}.`;
  if (czyFokus) fokus($("#h-panel"));
  if (admin) { await wczytajHistorie(); } else { await wczytajZbiory(); }
}

/* ======================= Moje zbiory ======================= */
async function wczytajZbiory() {
  const kont = $("#moje-zbiory");
  ladowanie(kont);
  try {
    const odp = await pobierz(`${API_ADMIN}/moje-zbiory`);
    zbiory = lista(odp).map((z) => ({ ...plaski(z), zasoby: lista(z.zasoby ?? plaski(z).zasoby) }));
  } catch (e) {
    if (e.status === 401) { wylogujKlik(); return; }
    pokazBlad(kont, e, "Nie udało się wczytać Twoich zbiorów"); return;
  }
  renderZbiory();
  opcje($("#z-zbior"), zbiory.map((z) => [String(z.id), z.tytul]), zbiory.length ? "Wybierz zbiór…" : "Najpierw utwórz zbiór");
  if (edytowanyZasob) $("#z-zbior").value = String(edytowanyZasob.zbior_id ?? "");
  else if (zbiory.length === 1) $("#z-zbior").value = String(zbiory[0].id);
}

function renderZbiory() {
  const kont = $("#moje-zbiory");
  if (!zbiory.length) {
    wstaw(kont, el("p", {}, "Ta instytucja nie ma jeszcze zbiorów. Utwórz pierwszy zbiór poniżej, a potem dodaj do niego zasób z danymi AED."));
    return;
  }
  wstaw(kont, el("div", { class: "stos" }, zbiory.map((z) => {
    const zasoby = z.zasoby.map(plaski);
    return el("article", { class: "karta", "aria-labelledby": `zb-${z.id}` },
      el("h3", { id: `zb-${z.id}` }, tekst(z.tytul)),
      el("p", { class: "maly odpowiedzialnosc" }, `Za dane w tym zbiorze odpowiada: ${aktualne.nazwa}`),
      el("p", { class: "maly tekst-drugorzedny" }, `Status zbioru: ${tekst(z.status)} · licencja: ${tekst(z.licencja)} · zmodyfikowano: ${formatData(z.zmodyfikowano)} · `,
        el("a", { href: `/zbior.html?id=${encodeURIComponent(z.id)}` }, "podgląd publiczny")),
      zbudujTabele({
        opis: `Zasoby zbioru „${tekst(z.tytul)}”`,
        pusty: "Brak zasobów w tym zbiorze.",
        kolumny: [
          { naglowek: "Tytuł zasobu", naglowekWiersza: true, wartosc: (r) => tekst(r.tytul) },
          { naglowek: "Format", wartosc: (r) => tekst(r.format).toUpperCase() },
          { naglowek: "Wykaz AED", wartosc: (r) => (r.wykaz_typ === "AED" ? plakietka("Zasób wykazu AED", "ok") : "–") },
          { naglowek: "Publikacja", wartosc: (r) => tekst(r.status) },
          { naglowek: "Walidacja", wartosc: (r) => plakietkaWalidacji(r.walidacja_status ?? "BRAK") },
          { naglowek: "Wiersze", klasa: "liczba", wartosc: (r) => (r.liczba_wierszy ?? "–") },
          { naglowek: "Zmodyfikowano", wartosc: (r) => formatData(r.zmodyfikowano) },
          {
            naglowek: "Działania", wartosc: (r) => el("div", { class: "rzad" },
              el("button", { type: "button", class: "przycisk przycisk--drugi przycisk--maly", on: { click: () => edytuj(r, z) } },
                "Zaktualizuj", el("span", { class: "tylko-czytniki" }, `: ${tekst(r.tytul)}`)),
              el("button", { type: "button", class: "przycisk przycisk--drugi przycisk--maly", on: { click: () => usun(r) } },
                "Usuń", el("span", { class: "tylko-czytniki" }, `: ${tekst(r.tytul)}`))),
          },
        ],
        wiersze: zasoby,
      }),
      ...zasoby.filter((r) => r.walidacja_status === "BLEDY" && r.walidacja_raport).map((r) =>
        el("details", {}, el("summary", {}, `Raport walidacji zasobu „${tekst(r.tytul)}” – zasób nie wchodzi do wykazu`),
          raportWalidacji(typeof r.walidacja_raport === "string" ? bezpiecznyJson(r.walidacja_raport) : r.walidacja_raport))));
  })));
}

function bezpiecznyJson(s) { try { return JSON.parse(s); } catch { return {}; } }

async function usun(r) {
  if (!window.confirm(`Usunąć zasób „${r.tytul}”? Wykaz zbiorczy zostanie przebudowany.`)) return;
  const wynik = $("#zasob-wynik");
  ladowanie(wynik, "Usuwanie zasobu…");
  try {
    const odp = await zapytanie(`${API_ADMIN}/zasoby/${encodeURIComponent(r.id)}`, { metoda: "DELETE" });
    const w = odp && odp.wykaz;
    komunikat(wynik, "ok", "Zasób usunięty", w && w.komunikat ? el("p", {}, w.komunikat) : el("p", {}, "Wykaz zbiorczy został przebudowany bez tego zasobu."));
    await wczytajZbiory();
  } catch (e) { pokazBlad(wynik, e, "Nie udało się usunąć zasobu"); }
  fokus($("#zasob-wynik"));
}

/* ======================= Nowy zbiór ======================= */
async function wyslijZbior(e) {
  e.preventDefault();
  const f = e.currentTarget;
  const wynik = $("#zbior-wynik");
  if (!sprawdzPola(f, [["zb-tytul", "Podaj tytuł zbioru."]])) return;
  const dane = {
    tytul: $("#zb-tytul").value.trim(), opis: $("#zb-opis").value.trim(), licencja: $("#zb-licencja").value,
    czestotliwosc: $("#zb-czest").value,
    slowa_kluczowe: $("#zb-slowa").value.split(",").map((s) => s.trim()).filter(Boolean),
  };
  const przycisk = e.submitter; przycisk.disabled = true;
  ladowanie(wynik, "Zapisywanie zbioru…");
  try {
    const z = plaski(await wyslij(`${API_ADMIN}/zbiory`, dane));
    komunikat(wynik, "ok", "Zbiór utworzony", el("p", {}, `Zbiór „${tekst(z.tytul, dane.tytul)}” jest gotowy. Dodaj do niego zasób z danymi AED w następnej sekcji.`));
    f.reset();
    await wczytajZbiory();
    if (z.id) $("#z-zbior").value = String(z.id);
  } catch (err) { pokazBlad(wynik, err, "Nie udało się utworzyć zbioru"); }
  finally { przycisk.disabled = false; }
}

/* ======================= Zasób ======================= */
function sprawdzPola(formularz, reguly) {
  let pierwszy = null;
  for (const [id, komunikatBledu, warunek] of reguly) {
    const pole = document.getElementById(id);
    const bladEl = document.getElementById(`${id}-blad`);
    const ok = warunek ? warunek(pole) : pole.value.trim() !== "";
    if (bladEl) bladEl.textContent = ok ? "" : komunikatBledu;
    if (ok) { pole.removeAttribute("aria-invalid"); }
    else { pole.setAttribute("aria-invalid", "true"); pierwszy = pierwszy || pole; }
  }
  if (pierwszy) pierwszy.focus();
  return !pierwszy;
}

function edytuj(r, z) {
  edytowanyZasob = { ...r, zbior_id: z.id };
  $("#z-zbior").value = String(z.id);
  $("#z-zbior").disabled = true;
  $("#z-tytul").value = r.tytul || "";
  $("#z-opis").value = r.opis || "";
  $("#z-url").value = r.url || "";
  $("#z-status").value = r.status || "opublikowany";
  $("#z-wykaz").checked = r.wykaz_typ === "AED";
  $("#tryb-info").hidden = false;
  $("#tryb-nazwa").textContent = r.tytul;
  $("#z-submit").textContent = "Zapisz zmiany zasobu";
  $("#sekcja-zasob").scrollIntoView({ block: "start" });
  fokus($("#h-zasob"));
}

function anulujEdycje() {
  edytowanyZasob = null;
  $("#form-zasob").reset();
  $("#z-zbior").disabled = false;
  $("#tryb-info").hidden = true;
  $("#z-submit").textContent = "Wyślij zasób";
  wczytajZbiory();
}

async function wyslijZasob(e) {
  e.preventDefault();
  const wynik = $("#zasob-wynik");
  const edycja = !!edytowanyZasob;
  const plik = $("#z-plik").files[0];
  const ok = sprawdzPola(e.currentTarget, [
    ["z-zbior", "Wybierz zbiór, do którego trafi zasób.", (p) => edycja || p.value !== ""],
    ["z-tytul", "Podaj tytuł zasobu."],
    ["z-plik", "Wybierz plik CSV lub XLSX albo podaj adres URL pliku.", () => edycja || !!plik || $("#z-url").value.trim() !== ""],
  ]);
  if (!ok) return;
  const fd = new FormData();
  if (plik) fd.set("plik", plik);
  if ($("#z-url").value.trim()) fd.set("url", $("#z-url").value.trim());
  fd.set("tytul", $("#z-tytul").value.trim());
  fd.set("opis", $("#z-opis").value.trim());
  fd.set("wykaz_typ", $("#z-wykaz").checked ? "AED" : "");
  fd.set("status", $("#z-status").value);
  const przycisk = $("#z-submit"); przycisk.disabled = true;
  ladowanie(wynik, "Wysyłanie i walidacja pliku wg wzorca…");
  await przeslijZasob(fd, edycja, edycja ? edytowanyZasob.id : $("#z-zbior").value, $("#z-wykaz").checked);
  przycisk.disabled = false;
  fokus($("#zasob-wynik-h"));
}

async function przeslijZasob(fd, edycja, idDocelowe, flagaAed) {
  const wynik = $("#zasob-wynik");
  const przycisk = $("#z-submit");
  try {
    const odp = edycja
      ? await wyslij(`${API_ADMIN}/zasoby/${encodeURIComponent(idDocelowe)}`, fd, "PUT")
      : await wyslij(`${API_ADMIN}/zbiory/${encodeURIComponent(idDocelowe)}/zasoby`, fd);
    pokazWynikZasobu(odp, flagaAed);
    if (edycja) { edytowanyZasob = null; $("#z-zbior").disabled = false; $("#tryb-info").hidden = true; $("#z-submit").textContent = "Wyślij zasób"; }
    $("#form-zasob").reset();
    await wczytajZbiory();
  } catch (err) { pokazBladZasobu(wynik, err, () => { fd.set("potwierdz_zastapienie", "true"); ladowanie(wynik, "Zastępowanie zasobu…"); return przeslijZasob(fd, edycja, idDocelowe, flagaAed); }); }
  finally { przycisk.disabled = false; }
  fokus($("#zasob-wynik-h"));
}

function pokazWynikZasobu(odp, flagaAed) {
  const wynik = $("#zasob-wynik");
  const zasob = plaski((odp && odp.zasob) || {});
  const raport = (odp && odp.walidacja) || {};
  const wykaz = (odp && odp.wykaz) || {};
  const aed = zasob.wykaz_typ ? zasob.wykaz_typ === "AED" : flagaAed;
  const wStat = zasob.walidacja_status || (aed ? ((raport.bledne_wiersze || 0) > 0 ? "BLEDY" : "OK") : "NIE_DOTYCZY");
  const opublikowany = !zasob.status || zasob.status === "opublikowany";
  let blok;
  if (!aed) {
    blok = komunikat(document.createElement("div"), "ok", "Zasób zapisany", el("p", {}, "Zasób nie jest oznaczony jako wykaz AED, więc nie wchodzi do wykazu zbiorczego."));
  } else if (wStat === "BLEDY") {
    blok = komunikat(document.createElement("div"), "blad", "Zasób odrzucony z wykazu – popraw plik i wyślij ponownie",
      el("p", {}, "Zasób został zapisany, ale ma błędy walidacji, więc NIE wchodzi do Wykazu zbiorczego AED. Poniżej wiersze i pola do poprawy. Po poprawieniu pliku użyj „Zaktualizuj” przy zasobie lub wyślij plik jeszcze raz."));
  } else if (!opublikowany) {
    blok = komunikat(document.createElement("div"), "uwaga", "Zasób zapisany jako szkic", el("p", {}, "Dane są poprawne, ale zasób nie jest opublikowany, więc jeszcze nie wchodzi do wykazu. Zmień status na „opublikowany”."));
  } else {
    blok = komunikat(document.createElement("div"), "ok", "Zasób włączony do Wykazu zbiorczego AED",
      el("p", {}, "Walidacja zakończona powodzeniem. Za dane w tym zasobie odpowiada: ", el("strong", {}, aktualne.nazwa), "."));
  }
  const info = wykaz.komunikat || wykaz.przebudowano !== undefined
    ? el("p", {}, plakietka(wykaz.przebudowano ? "Wykaz zbiorczy przebudowany" : "Wykaz bez zmian", wykaz.przebudowano ? "ok" : "info"), " ",
      wykaz.komunikat ? wykaz.komunikat : "",
      wykaz.przebudowano ? el("span", {}, " ", el("a", { href: "/wykaz-aed.html" }, "Zobacz wykaz AED"), " · ", el("a", { href: "/mapa.html" }, "zobacz na mapie")) : null)
    : null;
  wstaw(wynik,
    el("h3", { id: "zasob-wynik-h", tabindex: "-1" }, "Wynik wysyłania zasobu"),
    blok, info,
    aed ? el("h3", {}, "Raport walidacji") : null, aed ? raportWalidacji(raport) : null);
}

function pokazBladZasobu(wynik, err, ponow) {
  const raport = err.dane && (err.dane.walidacja || (err.dane.detail && err.dane.detail.walidacja));
  const wskazowka = err.status === 409
    ? el("p", {}, "Wskazówka: ta instytucja ma już opublikowany zasób AED. Zamiast dodawać drugi, użyj „Zaktualizuj” przy istniejącym zasobie w sekcji „Moje zbiory”.")
    : err.status === 422
      ? el("p", {}, "Plik nie ma kolumn wymaganych we wzorcu. Pobierz ", el("a", { href: "/api/asystent/wzorzec.csv" }, "wzorzec CSV"), " albo użyj ", el("a", { href: "/asystent.html" }, "asystenta dostawcy"), ".")
      : null;
  wstaw(wynik, el("h3", { id: "zasob-wynik-h", tabindex: "-1" }, "Wynik wysyłania zasobu"));
  wynik.append(komunikat(document.createElement("div"), "blad", err.status === 409 ? "Konflikt – zasób AED już istnieje" : "Nie udało się zapisać zasobu", el("p", {}, err.message), wskazowka));
  if (err.status === 409 && ponow) {
    wynik.append(el("p", {}, el("button", { type: "button", class: "przycisk przycisk--drugi", on: { click: ponow } },
      "Zastąp istniejący zasób AED tym plikiem")));
  }
  if (raport) wynik.append(raportWalidacji(raport));
}

/* ======================= Harvester XML ======================= */
async function wyslijXml(e) {
  e.preventDefault();
  const wynik = $("#xml-wynik");
  const formularz = e.currentTarget;
  const plik = $("#x-plik").files[0];
  if (!sprawdzPola(e.currentTarget, [["x-plik", "Wybierz plik XML harvestera (wersja 1.13 lub 1.14).", () => !!plik]])) return;
  const fd = new FormData(); fd.set("plik", plik);
  const przycisk = e.submitter; przycisk.disabled = true;
  ladowanie(wynik, "Importowanie pliku XML…");
  try {
    const odp = await wyslij(`${API_ADMIN}/harvester/xml`, fd);
    const bledy = Array.isArray(odp.bledy) ? odp.bledy : [];
    wstaw(wynik, el("h3", { id: "xml-wynik-h", tabindex: "-1" }, "Wynik importu XML"));
    wynik.append(
      komunikat(document.createElement("div"), bledy.length ? "uwaga" : "ok",
        bledy.length ? "Import zakończony z uwagami" : "Import zakończony powodzeniem",
        el("p", {}, `Utworzone zbiory: ${formatLiczba(odp.zbiory_utworzone ?? 0)}, utworzone zasoby: ${formatLiczba(odp.zasoby_utworzone ?? 0)}.`)));
    if (bledy.length) {
      wynik.append(el("h4", {}, `Błędy i pominięcia (${bledy.length})`),
        el("ul", {}, bledy.map((b) => el("li", {}, typeof b === "string" ? b : [b.zasob || b.extIdent, b.komunikat || b.error || JSON.stringify(b)].filter(Boolean).join(": ")))));
    }
    formularz.reset();
    await wczytajZbiory();
  } catch (err) {
    wstaw(wynik, el("h3", { id: "xml-wynik-h", tabindex: "-1" }, "Wynik importu XML"));
    wynik.append(komunikat(document.createElement("div"), "blad", "Nie udało się zaimportować pliku", el("p", {}, err.message)));
  } finally { przycisk.disabled = false; }
  fokus($("#xml-wynik-h"));
}

/* ======================= Admin: przebudowa i historia ======================= */
function podsumowanieUruchomienia(w) {
  const uwz = Array.isArray(w.uwzglednione) ? w.uwzglednione : [];
  const pom = Array.isArray(w.pominiete) ? w.pominiete : [];
  const nazwa = (i) => (typeof i === "string" ? i : (i && (i.title || i.nazwa)) || "–");
  return el("div", {},
    uwz.length ? el("p", { class: "maly" }, el("strong", {}, "Uwzględnieni: "), uwz.map((u) => `${nazwa(u.instytucja)} (${formatLiczba(u.rekordy)})`).join("; ")) : el("p", { class: "maly" }, "Uwzględnieni: brak."),
    pom.length ? el("p", { class: "maly" }, el("strong", {}, "Pominięte: "), pom.map((u) => `${nazwa(u.instytucja)} – ${tekst(u.powod)}`).join("; ")) : el("p", { class: "maly" }, "Pominięte: brak."));
}

async function przebuduj() {
  const wynik = $("#przebudowa-wynik");
  const p = $("#przebuduj"); p.disabled = true;
  ladowanie(wynik, "Przebudowa wykazu zbiorczego AED…");
  try {
    const w = plaski(await wyslij(`${API_ADMIN}/wykazy/AED/przebuduj`, undefined));
    const ok = !w.status || w.status === "OK";
    wstaw(wynik, el("h3", { id: "przebudowa-h", tabindex: "-1" }, "Wynik przebudowy"));
    wynik.append(komunikat(document.createElement("div"), ok ? "ok" : "blad", ok ? "Wykaz zbiorczy AED przebudowany" : "Przebudowa zakończona błędem",
      el("p", {}, `Rekordów: ${formatLiczba(w.liczba_rekordow)}, dostawców: ${formatLiczba(w.liczba_dostawcow)}. ${w.komunikat || ""}`),
      podsumowanieUruchomienia(w),
      ok ? el("p", {}, el("a", { href: "/wykaz-aed.html" }, "Zobacz wykaz")) : null));
    await wczytajHistorie();
  } catch (e) { pokazBlad(wynik, e, "Nie udało się przebudować wykazu"); }
  finally { p.disabled = false; }
  fokus($("#przebudowa-h"));
}

async function wczytajHistorie() {
  const kont = $("#historia");
  ladowanie(kont);
  try {
    const odp = await pobierz(`${API_ADMIN}/wykazy/AED/historia`);
    const h = lista(odp).map(plaski);
    wstaw(kont, zbudujTabele({
      opis: "Historia uruchomień scalania wykazu AED",
      pusty: "Wykaz nie był jeszcze budowany.",
      kolumny: [
        { naglowek: "Data", naglowekWiersza: true, wartosc: (w) => formatData(w.utworzono, true) },
        { naglowek: "Status", wartosc: (w) => plakietka(w.status === "OK" ? "OK" : "Błąd", w.status === "OK" ? "ok" : "blad") },
        { naglowek: "Rekordy", klasa: "liczba", wartosc: (w) => formatLiczba(w.liczba_rekordow) },
        { naglowek: "Dostawcy", klasa: "liczba", wartosc: (w) => formatLiczba(w.liczba_dostawcow) },
        { naglowek: "Uwzględnione i pominięte (z powodem)", wartosc: (w) => podsumowanieUruchomienia(w) },
        { naglowek: "Komunikat", wartosc: (w) => tekst(w.komunikat) },
      ],
      wiersze: h,
    }));
  } catch (e) { pokazBlad(kont, e, "Nie udało się wczytać historii"); }
}

/* ======================= Start ======================= */
function init() {
  $("#form-zbior").addEventListener("submit", wyslijZbior);
  $("#form-zasob").addEventListener("submit", wyslijZasob);
  $("#form-xml").addEventListener("submit", wyslijXml);
  $("#anuluj-edycje").addEventListener("click", anulujEdycje);
  $("#wyloguj").addEventListener("click", wylogujKlik);
  $("#przebuduj").addEventListener("click", przebuduj);
  const k = konto();
  if (k) { aktualne = { id: k.id, nazwa: k.nazwa }; pokazPanel(false); } else { pokazPanel(false); }
  wczytajKonta();
}
init();
