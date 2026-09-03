---
paths:
  - "upcoming_report.py"
  - "tests/test_upcoming_report.py"
  - ".claude/skills/upcoming-report/**"
---

# upcoming_report.py — справочник

Вынесено из CLAUDE.md 03.09.2026 (path-scoped).

## Справка по приближающимся срокам (`upcoming_report.py`)

`overdue_report.py` смотрит назад («что уже просрочено / горит сегодня»),
`upcoming_report.py` — вперёд: **какие задачи уйдут в просрочку**, если не закрыть их
в срок. Окно дат задаётся аргументами; результат выгружается в двух форматах.

### Запуск

```bash
python3 upcoming_report.py                        # сегодня .. +7 дней, txt + md
python3 upcoming_report.py --to 17.08.2026        # сегодня .. конкретная дата
python3 upcoming_report.py --days 4               # сегодня .. +4 дня
python3 upcoming_report.py --from 18.08.2026 --to 24.08.2026
python3 upcoming_report.py --format md            # txt | md | both (по умолчанию both)
python3 upcoming_report.py --include-overdue      # добавить ранее просроченные
python3 upcoming_report.py --stdout               # в консоль, без записи файлов
python3 upcoming_report.py --outdir /tmp/x --output ИМЯ --data data.json
```

Обёртка — локальный скилл `.claude/skills/upcoming-report/` (когда просят «справку
по срокам», «что горит на этой неделе», «задачи до ДД.ММ»).

### Выходные файлы

| Файл | Содержимое |
|------|-----------|
| `СПРАВКА_сроки_13-17.08.2026.txt` | Формат `overdue_tasks_*.txt` — готов к копированию в Telegram |
| `СПРАВКА_сроки_13-17.08.2026.md`  | Формат `СПРАВКА_*.md`: шапка + разбивка по датам, Часть 1 (детализация таблицами по проектам), Часть 2 (краткая сводка), Часть 3 («Обратить внимание») |

Имя формируется из окна (`window_slug`): один месяц → `13-17.08.2026`, разные месяцы →
`29.08-04.09.2026`, разные годы → `30.12.2026-05.01.2027`. Переопределяется `--output`.

> Справки **в git не хранятся** — это рабочие выгрузки под конкретную дату:
> `.txt` покрыт общим правилом `*.txt`, для markdown в `.gitignore` есть `СПРАВКА_*.md`.
> Пересобираются командой из актуального `data.json` в любой момент.

### Логика

- Отбор: дедлайн в `[--from .. --to]` включительно **и** статус ∉ `CLOSED_STATUSES`.
- Группировка по проекту (ответственный, ссылка, `is_priority` — из `projects[]`);
  группы сортируются по ближайшему сроку, задачи внутри — по дате.
- Задачи левее окна в справку не входят (только справочная строка) — для них
  `overdue_report.py`; `--include-overdue` сводит всё в один документ.
- **Два счётчика за левой границей** (`collect_window` → `stats`): `before_window`
  (срок < начала окна) и `overdue_now` (из них просрочено на сегодня). Различаются,
  когда окно начинается в будущем, — формулировку выбирает `before_window_line`.
- Имя выгрузки Redmine в шапке md определяется `detect_source`: файл `issues*.xlsx`
  рядом с `data.json`, mtime которого совпадает с `updated_at` (±60 c).
- Скрипт только **читает** `data.json`; пайплайн не запускает, рабочие файлы не трогает.
  Свежесть справки = свежесть `data.json` (обновляет владелец через `./deploy.sh`).

### Ключевые функции

| Функция | Назначение |
|---------|-----------|
| `parse_date_arg(s)` / `resolve_window(start, end, days, today)` | Разбор дат CLI и границы окна (умолчание — `DEFAULT_DAYS=7`); перевёрнутое окно → `ValueError` → `ap.error` |
| `window_slug(start, end)` / `window_title(start, end, with_year)` | Имя файла и заголовок периода |
| `collect_window(data, start, end, today, include_overdue)` | Группы задач + `stats` (`before_window` / `overdue_now`) |
| `before_window_line(stats, start, today, bold)` | Справочная строка про задачи левее окна (`bold` — для markdown) |
| `tasks_by_day(groups)` / `tasks_by_status(groups)` | Агрегаты для разбивки по датам и блока «Обратить внимание» |
| `time_left(days, style)` | «сегодня» / «завтра (1 день)» / «4 дня» (md) против «завтра, через 1 день» / «через 4 дня» (txt) |
| `detect_source(data_path, updated_at)` | Имя выгрузки `issues*.xlsx`, из которой собран `data.json` |
| `build_txt(...)` / `build_md(...)` | Рендер двух форматов |

Тесты: `tests/test_upcoming_report.py` — 29 тестов (окно дат, отбор, агрегаты, оба
рендера, экранирование `|` в md, CLI: запись файлов / `--stdout` / понятные ошибки).
