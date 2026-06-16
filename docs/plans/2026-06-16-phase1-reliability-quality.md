# Фаза 1 «Надёжность + Качество» — План реализации

> **Для исполнителя (агента):** РЕКОМЕНДУЕМЫЙ СУБ-СКИЛЛ — `superpowers:subagent-driven-development` (или `superpowers:executing-plans`) для пошагового выполнения. Шаги размечены чекбоксами (`- [ ]`).

**Goal:** Застраховать пайплайн `extract_data.py → data.json → index.html` — ничего не ломается молча, изменения безопасны (валидация, единый конфиг, тесты, линтер).

**Architecture:** Новый `config.py` — единый источник констант и помощников матчинга колонок; импортируется всеми Python-скриптами и прокидывается подмножеством в `data.json` (ключ `config`), который читает `index.html`. `extract()` параметризуется (тестируемость), получает валидацию результата + атомарную запись. `index.html` получает `escapeHTML` и читает конфиг вместо хардкода. `deploy.sh` — явный `git add` + guard'ы. Тесты на pytest, линтер ruff.

**Tech Stack:** Python 3.13 (pandas, openpyxl), pytest, ruff; статический HTML/JS; bash.

**Ветка:** `phase1-reliability-quality` (уже создана, спека закоммичена).

**Приёмочный критерий всей фазы:** контрольный прогон на реальных файлах (`issues_16.06.xlsx` + штатка + высвобождение) даёт `data.json` с **теми же** цифрами (36 проектов / 613 задач / 5 кураторов / 17 просрочено / 122%) **плюс** ключ `config`; `pytest` и `ruff check` зелёные; дашборд открывается без ошибок.

---

## Карта файлов

| Файл | Действие | Ответственность |
|---|---|---|
| `config.py` | создать | константы (год, URL, 1972, кураторы, статусы) + резолвер колонок |
| `extract_data.py` | изменить | импорт config, параметризация `extract()`, валидация колонок/результата, атомарная запись, ключ `config` |
| `process_report.py` | изменить | `HOURS_PER_UNIT` из config |
| `overdue_report.py` | изменить | `REDMINE_BASE`, `CLOSED_STATUSES` из config |
| `index.html` | изменить | `escapeHTML`, чтение `data.config` вместо хардкода `2026`/`1972`/URL |
| `deploy.sh` | изменить | явный `git add` + guard'ы (JSON валиден, remotes есть, diff) |
| `tests/test_config.py` | создать | юниты резолвера колонок |
| `tests/test_helpers.py` | создать | юниты чистых хелперов |
| `tests/test_extract_integration.py` | создать | smoke на Excel-фикстуре + тест валидации |
| `tests/fixtures.py` | создать | генератор минимальных Excel-файлов |
| `pyproject.toml` | создать | конфиг ruff |

**Порядок задач:** Task 1 (config) → 2 (extract wiring) → 3 (process/overdue wiring) → 4 (R2 колонки) → 5 (R1 валидация+тесты) → 6 (index.html config) → 7 (R5 escape) → 8 (R4 deploy) → 9 (Q1 юниты) → 10 (Q2 ruff/типы).

---

## Task 0: Подготовка окружения

**Files:** — (только установка инструментов)

- [ ] **Step 1: Установить pytest и ruff**

Run: `pip3 install pytest ruff openpyxl`
Expected: `Successfully installed ...` (pandas/openpyxl уже есть для пайплайна).

- [ ] **Step 2: Создать каталог тестов**

Run: `mkdir -p tests && touch tests/__init__.py`
Expected: каталог `tests/` существует.

---

## Task 1: `config.py` — единый источник констант + резолвер колонок [R3]

**Files:**
- Create: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_config.py`:

```python
import pytest
from config import (
    normalize_col, resolve_column, require_column,
    public_config, HOURS_PER_UNIT, YEAR,
)


def test_normalize_collapses_spaces_and_lowercases():
    assert normalize_col('  Внутрнее   Высвобождение ') == 'внутрнее высвобождение'


def test_normalize_yo_to_e():
    assert normalize_col('Кренёва') == 'кренева'


def test_resolve_column_matches_by_normalized_name():
    cols = ['План, шт. ед.', 'Проект']
    assert resolve_column(cols, 'план,  шт. ед.') == 'План, шт. ед.'


def test_resolve_column_returns_none_when_absent():
    assert resolve_column(['A', 'B'], 'C') is None


def test_require_column_raises_with_helpful_message():
    with pytest.raises(KeyError) as exc:
        require_column(['Статус', 'Проект'], 'Трекер')
    msg = str(exc.value)
    assert 'Трекер' in msg
    assert 'Статус' in msg  # перечисляет доступные колонки


def test_public_config_shape():
    cfg = public_config()
    assert set(cfg) == {'year', 'redmine_base', 'hours_per_unit'}
    assert cfg['year'] == YEAR
    assert cfg['hours_per_unit'] == HOURS_PER_UNIT
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`.

- [ ] **Step 3: Создать `config.py`**

```python
"""config.py — единый источник констант и помощников пайплайна.

Импортируется extract_data.py / process_report.py / overdue_report.py.
Подмножество (public_config) пишется в data.json под ключом "config" и
читается index.html — чтобы убрать хардкод года/URL/коэффициента из HTML.
"""
from __future__ import annotations

import re

# ── Доменные константы ────────────────────────────────────────────────
YEAR: int = 2026
REDMINE_BASE: str = 'https://transformation.rm.mosreg.ru/#/issues'
HOURS_PER_UNIT: int = 1972  # часов в 1 шт.ед.

TOTAL_CURATOR: str = 'Комитет и РЦТ'
CURATOR_ORDER: tuple[str, ...] = (
    'Кренёва АА', 'Родевальд СЕ', 'Гуляев ВА', 'Кудряшов ЕС',
)
# Исправление написания фамилий (в штатке/высвобождении встречаются опечатки).
# Правильно — «Кудряшов» (через «о»), как в Redmine.
CURATOR_NAME_FIX: tuple[tuple[str, str], ...] = (('Кудряшев', 'Кудряшов'),)

ACTIVE_STATUSES: tuple[str, ...] = ('В работе', 'Новая', 'На проверке')
CLOSED_STATUSES: frozenset[str] = frozenset(
    {'Закрыта', 'Закрыто', 'Выполнено', 'Выполнена', 'Завершена'}
)

# Порог регрессии: если число проектов/задач просело больше этой доли
# относительно прошлого data.json — стоп (защита от пустой выгрузки).
REGRESSION_DROP_LIMIT: float = 0.5

# Синонимы колонок Excel (новый/старый формат файла высвобождения).
COLUMN_SYNONYMS: dict[str, tuple[str, ...]] = {
    'vysv_units': ('План, шт. ед.', 'высвобождение, шт. ед.'),
    'vysv_external': ('Внешнее высвобождение, часы', 'Внешнее высвобождение'),
    'vysv_internal': ('Внутрнее высвобождение', 'Внутреннее высвобождение'),
}


def public_config() -> dict:
    """Подмножество конфига, попадающее в data.json → index.html."""
    return {
        'year': YEAR,
        'redmine_base': REDMINE_BASE,
        'hours_per_unit': HOURS_PER_UNIT,
    }


# ── Помощники матчинга колонок ────────────────────────────────────────
def normalize_col(name: object) -> str:
    """Нормализует имя колонки: strip, lowercase, схлопывание пробелов, ё→е."""
    s = str(name).strip().lower().replace('ё', 'е')
    return re.sub(r'\s+', ' ', s)


def resolve_column(columns, *candidates: str) -> str | None:
    """Фактическое имя колонки из `columns`, совпавшее с одним из
    `candidates` по нормализованному виду; иначе None."""
    norm = {normalize_col(c): c for c in columns}
    for cand in candidates:
        hit = norm.get(normalize_col(cand))
        if hit is not None:
            return hit
    return None


def require_column(columns, key: str, *candidates: str) -> str:
    """Как resolve_column, но при отсутствии бросает понятную ошибку."""
    cands = candidates or (key,)
    hit = resolve_column(columns, *cands)
    if hit is None:
        raise KeyError(
            f"Колонка '{key}' не найдена. Ожидалась одна из: {list(cands)}. "
            f"В файле есть: {list(columns)}"
        )
    return hit
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Коммит**

```bash
git add config.py tests/__init__.py tests/test_config.py
git commit -m "feat(config): единый config.py — константы + резолвер колонок [R3]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `extract_data.py` — импорт config, параметризация, ключ `config` [R3]

**Files:**
- Modify: `extract_data.py` (строки 33–53 — константы; 132 — сигнатура `extract`; 135–306 — обращения к глобалам; 388–400 — result + запись; 419–420 — `__main__`)

- [ ] **Step 1: Заменить блок констант (строки 33–53) на импорт из config**

Было (строки 33–53):

```python
REDMINE_FILE = sys.argv[1] if len(sys.argv) > 1 else "issues.xlsx"
SHTATKA_FILE = sys.argv[2] if len(sys.argv) > 2 else "ШТАТКА_ДБ.xlsx"
VYSV_FILE    = sys.argv[3] if len(sys.argv) > 3 else "ПРОЕКТЫ_Данные по высвобождению.xlsx"
OUTPUT_FILE  = "data.json"

ACTIVE_STATUSES = ('В работе', 'Новая', 'На проверке')
CLOSED_STATUSES = ('Закрыта', 'Закрыто', 'Выполнено', 'Выполнена', 'Завершена')

# Старый формат VYSV_FILE: ...
CURATOR_ORDER = ['Кренёва АА', 'Родевальд СЕ', 'Гуляев ВА']
TOTAL_CURATOR = 'Комитет и РЦТ'

# Варианты имён колонок в файле высвобождения (новый/старый формат)
VYSV_UNITS_COLS    = ('План, шт. ед.', 'высвобождение, шт. ед.')
VYSV_EXTERNAL_COLS = ('Внешнее высвобождение, часы', 'Внешнее высвобождение')
VYSV_INTERNAL_COLS = ('Внутрнее высвобождение', 'Внутреннее высвобождение')

# Исправления написания фамилий ...
CURATOR_NAME_FIX = (('Кудряшев', 'Кудряшов'),)
```

Стало:

```python
from config import (
    ACTIVE_STATUSES, CLOSED_STATUSES, CURATOR_ORDER, TOTAL_CURATOR,
    CURATOR_NAME_FIX, COLUMN_SYNONYMS, REGRESSION_DROP_LIMIT,
    public_config, resolve_column, require_column,
)

DEFAULT_REDMINE = "issues.xlsx"
DEFAULT_SHTATKA = "ШТАТКА_ДБ.xlsx"
DEFAULT_VYSV    = "ПРОЕКТЫ_Данные по высвобождению.xlsx"

VYSV_UNITS_COLS    = COLUMN_SYNONYMS['vysv_units']
VYSV_EXTERNAL_COLS = COLUMN_SYNONYMS['vysv_external']
VYSV_INTERNAL_COLS = COLUMN_SYNONYMS['vysv_internal']
```

> `CLOSED_STATUSES` теперь `frozenset` — проверки `t['status'] in CLOSED_STATUSES` работают так же. `import os` добавить в шапку (нужен в Task 5).

- [ ] **Step 2: Добавить `import os` в шапку (после `import sys`, строка ~26)**

```python
import os
```

- [ ] **Step 3: Параметризовать `extract()` (строка 132)**

Было:

```python
def extract():

    # ── 1. Redmine выгрузка ──
    print(f"📂 Читаем {REDMINE_FILE}...")
    df = pd.read_excel(REDMINE_FILE)
```

Стало:

```python
def extract(redmine_file=DEFAULT_REDMINE, shtatka_file=DEFAULT_SHTATKA,
            vysv_file=DEFAULT_VYSV, output_file="data.json"):

    # ── 1. Redmine выгрузка ──
    print(f"📂 Читаем {redmine_file}...")
    df = pd.read_excel(redmine_file)
```

- [ ] **Step 4: Заменить оставшиеся обращения к глобалам внутри `extract()`**

В теле `extract()` заменить:
- `print(f"📂 Читаем {VYSV_FILE}...")` → `print(f"📂 Читаем {vysv_file}...")` (строка ~236)
- `vdf = pd.read_excel(VYSV_FILE)` → `vdf = pd.read_excel(vysv_file)` (строка ~237)
- `print(f"📂 Читаем {SHTATKA_FILE}...")` → `print(f"📂 Читаем {shtatka_file}...")` (строка ~305)
- `sh = pd.read_excel(SHTATKA_FILE)` → `sh = pd.read_excel(shtatka_file)` (строка ~306)

- [ ] **Step 5: Добавить ключ `config` в result (строка 388)**

Было:

```python
    result = {
        'updated_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
        'summary':    summary,
        'projects':   projects,
        'all_tasks':  all_tasks,
        'curators':   curators,
    }
```

Стало:

```python
    result = {
        'updated_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
        'config':     public_config(),
        'summary':    summary,
        'projects':   projects,
        'all_tasks':  all_tasks,
        'curators':   curators,
    }
```

- [ ] **Step 6: Заменить запись файла на вызов хелпера (строки 396–400) и `OUTPUT_FILE`**

Было:

```python
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        # Экранируем </ чтобы не ломать <script> блок при любом встраивании
        safe_json = json.dumps(result, ensure_ascii=False, indent=2)
        safe_json = safe_json.replace('</', '<\\/')
        f.write(safe_json)

    kb = Path(OUTPUT_FILE).stat().st_size // 1024
```

Стало (хелпер `write_json_atomic` добавим в Task 5; пока — прямой вызов с тем же поведением, но в `output_file`):

```python
    write_json_atomic(result, output_file)

    kb = Path(output_file).stat().st_size // 1024
```

И добавить заглушку-хелпер перед `def extract` (будет дополнен валидацией в Task 5):

```python
def write_json_atomic(result, output_file):
    """Пишет JSON во временный файл, проверяет парсингом, затем атомарно
    подменяет целевой — чтобы битый результат не затирал рабочий data.json."""
    tmp = output_file + '.tmp'
    safe_json = json.dumps(result, ensure_ascii=False, indent=2).replace('</', '<\\/')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(safe_json)
    json.loads(Path(tmp).read_text(encoding='utf-8'))  # sanity-парсинг
    os.replace(tmp, output_file)
```

- [ ] **Step 7: Перенести разбор `sys.argv` в `__main__` (строки 419–420)**

Было:

```python
if __name__ == '__main__':
    extract()
```

Стало:

```python
if __name__ == '__main__':
    extract(
        sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REDMINE,
        sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SHTATKA,
        sys.argv[3] if len(sys.argv) > 3 else DEFAULT_VYSV,
    )
```

- [ ] **Step 8: Проверить, что модуль импортируется без чтения argv**

Run: `python3 -c "import extract_data; print('ok')"`
Expected: `ok` (без ошибок — argv больше не читается на импорте).

- [ ] **Step 9: Контрольный прогон на реальных файлах — поведение не изменилось**

Run:
```bash
python3 extract_data.py issues_16.06.xlsx "ШТАТКА_ДБ_15.06.2026.xlsx" "Проекты_Данные по высвобождению_15.06.2026.xlsx" && python3 -c "import json; d=json.load(open('data.json')); print(d['config']); print(d['summary']['projects_total'], d['summary']['tasks_total'], len(d['curators']))"
```
Expected: `{'year': 2026, 'redmine_base': '...', 'hours_per_unit': 1972}` и `36 613 5`.

- [ ] **Step 10: Восстановить data.json из git (чтобы прогон не попал в коммит кода)**

Run: `git checkout -- data.json`
Expected: рабочее дерево чистое по `data.json`.

- [ ] **Step 11: Коммит**

```bash
git add extract_data.py
git commit -m "refactor(extract): config-импорт, параметризация extract(), ключ config, атомарная запись [R3]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `process_report.py` и `overdue_report.py` — константы из config [R3]

**Files:**
- Modify: `process_report.py:425` (`HOURS_PER_UNIT`)
- Modify: `overdue_report.py:21,26` (`CLOSED_STATUSES`, `REDMINE_BASE`)

- [ ] **Step 1: `process_report.py` — убрать локальный `HOURS_PER_UNIT`**

Добавить импорт в шапку (после `from difflib import SequenceMatcher`, строка ~19):

```python
from config import HOURS_PER_UNIT
```

Удалить строку 425 `HOURS_PER_UNIT = 1972` (оставив её использование на 430/433 — оно теперь берёт значение из импорта).

- [ ] **Step 2: `overdue_report.py` — взять `CLOSED_STATUSES`/`REDMINE_BASE` из config**

Было (строки 21, 26):

```python
CLOSED_STATUSES = {'Закрыта', 'Закрыто', 'Выполнено', 'Выполнена', 'Завершена'}
...
REDMINE_BASE = 'https://transformation.rm.mosreg.ru/#/issues'
```

Стало — добавить импорт после `from datetime import datetime, date` (строка ~19):

```python
from config import CLOSED_STATUSES, REDMINE_BASE
```

И удалить локальные определения `CLOSED_STATUSES` (21) и `REDMINE_BASE` (26).

> `CLOSED_STATUSES` из config — `frozenset`; используется только как `in`-проверка, поведение идентично.

- [ ] **Step 3: Smoke-проверка обоих скриптов на текущем data.json**

Run:
```bash
python3 overdue_report.py --output /tmp/overdue_check.txt && head -3 /tmp/overdue_check.txt
```
Expected: первые строки отчёта (`📊 Отчёт ...`), без ошибок импорта.

- [ ] **Step 4: Коммит**

```bash
git add process_report.py overdue_report.py
git commit -m "refactor(reports): HOURS_PER_UNIT/REDMINE_BASE/CLOSED_STATUSES из config [R3]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `extract_data.py` — проверка обязательных колонок [R2]

**Files:**
- Modify: `extract_data.py` (добавить хелпер + вызовы после каждого `read_excel`)
- Test: `tests/test_helpers.py`

- [ ] **Step 1: Написать падающий тест на `validate_source_columns`**

Создать `tests/test_helpers.py`:

```python
import pandas as pd
import pytest
from extract_data import validate_source_columns


def test_validate_passes_when_all_present():
    df = pd.DataFrame(columns=['Трекер', '#', 'Проект'])
    # не бросает
    validate_source_columns(df, ['Трекер', '#'], 'Redmine')


def test_validate_raises_listing_missing_and_available():
    df = pd.DataFrame(columns=['Статус', 'Проект'])
    with pytest.raises(KeyError) as exc:
        validate_source_columns(df, ['Трекер', '#'], 'Redmine')
    msg = str(exc.value)
    assert 'Redmine' in msg
    assert 'Трекер' in msg and '#' in msg
    assert 'Статус' in msg  # перечисляет, что реально есть
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python3 -m pytest tests/test_helpers.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_source_columns'`.

- [ ] **Step 3: Добавить хелпер в `extract_data.py` (рядом с другими утилитами, после `short_name`, ~строка 128)**

```python
def validate_source_columns(df, required, source_name):
    """Бросает понятную ошибку, если в df нет нужных колонок (с учётом синонимов)."""
    missing = [c for c in required if resolve_column(df.columns, c) is None]
    if missing:
        raise KeyError(
            f"В файле {source_name} отсутствуют колонки: {missing}. "
            f"Есть: {list(df.columns)}"
        )
```

- [ ] **Step 4: Вызвать проверку после каждого `read_excel` в `extract()`**

После `df = pd.read_excel(redmine_file)` (строка ~136):

```python
    validate_source_columns(
        df, ['Трекер', '#', 'Проект', 'Статус', 'Родительская задача'], redmine_file
    )
```

После `vdf = pd.read_excel(vysv_file)` (строка ~237):

```python
    validate_source_columns(vdf, ['Проект'], vysv_file)
```

После `sh = pd.read_excel(shtatka_file)` (строка ~306):

```python
    validate_source_columns(
        sh, ['Куратор направления', 'План высвобождения - 20%'], shtatka_file
    )
```

- [ ] **Step 5: Запустить тест — проходит**

Run: `python3 -m pytest tests/test_helpers.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Контрольный прогон + откат data.json**

Run:
```bash
python3 extract_data.py issues_16.06.xlsx "ШТАТКА_ДБ_15.06.2026.xlsx" "Проекты_Данные по высвобождению_15.06.2026.xlsx" >/dev/null && echo OK && git checkout -- data.json
```
Expected: `OK` (валидные файлы проходят проверку).

- [ ] **Step 7: Коммит**

```bash
git add extract_data.py tests/test_helpers.py
git commit -m "feat(extract): проверка обязательных колонок с понятной ошибкой [R2]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Валидация результата + атомарная запись + интеграционные тесты [R1]

**Files:**
- Modify: `extract_data.py` (дополнить `write_json_atomic` валидацией; добавить `validate_result`; чтение прошлого data.json)
- Create: `tests/fixtures.py` (генератор Excel)
- Create: `tests/test_extract_integration.py`

- [ ] **Step 1: Написать генератор фикстур `tests/fixtures.py`**

```python
"""Генератор минимальных Excel-файлов для интеграционных тестов extract()."""
import pandas as pd


def build_fixtures(dir_path, broken=False):
    """Создаёт три xlsx в dir_path. broken=True → Redmine без колонки 'Трекер'.
    Возвращает (redmine_path, shtatka_path, vysv_path)."""
    redmine = dir_path / 'issues.xlsx'
    shtatka = dir_path / 'shtatka.xlsx'
    vysv = dir_path / 'vysv.xlsx'

    trekker_col = 'НЕ_Трекер' if broken else 'Трекер'
    redmine_df = pd.DataFrame([
        {trekker_col: 'Паспорт проекта', '#': 100, 'Проект': 'Проект А',
         'Статус': 'В работе', 'Назначена': 'Иванов Иван Иванович',
         'Ответственный': 'Кренёва (ККП) Анастасия Андреевна',
         'Срок завершения': '31.12.2026', 'Готовность': '40%',
         'Родительская задача': None, 'Тема': None,
         'Приоритетный проект': 'Да',
         'План высвобождения трудозатрат всего, часы': 1972},
        {trekker_col: 'Мероприятие проекта', '#': 101, 'Проект': 'Проект А',
         'Статус': 'Новая', 'Назначена': 'Петров Пётр Петрович',
         'Ответственный': None, 'Срок завершения': '01.01.2026',
         'Готовность': '0%', 'Родительская задача': 100, 'Тема': 'Этап 1',
         'Приоритетный проект': None,
         'План высвобождения трудозатрат всего, часы': None},
    ])
    redmine_df.to_excel(redmine, index=False)

    shtatka_df = pd.DataFrame([
        {'Куратор направления': 'Кренёва А.А.', 'Кол-во ставок': 47,
         'из них ККП': 14, 'Факт ККП': 11, ' из них РЦТ': 33, 'Факт РЦТ': 25,
         'Кол-во фактическое': 36, 'Вакансии': 0,
         'План высвобождения - 20%': 7.2},
        {'Куратор направления': 'Комитет и РЦТ', 'Кол-во ставок': 47,
         'из них ККП': 14, 'Факт ККП': 11, ' из них РЦТ': 33, 'Факт РЦТ': 25,
         'Кол-во фактическое': 36, 'Вакансии': 0,
         'План высвобождения - 20%': 7.2},
    ])
    shtatka_df.to_excel(shtatka, index=False)

    vysv_df = pd.DataFrame([
        {'Ответственный': 'Кренёва А.А.', 'Проект': None,
         'План по проектам, часы': 9000, 'План, шт. ед.': 9.16,
         'Внешнее высвобождение, часы': 5000, 'Внутрнее высвобождение': 4000,
         'Факт высвобождения трудозатрат всего, часы': 0,
         'Ссылка на акцептованную идею': None},
        {'Ответственный': None, 'Проект': 'Проект А',
         'План по проектам, часы': 9000, 'План, шт. ед.': 9.16,
         'Внешнее высвобождение, часы': 5000, 'Внутрнее высвобождение': 4000,
         'Факт высвобождения трудозатрат всего, часы': 0,
         'Ссылка на акцептованную идею': 'https://example/123'},
    ])
    vysv_df.to_excel(vysv, index=False)

    return str(redmine), str(shtatka), str(vysv)
```

- [ ] **Step 2: Написать падающие интеграционные тесты `tests/test_extract_integration.py`**

```python
import json
import pytest
from extract_data import extract
from tests.fixtures import build_fixtures


def test_extract_produces_valid_data(tmp_path):
    redmine, shtatka, vysv = build_fixtures(tmp_path)
    out = tmp_path / 'data.json'
    extract(redmine, shtatka, vysv, output_file=str(out))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert {'updated_at', 'config', 'summary', 'projects',
            'all_tasks', 'curators'} <= set(data)
    assert data['config']['hours_per_unit'] == 1972
    assert data['config']['year'] == 2026
    assert len(data['projects']) == 1
    assert len(data['all_tasks']) == 1
    assert data['projects'][0]['is_priority'] is True


def test_broken_excel_does_not_overwrite(tmp_path):
    out = tmp_path / 'data.json'
    out.write_text('{"keep": true}', encoding='utf-8')  # «рабочий» файл
    redmine, shtatka, vysv = build_fixtures(tmp_path, broken=True)

    with pytest.raises((KeyError, ValueError)):
        extract(redmine, shtatka, vysv, output_file=str(out))

    # старый файл не затёрт
    assert json.loads(out.read_text(encoding='utf-8')) == {'keep': True}


def test_empty_projects_blocks_write(tmp_path, monkeypatch):
    out = tmp_path / 'data.json'
    out.write_text('{"keep": true}', encoding='utf-8')
    redmine, shtatka, vysv = build_fixtures(tmp_path)

    import extract_data
    # подменяем validate_result, имитируя пустой результат → должно бросить
    real = extract_data.validate_result

    def fake(result, prev=None, drop_limit=0.5):
        result['projects'] = []
        return real(result, prev, drop_limit)

    monkeypatch.setattr(extract_data, 'validate_result', fake)
    with pytest.raises(ValueError):
        extract(redmine, shtatka, vysv, output_file=str(out))
    assert json.loads(out.read_text(encoding='utf-8')) == {'keep': True}
```

- [ ] **Step 3: Запустить — убедиться, что падает**

Run: `python3 -m pytest tests/test_extract_integration.py -v`
Expected: FAIL — `validate_result` ещё не существует / нет вызова валидации.

- [ ] **Step 4: Добавить `validate_result` и встроить валидацию в `extract()`**

Добавить хелпер рядом с `write_json_atomic`:

```python
def validate_result(result, prev=None, drop_limit=REGRESSION_DROP_LIMIT):
    """Проверяет, что результат не пустой и не просел относительно прошлого.
    Бросает ValueError с понятным текстом при нарушении."""
    errs = []
    if not result.get('projects'):
        errs.append('нет проектов')
    if not result.get('all_tasks'):
        errs.append('нет задач')
    if not result.get('curators'):
        errs.append('нет кураторов')
    if prev:
        for key in ('projects', 'all_tasks'):
            old, new = len(prev.get(key, [])), len(result.get(key, []))
            if old and new < old * (1 - drop_limit):
                errs.append(
                    f'{key}: было {old}, стало {new} '
                    f'(просадка > {int(drop_limit * 100)}%)'
                )
    if errs:
        raise ValueError('Валидация data.json не пройдена: ' + '; '.join(errs))
```

Встроить вызов в `extract()` — заменить `write_json_atomic(result, output_file)` (из Task 2 Step 6) на:

```python
    prev = None
    if os.path.exists(output_file):
        try:
            prev = json.loads(Path(output_file).read_text(encoding='utf-8'))
        except (ValueError, OSError):
            prev = None
    validate_result(result, prev)
    write_json_atomic(result, output_file)
```

- [ ] **Step 5: Запустить тесты — проходят**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (все тесты config + helpers + integration).

- [ ] **Step 6: Контрольный прогон на реальных файлах + откат**

Run:
```bash
python3 extract_data.py issues_16.06.xlsx "ШТАТКА_ДБ_15.06.2026.xlsx" "Проекты_Данные по высвобождению_15.06.2026.xlsx" >/dev/null && echo OK && git checkout -- data.json
```
Expected: `OK` (реальные данные проходят валидацию, файл записан атомарно).

- [ ] **Step 7: Коммит**

```bash
git add extract_data.py tests/fixtures.py tests/test_extract_integration.py
git commit -m "feat(extract): валидация результата + атомарная запись + smoke-тесты [R1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `index.html` — чтение `data.config` вместо хардкода [R3]

**Files:**
- Modify: `index.html` (глобал CONFIG ~1025; initDashboard ~1841; 1972 на 1230,1482-1490; год на 1686,1710,1771,1838,1881; URL на 1426; статичный год на 817)

- [ ] **Step 1: Добавить глобал CONFIG (после строки 1025 `let allCurators = [];`)**

```javascript
let CONFIG = {
  year: 2026,
  hoursPerUnit: 1972,
  redmineBase: 'https://transformation.rm.mosreg.ru/#/issues',
};
```

- [ ] **Step 2: Заполнять CONFIG из data в initDashboard (после строки 1841 `allCurators = data.curators;`)**

```javascript
  if (data.config) {
    CONFIG = {
      year:         data.config.year ?? CONFIG.year,
      hoursPerUnit: data.config.hours_per_unit ?? CONFIG.hoursPerUnit,
      redmineBase:  data.config.redmine_base ?? CONFIG.redmineBase,
    };
  }
  const yearLabel = document.getElementById('yearLabel');
  if (yearLabel) yearLabel.textContent = CONFIG.year;
```

- [ ] **Step 3: Дать id статичному году (строка 817)**

Было:
```html
<span class="filter-select" style="cursor:default;pointer-events:none;opacity:0.9">2026</span>
```
Стало:
```html
<span id="yearLabel" class="filter-select" style="cursor:default;pointer-events:none;opacity:0.9">2026</span>
```

- [ ] **Step 4: Заменить `1972` на `CONFIG.hoursPerUnit` (строки 1230, 1482, 1484, 1490)**

- 1230: `(h / 1972)` → `(h / CONFIG.hoursPerUnit)`
- 1482: `(d.plan_hours / 1972)` → `(d.plan_hours / CONFIG.hoursPerUnit)`
- 1484: `(d.plan_hours_cio / 1972)` → `(d.plan_hours_cio / CONFIG.hoursPerUnit)`
- 1490: `(planExtVal / 1972)` → `(planExtVal / CONFIG.hoursPerUnit)`

- [ ] **Step 5: Заменить сравнения года (строки 1686, 1710, 1771, 1838, 1881)**

Заменить во всех пяти местах строковый литерал `'2026'` на `String(CONFIG.year)`:
- 1686: `d.deadline.split('.')[2] === '2026'` → `d.deadline.split('.')[2] === String(CONFIG.year)`
- 1710: аналогично
- 1838: `p.deadline.split('.')[2] === '2026'` → `... === String(CONFIG.year)`
- 1771: `p.deadline.endsWith('2026')` → `p.deadline.endsWith(String(CONFIG.year))`
- 1881: `p.deadline.endsWith('2026')` → `p.deadline.endsWith(String(CONFIG.year))`

> CONFIG заполняется в начале initDashboard (Step 2) — до строк 1881+, поэтому значения уже актуальны. Строки 1686/1710/1771 — внутри render-функций, вызываемых после initDashboard.

- [ ] **Step 6: Заменить URL в renderTasks (строка 1426)**

Было:
```javascript
<td ...>${t.id ? `<a href="https://transformation.rm.mosreg.ru/#/issues/${t.id}" target="_blank" rel="noopener noreferrer" class="task-link">${t.theme}</a>` : t.theme}</td>
```
Стало (URL из CONFIG; экранирование темы добавим в Task 7):
```javascript
<td ...>${t.id ? `<a href="${CONFIG.redmineBase}/${t.id}" target="_blank" rel="noopener noreferrer" class="task-link">${t.theme}</a>` : t.theme}</td>
```

- [ ] **Step 7: Проверить в браузере на реальном data.json**

Run: `python3 -m http.server 8765 >/dev/null 2>&1 & sleep 1; curl -s localhost:8765/data.json | python3 -c "import sys,json; print(json.load(sys.stdin)['config'])"; kill %1`
Expected: `{'year': 2026, 'redmine_base': '...', 'hours_per_unit': 1972}`.
Затем открыть `http://localhost:8765/` в браузере (визуальный компаньон / вручную) — дашборд показывает те же цифры, год «2026» в фильтре, ссылки задач рабочие.

- [ ] **Step 8: Коммит**

```bash
git add index.html
git commit -m "feat(ui): index.html читает год/1972/redmine из data.config [R3]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: `index.html` — `escapeHTML` для строк из data.json [R5]

**Files:**
- Modify: `index.html` (хелпер ~1027; сайты: 1107-1108, 1149-1151, 1425-1428, 1621, 1646, 1654, 1660, 1672)

- [ ] **Step 1: Добавить хелпер `escapeHTML` (в блок HELPERS, после строки 1027)**

```javascript
function escapeHTML(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
```

- [ ] **Step 2: renderProjTable — экранировать имя/owner (строки 1106-1108)**

- 1106: `data-name="${p.name.replace(/"/g,'&quot;')}"` → `data-name="${escapeHTML(p.name)}"`
- 1107: `${p.is_priority ? PRIORITY_STAR : ''}${p.name}` → `${p.is_priority ? PRIORITY_STAR : ''}${escapeHTML(p.name)}`
- 1108: `${p.owner_short || p.person || '—'}` → `${escapeHTML(p.owner_short || p.person || '—')}`

- [ ] **Step 3: renderFullProjTable — то же (строки 1147-1151)**

- 1147: `data-name="${p.name.replace(/"/g,'&quot;')}"` → `data-name="${escapeHTML(p.name)}"`
- 1149: `${p.is_priority ? PRIORITY_STAR : ''}${p.name}` → `...${escapeHTML(p.name)}`
- 1150: `${p.status}` → `${escapeHTML(p.status)}`
- 1151: `${p.owner_short || p.person || '—'}` → `${escapeHTML(p.owner_short || p.person || '—')}`

- [ ] **Step 4: renderTasks — экранировать project/theme/status/executor (строки 1425-1428)**

- 1425: `${t.project}` → `${escapeHTML(t.project)}`
- 1426: внутри ссылки `class="task-link">${t.theme}</a>` → `>${escapeHTML(t.theme)}</a>`, и ветка без id `: t.theme}` → `: escapeHTML(t.theme)}`
- 1427: `${t.status}` → `${escapeHTML(t.status)}`
- 1428: `${t.executor_short || t.person || '—'}` → `${escapeHTML(t.executor_short || t.person || '—')}`

- [ ] **Step 5: loadDetail — экранировать team/status-строки/goal/problem/indicators**

- 1621: `font-size:13px">${m}</div>` → `${escapeHTML(m)}</div>`
- 1646: `color:...">${s}</div>` → `>${escapeHTML(s)}</div>` (строка статуса проекта)
- 1654: `<div class="big-goal">${d.goal || '—'}</div>` → `${escapeHTML(d.goal || '—')}`
- 1660: `<span style="font-size:13px">${s}</span>` → `${escapeHTML(s)}` (описание/проблема)
- 1672: `<span class="indicator-text">${ind}</span>` → `${escapeHTML(ind)}`

> Числа (`${i+1}`, `${p.pct}`, `${t.id}`) и стили НЕ оборачиваем — там нет данных пользователя.

- [ ] **Step 6: Проверка в браузере**

Открыть дашборд (как в Task 6 Step 7) на реальном `data.json` — все вкладки рендерятся, имена/темы/статусы отображаются как раньше (визуально без изменений, т.к. реальные данные не содержат спецсимволов).

- [ ] **Step 7: Быстрый smoke на спецсимвол (опционально)**

Временно подставить в одном проекте `data.json` имя `Тест <b>&"` → убедиться, что текст выводится буквально, без поломки разметки. Откатить: `git checkout -- data.json`.

- [ ] **Step 8: Коммит**

```bash
git add index.html
git commit -m "fix(ui): escapeHTML для строк из data.json (имена/темы/статусы) [R5]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: `deploy.sh` — явный `git add` + guard'ы [R4]

**Files:**
- Modify: `deploy.sh` (строки 45–51)

- [ ] **Step 1: Заменить блок коммита/пуша (строки 45–51)**

Было:

```bash
echo "📦 Коммит data.json..."
git add .
git commit -m "data: обновление $(date '+%d.%m.%Y %H:%M')"

echo "📤 Пуш в репозитории..."
git push -u upstream main
git push -u origin main
```

Стало:

```bash
echo "🔎 Проверка data.json..."
if [ ! -s data.json ]; then
  echo "❌ data.json отсутствует или пуст — деплой остановлен" >&2
  exit 1
fi
if ! python3 -c "import json,sys; json.load(open('data.json'))" 2>/dev/null; then
  echo "❌ data.json не парсится как JSON — деплой остановлен" >&2
  exit 1
fi

echo "📦 Коммит data.json..."
git add data.json
if git diff --cached --quiet; then
  echo "ℹ️  data.json не изменился — коммит/пуш пропущены"
  exit 0
fi
git commit -m "data: обновление $(date '+%d.%m.%Y %H:%M')"

echo "📤 Пуш в репозитории..."
for remote in upstream origin; do
  if git remote get-url "$remote" >/dev/null 2>&1; then
    git push -u "$remote" main
  else
    echo "⚠️  remote '$remote' не настроен — пропускаю"
  fi
done
```

> Только `git add data.json` — отчёты/выгрузки `.txt`/`.xlsx` уже в `.gitignore`. Изменения кода (`*.py`, `index.html`, `docs/`) коммитятся отдельно вручную, не через автодеплой данных.

- [ ] **Step 2: Синтаксис-проверка**

Run: `bash -n deploy.sh && echo "syntax ok"`
Expected: `syntax ok`.

- [ ] **Step 3: Прогон логики diff-guard (без пуша)**

Run: `git stash --include-untracked >/dev/null 2>&1; bash -c 'set -e; [ -s data.json ] && python3 -c "import json; json.load(open(\"data.json\"))" && echo "guards pass"'; git stash pop >/dev/null 2>&1 || true`
Expected: `guards pass` (data.json валиден).

- [ ] **Step 4: Коммит**

```bash
git add deploy.sh
git commit -m "fix(deploy): явный git add data.json + guard'ы (JSON/diff/remotes) [R4]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Юнит-тесты чистых хелперов [Q1]

**Files:**
- Modify: `tests/test_helpers.py` (добавить тесты)

- [ ] **Step 1: Дописать тесты хелперов extract_data + overdue_report**

Добавить в `tests/test_helpers.py`:

```python
from extract_data import (
    get_urgency, short_name, curator_key, canon_name, clean_pct, clean_date,
)
from overdue_report import parse_deadline, plural_days, plural_tasks, plural_projects
from datetime import date, timedelta


def test_get_urgency_closed_is_ok():
    assert get_urgency('01.01.2020', 'Закрыта') == 'ok'


def test_get_urgency_overdue_and_future():
    past = (date.today() - timedelta(days=3)).strftime('%d.%m.%Y')
    future = (date.today() + timedelta(days=30)).strftime('%d.%m.%Y')
    assert get_urgency(past, 'В работе') == 'overdue'
    assert get_urgency(future, 'В работе') == 'ok'


def test_short_name_strips_parens():
    assert short_name('Кренева (ККП) Анастасия Андреевна') == 'Кренева А.А.'


def test_curator_key_normalizes_surname():
    assert curator_key('Кудряшов Е.С.') == 'кудряшов'
    assert curator_key('Кренёва А.А.') == 'кренева'


def test_canon_name_fixes_typo():
    assert canon_name('Кудряшев Е.С.') == 'Кудряшов Е.С.'


def test_clean_pct_parses_variants():
    assert clean_pct('40%') == 40
    assert clean_pct('40,5') == 40
    assert clean_pct(None) == 0


def test_clean_date_formats():
    assert clean_date('2026-06-16') == '16.06.2026'
    assert clean_date('16.06.2026') == '16.06.2026'


def test_parse_deadline_valid_and_invalid():
    assert parse_deadline('16.06.2026') == date(2026, 6, 16)
    assert parse_deadline('2026-06-16') is None
    assert parse_deadline(None) is None


def test_plural_days():
    assert plural_days(1) == '1 день'
    assert plural_days(3) == '3 дня'
    assert plural_days(11) == '11 дн.'
    assert plural_days(21) == '21 день'
```

> Проверить реальные имена функций множественного числа в `overdue_report.py` (`plural_days/plural_tasks/plural_projects`) — если отличаются, поправить импорт и удалить лишние ассерты.

- [ ] **Step 2: Запустить всё**

Run: `python3 -m pytest tests/ -v`
Expected: PASS (все тесты).

- [ ] **Step 3: Коммит**

```bash
git add tests/test_helpers.py
git commit -m "test: юниты чистых хелперов extract_data/overdue_report [Q1]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: `pyproject.toml` + ruff + type hints [Q2]

**Files:**
- Create: `pyproject.toml`
- Modify: Python-файлы (точечные type hints + правки ruff)

- [ ] **Step 1: Создать `pyproject.toml`**

```toml
[tool.ruff]
line-length = 120
target-version = "py312"
exclude = ["archive", ".superpowers"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B"]
ignore = ["E501"]  # длинные строки в готовых f-print допустимы

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Прогнать ruff и посмотреть замечания**

Run: `ruff check .`
Expected: список замечаний (неиспользуемые импорты после рефакторинга, порядок импортов).

- [ ] **Step 3: Автоисправить безопасное**

Run: `ruff check . --fix`
Expected: импорты отсортированы, мусор убран.

- [ ] **Step 4: Добавить type hints на ключевые функции extract_data.py**

Точечно (не 100%): сигнатуры утилит. Примеры:

```python
def clean_date(v) -> str | None:
def clean_pct(v) -> int:
def safe(v) -> str | None:
def short_name(full_name) -> str | None:
def get_urgency(deadline_str, status=None) -> str:
def validate_source_columns(df, required, source_name) -> None:
def validate_result(result, prev=None, drop_limit=REGRESSION_DROP_LIMIT) -> None:
def write_json_atomic(result, output_file) -> None:
def extract(redmine_file=DEFAULT_REDMINE, shtatka_file=DEFAULT_SHTATKA, vysv_file=DEFAULT_VYSV, output_file="data.json") -> None:
```

- [ ] **Step 5: Финальный прогон — ruff + pytest зелёные**

Run: `ruff check . && python3 -m pytest tests/ -v`
Expected: `All checks passed!` и все тесты PASS.

- [ ] **Step 6: Контрольный прогон пайплайна + откат data.json**

Run:
```bash
python3 extract_data.py issues_16.06.xlsx "ШТАТКА_ДБ_15.06.2026.xlsx" "Проекты_Данные по высвобождению_15.06.2026.xlsx" >/dev/null && python3 -c "import json; d=json.load(open('data.json')); print(d['summary']['projects_total'], d['summary']['tasks_total'], len(d['curators']), d['config']['hours_per_unit'])" && git checkout -- data.json
```
Expected: `36 613 5 1972`.

- [ ] **Step 7: Коммит**

```bash
git add pyproject.toml extract_data.py process_report.py overdue_report.py config.py
git commit -m "chore: ruff + type hints; pyproject.toml [Q2]

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Финал: документация и приёмка

- [ ] **Step 1: Обновить `CLAUDE.md`**

- Раздел «Файлы»: добавить `config.py`, `tests/`, `pyproject.toml`.
- Раздел «Зависимости»: добавить `pytest`, `ruff`.
- Раздел «История изменений»: дописать строки за 2026-06-16 по каждому пункту (формат `| 2026-06-16 | Файл: описание |`).

- [ ] **Step 2: Финальная проверка приёмки фазы**

Run: `ruff check . && python3 -m pytest tests/ -v`
Expected: всё зелёное.
Открыть дашборд на реальном `data.json` — те же цифры (36/613/5, 17 просрочено, 122%), ключ `config` присутствует.

- [ ] **Step 3: Коммит документации**

```bash
git add CLAUDE.md
git commit -m "docs(phase1): актуализация CLAUDE.md по итогам Фазы 1

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: Предложить владельцу мердж ветки `phase1-reliability-quality` в `main`**

---

## Самопроверка плана (выполнена при написании)

- **Покрытие спеки:** R1 (Task 5) · R2 (Task 4) · R3 (Tasks 1,2,3,6) · R4 (Task 8) · R5 (Task 7) · Q1 (Tasks 5,9) · Q2 (Task 10). Все пункты спеки имеют задачу.
- **Заглушки:** нет — каждый шаг содержит реальный код/команды.
- **Согласованность имён:** `write_json_atomic`, `validate_result`, `validate_source_columns`, `public_config`, `resolve_column`, `require_column`, `CONFIG.hoursPerUnit`, `escapeHTML` — используются единообразно во всех задачах.
- **Замечание для исполнителя:** имена функций множественного числа в `overdue_report.py` (Task 9 Step 1) сверить с фактическими перед запуском.
