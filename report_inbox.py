#!/usr/bin/env python3
"""
report_inbox.py — накопитель еженедельных отчётов по проектам.

Отчёты приходят владельцу в мессенджер блоками (по одному проекту или пачкой)
в том же виде, в каком потом лежат в `ОТЧЕТ_ДД.ММ.md`. Раньше он собирал файл
руками; здесь блоки складываются по мере поступления, а когда сдали все активные
проекты — отчёт собирается сам и уходит в `process_report.py`.

Разбор блоков делает `process_report.parse_report` — тот же парсер, что читает
готовые отчёты: формат совпадает, включая шапку «ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ» и строки-
разделители направлений (они распознаются как заголовки групп и в накопитель
не попадают).

Использование:
    python3 report_inbox.py add ФАЙЛ            # принять текст (сообщение из чата)
    python3 report_inbox.py add --stdin         # то же, текст со стандартного ввода
    python3 report_inbox.py status              # кто сдал, кого ждём
    python3 report_inbox.py pending             # только несдавшие (для напоминания)
    python3 report_inbox.py build               # собрать ОТЧЕТ_ДД.ММ.md и сводки
    python3 report_inbox.py build --force       # собрать, даже если сдали не все
    python3 report_inbox.py reset               # закрыть цикл, начать новый

Ключи `--json` у `add`/`status`/`pending`/`build` дают машинный вывод — им
пользуется телеграм-бот.
"""
import os
import re
import sys
import json
import shutil
import argparse
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from difflib import SequenceMatcher

from config import CLOSED_STATUSES
from process_report import parse_report, find_in_data

# Даты — по рабочей зоне владельца: машина стоит в America/New_York, и при сборке
# ночью по МСК имя отчёта уехало бы на вчера. Тот же пояс у watch_pipeline.sh.
MSK = ZoneInfo('Europe/Moscow')
CYCLE_MAX_DAYS = 6          # старше — это прошлая неделя, цикл пора закрывать
NAME_MISMATCH_RATIO = 0.5   # ниже — присланное имя не похоже на проект по ссылке

HERE = Path(__file__).resolve().parent
INBOX = HERE / 'report_inbox'          # накопитель; в git не идёт
CURRENT = INBOX / 'current'            # блоки текущего цикла
META = CURRENT / '_meta.json'          # когда и что принято
RAW = CURRENT / '_raw'                 # присланное как есть — страховка от потери
PREV = CURRENT / '_prev'               # прошлая версия блока перед перезаписью


# ─────────────────────────── хранилище цикла ───────────────────────────

def now_msk() -> datetime:
    return datetime.now(MSK)


def today_msk() -> date:
    return now_msk().date()


def load_meta() -> dict:
    """Метаданные цикла: когда открыт, что принято, по каким проектам."""
    try:
        return json.loads(META.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {'opened_at': now_msk().isoformat(timespec='seconds'),
                'items': {}}


def save_meta(meta: dict) -> None:
    CURRENT.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                    encoding='utf-8')


def block_path(key: str) -> Path:
    """Файл блока. Ключ — issue_id, иначе нормализованное имя."""
    safe = re.sub(r'[^\w\-]+', '_', key, flags=re.UNICODE).strip('_')
    return CURRENT / f'{safe}.md'


def cycle_age_days() -> float | None:
    """Возраст открытого цикла в днях."""
    try:
        opened = datetime.fromisoformat(load_meta()['opened_at'])
    except (KeyError, ValueError):
        return None
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=MSK)
    return (now_msk() - opened).total_seconds() / 86400


def rotate_if_stale() -> bool:
    """Цикл старше недели закрывается сам.

    Иначе блоки прошлой недели доживают до следующей и уезжают в свежий отчёт
    как актуальные: достаточно один раз собрать сводки «без опоздавших»
    (при этом цикл намеренно остаётся открытым), и через неделю первый же
    новый отчёт добирает старьё до полноты.
    """
    if not CURRENT.exists() or not META.exists():
        return False
    age = cycle_age_days()
    if age is None or age < CYCLE_MAX_DAYS:
        return False
    reset()
    return True


# ─────────────────────────── ожидаемые проекты ──────────────────────────

def active_projects(data_path='data.json') -> list:
    """Активные проекты из data.json — те, с кого ждём отчёт."""
    data = json.loads(Path(data_path).read_text(encoding='utf-8'))
    return [p for p in data.get('projects', [])
            if p.get('status') not in CLOSED_STATUSES]


def render_block(proj: dict, dp: dict | None = None) -> str:
    """Собирает блок обратно в текст отчёта — как его пишет владелец.

    Название берётся из `data.json` (проект уже опознан по ссылке), а не из
    сообщения: присылают вразнобой — где капсом, где своей формулировкой, —
    а сводка уходит руководству. Приоритет тоже из данных, а не из эмодзи.
    """
    if dp is not None:
        name = dp.get('name') or proj['name']
        priority = dp.get('is_priority')
    else:
        name, priority = proj['name'], proj.get('priority')
    emoji = '🔴' if priority else '🔵'
    out = [f"{emoji} {name}"]
    if proj.get('person'):
        out.append(f"👤 {proj['person']}")
    if proj.get('url'):
        out.append(f"🔗 {proj['url']}")
    if proj.get('completed'):
        out.append('')
        out.append('✅ Выполнено:')
        out.append(proj['completed'])
    if proj.get('current'):
        out.append('')
        out.append('📍 Текущие этапы (в работе):')
        out.append(proj['current'])
    if proj.get('note'):
        out.append('')
        out.append(f"ℹ️ {proj['note']}")
    return '\n'.join(out)


# ──────────────────────────────── приём ─────────────────────────────────

def add_text(text: str, data_path='data.json') -> dict:
    """Разбирает присланный текст и раскладывает блоки по проектам.

    Возвращает сводку: что принято, что заменено, что не удалось опознать.
    """
    rotated = rotate_if_stale()
    CURRENT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(exist_ok=True)

    # Присланное сохраняем ДО разбора и целиком: отчёт живёт только в чате,
    # и всё, что разбор не понял (строки вне секций, хвост сообщения, разрезанного
    # Telegram по длине), иначе исчезло бы бесследно.
    raw_name = f"{now_msk():%Y-%m-%d_%H%M%S}.md"
    (RAW / raw_name).write_text(text, encoding='utf-8')

    tmp = CURRENT / '_incoming.md'
    tmp.write_text(text, encoding='utf-8')
    try:
        groups = parse_report(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)

    active = active_projects(data_path)
    meta = load_meta()
    accepted, replaced, unknown, warnings = [], [], [], []

    for group in groups:
        for proj in group['projects']:
            # пустышка: заголовок без тела — не отчёт
            if not (proj.get('completed') or proj.get('current')):
                continue
            # по ссылке — точно, по имени — нечётко (difflib): второе стоит показать
            dp, how = find_in_data(proj.get('issue_id'), proj.get('name'), active)
            if dp is None:
                unknown.append(proj.get('name'))
                continue
            key = str(dp.get('id'))
            # Ссылку могли скопировать не ту: имя из сообщения и имя проекта
            # разошлись — молча затирать чужой блок нельзя.
            if how == 'id' and proj.get('name'):
                ratio = SequenceMatcher(None, proj['name'].lower(),
                                        (dp.get('name') or '').lower()).ratio()
                if ratio < NAME_MISMATCH_RATIO:
                    warnings.append({'kind': 'name_mismatch',
                                     'as_sent': proj['name'],
                                     'name': dp.get('name'), 'id': key})
            path = block_path(key)
            was = path.exists()
            if was:
                # прежняя версия — на случай, если досылка окажется беднее
                PREV.mkdir(exist_ok=True)
                shutil.copy(path, PREV / f'{key}.md')
                old_text = path.read_text(encoding='utf-8')
                for mark, label in (('✅ Выполнено', 'Выполнено'),
                                    ('📍 Текущие этапы', 'Текущие этапы')):
                    if mark in old_text and not proj.get(
                            'completed' if 'Выполнено' in mark else 'current'):
                        warnings.append({'kind': 'section_lost', 'section': label,
                                         'name': dp.get('name'), 'id': key})
            path.write_text(render_block(proj, dp), encoding='utf-8')
            meta['items'][key] = {
                'name': dp.get('name'),
                'received_at': now_msk().isoformat(timespec='seconds'),
                'as_sent_name': proj.get('name'),
                'matched_by': how,
            }
            entry = {'name': dp.get('name'), 'matched_by': how,
                     'as_sent': proj.get('name')}
            (replaced if was else accepted).append(entry)

    save_meta(meta)
    done = done_active(meta, active)
    return {
        'accepted': accepted,
        'replaced': replaced,
        'unknown': unknown,
        'done_count': len(done),
        'total': len(active),
        'pending': [p['name'] for p in active if str(p.get('id')) not in done],
        'complete': len(done) >= len(active),
        'cycle_rotated': rotated,
        'warnings': warnings,
        'raw': raw_name,
    }


# ─────────────────────────────── статус ─────────────────────────────────

def done_active(meta: dict, active: list) -> set:
    """Сдавшие СРЕДИ ожидаемых.

    В `meta['items']` остаются проекты, закрывшиеся в Redmine за неделю
    (`data.json` обновляется автопрогоном каждое утро). Считая их, `complete`
    срабатывал досрочно: неделя закрывалась, а отчёт собирался без тех, кого
    реально ждали, — вплоть до пустого файла.
    """
    active_ids = {str(p.get('id')) for p in active}
    return {k for k in meta['items'] if k in active_ids}


def status(data_path='data.json') -> dict:
    active = active_projects(data_path)
    meta = load_meta()
    done = done_active(meta, active)
    return {
        'opened_at': meta.get('opened_at'),
        'done': [{'id': str(p.get('id')), 'name': p['name'],
                  'received_at': meta['items'][str(p.get('id'))]['received_at']}
                 for p in active if str(p.get('id')) in done],
        'pending': [{'id': str(p.get('id')), 'name': p['name'],
                     'owner': p.get('owner_short')}
                    for p in active if str(p.get('id')) not in done],
        'total': len(active),
        'complete': len(done) >= len(active),
    }


# ─────────────────────────────── сборка ─────────────────────────────────

def report_filename(today=None) -> str:
    today = today or today_msk()
    return f'ОТЧЕТ_{today:%d.%m}.md'


def find_prev_report(exclude: str) -> str | None:
    """Предыдущий отчёт для diff — свежайший по времени файла.

    По дате в имени сортировать нельзя: года в нём нет, и в январе
    `ОТЧЕТ_30.12.md` оказывался «свежее» январских — diff `🆕` в сводках
    руководству стал бы бессмысленным.
    """
    candidates = [p for p in
                  list(HERE.glob('ОТЧЕТ_*.md'))
                  + list((HERE / 'archive' / 'reports').glob('ОТЧЕТ_*.md'))
                  if p.name != exclude
                  and re.match(r'ОТЧЕТ_\d{2}\.\d{2}\.md$', p.name)]
    if not candidates:
        return None
    return str(max(candidates, key=lambda p: p.stat().st_mtime))


def build(data_path='data.json', force=False, run_process=True) -> dict:
    """Собирает ОТЧЕТ_ДД.ММ.md из накопленного и прогоняет process_report.py."""
    st = status(data_path)
    if not st['complete'] and not force:
        return {'ok': False, 'reason': 'не все сдали', **st}

    active = active_projects(data_path)
    meta = load_meta()
    priority, transform = [], []
    for p in active:
        key = str(p.get('id'))
        if key not in meta['items'] or not block_path(key).exists():
            continue
        text = block_path(key).read_text(encoding='utf-8')
        (priority if p.get('is_priority') else transform).append(text)

    out = ['ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ ПО ПРОЕКТАМ', f'📅 {today_msk():%d.%m.%Y}', '']
    if priority:
        out += ['🔴 ПРИОРИТЕТНЫЕ ПРОЕКТЫ', '']
        out += ['\n\n'.join(priority), '']
    if transform:
        out += ['🔵 ПРОЕКТЫ ТРАНСФОРМАЦИИ', '']
        out += ['\n\n'.join(transform), '']

    name = report_filename()
    path = HERE / name
    path.write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')

    result = {'ok': True, 'report': str(path), 'blocks': len(priority) + len(transform),
              'missing': [p['name'] for p in st['pending']], **st}

    if run_process:
        prev = find_prev_report(exclude=name)
        cmd = [sys.executable, str(HERE / 'process_report.py'), str(path)]
        if prev:
            cmd += ['--prev', prev]
            result['prev'] = prev
        proc = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True)
        result['process_rc'] = proc.returncode
        result['process_out'] = (proc.stdout + proc.stderr)[-2000:]
        if proc.returncode == 0:
            stamp = f'{today_msk():%d_%m_%Y}'
            for kind in ('priority', 'transform'):
                f = HERE / f'telegram_{kind}_{stamp}.txt'
                if f.exists():
                    result[f'{kind}_file'] = str(f)
    return result


def reset() -> dict:
    """Закрывает цикл: накопленное уезжает в архив под датой."""
    if not CURRENT.exists():
        return {'archived': None}
    dest = INBOX / f'{today_msk():%Y-%m-%d}'
    if dest.exists():
        dest = INBOX / f'{today_msk():%Y-%m-%d}_{now_msk():%H%M}'
    shutil.move(str(CURRENT), str(dest))
    return {'archived': str(dest)}


# ──────────────────────────────── CLI ───────────────────────────────────

def _print(obj, as_json: bool, human) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False))
    else:
        human(obj)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', default=str(HERE / 'data.json'))
    ap.add_argument('--json', action='store_true', help='машинный вывод')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_add = sub.add_parser('add', help='принять текст отчёта')
    p_add.add_argument('file', nargs='?', help='файл с текстом сообщения')
    p_add.add_argument('--stdin', action='store_true', help='читать со stdin')

    sub.add_parser('status', help='кто сдал, кого ждём')
    sub.add_parser('pending', help='только несдавшие')

    p_build = sub.add_parser('build', help='собрать отчёт и сводки')
    p_build.add_argument('--force', action='store_true', help='даже если сдали не все')
    p_build.add_argument('--no-process', action='store_true',
                         help='только собрать md, не запускать process_report.py')

    sub.add_parser('reset', help='закрыть цикл')
    args = ap.parse_args()

    if args.cmd == 'add':
        if args.stdin or not args.file:
            text = sys.stdin.read()
        else:
            text = Path(args.file).read_text(encoding='utf-8')
        if not text.strip():
            ap.error('пустой текст')
        res = add_text(text, args.data)

        def human(r):
            def mark(e):
                # совпадение по имени могло промахнуться — показываем, как поняли
                return (f"{e['name']}  (по названию «{e['as_sent']}»)"
                        if e['matched_by'] == 'name' else e['name'])
            for e in r['accepted']:
                print(f'✅ принято: {mark(e)}')
            for e in r['replaced']:
                print(f'♻️  обновлено: {mark(e)}')
            for n in r['unknown']:
                print(f'❓ не опознан проект: {n}')
            for w in r.get('warnings', []):
                if w['kind'] == 'name_mismatch':
                    print(f"⚠️  ссылка ведёт на «{w['name']}», а в тексте "
                          f"«{w['as_sent']}» — проверьте, тот ли проект")
                else:
                    print(f"⚠️  в новом блоке «{w['name']}» нет раздела "
                          f"«{w['section']}» — прежний перезаписан "
                          f"(копия в report_inbox/current/_prev/{w['id']}.md)")
            if r.get('cycle_rotated'):
                print('📦 прошлая неделя была не закрыта — убрал её в архив')
            print(f"📊 сдано {r['done_count']} из {r['total']}")
            if r['complete']:
                print('🎉 сдали все — можно собирать')
        _print(res, args.json, human)

    elif args.cmd == 'status':
        res = status(args.data)

        def human(r):
            print(f"📊 сдано {len(r['done'])} из {r['total']}")
            for d in r['done']:
                print(f"   ✅ {d['name']}")
            for p in r['pending']:
                print(f"   ⏳ {p['name']} — {p.get('owner') or '—'}")
        _print(res, args.json, human)

    elif args.cmd == 'pending':
        res = status(args.data)
        out = {'pending': res['pending'], 'total': res['total'],
               'done_count': len(res['done'])}

        def human(r):
            if not r['pending']:
                print('✅ сдали все')
                return
            print(f"⏳ не сдали {len(r['pending'])} из {r['total']}:")
            for p in r['pending']:
                print(f"   • {p['name']} — {p.get('owner') or '—'}")
        _print(out, args.json, human)

    elif args.cmd == 'build':
        res = build(args.data, force=args.force, run_process=not args.no_process)

        def human(r):
            if not r.get('ok'):
                print(f"⏸  {r['reason']}: сдано {len(r['done'])} из {r['total']}")
                return
            print(f"📝 собран {r['report']} ({r['blocks']} блоков)")
            if r.get('missing'):
                print(f"   без отчёта: {', '.join(r['missing'])}")
            if r.get('priority_file'):
                print(f"   🔴 {r['priority_file']}")
            if r.get('transform_file'):
                print(f"   🔵 {r['transform_file']}")
        _print(res, args.json, human)

    elif args.cmd == 'reset':
        res = reset()
        _print(res, args.json,
               lambda r: print(f"📦 цикл закрыт: {r['archived'] or 'нечего архивировать'}"))


if __name__ == '__main__':
    main()
