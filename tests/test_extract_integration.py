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


def test_project_shares_are_summed(tmp_path):
    """Проект разнесён по долям двух кураторов — величины суммируются,
    а строка с хвостом-версией («Проект А 2.0») сопоставляется с «Проект А»."""
    redmine, shtatka, vysv = build_fixtures(tmp_path, split_shares=True)
    out = tmp_path / 'data.json'
    extract(redmine, shtatka, vysv, output_file=str(out))

    proj = json.loads(out.read_text(encoding='utf-8'))['projects'][0]
    assert proj['internal_hours'] == 4000 + 1000
    assert proj['external_hours'] == 5000 + 500
    assert proj['total_units'] == pytest.approx(9.16 + 1.0)
    assert proj['plan_hours'] == 9000 + 1500
    # ссылка берётся из первой строки, где она заполнена
    assert proj['url'] == 'https://example/123'


def test_single_share_project_unchanged(tmp_path):
    """Без разнесения по долям значения остаются равны единственной строке."""
    redmine, shtatka, vysv = build_fixtures(tmp_path)
    out = tmp_path / 'data.json'
    extract(redmine, shtatka, vysv, output_file=str(out))

    proj = json.loads(out.read_text(encoding='utf-8'))['projects'][0]
    assert proj['internal_hours'] == 4000
    assert proj['external_hours'] == 5000
    assert proj['total_units'] == pytest.approx(9.16)


def test_shares_do_not_affect_curator_totals(tmp_path):
    """Итоги кураторов считаются по строкам-заголовкам — суммирование долей
    проектов на них не влияет (доля Гуляева = 1.0 шт.ед., не задваивается)."""
    redmine, shtatka, vysv = build_fixtures(tmp_path, split_shares=True)
    out = tmp_path / 'data.json'
    extract(redmine, shtatka, vysv, output_file=str(out))

    curators = {c['name']: c for c in json.loads(out.read_text(encoding='utf-8'))['curators']}
    assert curators['Гуляев В.А.']['vysv_units'] == pytest.approx(1.0)
    assert curators['Кренёва А.А.']['vysv_units'] == pytest.approx(9.16)


def test_ambiguous_version_names_are_skipped(tmp_path, capsys):
    """Два проекта, отличающиеся только версией, дали бы одинаковые часы обоим —
    оверлей не применяется, в лог идёт предупреждение."""
    import pandas as pd
    redmine, shtatka, vysv = build_fixtures(tmp_path)
    df = pd.read_excel(redmine)
    twin = df[df['Трекер'] == 'Паспорт проекта'].copy()
    twin['#'] = 200
    twin['Проект'] = 'Проект А 2.0'
    pd.concat([df, twin], ignore_index=True).to_excel(redmine, index=False)

    out = tmp_path / 'data.json'
    extract(redmine, shtatka, vysv, output_file=str(out))

    projects = json.loads(out.read_text(encoding='utf-8'))['projects']
    assert len(projects) == 2
    assert all(p['internal_hours'] is None for p in projects)
    assert 'неоднозначные названия' in capsys.readouterr().out
