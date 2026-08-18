#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Страница показателей цифровой трансформации → index.html.

Квартальный рейтинг ЦИО: 8 блоков, 35 подпоказателей, ровно 100 баллов. По каждому
подпоказателю видно порог, факт и цену в баллах.

С 17.08.2026 собирается **на общей дизайн-системе панели отчётов**
(`~/Projects/LIFE/otchety/dsh.py`, возврат Claude Design, круг 1) — той же, что и
вкладка «Показатели ЦТ» в панели и страница статуса роликов.

Расчёт и факты здесь не дублируются, они живут в `~/Projects/LIFE/rating/`:
`methodology.json` (блоки и пороги), `facts.json` (значения по кварталам),
`score.py` (правила), `live.py` (живые числа из свежей выгрузки Redmine).

    python3 build.py

Смотреть из корня transformation:
    python3 -m http.server 8024 --directory .
    → http://127.0.0.1:8024/pokazateli-ct/index.html
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home() / 'Projects'
RATING = HOME / 'LIFE' / 'rating'
OTCHETY = HOME / 'LIFE' / 'otchety'
sys.path.insert(0, str(RATING))
sys.path.insert(0, str(OTCHETY))

import dsh                                                    # noqa: E402
import score                                                  # noqa: E402
from dsh import (card, grid, indicator_table, metric_tile, note_list,  # noqa: E402
                 page, panel_header, section, tiles, triple_bar)

OUT = HERE / 'index.html'

try:
    from live import collect_live
    LIVE = collect_live()
except Exception:                                             # выгрузки нет — без живых чисел
    LIVE = {}


def block_section(b, notes: dict) -> str:
    """Блок целиком: полоса сверху, под ней таблица подпоказателей."""
    rows = []
    for it in b['items']:
        if it['status'] == 'unknown':
            rows.append({'name': it['name'], 'threshold': it['rule'], 'state': 'wait',
                         'weight': it['points'],
                         'reason': notes.get(it['id']) or 'данные не поступили'})
        else:
            rows.append({'name': it['name'], 'threshold': it['rule'], 'fact': it['why'],
                         'score': it['got'], 'max': it['points']})
    meta = f'набрано {b["earned"]} из {b["max"]}'
    if b['unknown']:
        meta += f' · {b["unknown"]} в подвешенном состоянии'
    if b['earned'] == b['max']:
        meta += ' · максимум взят'
    return section(b['name'],
                   triple_bar(b['name'], b['earned'], b['unknown'], b['max'],
                              meta=f'источник: {b["source"]} · влияние: {b["influence"]}')
                   + indicator_table(rows),
                   meta=meta)


def main() -> None:
    qs = score.quarters(LIVE)
    cur, prev, first = qs[-1], qs[-2], qs[0]
    ceiling = cur['earned'] + cur['unknown']
    notes = next((q.get('notes') or {} for q in score.FACTS['quarters']
                  if q['id'] == cur['id']), {})

    waiting = [(b, it) for b in cur['blocks'] for it in b['items']
               if it['status'] == 'unknown']
    losing = [(b, it) for b in cur['blocks'] for it in b['items']
              if it['status'] == 'fail']
    lost_pts = sum(it['points'] - (it['got'] or 0) for _, it in losing)

    # Коэффициент — к предыдущему кварталу с трендом по двум переходам: решение
    # владельца 17.08.2026. Индекс к среднему двух кварталов сознательно не считаем.
    d_prev = cur['earned'] - prev['total_fixed']
    d_ceil = ceiling - prev['total_fixed']

    head = tiles(
        metric_tile('Балл 3 квартала', cur['earned'], 'из 100', size='lg',
                    hint=f'потолок {ceiling}',
                    note=f'Не измерено {cur["unknown"]} баллов — они не потеряны. '
                         f'По потолку тренд к прошлому кварталу +{d_ceil}.',
                    delta=(abs(d_prev), 'down' if d_prev < 0 else 'up', 'ко 2 кварталу'),
                    track=[(first['total_fixed'], False), (prev['total_fixed'], False),
                           (cur['earned'], True)]),
        metric_tile('Ждём данных', cur['unknown'], 'баллов', state='wait',
                    hint=f'{len(waiting)} подпоказателя',
                    note='Разница между баллом и потолком.'),
        metric_tile('Теряем баллы', lost_pts, 'баллов', state='bad',
                    hint=f'{len(losing)} подпоказателей', note='В этом квартале не взять.'),
        metric_tile('Живые числа', len(cur['live_used']), 'показателя',
                    hint=', '.join(cur['live_used']) or '—',
                    note='Считаются из свежей выгрузки, а не вводятся руками.'),
    )

    lists = grid(
        note_list('Ждём данных',
                  [(it['name'], notes.get(it['id']) or b['name'], f'−{it["points"]}')
                   for b, it in waiting],
                  tone='wait', total=f'{len(waiting)} позиции · {cur["unknown"]} баллов',
                  foot=f'Пока данных нет, эти баллы дают разницу между {cur["earned"]} '
                       f'и потолком {ceiling}.') if waiting else '',
        note_list('Теряем баллы',
                  [(it['name'], notes.get(it['id']) or it['why'],
                    f'−{it["points"] - (it["got"] or 0)}') for b, it in losing],
                  tone='loss', total=f'{len(losing)} позиций · {lost_pts} баллов',
                  foot='Это уже не взять в этом квартале — только в следующем.') if losing else '',
    )

    overview = section('Восемь блоков рейтинга',
                       card(body=''.join(
                           triple_bar(b['name'], b['earned'], b['unknown'], b['max'],
                                      meta=f'{len(b["items"])} подпоказателей'
                                           + (f' · {b["unknown"]} ждут данных'
                                              if b['unknown'] else '')
                                           + (' · максимум взят'
                                              if b['earned'] == b['max'] else ''))
                           for b in cur['blocks'])),
                       meta=f'{sum(len(b["items"]) for b in cur["blocks"])} подпоказателей '
                            f'· ровно 100 баллов')

    blocks = ''.join(block_section(b, notes) for b in cur['blocks'])

    from datetime import datetime
    header = panel_header(f'Показатели цифровой трансформации · {cur["name"]}',
                          updated=f'пересчитано {datetime.now():%d.%m.%Y, %H:%M} · '
                                  f'{first["total_fixed"]} → {prev["total_fixed"]} → '
                                  f'{cur["earned"]}')
    OUT.write_text(page(f'Показатели цифровой трансформации · {cur["name"]}',
                        header, head + overview + lists + blocks), encoding='utf-8')
    dsh.write_styles(HERE)
    print(f'✓ pokazateli-ct/index.html — {cur["name"]}: {cur["earned"]} баллов, '
          f'потолок {ceiling}')
    print(f'  ждём данных: {len(waiting)} · теряем: {len(losing)} ({lost_pts} б) · '
          f'живые числа: {", ".join(cur["live_used"]) or "нет"}')


if __name__ == '__main__':
    main()
