/* instytucja.html – lista dostawców albo szczegóły instytucji (?id=): zbiory, status Partnera, kod odznaki. */
import { pobierz, API_14, API_PARTNERZY, lista, plaski } from "./api.js";
import {
  $, el, wstaw, ladowanie, pokazBlad, komunikat, param, tekst, plakietka, plakietkaPartnera, zbudujTabele,
  formatData, tytulStrony, kopiuj, TYP_INSTYTUCJI, formatLiczba,
} from "./ui.js";
import { kryteriaLista, opisWaznosci, adresOdznaki, kodStopki, ALT_ODZNAKI } from "./partner-wspolne.js";

async function listaInstytucji(kont) {
  tytulStrony("Dostawcy danych i Partnerzy");
  $("#instytucja-okruszek").textContent = "Dostawcy";
  let odp;
  try { odp = await pobierz(`${API_14}/institutions`, { per_page: 100 }); }
  catch (e) { pokazBlad(kont, e, "Nie udało się wczytać listy instytucji"); return; }
  const inst = lista(odp).map(plaski).sort((a, b) => String(a.title || a.nazwa).localeCompare(String(b.title || b.nazwa), "pl"));
  wstaw(kont,
    el("h1", {}, "Dostawcy danych i Partnerzy #TuBijeAED"),
    el("p", { class: "lead" }, "Dostawca to instytucja lub firma z kontem w portalu – publikuje zasób i odpowiada za dane. Partner #TuBijeAED to dostawca, którego dane przeszły weryfikację."),
    zbudujTabele({
      opis: "Dostawcy danych w portalu",
      kolumny: [
        { naglowek: "Dostawca", naglowekWiersza: true, wartosc: (i) => el("a", { href: `/instytucja.html?id=${encodeURIComponent(i.id)}` }, tekst(i.title || i.nazwa)) },
        { naglowek: "Typ", wartosc: (i) => TYP_INSTYTUCJI[i.institution_type || i.typ] || tekst(i.institution_type || i.typ) },
        { naglowek: "Status Partnera #TuBijeAED", wartosc: (i) => plakietkaPartnera(i.partner && i.partner.status ? i.partner.status : "BRAK") },
      ],
      wiersze: inst,
      pusty: "Brak instytucji.",
    }));
}

function sekcjaOdznaki(id, partner) {
  const status = partner ? partner.status : "BRAK";
  if (status === "BRAK") {
    return el("section", { class: "karta", "aria-labelledby": "h-odznaka" },
      el("h2", { id: "h-odznaka" }, "Odznaka Partnera"),
      el("p", {}, "Odznaka jest dostępna po spełnieniu wszystkich kryteriów programu Partner #TuBijeAED."));
  }
  const wariantRadio = (nazwa, wart, etykieta, zaznaczony) => el("div", { class: "opcja" },
    el("input", { type: "radio", name: nazwa, id: `${nazwa}-${wart}`, value: wart, checked: zaznaczony }),
    el("label", { for: `${nazwa}-${wart}` }, etykieta));
  const podglad = el("div", { class: "karta", id: "odznaka-podglad", style: "display:inline-block" });
  const obraz = el("img", { alt: ALT_ODZNAKI, id: "odznaka-img" });
  podglad.append(obraz);
  const kod = el("textarea", { id: "odznaka-kod", readonly: true, rows: "4", "aria-describedby": "kod-pomoc" });
  const status_ = el("p", { id: "kod-status", role: "status", class: "maly" });
  const odswiez = () => {
    const w = $('input[name="wariant"]:checked').value;
    const r = $('input[name="rozmiar"]:checked').value;
    obraz.setAttribute("src", adresOdznaki(id, w, r));
    obraz.parentElement.style.background = w === "ciemna" ? "var(--kolor-tekst)" : "var(--kolor-tlo)";
    kod.value = kodStopki(id, w, r);
  };
  const sek = el("section", { class: "karta karta--akcent", "aria-labelledby": "h-odznaka" },
    el("h2", { id: "h-odznaka" }, "Odznaka do stopki strony"),
    status === "WYGASŁY" ? el("p", {}, plakietka("Odznaka jest szara z napisem „wygasła”", "uwaga")) : null,
    el("p", {}, "Osadź odznakę w stopce swojej strony. Odznaka prowadzi do publicznej weryfikacji statusu na tym portalu, więc nikt nie może jej użyć bez pokrycia."),
    el("div", { class: "pole-wiersz" },
      el("fieldset", {}, el("legend", {}, "Wariant"), wariantRadio("wariant", "jasna", "Jasna (na jasne tło)", true), wariantRadio("wariant", "ciemna", "Ciemna (na ciemne tło)", false)),
      el("fieldset", {}, el("legend", {}, "Rozmiar"), wariantRadio("rozmiar", "mala", "Mała", true), wariantRadio("rozmiar", "pelna", "Pełna", false))),
    el("h3", {}, "Podgląd"), podglad,
    el("div", { class: "pole" },
      el("label", { for: "odznaka-kod" }, "Kod do stopki (HTML)"),
      kod,
      el("p", { id: "kod-pomoc", class: "podpowiedz" }, "Skopiuj kod i wklej go w stopce strony instytucji.")),
    el("div", { class: "rzad" },
      el("button", { type: "button", class: "przycisk", on: { click: () => kopiuj(kod.value, status_, kod) } }, "Skopiuj kod do stopki"),
      el("a", { class: "przycisk przycisk--drugi", href: `/partner.html?id=${encodeURIComponent(id)}` }, "Zobacz publiczną weryfikację")),
    status_);
  sek.addEventListener("change", odswiez);
  queueMicrotask(odswiez);
  return sek;
}

async function szczegoly(kont, id) {
  let inst, partner = null, zbiory = [];
  try {
    const odp = await pobierz(`${API_14}/institutions/${encodeURIComponent(id)}`);
    inst = plaski(odp.data ?? odp);
    inst.id = (odp.data ?? odp).id ?? id;
  } catch (e) { pokazBlad(kont, e, e.status === 404 ? "Nie znaleziono takiej instytucji" : "Nie udało się wczytać instytucji"); return; }
  const [p, z] = await Promise.allSettled([
    pobierz(`${API_PARTNERZY}/${encodeURIComponent(id)}`),
    pobierz(`${API_14}/datasets`, { instytucja: id, per_page: 50 }),
  ]);
  if (p.status === "fulfilled") partner = p.value; else if (inst.partner) partner = inst.partner;
  if (z.status === "fulfilled") zbiory = lista(z.value).map(plaski);
  const nazwa = inst.title || inst.nazwa || `Instytucja ${id}`;
  tytulStrony(nazwa);
  $("#instytucja-okruszek").textContent = nazwa;
  const status = partner ? partner.status : "BRAK";

  wstaw(kont,
    el("h1", {}, nazwa),
    el("p", {}, plakietkaPartnera(status), " ", el("span", { class: "tekst-drugorzedny" }, opisWaznosci(partner))),
    el("section", { class: "karta", "aria-labelledby": "h-dane" },
      el("h2", { id: "h-dane" }, "Dane instytucji"),
      el("dl", { class: "opis" },
        el("dt", {}, "Typ"), el("dd", {}, TYP_INSTYTUCJI[inst.institution_type || inst.typ] || tekst(inst.institution_type || inst.typ)),
        inst.regon ? [el("dt", {}, "REGON"), el("dd", {}, inst.regon)] : null,
        inst.website || inst.www ? [el("dt", {}, "Strona WWW"), el("dd", {}, el("a", { href: inst.website || inst.www }, inst.website || inst.www))] : null,
        inst.email ? [el("dt", {}, "E-mail"), el("dd", {}, el("a", { href: `mailto:${inst.email}` }, inst.email))] : null)),
    el("h2", { id: "h-zbiory" }, "Zbiory tego dostawcy"),
    z.status === "rejected"
      ? el("div", { class: "komunikat komunikat--blad" }, `Nie udało się wczytać zbiorów: ${z.reason.message}`)
      : zbudujTabele({
        opis: `Zbiory dostawcy: ${nazwa}`,
        pusty: "Ten dostawca nie opublikował jeszcze zbiorów. Za dane nie odpowiada tu nikt – instytucja może dołączyć w panelu dostawcy.",
        kolumny: [
          { naglowek: "Zbiór", naglowekWiersza: true, wartosc: (d) => el("a", { href: `/zbior.html?id=${encodeURIComponent(d.id)}` }, tekst(d.title)) },
          { naglowek: "Zasoby", klasa: "liczba", wartosc: (d) => formatLiczba(d.resources_count ?? 0) },
          { naglowek: "Wykaz AED", wartosc: (d) => (d.is_aggregated_list ? plakietka("Wykaz zbiorczy", "ok") : "–") },
          { naglowek: "Zmodyfikowano", wartosc: (d) => formatData(d.modified) },
        ],
        wiersze: zbiory,
      }),
    el("h2", { id: "h-partner" }, "Program Partner #TuBijeAED"),
    el("p", {}, "Kryteria statusu Partnera (sprawdzane automatycznie na podstawie wykazu zbiorczego):"),
    partner ? kryteriaLista(partner.kryteria) : el("p", { class: "tekst-drugorzedny" }, "Nie udało się pobrać statusu Partnera."),
    sekcjaOdznaki(id, partner));
}

async function init() {
  const kont = $("#instytucja-tresc");
  ladowanie(kont);
  const id = param("id");
  if (id) await szczegoly(kont, id); else await listaInstytucji(kont);
}
init();
