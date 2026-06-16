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
