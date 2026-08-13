"""Тесты upcoming_report.py — окно дат, отбор задач, рендер txt/md."""
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from upcoming_report import (  # noqa: E402
    parse_date_arg, resolve_window, window_slug, window_title,
    collect_window, tasks_by_day, tasks_by_status, time_left,
    before_window_line, build_txt, build_md,
)

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 8, 13)


def _data():
    """Мини-набор: 2 проекта, задачи до/внутри/после окна + закрытая."""
    return {
        'updated_at': '13.08.2026 08:53',
        'projects': [
            {'name': 'Альфа', 'owner_short': 'Иванов И.И.', 'is_priority': True,
             'url': 'https://example/1'},
            {'name': 'Бета', 'owner_short': 'Петров П.П.', 'is_priority': False},
        ],
        'all_tasks': [
            {'id': 1, 'project': 'Альфа', 'theme': 'Просроченная',
             'status': 'Новая', 'executor_short': 'Сидоров С.С.', 'deadline': '10.08.2026'},
            {'id': 2, 'project': 'Альфа', 'theme': 'Сегодня',
             'status': 'В работе', 'executor_short': 'Сидоров С.С.', 'deadline': '13.08.2026'},
            {'id': 3, 'project': 'Бета', 'theme': 'Послезавтра',
             'status': 'Новая', 'executor_short': 'Кузнецов К.К.', 'deadline': '15.08.2026'},
            {'id': 4, 'project': 'Бета', 'theme': 'За окном',
             'status': 'Новая', 'executor_short': 'Кузнецов К.К.', 'deadline': '25.08.2026'},
            {'id': 5, 'project': 'Бета', 'theme': 'Закрытая в окне',
             'status': 'Закрыта', 'executor_short': 'Кузнецов К.К.', 'deadline': '14.08.2026'},
        ],
    }


# ─── окно дат ───

@pytest.mark.parametrize('raw,expected', [
    ('17.08.2026', date(2026, 8, 17)),
    ('2026-08-17', date(2026, 8, 17)),
    (' 17.08.2026 ', date(2026, 8, 17)),
])
def test_parse_date_arg(raw, expected):
    assert parse_date_arg(raw) == expected


def test_parse_date_arg_invalid():
    with pytest.raises(ValueError):
        parse_date_arg('17 августа')


def test_resolve_window_defaults_to_week():
    assert resolve_window(today=TODAY) == (TODAY, date(2026, 8, 20))


def test_resolve_window_days_and_explicit_end():
    assert resolve_window(days=4, today=TODAY) == (TODAY, date(2026, 8, 17))
    assert resolve_window(start=date(2026, 8, 18), end=date(2026, 8, 24), today=TODAY) \
        == (date(2026, 8, 18), date(2026, 8, 24))


def test_resolve_window_rejects_reversed():
    with pytest.raises(ValueError):
        resolve_window(start=date(2026, 8, 17), end=date(2026, 8, 13), today=TODAY)


@pytest.mark.parametrize('start,end,slug', [
    (date(2026, 8, 13), date(2026, 8, 17), 'СПРАВКА_сроки_13-17.08.2026'),
    (date(2026, 8, 29), date(2026, 9, 4),  'СПРАВКА_сроки_29.08-04.09.2026'),
    (date(2026, 12, 30), date(2027, 1, 5), 'СПРАВКА_сроки_30.12.2026-05.01.2027'),
])
def test_window_slug(start, end, slug):
    assert window_slug(start, end) == slug


def test_window_title_without_year():
    assert window_title(date(2026, 8, 13), date(2026, 8, 17)) == '13.08–17.08.2026'
    assert window_title(date(2026, 8, 13), date(2026, 8, 17), with_year=False) == '13.08–17.08'


# ─── отбор задач ───

def test_collect_window_excludes_closed_and_out_of_range():
    groups, stats = collect_window(_data(), TODAY, date(2026, 8, 17), today=TODAY)
    themes = {t['theme'] for g in groups for t in g['tasks']}
    assert themes == {'Сегодня', 'Послезавтра'}   # без закрытой, просроченной и «за окном»
    assert stats == {'before_window': 1, 'overdue_now': 1}


def test_collect_window_include_overdue():
    groups, stats = collect_window(_data(), TODAY, date(2026, 8, 17),
                                   today=TODAY, include_overdue=True)
    themes = {t['theme'] for g in groups for t in g['tasks']}
    assert 'Просроченная' in themes
    assert stats == {'before_window': 1, 'overdue_now': 1}
    alpha = next(g for g in groups if g['name'] == 'Альфа')
    assert alpha['overdue'] == 1
    assert alpha['tasks'][0]['days_left'] == -3


def test_collect_window_group_order_and_aggregates():
    groups, _ = collect_window(_data(), TODAY, date(2026, 8, 17), today=TODAY)
    assert [g['name'] for g in groups] == ['Альфа', 'Бета']   # по ближайшему сроку
    assert [g['total'] for g in groups] == [1, 1]
    assert groups[0]['min_dl'] == TODAY


def test_tasks_by_day_and_status():
    groups, _ = collect_window(_data(), TODAY, date(2026, 8, 17), today=TODAY)
    assert tasks_by_day(groups) == {date(2026, 8, 13): 1, date(2026, 8, 15): 1}
    assert tasks_by_status(groups) == {'В работе': 1, 'Новая': 1}


@pytest.mark.parametrize('days,style,expected', [
    (0,  'md',  'сегодня'),
    (1,  'md',  'завтра (1 день)'),
    (1,  'txt', 'завтра, через 1 день'),
    (4,  'md',  '4 дня'),
    (4,  'txt', 'через 4 дня'),
    (-3, 'md',  'просрочено на 3 дня'),
])
def test_time_left(days, style, expected):
    assert time_left(days, style) == expected


# ─── рендер ───

def test_build_txt_structure():
    groups, stats = collect_window(_data(), TODAY, date(2026, 8, 17), today=TODAY)
    txt = build_txt(groups, TODAY, date(2026, 8, 17), TODAY, stats, '13.08.2026 08:53')
    assert '📊 Справка по задачам на контроле: сроки 13.08–17.08.2026' in txt
    assert 'Всего: 2 задачи в 2 проектах' in txt
    assert '1. 🔴 Альфа' in txt        # приоритетный
    assert '2. 🔵 Бета' in txt
    assert '⏳ Задачи со сроком 13.08–17.08 (1):' in txt
    assert 'Справочно: ранее просроченных активных задач (срок < 13.08.2026) — 1' in txt
    assert '16.08.2026 (воскресенье): 0 задач' in txt   # пустые дни окна показаны


def test_build_md_structure_and_escaping():
    data = _data()
    data['all_tasks'][1]['theme'] = 'Этап 1 | доработка'
    groups, stats = collect_window(data, TODAY, date(2026, 8, 17), today=TODAY)
    md = build_md(groups, TODAY, date(2026, 8, 17), TODAY, stats,
                  '13.08.2026 08:53', 'issues_13.08.xlsx')
    assert md.startswith('# Справка по задачам со сроком 13.08–17.08.2026')
    assert 'выгрузка Redmine `issues_13.08.xlsx`' in md
    assert 'Этап 1 \\| доработка' in md          # пайп экранирован
    assert '### 1. Альфа ★' in md
    assert '| | **ИТОГО** | | **2** | |' in md
    assert '★ — приоритетный проект' in md
    assert '## Часть 3. Обратить внимание' in md


def test_before_window_line_future_window_separates_counters():
    """Окно в будущем: задачи до его начала ≠ просроченные на сегодня."""
    start, end = date(2026, 8, 20), date(2026, 8, 26)
    groups, stats = collect_window(_data(), start, end, today=TODAY)
    assert stats == {'before_window': 3, 'overdue_now': 1}   # 10/13/15.08 до окна, просрочена одна
    line = before_window_line(stats, start, TODAY)
    assert 'со сроком до начала периода — 3' in line
    assert 'уже просрочено на 13.08.2026 — 1' in line
    assert 'Ранее просроченных' not in line
    md = build_md(groups, start, end, TODAY, stats)
    assert 'со сроком до начала периода — **3**' in md
    assert 'уже просрочено на 13.08.2026 — **1**' in md


def test_build_empty_window():
    groups, stats = collect_window(_data(), date(2026, 9, 1), date(2026, 9, 5),
                                   today=TODAY)
    assert groups == []
    txt = build_txt(groups, date(2026, 9, 1), date(2026, 9, 5), TODAY, stats)
    md = build_md(groups, date(2026, 9, 1), date(2026, 9, 5), TODAY, stats)
    assert '✅ Задач со сроком в этом периоде нет.' in txt
    assert 'задач со сроком в этом периоде нет' in md


# ─── CLI ───

def test_cli_writes_both_formats(tmp_path):
    import json
    data_path = tmp_path / 'data.json'
    data_path.write_text(json.dumps(_data(), ensure_ascii=False), encoding='utf-8')
    res = subprocess.run(
        [sys.executable, str(ROOT / 'upcoming_report.py'),
         '--data', str(data_path), '--outdir', str(tmp_path),
         '--from', '13.08.2026', '--to', '17.08.2026'],
        capture_output=True, text=True, cwd=ROOT)
    assert res.returncode == 0, res.stderr
    assert (tmp_path / 'СПРАВКА_сроки_13-17.08.2026.txt').exists()
    assert (tmp_path / 'СПРАВКА_сроки_13-17.08.2026.md').exists()
    assert '2 задачи в 2 проектах' in res.stdout


def test_cli_stdout_does_not_write_files(tmp_path):
    import json
    data_path = tmp_path / 'data.json'
    data_path.write_text(json.dumps(_data(), ensure_ascii=False), encoding='utf-8')
    res = subprocess.run(
        [sys.executable, str(ROOT / 'upcoming_report.py'),
         '--data', str(data_path), '--outdir', str(tmp_path),
         '--from', '13.08.2026', '--days', '4', '--format', 'md', '--stdout'],
        capture_output=True, text=True, cwd=ROOT)
    assert res.returncode == 0, res.stderr
    assert res.stdout.lstrip().startswith('# Справка')
    assert not list(tmp_path.glob('СПРАВКА*'))


def test_cli_reversed_window_fails_cleanly(tmp_path):
    import json
    data_path = tmp_path / 'data.json'
    data_path.write_text(json.dumps(_data(), ensure_ascii=False), encoding='utf-8')
    res = subprocess.run(
        [sys.executable, str(ROOT / 'upcoming_report.py'),
         '--data', str(data_path), '--outdir', str(tmp_path),
         '--from', '17.08.2026', '--to', '13.08.2026'],
        capture_output=True, text=True, cwd=ROOT)
    assert res.returncode != 0
    assert 'Traceback' not in res.stderr
    assert 'раньше начала' in res.stderr
    assert not list(tmp_path.glob('СПРАВКА*'))


def test_cli_missing_data_fails_cleanly(tmp_path):
    res = subprocess.run(
        [sys.executable, str(ROOT / 'upcoming_report.py'),
         '--data', str(tmp_path / 'нет.json'), '--outdir', str(tmp_path),
         '--from', '13.08.2026', '--days', '4'],
        capture_output=True, text=True, cwd=ROOT)
    assert res.returncode != 0
    assert 'Traceback' not in res.stderr
    assert 'не читается' in res.stderr
