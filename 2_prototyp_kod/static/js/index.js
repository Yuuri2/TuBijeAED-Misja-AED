/* index.html – krótkie statystyki wykazu (opcjonalne; strona jest kompletna także bez nich). */
import { pobierz, API_14, plaski } from "./api.js";
import { $, el, wstaw, formatLiczba, formatData } from "./ui.js";

async function start() {
  const kont = $("#statystyki-start");
  if (!kont) return;
  try {
    const odp = await pobierz(`${API_14}/aed-aggregated`);
    const w = plaski(odp.data ?? odp);
    wstaw(kont, el("dl", { class: "statystyki" },
      el("div", { class: "statystyka" }, el("dt", {}, "Rekordów w wykazie"), el("dd", {}, formatLiczba(w.liczba_rekordow))),
      el("div", { class: "statystyka" }, el("dt", {}, "Dostawców danych"), el("dd", {}, formatLiczba(w.liczba_dostawcow))),
      el("div", { class: "statystyka" }, el("dt", {}, "Ostatnie scalenie"), el("dd", {}, formatData(w.utworzono)))));
  } catch {
    wstaw(kont, el("p", { class: "tekst-drugorzedny" }, "Statystyki wykazu będą widoczne po jego zbudowaniu."));
  }
}
start();
