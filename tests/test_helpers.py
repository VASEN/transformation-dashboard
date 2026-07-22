from datetime import date, timedelta

import pandas as pd
import pytest

from extract_data import (
    canon_name,
    project_key,
    sum_opt,
    clean_date,
    clean_pct,
    curator_key,
    get_urgency,
    short_name,
    validate_source_columns,
)
from overdue_report import (
    parse_deadline,
    plural_days,
    plural_projects,
    plural_tasks,
)


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


def test_plural_tasks():
    assert plural_tasks(1) == '1 задача'
    assert plural_tasks(3) == '3 задачи'
    assert plural_tasks(11) == '11 задач'
    assert plural_tasks(21) == '21 задача'


def test_plural_projects():
    assert plural_projects(1) == '1 проекте'
    assert plural_projects(3) == '3 проектах'
    assert plural_projects(11) == '11 проектах'
    assert plural_projects(21) == '21 проекте'


# ── project_key: матчинг проектов с файлом высвобождения ──────────────

def test_project_key_ignores_version_suffix():
    """«Цифровое нормирование 2.0» (Redmine) = «Цифровое нормирование» (файл высвобождения)."""
    assert project_key('Цифровое нормирование 2.0') == project_key('Цифровое нормирование')


def test_project_key_normalizes_case_yo_and_spaces():
    assert project_key('Единый  личный кабинет ГИС «ЕАСУЗ»') == \
           project_key('единый личный кабинет гис ЕАСУЗ')
    assert project_key('Смарт-допуск к ЗИТ') == project_key('смарт допуск к зит')
    assert project_key('Всё о закупках') == project_key('Все о закупках')


def test_project_key_keeps_law_number_suffix():
    """Хвост «223-ФЗ» — не номер версии, проекты не должны схлопываться."""
    assert project_key('Оптимизация закупок 223-ФЗ') != project_key('Оптимизация закупок')
    assert project_key('Цифровой протокол 223-ФЗ') != project_key('ИИ проверка 223-ФЗ')


def test_project_key_distinguishes_different_projects():
    assert project_key('ИИ проверка закупок') != project_key('ИИ мониторинг закупок 223-ФЗ')


def test_project_key_handles_empty():
    assert project_key(None) == ''
    assert project_key('') == ''


def test_sum_opt_handles_none():
    assert sum_opt(None, None) is None
    assert sum_opt(None, 5) == 5
    assert sum_opt(5, None) == 5
    assert sum_opt(2, 3) == 5
    assert sum_opt(0, None) == 0
