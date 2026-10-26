"""
T6 (часть 1). Извлечение данных OpenStreetMap по Санкт-Петербургу из файла Geofabrik.

Вход:  data/raw/osm/northwestern-fed-district-*.osm.pbf  (выгрузка Geofabrik, СЗФО)
Выход: data/interim/
  osm_pois.csv        — точки «арендаторов»: amenity / shop / leisure / healthcare / office / craft
                        (узлы + полигоны → центр), с названием и адресом
  osm_buildings.csv   — жилые/многоэтажные здания (контуры в WKT) + этажность, адрес, start_date
  osm_landuse_res.csv — жилые кварталы (landuse=residential) с названием — часто это и есть ЖК
  osm_admin.csv       — границы: город (admin_level=4) и районы СПб (admin_level=5), WKT

Ограничение по рамке: 59.60–60.26 с. ш., 29.40–30.80 в. д. (весь СПб с Кронштадтом, Колпино,
Пушкиным, Зеленогорском; заодно ближние районы Ленобласти — их отрежем позже по границе города).

Как работает: два прохода по файлу (pyosmium). Первый собирает мультиполигоны-отношения,
второй — координаты узлов (индекс на диске, чтобы не упереться в память) и сами объекты.
"""
import csv, glob, sys, time
from pathlib import Path
import osmium

ROOT = Path(__file__).resolve().parent.parent
PBF = sorted(glob.glob(str(ROOT / "data/raw/osm/*.osm.pbf")))[-1]
OUT = ROOT / "data/interim"; OUT.mkdir(parents=True, exist_ok=True)
S, N, W, E = 59.60, 60.26, 29.40, 30.80
POI_KEYS = ("amenity", "shop", "leisure", "healthcare", "office", "craft")
LEISURE_OK = {"fitness_centre", "sports_centre", "dance", "sauna", "playground_indoor", "amusement_arcade"}
RES_BUILDINGS = {"apartments", "residential", "dormitory"}
wkt = osmium.geom.WKTFactory()

def inbox(lat, lon): return S <= lat <= N and W <= lon <= E

def is_poi(tags):
    for k in POI_KEYS:
        v = tags.get(k)
        if v:
            if k == "leisure" and v not in LEISURE_OK: continue
            if k == "amenity" and v in ("parking", "parking_space", "bench", "waste_basket", "parking_entrance",
                                        "bicycle_parking", "recycling", "waste_disposal", "shelter", "fountain",
                                        "drinking_water", "post_box", "vending_machine", "telephone", "clock",
                                        "toilets", "charging_station", "motorcycle_parking", "grave_yard",
                                        "hunting_stand", "loading_dock", "grit_bin", "letter_box", "bbq"):
                continue
            return True
    return False

def tagd(tags, keys): return {k: tags.get(k, "") for k in keys}
POI_COLS = ["osm_type", "osm_id", "lat", "lon", "amenity", "shop", "leisure", "healthcare", "office", "craft",
            "name", "brand", "addr:street", "addr:housenumber", "level", "opening_hours", "disused"]
B_COLS = ["osm_type", "osm_id", "lat", "lon", "building", "building:levels", "building:flats", "start_date",
          "name", "addr:street", "addr:housenumber", "wkt"]
L_COLS = ["osm_type", "osm_id", "lat", "lon", "name", "start_date", "wkt"]
A_COLS = ["osm_id", "admin_level", "name", "wkt"]

class H(osmium.SimpleHandler):
    def __init__(s, fp, fb, fl, fa):
        super().__init__(); s.fp, s.fb, s.fl, s.fa = fp, fb, fl, fa; s.n = [0, 0, 0, 0]
    def node(s, n):
        if not n.tags or not n.location.valid(): return
        lat, lon = n.location.lat, n.location.lon
        if inbox(lat, lon) and is_poi(n.tags):
            d = tagd(n.tags, POI_COLS[4:]); d["disused"] = n.tags.get("disused", "") or n.tags.get("disused:shop", "")
            s.fp.writerow({"osm_type": "n", "osm_id": n.id, "lat": round(lat, 7), "lon": round(lon, 7), **d}); s.n[0] += 1
    def area(s, a):
        t = a.tags
        is_admin = t.get("boundary") == "administrative" and t.get("admin_level") in ("4", "5")
        b, lu = t.get("building"), t.get("landuse")
        poi = is_poi(t)
        want_b = b and (b in RES_BUILDINGS or (t.get("building:levels", "").isdigit() and int(t["building:levels"]) >= 4))
        want_l = lu == "residential" and t.get("name")
        if not (is_admin or poi or want_b or want_l): return
        try:
            ring = next(iter(a.outer_rings()))
            pts = [(nd.location.lat, nd.location.lon) for nd in ring]
        except Exception:
            return
        lat = sum(p[0] for p in pts) / len(pts); lon = sum(p[1] for p in pts) / len(pts)
        if is_admin:
            if t.get("admin_level") == "4" and t.get("name") != "Санкт-Петербург": return
            if not inbox(lat, lon): return
            try: g = wkt.create_multipolygon(a)
            except Exception: return
            s.fa.writerow({"osm_id": a.orig_id(), "admin_level": t.get("admin_level"), "name": t.get("name", ""), "wkt": g}); s.n[3] += 1
            return
        if not inbox(lat, lon): return
        otype = "w" if a.from_way() else "r"
        if poi:
            d = tagd(t, POI_COLS[4:]); d["disused"] = t.get("disused", "")
            s.fp.writerow({"osm_type": otype, "osm_id": a.orig_id(), "lat": round(lat, 7), "lon": round(lon, 7), **d}); s.n[0] += 1
        if want_b or want_l:
            try: g = wkt.create_multipolygon(a)
            except Exception: return
            if want_b:
                s.fb.writerow({"osm_type": otype, "osm_id": a.orig_id(), "lat": round(lat, 7), "lon": round(lon, 7),
                               **tagd(t, B_COLS[4:11]), "wkt": g}); s.n[1] += 1
            if want_l:
                s.fl.writerow({"osm_type": otype, "osm_id": a.orig_id(), "lat": round(lat, 7), "lon": round(lon, 7),
                               "name": t.get("name"), "start_date": t.get("start_date", ""), "wkt": g}); s.n[2] += 1

if __name__ == "__main__":
    t0 = time.time(); print("Файл:", PBF, flush=True)
    files = [open(OUT / f, "w", newline="", encoding="utf-8") for f in
             ("osm_pois.csv", "osm_buildings.csv", "osm_landuse_res.csv", "osm_admin.csv")]
    ws = [csv.DictWriter(f, fieldnames=c) for f, c in zip(files, (POI_COLS, B_COLS, L_COLS, A_COLS))]
    for w in ws: w.writeheader()
    h = H(*ws)
    mp = osmium.area.AreaManager()
    print("Проход 1: отношения-мультиполигоны…", flush=True)
    osmium.apply(osmium.io.Reader(PBF), mp.first_pass_handler())
    print(f"  готово за {time.time()-t0:.0f} с", flush=True)
    idx_path = ROOT / "data/interim/_nodes.idx"
    idx = osmium.index.create_map(f"sparse_file_array,{idx_path}")
    lh = osmium.NodeLocationsForWays(idx); lh.ignore_errors()
    print("Проход 2: узлы, линии, полигоны…", flush=True)
    osmium.apply(osmium.io.Reader(PBF), lh, h, mp.second_pass_handler(h))
    for f in files: f.close()
    print(f"Готово за {time.time()-t0:.0f} с. POI: {h.n[0]}, зданий: {h.n[1]}, кварталов: {h.n[2]}, границ: {h.n[3]}", flush=True)
    print("DONE", flush=True)
