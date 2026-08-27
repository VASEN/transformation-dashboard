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


# ────────── находки независимого ревью (круг 1) ──────────

def test_saves_raw_message_verbatim(sandbox):
    """Присланное сохраняется дословно — отчёт живёт только в чате.

    Разбор выбрасывает строки вне секций (риски, готовность) и не спасает
    хвост сообщения, разрезанного Telegram по длине. Сырьё — единственная
    страховка: восстановить блок иначе можно только попросив прислать заново.
    """
    text = SAMPLE + '\n📉 Риски: подрядчик сорвал поставку\n📊 Готовность 40%\n'
    run(sandbox, 'add', '--stdin', stdin=text)

    raws = list((sandbox / 'report_inbox' / 'current' / '_raw').glob('*.md'))
    assert len(raws) == 1
    saved = raws[0].read_text(encoding='utf-8')
    assert saved == text, 'присланное сохранено не дословно'
    assert 'подрядчик сорвал поставку' in saved


def test_block_keeps_completed_section(sandbox):
    """Сохранённый блок содержит присланное «Выполнено».

    Без этой проверки мутация «сохранять блок до ✅» проходила незамеченной
    во всех тестах сразу.
    """
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    block = (sandbox / 'report_inbox' / 'current' / '11241.md').read_text(encoding='utf-8')
    assert '✅ Выполнено:' in block
    assert 'Корректировки ТЗ (08.06.2026)' in block
    assert '📍 Текущие этапы' in block
    assert 'ЭТАП 3. Внедрение функционала (09.10.2026)' in block


def test_closed_project_does_not_complete_the_week(sandbox):
    """Проект, закрывшийся за неделю, не считается сдавшим.

    `data.json` обновляется автопрогоном каждое утро. Пока сдавшие считались
    по всем накопленным ключам, закрытие проекта досрочно давало «сдали все»:
    неделя закрывалась, а отчёт собирался без тех, кого реально ждали.
    """
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)          # сдали 11241 и 11242
    make_data(sandbox, [                                   # 11241 закрылся в Redmine
        project(11241, 'ИИ мониторинг закупок 223-ФЗ', status='Закрыта'),
        project(11242, 'Оптимизация закупок 223-ФЗ'),
        project(11246, 'Робот закупщик', priority=True),
    ])
    st = run(sandbox, 'status')

    assert st['complete'] is False, 'закрытый проект досчитал неделю до полной'
    assert len(st['done']) == 1
    assert [p['name'] for p in st['pending']] == ['Робот закупщик']

    res = run(sandbox, 'build')
    assert res['ok'] is False, 'сборка пошла, хотя ждём отчёт'


def test_stale_cycle_rotates_before_accepting(sandbox):
    """Блоки прошлой недели не доживают до следующей.

    Сборка «без опоздавших» намеренно оставляет неделю открытой. Через неделю
    первый же свежий отчёт добирал старьё до полноты, и оно уезжало в сводку
    руководству как актуальное.
    """
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    meta_path = sandbox / 'report_inbox' / 'current' / '_meta.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta['opened_at'] = '2026-08-01T09:00:00+03:00'        # неделя с лишним назад
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')

    res = run(sandbox, 'add', '--stdin',
              stdin=('🔴 РОБОТ ЗАКУПЩИК\n'
                     '🔗 https://transformation.rm.mosreg.ru/#/issues/11246\n\n'
                     '✅ Выполнено:\nпилот запущен\n'))

    assert res['cycle_rotated'] is True
    assert res['done_count'] == 1, 'блоки прошлой недели дожили до новой'
    assert res['complete'] is False
    assert list((sandbox / 'report_inbox').glob('2026-*')), 'прошлая неделя не заархивирована'


def test_wrong_link_warns_before_overwriting(sandbox):
    """Ссылка не от того проекта не переписывает чужой блок молча."""
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    res = run(sandbox, 'add', '--stdin',
              stdin=('🔵 ЭЛЕКТРОННЫЕ ДС С ПИК\n'
                     '🔗 https://transformation.rm.mosreg.ru/#/issues/11241\n\n'
                     '✅ Выполнено:\nчто-то другое\n'))

    kinds = [w['kind'] for w in res['warnings']]
    assert 'name_mismatch' in kinds, 'подмена проекта прошла без предупреждения'


def test_poorer_resend_warns_and_keeps_copy(sandbox):
    """Досылка без «Выполнено» предупреждает и оставляет прежнюю версию."""
    run(sandbox, 'add', '--stdin', stdin=SAMPLE)
    res = run(sandbox, 'add', '--stdin',
              stdin=('🔵 ИИ МОНИТОРИНГ ЗАКУПОК 223-ФЗ\n'
                     '🔗 https://transformation.rm.mosreg.ru/#/issues/11241\n\n'
                     '📍 Текущие этапы (в работе):\nЭТАП 4\n'))

    assert any(w['kind'] == 'section_lost' for w in res['warnings'])
    prev = sandbox / 'report_inbox' / 'current' / '_prev' / '11241.md'
    assert prev.exists() and 'Корректировки ТЗ' in prev.read_text(encoding='utf-8')
