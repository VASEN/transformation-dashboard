#!/usr/bin/env python3
"""
upcoming_report.py — Справка по задачам с приближающимся сроком.

Отвечает на вопрос «что уйдёт в просрочку, если не закрыть вовремя»:
берёт из `data.json` активные задачи, срок которых попадает в окно
[--from .. --to] включительно, и печатает их по проектам — в текстовом
формате (как `overdue_tasks_*.txt`) и/или в markdown (как СПРАВКА_*.md).

Использование:
    python3 upcoming_report.py                          # сегодня .. +7 дней, txt + md
    python3 upcoming_report.py --to 17.08.2026          # сегодня .. 17.08.2026
    python3 upcoming_report.py --days 4                 # сегодня .. +4 дня
    python3 upcoming_report.py --from 18.08.2026 --to 24.08.2026
    python3 upcoming_report.py --format md              # только markdown
    python3 upcoming_report.py --include-overdue        # добавить ранее просроченные
    python3 upcoming_report.py --outdir /tmp --stdout   # куда писать / вывести в консоль
"""

import os
import glob
import json
import argparse
from datetime import date, datetime, timedelta

from config import CLOSED_STATUSES, REDMINE_BASE
from overdue_report import (
    parse_deadline, plural_days, plural_tasks, plural_projects,
    SEPARATOR_THICK, SEPARATOR_THIN,
)

WEEKDAYS = ['понедельник', 'вторник', 'среда', 'четверг',
            'пятница', 'суббота', 'воскресенье']
# винительный падеж: «переносится на пятницу 14.08»
WEEKDAYS_ACC = ['понедельник', 'вторник', 'среду', 'четверг',
                'пятницу', 'субботу', 'воскресенье']

DEFAULT_DAYS = 7


# ─────────────────────────── разбор окна дат ───────────────────────────

def parse_date_arg(s):
    """`ДД.ММ.ГГГГ` или `ГГГГ-ММ-ДД` → date. Ошибка формата → ValueError."""
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f'не распознана дата: {s!r} (ожидается ДД.ММ.ГГГГ)')


def resolve_window(start=None, end=None, days=None, today=None):
    """Границы окна из аргументов CLI. Возвращает (start, end)."""
    today = today or date.today()
    start = start or today
    if end is None:
        end = start + timedelta(days=DEFAULT_DAYS if days is None else days)
    if end < start:
        raise ValueError(f'конец окна ({end:%d.%m.%Y}) раньше начала ({start:%d.%m.%Y})')
    return start, end


def window_slug(start, end):
    """Имя файла без расширения: СПРАВКА_сроки_13-17.08.2026."""
    if (start.year, start.month) == (end.year, end.month):
        return f'СПРАВКА_сроки_{start:%d}-{end:%d.%m.%Y}'
    if start.year == end.year:
        return f'СПРАВКА_сроки_{start:%d.%m}-{end:%d.%m.%Y}'
    return f'СПРАВКА_сроки_{start:%d.%m.%Y}-{end:%d.%m.%Y}'


def window_title(start, end, with_year=True):
    """Заголовок окна: «13.08–17.08.2026» (или без года — «13.08–17.08»)."""
    if not with_year and start.year == end.year:
        return f'{start:%d.%m}–{end:%d.%m}'
    if (start.year, start.month) == (end.year, end.month):
        return f'{start:%d.%m}–{end:%d.%m.%Y}'
    return f'{start:%d.%m.%Y}–{end:%d.%m.%Y}'


# ─────────────────────────── сбор данных ───────────────────────────

def collect_window(data, start, end, today=None, include_overdue=False):
    """Активные задачи с дедлайном в окне, сгруппированные по проектам.

    Возвращает (groups, stats), где stats — счётчики задач, оставшихся
    за левой границей окна (в группы они попадают только при include_overdue):
      before_window — активных задач со сроком раньше `start`;
      overdue_now   — из них уже просроченных на сегодня (срок < today).
    Счётчики различаются, когда окно начинается в будущем.
    """
    today = today or date.today()
    proj_by_name = {p['name']: p for p in data.get('projects', [])}
    groups = {}
    stats = {'before_window': 0, 'overdue_now': 0}

    for t in data.get('all_tasks', []):
        if t.get('status') in CLOSED_STATUSES:
            continue
        dl = parse_deadline(t.get('deadline'))
        if not dl or dl > end:
            continue
        if dl < start:
            stats['before_window'] += 1
            if dl < today:
                stats['overdue_now'] += 1
            if not include_overdue:
                continue

        pname = t.get('project') or '(без проекта)'
        group = groups.setdefault(pname, {
            'name':    pname,
            'project': proj_by_name.get(pname),
            'tasks':   [],
        })
        group['tasks'].append({
            'id':        t.get('id'),
            'theme':     t.get('theme') or '(без темы)',
            'status':    t.get('status') or '',
            'executor':  t.get('executor_short') or t.get('executor') or '—',
            'deadline':  t.get('deadline'),
            'dl':        dl,
            'days_left': (dl - today).days,
        })

    result = list(groups.values())
    for g in result:
        g['tasks'].sort(key=lambda x: (x['dl'], x['theme']))
        g['min_dl']  = min(t['dl'] for t in g['tasks'])
        g['overdue'] = sum(1 for t in g['tasks'] if t['days_left'] < 0)
        g['total']   = len(g['tasks'])
    result.sort(key=lambda g: (g['min_dl'], -g['total'], g['name']))
    return result, stats


def before_window_line(stats, start, today, bold=False):
    """Справочная строка про задачи за левой границей окна (bold — для markdown)."""
    def n(value):
        return f'**{value}**' if bold else str(value)

    if start > today:
        return (f'Активных задач со сроком до начала периода — {n(stats["before_window"])}, '
                f'из них уже просрочено на {today:%d.%m.%Y} — {n(stats["overdue_now"])}.')
    line = (f'Ранее просроченных активных задач (срок < {start:%d.%m.%Y}) — '
            f'{n(stats["before_window"])}.')
    if not stats['before_window']:
        line += ' Вся зона риска сосредоточена в текущем окне.'
    return line


def tasks_by_day(groups):
    """{date: количество задач} по всем группам."""
    counts = {}
    for g in groups:
        for t in g['tasks']:
            counts[t['dl']] = counts.get(t['dl'], 0) + 1
    return counts


def tasks_by_status(groups):
    """{статус: количество}, по убыванию количества."""
    counts = {}
    for g in groups:
        for t in g['tasks']:
            counts[t['status'] or '—'] = counts.get(t['status'] or '—', 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def time_left(days, style='md'):
    """Человеческая подпись остатка срока.

    style='md'  — для колонки таблицы: «сегодня», «завтра (1 день)», «4 дня»
    style='txt' — для строки отчёта:   «сегодня», «завтра, через 1 день», «через 4 дня»
    """
    if days < 0:
        return f'просрочено на {plural_days(-days)}'
    if days == 0:
        return 'сегодня'
    if days == 1:
        return 'завтра, через 1 день' if style == 'txt' else 'завтра (1 день)'
    return f'через {plural_days(days)}' if style == 'txt' else plural_days(days)


def detect_source(data_path, updated_at):
    """Имя выгрузки Redmine, из которой собран data.json.

    Совпадение по времени: `updated_at` (ДД.ММ.ГГГГ ЧЧ:ММ) против mtime файлов
    `issues*.xlsx` рядом с data.json. Не нашли — None (строка источника
    обойдётся без имени файла).
    """
    if not updated_at:
        return None
    try:
        stamp = datetime.strptime(updated_at, '%d.%m.%Y %H:%M')
    except ValueError:
        return None
    folder = os.path.dirname(os.path.abspath(data_path)) or '.'
    for path in glob.glob(os.path.join(folder, 'issues*.xlsx')):
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if abs((mtime - stamp).total_seconds()) <= 60:
            return os.path.basename(path)
    return None


def project_meta(group):
    """(эмодзи, звезда, тип, ответственный, url) проекта группы."""
    proj = group['project'] or {}
    prio = bool(proj.get('is_priority'))
    return (
        '🔴' if prio else '🔵',
        ' ★' if prio else '',
        '_🔴 приоритетный_' if prio else '_🔵 трансформационный_',
        proj.get('owner_short') or '—',
        proj.get('url'),
    )


# ─────────────────────────── рендер: txt ───────────────────────────

def _render_task_txt(t):
    lines = [
        f'   • {t["theme"]}',
        f'     👤 {t["executor"]}',
        f'     📅 Дедлайн: {t["deadline"]} ({time_left(t["days_left"], "txt")})',
    ]
    if t['status']:
        lines.append(f'     📌 Статус: {t["status"]}')
    if t.get('id'):
        lines.append(f'     🔗 {REDMINE_BASE}/{t["id"]}')
    lines.append('')
    return lines


def build_txt(groups, start, end, today, stats, updated_at=None):
    out = []
    total = sum(g['total'] for g in groups)
    out.append(f'📊 Справка по задачам на контроле: сроки {window_title(start, end)}')
    out.append(f'Дата формирования: {today:%d.%m.%Y}'
               + (f' (данные data.json от {updated_at})' if updated_at else ''))
    if not groups:
        out.append('')
        out.append('✅ Задач со сроком в этом периоде нет.')
        return '\n'.join(out)

    out.append(f'Всего: {plural_tasks(total)} в {plural_projects(len(groups))}')
    out.append('')
    out.append('Разбивка по датам:')
    counts = tasks_by_day(groups)
    d = min(start, min(counts))
    while d <= end:
        mark = ' ← сегодня' if d == today else ''
        out.append(f'   {d:%d.%m.%Y} ({WEEKDAYS[d.weekday()]}): '
                   f'{plural_tasks(counts.get(d, 0))}{mark}')
        d += timedelta(days=1)
    out.append('')
    line = before_window_line(stats, start, today)
    out.append('Справочно: ' + line[0].lower() + line[1:])
    out.append('')
    out.append(SEPARATOR_THICK)
    out.append('')

    for idx, g in enumerate(groups, start=1):
        emoji, _, _, owner, url = project_meta(g)
        out.append(f'{idx}. {emoji} {g["name"]}')
        out.append(f'👤 Ответственный: {owner}')
        if url:
            out.append(f'🔗 {url}')
        out.append('')

        overdue = [t for t in g['tasks'] if t['days_left'] < 0]
        ahead   = [t for t in g['tasks'] if t['days_left'] >= 0]
        if overdue:
            out.append(f'⏰ Просроченные задачи ({len(overdue)}):')
            for t in overdue:
                out.extend(_render_task_txt(t))
        if ahead:
            out.append(f'⏳ Задачи со сроком {window_title(start, end, with_year=False)} '
                       f'({len(ahead)}):')
            for t in ahead:
                out.extend(_render_task_txt(t))

        if idx < len(groups):
            out.append(SEPARATOR_THIN)
            out.append('')

    return '\n'.join(out)


# ─────────────────────────── рендер: md ───────────────────────────

def md_cell(s):
    return str(s).replace('|', '\\|').strip()


def build_md(groups, start, end, today, stats,
             updated_at=None, source=None):
    out = []
    total = sum(g['total'] for g in groups)
    out.append(f'# Справка по задачам со сроком {window_title(start, end)}')
    out.append('')
    out.append(f'**Период:** {start:%d.%m.%Y}'
               + (' (сегодня)' if start == today else '')
               + f' — {end:%d.%m.%Y} включительно')
    src = f'`data.json`' + (f' от {updated_at}' if updated_at else '')
    if source:
        src += f' (выгрузка Redmine `{source}`)'
    out.append(f'**Источник:** {src}, трекер «Мероприятие проекта»')
    out.append('**Отбор:** срок завершения попадает в период, статус не входит в закрытые '
               f'({", ".join(sorted(CLOSED_STATUSES))})')
    out.append('')
    if not groups:
        out.append('**Итого:** задач со сроком в этом периоде нет.')
        return '\n'.join(out) + '\n'

    out.append(f'**Итого:** {plural_tasks(total)} в {plural_projects(len(groups))} — это задачи, '
               'которые уйдут в просрочку, если не будут закрыты в срок.')
    out.append('')
    out.append('> ' + before_window_line(stats, start, today, bold=True))
    out.append('')
    out.append('**Разбивка по датам:**')
    out.append('')
    out.append('| Дата | День недели | Задач |')
    out.append('|---|---|---:|')
    counts = tasks_by_day(groups)
    d = min(start, min(counts))
    while d <= end:
        mark = ' _(сегодня)_' if d == today else ''
        out.append(f'| {d:%d.%m.%Y}{mark} | {WEEKDAYS[d.weekday()]} | {counts.get(d, 0)} |')
        d += timedelta(days=1)
    out.append(f'| | **ИТОГО** | **{total}** |')
    out.append('')
    out.append('---')
    out.append('')
    out.append('## Часть 1. Детализированный отчёт')
    out.append('')

    for idx, g in enumerate(groups, start=1):
        _, star, kind, owner, url = project_meta(g)
        out.append(f'### {idx}. {md_cell(g["name"])}{star}')
        out.append(f'**Куратор/ответственный по проекту:** {owner} · {kind}')
        out.append(f'**Задач со сроком в периоде:** {plural_tasks(g["total"])}'
                   + (f' (из них просрочено: {g["overdue"]})' if g['overdue'] else ''))
        if url:
            out.append(f'**Проект в Redmine:** {url}')
        out.append('')
        out.append('| № | Задача | Ответственный сотрудник | Дедлайн | Осталось | Статус | Redmine |')
        out.append('|---|---|---|---|---|---|---|')
        for n, t in enumerate(g['tasks'], start=1):
            link = f'[{t["id"]}]({REDMINE_BASE}/{t["id"]})' if t.get('id') else '—'
            out.append(f'| {n} | {md_cell(t["theme"])} | **{md_cell(t["executor"])}** | '
                       f'{t["deadline"]} | {time_left(t["days_left"])} | '
                       f'{md_cell(t["status"])} | {link} |')
        out.append('')

    out.append('---')
    out.append('')
    out.append('## Часть 2. Краткая сводка — проект / количество задач в периоде')
    out.append('')
    out.append('| № | Проект | Ответственный | Задач | Ближайший срок |')
    out.append('|---|---|---|---:|---|')
    for idx, g in enumerate(groups, start=1):
        _, star, _, owner, _ = project_meta(g)
        out.append(f'| {idx} | {md_cell(g["name"])}{star} | {owner} | {g["total"]} | '
                   f'{g["min_dl"]:%d.%m.%Y} |')
    out.append(f'| | **ИТОГО** | | **{total}** | |')
    out.append('')
    if any((g['project'] or {}).get('is_priority') for g in groups):
        out.append('★ — приоритетный проект')
    else:
        out.append('_Приоритетных (★) проектов среди задач периода нет — '
                   'все проекты трансформационные._')
    out.append('')
    out.append('---')
    out.append('')
    out.append('## Часть 3. Обратить внимание')
    out.append('')
    by_status = tasks_by_status(groups)
    statuses = ', '.join(f'«{k}» — {v}' for k, v in by_status.items())
    line = f'- **Статусы задач периода:** {statuses}.'
    if by_status.get('Новая'):
        line += ' По задачам в статусе «Новая» работа в Redmine ещё не отмечена начатой.'
    out.append(line)
    peak_day, peak_n = max(counts.items(), key=lambda kv: (kv[1], -kv[0].toordinal()))
    out.append(f'- **Пик нагрузки — {peak_day:%d.%m.%Y}** ({WEEKDAYS[peak_day.weekday()]}): '
               f'{plural_tasks(peak_n)}.')
    weekend_days = sorted(k for k, v in counts.items() if k.weekday() >= 5 and v)
    if weekend_days:
        weekend = sum(counts[k] for k in weekend_days)
        dates = '–'.join(f'{d:%d.%m}' for d in (weekend_days[0], weekend_days[-1])) \
            if len(weekend_days) > 1 else f'{weekend_days[0]:%d.%m}'
        workday = weekend_days[0]
        while workday.weekday() >= 5:
            workday -= timedelta(days=1)
        out.append(f'- **{plural_tasks(weekend)} со сроком в выходные** ({dates}) — '
                   f'фактический срок исполнения приходится на '
                   f'{WEEKDAYS_ACC[workday.weekday()]} {workday:%d.%m}.')
    overdue_in = sum(g['overdue'] for g in groups)
    if overdue_in:
        out.append(f'- **{plural_tasks(overdue_in)} уже просрочено** и включено в справку '
                   '(флаг `--include-overdue`).')
    out.append('')
    return '\n'.join(out)


# ─────────────────────────── CLI ───────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Справка по задачам с приближающимся сроком.')
    ap.add_argument('--from', dest='start', metavar='ДД.ММ.ГГГГ',
                    help='начало окна (по умолчанию — сегодня)')
    ap.add_argument('--to', dest='end', metavar='ДД.ММ.ГГГГ',
                    help='конец окна включительно')
    ap.add_argument('--days', type=int,
                    help=f'длина окна в днях от начала (по умолчанию {DEFAULT_DAYS})')
    ap.add_argument('--format', choices=['txt', 'md', 'both'], default='both',
                    help='формат выгрузки (по умолчанию both)')
    ap.add_argument('--include-overdue', action='store_true',
                    help='включить в справку ранее просроченные задачи')
    ap.add_argument('--data', default='data.json', help='путь к data.json')
    ap.add_argument('--outdir', default='.', help='каталог для файлов справки')
    ap.add_argument('--output', metavar='ИМЯ',
                    help='имя файла без расширения (по умолчанию СПРАВКА_сроки_…)')
    ap.add_argument('--stdout', action='store_true',
                    help='напечатать справку в консоль вместо записи файлов')
    args = ap.parse_args()

    try:
        start, end = resolve_window(
            parse_date_arg(args.start) if args.start else None,
            parse_date_arg(args.end) if args.end else None,
            args.days,
        )
    except ValueError as e:
        ap.error(str(e))

    try:
        with open(args.data, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        ap.error(f'не читается {args.data}: {e}')

    today = date.today()
    groups, stats = collect_window(
        data, start, end, today=today, include_overdue=args.include_overdue)

    renders = {
        'txt': lambda: build_txt(groups, start, end, today, stats,
                                 data.get('updated_at')),
        'md':  lambda: build_md(groups, start, end, today, stats,
                                data.get('updated_at'),
                                detect_source(args.data, data.get('updated_at'))),
    }
    formats = ['txt', 'md'] if args.format == 'both' else [args.format]

    if args.stdout:
        for i, fmt in enumerate(formats):
            if i:
                print('\n' + '=' * 60 + '\n')
            print(renders[fmt]())
        return

    stem = args.output or window_slug(start, end)
    written = []
    for fmt in formats:
        path = f'{args.outdir.rstrip("/")}/{stem}.{fmt}'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(renders[fmt]())
        written.append(path)

    total = sum(g['total'] for g in groups)
    print(f'✅ Справка {window_title(start, end)}: '
          f'{plural_tasks(total)} в {plural_projects(len(groups))}'
          + (f', просрочено ранее {stats["overdue_now"]}' if stats['overdue_now'] else ''))
    for p in written:
        print(f'   → {p}')


if __name__ == '__main__':
    main()
