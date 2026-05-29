#!/usr/bin/env python3
"""
overdue_report.py — Отчёт по просроченным и сегодняшним задачам.

Использование:
    python3 overdue_report.py
    python3 overdue_report.py --data data.json
    python3 overdue_report.py --output overdue_tasks_28_05_2026.txt

Источник: `data.json` (после extract_data.py). Берутся задачи с дедлайном
≤ сегодня и статусом не из CLOSED_STATUSES, группируются по проекту.
У проекта указывается ответственный (owner_short), у задачи —
исполнитель (executor_short). Внутри проекта задачи разделены на
просроченные и со сроком сегодня.
"""

import json
import argparse
from datetime import datetime, date

CLOSED_STATUSES = {'Закрыта', 'Закрыто', 'Выполнено', 'Выполнена', 'Завершена'}

SEPARATOR_THICK = '━━━━━━━━━━━━━━━━'
SEPARATOR_THIN  = '─────────────────'

REDMINE_BASE = 'https://transformation.rm.mosreg.ru/#/issues'


def parse_deadline(s):
    try:
        return datetime.strptime(s, '%d.%m.%Y').date()
    except (ValueError, TypeError):
        return None


def collect_overdue(data, today):
    """Group overdue + today's tasks by project. Returns list of dicts."""
    proj_by_name = {p['name']: p for p in data.get('projects', [])}
    groups = {}

    for t in data.get('all_tasks', []):
        if t.get('status') in CLOSED_STATUSES:
            continue
        dl = parse_deadline(t.get('deadline'))
        if not dl or dl > today:
            continue

        pname = t.get('project') or '(без проекта)'
        group = groups.setdefault(pname, {
            'name':    pname,
            'project': proj_by_name.get(pname),
            'tasks':   [],
        })
        group['tasks'].append({
            'id':            t.get('id'),
            'theme':         t.get('theme') or '(без темы)',
            'status':        t.get('status') or '',
            'executor':      t.get('executor_short') or t.get('executor') or '—',
            'deadline':      t.get('deadline'),
            'days_overdue':  (today - dl).days,
        })

    result = list(groups.values())
    for g in result:
        g['tasks'].sort(key=lambda x: -x['days_overdue'])
        g['max_overdue']   = max((t['days_overdue'] for t in g['tasks']), default=0)
        g['total_overdue'] = sum(1 for t in g['tasks'] if t['days_overdue'] > 0)
        g['total_today']   = sum(1 for t in g['tasks'] if t['days_overdue'] == 0)
        g['total']         = len(g['tasks'])
    result.sort(key=lambda g: (-g['max_overdue'], -g['total'], g['name']))
    return result


def plural_days(n):
    if 11 <= n % 100 <= 14:
        return f'{n} дн.'
    last = n % 10
    if last == 1:           return f'{n} день'
    if 2 <= last <= 4:      return f'{n} дня'
    return f'{n} дн.'


def plural_tasks(n):
    if 11 <= n % 100 <= 14:
        return f'{n} задач'
    last = n % 10
    if last == 1:           return f'{n} задача'
    if 2 <= last <= 4:      return f'{n} задачи'
    return f'{n} задач'


def plural_projects(n):
    if 11 <= n % 100 <= 14:
        return f'{n} проектах'
    last = n % 10
    if last == 1:           return f'{n} проекте'
    return f'{n} проектах'


def _render_task(t, today_task):
    """Build lines for a single task entry."""
    lines = [f'   • {t["theme"]}', f'     👤 {t["executor"]}']
    if today_task:
        lines.append(f'     📅 Дедлайн: {t["deadline"]} (сегодня)')
    else:
        lines.append(f'     📅 Дедлайн: {t["deadline"]} '
                     f'(просрочено на {plural_days(t["days_overdue"])})')
    if t['status']:
        lines.append(f'     📌 Статус: {t["status"]}')
    if t.get('id'):
        lines.append(f'     🔗 {REDMINE_BASE}/{t["id"]}')
    lines.append('')
    return lines


def build_message(groups, today):
    out = []
    total_overdue = sum(g['total_overdue'] for g in groups)
    total_today   = sum(g['total_today']   for g in groups)
    out.append('📊 Отчёт по просроченным и сегодняшним задачам')
    out.append(f'Дата: {today.strftime("%d.%m.%Y")}')
    if not groups:
        out.append('')
        out.append('✅ Просроченных и сегодняшних задач нет.')
        return '\n'.join(out)

    summary_parts = []
    if total_overdue:
        summary_parts.append(f'просрочено {plural_tasks(total_overdue)}')
    if total_today:
        summary_parts.append(f'со сроком сегодня {plural_tasks(total_today)}')
    out.append(f'Всего: {", ".join(summary_parts)} в '
               f'{plural_projects(len(groups))}')
    out.append('')
    out.append(SEPARATOR_THICK)
    out.append('')

    for idx, g in enumerate(groups, start=1):
        proj  = g['project'] or {}
        emoji = '🔴' if proj.get('is_priority') else '🔵'
        owner = proj.get('owner_short') or '—'
        url   = proj.get('url')

        out.append(f'{idx}. {emoji} {g["name"]}')
        out.append(f'👤 Ответственный: {owner}')
        if url:
            out.append(f'🔗 {url}')
        out.append('')

        overdue_tasks = [t for t in g['tasks'] if t['days_overdue'] > 0]
        today_tasks   = [t for t in g['tasks'] if t['days_overdue'] == 0]

        if overdue_tasks:
            out.append(f'⏰ Просроченные задачи ({len(overdue_tasks)}):')
            for t in overdue_tasks:
                out.extend(_render_task(t, today_task=False))

        if today_tasks:
            out.append(f'📅 Срок сегодня ({len(today_tasks)}):')
            for t in today_tasks:
                out.extend(_render_task(t, today_task=True))

        if idx < len(groups):
            out.append(SEPARATOR_THIN)
            out.append('')

    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description='Отчёт по просроченным задачам.')
    ap.add_argument('--data',   default='data.json', help='Путь к data.json')
    ap.add_argument('--output', default=None,        help='Имя выходного файла')
    args = ap.parse_args()

    with open(args.data, encoding='utf-8') as f:
        data = json.load(f)

    today = date.today()
    groups = collect_overdue(data, today)
    message = build_message(groups, today)

    out_path = args.output or f'overdue_tasks_{today.strftime("%d_%m_%Y")}.txt'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(message)

    total_overdue = sum(g['total_overdue'] for g in groups)
    total_today   = sum(g['total_today']   for g in groups)
    print(f'✅ Отчёт сохранён: {out_path}')
    print(f'   Просроченных: {plural_tasks(total_overdue)}, '
          f'со сроком сегодня: {plural_tasks(total_today)} '
          f'в {plural_projects(len(groups))}')


if __name__ == '__main__':
    main()
