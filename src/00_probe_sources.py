"""
T2. Разведка источников данных (запускать на Mac).
Только стандартная библиотека Python — ничего ставить не нужно.

Что делает:
  1. ДОМ.РФ (наш.дом.рф): запрашивает список объектов по СПб (регион 78) в нескольких
     вариантах фильтра статуса и одну карточку объекта. Сохраняет сырые ответы в data/raw/probe/.
  2. OpenStreetMap (Overpass API): маленький тестовый запрос (кафе в радиусе 300 м от Невского, 1).
  3. Печатает отчёт и сохраняет его в data/raw/probe/probe_report.txt.

Запросов немного (≈6), между ними пауза 2 с — сайт не нагружаем.
Эндпоинты ДОМ.РФ неофициальные (их использует сам сайт); взяты из открытого парсера
github.com/fukttt/nash.dom.rf.parser. Структура ответа может отличаться — для этого и разведка.
"""
import json, sys, time, platform, urllib.request, urllib.parse, urllib.error
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "probe"
OUT.mkdir(parents=True, exist_ok=True)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
BASE = "https://xn--80az8a.xn--d1aqf.xn--p1ai/" + urllib.parse.quote("сервисы") + "/api"
report = []

def log(s=""):
    print(s); report.append(s)

def get(url, data=None, ctype=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json, */*"})
    if ctype: req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()

def keys_tree(obj, prefix="", depth=0, out=None):
    """Список всех ключей JSON (вложенные — через точку), с примером значения."""
    out = out if out is not None else []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)) and depth < 3:
                keys_tree(v, p, depth + 1, out)
            else:
                out.append(f"{p} = {str(v)[:70]!r}")
    elif isinstance(obj, list) and obj:
        keys_tree(obj[0], prefix + "[0]", depth + 1, out)
    return out

log(f"Python {sys.version.split()[0]} | {platform.platform()}")
log(f"Время запуска: {time.strftime('%Y-%m-%d %H:%M:%S')}")
log("=" * 70)

# ---------- 1. ДОМ.РФ: список объектов СПб ----------
variants = {
    "list_all":      "place=78",
    "list_status0":  "place=78&objStatus=0",
    "list_status1":  "place=78&objStatus=1",
}
first_obj_id = None
for name, q in variants.items():
    url = f"{BASE}/kn/object?offset=0&limit=20&sortField=obj_publ_dt&sortType=desc&{q}"
    st, body = get(url)
    (OUT / f"domrf_{name}.json").write_bytes(body)
    log(f"\n[ДОМ.РФ] {name}: HTTP {st}, {len(body)} байт")
    try:
        d = json.loads(body)
        data = d.get("data", d) if isinstance(d, dict) else d
        lst = data.get("list") if isinstance(data, dict) else data
        total = data.get("total") if isinstance(data, dict) else None
        log(f"  всего объектов по фильтру (total): {total}; в ответе: {len(lst) if lst else 0}")
        if lst:
            first_obj_id = first_obj_id or lst[0].get("objId")
            if name == "list_all":
                log("  Поля объекта в списке:")
                for line in keys_tree(lst[0]): log("    " + line)
    except Exception as e:
        log(f"  не JSON / неожиданная структура: {e}. Начало ответа: {body[:200]!r}")
    time.sleep(2)

# ---------- 1b. ДОМ.РФ: карточка одного объекта ----------
if first_obj_id:
    st, body = get(f"{BASE}/object/{first_obj_id}")
    (OUT / "domrf_object_card.json").write_bytes(body)
    log(f"\n[ДОМ.РФ] карточка objId={first_obj_id}: HTTP {st}, {len(body)} байт")
    try:
        d = json.loads(body)
        log("  Поля карточки:")
        for line in keys_tree(d.get("data", d)): log("    " + line)
    except Exception as e:
        log(f"  не JSON: {e}. Начало: {body[:200]!r}")
    time.sleep(2)
else:
    log("\n[ДОМ.РФ] карточку не запрашивали — не получили objId из списка")

# ---------- 2. OpenStreetMap / Overpass ----------
q = '[out:json][timeout:25];node["amenity"="cafe"](around:300,59.9365,30.3155);out 5;'
for host in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
    st, body = get(host, data=urllib.parse.urlencode({"data": q}).encode(),
                   ctype="application/x-www-form-urlencoded")
    try:
        n = len(json.loads(body).get("elements", []))
    except Exception:
        n = "не JSON"
    log(f"\n[Overpass] {host}: HTTP {st}, кафе найдено: {n}")
    if st == 200: break
    time.sleep(2)

log("\n" + "=" * 70)
log("Готово. Сырые ответы и отчёт: data/raw/probe/")
(OUT / "probe_report.txt").write_text("\n".join(report), encoding="utf-8")
