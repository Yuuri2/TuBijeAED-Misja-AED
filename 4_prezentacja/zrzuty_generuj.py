"""Zrzuty ekranu prototypu #TuBijeAED do prezentacji (Firefox headless + Marionette).

Wymaga: Firefox, działający serwer prototypu na świeżej bazie, np. (z katalogu 2_prototyp_kod):
    DB_PATH=/tmp/prez.sqlite ../.venv/bin/uvicorn app.main:app --port 8090
Uruchomienie (z katalogu repo):
    .venv/bin/python 4_prezentacja/zrzuty_generuj.py [--url http://localhost:8090] [--tylko nazwa1,nazwa2]
Wynik: 4_prezentacja/zrzuty/pelne/*.png (pełne strony, gęstość DPR=2, ok. 30 MB – katalog tymczasowy, poza
repozytorium) + zrzuty/kadry.json (współrzędne elementów w px CSS). Kadry (zrzuty/kadry/*.png) wycina z nich
generuj_prezentacje.py; potem katalog pelne/ można usunąć – prezentacja generuje się z samych kadrów.
Kolejność scenariuszy ma znaczenie (panel dostawcy zmienia dane) – pełny przebieg tylko na świeżej bazie.
"""
import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

TU = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TU)
ZRZUTY = os.path.join(TU, "zrzuty")
PELNE = os.path.join(ZRZUTY, "pelne")   # pełne zrzuty (duże, nie trafiają do repozytorium)
PRZYKLADY = os.path.join(REPO, "2_prototyp_kod", "static", "przyklady")
# pozycja „użytkownika” dla mapy: centrum Legionowa (dane demo)
GEO = (52.4040, 20.9300)
# gęstość pikseli zrzutów (2 = ostre zrzuty do PDF; szerokość strony nadal 1280 px CSS, telefon 390 px CSS)
DPR = 2


class Fx:
    """Minimalny klient Marionette."""

    def __init__(self, port=2829, w=1280, h=900):
        self.prof = tempfile.mkdtemp(prefix="fxprez")
        with open(os.path.join(self.prof, "user.js"), "w") as f:
            f.write(
                'user_pref("marionette.port", %d);\nuser_pref("geo.provider.testing", true);\n'
                'user_pref("geo.enabled", true);\n'
                'user_pref("geo.provider.network.url", "data:application/json,{\\"location\\":{\\"lat\\":%f,\\"lng\\":%f},\\"accuracy\\":20}");\n'
                'user_pref("permissions.default.geo", 1);\nuser_pref("network.proxy.type", 0);\n'
                'user_pref("layout.css.devPixelsPerPx", "%.1f");\n' % (port, GEO[0], GEO[1], DPR))
        self.p = subprocess.Popen(["firefox", "--headless", "--marionette", "--profile", self.prof, "--no-remote"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Marionette nie odpowiada")
        self.id = 0
        self._read()
        self.cmd("WebDriver:NewSession", {"capabilities": {}})
        self.size(w, h)

    def _read(self):
        buf = b""
        while b":" not in buf:
            buf += self.s.recv(1)
        n = int(buf.split(b":")[0])
        data = b""
        while len(data) < n:
            data += self.s.recv(n - len(data))
        return json.loads(data)

    def cmd(self, name, params=None):
        self.id += 1
        m = json.dumps([0, self.id, name, params or {}]).encode()
        self.s.sendall(str(len(m)).encode() + b":" + m)
        while True:
            r = self._read()
            if isinstance(r, list) and r[0] == 1 and r[1] == self.id:
                if r[2]:
                    raise RuntimeError(r[2])
                return r[3]

    def size(self, w, h):
        self.cmd("WebDriver:SetWindowRect", {"width": w, "height": h})

    def go(self, url, wait=3.0):
        self.cmd("WebDriver:Navigate", {"url": url})
        time.sleep(wait)

    def js(self, script, args=None):
        r = self.cmd("WebDriver:ExecuteScript", {"script": script, "args": args or []})
        return r.get("value") if isinstance(r, dict) else r

    def find(self, css):
        v = self.cmd("WebDriver:FindElement", {"using": "css selector", "value": css})["value"]
        return list(v.values())[0]

    def upload(self, css, path):
        self.cmd("WebDriver:ElementSendKeys", {"id": self.find(css), "text": path})

    def wait_no_loading(self, timeout=15):
        """Czeka, aż na stronie (lub w iframe #fr) nie będzie tekstu „Wczytywanie”."""
        for _ in range(int(timeout * 4)):
            t = self.js("const f=document.getElementById('fr');const d=f?f.contentDocument:document;"
                        "return d && d.body ? d.body.innerText : ''")
            if t and "Wczytywanie" not in t and "Ładowanie" not in t:
                return
            time.sleep(0.25)
        print("  ! nadal „Wczytywanie…”", file=sys.stderr)

    def rect(self, css):
        return self.js("const e=document.querySelector(arguments[0]);if(!e)return null;const r=e.getBoundingClientRect();"
                       "return [Math.round(r.left+scrollX),Math.round(r.top+scrollY),Math.round(r.width),Math.round(r.height)]",
                       [css])

    def shot(self, name):
        r = self.cmd("WebDriver:TakeScreenshot", {"full": True})
        with open(os.path.join(PELNE, name + ".png"), "wb") as f:
            f.write(base64.b64decode(r["value"]))
        print("  zrzut", name)

    def close(self):
        try:
            self.cmd("Marionette:Quit")
        except Exception:
            pass
        self.p.terminate()
        shutil.rmtree(self.prof, ignore_errors=True)


KADRY = {}


def kadr(nazwa, f, css, nad=0, pod=0):
    """Zapamiętuje prostokąt elementu (x, y, w, h) na zrzucie – do kadrowania w prezentacji."""
    r = f.rect(css)
    if r:
        KADRY.setdefault(nazwa, {})[css] = [r[0], max(0, r[1] - nad), r[2], r[3] + nad + pod]


def zaloguj(f, B, kto):
    f.go(B + "/admin/index.html", 3)
    f.js("[...document.querySelectorAll('#konta-lista button')].find(b=>b.textContent.includes(arguments[0])).click()", [kto])
    time.sleep(2.5)


# ------------------------------------------------------------------ scenariusze
def wykaz(f, B):
    f.go(B + "/wykaz-aed.html", 3)
    f.wait_no_loading()
    f.shot("01_wykaz")
    kadr("01_wykaz", f, "#sekcja-pominiete", nad=10, pod=10)
    kadr("01_wykaz", f, "#sekcja-dostawcy", nad=10, pod=10)


def api(f, B):
    f.go(B + "/api/1.4/aed-aggregated", 3)
    f.shot("09_api_json")
    f.go(B + "/docs", 5)
    f.shot("10_api_docs")
    r = f.js("const s=[...document.querySelectorAll('.opblock-tag-section')].find(e=>e.textContent.includes('/api/1.4/aed-aggregated'));"
             "if(!s)return null;const r=s.getBoundingClientRect();return [Math.round(r.left+scrollX),Math.round(r.top+scrollY),Math.round(r.width),Math.round(r.height)]")
    if r:
        KADRY.setdefault("10_api_docs", {})["api14"] = r


def dostawca(f, B):
    zaloguj(f, B, "Warszawy")
    # 1) harvester XML 1.14
    f.upload("#x-plik", os.path.join(PRZYKLADY, "harvester_1_14_przyklad.xml"))
    f.js("document.querySelector('#form-xml [type=submit]').click()")
    time.sleep(4)
    f.js("document.querySelector('#sekcja-harvester').scrollIntoView()")
    f.shot("05_harvester_xml")
    kadr("05_harvester_xml", f, "#sekcja-harvester", nad=10, pod=10)
    kadr("05_harvester_xml", f, "#sekcja-zbiory", nad=10, pod=10)
    # usuwamy zasób z importu, by pokazać ścieżkę z plikiem CSV (jeden zasób AED na dostawcę)
    print("  usuwanie zasobu z importu:", f.js("""
      return fetch('/api/admin/moje-zbiory',{headers:{'X-Demo-Konto':'6'}}).then(r=>r.json()).then(async d=>{
        const lista=(d.data||d.items||d); const out=[];
        for(const z of lista){for(const r of (z.zasoby||[])){const x=await fetch('/api/admin/zasoby/'+r.id,{method:'DELETE',headers:{'X-Demo-Konto':'6'}});out.push(r.id+':'+x.status)}}
        return out.join(',');})"""))
    zaloguj(f, B, "Warszawy")
    # 2) zasób z błędami
    sel = f.js("const s=document.querySelector('#z-zbior');return [...s.options].map(o=>o.value+'|'+o.text)")
    print("  zbiory:", sel)
    f.js("const s=document.querySelector('#z-zbior');s.value=[...s.options].filter(o=>o.value).pop().value;s.dispatchEvent(new Event('change'))")
    f.js("document.querySelector('#z-tytul').value='Lokalizacje AED – Warszawa (wzorzec #TuBijeAED)'")
    f.upload("#z-plik", os.path.join(PRZYKLADY, "aed_z_bledami.csv"))
    f.js("document.querySelector('#z-wykaz').checked=true")
    f.js("document.querySelector('#form-zasob [type=submit]').click()")
    time.sleep(4)
    f.js("document.querySelector('#zasob-wynik').scrollIntoView()")
    f.shot("03_dostawca_bledy")
    kadr("03_dostawca_bledy", f, "#zasob-wynik", nad=10, pod=10)
    kadr("03_dostawca_bledy", f, "#form-zasob", nad=60, pod=10)
    kadr("03_dostawca_bledy", f, "#sekcja-zbiory", nad=10, pod=10)
    # 3) poprawny plik – „Zaktualizuj”
    f.js("[...document.querySelectorAll('#moje-zbiory button')].find(b=>b.textContent.startsWith('Zaktualizuj')).click()")
    time.sleep(1.5)
    f.upload("#z-plik", os.path.join(PRZYKLADY, "aed_poprawny.csv"))
    f.js("document.querySelector('#z-wykaz').checked=true")
    f.js("document.querySelector('#form-zasob [type=submit]').click()")
    time.sleep(5)
    f.js("document.querySelector('#zasob-wynik').scrollIntoView()")
    f.shot("04_dostawca_poprawny")
    kadr("04_dostawca_poprawny", f, "#zasob-wynik", nad=10, pod=10)
    kadr("04_dostawca_poprawny", f, "#sekcja-zbiory", nad=10, pod=10)
    f.go(B + "/wykaz-aed.html", 3)
    f.wait_no_loading()
    f.shot("04b_wykaz_po")
    kadr("04b_wykaz_po", f, "#sekcja-dostawcy", nad=10, pod=10)
    kadr("04b_wykaz_po", f, "#h-stan", nad=10, pod=0)


def admin(f, B):
    zaloguj(f, B, "Administrator")
    f.js("document.querySelector('#przebuduj').click()")
    time.sleep(4)
    f.js("document.querySelector('#sekcja-admin').scrollIntoView()")
    f.wait_no_loading()
    f.shot("06_admin_historia")
    kadr("06_admin_historia", f, "#sekcja-admin", nad=10, pod=10)


def mapa(f, B):
    f.go(B + "/mapa.html", 4)
    f.js("document.querySelector('#znajdz').click()")
    time.sleep(6)
    f.shot("07_mapa_desktop")
    kadr("07_mapa_desktop", f, "#najblizsze-wynik", nad=10, pod=10)
    kadr("07_mapa_desktop", f, "#mapa", nad=10, pod=10)


def mapa_mobile(f, B):
    f.go(B + "/jury.html", 2)
    f.js("document.body.innerHTML='';document.body.style.margin='0';const i=document.createElement('iframe');i.id='fr';"
         "i.style.cssText='width:390px;height:2400px;border:0;display:block';i.src=arguments[0];document.body.append(i);",
         [B + "/mapa.html"])
    time.sleep(4)
    f.js("document.getElementById('fr').contentDocument.querySelector('#znajdz').click()")
    time.sleep(6)
    f.js("const i=document.getElementById('fr');i.style.height=Math.min(i.contentDocument.documentElement.scrollHeight,4000)+'px'")
    time.sleep(1)
    f.shot("08_mapa_mobile")
    # zostaw tylko „telefon” (iframe 390 px CSS)
    from PIL import Image
    pth = os.path.join(PELNE, "08_mapa_mobile.png")
    im = Image.open(pth)
    im.crop((0, 0, 390 * DPR, im.height)).save(pth)


def partner(f, B):
    f.go(B + "/partner.html?id=7", 3)
    f.wait_no_loading()
    f.shot("11_partner_aktywny")
    f.go(B + "/partner.html?id=8", 3)
    f.wait_no_loading()
    f.shot("11b_partner_wygasly")
    f.go(B + "/instytucja.html?id=7", 3)
    f.wait_no_loading()
    f.shot("11c_instytucja")


def asystent(f, B):
    f.go(B + "/asystent.html", 3)
    f.upload("#k-plik", os.path.join(PRZYKLADY, "gmina_stary_uklad_krosno.csv"))
    f.js("document.querySelector('#form-konwertuj [type=submit]').click()")
    time.sleep(4)
    f.js("document.querySelector('#konwertuj-wynik').scrollIntoView()")
    f.shot("12_asystent_konwersja")
    kadr("12_asystent_konwersja", f, "#konwertuj-wynik", nad=10, pod=10)
    kadr("12_asystent_konwersja", f, "#form-konwertuj", nad=70, pod=10)


SCENARIUSZE = [("wykaz", wykaz), ("api", api), ("dostawca", dostawca), ("admin", admin), ("mapa", mapa),
               ("mapa_mobile", mapa_mobile), ("partner", partner), ("asystent", asystent)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8090")
    ap.add_argument("--tylko", default="")
    a = ap.parse_args()
    os.makedirs(PELNE, exist_ok=True)
    plik_kadrow = os.path.join(ZRZUTY, "kadry.json")
    if os.path.exists(plik_kadrow):
        KADRY.update(json.load(open(plik_kadrow)))
    wybrane = set(filter(None, a.tylko.split(",")))
    f = Fx()
    try:
        for nazwa, fn in SCENARIUSZE:
            if wybrane and nazwa not in wybrane:
                continue
            print("scenariusz", nazwa)
            fn(f, a.url.rstrip("/"))
    finally:
        f.close()
        KADRY["_dpr"] = DPR
        json.dump(KADRY, open(plik_kadrow, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
