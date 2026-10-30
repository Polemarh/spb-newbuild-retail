"""
T5b. Выборка домов, для которых сохраняем карточки ДОМ.РФ вручную (вариант «а», решение 27.10).

Зачем: в карточке дома есть поля, которых нет в списке, — nonlivFirstFloor (1 = нежилой первый этаж)
и objNonlivElemCnt (число нежилых помещений). Все 789 карточек сохранить нельзя: при частом открытии
сайт ДОМ.РФ блокирует пользователя (защита от ботов, 27.10). Поэтому берём выборку:
  - Бизнес и Элитный — все дома (это «верхняя» группа главного сравнения, их мало);
  - Комфорт — 50 случайных домов, Типовой — 25 случайных (фиксированное зерно, воспроизводимо).
Допущение: случайные 50/25 домов представляют свои классы. В отчёте даём долю ± погрешность
и честно пишем, что «нижняя» группа — выборка, а не все дома.

Вход:  data/processed/zk.csv
Выход: data/processed/card_sample.csv              — obj_id, класс, ЖК, сохранена ли уже карточка
       data/raw/domrf/_links_cards_sample.html     — ссылки блоками по 25 с порядком сохранения
"""
import random
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/domrf"
SEED = 2026
N_RANDOM = {"Комфорт": 50, "Типовой": 25}

zk = pd.read_csv(ROOT / "data/processed/zk.csv")
have = {int(p.stem.split("_")[1]) for p in RAW.glob("card_*.json")}

parts = [zk[zk.class_name.isin(["Элитный", "Бизнес"])]]
for cls, n in N_RANDOM.items():
    pool = zk[zk.class_name == cls].sort_values("obj_id")
    ids = random.Random(SEED).sample(list(pool.obj_id), min(n, len(pool)))
    parts.append(pool[pool.obj_id.isin(ids)])
order = {"Элитный": 0, "Бизнес": 1, "Типовой": 2, "Комфорт": 3}
s = pd.concat(parts).assign(o=lambda d: d.class_name.map(order)).sort_values(["o", "zk_name", "obj_id"])
s["have_card"] = s.obj_id.isin(have)
s[["obj_id", "class_name", "zk_name", "district", "ready_year", "have_card"]].to_csv(
    ROOT / "data/processed/card_sample.csv", index=False)

todo = s[~s.have_card].reset_index(drop=True)
rows, BLOCK = [], 25
for i, r in todo.iterrows():
    if i % BLOCK == 0:
        rows.append(f'<tr><th colspan=5 style="background:#eef;text-align:left">Блок {i//BLOCK+1} '
                    f'(№{i+1}–{min(i+BLOCK, len(todo))}) — после блока пауза 10 мин</th></tr>')
    rows.append(f'<tr><td>{i+1}</td><td><a href="https://наш.дом.рф/сервисы/api/object/{r.obj_id}" target="_blank">'
                f'дом {r.obj_id}</a></td><td>{r.class_name}</td><td>{r.zk_name}</td><td><code>card_{r.obj_id}.json</code></td></tr>')
html = f"""<!doctype html><meta charset="utf-8"><title>ДОМ.РФ — карточки (выборка)</title>
<style>body{{font-family:-apple-system,sans-serif;margin:24px}}td,th{{padding:3px 8px;border-bottom:1px solid #ddd;font-size:14px}}a:visited{{color:#999}}</style>
<h2>Карточки: выборка {len(s)} домов, осталось сохранить {len(todo)}</h2>
<p><b>Медленно, чтобы сайт снова не заблокировал:</b> одна ссылка раз в 15–20 секунд, после блока из 25 — пауза 10 минут.
Если появилась страница «Доступ заблокирован» — не сохраняйте её, остановитесь на час.<br>
Открыть → ⌘S → формат «Исходный код страницы» → имя из последней колонки → папка data/raw/domrf/.<br>
Проверка: <code>ls ~/Desktop/projects/pet1/data/raw/domrf/card_*.json | wc -l</code></p>
<table>{''.join(rows)}</table>"""
(RAW / "_links_cards_sample.html").write_text(html, encoding="utf-8")
print(f"Выборка: {len(s)} домов ({s.class_name.value_counts().to_dict()}); уже есть: {int(s.have_card.sum())}; сохранить: {len(todo)}")
