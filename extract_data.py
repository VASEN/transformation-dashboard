"""
extract_data.py — скрипт извлечения данных из Excel в data.json
Запуск: python3 extract_data.py

Положи этот файл рядом с Excel-файлами:
  - Трансформация.xlsx
  - Проекты_НМА.xlsx

На выходе создаётся data.json, который читает дашборд.
"""

import pandas as pd
import json
from datetime import datetime
from pathlib import Path

# ===== НАСТРОЙКИ =====
TRANSFORMACIA_FILE = "Трансформация.xlsx"
NMA_FILE = "Проекты_НМА.xlsx"
OUTPUT_FILE = "data.json"


# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def clean_date(v):
    """Приводит дату к формату DD.MM.YYYY"""
    if pd.isna(v):
        return None
    s = str(v).strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s[:10], fmt).strftime('%d.%m.%Y')
        except:
            pass
    return s[:10] if len(s) >= 10 else s


def clean_pct(v):
    """Очищает процент готовности"""
    if pd.isna(v):
        return 0
    s = str(v).replace('%', '').replace(',', '.').strip()
    try:
        return int(float(s))
    except:
        return 0


def safe(v):
    """Безопасно преобразует значение в строку, None если пусто"""
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s if s and s != 'nan' else None


def get_urgency(deadline_str):
    """Определяет срочность по дедлайну"""
    if not deadline_str:
        return 'ok'
    try:
        days = (datetime.strptime(deadline_str, '%d.%m.%Y') - datetime.now()).days
        if days <= 5:
            return 'urgent'
        elif days <= 14:
            return 'soon'
    except:
        pass
    return 'ok'


def safe_float(v):
    try:
        return float(v) if pd.notna(v) else None
    except:
        return None


def safe_int(v):
    try:
        return int(v) if pd.notna(v) else None
    except:
        return None


# ===== ОСНОВНАЯ ЛОГИКА =====

def extract():
    print(f"📂 Читаем {TRANSFORMACIA_FILE}...")
    df = pd.read_excel(TRANSFORMACIA_FILE)

    # --- Разделяем на проекты и задачи ---
    projects_raw = df[df['Родительская задача'].isna()].copy()
    tasks_raw = df[df['Родительская задача'].notna()].copy()

    # --- Проекты ---
    projects = []
    for _, r in projects_raw.iterrows():
        projects.append({
            'id': safe_int(r.get('#')),
            'name': safe(r.get('Проект')),
            'theme': safe(r.get('Тема')),
            'status': safe(r.get('Статус')),
            'person': safe(r.get('Назначена')),
            'deadline': clean_date(r.get('Срок завершения')),
            'start_date': clean_date(r.get('Дата начала')),
            'pct': clean_pct(r.get('Готовность')),
            'curator': safe(r.get('Куратор')),
            'goal': safe(r.get('Критически важная цель')),
            'indicators': safe(r.get('Опережающие показатели (что делаем)')),
            'team': safe(r.get('Команда проекта')),
            'current_status': safe(r.get('Актуальный статус')),
            'problem': safe(r.get('Проблема')),
            'project_type': safe(r.get('Тип проекта')),
            'plan_hours': safe_float(r.get('План высвобождения трудозатрат всего, часы')),
            'fact_hours': safe_float(r.get('Факт высвобождения трудозатрат всего, часы')),
            'plan_units': safe_float(r.get('План: в том числе фактическое сокращение сотрудников всего, шт.ед.')),
        })
    print(f"  ✅ Проектов: {len(projects)}")

    # --- Задачи ---
    tasks = []
    for _, r in tasks_raw.iterrows():
        dl = clean_date(r.get('Срок завершения'))
        tasks.append({
            'id': safe_int(r.get('#')),
            'project': safe(r.get('Проект')),
            'theme': safe(r.get('Тема')),
            'status': safe(r.get('Статус')),
            'person': safe(r.get('Назначена')),
            'deadline': dl,
            'urgency': get_urgency(dl),
            'parent_id': safe_int(r.get('Родительская задача')),
            'pct': clean_pct(r.get('Готовность')),
        })
    print(f"  ✅ Задач: {len(tasks)}")

    # --- НМА: кураторы ---
    print(f"\n📂 Читаем {NMA_FILE}...")
    nma_curators = pd.read_excel(NMA_FILE, sheet_name='Лист1')
    curators = []
    for _, r in nma_curators.iterrows():
        name = safe(r.get('Куратор направления'))
        if not name:
            continue
        plan_ratio = safe_float(r.get('План высвобождения по проектам'))
        pct_vysv = round(plan_ratio * 100) if plan_ratio is not None else None
        curators.append({
            'name': name,
            'headcount': safe_int(r.get('Кол-во ставок')),
            'kkp': safe_int(r.get('из них ККП')),
            'kkp_fact': safe_int(r.get('Факт ККП')),
            'rct': safe_int(r.get(' из них РЦТ')),
            'rct_fact': safe_int(r.get('Факт РЦТ')),
            'fact_total': safe_int(r.get('Кол-во фактическое')),
            'plan_minus20': safe_float(r.get('План высвобождения - 20%')),
            'fact_vysv': safe_float(r.get('Факт высв')),
            'pct_vysv': pct_vysv,
        })
    print(f"  ✅ Кураторов: {len(curators)}")

    # --- НМА Sheet1: детализация проектов ---
    nma_proj = pd.read_excel(NMA_FILE, sheet_name='Sheet1')
    project_details = []
    for _, r in nma_proj.iterrows():
        name = safe(r.get('Проект'))
        if not name:
            continue
        project_details.append({
            'name': name,
            'person': safe(r.get('Ответственный за проект')) or safe(r.get('Назначена')),
            'curator': safe(r.get('Ответственный')),
            'status': safe(r.get('Статус')),
            'deadline': clean_date(r.get('Срок завершения')),
            'start_date': clean_date(r.get('Дата начала')),
            'goal': safe(r.get('Критически важная цель')),
            'indicators': safe(r.get('Опережающие показатели (что делаем)')),
            'team': safe(r.get('Команда проекта')),
            'current_status': safe(r.get('Актуальный статус')),
            'problem': safe(r.get('Проблема')),
            'plan_hours': safe_float(r.get('План по проектам, часы')),
            'plan_int': safe_float(r.get('Внутрнее высвобождение')),
            'plan_ext': safe_float(r.get('Внешнее высвобождение')),
            'fact_hours': safe_float(r.get('Факт высвобождения трудозатрат всего, часы')),
            'plan_units': safe_float(r.get('План, шт. ед.')),
        })
    print(f"  ✅ Детализация проектов: {len(project_details)}")

    # --- Сводная статистика ---
    active_statuses = ('В работе', 'Новая', 'На проверке')
    closed_statuses = ('Закрыта', 'Выполнено')

    tasks_active = [t for t in tasks if t['status'] in active_statuses]
    tasks_closed = [t for t in tasks if t['status'] in closed_statuses]
    tasks_urgent = [t for t in tasks_active if t['urgency'] == 'urgent']
    tasks_soon   = [t for t in tasks_active if t['urgency'] == 'soon']

    summary = {
        'projects_total': len(projects),
        'projects_active': sum(1 for p in projects if p['status'] in active_statuses),
        'projects_closed': sum(1 for p in projects if p['status'] in closed_statuses),
        'tasks_total': len(tasks),
        'tasks_active': len(tasks_active),
        'tasks_closed': len(tasks_closed),
        'tasks_deadline_5': len(tasks_urgent),
        'tasks_deadline_14': len(tasks_urgent) + len(tasks_soon),
        'tasks_overdue': len(tasks_urgent),
    }

    # --- Собираем итоговый JSON ---
    result = {
        'updated_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
        'summary': summary,
        'projects': projects,
        'tasks': tasks,
        'project_details': project_details,
        'curators': curators,
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {OUTPUT_FILE} сохранён ({Path(OUTPUT_FILE).stat().st_size // 1024} KB)")
    print(f"\n📊 Сводка:")
    print(f"  Проектов: {summary['projects_total']} (активных: {summary['projects_active']}, закрытых: {summary['projects_closed']})")
    print(f"  Задач: {summary['tasks_total']} (активных: {summary['tasks_active']}, закрытых: {summary['tasks_closed']})")
    print(f"  Дедлайн ≤5 дней: {summary['tasks_deadline_5']}")
    print(f"  Дедлайн ≤14 дней: {summary['tasks_deadline_14']}")
    print(f"  Кураторов: {len(curators)}")
    for c in curators:
        print(f"    {c['name']}: {c['pct_vysv']}% высвобождения")


if __name__ == '__main__':
    extract()
