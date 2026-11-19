# Карта дарксторов Ozon fresh

Данные для неофициальной карты складов. В репозитории уже есть 445 записей, 389 файлов схем и скрипты подготовки данных. У 439 записей стоит `show: true`. Сайт и координаты пока в работе.

- [Источники и история проекта](NOTES.md)
- [Как перенести проект и продолжить работу](docs/HANDOFF.md)
- [Аудит адресов и схем](docs/DATA_AUDIT.md)

Проверка текущих данных из корня репозитория:

```bash
python3 tools/audit_dataset.py
```

Для пересборки из исходного SingleFile HTML нужен Python 3.12. Установи зависимости в отдельное окружение:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

В Windows используй `py -3.12 -m venv .venv` и `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`. Команды пересборки и действия с ключом Яндекса описаны в инструкции переноса.
