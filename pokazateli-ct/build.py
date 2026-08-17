#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Страница показателей цифровой трансформации → index.html.

Показывает рейтинг ЦИО по кварталам: 8 блоков, 35 подпоказателей, 100 баллов.
По каждому видно значение, порог и цену вопроса в баллах.

Расчёт и факты не дублируются — они живут в `~/Projects/LIFE/rating/`:
  · `methodology.json` — блоки, веса, пороги (восстановлены из заголовков выгрузки);
  · `facts.json` — значения по кварталам;
  · `score.py` — правила подсчёта; `live.py` — живые числа из свежей выгрузки Redmine.
Здесь только подача. Второй источник значений завести нельзя: учёт разъедется,
а квартальная динамика считается по одной и той же истории.

    python3 build.py                 # → index.html

Смотреть через локальный сервер, из корня transformation:
    python3 -m http.server 8024 --directory .
    → http://127.0.0.1:8024/pokazateli-ct/index.html
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATING = Path.home() / 'Projects' / 'LIFE' / 'rating'
sys.path.insert(0, str(RATING))

import score                                        # noqa: E402

OUT = HERE / 'index.html'

try:
    from live import collect_live
    LIVE = collect_live()
except Exception:                                   # выгрузки нет — живые числа опустим
    LIVE = {}

REPORTS = score.quarters(LIVE)
CURRENT = REPORTS[-1]
PREV = REPORTS[-2]
FIRST = REPORTS[0]
METHOD = score.METHOD if hasattr(score, 'METHOD') else None
FACTS_CUR = [q for q in score.FACTS['quarters'] if q['id'] == CURRENT['id']][0]
NOTES = FACTS_CUR.get('notes') or {}

CEILING = CURRENT['earned'] + CURRENT['unknown']


def E(s) -> str:
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if s is not None else '')


def delta(now: int, was: int) -> str:
    d = now - was
    if d == 0:
        return '<span class="dl same">без изменений</span>'
    cls = 'up' if d > 0 else 'down'
    return f'<span class="dl {cls}">{"+" if d > 0 else "−"}{abs(d)}</span>'


# ── сборка строк ─────────────────────────────────────────────────────────
def item_row(it: dict, block_id: str) -> str:
    """Подпоказатель: чем он измеряется, что вышло и сколько это стоит в баллах."""
    st = it['status']
    note = NOTES.get(it['id'])
    live = ' <em class="live">живое число</em>' if it['id'] in CURRENT['live_used'] else ''
    if st == 'unknown':
        val = '<span class="v wait">нет данных</span>'
        got = f'<span class="pts wait">−{it["points"]}</span>'
    else:
        val = f'<span class="v {"ok" if st == "ok" else "bad"}">{E(it["why"])}</span>'
        got = (f'<span class="pts ok">{it["got"]}</span>' if it['got'] == it['points']
               else f'<span class="pts bad">{it["got"]} из {it["points"]}</span>')
    return f'''      <tr class="i-{st}">
        <td class="i-name">{E(it['name'])}{live}
          {f'<em class="i-note">{E(note)}</em>' if note else ''}</td>
        <td class="i-rule">{E(it['rule'])}</td>
        <td class="i-val">{val}</td>
        <td class="i-pts">{got}</td>
      </tr>'''


def block_card(b: dict) -> str:
    prev_b = next((x for x in PREV['blocks'] if x['id'] == b['id']), None)
    prev_val = (prev_b.get('fixed') if prev_b and prev_b.get('fixed') is not None
                else (prev_b or {}).get('earned'))
    ceiling = b['earned'] + b['unknown']
    pct = round(b['earned'] / b['max'] * 100)
    state = ('full' if b['earned'] == b['max'] else
             'wait' if b['unknown'] else
             'part')
    return f'''  <section class="blk {state}">
    <header class="blk-h">
      <div>
        <h2>{E(b['name'])}</h2>
        <p class="blk-src">источник: {E(b['source'])} · влияние: {E(b['influence'])}</p>
      </div>
      <div class="blk-sc">
        <b>{b['earned']}</b><span>из {b['max']}</span>
        {f'<em class="blk-ceil">потолок {ceiling}</em>' if b['unknown'] else ''}
        <em class="blk-prev">Q2: {prev_val if prev_val is not None else '—'}
          {'' if prev_val is None else
             delta(ceiling, prev_val) + ' по потолку' if b['unknown'] else
             delta(b['earned'], prev_val)}</em>
      </div>
    </header>
    <div class="bar"><i style="width:{pct}%"></i>
      {f'<u style="width:{round(b["unknown"] / b["max"] * 100)}%"></u>' if b['unknown'] else ''}</div>
    <table class="items">
      <thead><tr><th>подпоказатель</th><th>порог</th><th>факт</th><th>баллы</th></tr></thead>
      <tbody>
{chr(10).join(item_row(it, b['id']) for it in b['items'])}
      </tbody>
    </table>
  </section>'''


waiting = [(b, it) for b in CURRENT['blocks'] for it in b['items']
           if it['status'] == 'unknown']
losing = [(b, it) for b in CURRENT['blocks'] for it in b['items']
          if it['status'] == 'fail']

HTML = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Показатели цифровой трансформации — {E(CURRENT['name'])}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Exo+2:wght@300;400;500;600;700&display=swap');
  :root {{
    --bg:#06060f; --bg2:#0d0d1e; --card:rgba(255,255,255,.04);
    --card-border:rgba(255,255,255,.08);
    --accent:#00e5ff; --accent2:#b44fff; --accent3:#00ff9d;
    --warn:#ffb800; --danger:#ff3b5c;
    --text:#e8eaf6; --dim:rgba(232,234,246,.72); --faint:rgba(232,234,246,.42);
  }}
  * {{ margin:0; padding:0; box-sizing:border-box }}
  body {{ font-family:'Exo 2',sans-serif; background:var(--bg); color:var(--text);
          padding:48px 24px 80px; line-height:1.5 }}
  .wrap {{ max-width:1180px; margin:0 auto }}

  /* ШАПКА. Заголовок по центру, цифры — Orbitron (в нём только латиница и цифры,
     кириллицу им набирать нельзя: тихо подменится системным шрифтом). */
  .head {{ text-align:center; margin-bottom:36px }}
  .head .eyebrow {{ font-family:'Orbitron',sans-serif; font-size:11px; font-weight:700;
                    letter-spacing:4px; text-transform:uppercase; color:var(--accent);
                    margin-bottom:14px }}
  h1 {{ font-size:36px; font-weight:700; letter-spacing:-.02em; margin-bottom:10px }}
  .head .meta {{ font-size:13px; color:var(--faint) }}

  /* Балл квартала: главное число страницы. */
  .score {{ display:flex; align-items:center; justify-content:center; gap:44px;
            flex-wrap:wrap; padding:28px 24px; margin-bottom:14px;
            background:var(--card); border:1px solid var(--card-border);
            border-radius:18px }}
  .score .now b {{ font-family:'Orbitron',sans-serif; font-size:64px; font-weight:900;
                   line-height:1; color:var(--accent3);
                   text-shadow:0 0 34px rgba(0,255,157,.35) }}
  .score .now span {{ display:block; font-size:13px; color:var(--dim); margin-top:8px }}
  .score .col b {{ font-family:'Orbitron',sans-serif; font-size:30px; font-weight:700;
                   line-height:1; color:var(--text) }}
  .score .col.ceil b {{ color:var(--warn) }}
  .score .col span {{ display:block; font-size:12.5px; color:var(--faint); margin-top:7px }}
  .dl {{ font-family:'Orbitron',sans-serif; font-size:12px; font-weight:700;
         margin-left:8px }}
  .dl.up {{ color:var(--accent3) }} .dl.down {{ color:var(--danger) }}
  .dl.same {{ color:var(--faint); font-family:'Exo 2',sans-serif; font-weight:500 }}

  .callouts {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:34px }}
  .call {{ background:var(--card); border:1px solid var(--card-border);
           border-left:3px solid var(--ac,var(--warn)); border-radius:14px; padding:18px 20px }}
  .call h3 {{ font-size:14px; font-weight:700; margin-bottom:4px; color:var(--ac,var(--warn)) }}
  .call p {{ font-size:12.5px; color:var(--faint); margin-bottom:12px }}
  .call li {{ list-style:none; font-size:13.5px; padding:7px 0;
              border-top:1px solid var(--card-border) }}
  .call li b {{ font-weight:600 }}
  .call li em {{ font-style:normal; color:var(--faint); font-size:12.5px }}
  .call li u {{ text-decoration:none; float:right; font-family:'Orbitron',sans-serif;
                font-size:12px; color:var(--ac,var(--warn)) }}

  .blk {{ background:var(--card); border:1px solid var(--card-border);
          border-radius:16px; padding:22px 24px; margin-bottom:16px }}
  .blk.full {{ border-color:rgba(0,255,157,.28) }}
  .blk.wait {{ border-color:rgba(255,184,0,.28) }}
  .blk-h {{ display:flex; justify-content:space-between; align-items:flex-start;
            gap:20px; flex-wrap:wrap; margin-bottom:14px }}
  .blk-h h2 {{ font-size:19px; font-weight:700; letter-spacing:-.01em }}
  .blk-src {{ font-size:12px; color:var(--faint); margin-top:3px }}
  .blk-sc {{ text-align:right; white-space:nowrap }}
  .blk-sc b {{ font-family:'Orbitron',sans-serif; font-size:30px; font-weight:900;
               color:var(--accent) }}
  .blk-sc span {{ font-size:13px; color:var(--faint); margin-left:5px }}
  .blk-ceil, .blk-prev {{ display:block; font-style:normal; font-size:12px;
                          color:var(--faint); margin-top:4px }}
  .blk-ceil {{ color:var(--warn) }}

  .bar {{ position:relative; height:6px; border-radius:4px; background:rgba(255,255,255,.07);
          overflow:hidden; margin-bottom:16px }}
  .bar i {{ position:absolute; left:0; top:0; bottom:0; background:var(--accent3) }}
  .bar u {{ position:absolute; right:0; top:0; bottom:0; background:rgba(255,184,0,.45) }}

  table.items {{ width:100%; border-collapse:collapse; font-size:14px }}
  table.items th {{ font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
                    color:var(--faint); text-align:left; font-weight:600;
                    padding:0 12px 8px 0 }}
  table.items td {{ padding:10px 12px 10px 0; border-top:1px solid var(--card-border);
                    vertical-align:top }}
  tr.i-unknown td {{ background:rgba(255,184,0,.05) }}
  tr.i-fail td {{ background:rgba(255,59,92,.06) }}
  .i-name {{ font-weight:600; max-width:38ch }}
  .i-name em.i-note {{ display:block; font-style:normal; font-size:12px;
                       color:var(--faint); margin-top:3px }}
  em.live {{ font-style:normal; font-size:9.5px; letter-spacing:.08em; text-transform:uppercase;
             color:var(--accent); border:1px solid rgba(0,229,255,.4); border-radius:4px;
             padding:1px 5px; margin-left:7px; vertical-align:middle }}
  .i-rule {{ font-size:13px; color:var(--faint); white-space:nowrap }}
  .i-val {{ max-width:44ch }}
  .v.ok {{ color:var(--accent3) }} .v.bad {{ color:var(--danger) }}
  .v.wait {{ color:var(--warn) }}
  .i-pts {{ text-align:right; white-space:nowrap }}
  .pts {{ font-family:'Orbitron',sans-serif; font-size:14px; font-weight:700 }}
  .pts.ok {{ color:var(--accent3) }} .pts.bad {{ color:var(--danger) }}
  .pts.wait {{ color:var(--warn) }}

  @media (max-width:860px) {{
    .callouts {{ grid-template-columns:1fr }}
    table.items .i-rule {{ display:none }}
  }}
</style>
</head>
<body>
<div class="wrap">

  <div class="head">
    <div class="eyebrow">рейтинг ЦИО · {E(score.FACTS.get('owner', ''))}</div>
    <h1>Показатели цифровой трансформации</h1>
    <p class="meta">{E(CURRENT['name'])} · {len(CURRENT['blocks'])} блоков,
      {sum(len(b['items']) for b in CURRENT['blocks'])} подпоказателей, 100 баллов ·
      опрос владельца 17.08.2026</p>
  </div>

  <div class="score">
    <div class="now"><b>{CURRENT['earned']}</b><span>баллов на сегодня</span></div>
    <div class="col ceil"><b>{CEILING}</b><span>потолок, когда придут данные</span></div>
    <div class="col"><b>{PREV['total_fixed']}</b><span>2 квартал (карточка)
      {delta(CEILING, PREV['total_fixed'])}</span></div>
    <div class="col"><b>{FIRST['total_fixed']}</b><span>1 квартал (карточка)</span></div>
  </div>

  <div class="callouts">
    <div class="call" style="--ac:var(--warn)">
      <h3>Ждём данных — {len(waiting)}</h3>
      <p>показатели не провалены, значение ещё не пришло: {CURRENT['unknown']} баллов в подвешенном состоянии</p>
      <ul>
{chr(10).join(f"""        <li><b>{E(it['name'])}</b><u>−{it['points']}</u>
          <em>{E(NOTES.get(it['id']) or b['name'])}</em></li>""" for b, it in waiting)}
      </ul>
    </div>
    <div class="call" style="--ac:var(--danger)">
      <h3>Теряем баллы — {len(losing)}</h3>
      <p>пороги не взяты, и это уже факт квартала</p>
      <ul>
{chr(10).join(f"""        <li><b>{E(it['name'])}</b><u>−{it['points'] - (it['got'] or 0)}</u>
          <em>{E(NOTES.get(it['id']) or it['why'])}</em></li>""" for b, it in losing)}
      </ul>
    </div>
  </div>

{chr(10).join(block_card(b) for b in CURRENT['blocks'])}

</div>
</body>
</html>
'''

OUT.write_text(HTML, encoding='utf-8')
print(f'✓ {OUT.relative_to(HERE.parent)} — {CURRENT["name"]}: '
      f'{CURRENT["earned"]} баллов, потолок {CEILING}')
print(f'  ждём данных: {len(waiting)} · теряем: {len(losing)} · '
      f'живые числа: {", ".join(CURRENT["live_used"]) or "нет"}')
