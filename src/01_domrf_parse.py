"""
T4–T5. Сборка списка сданных домов Санкт-Петербурга из выгрузок ДОМ.РФ.

Вход:
  data/raw/domrf/list_c{класс}_p{страница}.json — постраничный список сданных домов СПб
      (сохранён вручную из браузера; фильтры API: place=78, objStatus=2 «Сдан», objClass=1..4)
  data/raw/domrf/card_{objId}.json — карточки домов, которые API пропустил в постраничном списке (сохранены вручную)
  data/raw/domrf/map_class{1..4}.json — точки всех сданных домов РФ по классам (для проверки полноты)
  data/interim/osm_admin.csv — границы города и районов из OpenStreetMap (результат 03_osm_extract.py)
Выход:
  data/processed/domrf_all.csv — все сданные дома СПб (жилые и нежилые) с классом, годом ввода, районом
  data/processed/zk.csv        — выборка исследования: жилые дома, введённые в 2021–2025 гг.
  data/processed/01_domrf_report.txt — отчёт: сколько было, сколько отброшено и почему
  data/processed/domrf_missing_ids.txt — дома, которых нет в списке (сбой пагинации), — их карточки сохранить вручную

Класс дома берётся из официального фильтра ДОМ.РФ (objClass), а не из текста описания.
Текст описания (aiDescription, сгенерирован ИИ) используется только для проверки, что номер класса понят верно.
"""
import csv, glob, json, re, sys
from collections import Counter
from pathlib import Path
from shapely import wkt as swkt
from shapely.geometry import Point
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/domrf"
OUT = ROOT / "data/processed"; OUT.mkdir(parents=True, exist_ok=True)
CLASS_NAME = {1: "Типовой", 2: "Комфорт", 3: "Бизнес", 4: "Элитный"}   # проверяется ниже по тексту описаний
CLASS_WORD = {1: "типов", 2: "комфорт", 3: "бизнес", 4: "элит"}
YEAR_FROM, YEAR_TO = 2021, 2025
csv.field_size_limit(sys.maxsize)

rep = []
def log(s=""):
    print(s); rep.append(s)

def clean_name(s):
    """'Жилой комплекс «INKERI»' -> 'INKERI'."""
    s = (s or "").strip()
    m = re.search(r"[«\"]([^»\"]+)[»\"]", s)
    return (m.group(1) if m else s).strip()

# ---------- 1. Список: склеиваем страницы ----------
rows, totals = [], {}
for f in sorted(RAW.glob("list_c*_p*.json")):
    c = int(re.search(r"list_c(\d)_", f.name).group(1))
    d = json.loads(f.read_text(encoding="utf-8"))["data"]
    totals[c] = d["total"]
    for o in d["list"]:
        o["_class"] = c
        rows.append(o)
log(f"ДОМ.РФ, сданные дома СПб (place=78, objStatus=2). Файлов страниц: {len(list(RAW.glob('list_c*_p*.json')))}")
log(f"Строк в страницах: {len(rows)}; total по API: {sum(totals.values())} ({totals})")

# дубли: при сортировке по умолчанию API отдаёт часть домов на двух страницах, а часть — ни на одной
seen, uniq = set(), []
for o in rows:
    if o["objId"] in seen: continue
    seen.add(o["objId"]); uniq.append(o)
log(f"Дублей (один дом на двух страницах): {len(rows) - len(uniq)} -> уникальных домов: {len(uniq)}")

# ---------- 1б. Карточки пропущенных домов: приводим к формату списка ----------
# класс в карточке — текстом (objLkClassDesc); переводим в код и сверяем с файлами карты ниже
NAME_TO_CODE = {v: k for k, v in CLASS_NAME.items()}
cards = sorted(RAW.glob("card_*.json"))
for f in cards:
    x = json.loads(f.read_text(encoding="utf-8"))["data"]
    if x["id"] in seen: continue
    dev = x.get("developer") or {}
    addr = x.get("address")
    uniq.append({
        "objId": x["id"], "hobjId": x.get("hobjId"),
        "objCommercNm": x.get("complexShortNm") or x.get("nameObj") or "",
        "developer": {"groupName": dev.get("developerGroupName") or "",
                      "shortName": dev.get("devShortNm") or dev.get("shortName") or ""},
        "shortAddr": addr if isinstance(addr, str) else "",
        "latitude": float(x["objLkLatitude"]) if x.get("objLkLatitude") else None,
        "longitude": float(x["objLkLongitude"]) if x.get("objLkLongitude") else None,
        "objReady100PercDt": x.get("objReady100PercDt"), "objElemLivingCnt": x.get("objElemLivingCnt"),
        "objSquareLiving": x.get("objSquareLiving"), "objFloorMax": x.get("floorMax"),
        "buildType": "Жилое" if "Многоквартирный" in (x.get("objTypeDesc") or "Многоквартирный дом") else "Нежилое",
        "residentialBuildings": x.get("residentialBuildings"), "objPublDt": x.get("objPublDt"),
        "_class": NAME_TO_CODE[x["objLkClassDesc"]], "_src": "card",
    })
    seen.add(x["id"])
log(f"Карточек пропущенных домов: {len(cards)} -> всего уникальных домов: {len(uniq)}")

# ---------- 2. Проверка расшифровки классов по тексту описаний ----------
log("\nПроверка номера класса по тексту описания (aiDescription): доля описаний, где упомянут ожидаемый класс")
for c in sorted(CLASS_NAME):
    sub = [o for o in uniq if o["_class"] == c and o.get("_src") != "card"]
    txt = [(o.get("aiDescription") or "").lower() for o in sub]
    with_any = [t for t in txt if any(w in t for w in CLASS_WORD.values())]
    hit = sum(CLASS_WORD[c] in t for t in with_any)
    log(f"  objClass={c} -> «{CLASS_NAME[c]}»: домов {len(sub)}, класс упомянут в {len(with_any)}, из них ожидаемый — {hit}")

# ---------- 3. Районы по границам OSM ----------
city, districts = None, []
with open(ROOT / "data/interim/osm_admin.csv", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        g = swkt.loads(r["wkt"])
        if r["admin_level"] == "4": city = prep(g)
        elif r["name"]: districts.append((r["name"], prep(g)))
def district_of(lat, lon):
    p = Point(lon, lat)
    for name, g in districts:
        if g.contains(p): return name
    return ""

# ---------- 4. Таблица всех сданных домов ----------
COLS = ["obj_id", "hobj_id", "zk_name", "developer_group", "developer", "address", "lat", "lon", "district",
        "class_code", "class_name", "ready_date", "ready_year", "flats", "living_area_m2", "floors_max",
        "build_type", "residential_buildings", "publ_date", "source"]
out = []
for o in uniq:
    dev = o.get("developer") or {}
    lat, lon = o.get("latitude"), o.get("longitude")
    rd = o.get("objReady100PercDt") or ""
    out.append({
        "obj_id": o["objId"], "hobj_id": o.get("hobjId", ""),
        "zk_name": clean_name(o.get("objCommercNm")),
        "developer_group": dev.get("groupName") or "", "developer": dev.get("shortName") or "",
        "address": o.get("shortAddr") or o.get("objAddr") or "",
        "lat": lat, "lon": lon, "district": district_of(lat, lon) if lat and lon else "",
        "class_code": o["_class"], "class_name": CLASS_NAME[o["_class"]],
        "ready_date": rd, "ready_year": rd[:4],
        "flats": o.get("objElemLivingCnt", ""), "living_area_m2": o.get("objSquareLiving", ""),
        "floors_max": o.get("objFloorMax", ""), "build_type": o.get("buildType", ""),
        "residential_buildings": o.get("residentialBuildings", ""), "publ_date": o.get("objPublDt", ""),
        "source": o.get("_src", "list"),
    })
def write(path, data):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader(); w.writerows(data)
write(OUT / "domrf_all.csv", out)

# ---------- 5. Выборка исследования ----------
log(f"\nОтбор выборки (из {len(out)} уникальных домов):")
step = out
def keep(cond, why):
    global step
    before = len(step); step = [r for r in step if cond(r)]
    log(f"  - {why}: отброшено {before - len(step)}, осталось {len(step)}")
keep(lambda r: r["build_type"] == "Жилое", "нежилые объекты (паркинги, отдельные коммерческие здания)")
keep(lambda r: r["ready_year"] != "", "нет даты ввода")
keep(lambda r: YEAR_FROM <= int(r["ready_year"]) <= YEAR_TO, f"ввод вне {YEAR_FROM}–{YEAR_TO} гг.")
keep(lambda r: r["district"] != "", "координаты вне районов СПб по границам OSM")
write(OUT / "zk.csv", step)

log(f"\nИтог: data/processed/zk.csv — {len(step)} жилых домов, введённых в {YEAR_FROM}–{YEAR_TO} гг.")
log(f"  ЖК (уникальных названий): {len({r['zk_name'] for r in step})}; квартир: {sum(int(r['flats'] or 0) for r in step):,}".replace(",", " "))
log("  По классам (дома / квартиры):")
for c in sorted(CLASS_NAME):
    s = [r for r in step if r["class_code"] == c]
    log(f"    {CLASS_NAME[c]:9s} {len(s):5d} / {sum(int(r['flats'] or 0) for r in s):7d}")
log("  По годам ввода: " + ", ".join(f"{y}: {n}" for y, n in sorted(Counter(r['ready_year'] for r in step).items())))
log("  По районам: " + ", ".join(f"{d}: {n}" for d, n in Counter(r['district'] for r in step).most_common()))

# ---------- 6. Полнота: сравнение с файлами карты ----------
in_list = {r["obj_id"] for r in out}
missing = []
for c in sorted(CLASS_NAME):
    d = json.loads((RAW / f"map_class{c}.json").read_text(encoding="utf-8"))["data"]
    pts = d["list"] if isinstance(d, dict) else d
    spb = [p for p in pts if p.get("latitude") and city.contains(Point(p["longitude"], p["latitude"]))]
    miss = [p["objId"] for p in spb if p["objId"] not in in_list]
    wrong = [r["obj_id"] for r in out if r["source"] == "card" and r["class_code"] != c and r["obj_id"] in {p["objId"] for p in spb}]
    if wrong: log(f"  ! класс карточки не совпал с файлом карты (класс {c}): {wrong}")
    missing += [(c, i) for i in miss]
log(f"\nПолнота: в файлах карты внутри границы СПб есть домов, которых нет в списке: {len(missing)}")
with open(OUT / "domrf_missing_ids.txt", "w", encoding="utf-8") as fh:
    for c, i in missing: fh.write(f"{c}\t{i}\n")
log("  (их id — в data/processed/domrf_missing_ids.txt; часть может быть домами Ленобласти у самой границы)")

(OUT / "01_domrf_report.txt").write_text("\n".join(rep) + "\n", encoding="utf-8")
