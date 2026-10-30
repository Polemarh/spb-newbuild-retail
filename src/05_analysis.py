"""
T8. Анализ: кто занимает первые этажи новостроек СПб (сданы в 2021–2025) и отличается ли это по классам и районам.

Вход:  data/processed/zk_categories.csv  — дома ДОМ.РФ с привязкой к OSM (04_osm_link.py)
       data/processed/poi_links.csv      — пары «дом × объект OSM»
Выход: output/tables/*.csv                — таблицы для графиков и отчёта
       data/processed/05_analysis_report.txt

Главная проверка — правило из классификации бизнес-класса NF GROUP (обзор «Бизнес-класс СПб, I пол. 2026», стр. 7):
в бизнес-классе «нежелательны общепит и продуктовые». В ДОМ.РФ нет подкласса «бизнес лайт», поэтому сравниваем
группы «Бизнес + Элитный» (Б+Э) и «Комфорт + Типовой» (К+Т).

Решения:
 1. Единица — ЖК, а не дом: 338 домов делят один контур OSM, поэтому объект считаем один раз на ЖК.
    ЖК = название ДОМ.РФ; у 52 домов без названия — «застройщик + адрес».
 2. Доля категории = объекты категории / все арендаторы (без «Пустует»).
 3. 95% доверительный интервал — кластерный бутстрэп по ЖК (2 000 повторов, seed 2026): ЖК, а не объекты, независимы.
 4. Контроль «центр vs окраина»: Б+Э в среднем ближе к центру, где плотнее общепит.
    (а) сравнение внутри поясов удалённости от центра; (б) индекс «внутри ЖК / окружение 500 м»:
    насколько доля категории в ЖК выше или ниже, чем в его же окружении.
 5. Устойчивость: только дома, чья точка лежит внутри контура OSM (match=inside), и порог 10 м вместо 30 м.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC, TAB = ROOT / "data/processed", ROOT / "output/tables"
TAB.mkdir(parents=True, exist_ok=True)
CENTER = (59.9390, 30.3158)                      # Дворцовая площадь
KX, KY = 111320 * np.cos(np.radians(59.94)), 110574
ZONES = [(0, 8, "до 8 км"), (8, 15, "8–15 км"), (15, 99, "15 км и дальше")]
GROUP = {"Элитный": "Б+Э", "Бизнес": "Б+Э", "Комфорт": "К+Т", "Типовой": "К+Т"}
CLASSES = ["Элитный", "Бизнес", "Комфорт", "Типовой"]
CAT = {"food": "Общепит", "grocery": "Продукты", "pickup": "Пункты выдачи заказов", "retail": "Непрод. торговля",
       "beauty": "Красота", "medical": "Медицина", "pharmacy": "Аптеки", "services": "Бытовые и фин. услуги",
       "office": "Офисы", "kids_edu": "Детские и образование", "fitness": "Фитнес и спорт", "other": "Прочее"}
N_BOOT, SEED = 2000, 2026

rep = []
def log(s=""):
    print(s); rep.append(str(s))

# ---------------- данные ----------------
z = pd.read_csv(PROC / "zk_categories.csv")
z["zk"] = z.zk_name.fillna(z.developer.fillna("?") + " / " + z.address)
z["group"] = z.class_name.map(GROUP)
z["dc_km"] = np.hypot((z.lon - CENTER[1]) * KX, (z.lat - CENTER[0]) * KY) / 1000
z["zone"] = pd.cut(z.dc_km, [a for a, _, _ in ZONES] + [ZONES[-1][1]], labels=[n for _, _, n in ZONES], right=False)
L = pd.read_csv(PROC / "poi_links.csv")
L = L[L.cat != "vacant"].merge(z[["obj_id", "zk", "class_name", "group", "zone", "district", "match"]], on="obj_id")

def objects(level, max_d=None, houses=None):
    """Уникальные объекты на ЖК: level='inside' или 'env500'."""
    d = L[L[level]]
    if max_d is not None:
        d = d[d.dist_bld_m <= max_d]
    if houses is not None:
        d = d[d.obj_id.isin(houses)]
    return d.drop_duplicates(["zk", "poi_key"])

def shares(d, by):
    t = pd.crosstab(d.cat, d[by])
    return t, (t / t.sum() * 100)

def boot_share(d, cat, seed=SEED):
    """Доля категории в % и 95% ДИ, кластерный бутстрэп по ЖК."""
    per = d.assign(hit=d.cat == cat).groupby("zk").hit.agg(["sum", "count"])
    s, n = per["sum"].values, per["count"].values
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(per), (N_BOOT, len(per)))
    bs = s[idx].sum(1) / n[idx].sum(1) * 100
    return s.sum() / n.sum() * 100, np.percentile(bs, 2.5), np.percentile(bs, 97.5), per

def boot_diff(d, cat, seed=SEED):
    """Разница долей Б+Э − К+Т в п. п. и 95% ДИ (ЖК ресэмплим внутри каждой группы)."""
    rng = np.random.default_rng(seed)
    res = []
    for g in ("Б+Э", "К+Т"):
        per = d[d.group == g].assign(hit=lambda x: x.cat == cat).groupby("zk").hit.agg(["sum", "count"])
        s, n = per["sum"].values, per["count"].values
        idx = rng.integers(0, len(per), (N_BOOT, len(per)))
        res.append((s.sum() / n.sum() * 100, s[idx].sum(1) / n[idx].sum(1) * 100))
    diff = res[0][1] - res[1][1]
    return res[0][0] - res[1][0], np.percentile(diff, 2.5), np.percentile(diff, 97.5)

# ---------------- 1. выборка ----------------
log("1. ВЫБОРКА: жилые дома ДОМ.РФ, сданные в 2021–2025 гг.")
s = z.groupby("class_name").agg(домов=("obj_id", "count"), ЖК=("zk", "nunique"), квартир=("flats", "sum"),
                                 км_до_центра_медиана=("dc_km", "median")).reindex(CLASSES)
s.loc["Итого"] = [len(z), z.zk.nunique(), z.flats.sum(), z.dc_km.median()]
s["км_до_центра_медиана"] = s["км_до_центра_медиана"].round(1)
log(s.to_string())
s.to_csv(TAB / "t1_sample.csv")
log(f"  Пояса удалённости, домов: " + ", ".join(f"{k} {v}" for k, v in z.zone.value_counts(sort=False).items()))
cz = pd.crosstab(z.class_name, z.zone).reindex(CLASSES)
log(cz.to_string())
cz.to_csv(TAB / "t1_class_zone_n.csv")

# ---------------- 2. заполненность ----------------
log()
log("2. ДОЛЯ ДОМОВ С ХОТЯ БЫ ОДНИМ АРЕНДАТОРОМ OSM «ВНУТРИ ЖК» (≤30 м от контура)")
z["has"] = z.in_total > 0
fill = pd.DataFrame({"по классам": z.groupby("class_name").has.mean().reindex(CLASSES)})
log((fill * 100).round(0).astype(int).to_string())
fy = (z.groupby("ready_year").has.mean() * 100).round(0)
log("  по году ввода, %: " + ", ".join(f"{int(k)} — {int(v)}" for k, v in fy.items()))
fz = (pd.crosstab(z.class_name, z.zone, values=z.has, aggfunc="mean") * 100).round(0).reindex(CLASSES)
log("  по классу и поясу, %:\n" + fz.to_string())
fy.to_csv(TAB / "t2_fill_by_year.csv"); fz.to_csv(TAB / "t2_fill_by_class_zone.csv")

# ---------------- 3. структура арендаторов ----------------
I = objects("inside")
log()
log(f"3. СТРУКТУРА АРЕНДАТОРОВ «ВНУТРИ ЖК»: уникальных объектов (на ЖК) — {len(I)}, ЖК с арендаторами — {I.zk.nunique()}")
cnt, sh = shares(I, "class_name")
cnt, sh = cnt.reindex(columns=CLASSES), sh.reindex(columns=CLASSES)
cg, shg = shares(I, "group")
tab = pd.concat([sh, shg], axis=1).round(1)
tab.loc["Всего объектов, шт."] = list(cnt.sum()) + list(cg.sum())
tab.index = [CAT.get(i, i) for i in tab.index]
tab = tab.sort_values("К+Т", ascending=False)
log(tab.to_string())
tab.to_csv(TAB / "t3_structure_by_class.csv")
top = I.cat.value_counts(normalize=True).mul(100).round(1)
log("  все классы вместе, %: " + ", ".join(f"{CAT[k]} {v}" for k, v in top.items()))
top.rename(index=CAT).to_csv(TAB / "t3_structure_total.csv")

# ---------------- 4. главная проверка: общепит и продукты ----------------
log()
log("4. ПРОВЕРКА ПРАВИЛА «В БИЗНЕС-КЛАССЕ НЕЖЕЛАТЕЛЬНЫ ОБЩЕПИТ И ПРОДУКТЫ» (Б+Э vs К+Т), 95% ДИ — бутстрэп по ЖК")
rows = []
for cat in ("food", "grocery", "pickup", "retail"):
    for g in ("Б+Э", "К+Т"):
        v, lo, hi, per = boot_share(I[I.group == g], cat)
        rows.append({"категория": CAT[cat], "группа": g, "доля_%": round(v, 1), "ДИ_низ": round(lo, 1),
                     "ДИ_верх": round(hi, 1), "ЖК": len(per), "объектов": int(per["count"].sum())})
    dv, dlo, dhi = boot_diff(I, cat)
    rows.append({"категория": CAT[cat], "группа": "разница, п. п.", "доля_%": round(dv, 1),
                 "ДИ_низ": round(dlo, 1), "ДИ_верх": round(dhi, 1)})
main = pd.DataFrame(rows)
log(main.to_string(index=False))
main.to_csv(TAB / "t4_rule_check.csv", index=False)

# 4а. по поясам удалённости
log()
log("4а. КОНТРОЛЬ ЛОКАЦИИ: доли внутри поясов удалённости от центра (если объектов в группе ≥30)")
rows = []
for zone in [n for _, _, n in ZONES]:
    for cat in ("food", "grocery"):
        r = {"пояс": zone, "категория": CAT[cat]}
        for g in ("Б+Э", "К+Т"):
            d = I[(I.zone == zone) & (I.group == g)]
            r[g + "_объектов"] = len(d)
            r[g + "_%"] = round((d.cat == cat).mean() * 100, 1) if len(d) >= 30 else np.nan
        rows.append(r)
zt = pd.DataFrame(rows)
log(zt.to_string(index=False))
zt.to_csv(TAB / "t4a_by_zone.csv", index=False)

# 4б. индекс «внутри / окружение 500 м»
log()
log("4б. ИНДЕКС «ВНУТРИ ЖК / ОКРУЖЕНИЕ 500 м» (1,0 = как вокруг; <1 — в ЖК категории меньше, чем в его окружении)")
E = objects("env500")
_, she = shares(E, "group")
_, shi = shares(I, "group")
idx = pd.DataFrame({"внутри_Б+Э_%": shi["Б+Э"], "окружение_Б+Э_%": she["Б+Э"],
                    "внутри_К+Т_%": shi["К+Т"], "окружение_К+Т_%": she["К+Т"]})
idx["индекс_Б+Э"] = idx["внутри_Б+Э_%"] / idx["окружение_Б+Э_%"]
idx["индекс_К+Т"] = idx["внутри_К+Т_%"] / idx["окружение_К+Т_%"]
idx = idx.round(2).rename(index=CAT).sort_values("внутри_К+Т_%", ascending=False)
log(idx.to_string())
idx.to_csv(TAB / "t4b_inside_vs_env.csv")

# 4в. устойчивость
log()
log("4в. УСТОЙЧИВОСТЬ: доля общепита / продуктов, % (Б+Э | К+Т)")
strict = z.loc[z.match == "inside", "obj_id"]
with_fp = z.loc[z.footprint == "osm", "obj_id"]
big = I.groupby("zk").size().sort_values(ascending=False)
log(f"  концентрация: 5 крупнейших ЖК дают {big.head(5).sum() / len(I):.0%} объектов ({', '.join(big.head(5).index)})")
rows = []
for name, d in [("основной вариант (≤30 м, все дома)", I),
                ("порог 10 м", objects("inside", max_d=10)),
                ("без домов без контура OSM (круг 50 м)", objects("inside", houses=with_fp)),
                ("только дома с точкой внутри контура OSM", objects("inside", houses=strict)),
                ("без 5 крупнейших ЖК", I[~I.zk.isin(big.head(5).index)])]:
    r = {"вариант": name}
    for cat in ("food", "grocery"):
        for g in ("Б+Э", "К+Т"):
            dd = d[d.group == g]
            r[f"{CAT[cat]}_{g}"] = round((dd.cat == cat).mean() * 100, 1)
    r["объектов"] = len(d)
    rows.append(r)
rob = pd.DataFrame(rows)
log(rob.to_string(index=False))
rob.to_csv(TAB / "t4c_robustness.csv", index=False)

# ---------------- 5. районы ----------------
log()
log("5. РАЙОНЫ: арендаторы «внутри ЖК» на 1 000 квартир и доля домов с арендаторами (районы с ≥10 домами)")
dist = z.groupby("district").agg(домов=("obj_id", "count"), квартир=("flats", "sum"), домов_с_арендаторами=("has", "mean"),
                                  доля_БЭ=("group", lambda g: (g == "Б+Э").mean()))
dist["объектов_внутри"] = I.drop_duplicates("poi_key").groupby("district").size()
dist = dist.fillna({"объектов_внутри": 0})
dist["на_1000_кв"] = dist.объектов_внутри / dist.квартир * 1000
ds = I.drop_duplicates("poi_key").pipe(lambda d: pd.crosstab(d.district, d.cat, normalize="index") * 100)
for c in ("food", "grocery", "pickup"):
    dist[f"{CAT[c]}_%"] = ds.get(c)
dist["домов_с_арендаторами"] *= 100; dist["доля_БЭ"] *= 100
dist = dist.round(1).sort_values("на_1000_кв", ascending=False)
dist.to_csv(TAB / "t5_districts.csv")
log(dist[dist.домов >= 10].to_string())
d10 = dist[dist.домов >= 10]
log(f"  Медиана по районам (≥10 домов): {d10.на_1000_кв.median():.1f} объекта на 1 000 квартир; "
    f"разброс {d10.на_1000_кв.min():.1f}–{d10.на_1000_кв.max():.1f}")
cls_d = (I.drop_duplicates(["class_name", "poi_key"]).groupby("class_name").size()
         / z.groupby("class_name").flats.sum() * 1000).reindex(CLASSES).round(1)
log("  на 1 000 квартир по классам: " + ", ".join(f"{k} {v}" for k, v in cls_d.items()))
cls_d.to_csv(TAB / "t5_density_by_class.csv")

# ---------------- 6. сети ----------------
log()
log("6. СЕТИ «ВНУТРИ ЖК»: доля объектов с брендом и топ-10 брендов")
u = I.drop_duplicates("poi_key")
log(f"  объектов с тегом brand: {u.brand.notna().sum()} из {len(u)} ({u.brand.notna().mean():.0%})")
br = u.groupby("brand").agg(объектов=("poi_key", "count"), категория=("cat", lambda c: CAT[c.mode()[0]]))
br = br.sort_values("объектов", ascending=False).head(10)
log(br.to_string())
br.to_csv(TAB / "t6_brands.csv")
mp = u[u.cat == "pickup"].brand.value_counts(normalize=True).mul(100).round(0).head(4)
log("  ПВЗ по брендам, %: " + ", ".join(f"{k} {int(v)}" for k, v in mp.items()))
u[u.cat == "pickup"].brand.value_counts().to_csv(TAB / "t6_pvz_brands.csv")
gr = u[u.cat == "grocery"]
log(f"  продуктовые: сетевых (есть brand) {gr.brand.notna().mean():.0%}; алкомаркеты (shop=alcohol/wine) "
    f"{gr.shop.isin(['alcohol', 'wine']).mean():.0%} продуктовых")
alc = I[I.cat == "grocery"].assign(alc=lambda d: d.shop.isin(["alcohol", "wine"])).groupby("group").alc.agg(["mean", "sum", "count"])
log("  алкомаркеты среди продуктовых по группам: " + ", ".join(
    f"{g} {r['mean']:.0%} ({int(r['sum'])} из {int(r['count'])})" for g, r in alc.iterrows()))
alc.to_csv(TAB / "t6_alcohol.csv")
fd = I[I.cat == "food"]
fdt = (pd.crosstab(fd.amenity.replace({"pub": "bar", "food_court": "fast_food", "ice_cream": "cafe"}), fd.group,
                   normalize="columns") * 100).round(0)
log("  общепит по формату, % внутри группы:\n" + fdt.to_string())
fdt.to_csv(TAB / "t6_food_formats.csv")

# ---------------- 7. сводные цифры для дайджеста ----------------
kp = {"домов": len(z), "ЖК": z.zk.nunique(), "квартир": int(z.flats.sum()),
      "объектов_внутри": len(u), "доля_домов_с_арендаторами_%": round(z.has.mean() * 100),
      "общепит_БЭ_%": main.query("категория=='Общепит' and группа=='Б+Э'")["доля_%"].iloc[0],
      "общепит_КТ_%": main.query("категория=='Общепит' and группа=='К+Т'")["доля_%"].iloc[0],
      "продукты_БЭ_%": main.query("категория=='Продукты' and группа=='Б+Э'")["доля_%"].iloc[0],
      "продукты_КТ_%": main.query("категория=='Продукты' and группа=='К+Т'")["доля_%"].iloc[0],
      "ПВЗ_все_%": round(top.get("pickup", 0), 1)}
pd.Series(kp).to_csv(TAB / "t0_kpi.csv", header=["значение"])
log()
log("KPI: " + ", ".join(f"{k} {v}" for k, v in kp.items()))
z.to_csv(TAB / "houses_for_dashboard.csv", index=False)
(PROC / "05_analysis_report.txt").write_text("\n".join(rep), encoding="utf-8")
print("\nГотово: output/tables/*.csv, data/processed/05_analysis_report.txt")
