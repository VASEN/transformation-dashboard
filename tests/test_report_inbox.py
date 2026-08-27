"""Тесты накопителя еженедельных отчётов (`report_inbox.py`).

Отчёты приходят владельцу пересылкой из мессенджера — текстом, который он не
контролирует: с шапкой, строками-разделителями направлений, названиями в другом
регистре. Поэтому проверяется прежде всего разбор реального сообщения и то, что
накопитель не создаёт фантомных проектов и не теряет присланное.

Скрипт запускается процессом в отдельном каталоге — так же, как его зовёт бот.
"""
import os
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MODULES = ('report_inbox.py', 'process_report.py', 'config.py',
           'extract_data.py', 'overdue_report.py')

# Реальное сообщение владельца: шапка, разделитель направления, два проекта.
SAMPLE = """ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ ПО ПРОЕКТАМ
📅 19.08– 26.08.2026

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
🔵 ПРОЕКТЫ ТРАНСФОРМАЦИ
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬

🔵 ИИ МОНИТОРИНГ ЗАКУПОК 223-ФЗ
👤 Алёхина А.Л.
🔗 https://transformation.rm.mosreg.ru/#/issues/11241

✅ Выполнено:
Корректировки ТЗ (08.06.2026)

📍 Текущие этапы (в работе):
ЭТАП 3. Внедрение функционала (09.10.2026)

🔵 ОПТИМИЗАЦИЯ ЗАКУПОК 223-ФЗ
👤 Петров А.М., Алёхина А.Л.
🔗 https://transformation.rm.mosreg.ru/#/issues/11242

✅ Выполнено:
ЭТАП 1 — функционал реализован (25.06.2026)

📍 Текущие этапы (в работе):
ЭТАП 3 — конфигуратор сроков (10.09.2026)
"""


def make_data(tmp_path, projects):
    (tmp_path / 'data.json').write_text(json.dumps({
        'updated_at': '26.08.2026 08:18',
        'config': {'year': 2026, 'hours_per_unit': 1972,
                   'redmine_base': 'https://transformation.rm.mosreg.ru/#/issues'},
        'summary': {}, 'projects': projects, 'all_tasks': [], 'curators': [],
    }, ensure_ascii=False), encoding='utf-8')


def project(pid, name, priority=False, status='В работе', owner='Иванов И.И.'):
    return {'id': pid, 'name': name, 'status': status, 'is_priority': priority,
            'owner_short': owner,
            'url': f'https://transformation.rm.mosreg.ru/#/issues/{pid}'}


@pytest.fixture
def sandbox(tmp_path):
    for m in MODULES:
        shutil.copy(ROOT / m, tmp_path / m)
    make_data(tmp_path, [
        project(11241, 'ИИ мониторинг закупок 223-ФЗ'),
        project(11242, 'Оптимизация закупок 223-ФЗ'),
        project(11246, 'Робот закупщик', priority=True),
        project(9999, 'Закрытый проект', status='Закрыта'),
    ])
    return tmp_path


def run(sandbox, *args, stdin=None):
    proc = subprocess.run(
        ['python3', 'report_inbox.py', '--json', *args],
        input=stdin, capture_output=True, text=True, cwd=str(sandbox), timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ───────────────────────────── приём ─────────────────────────────

def test_parses_real_forwarded_message(sandbox):
    """Сообщение как есть: шапка и разделитель отбрасываются, проекты приняты."""
    res = run(sandbox, 'add', '--stdin', stdin=SAMPLE)

    names = sorted(e['name'] for e in res['accepted'])
    assert names == ['ИИ мониторинг закупок 223-ФЗ', 'Оптимизация закупок 223-ФЗ']
    assert res['unknown'] == [], 'разделитель направления принят за проект'
    assert res['done_count'] == 2
    assert res['total'] == 3, 'закрытый проект попал в ожидаемые'
    assert res['complete'] is False


def test_matched_by_link_not_name(sandbox):
    """Проект опознаётся по ссылке — регистр и формулировка названия не важны."""
    res = run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    assert all(e['matched_by'] == 'id' for e in res['accepted'])


def test_resend_replaces_not_duplicates(sandbox):
    """Повторный отчёт по тому же проекту заменяет прежний, а не множит записи."""
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    res = run(sandbox, 'add', '--stdin', stdin=SAMPLE)

    assert res['accepted'] == []
    assert len(res['replaced']) == 2
    assert res['done_count'] == 2, 'повтор посчитан как новый отчёт'


def test_unknown_project_is_reported(sandbox):
    """Отчёт по проекту не из списка не теряется молча."""
    text = ('🔵 СОВЕРШЕННО ПОСТОРОННИЙ ПРОЕКТ\n'
            '🔗 https://transformation.rm.mosreg.ru/#/issues/70000\n\n'
            '✅ Выполнено:\nчто-то сделано\n')
    res = run(sandbox, 'add', '--stdin', stdin=text)

    assert res['accepted'] == []
    assert res['unknown'] == ['СОВЕРШЕННО ПОСТОРОННИЙ ПРОЕКТ']
    assert res['done_count'] == 0


def test_empty_block_is_not_a_report(sandbox):
    """Заголовок без тела отчётом не считается."""
    res = run(sandbox, 'add', '--stdin',
              stdin='🔵 ИИ мониторинг закупок 223-ФЗ\n👤 Кто-то\n')
    assert res['done_count'] == 0


# ───────────────────────────── статус ─────────────────────────────

def test_status_counts_only_active(sandbox):
    st = run(sandbox, 'status')
    assert st['total'] == 3
    assert [p['name'] for p in st['pending']].count('Закрытый проект') == 0

    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    st = run(sandbox, 'status')
    assert len(st['done']) == 2 and len(st['pending']) == 1
    assert st['pending'][0]['name'] == 'Робот закупщик'


def test_pending_lists_owner(sandbox):
    res = run(sandbox, 'pending')
    assert res['total'] == 3
    assert all('owner' in p for p in res['pending'])


# ───────────────────────────── сборка ─────────────────────────────

def test_build_refuses_until_complete(sandbox):
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    res = run(sandbox, 'build')
    assert res['ok'] is False
    assert not list(sandbox.glob('ОТЧЕТ_*.md')), 'отчёт собран раньше времени'


def test_build_force_collects_what_there_is(sandbox):
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    res = run(sandbox, 'build', '--force', '--no-process')

    assert res['ok'] is True and res['blocks'] == 2
    assert res['missing'] == ['Робот закупщик']
    text = Path(res['report']).read_text(encoding='utf-8')
    assert '🔵 ПРОЕКТЫ ТРАНСФОРМАЦИИ' in text
    # название нормализовано по data.json: прислали капсом, в отчёт идёт канон
    assert 'ИИ мониторинг закупок 223-ФЗ' in text
    assert 'ИИ МОНИТОРИНГ ЗАКУПОК 223-ФЗ' not in text
    assert 'issues/11241' in text, 'ссылка потеряна — по ней матчится process_report'


def test_build_when_complete_runs_without_force(sandbox):
    """Сдали все — сборка идёт сама, приоритетные отделены от остальных."""
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    run(sandbox, 'add', '--stdin',
        stdin=('🔴 РОБОТ ЗАКУПЩИК\n'
               '🔗 https://transformation.rm.mosreg.ru/#/issues/11246\n\n'
               '✅ Выполнено:\nпилот запущен (01.08.2026)\n'))
    res = run(sandbox, 'build', '--no-process')

    assert res['ok'] is True and res['blocks'] == 3
    text = Path(res['report']).read_text(encoding='utf-8')
    assert text.index('🔴 ПРИОРИТЕТНЫЕ ПРОЕКТЫ') < text.index('🔵 ПРОЕКТЫ ТРАНСФОРМАЦИИ')


def test_build_produces_two_summaries(sandbox):
    """Полный цикл: собранный отчёт проходит через process_report.py."""
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    res = run(sandbox, 'build', '--force')

    assert res['process_rc'] == 0, res.get('process_out')
    stamp = f'{date.today():%d_%m_%Y}'
    assert (sandbox / f'telegram_priority_{stamp}.txt').exists()
    assert (sandbox / f'telegram_transform_{stamp}.txt').exists()
    body = (sandbox / f'telegram_transform_{stamp}.txt').read_text(encoding='utf-8')
    assert 'ИИ мониторинг закупок 223-ФЗ' in body


# ───────────────────────────── цикл ─────────────────────────────

def test_reset_archives_and_starts_clean(sandbox):
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    res = run(sandbox, 'reset')

    assert res['archived'] and Path(res['archived']).exists()
    assert run(sandbox, 'status')['done'] == []
