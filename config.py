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
