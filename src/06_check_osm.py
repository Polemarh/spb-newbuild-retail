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
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
F = ROOT / "output/check_t7.csv"
CLASSES = ["Элитный", "Бизнес", "Комфорт", "Типовой"]

if F.exists():
    c = pd.read_csv(F)
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
        lines.append(f"  {k}: {g.osm_ok.sum() / max(g.osm_n.sum(), 1):.0%} | {g.osm_ok.sum() / max(g.yandex_n.sum(), 1):.0%}")
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
