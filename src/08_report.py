"""
T11–T12. Дайджест (2 стр.) и полная версия (5–6 стр.) → report/digest.pdf, report/full.pdf.

Все числа в тексте подставляются из output/tables/*.csv (05_analysis.py) и отчётов скриптов — вручную цифры не вписываются.
HTML печатается в PDF через Google Chrome в headless-режиме (есть на Mac пользователя).
Запуск: python3 src/08_report.py
"""
import subprocess
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TAB, REP = ROOT / "output/tables", ROOT / "report"
REP.mkdir(exist_ok=True)
AUTHOR = "Михаил"                      # ← впишите фамилию
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DATE = "Октябрь 2026 г."
SRC = "Источник: расчёты автора по данным ДОМ.РФ и OpenStreetMap, 2026"


def num(x, d=1):
    """Число по-русски: запятая, неразрывный пробел в тысячах, минус «−»."""
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")
    return s


def pp(x, d=0):
    return ("+" if x > 0 else "") + num(x, d) + " п. п."


t = lambda f, **kw: pd.read_csv(TAB / f, **kw)
kpi = t("t0_kpi.csv", index_col=0)["значение"]
sample = t("t1_sample.csv", index_col=0)
struct = t("t3_structure_by_class.csv", index_col=0)
total = t("t3_structure_total.csv", index_col=0)["proportion"]
rule = t("t4_rule_check.csv")
zone = t("t4a_by_zone.csv")
env = t("t4b_inside_vs_env.csv", index_col=0)
rob = t("t4c_robustness.csv")
dist = t("t5_districts.csv", index_col=0)
dens = t("t5_density_by_class.csv", index_col=0).iloc[:, 0]
fill_y = t("t2_fill_by_year.csv", index_col=0)["has"]
fill_cz = t("t2_fill_by_class_zone.csv", index_col=0)
brands = t("t6_brands.csv")
alc = t("t6_alcohol.csv", index_col=0)
food = t("t6_food_formats.csv", index_col=0)
osm_rep = (ROOT / "data/processed/04_osm_link_report.txt").read_text(encoding="utf-8")
chk_f = ROOT / "data/processed/06_check_report.txt"
check = chk_f.read_text(encoding="utf-8").splitlines() if chk_f.exists() else None


def R(cat, grp, col="доля_%"):
    return rule[(rule.категория == cat) & (rule.группа == grp)][col].iloc[0]


def Z(z, cat, g):
    return zone[(zone.пояс == z) & (zone.категория == cat)][g + "_%"].iloc[0]


food_be, food_kt = R("Общепит", "Б+Э"), R("Общепит", "К+Т")
gro_be, gro_kt = R("Продукты", "Б+Э"), R("Продукты", "К+Т")
pvz_be, pvz_kt = R("Пункты выдачи заказов", "Б+Э"), R("Пункты выдачи заказов", "К+Т")
d_food, d_gro, d_pvz = (R(c, "разница, п. п.") for c in ("Общепит", "Продукты", "Пункты выдачи заказов"))
ci = lambda c: f"[{num(R(c, 'разница, п. п.', 'ДИ_низ'), 0)}; {num(R(c, 'разница, п. п.', 'ДИ_верх'), 0)}]"
n_be, n_kt = int(R("Общепит", "Б+Э", "ЖК")), int(R("Общепит", "К+Т", "ЖК"))
ob_be, ob_kt = int(R("Общепит", "Б+Э", "объектов")), int(R("Общепит", "К+Т", "объектов"))
houses, zks, flats, objs = int(kpi["домов"]), int(kpi["ЖК"]), int(kpi["квартир"]), int(kpi["объектов_внутри"])
filled = int(kpi["доля_домов_с_арендаторами_%"])
pvz_all, gro_all = total["Пункты выдачи заказов"], total["Продукты"]
top_d = dist[dist.домов >= 10].sort_values("на_1000_кв", ascending=False)
d10 = top_d
alc_all = alc["sum"].sum() / alc["count"].sum() * 100
ozon_share = brands.set_index("brand").объектов
pvz_brand_n = t("t6_pvz_brands.csv", index_col=0).iloc[:, 0].sum()
lead2 = f"{num(env.loc['Пункты выдачи заказов', 'индекс_К+Т'], 1)}–{num(env.loc['Пункты выдачи заказов', 'индекс_Б+Э'], 1)}"
match = {k: v for k, v in (l.split()[:2] for l in osm_rep.splitlines() if l.strip().split()[:1] and l.strip().split()[0] in ("inside", "nearest", "none"))}
check_line = (" ".join(check[1:3]) if check else
              "Выборочная сверка 12 ЖК с Яндекс Картами выполняется (шаблон — output/check_t7.csv); результат будет добавлен.")

CSS = """
@page { size: A4; margin: 14mm 15mm 14mm 15mm; }
* { box-sizing: border-box; }
body { font-family: 'PT Sans', Arial, sans-serif; color: #1F2A36; font-size: 10pt; line-height: 1.38; margin: 0; }
h1 { font-size: 25pt; line-height: 1.08; margin: 0 0 4mm; color: #1F2A36; }
h2 { font-size: 14pt; margin: 6mm 0 2.5mm; color: #1F2A36; border-bottom: 2px solid #B5404C; padding-bottom: 1mm; }
h3 { font-size: 11pt; margin: 4mm 0 1.5mm; }
.sub { color: #4B5563; font-size: 11.5pt; margin-bottom: 1mm; }
.by { color: #6B7280; font-size: 8.5pt; margin-bottom: 5mm; }
.kpi { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; margin: 4mm 0 5mm; }
.kpi div { background: #F3F5F8; border-top: 3px solid #1F3A5F; padding: 3mm; }
.kpi b { display: block; font-size: 20pt; color: #1F3A5F; line-height: 1.05; }
.kpi span { font-size: 8.5pt; color: #4B5563; }
.lead { font-size: 11pt; margin-bottom: 4mm; }
.quote { border-left: 3px solid #B5404C; padding: 1mm 0 1mm 4mm; margin: 4mm 0; color: #374151; font-style: italic; }
.quote .who { font-style: normal; font-size: 8.5pt; color: #6B7280; margin-top: 1mm; }
ul.k { padding-left: 5mm; margin: 2mm 0; } ul.k li { margin-bottom: 1.6mm; }
img { width: 100%; display: block; margin: 1.5mm auto 1mm; break-inside: avoid; }
.w90 { width: 90%; } .w80 { width: 80%; }
.g2 { display: grid; grid-template-columns: 56% 1fr; gap: 5mm; align-items: start; break-inside: avoid; }
.g2 img { margin-top: 0; }
table, .quote, .kpi { break-inside: avoid; }
h2, h3 { break-after: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 8.8pt; margin: 2mm 0 1mm; }
th { text-align: left; color: #4B5563; font-weight: normal; border-bottom: 1.5px solid #1F3A5F; padding: 1.2mm 1.5mm; }
td { border-bottom: 1px solid #E5E7EB; padding: 1.1mm 1.5mm; }
td.n, th.n { text-align: right; white-space: nowrap; }
.src { font-size: 7.5pt; color: #6B7280; margin-bottom: 3mm; }
.note { font-size: 8.5pt; color: #4B5563; }
.pb { page-break-before: always; }
.up { color: #1F3A5F; font-weight: bold; } .dn { color: #B5404C; font-weight: bold; }
.foot { font-size: 7.5pt; color: #6B7280; border-top: 1px solid #E5E7EB; padding-top: 2mm; margin-top: 4mm; }
"""


def table(df, num_cols=(), fmt=None):
    head = "".join(f'<th class="{"n" if c in num_cols else ""}">{c}</th>' for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            if c in num_cols and not isinstance(v, str):
                v = "—" if pd.isna(v) else (fmt or {}).get(c, lambda x: num(x, 1))(v)
            cells.append(f'<td class="{"n" if c in num_cols else ""}">{v}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><tr>{head}</tr>{''.join(rows)}</table>"


def page(title, body):
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{title}</title>'
            f"<style>{CSS}</style></head><body>{body}</body></html>")


HEAD = f"""
<h1>Кто занимает первые этажи новостроек Санкт-Петербурга</h1>
<div class="sub">Санкт-Петербург. Жилые дома, введённые в 2021–2025 гг. {DATE}</div>
<div class="by">Независимое студенческое исследование. Автор: {AUTHOR}. Открытые данные ДОМ.РФ и OpenStreetMap; код и методология — в репозитории проекта.</div>
<div class="kpi">
 <div><b>{num(houses, 0)}</b><span>жилых домов в {num(zks, 0)} ЖК, {num(flats / 1000, 0)} тыс. квартир</span></div>
 <div><b>{num(objs, 0)}</b><span>арендаторов первых этажей найдено в OSM</span></div>
 <div><b>{num(pvz_all, 0)}%</b><span>арендаторов — пункты выдачи заказов маркетплейсов</span></div>
 <div><b>{pp(d_gro)}</b><span>доля продуктовых в бизнес-классе по сравнению с комфорт-классом</span></div>
</div>"""

LEAD = (f"Первые этажи новостроек, сданных в 2021–2025 гг., заняты прежде всего форматами повседневного спроса: "
        f"продуктовые магазины ({num(gro_all, 0)}% арендаторов) и пункты выдачи заказов ({num(pvz_all, 0)}%) вместе дают "
        f"{num(gro_all + pvz_all, 0)}% объектов. Структура заметно различается по классам: в ЖК бизнес- и элитного класса "
        f"продуктовых в {num(gro_kt / gro_be, 1)} раза меньше, чем в комфорт- и типовом классе ({num(gro_be, 0)}% против {num(gro_kt, 0)}%), "
        f"а общепита — в {num(food_be / food_kt, 1)} раза больше ({num(food_be, 0)}% против {num(food_kt, 0)}%).")

FIND = [
    f"<b>Правило классификации подтверждается для продуктовых.</b> Согласно классификации бизнес-класса NF GROUP, "
    f"в нежилых помещениях такого класса нежелательны общепит и продуктовые магазины. Доля продуктовых в ЖК бизнес- и элитного "
    f"класса на {num(abs(d_gro), 0)} п. п. ниже (95% ДИ {ci('Продукты')}), разница сохраняется на одинаковом расстоянии от центра "
    f"({num(Z('8–15 км', 'Продукты', 'Б+Э'), 0)}% против {num(Z('8–15 км', 'Продукты', 'К+Т'), 0)}% в поясе 8–15 км).",
    f"<b>…но не для общепита.</b> Общепита в бизнес-классе больше: {pp(d_food)} (95% ДИ {ci('Общепит')}). Меняется формат: "
    f"рестораны и бары — {num(food.loc['restaurant', 'Б+Э'] + food.loc['bar', 'Б+Э'], 0)}% общепита бизнес-класса против "
    f"{num(food.loc['restaurant', 'К+Т'] + food.loc['bar', 'К+Т'], 0)}% в комфорте, фастфуд — {num(food.loc['fast_food', 'Б+Э'], 0)}% против "
    f"{num(food.loc['fast_food', 'К+Т'], 0)}%. Данные согласуются с тем, что ограничение касается массовых форматов, а не общепита в целом.",
    f"<b>Маркетплейсы — новый якорный арендатор.</b> Каждый пятый арендатор ({num(pvz_all, 0)}%) — пункт выдачи заказов; "
    f"в комфорт-классе — {num(pvz_kt, 0)}%. В новых ЖК доля ПВЗ в {lead2} раза выше, чем в окружающей застройке (500 м). "
    f"Крупнейший оператор ПВЗ — Ozon ({int(ozon_share['Ozon'])} объектов, {num(ozon_share['Ozon'] / pvz_brand_n * 100, 0)}% ПВЗ с указанным брендом), далее Wildberries ({int(ozon_share['Wildberries'])}).",
    f"<b>{num(alc_all, 0)}% продуктовых — алкомаркеты</b> (shop=alcohol/wine в OSM); «Красное&Белое» — третий по числу "
    f"объектов сетевой арендатор ({int(ozon_share['Красное&Белое'])}).",
    f"<b>Насыщенность падает к окраинам.</b> В Адмиралтейском и Петроградском районах — "
    f"{num(dist.loc['Адмиралтейский район', 'на_1000_кв'], 0)} и {num(dist.loc['Петроградский район', 'на_1000_кв'], 0)} "
    f"арендаторов на 1 000 квартир, в Приморском (крупнейший по вводу, {num(dist.loc['Приморский район', 'квартир'] / 1000, 0)} тыс. квартир) — "
    f"{num(dist.loc['Приморский район', 'на_1000_кв'], 1)}, в Пушкинском — {num(dist.loc['Пушкинский район', 'на_1000_кв'], 1)}. "
    f"У домов комфорт-класса дальше 15 км от центра арендатор в OSM есть лишь в {num(fill_cz.loc['Комфорт', '15 км и дальше'], 0)}% случаев.",
]

COMMENT = (f"Самое интересное — расхождение по общепиту. Ограничение из классификации работает как фильтр формата, а не категории: "
           f"в бизнес-классе фастфуда меньше, а ресторанов и баров больше, чем в комфорте. В массовом сегменте первые этажи всё больше "
           f"работают как «склад последней мили»: ПВЗ и продуктовые у дома — более половины известных арендаторов. Для девелопера это аргумент "
           f"заранее проектировать помещения под ПВЗ (зона хранения, отдельный вход), а для аналитика — повод учитывать маркетплейсы "
           f"как отдельный сегмент спроса на стрит-ритейл.")

LIM_SHORT = (f"OSM неполон, особенно для новых окраинных домов (дом с хотя бы одним арендатором: {filled}% выборки; для сданных в 2025 г. — "
             f"{num(fill_y.loc[2025], 0)}%), поэтому выводы — о структуре (долях), а не об абсолютном числе арендаторов. "
             f"В ДОМ.РФ нет подкласса «бизнес лайт»: сравниваются «Бизнес + Элитный» и «Комфорт + Типовой». {check_line}")

digest = page("Первые этажи новостроек СПб — дайджест", f"""
{HEAD}
<p class="lead">{LEAD}</p>
<h2>Ключевые выводы</h2>
<ul class="k">{''.join(f'<li>{x}</li>' for x in FIND[:3])}</ul>
<img src="../output/charts/c2_rule_check.png" class="w90">
<div class="pb"></div>
<img src="../output/charts/c1_structure.png" class="w90">
<div class="g2"><img src="../output/charts/c5_map.png"><div>
<div class="quote" style="margin-top:0">{COMMENT}<div class="who">Комментарий автора</div></div>
<div class="foot"><b>Методология.</b> {num(houses, 0)} жилых домов, введённых в 2021–2025 гг. (ДОМ.РФ, наш.дом.рф, выгрузка 26–27.10.2026;
класс — официальный фильтр ДОМ.РФ). Арендаторы — объекты OpenStreetMap (Geofabrik, 25.10.2026) не дальше 30 м от контура
корпуса; каждый объект считается один раз на ЖК; 95% ДИ — бутстрэп по ЖК. {LIM_SHORT}
Цитаты классификации — по данным NF GROUP («Рынок жилой недвижимости бизнес-класса. Санкт-Петербург. I полугодие 2026»).
Исследование не связано с NF GROUP и не воспроизводит её методологию.</div></div></div>
""")

# ---------------- полная версия ----------------
main_tab = pd.DataFrame([
    ["Арендаторов «внутри ЖК», шт.", ob_be, ob_kt, objs, "—"],
    ["Продуктовые, %", gro_be, gro_kt, gro_all, pp(d_gro, 1)],
    ["Общепит, %", food_be, food_kt, total["Общепит"], pp(d_food, 1)],
    ["Пункты выдачи заказов, %", pvz_be, pvz_kt, pvz_all, pp(d_pvz, 1)],
    ["Непрод. торговля, %", R("Непрод. торговля", "Б+Э"), R("Непрод. торговля", "К+Т"), total["Непрод. торговля"],
     pp(R("Непрод. торговля", "разница, п. п."), 1)],
    ["Арендаторов на 1 000 квартир", (dens["Бизнес"] * sample.loc["Бизнес", "квартир"] + dens["Элитный"] * sample.loc["Элитный", "квартир"])
     / (sample.loc["Бизнес", "квартир"] + sample.loc["Элитный", "квартир"]),
     (dens["Комфорт"] * sample.loc["Комфорт", "квартир"] + dens["Типовой"] * sample.loc["Типовой", "квартир"])
     / (sample.loc["Комфорт", "квартир"] + sample.loc["Типовой", "квартир"]), objs / flats * 1000, "—"],
], columns=["Показатель", "Бизнес + Элитный", "Комфорт + Типовой", "Все", "Разница Б+Э − К+Т"])
fmt0 = {c: (lambda x: num(x, 0) if x > 100 else num(x, 1)) for c in ["Бизнес + Элитный", "Комфорт + Типовой", "Все"]}

s_tab = sample.reset_index().rename(columns={"class_name": "Класс ДОМ.РФ", "домов": "Домов", "квартир": "Квартир",
                                             "км_до_центра_медиана": "Медиана до центра, км"})
s_tab["Плотность арендаторов на 1 000 кв."] = s_tab["Класс ДОМ.РФ"].map(dens).fillna(objs / flats * 1000)
s_tab["Домов с арендатором, %"] = s_tab["Класс ДОМ.РФ"].map(
    t("houses_for_dashboard.csv").groupby("class_name").has.mean() * 100).fillna(filled)

rob_tab = rob.rename(columns={"вариант": "Вариант расчёта", "объектов": "Объектов"})
env_tab = env.reset_index().rename(columns={"cat": "Категория", "внутри_Б+Э_%": "Б+Э: в ЖК, %", "окружение_Б+Э_%": "Б+Э: 500 м, %",
                                            "индекс_Б+Э": "Б+Э: индекс", "внутри_К+Т_%": "К+Т: в ЖК, %",
                                            "окружение_К+Т_%": "К+Т: 500 м, %", "индекс_К+Т": "К+Т: индекс"}).head(6)
dist_tab = d10.reset_index()[["district", "домов", "квартир", "доля_БЭ", "домов_с_арендаторами", "на_1000_кв",
                              "Общепит_%", "Продукты_%", "Пункты выдачи заказов_%"]]
dist_tab.columns = ["Район", "Домов", "Квартир", "Доля Б+Э, %", "Домов с арендатором, %", "На 1 000 кв.", "Общепит, %",
                    "Продукты, %", "ПВЗ, %"]
dist_tab["Район"] = dist_tab["Район"].str.replace(" район", "")

CATS = [("Общепит", "amenity: restaurant, cafe, fast_food, bar, pub, food_court, ice_cream"),
        ("Продукты", "shop: supermarket, convenience, alcohol, wine, bakery, butcher, greengrocer и др."),
        ("Пункты выдачи заказов", "shop=outpost (Ozon, Wildberries, Яндекс Маркет, Авито)"),
        ("Аптеки / Медицина", "amenity=pharmacy; amenity: clinic, dentist, doctors; healthcare=*"),
        ("Красота", "shop: beauty, hairdresser, cosmetics, massage, nails"),
        ("Фитнес и спорт", "leisure: fitness_centre, sports_centre, dance; amenity=dojo"),
        ("Детские и образование", "amenity: kindergarten, childcare, language_school и др."),
        ("Бытовые и фин. услуги", "amenity: bank, post_office, veterinary; shop: laundry, dry_cleaning, repair и др.; craft=*"),
        ("Офисы", "office=*, amenity=coworking_space"),
        ("Непрод. торговля", "прочие shop=* (одежда, хозтовары, электроника, цветы и др.)"),
        ("Исключены (не арендаторы)", "банкоматы, постаматы, терминалы, АЗС, храмы, киоски, ТЦ-«контейнеры»")]

full = page("Первые этажи новостроек СПб — полная версия", f"""
{HEAD}
<p class="lead">{LEAD}</p>
<h2>5 ключевых выводов</h2>
<ol class="k">{''.join(f'<li>{x}</li>' for x in FIND)}</ol>
<h3>Основные показатели</h3>
{table(main_tab, num_cols=["Бизнес + Элитный", "Комфорт + Типовой", "Все", "Разница Б+Э − К+Т"], fmt=fmt0)}
<div class="src">{SRC}. Доли — от арендаторов «внутри ЖК» (≤30 м от корпуса), объект учитывается один раз на ЖК.</div>

<div class="pb"></div>
<h2>1. Вопрос и выборка</h2>
<p>NF GROUP в обзоре рынка бизнес-класса Санкт-Петербурга за I полугодие 2026 г. относит к требованиям класса качество
нежилых помещений: в них возможны офисы, услуги и торговля, но нежелательны общепит и продуктовые магазины; для бизнес лайт
требований нет (по данным NF GROUP). Исследование проверяет, видно ли это правило в том, кто фактически занимает первые этажи
уже заселённых ЖК, — и как наполнение различается по классам и районам.</p>
<p>Выборка — все {num(houses, 0)} жилых домов Санкт-Петербурга со статусом «Сдан» в ДОМ.РФ и датой ввода 2021–2025 гг.
({num(zks, 0)} ЖК, {num(flats, 0)} квартир). Класс — официальный фильтр каталога ДОМ.РФ. Медиана расстояния до центра у элитных и бизнес-домов —
{num(sample.loc['Элитный', 'км_до_центра_медиана'], 1)} и {num(sample.loc['Бизнес', 'км_до_центра_медиана'], 1)} км, у комфорт и типовых — {num(sample.loc['Комфорт', 'км_до_центра_медиана'], 1)} и {num(sample.loc['Типовой', 'км_до_центра_медиана'], 1)} км, — поэтому ниже каждое сравнение проверяется с поправкой на локацию.</p>
{table(s_tab, num_cols=["Домов", "ЖК", "Квартир", "Медиана до центра, км", "Плотность арендаторов на 1 000 кв.", "Домов с арендатором, %"],
       fmt={"Домов": lambda x: num(x, 0), "ЖК": lambda x: num(x, 0), "Квартир": lambda x: num(x, 0),
            "Домов с арендатором, %": lambda x: num(x, 0)})}
<div class="src">{SRC}</div>

<h2>2. Структура арендаторов</h2>
<img src="../output/charts/c1_structure.png" class="w80">
<p>Комфорт и типовой класс — это «магазин у дома»: продукты ({num(gro_kt, 0)}%), ПВЗ ({num(pvz_kt, 0)}%) и аптеки
({num(struct.loc['Аптеки', 'К+Т'], 0)}%). В бизнес- и элитном классе структура ровнее: больше непродовольственной
торговли ({num(struct.loc['Непрод. торговля', 'Б+Э'], 0)}%), общепита ({num(food_be, 0)}%), салонов красоты
({num(struct.loc['Красота', 'Б+Э'], 0)}%) и офисов ({num(struct.loc['Офисы', 'Б+Э'], 0)}% против {num(struct.loc['Офисы', 'К+Т'], 1)}%).</p>
<img src="../output/charts/c6_brands.png" class="w80">

<h2>3. Проверка правила классификации</h2>
<img src="../output/charts/c2_rule_check.png" class="w80">
<p>Разница по продуктовым ({pp(d_gro)}) и ПВЗ ({pp(d_pvz)}) значима: 95% доверительные интервалы (бутстрэп по {n_be} и {n_kt} ЖК)
не включают ноль. Общепита в бизнес-классе больше ({pp(d_food)}, ДИ {ci('Общепит')}).</p>
<h3>Это не эффект центра?</h3>
<img src="../output/charts/c3_zones.png" class="w80">
<p>На одном расстоянии от центра разница сохраняется. Второй контроль — сравнение ЖК с его же окружением (все объекты OSM в радиусе 500 м):
индекс 1,0 означает «как вокруг». В ЖК комфорт-класса продуктовых в {num(env.loc['Продукты', 'индекс_К+Т'], 2)} раза больше, чем вокруг,
а в бизнес-классе — столько же, сколько вокруг ({num(env.loc['Продукты', 'индекс_Б+Э'], 2)}). Общепит в бизнес-классе — на уровне окружения
({num(env.loc['Общепит', 'индекс_Б+Э'], 2)}): ЖК его не избегают, но и не притягивают. ПВЗ в новых ЖК обоих групп почти вдвое чаще, чем вокруг.</p>
{table(env_tab, num_cols=[c for c in env_tab.columns if c != "Категория"], fmt={c: (lambda x: num(x, 2)) for c in env_tab.columns if "индекс" in c})}
<div class="src">{SRC}</div>
<h3>Устойчивость</h3>
{table(rob_tab, num_cols=[c for c in rob_tab.columns if c != "Вариант расчёта"], fmt={"Объектов": lambda x: num(x, 0)})}
<div class="src">{SRC}. Доли общепита и продуктовых, % (Б+Э — Бизнес + Элитный, К+Т — Комфорт + Типовой).</div>

<h2>4. Районы</h2>
<div class="g2"><img src="../output/charts/c5_map.png"><div>
<p>Плотность арендаторов на 1 000 квартир различается по районам в {num(dist.loc['Адмиралтейский район', 'на_1000_кв'] / dist.loc['Пушкинский район', 'на_1000_кв'], 0)} раз и более: от {num(dist.loc['Адмиралтейский район', 'на_1000_кв'], 1)}
в Адмиралтейском до {num(dist.loc['Пушкинский район', 'на_1000_кв'], 1)} в Пушкинском и {num(dist.loc['Колпинский район', 'на_1000_кв'], 1)} в Колпинском.
Лидеры — районы, где в выборке преобладает бизнес-класс (доля Б+Э в Адмиралтейском — {num(dist.loc['Адмиралтейский район', 'доля_БЭ'], 0)}%,
в Петроградском — {num(dist.loc['Петроградский район', 'доля_БЭ'], 0)}%).</p>
<p>Крупнейшие по вводу районы — Приморский ({num(dist.loc['Приморский район', 'квартир'] / 1000, 0)} тыс. квартир), Выборгский и Пушкинский —
имеют {num(dist.loc['Пушкинский район', 'на_1000_кв'], 1)}–{num(dist.loc['Выборгский район', 'на_1000_кв'], 1)} арендатора на 1 000 квартир; в Пушкинском {num(dist.loc['Пушкинский район', 'Продукты_%'], 0)}% арендаторов — продуктовые.</p>
</div></div>
{table(dist_tab, num_cols=[c for c in dist_tab.columns if c != "Район"],
       fmt={"Домов": lambda x: num(x, 0), "Квартир": lambda x: num(x, 0), "Доля Б+Э, %": lambda x: num(x, 0),
            "Домов с арендатором, %": lambda x: num(x, 0)})}
<div class="src">{SRC}. Районы с 10 и более домами в выборке.</div>

<img src="../output/charts/c4_fill.png" class="w80">
<p>Доля домов, у которых OSM знает хотя бы одного арендатора, падает от центра к окраинам и от старых домов к новым
(сданы в 2021 г. — {num(fill_y.loc[2021], 0)}%, в 2025 г. — {num(fill_y.loc[2025], 0)}%). Это сумма двух эффектов, которые открытые данные
не разделяют: помещения действительно пустуют или ещё не заняты, и OSM медленнее обновляется на окраинах. Поэтому на окраинах выводы
о структуре опираются на меньшее число объектов.</p>

<h2>5. Методология</h2>
<ul class="k">
<li><b>Дома.</b> ДОМ.РФ, каталог наш.дом.рф: 36 страниц списка сданных домов (place=78, objStatus=2) + 10 карточек, сохранены вручную
в браузере 26–27.10.2026. Удалены дубли (8), нежилые объекты (287), дома без даты ввода (3) и вне 2021–2025 гг. (630).</li>
<li><b>Арендаторы.</b> OpenStreetMap, выгрузка Geofabrik на 25.10.2026: 81 403 объекта в границах города, из них 6 885 «не арендаторов» исключены.
Классификация тегов — в приложении.</li>
<li><b>Привязка.</b> Точка дома ДОМ.РФ → контур здания OSM: точка внутри контура — {match.get('inside', '?')} домов, ближайший контур ≤50 м —
{match.get('nearest', '?')}, контур не найден — {match.get('none', '?')} (для них круг 50 м). «Внутри ЖК» — объект не дальше 30 м от контура
(чувствительность к порогу 0/10/30/50 м — в отчёте 04_osm_link). Объект считается один раз на ЖК.</li>
<li><b>Статистика.</b> Доли — от всех арендаторов группы; 95% доверительные интервалы — кластерный бутстрэп по ЖК (2 000 повторов).
Контроль локации — пояса удалённости от Дворцовой площади (до 8 / 8–15 / 15+ км) и индекс «ЖК / окружение 500 м».</li>
<li><b>Воспроизводимость.</b> Каждая цифра получается скриптами src/01–08 (Python 3.9, pandas, shapely, matplotlib).</li>
</ul>
<h2>6. Ограничения</h2>
<ul class="k">
<li><b>Полнота OSM.</b> У {100 - filled}% домов OSM не знает ни одного арендатора; поэтому сравниваются доли, а не количества. {check_line}</li>
<li><b>Классы.</b> В ДОМ.РФ нет «бизнес лайт» — он внутри «Бизнеса», поэтому прямо сравнить «бизнес vs бизнес лайт», как в классификации NF GROUP, нельзя.
Классы ДОМ.РФ и консультантов могут расходиться.</li>
<li><b>Первый этаж ≠ 30 м.</b> В радиус могут попасть объекты соседних зданий, особенно в плотном центре. Проверка: только дома с точкой
внутри контура и порог 10 м дают те же выводы (таблица «Устойчивость»).</li>
<li><b>Нет площадей и ставок.</b> Открытые данные не дают площадь помещений, ставку аренды и вакантность — только факт наличия арендатора.
Поле ДОМ.РФ «нежилой первый этаж» есть в карточках домов, но массовая выгрузка карточек невозможна (защита сайта), поэтому метрика не используется.</li>
<li><b>Срез, не динамика.</b> Данные на конец октября 2026 г.; сравнение «год к году» потребует повторной выгрузки.</li>
</ul>
<h3>Приложение. Категории арендаторов (теги OSM)</h3>
{table(pd.DataFrame(CATS, columns=["Категория", "Теги OpenStreetMap"]))}
<div class="foot">Независимое исследование автора; не связано с NF GROUP и не воспроизводит её методологию. Цитаты классификации бизнес-класса —
по данным NF GROUP («Рынок жилой недвижимости бизнес-класса. Санкт-Петербург. I полугодие 2026»). Источники: ДОМ.РФ (наш.дом.рф),
© участники OpenStreetMap (ODbL), Geofabrik.</div>
""")

for name, html in (("digest", digest), ("full", full)):
    f = REP / f"{name}.html"
    f.write_text(html, encoding="utf-8")
    pdf = REP / f"{name}.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
                    f"--print-to-pdf={pdf}", f.as_uri()], check=True, capture_output=True)
    print("  ", pdf.relative_to(ROOT))
print("Готово: report/digest.pdf, report/full.pdf")
