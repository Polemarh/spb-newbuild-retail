"""
T9. Графики и карта районов для дайджеста и полной версии (PNG, 200 dpi, в output/charts/).

Вход:  output/tables/*.csv (05_analysis.py), data/interim/osm_admin.csv (границы районов), data/processed/zk_categories.csv
Стиль: заголовок-вывод, единицы в подзаголовке, источник под каждым графиком; одна ось; две группы —
       «Бизнес + Элитный» (бордовый) и «Комфорт + Типовой» (синий), палитра проверена на дальтонизм (ΔE ≥ 14).
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib import font_manager
from matplotlib.patches import Polygon as MplPolygon, Patch
from matplotlib.colors import LinearSegmentedColormap, Normalize
from shapely import wkt as swkt

ROOT = Path(__file__).resolve().parent.parent
TAB, OUTC = ROOT / "output/tables", ROOT / "output/charts"
OUTC.mkdir(parents=True, exist_ok=True)

for f in ("/System/Library/Fonts/Supplemental/PTSans.ttc",):
    if Path(f).exists():
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": ["PT Sans", "Arial", "DejaVu Sans"], "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
                     "axes.edgecolor": "#9AA0A6", "xtick.color": "#4B5563", "ytick.color": "#1F2A36",
                     "axes.labelcolor": "#4B5563", "figure.facecolor": "white"})
INK, MUTED, GRID = "#1F2A36", "#6B7280", "#E5E7EB"
BE, KT = "#B5404C", "#3A6EA5"                      # Б+Э, К+Т
SRC = "Источник: расчёты автора по данным ДОМ.РФ (наш.дом.рф, 26–27.10.2026) и OpenStreetMap (Geofabrik, 25.10.2026)"

def frame(fig, title, sub, tsize=14, sub_y=0.42, src=SRC):
    h = fig.get_figheight()
    fig.text(0.02, 1 - 0.12 / h, title, fontsize=tsize, fontweight="bold", color=INK, va="top")
    fig.text(0.02, 1 - sub_y / h, sub, fontsize=10, color=MUTED, va="top", wrap=True)
    fig.text(0.02, 0.015, src, fontsize=7.5, color=MUTED, va="bottom")

def save(fig, name):
    fig.savefig(OUTC / name, dpi=200)
    plt.close(fig)
    print("  ", name)

# ---------- 1. структура арендаторов по группам ----------
t = pd.read_csv(TAB / "t3_structure_by_class.csv", index_col=0).drop(index="Всего объектов, шт.")
t = t.sort_values("К+Т")
n = pd.read_csv(TAB / "t3_structure_by_class.csv", index_col=0).loc["Всего объектов, шт."]
fig, ax = plt.subplots(figsize=(8, 5.0))
fig.subplots_adjust(left=0.27, right=0.95, top=0.84, bottom=0.12)
y = np.arange(len(t)); h = 0.38
ax.barh(y + h / 2 + 0.01, t["Б+Э"], h, color=BE, label=f"Бизнес + Элитный ({int(n['Б+Э'])} объектов)")
ax.barh(y - h / 2 - 0.01, t["К+Т"], h, color=KT, label=f"Комфорт + Типовой ({int(n['К+Т'])} объектов)")
for i, cat in enumerate(t.index):
    if cat in ("Продукты", "Общепит", "Пункты выдачи заказов", "Непрод. торговля"):
        ax.text(t.loc[cat, "Б+Э"] + 0.4, i + h / 2, f"{t.loc[cat, 'Б+Э']:.0f}", va="center", fontsize=9, color=INK)
        ax.text(t.loc[cat, "К+Т"] + 0.4, i - h / 2, f"{t.loc[cat, 'К+Т']:.0f}", va="center", fontsize=9, color=INK)
ax.set_yticks(y); ax.set_yticklabels(t.index)
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(axis="y", length=0)
ax.set_xlabel("% арендаторов «внутри ЖК»")
ax.legend(loc="lower right", frameon=False)
frame(fig, "В комфорт-классе каждый второй арендатор — продукты или ПВЗ",
      "Структура арендаторов первых этажей ЖК, сданных в 2021–2025 гг., % от объектов OSM ≤10 м от корпусов")
save(fig, "c1_structure.png")

# ---------- 2. проверка правила: доли с 95% ДИ ----------
r = pd.read_csv(TAB / "t4_rule_check.csv")
cats = ["Продукты", "Общепит", "Пункты выдачи заказов", "Непрод. торговля"]
fig, ax = plt.subplots(figsize=(8, 4.4))
fig.subplots_adjust(left=0.27, right=0.95, top=0.74, bottom=0.14)
for i, c in enumerate(cats[::-1]):
    for g, col, dy in (("Б+Э", BE, 0.15), ("К+Т", KT, -0.15)):
        row = r[(r.категория == c) & (r.группа == g)].iloc[0]
        ax.plot([row.ДИ_низ, row.ДИ_верх], [i + dy] * 2, color=col, lw=2, solid_capstyle="round")
        ax.plot(row["доля_%"], i + dy, "o", ms=8, color=col, mec="white", mew=1.5)
        ax.text(row.ДИ_верх + 0.6, i + dy, f"{row['доля_%']:.0f}%", va="center", fontsize=9, color=INK)
    d = r[(r.категория == c) & (r.группа == "разница, п. п.")].iloc[0]
    ax.text(41, i, f"{d['доля_%']:+.0f} п. п.\n[{d.ДИ_низ:+.0f}; {d.ДИ_верх:+.0f}]", va="center", ha="right", fontsize=8.5, color=MUTED)
ax.set_yticks(range(len(cats))); ax.set_yticklabels(cats[::-1]); ax.set_xlim(0, 41)
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(axis="y", length=0)
ax.set_xlabel("% арендаторов «внутри ЖК»; линия — 95% доверительный интервал (бутстрэп по ЖК)")
nzk = r.dropna(subset=["ЖК"]).groupby("группа").ЖК.first().astype(int)
ax.plot([], [], "o", color=BE, label=f"Бизнес + Элитный ({nzk['Б+Э']} ЖК)"); ax.plot([], [], "o", color=KT, label=f"Комфорт + Типовой ({nzk['К+Т']} ЖК)")
ax.legend(loc="upper center", bbox_to_anchor=(0.45, 1.13), ncol=2, frameon=False)
frame(fig, "В бизнес-классе продуктовых меньше, а общепита — больше",
      "Доля категории среди арендаторов первых этажей, %; справа — разница Б+Э − К+Т")
save(fig, "c2_rule_check.png")

# ---------- 3. контроль локации: пояса удалённости ----------
zt = pd.read_csv(TAB / "t4a_by_zone.csv").dropna()
fig, axes = plt.subplots(1, 2, figsize=(8, 3.8), sharey=True)
fig.subplots_adjust(left=0.08, right=0.97, top=0.72, bottom=0.17, wspace=0.12)
for ax, c in zip(axes, ["Общепит", "Продукты"]):
    d = zt[zt.категория == c]
    x = np.arange(len(d))
    ax.bar(x - 0.2, d["Б+Э_%"], 0.38, color=BE)
    ax.bar(x + 0.2, d["К+Т_%"], 0.38, color=KT)
    for xi, a, b in zip(x, d["Б+Э_%"], d["К+Т_%"]):
        ax.text(xi - 0.2, a + 0.6, f"{a:.0f}", ha="center", fontsize=9, color=INK)
        ax.text(xi + 0.2, b + 0.6, f"{b:.0f}", ha="center", fontsize=9, color=INK)
    ax.set_xticks(x); ax.set_xticklabels(["до 8 км от центра", "8–15 км"])
    ax.set_title(c, fontsize=11, color=INK, loc="left")
    ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(axis="x", length=0)
axes[0].set_ylabel("% арендаторов")
fig.legend(handles=[Patch(color=BE, label="Бизнес + Элитный"), Patch(color=KT, label="Комфорт + Типовой")],
           loc="upper right", bbox_to_anchor=(0.97, 0.86), ncol=2, frameon=False)
frame(fig, "Внутри поясов удалённости от центра разница сохраняется",
      "Доля категории среди арендаторов «внутри ЖК», % (дальше 15 км бизнес-класса почти нет)")
save(fig, "c3_zones.png")

# ---------- 4. заполненность первых этажей по классу и поясу ----------
fz = pd.read_csv(TAB / "t2_fill_by_class_zone.csv", index_col=0).loc[["Бизнес", "Комфорт", "Типовой"]]
hz = pd.read_csv(TAB / "t1_class_zone_n.csv", index_col=0).loc[fz.index, fz.columns]
fz = fz.where(hz >= 10)                         # ячейки с <10 домами не показываем
zcol = ["#9DBFE0", "#5C8DC2", "#2B5486"]       # пояса: светлее = ближе к центру
fig, ax = plt.subplots(figsize=(8, 3.8))
fig.subplots_adjust(left=0.08, right=0.97, top=0.72, bottom=0.12)
x = np.arange(len(fz))
for k, (zone, col) in enumerate(zip(fz.columns, zcol)):
    vals = fz[zone]
    ax.bar(x + (k - 1) * 0.27, vals, 0.25, color=col, label=zone)
    for xi, v in zip(x, vals):
        if not np.isnan(v):
            ax.text(xi + (k - 1) * 0.27, v + 1.5, f"{v:.0f}", ha="center", fontsize=9, color=INK)
ax.set_xticks(x); ax.set_xticklabels(fz.index); ax.set_ylim(0, 100)
ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(axis="x", length=0)
ax.set_ylabel("% домов")
ax.legend(title="Удалённость от центра", loc="upper right", bbox_to_anchor=(1, 1.2), ncol=3, frameon=False, fontsize=9, title_fontsize=9)
frame(fig, f"Дальше 15 км от центра у {100 - fz.loc['Комфорт', '15 км и дальше']:.0f}% домов комфорт-класса нет арендаторов в OSM",
      "Доля домов с надёжным контуром OSM, у которых известен хотя бы один арендатор, %; ячейки с <10 домами скрыты")
save(fig, "c4_fill.png")

# ---------- 5. карта районов ----------
dist = pd.read_csv(TAB / "t5_districts.csv", index_col=0)
adm = pd.read_csv(ROOT / "data/interim/osm_admin.csv").dropna(subset=["name"])
adm = adm[adm.admin_level == 5]
z = pd.read_csv(ROOT / "data/processed/zk_categories.csv")
LABEL_SHIFT = {"Курортный район": (0.05, -0.07), "Василеостровский район": (-0.08, -0.006), "Петроградский район": (0, 0.01),
               "Невский район": (0.05, 0), "Фрунзенский район": (-0.01, -0.01),
               "Адмиралтейский район": (-0.07, -0.01), "Центральный район": (0.01, 0.0)}
cmap = LinearSegmentedColormap.from_list("seq", ["#E8EEF6", "#2B5486"])
norm = Normalize(0, 12)
fig, ax = plt.subplots(figsize=(6.2, 6.9))
fig.subplots_adjust(left=0.01, right=0.99, top=0.82, bottom=0.15)
k = 1 / np.cos(np.radians(59.94))
for _, r in adm.iterrows():
    g = swkt.loads(r.wkt)
    polys = list(g.geoms) if hasattr(g, "geoms") else [g]
    ok = r["name"] in dist.index and dist.loc[r["name"], "домов"] >= 10
    fc = cmap(norm(min(dist.loc[r["name"], "на_1000_кв"], 12))) if ok else "#F3F4F6"
    for p in polys:
        ax.add_patch(MplPolygon(np.array(p.exterior.coords), closed=True, fc=fc, ec="white", lw=1.2))
    if r["name"] in dist.index:
        c = g.representative_point()
        dx, dy = LABEL_SHIFT.get(r["name"], (0, 0))
        c = type(c)(c.x + dx, c.y + dy)
        v = dist.loc[r["name"]]
        lab = r["name"].replace(" район", "")
        txt = f"{lab}\n{v.на_1000_кв:.1f}" if ok else f"{lab}\n(<10 домов)"
        ax.text(c.x, c.y, txt, ha="center", va="center", fontsize=8.5, color=INK,
                path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])
ax.scatter(z.lon, z.lat, s=2.5, color="#B5404C", alpha=0.6, lw=0)
ax.set_aspect(k); ax.autoscale_view(); ax.axis("off")
ax.set_xlim(29.65, 30.75); ax.set_ylim(59.63, 60.10)
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
cax = fig.add_axes([0.25, 0.12, 0.5, 0.012])
cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
cb.set_label("арендаторов «внутри ЖК» на 1 000 квартир (шкала обрезана на 12)", color=MUTED, fontsize=8.5)
cb.outline.set_visible(False)
hi = dist.loc[["Адмиралтейский район", "Петроградский район"], "на_1000_кв"]
SLEEP = dist.nlargest(5, "квартир").index                # 5 крупнейших районов по числу квартир в выборке
sp = dist.loc[SLEEP, "на_1000_кв"]
TITLE5 = f"Центр: {hi.min():.0f}–{hi.max():.0f} арендаторов на 1 000 квартир,\n5 крупнейших по вводу районов: {sp.min():.0f}–{sp.max():.0f}"
frame(fig, TITLE5, "Арендаторы первых этажей ЖК 2021–2025 гг. на 1 000 квартир;\nточки — дома выборки (793); дома с надёжным контуром", tsize=13, sub_y=0.62,
      src=SRC.replace(" и OpenStreetMap", "\nи OpenStreetMap"))
save(fig, "c5_map.png")

# ---------- 6. сети ----------
br = pd.read_csv(TAB / "t6_brands.csv").iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 4.4))
fig.subplots_adjust(left=0.2, right=0.95, top=0.80, bottom=0.17)
ax.barh(br.brand, br.объектов, color="#4B6584", height=0.65)
for i, (v, c) in enumerate(zip(br.объектов, br.категория)):
    ax.text(v + 1, i, f"{v}  ·  {c.lower()}", va="center", fontsize=8.5, color=MUTED)
ax.set_xlim(0, br.объектов.max() * 1.45)
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(axis="y", length=0)
ax.set_xlabel("объектов «внутри ЖК», шт.")
frame(fig, "Самые частые сетевые арендаторы — ПВЗ маркетплейсов и «Красное&Белое»",
      "Топ-10 брендов среди арендаторов первых этажей ЖК 2021–2025 гг. (по тегу brand в OSM, 34% объектов)")
save(fig, "c6_brands.png")
print("Готово: output/charts/")
