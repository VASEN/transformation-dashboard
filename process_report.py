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
            p['completed'] = completed or None
            p['current']   = current   or None
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
    """Normalize a line for comparison: strip bullet markers, lowercase."""
    s = strip_dates(s)
    s = re.sub(r'^[\s]*(?:[•\-\*]|\d+\.)\s*', '', s)
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

def build_current_status(completed, current):
    """Compose the current_status string from parsed sections."""
    parts = []
    if completed:
        parts.append('✅ Выполнено:\n' + completed)
    if current:
        parts.append('📍 В работе:\n' + current)
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

        HOURS_PER_UNIT = 1972
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
                    prev_proj.get('completed'),
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
                    prev_proj.get('current'),
                )
                out.extend(render_block_with_diff(proj['current'], new_current))
            else:
                out.append(proj['current'])
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
                           prev_index=None, prev_date=None):
    """Telegram message for priority projects only."""
    out = []
    date_str = report_date.strftime('%d.%m.%Y')
    out.append('📊 Еженедельный отчёт — Приоритетные проекты')
    out.append(f'Дата: {date_str}')
    if prev_date is not None:
        out.append(f'🔄 Сравнение с отчётом от {prev_date.strftime("%d.%m.%Y")}')
    out.append('')
    _render_group(out, '🔴', 'ПРИОРИТЕТНЫЕ ПРОЕКТЫ', priority_projs, prev_index)
    if not_reported:
        out.append('')
        _render_not_reported(out, not_reported)
    return '\n'.join(out)


def build_transform_message(transform_projs, not_reported, report_date,
                            prev_index=None, prev_date=None):
    """Telegram message for transformation projects only."""
    out = []
    date_str = report_date.strftime('%d.%m.%Y')
    out.append('📊 Еженедельный отчёт — Трансформационные проекты')
    out.append(f'Дата: {date_str}')
    if prev_date is not None:
        out.append(f'🔄 Сравнение с отчётом от {prev_date.strftime("%d.%m.%Y")}')
    out.append('')
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
                status = build_current_status(proj.get('completed'), proj.get('current'))
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

        priority_projs   = [p for p in all_report_projects if p.get('is_priority')]
        transform_projs  = [p for p in all_report_projects if not p.get('is_priority')]

        # File 1 — priority projects
        fn_priority  = f'telegram_priority_{date_suffix}.txt'
        msg_priority = build_priority_message(
            priority_projs, not_reported_priority, report_date,
            prev_index=prev_index, prev_date=prev_date,
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
