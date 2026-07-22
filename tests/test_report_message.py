"""Интеграционные тесты Telegram-сообщения: секция «Реализовано», портфель,
примечания. Скрипт запускается как процесс — покрывается сборка списков в main()."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'process_report.py'


def _project(pid, name, status, closed_at=None, owner='Иванов И.И.', priority=False):
    return {
        'id': pid, 'name': name, 'status': status,
        'closed_at': closed_at, 'defense_at': None,
        'is_priority': priority, 'owner_short': owner,
        'url': f'https://rm.example/{pid}', 'deadline': '31.12.2026',
        'internal_hours': None, 'external_hours': None,
    }


REPORT_MD = """🔵 Закрытый на этой неделе
👤 Иванов И.И.
🔗 https://rm.example/1

✅ Выполнено:
Этап 3. Внедрение (26.06.2026)

🔵 Активный проект
👤 Петров П.П.
🔗 https://rm.example/2

✅ Выполнено:
Этап 1. Анализ (01.06.2026)

📍 Текущие этапы (в работе):
Этап 2. Разработка (31.10.2026)

Доп. информация: сроки этапа 2 сдвигаются, итоговая дата проекта не меняется.
"""


def _run(tmp_path, projects, report_md=REPORT_MD):
    (tmp_path / 'data.json').write_text(
        json.dumps({'projects': projects}, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'ОТЧЕТ_15.07.md').write_text(report_md, encoding='utf-8')

    result = subprocess.run(
        [sys.executable, str(SCRIPT), 'ОТЧЕТ_15.07.md', '--telegram-only'],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return (tmp_path / 'telegram_transform_15_07_2026.txt').read_text(encoding='utf-8')


@pytest.fixture
def portfolio():
    return [
        _project(1, 'Закрытый на этой неделе', 'Закрыта', closed_at='26.06.2026'),
        _project(2, 'Активный проект', 'В работе', owner='Петров П.П.'),
        _project(3, 'Проект без отчёта', 'В работе', owner='Сидоров С.С.'),
    ]


def test_closed_project_appears_once_and_counters_agree(tmp_path, portfolio):
    """Проект, закрытый на отчётной неделе, — только в «Реализовано»,
    не дублируется в списке «в работе»; счётчики сходятся."""
    msg = _run(tmp_path, portfolio)

    assert msg.count('Закрытый на этой неделе') == 1
    assert '📈 Портфель: 3 · ✅ реализовано 1 · 🔄 в работе 2' in msg
    assert '🔵 ТРАНСФОРМАЦИОННЫЕ ПРОЕКТЫ (1)' in msg
    # блок «в работе» остался только у активного проекта
    assert '1. 🔵 Активный проект' in msg


def test_completed_section_format_and_position(tmp_path, portfolio):
    msg = _run(tmp_path, portfolio)

    assert '✅ РЕАЛИЗОВАНО В 2026 (1)' in msg
    assert '1. Закрытый на этой неделе — 26.06.2026 · Иванов И.И.' in msg
    assert '🔗 https://rm.example/1' in msg
    # секция стоит до списка проектов в работе
    assert msg.index('✅ РЕАЛИЗОВАНО') < msg.index('🔵 ТРАНСФОРМАЦИОННЫЕ ПРОЕКТЫ')


def test_note_rendered_as_separate_block(tmp_path, portfolio):
    msg = _run(tmp_path, portfolio)

    assert 'ℹ️ Дополнительно:' in msg
    assert 'сроки этапа 2 сдвигаются' in msg
    # примечание не осталось хвостом блока «В работе»
    work_block = msg.split('📍 В работе:')[1].split('ℹ️ Дополнительно:')[0]
    assert 'сроки этапа 2 сдвигаются' not in work_block


def test_project_without_report_goes_to_not_reported(tmp_path, portfolio):
    msg = _run(tmp_path, portfolio)

    assert '⚠️ ИНФОРМАЦИЯ НЕ ПРЕДСТАВЛЕНА' in msg
    assert '• Проект без отчёта' in msg


def test_no_completed_projects_section_hidden_but_portfolio_shown(tmp_path):
    projects = [
        _project(2, 'Активный проект', 'В работе', owner='Петров П.П.'),
        _project(1, 'Закрытый в прошлом году', 'Закрыта', closed_at='11.12.2025'),
    ]
    msg = _run(tmp_path, projects)

    assert 'РЕАЛИЗОВАНО' not in msg
    assert 'Закрытый в прошлом году' not in msg
    assert '📈 Портфель: 1 · ✅ реализовано 0 · 🔄 в работе 1' in msg


def test_note_marked_new_when_changed(tmp_path, portfolio):
    """При --prev изменившееся примечание помечается 🆕."""
    (tmp_path / 'data.json').write_text(
        json.dumps({'projects': portfolio}, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'ОТЧЕТ_15.07.md').write_text(REPORT_MD, encoding='utf-8')
    (tmp_path / 'ОТЧЕТ_08.07.md').write_text(
        REPORT_MD.replace(
            'Доп. информация: сроки этапа 2 сдвигаются, итоговая дата проекта не меняется.',
            'Доп. информация: работы идут по графику, отклонений нет, сроки подтверждены.',
        ),
        encoding='utf-8',
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), 'ОТЧЕТ_15.07.md', '--telegram-only',
         '--prev', 'ОТЧЕТ_08.07.md'],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    msg = (tmp_path / 'telegram_transform_15_07_2026.txt').read_text(encoding='utf-8')

    assert '🆕 ℹ️ Дополнительно:' in msg


def test_closed_project_outside_current_year_stays_in_group(tmp_path):
    """Закрытый в прошлом году проект в секцию «Реализовано» не попадает —
    значит он должен остаться в списке проектов отчёта, а не исчезнуть."""
    projects = [
        _project(1, 'Закрытый на этой неделе', 'Закрыта', closed_at='11.12.2025'),
        _project(2, 'Активный проект', 'В работе', owner='Петров П.П.'),
    ]
    msg = _run(tmp_path, projects)

    assert 'РЕАЛИЗОВАНО' not in msg
    assert 'Закрытый на этой неделе' in msg
    assert '🔵 ТРАНСФОРМАЦИОННЫЕ ПРОЕКТЫ (2)' in msg


def test_note_not_marked_new_when_moved_from_block_body(tmp_path, portfolio):
    """Абзац был частью блока «В работе», стал примечанием — текст не новый."""
    (tmp_path / 'data.json').write_text(
        json.dumps({'projects': portfolio}, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'ОТЧЕТ_15.07.md').write_text(REPORT_MD, encoding='utf-8')
    # в прошлом отчёте тот же текст шёл прямо в теле блока (без пустой строки)
    (tmp_path / 'ОТЧЕТ_08.07.md').write_text(
        REPORT_MD.replace(
            'Этап 2. Разработка (31.10.2026)\n\nДоп. информация:',
            'Этап 2. Разработка (31.10.2026)\nДоп. информация:',
        ),
        encoding='utf-8',
    )

    subprocess.run(
        [sys.executable, str(SCRIPT), 'ОТЧЕТ_15.07.md', '--telegram-only',
         '--prev', 'ОТЧЕТ_08.07.md'],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    msg = (tmp_path / 'telegram_transform_15_07_2026.txt').read_text(encoding='utf-8')

    assert 'ℹ️ Дополнительно:' in msg
    assert '🆕 ℹ️ Дополнительно:' not in msg


def test_note_not_marked_new_when_unchanged(tmp_path, portfolio):
    (tmp_path / 'data.json').write_text(
        json.dumps({'projects': portfolio}, ensure_ascii=False), encoding='utf-8')
    (tmp_path / 'ОТЧЕТ_15.07.md').write_text(REPORT_MD, encoding='utf-8')
    (tmp_path / 'ОТЧЕТ_08.07.md').write_text(REPORT_MD, encoding='utf-8')

    subprocess.run(
        [sys.executable, str(SCRIPT), 'ОТЧЕТ_15.07.md', '--telegram-only',
         '--prev', 'ОТЧЕТ_08.07.md'],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    msg = (tmp_path / 'telegram_transform_15_07_2026.txt').read_text(encoding='utf-8')

    assert 'ℹ️ Дополнительно:' in msg
    assert '🆕 ℹ️ Дополнительно:' not in msg
