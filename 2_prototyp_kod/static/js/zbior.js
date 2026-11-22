/* zbior.html?id= (lub ?zasob=) – szczegóły zbioru i jego zasoby. */
import { pobierz, API_14, lista, plaski } from "./api.js";
import { $, el, wstaw, ladowanie, pokazBlad, komunikat, param, formatData, tekst, plakietka, plakietkaWalidacji, zbudujTabele, linkInstytucji, tytulStrony, TYP_INSTYTUCJI, CZESTOTLIWOSC } from "./ui.js";

async function ustalId() {
  const id = param("id");
  if (id) return id;
  const zasob = param("zasob");
  if (!zasob) return null;
  const odp = await pobierz(`${API_14}/resources/${encodeURIComponent(zasob)}`);
  const d = odp.data ?? odp;
  const a = plaski(d);
  const rel = d.relationships && d.relationships.dataset && d.relationships.dataset.data;
  return (rel && rel.id) ?? a.dataset_id ?? a.zbior_id ?? (a.dataset && a.dataset.id) ?? null;
}

function wierszZasobu(z) {
  const aggr = z.aggregated_list_type === "AED" || z.wykaz_typ === "AED";
  return {
    ...z, aggr,
  };
}

async function init() {
  const kont = $("#zbior-tresc");
  ladowanie(kont);
  let id;
  try { id = await ustalId(); } catch (e) { pokazBlad(kont, e, "Nie udało się ustalić zbioru"); return; }
  if (!id) {
    komunikat(kont, "uwaga", "Nie wskazano zbioru", el("p", {}, "Wybierz zbiór z ", el("a", { href: "/zbiory.html" }, "listy zbiorów"), "."));
    return;
  }
  let z, zasoby;
  try {
    const odp = await pobierz(`${API_14}/datasets/${encodeURIComponent(id)}`);
    z = plaski(odp.data ?? odp);
    z.id = (odp.data ?? odp).id ?? id;
  } catch (e) { pokazBlad(kont, e, e.status === 404 ? "Nie znaleziono takiego zbioru" : "Nie udało się wczytać zbioru"); return; }
  try {
    const odp = await pobierz(`${API_14}/datasets/${encodeURIComponent(id)}/resources`);
    zasoby = lista(odp).map((x) => wierszZasobu(plaski(x)));
  } catch (e) { zasoby = null; var bladZasobow = e; }

  const inst = z.institution || {};
  tytulStrony(`Zbiór: ${tekst(z.title, id)}`);
  $("#zbior-okruszek").textContent = tekst(z.title, `Zbiór ${id}`);

  wstaw(kont,
    el("h1", { id: "zbior-h1", tabindex: "-1" }, tekst(z.title, `Zbiór ${id}`)),
    z.is_aggregated_list ? el("p", {}, plakietka("Wykaz zbiorczy AED (zbiór właściciela wykazu)", "ok")) : null,
    z.notes ? el("p", { class: "lead" }, z.notes) : null,
    el("section", { class: "karta karta--akcent", "aria-labelledby": "h-meta" },
      el("h2", { id: "h-meta" }, "Informacje o zbiorze"),
      el("p", { class: "odpowiedzialnosc" }, "Za dane w tym zbiorze odpowiada: ",
        inst.id !== undefined ? linkInstytucji(inst.id, tekst(inst.title)) : tekst(inst.title)),
      el("dl", { class: "opis" },
        el("dt", {}, "Typ dostawcy"), el("dd", {}, TYP_INSTYTUCJI[inst.type] || tekst(inst.type)),
        el("dt", {}, "Licencja"), el("dd", {}, tekst(z.license)),
        el("dt", {}, "Częstotliwość aktualizacji"), el("dd", {}, CZESTOTLIWOSC[z.update_frequency] || tekst(z.update_frequency)),
        el("dt", {}, "Kategorie"), el("dd", {}, Array.isArray(z.categories) ? z.categories.map((c) => (typeof c === "string" ? c : c.title || c.code)).join(", ") || "–" : tekst(z.categories)),
        el("dt", {}, "Słowa kluczowe"), el("dd", {}, Array.isArray(z.keywords) ? z.keywords.join(", ") || "–" : tekst(z.keywords)),
        el("dt", {}, "Ostatnia zmiana"), el("dd", {}, formatData(z.modified, true)))),
    el("h2", { id: "h-zasoby" }, "Zasoby (pliki danych)"),
    zasoby === null
      ? el("div", { class: "komunikat komunikat--blad" }, `Nie udało się wczytać zasobów: ${bladZasobow.message}`)
      : zbudujTabele({
        opis: "Zasoby zbioru – format, status walidacji, pobieranie",
        pusty: "Ten zbiór nie ma jeszcze zasobów.",
        kolumny: [
          { naglowek: "Tytuł", naglowekWiersza: true, wartosc: (r) => el("span", {}, tekst(r.title), r.aggr ? el("span", {}, " ", plakietka("Zasób wykazu AED", "ok")) : null) },
          { naglowek: "Format", wartosc: (r) => tekst(r.format).toUpperCase() },
          { naglowek: "Walidacja wg wzorca", wartosc: (r) => plakietkaWalidacji(r.validation_status ?? "NIE_DOTYCZY") },
          { naglowek: "Zmodyfikowano", wartosc: (r) => formatData(r.modified) },
          { naglowek: "Pobierz", wartosc: (r) => (r.download_url
            ? el("a", { href: r.download_url, download: "" }, "Pobierz", el("span", { class: "tylko-czytniki" }, ` plik: ${tekst(r.title)}`))
            : "–") },
        ],
        wiersze: zasoby,
      }),
    z.is_aggregated_list
      ? el("p", {}, el("a", { class: "przycisk", href: "/wykaz-aed.html" }, "Przejdź do wykazu zbiorczego AED"))
      : (zasoby || []).some((r) => r.aggr)
        ? el("p", {}, "Zasób oznaczony jako „Zasób wykazu AED” jest scalany do ", el("a", { href: "/wykaz-aed.html" }, "wykazu zbiorczego AED"), " po pozytywnej walidacji.")
        : null);
}
init();
