#!/usr/bin/env python3
"""
report_reminder.py — напоминание о несданных еженедельных отчётах.

По средам в 12:00 МСК присылает владельцу список проектов, по которым отчёт
ещё не пришёл. Если сдали все — молчит.

Запускается LaunchAgent'ом `com.vz.transformation-report-reminder` дважды
(в 04:00 и 05:00 по времени машины) — а нужный ли сейчас час, решает сам
скрипт, сверяясь с московским временем. Причина: машина стоит в
America/New_York и переходит на зимнее время, а Москва — нет; жёстко
прописанный в plist час уехал бы на неделю раньше срока.

    python3 report_reminder.py            # штатно: сработает только в среду 12:00 МСК
    python3 report_reminder.py --now      # прислать сейчас, без проверки времени
    python3 report_reminder.py --dry-run  # показать текст, ничего не отправляя
"""
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
INBOX_PY = HERE / 'report_inbox.py'
TG = Path.home() / 'Projects' / 'LIFE' / 'bin' / 'tg.py'

MSK = ZoneInfo('Europe/Moscow')
REPORT_WEEKDAY = 2      # среда (понедельник = 0)
REPORT_HOUR = 12        # 12:00 МСК


def is_reminder_time(now=None) -> bool:
    now = now or datetime.now(MSK)
    return now.weekday() == REPORT_WEEKDAY and now.hour == REPORT_HOUR


def pending() -> dict:
    """Список несдавших от report_inbox.py."""
    proc = subprocess.run(
        [sys.executable, str(INBOX_PY), '--json', 'pending'],
        capture_output=True, text=True, cwd=str(HERE), timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout)[-300:])
    import json
    return json.loads(proc.stdout.strip().splitlines()[-1])


def build_message(data: dict, now=None) -> str:
    now = now or datetime.now(MSK)
    items = data.get('pending', [])
    total = data.get('total', 0)
    done = data.get('done_count', 0)
    head = (f'⏰ Отчёты за неделю · {now:%d.%m} {now:%H:%M} МСК\n\n'
            f'📊 Сдано {done} из {total}, ждём {len(items)}:')
    body = '\n'.join(f"   • {p['name']} — {p.get('owner') or '—'}" for p in items)
    tail = ('\n\nПерешлите отчёты боту — я разложу их сам.\n'
            '«/report собрать» — собрать сводки без опоздавших.')
    return f'{head}\n{body}{tail}'


def send(text: str) -> None:
    subprocess.run([sys.executable, str(TG), text], check=True, timeout=60)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--now', action='store_true', help='не проверять день и час')
    ap.add_argument('--dry-run', action='store_true', help='показать, не отправляя')
    args = ap.parse_args()

    if not args.now and not is_reminder_time():
        return          # не наш час — молча выходим, это штатный исход

    try:
        data = pending()
    except (RuntimeError, OSError, ValueError) as exc:
        msg = f'⚠️ Напоминание об отчётах не собралось: {exc}'
        print(msg)
        if not args.dry_run:
            send(msg)
        return

    if not data.get('pending'):
        print('сдали все — напоминание не нужно')
        return

    text = build_message(data)
    if args.dry_run:
        print(text)
        return
    send(text)
    print(f"напоминание отправлено: ждём {len(data['pending'])}")


if __name__ == '__main__':
    main()
