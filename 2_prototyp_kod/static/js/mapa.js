/* mapa.html – Mapa #TuBijeAED dla obywatela. Właściciel: Frontend.
   Zasady: lista tekstowa jest pełnoprawną alternatywą mapy; geolokalizacja ma fallback (miasto / klik na mapie);
   marker = kształt + kolor + symbol; „Zadzwoń 112” zawsze widoczny; OSM tylko jako warstwa „do weryfikacji”. */
import { pobierz, wyslij, API_MAPA, lista, plaski } from "./api.js";
import {
  bladPola, $, el, wstaw, wyczysc, ladowanie, pokazBlad, komunikat, tekst, formatOdleglosc, plakietka, plakietkaDostepnosci,
  adresRekordu, wspolrzedne, nazwaDostawcy, linkInstytucji, fokus, ZABEZPIECZENIE, DOSTEPNOSC_TYP, STATUS_URZADZENIA,
  tekstZeSlownika, formatLiczba,
} from "./ui.js";

const L = window.L; // Leaflet (może być niedostępny offline – wtedy działa lista i najbliższe AED)

const MIASTA = {
  Krosno: [49.6886, 21.7706], "Przemyśl": [49.7838, 22.7678], Marki: [52.3228, 21.105],
  Legionowo: [52.4017, 20.9262], Warszawa: [52.2297, 21.0122],
};
const NA_STRONE_LISTY = 12;

const stan = {
  mapa: null, pozycja: null, trybWskaz: false, punkty: [], osm: [], pokazOsm: false,
  warstwaWykaz: null, warstwaOsm: null, markerJa: null, ileNaLiscie: NA_STRONE_LISTY, markery: new Map(),
};

/* ---------- Rekordy ---------- */
function nazwaPunktu(r) {
  return [r.miejscowosc, [r.ulica, r.nr_budynku].filter(Boolean).join(" ")].filter(Boolean).join(", ") || r.lokalizacja_szczegolowa || "AED";
}
function rodzaj(r) { return r._osm ? "osm" : r.partner ? "partner" : "wykaz"; }
const OPIS_RODZAJU = {
  wykaz: "Zweryfikowany w wykazie (dostawca odpowiada za dane)",
  partner: "Dostawca z odznaką Partner #TuBijeAED",
  osm: "OSM – do weryfikacji (brak odpowiedzialnego dostawcy)",
};

function haversine(a, b) {
  const R = 6371000, rad = Math.PI / 180;
  const dLat = (b[0] - a[0]) * rad, dLon = (b[1] - a[1]) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

const IKONA = (plik, w, h, ax, ay) => (L ? L.icon({ iconUrl: `/brand/${plik}`, iconSize: [w, h], iconAnchor: [ax, ay], popupAnchor: [0, -(h - 6)] }) : null);
const IKONY = {
  wykaz: IKONA("marker-wykaz.svg", 32, 40, 16, 39),
  partner: IKONA("marker-partner.svg", 32, 40, 16, 38),
  osm: IKONA("marker-osm.svg", 28, 28, 14, 14),
};
const PLIKI_MARKEROW = { wykaz: "marker-wykaz.svg", partner: "marker-partner.svg", osm: "marker-osm.svg" };

/* Pozycja użytkownika: kropla (jedyny marker rysowany w CSS) */
function znacznikJa() { return el("div", { class: "znacznik znacznik--ja" }); }

/* ---------- Karty „najbliższe AED” ---------- */
function linkiNawigacji(r, poz, zGeo = true) {
  const c = wspolrzedne(r);
  if (!c) return null;
  const route = poz ? `${poz[0].toFixed(6)},${poz[1].toFixed(6)};${c[0]},${c[1]}` : `;${c[0]},${c[1]}`;
  const osm = `https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=${route}`;
  const geo = `geo:${c[0]},${c[1]}?q=${c[0]},${c[1]}(${encodeURIComponent("AED")})`;
  return el("div", { class: "rzad" },
    el("a", { class: "przycisk", href: osm, target: "_blank", rel: "noopener" }, "Prowadź",
      el("span", { class: "tylko-czytniki" }, ` do ${nazwaPunktu(r)} (OpenStreetMap, nowa karta)`)),
    zGeo ? el("a", { class: "przycisk przycisk--drugi", href: geo }, "Otwórz w aplikacji nawigacji") : null);
}

function karta(r, nr, poz) {
  const rodz = rodzaj(r);
  const zam = r.czy_zamkniete && r.czy_zamkniete !== "NIE";
  const statusUrz = r.status_urzadzenia ?? "nieznany";
  const odl = r.odleglosc_m;
  return el("li", { class: "karta wynik-aed" },
    el("div", { class: "wynik-aed__glowa" },
      el("h3", {}, `${nr}. ${nazwaPunktu(r)}`),
      Number.isFinite(Number(odl)) ? el("span", { class: "wynik-aed__odleglosc" }, formatOdleglosc(odl), el("span", { class: "tylko-czytniki" }, " od Ciebie")) : null),
    el("div", { class: "rzad" },
      plakietkaDostepnosci(r.dostepny_teraz ?? null),
      statusUrz === "sprawne" ? plakietka("Urządzenie sprawne", "ok")
        : plakietka(tekstZeSlownika(STATUS_URZADZENIA, statusUrz) + (statusUrz === "nieznany" ? " – sprawdź przy użyciu" : ""), "uwaga"),
      r.partner ? plakietka("Partner #TuBijeAED", "info") : null,
      zam ? plakietka("Szafka/pomieszczenie zamknięte", "uwaga") : null),
    el("dl", {},
      el("dt", {}, "Jak dostać się do urządzenia"),
      el("dd", {}, [r.lokalizacja_szczegolowa, r.instrukcja_dostepu].filter(Boolean).join(". ") || "Brak opisu – zadzwoń 112, dyspozytor pomoże."),
      el("dt", {}, "Dostępność"),
      el("dd", {}, [tekstZeSlownika(DOSTEPNOSC_TYP, r.dostepnosc_typ), r.godziny_dostepnosci].filter((x) => x && x !== "–").join(": ") || "Nieznana",
        zam ? ` · ${ZABEZPIECZENIE[r.czy_zamkniete] || r.czy_zamkniete}` : ""),
      el("dt", {}, "Adres"), el("dd", {}, adresRekordu(r) || "–"),
      el("dt", {}, "Za dane odpowiada"),
      el("dd", {}, nazwaDostawcy(r) ? linkInstytucji(r.instytucja_id, nazwaDostawcy(r)) : "Dostawca niewskazany",
        r.nazwa_dysponenta && r.nazwa_dysponenta !== nazwaDostawcy(r) ? ` (urządzenie należy do: ${r.nazwa_dysponenta})` : "",
        r.kontakt_dysponenta ? ` · kontakt: ${r.kontakt_dysponenta}` : "")),
    linkiNawigacji(r, poz),
    rodz === "osm" ? el("p", { class: "maly" }, "Dane z OpenStreetMap – nie są weryfikowane przez dostawcę.") : null);
}

function normalizuj(x) {
  const r = plaski(x);
  if (r.partner && typeof r.partner === "object") r.partner = r.partner.status === "AKTYWNY";
  return r;
}

async function szukajNajblizszych(poz) {
  const kont = $("#najblizsze-wynik");
  ladowanie(kont, "Szukam najbliższych defibrylatorów…");
  try {
    const odp = await pobierz(`${API_MAPA}/najblizsze`, { lat: poz[0].toFixed(6), lon: poz[1].toFixed(6), limit: 3 });
    const wyn = lista(odp).map(normalizuj);
    if (!wyn.length) {
      komunikat(kont, "uwaga", "Nie znaleziono AED w pobliżu",
        el("p", {}, "W wykazie nie ma jeszcze defibrylatora w tej okolicy. W nagłym wypadku zadzwoń 112."));
      $("#mapa-status").textContent = "Nie znaleziono defibrylatorów w pobliżu. Zadzwoń 112.";
      return;
    }
    const h = el("h3", { id: "najblizsze-h", tabindex: "-1" }, `Najbliższe AED (${wyn.length})`);
    wstaw(kont, h, el("ol", { class: "lista-czysta" }, wyn.map((r, i) => karta(r, i + 1, poz))));
    $("#mapa-status").textContent = `Znaleziono ${wyn.length} najbliższe AED. Najbliższe: ${nazwaPunktu(wyn[0])}, ${formatOdleglosc(wyn[0].odleglosc_m)}.`;
    fokus(h);
    if (stan.mapa && wyn[0] && wspolrzedne(wyn[0])) {
      stan.mapa.fitBounds(L.latLngBounds([poz, ...wyn.map(wspolrzedne).filter(Boolean)]), { padding: [40, 40], maxZoom: 17 });
    }
  } catch (e) {
    pokazBlad(kont, e, "Nie udało się wyszukać najbliższych AED");
    $("#mapa-status").textContent = "Błąd wyszukiwania. W nagłym wypadku zadzwoń 112.";
  }
}

/* ---------- Pozycja użytkownika ---------- */
function ustawPozycje(lat, lon, zrodlo) {
  stan.pozycja = [lat, lon];
  stan.ileNaLiscie = NA_STRONE_LISTY;
  if (stan.mapa) {
    if (stan.markerJa) stan.markerJa.remove();
    stan.markerJa = L.marker([lat, lon], {
      icon: L.divIcon({ className: "znacznik-wrap", html: znacznikJa(), iconSize: [28, 28], iconAnchor: [14, 26] }),
      title: "Twoja pozycja", alt: "Twoja pozycja", keyboard: false,
    }).addTo(stan.mapa);
    stan.mapa.setView([lat, lon], 15);
  }
  $("#pozycja-opis").textContent = `Twoja pozycja: ${lat.toFixed(4)}, ${lon.toFixed(4)} (${zrodlo}).`;
  szukajNajblizszych(stan.pozycja);
  rysujListe();
}

function znajdzMnie() {
  const przycisk = $("#znajdz");
  const status = $("#mapa-status");
  if (!("geolocation" in navigator)) {
    status.textContent = "Ta przeglądarka nie obsługuje geolokalizacji. Wpisz miasto albo wskaż miejsce na mapie.";
    pokazFallback(true);
    return;
  }
  przycisk.disabled = true;
  status.textContent = "Ustalam Twoją pozycję…";
  navigator.geolocation.getCurrentPosition(
    (p) => { przycisk.disabled = false; ustawPozycje(p.coords.latitude, p.coords.longitude, "geolokalizacja"); },
    (b) => {
      przycisk.disabled = false;
      const powod = b.code === 1 ? "Brak zgody na lokalizację." : "Nie udało się ustalić pozycji.";
      status.textContent = `${powod} Wpisz miasto albo wskaż miejsce na mapie.`;
      pokazFallback(true);
    },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
}

function pokazFallback(fokusuj) {
  const d = $("#fallback");
  d.open = true;
  if (fokusuj) $("#miasto").focus();
}

function szukajMiasta(e) {
  e.preventDefault();
  const wpis = $("#miasto").value.trim().toLocaleLowerCase("pl");
  const klucz = Object.keys(MIASTA).find((m) => m.toLocaleLowerCase("pl") === wpis);
  if (!klucz) {
    bladPola("miasto", `Nie znam miasta „${$("#miasto").value}” w danych demo. Wybierz z listy (${Object.keys(MIASTA).join(", ")}) albo wskaż miejsce na mapie.`);
    return;
  }
  bladPola("miasto", "");
  ustawPozycje(MIASTA[klucz][0], MIASTA[klucz][1], `środek miasta ${klucz}`);
}

function przelaczWskaz() {
  stan.trybWskaz = !stan.trybWskaz;
  const p = $("#wskaz");
  p.setAttribute("aria-pressed", String(stan.trybWskaz));
  p.textContent = stan.trybWskaz ? "Kliknij na mapie swoje miejsce (anuluj)" : "Wskaż swoją pozycję na mapie";
  $("#mapa-status").textContent = stan.trybWskaz ? "Tryb wskazywania: kliknij na mapie miejsce, w którym jesteś." : "Tryb wskazywania wyłączony.";
  if (stan.mapa) stan.mapa.getContainer().style.cursor = stan.trybWskaz ? "crosshair" : "";
}

/* ---------- Mapa i warstwy ---------- */
function popup(r) {
  const c = wspolrzedne(r);
  return el("div", {},
    el("strong", {}, nazwaPunktu(r)), el("br"),
    el("span", {}, OPIS_RODZAJU[rodzaj(r)]), el("br"),
    r.lokalizacja_szczegolowa ? el("span", {}, r.lokalizacja_szczegolowa) : null, r.lokalizacja_szczegolowa ? el("br") : null,
    nazwaDostawcy(r) ? el("span", {}, "Za dane odpowiada: ", linkInstytucji(r.instytucja_id, nazwaDostawcy(r))) : el("span", {}, "Brak odpowiedzialnego dostawcy"),
    c ? el("div", {}, el("a", { href: `https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=${stan.pozycja ? `${stan.pozycja[0]},${stan.pozycja[1]}` : ""};${c[0]},${c[1]}`, target: "_blank", rel: "noopener" }, "Prowadź (nowa karta)")) : null);
}

function dodajMarkery(warstwa, punkty) {
  warstwa.clearLayers();
  for (const r of punkty) {
    const c = wspolrzedne(r);
    if (!c) continue;
    const rod = rodzaj(r);
    const m = L.marker(c, {
      icon: IKONY[rod],
      title: `${nazwaPunktu(r)} – ${OPIS_RODZAJU[rod]}`, alt: `${nazwaPunktu(r)} – ${OPIS_RODZAJU[rod]}`,
      /* keyboard:false – 15+ markerów to 15+ tabstopów; pełną alternatywą jest lista tekstowa (przycisk „Pokaż na mapie”), do której prowadzi link „Pomiń mapę” (WCAG 2.1.1 spełnione listą, 2.4.3 – logiczna kolejność). */
      keyboard: false, riseOnHover: true,
    });
    m.bindPopup(() => popup(r));
    m.addTo(warstwa);
    stan.markery.set(r, m);
  }
}

function zainicjujMape() {
  const kont = $("#mapa");
  if (!L) {
    kont.removeAttribute("role");
    wstaw(kont, el("div", { class: "mapa-brak" }, komunikat(document.createElement("div"), "uwaga", "Mapa jest niedostępna",
      el("p", {}, "Nie udało się wczytać biblioteki mapy (brak połączenia z internetem?). Wszystkie funkcje działają dalej: użyj przycisku „Znajdź najbliższy AED” i listy tekstowej poniżej."))));
    kont.style.height = "auto";
    $("#warstwa-osm").disabled = true;
    return;
  }
  stan.mapa = L.map(kont, { zoomControl: true, keyboard: true }).setView([52.0, 19.4], 6);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "© współtwórcy <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>",
  }).addTo(stan.mapa);
  stan.warstwaWykaz = L.layerGroup().addTo(stan.mapa);
  stan.warstwaOsm = L.layerGroup();
  stan.mapa.on("click", (e) => {
    if (!stan.trybWskaz) return;
    przelaczWskaz();
    ustawPozycje(e.latlng.lat, e.latlng.lng, "wskazana na mapie");
  });
  let t;
  stan.mapa.on("moveend", () => { if (stan.pokazOsm) { clearTimeout(t); t = setTimeout(wczytajOsm, 500); } });
}

async function wczytajPunkty() {
  const kont = $("#lista-wynik");
  ladowanie(kont, "Wczytywanie punktów AED…");
  try {
    const odp = await pobierz(`${API_MAPA}/aed`);
    stan.punkty = lista(odp).map(normalizuj);
  } catch (e) {
    pokazBlad(kont, e, "Nie udało się wczytać punktów AED");
    $("#legenda-liczba").textContent = "";
    return;
  }
  $("#legenda-liczba").textContent = `W wykazie: ${formatLiczba(stan.punkty.length)} punktów.`;
  if (stan.mapa) {
    dodajMarkery(stan.warstwaWykaz, stan.punkty);
    const pkt = stan.punkty.map(wspolrzedne).filter(Boolean);
    if (pkt.length) stan.mapa.fitBounds(L.latLngBounds(pkt), { padding: [30, 30], maxZoom: 13 });
  }
  rysujListe();
}

async function wczytajOsm() {
  const status = $("#osm-status");
  if (!stan.pokazOsm) return;
  const b = stan.mapa ? stan.mapa.getBounds() : null;
  const parametry = b ? { bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map((x) => x.toFixed(5)).join(",") } : {};
  status.textContent = "Wczytywanie punktów OSM…";
  try {
    const odp = await pobierz(`${API_MAPA}/osm`, parametry);
    stan.osm = lista(odp).map(normalizuj).map((r) => ({ ...r, _osm: true }));
    status.textContent = stan.osm.length
      ? `Pokazano ${stan.osm.length} punktów OSM „do weryfikacji” w tym obszarze.`
      : "Brak punktów OSM w tym obszarze. Możesz pobrać dane OSM dla miasta (opcja poniżej).";
    if (stan.mapa) dodajMarkery(stan.warstwaOsm, stan.osm);
  } catch (e) {
    stan.osm = [];
    status.textContent = `Nie udało się wczytać warstwy OSM: ${e.message}`;
  }
  rysujListe();
}

function przelaczOsm(e) {
  stan.pokazOsm = e.target.checked;
  if (stan.mapa) {
    if (stan.pokazOsm) { stan.warstwaOsm.addTo(stan.mapa); } else { stan.warstwaOsm.remove(); }
  }
  if (stan.pokazOsm) wczytajOsm();
  else { stan.osm = []; $("#osm-status").textContent = "Warstwa OSM wyłączona."; rysujListe(); }
}

async function pobierzOsmDlaMiasta(e) {
  e.preventDefault();
  const miasto = $("#osm-miasto").value;
  const status = $("#osm-status");
  const przycisk = e.submitter;
  przycisk.disabled = true;
  status.textContent = `Pobieranie danych OSM dla: ${miasto}… (wymaga internetu, może potrwać)`;
  try {
    const fd = new FormData(); fd.set("miasto", miasto);
    await wyslij(`${API_MAPA}/osm/pobierz`, fd);
    status.textContent = `Pobrano dane OSM dla: ${miasto}.`;
    if (stan.pokazOsm) await wczytajOsm();
  } catch (err) { status.textContent = `Nie udało się pobrać danych OSM: ${err.message}`; }
  finally { przycisk.disabled = false; }
}

/* ---------- Lista tekstowa (alternatywa mapy) ---------- */
function rysujListe() {
  const kont = $("#lista-wynik");
  let punkty = [...stan.punkty, ...(stan.pokazOsm ? stan.osm : [])];
  if (stan.pozycja) {
    punkty = punkty.map((r) => {
      const c = wspolrzedne(r);
      return { ...r, _odl: c ? haversine(stan.pozycja, c) : Infinity, _orig: r };
    }).sort((a, b) => a._odl - b._odl);
  } else {
    punkty = punkty.map((r) => ({ ...r, _orig: r })).sort((a, b) => String(a.miejscowosc).localeCompare(String(b.miejscowosc), "pl"));
  }
  $("#lista-opis").textContent = stan.pozycja
    ? "Posortowano od najbliższego do Twojej pozycji."
    : "Posortowano alfabetycznie wg miejscowości. Użyj „Znajdź najbliższy AED”, aby posortować wg odległości.";
  if (!punkty.length) { wstaw(kont, el("p", {}, "Brak punktów do wyświetlenia.")); return; }
  const widoczne = punkty.slice(0, stan.ileNaLiscie);
  wstaw(kont,
    el("ul", { class: "lista-czysta lista-karty" }, widoczne.map((r) => {
      const rod = rodzaj(r);
      const m = stan.markery.get(r._orig);
      return el("li", {},
        el("h3", {}, nazwaPunktu(r)),
        el("p", { class: "rzad" },
          plakietka({ wykaz: "Zweryfikowany w wykazie", partner: "Partner #TuBijeAED", osm: "OSM – do weryfikacji" }[rod], rod === "osm" ? "uwaga" : rod === "partner" ? "info" : "ok"),
          r._odl !== undefined && Number.isFinite(r._odl) ? el("strong", {}, formatOdleglosc(r._odl)) : null),
        el("p", { class: "maly" },
          r.lokalizacja_szczegolowa ? `${r.lokalizacja_szczegolowa}. ` : "",
          nazwaDostawcy(r) ? ["Za dane odpowiada: ", linkInstytucji(r.instytucja_id, nazwaDostawcy(r)), ". "] : "Brak odpowiedzialnego dostawcy. ",
          r.godziny_dostepnosci ? `Godziny: ${r.godziny_dostepnosci}. ` : "",
          r.status_urzadzenia ? `Status: ${tekstZeSlownika(STATUS_URZADZENIA, r.status_urzadzenia)}.` : ""),
        el("div", { class: "rzad" },
          linkiNawigacji(r, stan.pozycja, false),
          m && stan.mapa ? el("button", { type: "button", class: "przycisk przycisk--drugi przycisk--maly", on: { click: () => { stan.mapa.setView(m.getLatLng(), 17); m.openPopup(); $("#mapa").scrollIntoView({ block: "center" }); } } },
            "Pokaż na mapie", el("span", { class: "tylko-czytniki" }, `: ${nazwaPunktu(r)}`)) : null));
    })),
    punkty.length > widoczne.length
      ? el("button", { type: "button", class: "przycisk przycisk--drugi", on: { click: () => { stan.ileNaLiscie += NA_STRONE_LISTY; rysujListe(); } } },
        `Pokaż więcej (${widoczne.length} z ${formatLiczba(punkty.length)})`)
      : el("p", { class: "maly tekst-drugorzedny" }, `Wyświetlono wszystkie punkty (${formatLiczba(punkty.length)}).`));
}

/* ---------- Legenda ---------- */
function rysujLegende() {
  const ul = $("#legenda");
  const miniatura = (rodz) => el("span", { style: "display:inline-flex;width:2rem;flex:none;justify-content:center" },
    el("img", { src: `/brand/${PLIKI_MARKEROW[rodz]}`, alt: "", width: "26" }));
  wstaw(ul,
    ...["wykaz", "partner", "osm"].map((r) => el("li", {}, miniatura(r),
      el("span", {}, el("strong", {}, { wykaz: "Okrągła pinezka z sercem", partner: "Kwadratowy dymek z ptaszkiem", osm: "Romb z przerywaną krawędzią i znakiem ?" }[r]),
        ` – ${OPIS_RODZAJU[r]}`))),
    el("li", {}, el("span", { "aria-hidden": "true", style: "display:inline-flex;width:2rem;flex:none;justify-content:center" }, znacznikJa()),
      el("span", {}, el("strong", {}, "Czerwona kropla"), " – Twoja pozycja")));
}

function init() {
  rysujLegende();
  zainicjujMape();
  $("#znajdz").addEventListener("click", znajdzMnie);
  $("#wskaz").addEventListener("click", przelaczWskaz);
  $("#formularz-miasto").addEventListener("submit", szukajMiasta);
  $("#warstwa-osm").addEventListener("change", przelaczOsm);
  $("#formularz-osm").addEventListener("submit", pobierzOsmDlaMiasta);
  const dl = $("#miasta-lista");
  for (const m of Object.keys(MIASTA)) dl.append(el("option", { value: m }));
  const sel = $("#osm-miasto");
  for (const m of Object.keys(MIASTA)) sel.append(el("option", { value: m }, m));
  wczytajPunkty();
}
init();
