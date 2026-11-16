"""Находит координаты складов через HTTP Геокодер Яндекса.

Запускается в GitHub Actions: ключ берётся из секрета YANDEX_MAPS_API_KEY (переменная окружения).
Ответы кешируются в data/geocode_cache.json — повторный запуск спрашивает только новые адреса.
Пишет координаты в data/darkstores.json и отчёт data/geocode_report.txt.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "darkstores.json"
CACHE = ROOT / "data" / "geocode_cache.json"
REPORT = ROOT / "data" / "geocode_report.txt"

KEY = os.environ.get("YANDEX_MAPS_API_KEY", "").strip()
if not KEY:
    sys.exit("Нет ключа: задайте секрет YANDEX_MAPS_API_KEY")

# город региона — подставляем, если в адресе его нет
REGION_CITY = {
    "Санкт-Петербург": "Санкт-Петербург", "Волгоград": "Волгоград", "Екатеринбург": "Екатеринбург",
    "Казань": "Казань", "Кострома": "Кострома", "Набережные Челны": "Набережные Челны",
    "Нижний Новгород": "Нижний Новгород", "Новосибирск": "Новосибирск", "Пермь": "Пермь",
    "Ростов-на-Дону": "Ростов-на-Дону", "Самара": "Самара", "Сочи": "Сочи", "Тверь": "Тверь",
    "Тюмень": "Тюмень", "Челябинск": "Челябинск",
}
# что должно встретиться в найденном адресе, чтобы точка точно была в своём регионе
REGION_CHECK = {
    "Москва и МО": ("Москва", "Московская область"),
    "Санкт-Петербург": ("Санкт-Петербург", "Ленинградская область"),
    "Краснодарский край": ("Краснодарский край", "Краснодар", "Адыгея"),
    "Адыгея": ("Адыгея",),
    "Набережные Челны": ("Набережные Челны", "Татарстан"),
}


def query_for(item):
    a = re.sub(r"^\s*\d{5,7}\s*,?\s*", "", item["address"])   # почтовый индекс
    a = re.sub(r"(?i)\bвн\.?\s*тер\.?\s*г\.?\s*", "", a)       # «вн.тер.г.»
    a = re.sub(r"\s+,", ",", a).strip(" ,")
    city = REGION_CITY.get(item["region"])
    if city and city.lower().replace("ё", "е") not in a.lower().replace("ё", "е"):
        a = f"{city}, {a}"
    return a


def geocode(q):
    url = "https://geocode-maps.yandex.ru/1.x/?" + urllib.parse.urlencode(
        {"apikey": KEY, "geocode": q, "format": "json", "lang": "ru_RU", "results": 1})
    req = urllib.request.Request(url, headers={"Referer": "https://barsicc.github.io/", "User-Agent": "darkstore-map/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                body = e.read().decode("utf-8", "replace").replace(KEY, "***")[:500]
                sys.exit(f"Геокодер отказал ({e.code}). Ответ Яндекса: {body}\n"
                         f"Длина ключа в секрете: {len(KEY)} символов (у ключа Яндекса обычно 36).")
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
        except urllib.error.URLError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    fm = d["response"]["GeoObjectCollection"]["featureMember"]
    if not fm:
        return None
    go = fm[0]["GeoObject"]
    md = go["metaDataProperty"]["GeocoderMetaData"]
    lon, lat = (float(x) for x in go["Point"]["pos"].split())
    return {"lat": round(lat, 6), "lon": round(lon, 6), "precision": md.get("precision", ""),
            "kind": md.get("kind", ""), "text": md.get("text", "")}


def main():
    items = json.loads(DATA.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    asked = 0
    for it in items:
        if not it.get("show"):
            continue
        q = query_for(it)
        if q not in cache:
            cache[q] = geocode(q)
            asked += 1
            time.sleep(0.15)
        g = cache[q]
        it["query"] = q
        if g:
            it.update({"lat": g["lat"], "lon": g["lon"], "geo_precision": g["precision"], "geo_text": g["text"]})
        else:
            for k in ("lat", "lon", "geo_precision", "geo_text"):
                it.pop(k, None)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    DATA.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    shown = [i for i in items if i.get("show")]
    prec = Counter(i.get("geo_precision", "не найден") for i in shown)
    lines = [f"Запросов к геокодеру в этом запуске: {asked}",
             f"Складов на карте: {len(shown)}; точность: {dict(prec)}", ""]
    bad = [i for i in shown if i.get("geo_precision") != "exact"]
    lines.append(f"Найдены не точно до дома ({len(bad)}):")
    for i in bad:
        lines.append(f"  [{i.get('geo_precision', 'не найден')}] {i['region']} | {i['name']} | {i['address']} -> {i.get('geo_text', '—')}")
    wrong = []
    for i in shown:
        need = REGION_CHECK.get(i["region"], (REGION_CITY.get(i["region"], i["region"]),))
        if i.get("geo_text") and not any(n.lower() in i["geo_text"].lower() for n in need):
            wrong.append(i)
    lines += ["", f"Найдены не в своём регионе ({len(wrong)}):"]
    for i in wrong:
        lines.append(f"  {i['region']} | {i['name']} | {i['address']} -> {i['geo_text']}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
