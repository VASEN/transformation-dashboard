"""Тесты блока «Реализовано» и примечаний к проектам (process_report.py)."""

from datetime import date

from process_report import (
    collect_completed,
    completed_date,
    project_url,
    split_note,
    build_current_status,
)


# ── completed_date / collect_completed ────────────────────────────────

def test_completed_date_prefers_closed_at():
    dp = {'closed_at': '12.03.2026', 'defense_at': '11.03.2026'}
    assert completed_date(dp) == date(2026, 3, 12)


def test_completed_date_falls_back_to_defense():
    assert completed_date({'closed_at': None, 'defense_at': '11.03.2026'}) == date(2026, 3, 11)


def test_completed_date_none_when_no_dates():
    assert completed_date({'closed_at': None, 'defense_at': ''}) is None


def _dp(name, closed_at, priority=False, status='Закрыта'):
    return {'name': name, 'closed_at': closed_at, 'defense_at': None,
            'status': status, 'is_priority': priority}


def test_collect_completed_filters_year_group_and_status():
    projects = [
        _dp('в этом году', '26.06.2026'),
        _dp('в прошлом году', '11.12.2025'),
        _dp('приоритетный', '16.04.2026', priority=True),
        _dp('ещё в работе', None, status='В работе'),
    ]
    got = collect_completed(projects, priority=False, year=2026)
    assert [p['name'] for p in got] == ['в этом году']

    got_priority = collect_completed(projects, priority=True, year=2026)
    assert [p['name'] for p in got_priority] == ['приоритетный']


def test_collect_completed_sorted_newest_first():
    projects = [
        _dp('март', '12.03.2026'),
        _dp('июнь', '26.06.2026'),
        _dp('апрель', '16.04.2026'),
    ]
    got = collect_completed(projects, priority=False, year=2026)
    assert [p['name'] for p in got] == ['июнь', 'апрель', 'март']


def test_collect_completed_skips_closed_without_date():
    projects = [_dp('без даты', None)]
    assert collect_completed(projects, priority=False, year=2026) == []


def test_project_url_uses_field_then_id():
    assert project_url({'url': 'https://x/1', 'id': 42}) == 'https://x/1'
    assert project_url({'url': None, 'id': 42}).endswith('/42')
    assert project_url({'url': None, 'id': None}) is None


# ── split_note ────────────────────────────────────────────────────────

def test_split_note_explicit_marker():
    text = 'Этап 1. Работа (01.07.2026)\n\nДоп. информация: сроки сдвинуты на август.'
    body, note = split_note(text)
    assert body == 'Этап 1. Работа (01.07.2026)'
    assert note == 'сроки сдвинуты на август.'


def test_split_note_free_text_paragraph():
    long_line = (
        '11.06.2026 с Мингос проведено ВКС совещание, на котором определены '
        'ориентировочные сроки разработки ИИ-агента — до 31.07.2026.'
    )
    body, note = split_note(f'Этап 2. Разработка ТЗ (31.07.2026)\n\n{long_line}')
    assert body == 'Этап 2. Разработка ТЗ (31.07.2026)'
    assert note == long_line


def test_split_note_keeps_short_subitems():
    """Короткий подпункт этапа — не примечание."""
    text = ('Этап 1. Формирование ТЗ\n\n'
            'Анализ ТЗ со стороны аналитиков (05.06.2026)\n'
            '(При необходимости корректировка ТЗ)')
    body, note = split_note(text)
    assert note is None
    assert body == text


def test_split_note_keeps_bullet_list():
    text = ('Этап 1. Работа\n\n'
            '• Модуль комплектности (20.04.2026)\n'
            '• Модуль разночтения (25.05.2026)')
    body, note = split_note(text)
    assert note is None


def test_split_note_single_paragraph_without_marker():
    text = 'Этап 1. Работа (01.07.2026)'
    assert split_note(text) == (text, None)


def test_split_note_empty_input():
    assert split_note(None) == (None, None)
    assert split_note('') == ('', None)


def test_build_current_status_includes_note():
    status = build_current_status('сделано', 'в работе', 'важное примечание')
    assert '✅ Выполнено:\nсделано' in status
    assert '📍 В работе:\nв работе' in status
    assert 'ℹ️ Дополнительно:\nважное примечание' in status


def test_build_current_status_without_note_unchanged():
    status = build_current_status('сделано', 'в работе')
    assert 'ℹ️' not in status
