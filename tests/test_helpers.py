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
