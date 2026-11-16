"""Собирает data/darkstores.json и сжатые схемы проезда images/schemes/*.jpg.

Вход:
  <work>/stores.json  — результат tools/parse_stores.py (страница Ozon «Адреса и реквизиты складов Ozon Fresh»)
  <work>/imgs/        — картинки, вынутые tools/strip_images.py
  data/bez_adresa.txt — адреса складов, которых нет на странице (2ГИС, документ Ozon, проверка в Ozon Job)

usage: python3 -I tools/build_dataset.py <work_dir>
Реквизиты (ИНН/КПП, счета, GLN, GUID) в выход не попадают.
"""
import json
import sys
from pathlib import Path

from PIL import Image

work = Path(sys.argv[1])
root = Path(__file__).resolve().parent.parent
stores = json.loads((work / "stores.json").read_text(encoding="utf-8"))
out_img = root / "images" / "schemes"
out_img.mkdir(parents=True, exist_ok=True)

TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
               "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def slug(s):
    s = s.lower()
    r = "".join(TR.get(c, c if c.isascii() and c.isalnum() else "_") for c in s)
    while "__" in r:
        r = r.replace("__", "_")
    return r.strip("_")


DC = {"РЦ Рябиновая", "Бугры — Шоссейная", "ДС Лиговский", "РЦ Шапсугское"}
manual = {}
for line in (root / "data" / "bez_adresa.txt").read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    st, region, title, system, addr, src, how = [x.strip() for x in line.split(" | ")]
    manual[title] = {"status": st, "address": addr, "source": src, "how": "" if how == "—" else how}

items, seen, used_slugs = [], set(), set()
for s in stores:
    f = s["fields"]
    title, region = s["title"], s["region"]
    system = f.get("Название в системе", "").strip()
    addr = f.get("Фактический адрес", "").strip()
    if title in DC:
        continue
    key = (system, addr)
    if key in seen:          # дубль на самой странице
        continue
    seen.add(key)
    if addr:
        rec = {"status": "ok", "address": addr, "source": "страница Ozon", "how": ""}
    elif title in manual:
        rec = manual[title]
    else:
        print("нет данных:", region, title)
        continue
    sid = slug(system or (region + "_" + title))
    while sid in used_slugs:
        sid += "_2"
    used_slugs.add(sid)
    schemes = []
    for k, im in enumerate([i for i in s["images"] if i.get("after") == "Схема проезда"]):
        name = f"{sid}{'' if k == 0 else '_' + str(k + 1)}.jpg"
        with Image.open(work / "imgs" / im["file"]) as I:
            I = I.convert("RGB")
            I.thumbnail((1400, 1400))
            I.save(out_img / name, "JPEG", quality=72, optimize=True, progressive=True)
        schemes.append("images/schemes/" + name)
    items.append({
        "id": sid, "region": region, "name": title, "system": system,
        "address": rec["address"], "status": rec["status"], "source": rec["source"],
        "how": rec["how"], "schemes": schemes,
        "show": rec["status"] in ("ok", "app"),
    })

(root / "data" / "darkstores.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
print("записей:", len(items), "| на карту:", sum(i["show"] for i in items),
      "| по статусам:", dict(Counter(i["status"] for i in items)),
      "| схем:", sum(len(i["schemes"]) for i in items))
print("по регионам (на карту):", dict(Counter(i["region"] for i in items if i["show"])))
