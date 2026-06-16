"""
extract_data.py — скрипт извлечения данных из Excel в data.json
Запуск: python3 extract_data.py

Файлы-источники:
  - issues_1.xlsx                         (выгрузка из Redmine)
  - ШТАТКА_ДБ.xlsx                        (штатная численность)
  - ПРОЕКТЫ_Данные по высвобождению.xlsx  (расчёт % высвобождения)

Логика сущностей:
  Паспорт проекта:
    owner   = Ответственный (держатель, отчитывается за результат)
    manager = Назначена     (руководитель, ведёт проект)
  Мероприятие проекта (этапы и подзадачи):
    executor = Назначена    (ответственный исполнитель по задаче)

Формула % высвобождения по кураторам:
  высвобождение_шт.ед. (из файла НМА) / план_20% (из штатки) × 100
  Порядок групп в НМА-файле: Кренёва АА → Родевальд СЕ → Гуляев ВА
  Комитет и РЦТ = сумма всех трёх групп
"""

import pandas as pd
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from config import (
    ACTIVE_STATUSES, CLOSED_STATUSES, CURATOR_ORDER, TOTAL_CURATOR,
    CURATOR_NAME_FIX, COLUMN_SYNONYMS, REGRESSION_DROP_LIMIT,
    public_config, resolve_column, require_column,
)

DEFAULT_REDMINE = "issues.xlsx"
DEFAULT_SHTATKA = "ШТАТКА_ДБ.xlsx"
DEFAULT_VYSV    = "ПРОЕКТЫ_Данные по высвобождению.xlsx"

VYSV_UNITS_COLS    = COLUMN_SYNONYMS['vysv_units']
VYSV_EXTERNAL_COLS = COLUMN_SYNONYMS['vysv_external']
VYSV_INTERNAL_COLS = COLUMN_SYNONYMS['vysv_internal']


# ===== УТИЛИТЫ =====

def clean_date(v):
    if pd.isna(v): return None
    s = str(v).strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try: return datetime.strptime(s[:10], fmt).strftime('%d.%m.%Y')
        except: pass
    return s[:10] if len(s) >= 10 else s

def clean_pct(v):
    if pd.isna(v): return 0
    try: return int(float(str(v).replace('%', '').replace(',', '.').strip()))
    except: return 0

def safe(v):
    if pd.isna(v): return None
    s = str(v).strip()
    return s if s and s != 'nan' else None

def safe_float(v):
    try: return float(v) if pd.notna(v) else None
    except: return None

def safe_int(v):
    try: return int(v) if pd.notna(v) else None
    except: return None

def cell_any(row, *names):
    """Первое присутствующее непустое значение среди колонок (совместимость имён)."""
    for n in names:
        if n in row.index:
            v = row.get(n)
            if pd.notna(v):
                return v
    return None

def canon_name(name):
    """Исправляет опечатки в написании фамилий кураторов (см. CURATOR_NAME_FIX)."""
    if not name: return name
    s = str(name).strip()
    for wrong, right in CURATOR_NAME_FIX:
        s = s.replace(wrong, right)
    return s

def curator_key(name):
    """Ключ куратора по фамилии для матчинга между файлами:
    'Кудряшов Е.С.' / 'Кудряшов ЕС' → 'кудряшов'; 'Кренёва А.А.' → 'кренева'."""
    if not name: return None
    return canon_name(name).split()[0].lower().replace('ё', 'е')

def get_urgency(deadline_str, status=None):
    if status in CLOSED_STATUSES: return 'ok'
    if not deadline_str: return 'ok'
    try:
        from datetime import date as _date
        days = (datetime.strptime(deadline_str, '%d.%m.%Y').date() - _date.today()).days
        if days < 0:   return 'overdue'
        if days == 0:  return 'today'
        if days <= 5:  return 'urgent'
        if days <= 14: return 'soon'
    except: pass
    return 'ok'

def short_name(full_name):
    """'Кренева (ККП) Анастасия Андреевна' → 'Кренева А.А.'"""
    if not full_name: return None
    s = re.sub(r'\s*\(.*?\)\s*', ' ', full_name).strip()
    parts = s.split()
    if len(parts) >= 3:
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    return s


def validate_source_columns(df, required, source_name):
    """Бросает понятную ошибку, если в df нет нужных колонок (с учётом синонимов)."""
    missing = [c for c in required if resolve_column(df.columns, c) is None]
    if missing:
        raise KeyError(
            f"В файле {source_name} отсутствуют колонки: {missing}. "
            f"Есть: {list(df.columns)}"
        )


# ===== ОСНОВНАЯ ЛОГИКА =====

def write_json_atomic(result, output_file):
    """Пишет JSON во временный файл, проверяет парсингом, затем атомарно
    подменяет целевой — чтобы битый результат не затирал рабочий data.json."""
    tmp = output_file + '.tmp'
    safe_json = json.dumps(result, ensure_ascii=False, indent=2).replace('</', '<\\/')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(safe_json)
    json.loads(Path(tmp).read_text(encoding='utf-8'))  # sanity-парсинг
    os.replace(tmp, output_file)


def validate_result(result, prev=None, drop_limit=REGRESSION_DROP_LIMIT):
    """Проверяет, что результат не пустой и не просел относительно прошлого.
    Бросает ValueError с понятным текстом при нарушении."""
    errs = []
    if not result.get('projects'):
        errs.append('нет проектов')
    if not result.get('all_tasks'):
        errs.append('нет задач')
    if not result.get('curators'):
        errs.append('нет кураторов')
    if prev:
        for key in ('projects', 'all_tasks'):
            old, new = len(prev.get(key, [])), len(result.get(key, []))
            if old and new < old * (1 - drop_limit):
                errs.append(
                    f'{key}: было {old}, стало {new} '
                    f'(просадка > {int(drop_limit * 100)}%)'
                )
    if errs:
        raise ValueError('Валидация data.json не пройдена: ' + '; '.join(errs))


def extract(redmine_file=DEFAULT_REDMINE, shtatka_file=DEFAULT_SHTATKA,
            vysv_file=DEFAULT_VYSV, output_file="data.json"):

    # ── 1. Redmine выгрузка ──────────────────────────────────────────────────
    print(f"📂 Читаем {redmine_file}...")
    df = pd.read_excel(redmine_file)
    validate_source_columns(
        df, ['Трекер', '#', 'Проект', 'Статус', 'Родительская задача'], redmine_file
    )

    passport   = df[df['Трекер'] == 'Паспорт проекта'].copy()
    activities = df[df['Трекер'] == 'Мероприятие проекта'].copy()
    passport_ids = set(passport['#'].tolist())

    all_tasks_df_rows = []
    covered_ids = set()
    parent_ids = passport_ids.copy()
    level = 0

    while True:
        children = activities[
            activities['Родительская задача'].isin(parent_ids) &
            ~activities['#'].isin(covered_ids)
        ].copy()
        if children.empty:
            break
        level += 1
        new_ids = set(children['#'].tolist())
        print(f"  L{level}: {len(children)} задач")
        all_tasks_df_rows.append(children)
        covered_ids |= new_ids
        parent_ids = new_ids

    all_tasks_df = pd.concat(all_tasks_df_rows) if all_tasks_df_rows else pd.DataFrame()
    print(f"  Итого задач всех уровней: {len(all_tasks_df)}")

    # Диагностика: показываем уникальные значения поля Приоритетный проект
    if 'Приоритетный проект' in passport.columns:
        priority_values = sorted(passport['Приоритетный проект'].dropna().unique().tolist())
        print(f"  Значения поля 'Приоритетный проект': {priority_values}")
        priority_counts = passport['Приоритетный проект'].value_counts().to_dict()
        for val, cnt in sorted(priority_counts.items(), key=lambda x: -x[1]):
            print(f"    {val}: {cnt} проектов")
    else:
        print("  ⚠️  Колонка 'Приоритетный проект' не найдена в файле!")
        print(f"  Доступные колонки: {list(passport.columns)}")

    # ── 2. Проекты ───────────────────────────────────────────────────────────
    projects = []
    for _, r in passport.iterrows():
        dl = clean_date(r.get('Срок завершения'))
        projects.append({
            'id':             safe_int(r.get('#')),
            'name':           safe(r.get('Проект')),
            'status':         safe(r.get('Статус')),
            'owner':          safe(r.get('Ответственный')),
            'owner_short':    short_name(safe(r.get('Ответственный'))),
            'manager':        safe(r.get('Назначена')),
            'manager_short':  short_name(safe(r.get('Назначена'))),
            'deadline':       dl,
            'start_date':     clean_date(r.get('Дата начала')),
            'closed_at':      clean_date(r.get('Закрыта')),
            'defense_at':     clean_date(r.get('Дата и время защиты')),
            'pct':            clean_pct(r.get('Готовность')),
            'project_type':   safe(r.get('Тип проекта')),
            'is_priority':    safe(r.get('Приоритетный проект')) == 'Да',
            'goal':           safe(r.get('Критически важная цель')),
            'indicators':     safe(r.get('Опережающие показатели (что делаем)')),
            'team':           safe(r.get('Команда проекта')),
            'current_status': safe(r.get('Актуальный статус')) or safe(r.get('Последний результат')),
            'problem':        safe(r.get('Проблема')),
            'plan_hours':     safe_float(r.get('План высвобождения трудозатрат всего, часы')),
            'fact_hours':     safe_float(r.get('Факт высвобождения трудозатрат всего, часы')),
            'plan_hours_cio': safe_float(r.get('План высвобождения трудозатрат ЦИО (отвечающего за проект), часы')),
            'fact_hours_cio': safe_float(r.get('Факт высвобождения трудозатрат ЦИО (отвечающего за проект), часы')),
            'plan_units':     safe_float(r.get('План: в том числе фактическое сокращение сотрудников всего, шт.ед.')),
            'fact_units':     safe_float(r.get('Факт: в том числе фактическое сокращение сотрудников всего, шт.ед.')),
            'url':            None,
            'internal_hours': None,
            'external_hours': None,
            'total_units':    None,
        })

    priority_count = sum(1 for p in projects if p.get('is_priority'))
    print(f"  Приоритетных проектов (is_priority=true): {priority_count}")
    for p in projects:
        if p.get('is_priority'):
            print(f"    ✓ #{p['id']} {p['name']}")

    # ── 3–4. Все задачи (все уровни) ─────────────────────────────────────────
    all_tasks = []
    for _, r in all_tasks_df.iterrows():
        dl  = clean_date(r.get('Срок завершения'))
        st  = safe(r.get('Статус'))
        all_tasks.append({
            'id':             safe_int(r.get('#')),
            'project':        safe(r.get('Проект')),
            'theme':          safe(r.get('Тема')),
            'status':         st,
            'executor':       safe(r.get('Назначена')),
            'executor_short': short_name(safe(r.get('Назначена'))),
            'deadline':       dl,
            'urgency':        get_urgency(dl, st),
            'pct':            clean_pct(r.get('Готовность')),
            'parent_id':      safe_int(r.get('Родительская задача')),
        })

    # ── 5. Высвобождение (ПРОЕКТЫ_НМА) ───────────────────────────────────────
    print(f"📂 Читаем {vysv_file}...")
    vdf = pd.read_excel(vysv_file)
    validate_source_columns(vdf, ['Проект'], vysv_file)

    # Overlay per-project данных из VYSV: plan_hours_cio (внутреннее), plan_units, fact_hours
    # Строки проектов — где заполнена колонка «Проект».
    vysv_proj = {}
    for _, r in vdf[vdf['Проект'].notna()].iterrows():
        name = str(r['Проект']).strip()
        internal_raw = cell_any(r, *VYSV_INTERNAL_COLS)
        units        = safe_float(cell_any(r, *VYSV_UNITS_COLS))
        vysv_proj[name] = {
            'plan_hours':     safe_float(r.get('План по проектам, часы')),
            'plan_hours_cio': safe_float(internal_raw),
            'plan_units':     units,
            'fact_hours':     safe_float(r.get('Факт высвобождения трудозатрат всего, часы')),
            'url':            safe(r.get('Ссылка на акцептованную идею')),
            'internal_hours': safe_float(internal_raw),
            'external_hours': safe_float(cell_any(r, *VYSV_EXTERNAL_COLS)),
            'total_units':    units,
        }
    for p in projects:
        v = vysv_proj.get(p['name'].strip())
        if not v:
            continue
        if v['plan_hours'] is not None:
            p['plan_hours'] = v['plan_hours']
        if v['plan_hours_cio'] is not None:
            p['plan_hours_cio'] = v['plan_hours_cio']
        if v['plan_units'] is not None:
            p['plan_units'] = v['plan_units']
        if v['fact_hours'] is not None:
            p['fact_hours'] = v['fact_hours']
        if v.get('url'):
            p['url'] = v['url']
        if v.get('internal_hours') is not None:
            p['internal_hours'] = v['internal_hours']
        if v.get('external_hours') is not None:
            p['external_hours'] = v['external_hours']
        if v.get('total_units') is not None:
            p['total_units'] = v['total_units']

    # Итоги по группам кураторов. Ключ — фамилия (curator_key), т.к. написание
    # имён в файле высвобождения и штатке может отличаться (точки, ё/е).
    def _curator_total_row(row):
        internal_raw = cell_any(row, *VYSV_INTERNAL_COLS)
        return {
            'plan_hours':     safe_float(row.get('План по проектам, часы')),
            'units':          safe_float(cell_any(row, *VYSV_UNITS_COLS)),
            'fact_hours':     safe_float(row.get('Факт высвобождения трудозатрат всего, часы')),
            'internal_hours': safe_float(internal_raw),
            'external_hours': safe_float(cell_any(row, *VYSV_EXTERNAL_COLS)),
        }

    vysv_by_curator = {}
    if 'Ответственный' in vdf.columns:
        # Новый формат: строки-заголовки кураторов (Проект пуст, Ответственный заполнен)
        header_rows = vdf[vdf['Проект'].isna() & vdf['Ответственный'].notna()]
        for _, row in header_rows.iterrows():
            key = curator_key(safe(row.get('Ответственный')))
            if key:
                vysv_by_curator[key] = _curator_total_row(row)
    else:
        # Старый формат: NaN-строки в порядке CURATOR_ORDER
        nan_rows = vdf[vdf['Проект'].isna()].reset_index(drop=True)
        for i, curator_name in enumerate(CURATOR_ORDER):
            if i < len(nan_rows):
                vysv_by_curator[curator_key(curator_name)] = _curator_total_row(nan_rows.iloc[i])

    # ── 6. Штатка + % высвобождения ──────────────────────────────────────────
    print(f"📂 Читаем {shtatka_file}...")
    sh = pd.read_excel(shtatka_file)
    validate_source_columns(
        sh, ['Куратор направления', 'План высвобождения - 20%'], shtatka_file
    )

    curators        = []
    total_units     = 0.0
    total_plan20    = 0.0
    total_internal  = 0.0
    total_external  = 0.0

    for _, r in sh.iterrows():
        name = canon_name(safe(r.get('Куратор направления')))
        if not name: continue

        plan20 = safe_float(r.get('План высвобождения - 20%'))
        vysv   = vysv_by_curator.get(curator_key(name), {})
        units  = vysv.get('units')

        if units is not None and plan20:
            pct_vysv = round(units / plan20 * 100)
            if name != TOTAL_CURATOR:
                total_units  += units
                total_plan20 += plan20
                if vysv.get('internal_hours') is not None:
                    total_internal += vysv['internal_hours']
                if vysv.get('external_hours') is not None:
                    total_external += vysv['external_hours']
        else:
            pct_vysv = None

        curators.append({
            'name':                name,
            'headcount':           safe_int(r.get('Кол-во ставок')),
            'kkp':                 safe_int(r.get('из них ККП')),
            'kkp_fact':            safe_int(r.get('Факт ККП')),
            'rct':                 safe_int(r.get(' из них РЦТ')),
            'rct_fact':            safe_int(r.get('Факт РЦТ')),
            'fact_total':          safe_int(r.get('Кол-во фактическое')),
            'vacancies':           safe_int(r.get('Вакансии')),
            'plan_minus20':        plan20,
            'vysv_units':          units,
            'vysv_plan_hours':     vysv.get('plan_hours'),
            'vysv_fact_hours':     vysv.get('fact_hours'),
            'vysv_internal_hours': vysv.get('internal_hours'),
            'vysv_external_hours': vysv.get('external_hours'),
            'pct_vysv':            pct_vysv,
        })

    # Пересчитываем итог для "Комитет и РЦТ"
    total_pct = round(total_units / total_plan20 * 100) if total_plan20 else None
    for c in curators:
        if c['name'] == TOTAL_CURATOR:
            c['vysv_units']          = round(total_units, 2)
            c['pct_vysv']            = total_pct
            c['vysv_internal_hours'] = round(total_internal, 2) if total_internal else None
            c['vysv_external_hours'] = round(total_external, 2) if total_external else None

    # ── 7. Сводная статистика ─────────────────────────────────────────────────
    t_active = [t for t in all_tasks if t['status'] in ACTIVE_STATUSES]
    t_closed = [t for t in all_tasks if t['status'] in CLOSED_STATUSES]
    t_overdue = [t for t in t_active if t['urgency'] == 'overdue']
    t_today   = [t for t in t_active if t['urgency'] == 'today']
    t_urgent  = [t for t in t_active if t['urgency'] == 'urgent']
    t_soon    = [t for t in t_active if t['urgency'] == 'soon']
    p_active = [p for p in projects if p['status'] in ACTIVE_STATUSES]
    p_closed = [p for p in projects if p['status'] in CLOSED_STATUSES]
    avg_pct  = round(sum(p['pct'] for p in p_active) / len(p_active)) if p_active else 0

    summary = {
        'projects_total':    len(projects),
        'projects_active':   len(p_active),
        'projects_closed':   len(p_closed),
        'projects_avg_pct':  avg_pct,
        'tasks_total':       len(all_tasks),
        'tasks_active':      len(t_active),
        'tasks_closed':      len(t_closed),
        'tasks_deadline_5':  len(t_today) + len(t_urgent),
        'tasks_deadline_14': len(t_overdue) + len(t_today) + len(t_urgent) + len(t_soon),
        'tasks_overdue':     len(t_overdue),
        'tasks_today':       len(t_today),
        'vysv_pct_total':    total_pct,
    }

    # ── 8. Сохраняем JSON ─────────────────────────────────────────────────────
    result = {
        'updated_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
        'config':     public_config(),
        'summary':    summary,
        'projects':   projects,
        'all_tasks':  all_tasks,
        'curators':   curators,
    }

    prev = None
    if os.path.exists(output_file):
        try:
            prev = json.loads(Path(output_file).read_text(encoding='utf-8'))
        except (ValueError, OSError):
            prev = None
    validate_result(result, prev)
    write_json_atomic(result, output_file)

    kb = Path(output_file).stat().st_size // 1024
    print(f"\n✅ {output_file} сохранён ({kb} KB)")
    print(f"\n📊 Сводка:")
    print(f"  Проектов:           {summary['projects_total']}  (активных: {summary['projects_active']}, закрытых: {summary['projects_closed']})")
    print(f"  Среднее выполнение: {summary['projects_avg_pct']}%")
    print(f"  Этапов + задач:     {summary['tasks_total']}  (активных: {summary['tasks_active']}, закрытых: {summary['tasks_closed']})")
    print(f"  Дедлайн ≤5 дней:    {summary['tasks_deadline_5']}")
    print(f"  Дедлайн ≤14 дней:   {summary['tasks_deadline_14']}")
    print()
    print(f"  {'Куратор':<20} {'Ставок':>7} {'Факт':>6} {'шт.ед.':>8} {'план20':>7} {'%':>5}")
    print(f"  {'-'*52}")
    for c in curators:
        units_s = f"{c['vysv_units']:.2f}" if c['vysv_units'] else '—'
        pct_s   = f"{c['pct_vysv']}%" if c['pct_vysv'] else '—'
        print(f"  {c['name']:<20} {str(c['headcount'] or ''):>7} {str(c['fact_total'] or ''):>6} {units_s:>8} {str(c['plan_minus20'] or ''):>7} {pct_s:>5}")


if __name__ == '__main__':
    extract(
        sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REDMINE,
        sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SHTATKA,
        sys.argv[3] if len(sys.argv) > 3 else DEFAULT_VYSV,
    )
