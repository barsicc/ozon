"""Разбирает stripped.html (страница Ozon «Адреса и реквизиты складов Ozon Fresh»)
в список складов: регион, название, поля «Метка: значение», картинки, прочий текст.

usage: python3 -I parse_stores.py <work_dir>
"""
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

work = Path(sys.argv[1])
html = (work / "stripped.html").read_text(encoding="utf-8", errors="replace")
images = json.loads((work / "images.json").read_text(encoding="utf-8"))

# --sf-img-N: url("IMG#k") из корневых стилей SingleFile
var_map = {m.group(1): int(m.group(2)) for m in re.finditer(r'--sf-img-(\d+)\s*:\s*url\(\s*["\']?IMG#(\d+)', html)}

soup = BeautifulSoup(html, "lxml")
h1 = soup.find("h1")
# основной контейнер статьи: ближайший предок h1, где есть h2
article = h1
while article is not None and not article.find("h2"):
    article = article.parent

LABEL_RE = re.compile(r"^\s*([^:]{2,80}?):\s*(.*)$", re.S)


def clean(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def img_ref(tag):
    style = tag.get("style", "") or ""
    m = re.search(r"var\(--sf-img-(\d+)\)", style)
    if m and m.group(1) in var_map:
        return var_map[m.group(1)]
    src = tag.get("src", "") or ""
    m = re.match(r"IMG#(\d+)", src)
    if m:
        return int(m.group(1))
    return None


stores = []
region = None
cur = None
stop = False
seen_p = set()

for el in article.descendants:
    if stop:
        break
    if not isinstance(el, Tag):
        continue
    name = el.name
    if name in ("h2", "h3"):
        txt = clean(el.get_text(" "))
        if name == "h2":
            if txt.startswith("Помогла эта информация"):
                stop = True
                continue
            region = txt
            cur = {"region": region, "title": txt, "fields": {}, "images": [], "text": [], "_headless": True}
            stores.append(cur)
        else:
            cur = {"region": region, "title": txt, "fields": {}, "images": [], "text": []}
            stores.append(cur)
        continue
    if cur is None:
        continue
    if name == "img":
        k = img_ref(el)
        if k is not None:
            meta = images[k]
            if meta["mime"] != "image/svg+xml":
                cur["images"].append({"img": k, "file": meta["file"], "bytes": meta["bytes"], "mime": meta["mime"],
                                      "after": cur.get("_last_label")})
        continue
    if name in ("p", "li"):
        if id(el) in seen_p:
            continue
        seen_p.add(id(el))
        txt = clean(el.get_text(" "))
        if not txt:
            continue
        b = el.find("b")
        m = LABEL_RE.match(txt)
        if b is not None and m:
            label = clean(m.group(1))
            value = clean(m.group(2))
            # одна метка может встретиться дважды — склеиваем
            if label in cur["fields"] and value:
                cur["fields"][label] += " | " + value
            else:
                cur["fields"][label] = value
            cur["_last_label"] = label
        else:
            cur["text"].append(txt)

stores = [s for s in stores if not (s.get("_headless") and not s["fields"])]
for s in stores:
    s.pop("_last_label", None)
    s.pop("_headless", None)

(work / "stores.json").write_text(json.dumps(stores, ensure_ascii=False, indent=1), encoding="utf-8")

# сводка
from collections import Counter
by_region = Counter(s["region"] for s in stores)
print("всего блоков:", len(stores))
for r, c in by_region.most_common():
    print(f"  {c:4d}  {r}")
msk = [s for s in stores if s["region"] == "Москва и МО"]
lab = Counter(l for s in msk for l in s["fields"])
print("\nМосква и МО — поля:")
for l, c in lab.most_common():
    print(f"  {c:4d}  {l}")
print("\nМосква и МО — картинок всего:", sum(len(s["images"]) for s in msk),
      "; блоков с картинками:", sum(1 for s in msk if s["images"]),
      "; блоков с фактическим адресом:", sum(1 for s in msk if s["fields"].get("Фактический адрес")))
print("блоков с доп. текстом:", sum(1 for s in msk if s["text"]))
