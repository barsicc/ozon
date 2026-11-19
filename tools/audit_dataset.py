"""Проверяет список складов и ссылки на схемы. Требуется только Python."""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "darkstores.json"
SCHEMES = ROOT / "images" / "schemes"


def normalized(value):
    return re.sub(r"[\W_]", "", value.casefold().replace("ё", "е"))


def main():
    stores = json.loads(DATA.read_text(encoding="utf-8"))
    if not isinstance(stores, list) or not stores:
        raise SystemExit("Ожидался непустой список складов.")

    errors = []
    visible = 0
    without_schemes = 0
    paths_by_hash = defaultdict(set)
    rows_by_field = {field: defaultdict(list) for field in ("id", "system", "address")}
    for index, store in enumerate(stores, 1):
        if not isinstance(store, dict):
            errors.append(f"Запись {index}: ожидался объект")
            continue
        label = store.get("id") or f"запись {index}"
        for field, rows in rows_by_field.items():
            value = store.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: пустое или некорректное поле {field}")
            else:
                rows[normalized(value)].append(label)

        status = store.get("status")
        show = store.get("show")
        if status not in ("ok", "app", "dup", "gone") or show is not (status in ("ok", "app")):
            errors.append(f"{label}: некорректное сочетание status и show")
        visible += show is True

        schemes = store.get("schemes")
        if not isinstance(schemes, list):
            errors.append(f"{label}: ожидался список schemes")
            continue
        without_schemes += show is True and not schemes
        for ref in schemes:
            if not isinstance(ref, str) or not ref.startswith("images/schemes/"):
                errors.append(f"{label}: некорректная ссылка на схему {ref!r}")
                continue
            path = (ROOT / ref).resolve()
            if path.parent != SCHEMES or not path.is_file():
                errors.append(f"{label}: не найдена схема {ref}")
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            paths_by_hash[digest].add(ref)

    for field, rows in rows_by_field.items():
        for labels in rows.values():
            if len(labels) > 1:
                message = f"Совпадение {field}: {', '.join(labels)}"
                if field == "id":
                    errors.append(message)
                else:
                    print(f"Проверить: {message}")

    for paths in paths_by_hash.values():
        if len(paths) > 1:
            print(f"Проверить одинаковые схемы: {', '.join(sorted(paths))}")

    print(f"Записей: {len(stores)}. Видимых: {visible}. Видимых без схем: {without_schemes}.")
    print(f"Файлов схем в записях: {sum(map(len, paths_by_hash.values()))}.")
    for error in errors:
        print(f"Ошибка: {error}")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
