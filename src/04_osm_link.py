"""
T6. Привязка объектов OpenStreetMap («арендаторов») к сданным домам ДОМ.РФ.

Вход:  data/processed/zk.csv            — 793 жилых дома СПб, введённых в 2021–2025 гг. (01_domrf_parse.py)
       data/interim/osm_buildings.csv   — контуры многоэтажных зданий OSM (03_osm_extract.py)
       data/interim/osm_pois.csv        — точки «арендаторов» OSM: amenity / shop / leisure / healthcare / office / craft
Выход: data/processed/house_osm_match.csv — какой контур OSM соответствует дому ДОМ.РФ и насколько надёжно
       data/processed/poi_links.csv       — пары «дом × объект OSM» с категорией и расстоянием (уровни «внутри» и «окружение»)
       data/processed/zk_categories.csv   — по каждому дому: число объектов по категориям внутри дома и в радиусе 500 м
       data/processed/04_osm_link_report.txt

Как работает:
 1. Переводим градусы в метры (локальная плоская проекция вокруг центра СПб; погрешность по городу < 1%).
 2. Дом ДОМ.РФ → контур здания OSM: здание, внутри которого лежит точка дома; если такого нет —
    ближайшее здание не дальше MATCH_M метров. Качество сверяем: этажность OSM vs этажность ДОМ.РФ.
 3. «Внутри ЖК» = объект OSM внутри контура дома или не дальше INSIDE_M метров от него
    (точку магазина в OSM часто ставят у входа, снаружи контура). Считается только для домов
    с НАДЁЖНЫМ контуром (reliable): контур найден и его этажность не расходится с ДОМ.РФ больше чем на 2 эт.
    (если этажности в OSM нет — контур считаем надёжным). 31.10: порог снижен с 30 до 10 м, круг 50 м
    для домов без контура убран — ручная сверка с Яндекс Картами показала, что в центре 30 м захватывают
    соседние здания и через дорогу, а при неверном контуре арендаторы чужие.
 4. «Окружение» = объекты в радиусе ENV_M метров от точки дома (включая «внутренние»).
 5. Категории арендаторов — по таблице тегов ниже (CATEGORY_RULES); объекты-«не арендаторы»
    (банкоматы, постаматы, терминалы и т. п.) исключаются.
Чувствительность к порогам (10 / 30 / 50 м) — в отчёте.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from shapely import wkt as swkt
from shapely.geometry import Point
from shapely.ops import transform
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent.parent
INT, OUT = ROOT / "data/interim", ROOT / "data/processed"
MATCH_M, INSIDE_M, FALLBACK_M, ENV_M = 50, 10, 50, 500
LAT0, LON0 = 59.94, 30.31
KX, KY = 111320 * np.cos(np.radians(LAT0)), 110574      # метров в градусе долготы / широты на широте СПб

def to_m(lon, lat):
    return (np.asarray(lon) - LON0) * KX, (np.asarray(lat) - LAT0) * KY

rep = []
def log(s=""):
    print(s); rep.append(str(s))

# ---------------- категории арендаторов ----------------
CAT = {
    "food":     "Общепит",
    "grocery":  "Продукты",
    "pharmacy": "Аптеки",
    "medical":  "Медицина",
    "beauty":   "Красота (beauty)",
    "fitness":  "Фитнес и спорт",
    "kids_edu": "Детские и образование",
    "pickup":   "Пункты выдачи заказов",
    "services": "Бытовые и финансовые услуги",
    "office":   "Офисы",
    "retail":   "Непродовольственная торговля",
    "vacant":   "Пустует",
    "other":    "Прочее",
}
FOOD = {"restaurant", "cafe", "fast_food", "bar", "pub", "food_court", "ice_cream", "biergarten", "hookah_lounge"}
GROCERY = {"supermarket", "convenience", "greengrocer", "butcher", "bakery", "pastry", "confectionery", "alcohol",
           "beverages", "seafood", "dairy", "deli", "farm", "frozen_food", "cheese", "tea", "coffee", "wine",
           "chocolate", "health_food", "spices", "food", "water", "nuts", "pasta"}
MEDICAL_A = {"clinic", "doctors", "dentist", "hospital"}
BEAUTY = {"beauty", "hairdresser", "cosmetics", "massage", "tattoo", "perfumery", "nails"}
FITNESS = {"fitness_centre", "sports_centre", "dance", "sauna", "tanning_salon"}
KIDS = {"kindergarten", "childcare", "school", "language_school", "music_school", "dancing_school", "driving_school",
        "training", "prep_school", "college", "university", "art_school"}
SERVICES_A = {"bank", "post_office", "bureau_de_change", "money_transfer", "payment_centre", "veterinary", "car_rental"}
SERVICES_S = {"laundry", "dry_cleaning", "tailor", "shoe_repair", "copyshop", "travel_agency", "pawnbroker", "photo",
              "ticket", "funeral_directors", "rental", "repair", "money_lender", "pet_grooming", "locksmith", "storage_rental"}
NOT_TENANT_A = {"atm", "payment_terminal", "parcel_locker", "post_locker", "lounger", "chair", "smoking_area",
                "photo_booth", "compressed_air", "drinking_water", "dressing_room", "security_booth", "vehicle_ramp",
                "checkpoint", "binoculars", "ferry_terminal", "bicycle_rental", "kick-scooter_rental", "taxi",
                "bus_station", "water_point", "telephone", "vending_machine", "fuel", "car_wash", "place_of_worship",
                "fire_station", "police", "townhall", "courthouse", "dormitory", "marketplace", "parking"}
NOT_TENANT_S = {"mall", "kiosk", "department_store"}   # «контейнеры» и киоски, а не помещения в доме

def categorize(r):
    a, s, l, h, o, c = (r["amenity"], r["shop"], r["leisure"], r["healthcare"], r["office"], r["craft"])
    if s == "vacant" or r["disused"]:
        return "vacant"
    if a in FOOD: return "food"
    if a == "pharmacy" or h == "pharmacy": return "pharmacy"
    if a in MEDICAL_A or (h and h != "pharmacy"): return "medical"
    if a in KIDS or o in ("tutoring", "educational_institution"): return "kids_edu"
    if a in SERVICES_A: return "services"
    if a == "coworking_space": return "office"
    if a in NOT_TENANT_A: return None
    if s:
        if s in NOT_TENANT_S: return None
        if s in GROCERY: return "grocery"
        if s in BEAUTY: return "beauty"
        if s == "outpost": return "pickup"
        if s in SERVICES_S: return "services"
        return "retail"
    if l in FITNESS or a == "dojo": return "fitness"
    if o == "студия_красоты": return "beauty"
    if o: return "office"
    if c: return "services"
    if a: return "other"
    return None

# ---------------- 1. данные ----------------
csv_kw = dict(dtype=str, keep_default_na=False)
zk = pd.read_csv(OUT / "zk.csv")
pois = pd.read_csv(INT / "osm_pois.csv", **csv_kw)
pois["cat"] = pois.apply(categorize, axis=1)
log(f"Объектов OSM в рамке СПб: {len(pois)}; из них «не арендаторы» (банкоматы, постаматы и т. п.) исключены: {pois.cat.isna().sum()}")
pois = pois[pois.cat.notna()].reset_index(drop=True)
pois["poi_key"] = pois.osm_type + pois.osm_id
px, py = to_m(pois.lon.astype(float), pois.lat.astype(float))
poi_pts = [Point(x, y) for x, y in zip(px, py)]
poi_tree = STRtree(poi_pts)
log(f"Объектов-арендаторов: {len(pois)}")
log("  по категориям: " + ", ".join(f"{CAT[k]} {v}" for k, v in pois.cat.value_counts().items()))

b = pd.read_csv(INT / "osm_buildings.csv", **csv_kw)
proj = lambda x, y, z=None: to_m(x, y)
b_geom = [transform(proj, swkt.loads(w)) for w in b.wkt]
b_tree = STRtree(b_geom)
log(f"Контуров зданий OSM: {len(b)}")

# ---------------- 2. дом → контур OSM ----------------
zx, zy = to_m(zk.lon, zk.lat)
prec = zk.lat.astype(str).str.split(".").str[1].str.len()
match = []
for i in range(len(zk)):
    p = Point(zx[i], zy[i])
    hit = [j for j in b_tree.query(p, predicate="intersects")]
    how, dist = "inside", 0.0
    if not hit:
        near = b_tree.query(p, predicate="dwithin", distance=MATCH_M)
        if len(near):
            d = [b_geom[j].distance(p) for j in near]
            hit, how, dist = [near[int(np.argmin(d))]], "nearest", float(min(d))
        else:
            hit, how, dist = [], "none", np.nan
    j = hit[0] if hit else None
    match.append({"obj_id": zk.obj_id[i], "coord_decimals": int(prec[i]), "match": how, "match_dist_m": round(dist, 1),
                  "bld_idx": j, "bld_osm": (b.osm_type[j] + b.osm_id[j]) if j is not None else "",
                  "bld_type": b.building[j] if j is not None else "",
                  "bld_levels": b["building:levels"][j] if j is not None else "",
                  "bld_addr": (b["addr:street"][j] + " " + b["addr:housenumber"][j]).strip() if j is not None else ""})
m = pd.DataFrame(match)
m = m.merge(zk[["obj_id", "floors_max"]], on="obj_id")
m["levels_ok"] = np.where(m.bld_levels.str.isdigit(),
                          (pd.to_numeric(m.bld_levels, errors="coerce") - m.floors_max).abs() <= 2, np.nan)
m["bld_shared_n"] = m.groupby("bld_osm").obj_id.transform("count").where(m.bld_osm != "", 0)
m["footprint"] = np.where(m.match == "none", "point", "osm")
m["reliable"] = (m.footprint == "osm") & (m.levels_ok != 0)        # NaN (нет этажности в OSM) — надёжный

log()
log("Дом ДОМ.РФ → контур здания OSM:")
for k, v in m.match.value_counts().items():
    log(f"  {k:8s} {v:4d} ({v/len(m):.0%})")
log(f"  точность координат ДОМ.РФ: 4 знака (≈10 м) — {(m.coord_decimals>=4).sum()}, 3 знака (≈100 м) — "
    f"{(m.coord_decimals==3).sum()}, 2 знака (≈1 км) — {(m.coord_decimals<=2).sum()}")
lv = m[m.levels_ok.notna()]
log(f"  проверка этажностью: у {len(lv)} совпавших контуров в OSM есть этажность; совпадает с ДОМ.РФ (±2 эт.) — "
    f"{lv.levels_ok.astype(bool).sum()} ({lv.levels_ok.astype(bool).mean():.0%})")
log(f"  один контур OSM на несколько домов ДОМ.РФ (одна точка на весь ЖК/очередь): домов {int((m.bld_shared_n>1).sum())}")
log(f"  надёжный контур (найден и этажность не противоречит): {int(m.reliable.sum())} домов из {len(m)}; "
    f"исключены: без контура {int((m.footprint == 'point').sum())}, этажность расходится {int((m.levels_ok == 0).sum())}")

# ---------------- 3. объекты внутри / рядом ----------------
links = []
for i, r in m.iterrows():
    p = Point(zx[i], zy[i])
    shape = b_geom[int(r.bld_idx)] if r.footprint == "osm" else p
    thr = 50 if r.footprint == "osm" else FALLBACK_M          # 50 — максимум для анализа чувствительности
    for j in poi_tree.query(shape, predicate="dwithin", distance=max(thr, 0.01)):
        links.append((r.obj_id, j, round(shape.distance(poi_pts[j]), 1), round(p.distance(poi_pts[j]), 1)))
    for j in poi_tree.query(p, predicate="dwithin", distance=ENV_M):
        links.append((r.obj_id, j, np.nan, round(p.distance(poi_pts[j]), 1)))
L = (pd.DataFrame(links, columns=["obj_id", "pidx", "dist_bld_m", "dist_point_m"])
       .sort_values("dist_bld_m").drop_duplicates(["obj_id", "pidx"]))
L = L.merge(m[["obj_id", "footprint", "reliable"]], on="obj_id")
L["inside"] = L.reliable & (L.dist_bld_m <= INSIDE_M)
L["env500"] = L.dist_point_m <= ENV_M
P = pois[["poi_key", "cat", "amenity", "shop", "leisure", "healthcare", "office", "craft", "name", "brand"]]
L = L.join(P, on="pidx").drop(columns="pidx")
L.to_csv(OUT / "poi_links.csv", index=False)

# ---------------- 4. таблица «дом × категории» ----------------
cats = list(CAT)
ins = L[L.inside].pivot_table(index="obj_id", columns="cat", values="poi_key", aggfunc="count").reindex(columns=cats)
env = L[L.env500].pivot_table(index="obj_id", columns="cat", values="poi_key", aggfunc="count").reindex(columns=cats)
ins.columns = ["in_" + c for c in cats]; env.columns = ["env_" + c for c in cats]
out = zk.merge(m.drop(columns=["bld_idx", "floors_max"]), on="obj_id").set_index("obj_id").join(ins).join(env)
out[ins.columns.tolist() + env.columns.tolist()] = out[ins.columns.tolist() + env.columns.tolist()].fillna(0).astype(int)
tenant_in = [c for c in ins.columns if c != "in_vacant"]
out["in_total"] = out[tenant_in].sum(axis=1)
out["env_total"] = out[[c for c in env.columns if c != "env_vacant"]].sum(axis=1)
out.reset_index().to_csv(OUT / "zk_categories.csv", index=False)
m.drop(columns="bld_idx").to_csv(OUT / "house_osm_match.csv", index=False)

# ---------------- 5. отчёт ----------------
log()
log(f"Пар «дом × объект»: внутри ЖК (≤{INSIDE_M} м от надёжного контура) — {int(L.inside.sum())}, в радиусе {ENV_M} м — {int(L.env500.sum())}")
u_in = L[L.inside].drop_duplicates("poi_key")
log(f"Уникальных объектов «внутри ЖК»: {len(u_in)} (один объект может попасть к соседним корпусам одного ЖК)")
rel = out[out.reliable]
log(f"Домов с надёжным контуром, у которых внутри есть хотя бы один арендатор OSM: {(rel.in_total>0).sum()} из {len(rel)} ({(rel.in_total>0).mean():.0%})")
log()
log("Чувствительность к порогу «внутри» (уникальные объекты, только дома с надёжным контуром):")
osm_l = L[L.reliable]
for t in (0, 10, 30, 50):
    log(f"  ≤{t:2d} м: {osm_l[osm_l.dist_bld_m <= t].poi_key.nunique()}")
log()
log("Предварительно (без выводов!): уникальные объекты «внутри ЖК» по классам, доли категорий:")
cls = L[L.inside].merge(zk[["obj_id", "class_name"]], on="obj_id").drop_duplicates(["class_name", "poi_key"])
t = pd.crosstab(cls.cat, cls.class_name).reindex(columns=["Элитный", "Бизнес", "Комфорт", "Типовой"])
share = (t / t.drop(index="vacant", errors="ignore").sum() * 100).round(1)
t.index = [CAT[i] for i in t.index]; share.index = t.index
log("  объектов:\n" + t.to_string())
log("  доля от арендаторов, %:\n" + share.to_string())
(OUT / "04_osm_link_report.txt").write_text("\n".join(rep), encoding="utf-8")
print("\nГотово: house_osm_match.csv, poi_links.csv, zk_categories.csv, 04_osm_link_report.txt")
