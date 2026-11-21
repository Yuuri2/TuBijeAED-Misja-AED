from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import requests
import io
import math
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

app = FastAPI(title="AED.gov Hub - Integrator Danych Ratujących Życie")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AED_DATABASE = [
    {
        "id_aed": "UMW-AED-001",
        "nazwa_dysponenta": "Urząd Miasta Stołecznego Warszawy",
        "identyfikator_dysponenta": "5252248481",
        "typ_dysponenta": "JST",
        "wojewodztwo": "mazowieckie",
        "miejscowosc": "Warszawa",
        "adres": "pl. Bankowy 3/5, 00-950",
        "szerokosc_geo": 52.24285,
        "dlugosc_geo": 21.00214,
        "lokalizacja_szczegolowa": "Wejście główne B, parter przy portierni",
        "dostepnosc_typ": "godziny_otwarcia",
        "godziny_dostepnosci": "Pn-Pt 08:00-16:00",
        "czy_zamkniete": "NIE",
        "instrukcja_dostepu": "Dostęp swobodny w godzinach pracy urzędu",
        "status_urzadzenia": "sprawne",
        "status_weryfikacji": "ZWERYFIKOWANY_DYSPONENT",
        "zrodlo": "Oficjalny rejestr JST (dane.gov.pl)",
        "data_aktualizacji": "2026-11-21T12:00:00Z"
    },
    {
        "id_aed": "PKP-AED-104",
        "nazwa_dysponenta": "Polskie Koleje Państwowe S.A.",
        "identyfikator_dysponenta": "5250000251",
        "typ_dysponenta": "Przedsiebiorstwo",
        "wojewodztwo": "slaskie",
        "miejscowosc": "Sosnowiec",
        "adres": "ul. 3 Maja 16, 41-200",
        "szerokosc_geo": 50.27852,
        "dlugosc_geo": 19.12684,
        "lokalizacja_szczegolowa": "Hala główna dworca kolejowego przy kasach biletowych",
        "dostepnosc_typ": "24_7",
        "godziny_dostepnosci": "24/7",
        "czy_zamkniete": "NIE",
        "instrukcja_dostepu": "Kapsuła otwarta, alarm dźwiękowy przy otwarciu",
        "status_urzadzenia": "sprawne",
        "status_weryfikacji": "ZWERYFIKOWANY_DYSPONENT",
        "zrodlo": "Oficjalny rejestr PKP S.A. (dane.gov.pl)",
        "data_aktualizacji": "2026-11-21T14:30:00Z"
    },
    {
        "id_aed": "KPRM-AED-002",
        "nazwa_dysponenta": "Kancelaria Prezesa Rady Ministrów",
        "identyfikator_dysponenta": "5261645000",
        "typ_dysponenta": "Administracja_rzadowa",
        "wojewodztwo": "mazowieckie",
        "miejscowosc": "Warszawa",
        "adres": "Al. Ujazdowskie 1/3, 00-583",
        "szerokosc_geo": 52.21941,
        "dlugosc_geo": 21.02431,
        "lokalizacja_szczegolowa": "Biuro Przepustek przy wejściu głównym",
        "dostepnosc_typ": "24_7",
        "godziny_dostepnosci": "24/7",
        "czy_zamkniete": "TAK_OCHRONA",
        "instrukcja_dostepu": "Dostępne natychmiast u funkcjonariusza SOP na stanowisku ochrony 24/7",
        "status_urzadzenia": "sprawne",
        "status_weryfikacji": "ZWERYFIKOWANY_DYSPONENT",
        "zrodlo": "Oficjalny rejestr KPRM (dane.gov.pl)",
        "data_aktualizacji": "2026-11-21T15:00:00Z"
    }
]

def distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/v1/aed")
def get_all_aed():
    return {"count": len(AED_DATABASE), "items": AED_DATABASE}

@app.post("/api/v1/harvest-osm")
def harvest_from_osm(city: str = Form("Sosnowiec")):
    query = f"""
    [out:json][timeout:15];
    area["name"="{city}"]["admin_level"~"6|7|8"]->.searchArea;
    node["emergency"="defibrillator"](area.searchArea);
    out body;
    """
    try:
        resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=15)
        data = resp.json()
        elements = data.get("elements", [])
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": f"Błąd połączenia z Overpass API: {str(e)}"})

    added = 0
    duplicates = 0
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for el in elements:
        lat = el.get("lat")
        lon = el.get("lon")
        tags = el.get("tags", {})
        if not lat or not lon:
            continue

        is_dup = any(distance_meters(lat, lon, item["szerokosc_geo"], item["dlugosc_geo"]) < 20 for item in AED_DATABASE)
        if is_dup:
            duplicates += 1
            continue

        AED_DATABASE.append({
            "id_aed": f"OSM-{el.get('id')}",
            "nazwa_dysponenta": tags.get("operator", "Brak oficjalnego dysponenta (Społeczność OSM)"),
            "identyfikator_dysponenta": "BRAK_WERYFIKACJI",
            "typ_dysponenta": "NGO_Inne",
            "wojewodztwo": "nieokreślone",
            "miejscowosc": city,
            "adres": f"{tags.get('addr:street', 'Brak ulicy')} {tags.get('addr:housenumber', '')}".strip(),
            "szerokosc_geo": round(lat, 6),
            "dlugosc_geo": round(lon, 6),
            "lokalizacja_szczegolowa": tags.get("defibrillator:location", tags.get("description", "Brak opisu szczegółowego w OSM")),
            "dostepnosc_typ": "24_7" if tags.get("opening_hours") == "24/7" else "ograniczona",
            "godziny_dostepnosci": tags.get("opening_hours", "Nieznane"),
            "czy_zamkniete": "TAK_KLUCZ" if tags.get("locked") == "yes" else "NIE",
            "instrukcja_dostepu": "Wymaga potwierdzenia przez zarządcę obiektu",
            "status_urzadzenia": "sprawne",
            "status_weryfikacji": "NIEZWERYFIKOWANY_OSM",
            "zrodlo": "OpenStreetMap (Overpass API)",
            "data_aktualizacji": now_iso
        })
        added += 1

    return {
        "message": f"Zakończono pobieranie z OpenStreetMap dla miasta: {city}",
        "fetched": len(elements),
        "added": added,
        "duplicates_skipped": duplicates
    }

@app.post("/api/v1/upload-institution")
async def upload_institution_file(
    file: UploadFile = File(...),
    nazwa_dysponenta: str = Form(...),
    nip_regon: str = Form(...),
    typ_dysponenta: str = Form("JST")
):
    content = await file.read()
    try:
        if file.filename.endswith(".xlsx"):
            excel_file = pd.ExcelFile(io.BytesIO(content))
            df = pd.read_excel(io.BytesIO(content), sheet_name="Dane_przykladowe" if "Dane_przykladowe" in excel_file.sheet_names else 0)
        elif file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            return JSONResponse(status_code=400, content={"error": "Dozwolone formaty odczytywalne maszynowo: .xlsx lub .csv"})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Nie udało się odczytać pliku: {str(e)}"})

    required_cols = ["miejscowosc", "szerokosc_geo", "dlugosc_geo", "lokalizacja_szczegolowa"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return JSONResponse(status_code=422, content={
            "error": "Plik niezgodny ze wzorcem AED.gov.pl!",
            "missing_columns": missing,
            "hint": "Pobierz wzorzec_danych_aed.xlsx i uzupełnij wymagane kolumny."
        })

    warnings = []
    imported = 0
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for idx, row in df.iterrows():
        try:
            lat = float(row["szerokosc_geo"])
            lon = float(row["dlugosc_geo"])
            if not (49.0 <= lat <= 54.9 and 14.1 <= lon <= 24.2):
                warnings.append(f"Wiersz {idx+2}: Współrzędne ({lat}, {lon}) poza granicami Polski – pominięto.")
                continue
        except ValueError:
            warnings.append(f"Wiersz {idx+2}: Nieprawidłowy format współrzędnych – pominięto.")
            continue

        czy_zamkniete = str(row.get("czy_zamkniete", "NIE")).strip()
        if czy_zamkniete not in ["NIE", "TAK_KLUCZ", "TAK_KOD", "TAK_OCHRONA"]:
            warnings.append(f"Wiersz {idx+2}: Brak informacji czy AED jest zamknięte na klucz – ustawiono domyślnie 'NIE'.")
            czy_zamkniete = "NIE"

        record = {
            "id_aed": str(row.get("id_aed", f"{nip_regon[:4]}-AED-{idx+1:03d}")),
            "nazwa_dysponenta": nazwa_dysponenta,
            "identyfikator_dysponenta": nip_regon,
            "typ_dysponenta": typ_dysponenta,
            "wojewodztwo": str(row.get("wojewodztwo", "mazowieckie")),
            "miejscowosc": str(row["miejscowosc"]),
            "adres": f"{row.get('ulica', '')} {row.get('nr_budynku', '')}, {row.get('kod_pocztowy', '')}".strip(", "),
            "szerokosc_geo": round(lat, 6),
            "dlugosc_geo": round(lon, 6),
            "lokalizacja_szczegolowa": str(row["lokalizacja_szczegolowa"]),
            "dostepnosc_typ": str(row.get("dostepnosc_typ", "24_7")),
            "godziny_dostepnosci": str(row.get("godziny_dostepnosci", "24/7")),
            "czy_zamkniete": czy_zamkniete,
            "instrukcja_dostepu": str(row.get("instrukcja_dostepu", "")),
            "status_urzadzenia": str(row.get("status_urzadzenia", "sprawne")),
            "status_weryfikacji": "ZWERYFIKOWANY_DYSPONENT",
            "zrodlo": f"Zweryfikowany dostawca: {nazwa_dysponenta} (NIP/REGON: {nip_regon})",
            "data_aktualizacji": now_iso
        }

        AED_DATABASE[:] = [
            item for item in AED_DATABASE
            if not (item["status_weryfikacji"] == "NIEZWERYFIKOWANY_OSM" and distance_meters(lat, lon, item["szerokosc_geo"], item["dlugosc_geo"]) < 25)
        ]
        AED_DATABASE.append(record)
        imported += 1

    return {
        "message": f"Zaimportowano {imported} zweryfikowanych punktów AED dla podmiotu {nazwa_dysponenta}.",
        "imported": imported,
        "warnings": warnings
    }

@app.get("/api/v1/export/csv")
def export_csv():
    df = pd.DataFrame(AED_DATABASE)
    csv_data = df.to_csv(index=False, encoding="utf-8-sig")
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ogolnopolski_rejestr_aed_danegov.csv"}
    )

@app.get("/api/v1/export/geojson")
def export_geojson():
    features = []
    for item in AED_DATABASE:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [item["dlugosc_geo"], item["szerokosc_geo"]]
            },
            "properties": item
        })
    return {"type": "FeatureCollection", "features": features}

@app.get("/api/v1/export/harvester-xml")
def export_harvester_xml():
    ns = "urn:otwarte-dane:harvester:1.13"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}datasets")
    dataset = ET.SubElement(root, "dataset", status="published")

    ET.SubElement(dataset, "extIdent").text = "aed-gov-hub-ogolnopolski-rejestr-defibrylatorow-2026"

    title = ET.SubElement(dataset, "title")
    ET.SubElement(title, "polish").text = "Ogólnopolski rejestr defibrylatorów AED – zbiór zintegrowany i zweryfikowany"
    ET.SubElement(title, "english").text = "National Registry of AED Defibrillators – integrated and verified dataset"

    desc = ET.SubElement(dataset, "description")
    ET.SubElement(desc, "polish").text = (
        "Ustandaryzowany, otwarty zbiór danych o lokalizacji, dostępności godzinowej oraz statusie technicznym "
        "automatycznych defibrylatorów zewnętrznych (AED) w Polsce, integrujący zweryfikowane zasoby dysponentów publicznych i prywatnych."
    )

    ET.SubElement(dataset, "updateFrequency").text = "daily"
    categories = ET.SubElement(dataset, "categories")
    ET.SubElement(categories, "category").text = "HEAL"

    resources = ET.SubElement(dataset, "resources")
    for fmt, url_path, res_title in [
        ("csv", "http://localhost:8080/api/v1/export/csv", "Rejestr AED – format tabelaryczny CSV (UTF-8)"),
        ("geojson", "http://localhost:8080/api/v1/export/geojson", "Rejestr AED – dane przestrzenne GeoJSON")
    ]:
        res = ET.SubElement(resources, "resource", status="published")
        ET.SubElement(res, "extIdent").text = f"aed-resource-{fmt}-2026"
        ET.SubElement(res, "url").text = url_path
        r_title = ET.SubElement(res, "title")
        ET.SubElement(r_title, "polish").text = res_title
        ET.SubElement(res, "availability").text = "remote"
        ET.SubElement(res, "dataDate").text = datetime.now().strftime("%Y-%m-%d")
        ET.SubElement(res, "hasDynamicData").text = "true"
        ET.SubElement(res, "hasHighValueData").text = "true"

    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(
        content=xml_str,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=harvester_import_aed_1_13.xml"}
    )