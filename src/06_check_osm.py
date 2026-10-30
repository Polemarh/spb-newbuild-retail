"""
T7. Выборочная сверка OSM с Яндекс Картами (≥10 ЖК, вручную).

Шаг 1 (файла нет):  python3 src/06_check_osm.py
   → output/check_t7.csv: 12 ЖК (по 3 на класс, seed 2026; только дома с контуром OSM),
     ссылка на Яндекс Карты и список арендаторов, которых нашёл OSM «внутри ЖК».
   Вручную по каждому ЖК (карта + панорамы, ~5–7 мин) заполнить столбцы:
     yandex_n     — сколько коммерческих помещений с вывеской на первых этажах этого дома видно в Яндексе
     osm_ok       — сколько объектов из списка osm_list есть в Яндексе (тот же арендатор или та же категория)
     comment      — что не так (закрылось, новый арендатор, OSM поставил точку не к тому дому…)
Шаг 2 (файл заполнен): python3 src/06_check_osm.py
   → точность OSM = Σ osm_ok / Σ osm_n; полнота OSM ≈ Σ osm_ok / Σ yandex_n. Порог из PLAN.md: ≥60%.
   Считается только по домам с надёжным контуром (reliable) — остальные в анализе «внутри ЖК» не участвуют.
После изменения метода привязки: python3 src/06_check_osm.py --refresh
   → пересобирает osm_n / osm_list для тех же 12 ЖК по новому poi_links.csv, сохраняя yandex_n и comment;
     osm_ok обнуляется там, где список OSM изменился (кроме пустых списков — там osm_ok = 0).
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
F = ROOT / "output/check_t7.csv"
CLASSES = ["Элитный", "Бизнес", "Комфорт", "Типовой"]

def osm_for(obj_id, L):
    o = L[L.obj_id == obj_id]
    return len(o), "; ".join(f"{n if isinstance(n, str) else '(без названия)'} [{c}]" for n, c in zip(o.name, o.cat))

if F.exists() and "--refresh" in sys.argv:
    c = pd.read_csv(F, dtype={"comment": str, "osm_list": str})
    z = pd.read_csv(ROOT / "data/processed/zk_categories.csv")
    z["zk"] = z.zk_name.fillna(z.developer.fillna("?") + " / " + z.address)
    L = pd.read_csv(ROOT / "data/processed/poi_links.csv")
    L = L[L.inside & (L.cat != "vacant")]
    if "obj_id" not in c:
        cand = z[z.footprint == "osm"].drop_duplicates("zk")
        pick = pd.concat([cand[cand.class_name == k].sample(3, random_state=2026) for k in CLASSES])
        assert list(pick.zk) == list(c.zk), "выборка ЖК не совпала"
        c.insert(0, "obj_id", pick.obj_id.values)
    c["reliable"] = c.obj_id.map(z.set_index("obj_id").reliable)
    for i, r in c.iterrows():
        n, lst = osm_for(r.obj_id, L)
        if n != r.osm_n or (lst or "") != (r.osm_list if isinstance(r.osm_list, str) else ""):
            c.loc[i, ["osm_n", "osm_list"]] = [n, lst]
            c.loc[i, "osm_ok"] = 0 if (n == 0 and pd.notna(r.yandex_n)) else None
    # добор: в каждом классе должно быть 3 ЖК с надёжным контуром (отбракованные остаются в файле для отчёта)
    zr = z[z.reliable & ~z.zk.isin(c.zk)].drop_duplicates("zk")
    add = []
    for k in CLASSES:
        need = 3 - int(c[(c.class_name == k) & c.reliable.astype(bool)].shape[0])
        for _, r in zr[zr.class_name == k].sample(max(need, 0), random_state=2026).iterrows():
            n, lst = osm_for(r.obj_id, L)
            add.append({"obj_id": r.obj_id, "zk": r.zk, "class_name": k, "district": r.district, "address": r.address,
                        "ready_year": r.ready_year, "reliable": True, "osm_n": n, "osm_list": lst, "comment": "добор после 31.10",
                        "yandex_link": f"https://yandex.ru/maps/?ll={r.lon},{r.lat}&z=18&pt={r.lon},{r.lat}"})
    if add:
        c = pd.concat([c, pd.DataFrame(add)], ignore_index=True)
    c.to_csv(F, index=False)
    print(c[["zk", "reliable", "osm_n", "yandex_n", "osm_ok"]].to_string())
    raise SystemExit

if F.exists():
    c = pd.read_csv(F)
    if "reliable" in c:
        c = c[c.reliable.astype(bool)]
    done = c[c.yandex_n.notna()]
    if len(done) == 0:
        raise SystemExit(f"{F} ещё не заполнен: внесите yandex_n и osm_ok")
    prec = done.osm_ok.sum() / max(done.osm_n.sum(), 1)
    rec = done.osm_ok.sum() / max(done.yandex_n.sum(), 1)
    lines = [f"Сверено ЖК: {len(done)} из {len(c)}",
             f"Объектов OSM: {int(done.osm_n.sum())}, подтверждено в Яндексе: {int(done.osm_ok.sum())} → точность {prec:.0%}",
             f"Помещений с вывеской по Яндексу: {int(done.yandex_n.sum())} → полнота OSM ≈ {rec:.0%}",
             "По классам (точность | полнота):"]
    for k, g in done.groupby("class_name"):
        pr = f"{g.osm_ok.sum() / g.osm_n.sum():.0%}" if g.osm_n.sum() else "—"
        lines.append(f"  {k} ({len(g)} ЖК): {pr} | {g.osm_ok.sum() / max(g.yandex_n.sum(), 1):.0%}")
    pd.Series({"ЖК": len(done), "osm_n": int(done.osm_n.sum()), "osm_ok": int(done.osm_ok.sum()),
               "yandex_n": int(done.yandex_n.sum()), "точность_%": round(prec * 100),
               "полнота_%": round(rec * 100)}).to_csv(ROOT / "output/tables/t7_check.csv", header=["значение"])
    print("\n".join(lines))
    (ROOT / "data/processed/06_check_report.txt").write_text("\n".join(lines), encoding="utf-8")
    raise SystemExit

z = pd.read_csv(ROOT / "data/processed/zk_categories.csv")
z["zk"] = z.zk_name.fillna(z.developer.fillna("?") + " / " + z.address)
L = pd.read_csv(ROOT / "data/processed/poi_links.csv")
L = L[L.inside & (L.cat != "vacant")]
cand = z[z.footprint == "osm"].drop_duplicates("zk")          # один дом на ЖК
pick = pd.concat([cand[cand.class_name == k].sample(3, random_state=2026) for k in CLASSES])
rows = []
for _, r in pick.iterrows():
    o = L[L.obj_id == r.obj_id]
    lst = "; ".join(f"{n if isinstance(n, str) else '(без названия)'} [{c}]" for n, c in zip(o.name, o.cat))
    rows.append({"zk": r.zk, "class_name": r.class_name, "district": r.district, "address": r.address,
                 "ready_year": r.ready_year, "yandex_link": f"https://yandex.ru/maps/?ll={r.lon},{r.lat}&z=18&pt={r.lon},{r.lat}",
                 "osm_n": len(o), "osm_list": lst, "yandex_n": None, "osm_ok": None, "comment": ""})
pd.DataFrame(rows).to_csv(F, index=False)
print(f"Создан {F}: {len(rows)} ЖК. Заполните yandex_n, osm_ok, comment и запустите скрипт ещё раз.")
