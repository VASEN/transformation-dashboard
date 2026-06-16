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
