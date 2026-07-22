#!/usr/bin/env python3
"""compare_data.py — что изменилось между двумя data.json.

Сравнивает сводку, поля проектов и итоги кураторов; отдельно проверяет
инвариант сходимости: сумма шт.ед. по проектам == итог «Комитет и РЦТ».
"""
import json
import sys

PROJECT_FIELDS = (
    'internal_hours', 'external_hours', 'total_units', 'plan_hours',
    'plan_units', 'fact_hours', 'url', 'status', 'deadline', 'pct',
)
CURATOR_FIELDS = ('vysv_units', 'pct_vysv', 'vysv_internal_hours', 'vysv_external_hours')
TOTAL_CURATOR = 'Комитет и РЦТ'


def _fmt(v):
    return f'{v:.2f}' if isinstance(v, float) else repr(v)


def convergence(data):
    """(сумма шт.ед. по проектам, итог куратора «Комитет и РЦТ»)."""
    total = sum(p['total_units'] for p in data.get('projects', []) if p.get('total_units'))
    komitet = next((c.get('vysv_units') for c in data.get('curators', [])
                    if c.get('name') == TOTAL_CURATOR), None)
    return total, komitet


def main():
    base = json.load(open(sys.argv[1], encoding='utf-8'))
    work = json.load(open(sys.argv[2], encoding='utf-8'))

    lines = []

    b_sum, w_sum = base.get('summary', {}), work.get('summary', {})
    for k in sorted(set(b_sum) | set(w_sum)):
        if k in ('updated_at', 'report_updated_at'):
            continue
        if b_sum.get(k) != w_sum.get(k):
            lines.append(f'summary.{k}: {_fmt(b_sum.get(k))} → {_fmt(w_sum.get(k))}')

    b_proj = {p['id']: p for p in base.get('projects', [])}
    for p in work.get('projects', []):
        q = b_proj.get(p['id'])
        if q is None:
            lines.append(f'НОВЫЙ проект: {p["name"]}')
            continue
        for f in PROJECT_FIELDS:
            if p.get(f) != q.get(f):
                lines.append(f'{p["name"][:44]} · {f}: {_fmt(q.get(f))} → {_fmt(p.get(f))}')
    w_ids = {p['id'] for p in work.get('projects', [])}
    for pid, q in b_proj.items():
        if pid not in w_ids:
            lines.append(f'ПРОПАЛ проект: {q["name"]}')

    b_cur = {c['name']: c for c in base.get('curators', [])}
    for c in work.get('curators', []):
        q = b_cur.get(c['name'], {})
        for f in CURATOR_FIELDS:
            if c.get(f) != q.get(f):
                lines.append(f'куратор {c["name"]} · {f}: {_fmt(q.get(f))} → {_fmt(c.get(f))}')

    print('\n'.join(lines) if lines else 'без изменений')

    b_total, b_kom = convergence(base)
    w_total, w_kom = convergence(work)
    print()
    print('Сходимость (сумма шт.ед. по проектам ↔ итог «Комитет и РЦТ»):')
    for label, total, kom in (('base', b_total, b_kom), ('work', w_total, w_kom)):
        if kom is None:
            print(f'   {label}: итог куратора не найден')
            continue
        mark = '✅' if abs(total - kom) < 0.05 else '⚠️ РАСХОЖДЕНИЕ'
        print(f'   {label}: {total:.2f} ↔ {kom:.2f}  {mark}')


if __name__ == '__main__':
    main()
