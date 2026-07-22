#!/usr/bin/env python3
"""
process_report.py — Обработка еженедельных отчётов по проектам трансформации.

Использование:
    python3 process_report.py ОТЧЕТ_01_04.md
    python3 process_report.py ОТЧЕТ_01_04.md --data data.json
    python3 process_report.py ОТЧЕТ_01_04.md --telegram-only
    python3 process_report.py ОТЧЕТ_01_04.md --no-telegram
"""

import json
import re
import sys
import os
import shutil
import argparse
from datetime import datetime, date
from difflib import SequenceMatcher

from config import HOURS_PER_UNIT, REDMINE_BASE, YEAR


CLOSED_STATUSES = {'Закрыта', 'Закрыто', 'Выполнено', 'Выполнена', 'Завершена'}

TELEGRAM_SEPARATOR_THICK = '━━━━━━━━━━━━━━━━'
TELEGRAM_SEPARATOR_THIN  = '─────────────────'

DEFAULT_FIRST_GROUP_NAME  = 'ТРАНСФОРМАЦИОННЫЕ ПРОЕКТЫ'
DEFAULT_FIRST_GROUP_EMOJI = '🔵'

FUZZY_MATCH_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_date_from_filename(filename):
    """Extract date from filename like ОТЧЕТ_01_04.md or ОТЧЕТ_01.04.md."""
    basename = os.path.basename(filename)
    m = re.search(r'(\d{1,2})[._](\d{1,2})(?:[._](\d{4}))?', basename)
    if m:
        day   = int(m.group(1))
        month = int(m.group(2))
        year  = int(m.group(3)) if m.group(3) else datetime.now().year
        try:
            return date(year, month, day)
        except ValueError:
            pass
    return date.today()


# ---------------------------------------------------------------------------
# Report parser
# ---------------------------------------------------------------------------

def extract_id_from_url(url):
    """Extract issue ID from Redmine URL.

    Handles variants:
      https://...rm.mosreg.ru/#/issues/11498
      https://...rm.mosreg.ru/issues/11245
    """
    m = re.search(r'(?:#/issues|/issues)/(\d+)', url)
    return int(m.group(1)) if m else None


# Явный маркер примечания в MD-отчёте.
NOTE_MARKER_RE = re.compile(
    r'^(?:ℹ️|📝|💬|❗|‼️|Примечание|Прим\.|Доп\.?\s*информация'
    r'|Дополнительно|Дополнительная информация|Справочно)\s*:?\s*',
    re.IGNORECASE,
)

# Строка выглядит как пункт списка / этап (а не свободный текст).
LIST_ITEM_RE = re.compile(r'^\s*(?:[•\-–—*✅📍]|\d{1,2}[.)](?!\d)|этап\b)', re.IGNORECASE)

# Абзац без явного маркера считается примечанием, только если это связный
# текст: есть строка не короче стольких символов (иначе это подпункт этапа).
NOTE_MIN_FREE_TEXT_LEN = 100


def split_note(text):
    """Отделить примечание к проекту от тела блока.

    Примечанием считается последний абзац блока, если он либо помечен явно
    («ℹ️», «Примечание:», «Дополнительно:» …), либо не содержит ни одного
    пункта списка/этапа и перед ним в блоке есть хотя бы один абзац.

    Возвращает кортеж (тело_без_примечания, примечание | None).
    """
    if not text:
        return text, None

    paragraphs = [p for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]
    if not paragraphs:
        return text, None

    last = paragraphs[-1].strip()
    explicit  = bool(NOTE_MARKER_RE.match(last))
    lines_last = [ln for ln in last.split('\n') if ln.strip()]
    free_text = (
        len(paragraphs) > 1
        and not any(LIST_ITEM_RE.match(ln) for ln in lines_last)
        and max((len(ln.strip()) for ln in lines_last), default=0) >= NOTE_MIN_FREE_TEXT_LEN
    )
    if not (explicit or free_text):
        return text, None

    note = NOTE_MARKER_RE.sub('', last).strip()
    if not note:                      # маркер без текста — оставляем блок как есть
        return text, None
    body = '\n\n'.join(paragraphs[:-1]).strip()
    return (body or None), note


def parse_report(filepath):
    """
    Parse the MD weekly report file.

    Returns a list of groups::

        [
            {
                'name':     str,   # e.g. 'ПРОЕКТЫ ЗИТ'
                'emoji':    str,   # '🔵' or '🔴'
                'projects': [
                    {
                        'name':      str,
                        'person':    str or None,
                        'url':       str or None,
                        'issue_id':  int or None,
                        'completed': str or None,  # ✅ section text
                        'current':   str or None,  # 📍 section text
                        'priority':  bool,         # True if 🔴
                    },
                    ...
                ],
            },
            ...
        ]
    """
    with open(filepath, encoding='utf-8') as f:
        lines = f.read().split('\n')

    n = len(lines)

    # Mutable state (manipulated via nested helpers)
    state = {'value': 'idle'}  # idle | header | completed | current

    current_group = {
        'name':     DEFAULT_FIRST_GROUP_NAME,
        'emoji':    DEFAULT_FIRST_GROUP_EMOJI,
        'projects': [],
    }
    groups = [current_group]
    proj   = [None]  # use list so nested helpers can rebind

    def flush_project():
        p = proj[0]
        if p is not None:
            completed = '\n'.join(p.pop('_completed')).strip()
            current   = '\n'.join(p.pop('_current')).strip()
            # Свободный абзац в конце блока — это примечание к проекту,
            # а не очередной этап: выносим его отдельно.
            current,   note_cur  = split_note(current)
            completed, note_done = split_note(completed)
            p['completed'] = completed or None
            p['current']   = current   or None
            p['note']      = '\n\n'.join(x for x in (note_done, note_cur) if x) or None
            current_group['projects'].append(p)
            proj[0] = None

    def start_group(name, emoji):
        flush_project()
        nonlocal current_group
        # Don't add empty groups
        if not current_group['projects'] and groups and groups[-1] is current_group:
            # Replace placeholder first group if it has no projects yet
            current_group['name']  = name
            current_group['emoji'] = emoji
        else:
            new_group = {'name': name, 'emoji': emoji, 'projects': []}
            groups.append(new_group)
            current_group = new_group
        state['value'] = 'idle'

    i = 0
    while i < n:
        raw_line = lines[i]
        line     = raw_line.strip()

        # Skip pure divider lines (▬, ━, ─, -, =)
        if line and re.match(r'^[▬━─\-=]{3,}$', line):
            i += 1
            continue

        # -------------------------------------------------------------------
        # Detect lines starting with 🔵 or 🔴
        # -------------------------------------------------------------------
        emoji_m = re.match(r'^(?:\d+\.\s*)?([🔵🔴])\s*(.*)', line)
        if emoji_m:
            emoji = emoji_m.group(1)
            rest  = emoji_m.group(2).strip()

            # Look ahead up to 8 lines for a 🔗 URL to distinguish project
            # from section header
            has_url = False
            for j in range(i + 1, min(i + 9, n)):
                s = lines[j].strip()
                if re.match(r'^🔗', s):
                    has_url = True
                    break
                # Stop if we hit another emoji header or divider
                if re.match(r'^[🔵🔴▬━]', s):
                    break

            if not has_url:
                # Section header — start a new group
                start_group(rest, emoji)
                i += 1
                continue

            # New project entry
            flush_project()
            proj[0] = {
                'name':       rest,
                'person':     None,
                'url':        None,
                'issue_id':   None,
                '_completed': [],
                '_current':   [],
                'priority':   emoji == '🔴',
            }
            state['value'] = 'header'
            i += 1
            continue

        # -------------------------------------------------------------------
        # 👤 person line
        # -------------------------------------------------------------------
        if line.startswith('👤') and proj[0] is not None and state['value'] in ('header', 'idle'):
            proj[0]['person'] = re.sub(r'^👤\s*', '', line).strip()
            i += 1
            continue

        # -------------------------------------------------------------------
        # 🔗 URL line
        # -------------------------------------------------------------------
        if line.startswith('🔗') and proj[0] is not None:
            url_text = re.sub(r'^🔗\s*', '', line).strip()
            proj[0]['url']      = url_text
            proj[0]['issue_id'] = extract_id_from_url(url_text)
            state['value'] = 'header'
            i += 1
            continue

        # -------------------------------------------------------------------
        # ✅ Выполнено: section header
        # -------------------------------------------------------------------
        if re.match(r'^✅\s*Выполнено', line) and proj[0] is not None:
            state['value'] = 'completed'
            after = re.sub(r'^✅\s*Выполнено\s*:?\s*', '', line).strip()
            if after:
                proj[0]['_completed'].append(after)
            i += 1
            continue

        # -------------------------------------------------------------------
        # 📍 section header (Текущие этапы / В работе)
        # -------------------------------------------------------------------
        if re.match(r'^📍', line) and proj[0] is not None:
            state['value'] = 'current'
            after = re.sub(r'^📍\s*(?:(?:Текущие\s*этапы|В работе)[^:]*:?)?\s*', '', line).strip()
            if after:
                proj[0]['_current'].append(after)
            i += 1
            continue

        # -------------------------------------------------------------------
        # Content accumulation
        # -------------------------------------------------------------------
        if proj[0] is not None:
            if state['value'] == 'completed':
                proj[0]['_completed'].append(raw_line.rstrip())
            elif state['value'] == 'current':
                proj[0]['_current'].append(raw_line.rstrip())
            # else: header / idle — ignore (intro text, empty lines, etc.)

        i += 1

    # Flush whatever is remaining
    flush_project()

    # Remove groups with no projects
    return [g for g in groups if g['projects']]


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

def strip_dates(s):
    """Remove date patterns like (01.04) or (01.04.2026) from string."""
    return re.sub(r'\(\d{1,2}\.\d{1,2}(?:\.\d{4})?\)', '', s).strip()


def normalize_line(s):
    """Normalize a line for comparison: strip bullet markers, lowercase.

    Маркер примечания («Доп. информация:» …) тоже убирается: один и тот же
    текст на прошлой неделе мог лежать в теле блока вместе с маркером,
    а на этой — быть отделён в примечание уже без него.
    """
    s = strip_dates(s)
    s = re.sub(r'^[\s]*(?:[•\-\*]|\d+\.)\s*', '', s)
    s = NOTE_MARKER_RE.sub('', s)
    return s.lower().strip()


def _text_to_norm_set(text):
    if not text:
        return set()
    result = set()
    for line in text.split('\n'):
        norm = normalize_line(line)
        if norm:
            result.add(norm)
    return result


def compute_new_lines(current_text, prev_completed, prev_current):
    """
    Return a set of normalized lines from current_text that don't appear
    in either prev_completed or prev_current (after normalization + date stripping).
    """
    prev_all = _text_to_norm_set(prev_completed) | _text_to_norm_set(prev_current)
    new_lines = set()
    if current_text:
        for line in current_text.split('\n'):
            norm = normalize_line(line)
            if norm and norm not in prev_all:
                new_lines.add(norm)
    return new_lines


def find_prev_project(proj, prev_index):
    """
    Find the previous version of a project in prev_index.
    Matches by issue_id first, then fuzzy name.
    Returns prev_proj dict or None.
    """
    issue_id = proj.get('issue_id')
    if issue_id is not None and issue_id in prev_index['by_id']:
        return prev_index['by_id'][issue_id]

    name_lower = proj['name'].lower()
    best_ratio = 0.0
    best_proj  = None
    for pname, pp in prev_index['by_name']:
        ratio = SequenceMatcher(None, name_lower, pname).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_proj  = pp
    if best_ratio >= FUZZY_MATCH_THRESHOLD:
        return best_proj
    return None


def build_prev_index(prev_groups):
    """Build lookup structure from parsed previous report groups."""
    by_id   = {}
    by_name = []
    for g in prev_groups:
        for p in g['projects']:
            if p.get('issue_id') is not None:
                by_id[p['issue_id']] = p
            by_name.append((p['name'].lower(), p))
    return {'by_id': by_id, 'by_name': by_name}


def _with_note(block_text, note):
    """Тело блока вместе с примечанием — для сравнения с прошлой неделей:
    абзац мог быть примечанием тогда и частью блока сейчас (и наоборот)."""
    return '\n\n'.join(x for x in (block_text, note) if x) or None


def render_block_with_diff(block_text, new_lines_set):
    """
    Return list of lines from block_text, with new lines prefixed by '🆕 '.
    A line is "new" if normalize_line(line) is in new_lines_set.
    """
    if not block_text:
        return []
    result = []
    for line in block_text.split('\n'):
        norm = normalize_line(line)
        if norm and norm in new_lines_set:
            result.append(f'🆕 {line}')
        else:
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# Matching report projects to data.json
# ---------------------------------------------------------------------------

def in_completed_section(proj, completed_projects):
    """Проект из MD-отчёта, попавший в секцию «Реализовано» (и потому не
    должен дублироваться в списке «в работе»)."""
    dp = proj.get('_data_project')
    return dp is not None and any(dp is c for c in completed_projects)


def find_in_data(issue_id, name, data_projects):
    """
    Find a project in data_projects by ID (primary) or fuzzy name (fallback).

    Returns (project_dict, match_type) where match_type is 'id', 'name', or None.
    """
    if issue_id is not None:
        for p in data_projects:
            if p.get('id') == issue_id:
                return p, 'id'

    best_ratio   = 0.0
    best_project = None
    name_lower   = name.lower()
    for p in data_projects:
        ratio = SequenceMatcher(None, name_lower, p['name'].lower()).ratio()
        if ratio > best_ratio:
            best_ratio   = ratio
            best_project = p

    if best_ratio >= FUZZY_MATCH_THRESHOLD:
        return best_project, 'name'

    return None, None


# ---------------------------------------------------------------------------
# current_status builder
# ---------------------------------------------------------------------------

def build_current_status(completed, current, note=None):
    """Compose the current_status string from parsed sections."""
    parts = []
    if completed:
        parts.append('✅ Выполнено:\n' + completed)
    if current:
        parts.append('📍 В работе:\n' + current)
    if note:
        parts.append('ℹ️ Дополнительно:\n' + note)
    return '\n\n'.join(parts) if parts else None


# ---------------------------------------------------------------------------
# Telegram message builder
# ---------------------------------------------------------------------------

def _deadline_sort_key(proj):
    """Return a sortable date from a project's deadline string (DD.MM.YYYY)."""
    dl = proj.get('deadline') or ''
    try:
        d, m, y = dl.split('.')
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return date.max  # no deadline → sort last


# ---------------------------------------------------------------------------
# Completed (closed) projects
# ---------------------------------------------------------------------------

def _parse_ddmmyyyy(s):
    """'DD.MM.YYYY' → date, иначе None."""
    try:
        d, m, y = str(s).split('.')
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


def completed_date(dp):
    """Дата реализации проекта: «Закрыта», иначе «Дата защиты»."""
    return _parse_ddmmyyyy(dp.get('closed_at')) or _parse_ddmmyyyy(dp.get('defense_at'))


def collect_completed(data_projects, priority, year=YEAR):
    """Реализованные (закрытые) проекты выбранной группы за год `year`,
    свежие первыми. Проекты прошлых лет в отчёт не попадают."""
    result = []
    for dp in data_projects:
        if dp.get('status') not in CLOSED_STATUSES:
            continue
        if bool(dp.get('is_priority')) != bool(priority):
            continue
        cd = completed_date(dp)
        if cd is None or cd.year != year:
            continue
        result.append(dp)
    result.sort(key=lambda dp: completed_date(dp), reverse=True)
    return result


def project_url(dp):
    """Ссылка на проект в Redmine: поле url, иначе собирается из id."""
    url = dp.get('url')
    if url:
        return url
    pid = dp.get('id')
    return f'{REDMINE_BASE}/{pid}' if pid else None


def _portfolio_line(completed, in_work_count):
    """Строка-счётчик портфеля для шапки сообщения."""
    total = len(completed) + in_work_count
    return (f'📈 Портфель: {total} · '
            f'✅ реализовано {len(completed)} · '
            f'🔄 в работе {in_work_count}')


def _render_completed(out, projects, year=YEAR):
    """Секция «Реализовано»: проекты, закрытые в текущем году."""
    if not projects:
        return

    out.append(TELEGRAM_SEPARATOR_THICK)
    out.append(f'✅ РЕАЛИЗОВАНО В {year} ({len(projects)})')
    out.append(TELEGRAM_SEPARATOR_THICK)
    out.append('')

    for idx, dp in enumerate(projects):
        cd = completed_date(dp)
        cd_str = cd.strftime('%d.%m.%Y') if cd else '—'
        owner = dp.get('owner_short') or '—'
        out.append(f'{idx + 1}. {dp["name"]} — {cd_str} · {owner}')
        url = project_url(dp)
        if url:
            out.append(f'🔗 {url}')
        out.append('')


def _render_group(out, emoji, title, projects, prev_index=None):
    """Append one group section (header + numbered projects) to out."""
    count = len(projects)
    sorted_projs = sorted(projects, key=_deadline_sort_key)

    out.append(TELEGRAM_SEPARATOR_THICK)
    out.append(f'{emoji} {title} ({count})')
    out.append(TELEGRAM_SEPARATOR_THICK)
    out.append('')

    for idx, proj in enumerate(sorted_projs):
        proj_emoji = '🔴' if proj.get('is_priority') else '🔵'

        # Diff: detect new projects and new lines within blocks
        prev_proj = find_prev_project(proj, prev_index) if prev_index else None
        is_new_project = prev_index is not None and prev_proj is None

        name_suffix = ' 🆕 новый проект' if is_new_project else ''
        out.append(f'{idx + 1}. {proj_emoji} {proj["name"]}{name_suffix}')

        dp = proj.get('_data_project') or {}
        manager = dp.get('owner_short') or proj.get('person')
        if manager:
            out.append(f'👤 {manager}')

        url = proj.get('url') or dp.get('url')
        if url:
            out.append(f'🔗 {url}')

        internal = dp.get('internal_hours')
        external = dp.get('external_hours')
        lines_vysv = []
        if internal:
            i_units = round(internal / HOURS_PER_UNIT, 2)
            lines_vysv.append(f'   Внутреннее: {int(round(internal))} ч / {i_units} шт.ед.')
        if external:
            e_units = round(external / HOURS_PER_UNIT, 2)
            lines_vysv.append(f'   Внешнее:    {int(round(external))} ч / {e_units} шт.ед.')
        if lines_vysv:
            out.append('📉 Высвобождение:')
            out.extend(lines_vysv)

        out.append('')

        if proj.get('completed'):
            out.append('✅ Выполнено:')
            if prev_proj is not None:
                new_completed = compute_new_lines(
                    proj.get('completed'),
                    _with_note(prev_proj.get('completed'), prev_proj.get('note')),
                    prev_proj.get('current'),
                )
                out.extend(render_block_with_diff(proj['completed'], new_completed))
            else:
                out.append(proj['completed'])
            out.append('')

        if proj.get('current'):
            out.append('📍 В работе:')
            if prev_proj is not None:
                new_current = compute_new_lines(
                    proj.get('current'),
                    None,
                    _with_note(prev_proj.get('current'), prev_proj.get('note')),
                )
                out.extend(render_block_with_diff(proj['current'], new_current))
            else:
                out.append(proj['current'])
            out.append('')

        if proj.get('note'):
            # Примечание новое, только если его строк не было в прошлом отчёте
            # ни в примечании, ни в теле блоков (абзац мог «переехать» между ними).
            note_changed = bool(
                compute_new_lines(
                    proj['note'],
                    _with_note(prev_proj.get('completed'), prev_proj.get('note')),
                    prev_proj.get('current'),
                )
            ) if prev_proj is not None else False
            out.append(('🆕 ' if note_changed else '') + 'ℹ️ Дополнительно:')
            out.append(proj['note'])
            out.append('')

        if idx < count - 1:
            out.append(TELEGRAM_SEPARATOR_THIN)
            out.append('')


def _render_not_reported(out, names):
    """Append the 'no status provided' section to out."""
    out.append(TELEGRAM_SEPARATOR_THICK)
    out.append('⚠️ ИНФОРМАЦИЯ НЕ ПРЕДСТАВЛЕНА')
    out.append(TELEGRAM_SEPARATOR_THICK)
    out.append('')
    out.append('По следующим проектам статус на эту неделю не предоставлен:')
    out.append('')
    for name in names:
        out.append(f'• {name}')
    out.append('')
    out.append(TELEGRAM_SEPARATOR_THICK)


def build_priority_message(priority_projs, not_reported, report_date,
                           prev_index=None, prev_date=None,
                           completed_projs=None, in_work_count=None):
    """Telegram message for priority projects only."""
    out = []
    completed_projs = completed_projs or []
    date_str = report_date.strftime('%d.%m.%Y')
    out.append('📊 Еженедельный отчёт — Приоритетные проекты')
    out.append(f'Дата: {date_str}')
    if prev_date is not None:
        out.append(f'🔄 Сравнение с отчётом от {prev_date.strftime("%d.%m.%Y")}')
    if in_work_count is not None:
        out.append(_portfolio_line(completed_projs, in_work_count))
    out.append('')
    if completed_projs:
        _render_completed(out, completed_projs)
    _render_group(out, '🔴', 'ПРИОРИТЕТНЫЕ ПРОЕКТЫ', priority_projs, prev_index)
    if not_reported:
        out.append('')
        _render_not_reported(out, not_reported)
    return '\n'.join(out)


def build_transform_message(transform_projs, not_reported, report_date,
                            prev_index=None, prev_date=None,
                            completed_projs=None, in_work_count=None):
    """Telegram message for transformation projects only."""
    out = []
    completed_projs = completed_projs or []
    date_str = report_date.strftime('%d.%m.%Y')
    out.append('📊 Еженедельный отчёт — Трансформационные проекты')
    out.append(f'Дата: {date_str}')
    if prev_date is not None:
        out.append(f'🔄 Сравнение с отчётом от {prev_date.strftime("%d.%m.%Y")}')
    if in_work_count is not None:
        out.append(_portfolio_line(completed_projs, in_work_count))
    out.append('')
    if completed_projs:
        _render_completed(out, completed_projs)
    _render_group(out, '🔵', 'ТРАНСФОРМАЦИОННЫЕ ПРОЕКТЫ', transform_projs, prev_index)
    if not_reported:
        out.append('')
        _render_not_reported(out, not_reported)
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Обработка еженедельного MD-отчёта по проектам трансформации'
    )
    parser.add_argument('report', help='Путь к .md-файлу отчёта')
    parser.add_argument('--data', default='data.json',
                        help='Путь к data.json (по умолчанию data.json)')
    parser.add_argument('--telegram-only', action='store_true',
                        help='Только сформировать Telegram-сообщение, не изменять data.json')
    parser.add_argument('--no-telegram', action='store_true',
                        help='Только обновить data.json, не формировать Telegram-сообщение')
    parser.add_argument('--prev', default=None, metavar='PREV_REPORT',
                        help='Предыдущий .md-файл отчёта для сравнения (diff)')
    args = parser.parse_args()

    update_data     = not args.telegram_only
    make_telegram   = not args.no_telegram

    # ------------------------------------------------------------------
    # Validate inputs
    # ------------------------------------------------------------------
    if not os.path.exists(args.report):
        print(f'❌ Ошибка: файл отчёта не найден: {args.report}', file=sys.stderr)
        sys.exit(1)

    if update_data and not os.path.exists(args.data):
        print(f'❌ Ошибка: файл {args.data} не найден', file=sys.stderr)
        sys.exit(1)

    if args.prev and not os.path.exists(args.prev):
        print(f'❌ Ошибка: предыдущий отчёт не найден: {args.prev}', file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # Parse report
    # ------------------------------------------------------------------
    report_date = parse_date_from_filename(args.report)

    print(f'📂 Читаем отчёт: {args.report}')
    groups = parse_report(args.report)
    all_report_projects = [p for g in groups for p in g['projects']]
    print(f'   Найдено проектов в отчёте: {len(all_report_projects)}')
    print()

    # ------------------------------------------------------------------
    # Parse previous report for diff (optional)
    # ------------------------------------------------------------------
    prev_index = None
    prev_date  = None

    if args.prev:
        print(f'📂 Читаем предыдущий отчёт: {args.prev}')
        prev_groups = parse_report(args.prev)
        prev_index  = build_prev_index(prev_groups)
        prev_date   = parse_date_from_filename(args.prev)
        prev_count  = sum(len(g['projects']) for g in prev_groups)
        print(f'   Проектов в предыдущем отчёте: {prev_count}')
        print()

    # ------------------------------------------------------------------
    # Load data.json (always, if available — needed for matching/deadlines)
    # ------------------------------------------------------------------
    data          = None
    data_projects = []

    if os.path.exists(args.data):
        with open(args.data, encoding='utf-8') as f:
            data = json.load(f)
        data_projects = data.get('projects', [])

    # ------------------------------------------------------------------
    # Match report projects → data.json
    # ------------------------------------------------------------------
    not_found_in_data = []
    matched_dp_object_ids = set()

    if data_projects:
        print('🔗 Сопоставление с data.json:')
        for proj in all_report_projects:
            dp, match_type = find_in_data(
                proj.get('issue_id'), proj['name'], data_projects
            )
            proj['_data_project'] = dp
            proj['_match_type']   = match_type

            if dp is not None:
                matched_dp_object_ids.add(id(dp))
                proj['deadline']    = dp.get('deadline')
                proj['is_priority'] = dp.get('is_priority', False)
                if match_type == 'id':
                    print(f'   ✓ {proj["name"]:<42} — найден по ID #{proj["issue_id"]}')
                else:
                    print(f'   ~ {proj["name"]:<42} — найден по имени (нечёткое совпадение)')
            else:
                not_found_in_data.append(proj)
                print(f'   ✗ "{proj["name"]}" — НЕ НАЙДЕН в data.json')
        print()

    # ------------------------------------------------------------------
    # Build lists of active projects absent from the report (split by priority)
    # ------------------------------------------------------------------
    not_reported_priority  = []
    not_reported_transform = []
    for dp in data_projects:
        if dp.get('status') not in CLOSED_STATUSES and id(dp) not in matched_dp_object_ids:
            if dp.get('is_priority'):
                not_reported_priority.append(dp['name'])
            else:
                not_reported_transform.append(dp['name'])
    not_reported = not_reported_priority + not_reported_transform

    # ------------------------------------------------------------------
    # Update data.json
    # ------------------------------------------------------------------
    updated_count = 0

    if update_data and data is not None:
        print('📊 Обновление data.json:')

        for proj in all_report_projects:
            dp = proj.get('_data_project')
            if dp is not None:
                status = build_current_status(
                    proj.get('completed'), proj.get('current'), proj.get('note')
                )
                if status:
                    dp['current_status'] = status
                    updated_count += 1

        data.setdefault('summary', {})['report_updated_at'] = report_date.strftime('%d.%m.%Y')

        # Back up then overwrite
        shutil.copy2(args.data, args.data + '.bak')
        with open(args.data, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f'   Обновлено полей current_status: {updated_count}')
        print(f'   Не найдено в data.json:         {len(not_found_in_data)}')
        print(f'   Не было в отчёте (активных):   {len(not_reported)}')
        print()

    # ------------------------------------------------------------------
    # Generate Telegram messages (two files)
    # ------------------------------------------------------------------
    if make_telegram:
        date_suffix = report_date.strftime('%d_%m_%Y')

        # Реализованные (закрытые) проекты и число активных — из data.json
        completed_priority  = collect_completed(data_projects, priority=True)
        completed_transform = collect_completed(data_projects, priority=False)

        # Проект, закрытый на отчётной неделе, ещё присутствует в MD-отчёте.
        # Убираем из списка «в работе» только те, что реально попали в секцию
        # «Реализовано», — иначе закрытый проект прошлого года (или без даты
        # закрытия) исчез бы из сообщения совсем.
        completed_all    = completed_priority + completed_transform
        closed_in_report = [
            p for p in all_report_projects if in_completed_section(p, completed_all)
        ]
        active_report_projects = [
            p for p in all_report_projects if not in_completed_section(p, completed_all)
        ]

        priority_projs   = [p for p in active_report_projects if p.get('is_priority')]
        transform_projs  = [p for p in active_report_projects if not p.get('is_priority')]

        # Портфель показываем только когда есть data.json (иначе счётчики не с чем сверить)
        in_work_priority = in_work_transform = None
        if data_projects:
            in_work_priority = sum(
                1 for dp in data_projects
                if dp.get('status') not in CLOSED_STATUSES and dp.get('is_priority')
            )
            in_work_transform = sum(
                1 for dp in data_projects
                if dp.get('status') not in CLOSED_STATUSES and not dp.get('is_priority')
            )

        if closed_in_report:
            print('✅ Реализованы — перенесены из блока «в работе» в секцию «Реализовано»:')
            for p in closed_in_report:
                print(f'   • {p["name"]}')
            print()

        # Закрытые проекты без даты закрытия/защиты не попадут никуда — предупреждаем
        undated_closed = [
            dp for dp in data_projects
            if dp.get('status') in CLOSED_STATUSES and completed_date(dp) is None
        ]
        if undated_closed:
            print('⚠️ Закрытые проекты без даты закрытия и защиты '
                  '(не попадут в секцию «Реализовано»):')
            for dp in undated_closed:
                print(f'   • {dp["name"]}')
            print()

        # File 1 — priority projects
        fn_priority  = f'telegram_priority_{date_suffix}.txt'
        msg_priority = build_priority_message(
            priority_projs, not_reported_priority, report_date,
            prev_index=prev_index, prev_date=prev_date,
            completed_projs=completed_priority, in_work_count=in_work_priority,
        )
        with open(fn_priority, 'w', encoding='utf-8') as f:
            f.write(msg_priority)
        print(f'📩 Приоритетные проекты:     {fn_priority}')
        print(f'   Символов: {len(msg_priority)} | Проектов: {len(priority_projs)}'
              + (f' | ⚠️ без статуса: {len(not_reported_priority)}' if not_reported_priority else ''))

        # File 2 — transformation projects
        fn_transform  = f'telegram_transform_{date_suffix}.txt'
        msg_transform = build_transform_message(
            transform_projs, not_reported_transform, report_date,
            prev_index=prev_index, prev_date=prev_date,
            completed_projs=completed_transform, in_work_count=in_work_transform,
        )
        with open(fn_transform, 'w', encoding='utf-8') as f:
            f.write(msg_transform)
        print(f'📩 Трансформационные проекты: {fn_transform}')
        print(f'   Символов: {len(msg_transform)} | Проектов: {len(transform_projs)}'
              + (f' | ⚠️ без статуса: {len(not_reported_transform)}' if not_reported_transform else ''))
        print()

    print('✅ Готово!')


if __name__ == '__main__':
    main()
