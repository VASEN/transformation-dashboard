from datetime import date, timedelta

import pandas as pd
import pytest

from extract_data import (
    canon_name,
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
