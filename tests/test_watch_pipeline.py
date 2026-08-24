"""Тесты автопрогона `watch_pipeline.sh`.

Скрипт запускается без человека и заканчивается коммитом и пушем в публичные
репозитории, поэтому проверяются прежде всего сценарии, в которых он может
навредить: бесконечный повтор упавшего прогона, затирание сегодняшнего снимка
посторонним файлом, публикация старой выгрузки под видом свежей и молчаливая
отбраковка (владелец читает тишину как «всё прошло»).

Настоящие `deploy.sh`, `tg.py` и `osascript` подменены заглушками — прогон
идёт целиком во временном каталоге и наружу ничего не отправляет.
"""
import os
import json
import time
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.fixtures import build_fixtures

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'watch_pipeline.sh'

DEPLOY_OK = '#!/bin/bash\necho "✅ Деплой завершён"\n'
DEPLOY_FAIL = '#!/bin/bash\necho "❌ data.json не парсится" >&2\nexit 3\n'


def make_sandbox(tmp_path, deploy=DEPLOY_OK):
    """Разворачивает изолированную копию проекта: скрипт с подменёнными путями,
    заглушки внешних вызовов, `data.json` и модули для проверки колонок."""
    src = SCRIPT.read_text()
    src = src.replace(
        'PROJECT_DIR="/Users/valeriy/Projects/transformation"',
        f'PROJECT_DIR="{tmp_path}"')
    src = src.replace(
        'TG="/Users/valeriy/Projects/LIFE/bin/tg.py"',
        f'TG="{tmp_path}/tg.py"')
    # свой bin впереди — перехватываем osascript, чтобы всплывашки не летели наружу
    src = src.replace('export PATH="', f'export PATH="{tmp_path}/bin:')
    script = tmp_path / 'wp.sh'
    script.write_text(src)
    script.chmod(0o755)

    (tmp_path / 'bin').mkdir()
    stub_osascript = tmp_path / 'bin' / 'osascript'
    stub_osascript.write_text('#!/bin/bash\nexit 0\n')
    stub_osascript.chmod(0o755)

    deploy_sh = tmp_path / 'deploy.sh'
    deploy_sh.write_text(deploy)
    deploy_sh.chmod(0o755)

    # каждое сообщение — отдельной строкой, чтобы считать их количество
    (tmp_path / 'tg.py').write_text(
        'import sys, json, pathlib\n'
        'p = pathlib.Path("tg-sent.jsonl")\n'
        'with p.open("a") as f:\n'
        '    f.write(json.dumps(sys.argv[1], ensure_ascii=False) + "\\n")\n')
    (tmp_path / 'upcoming_report.py').write_text(
        'print("✅ Справка: 0 задач в 0 проектах")\n')

    # нужны проверке колонок (python-вставка в скрипте импортирует extract_data)
    for mod in ('extract_data.py', 'config.py'):
        shutil.copy(ROOT / mod, tmp_path / mod)
    (tmp_path / 'data.json').write_text(json.dumps(
        {'summary': {'projects_total': 1, 'projects_active': 1,
                     'tasks_total': 2, 'tasks_active': 1,
                     'tasks_overdue': 0, 'tasks_today': 0,
                     'vysv_pct_total': 100}}, ensure_ascii=False))
    return script


def run(script, *args):
    return subprocess.run([str(script), *args], capture_output=True, text=True,
                          cwd=str(script.parent))


def messages(tmp_path):
    """Сообщения, ушедшие в Telegram за все прогоны."""
    f = tmp_path / 'tg-sent.jsonl'
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text().splitlines() if line.strip()]


def redmine_xlsx(tmp_path, name, broken=False):
    """Кладёт в песочницу выгрузку под нужным именем."""
    staging = tmp_path / f'_staging_{name}'
    staging.mkdir()
    redmine, _, _ = build_fixtures(staging, broken=broken)
    target = tmp_path / name
    shutil.move(str(redmine), str(target))
    shutil.rmtree(staging)
    return target


def today_name():
    return time.strftime('%d.%m', time.localtime())


# ─────────────────────────── базовый сценарий ───────────────────────────

def test_renames_to_today_and_runs(tmp_path):
    """Выгрузка с «как скачалось» именем переименовывается в сегодняшнюю дату."""
    script = make_sandbox(tmp_path)
    redmine_xlsx(tmp_path, 'issues (7).xlsx')

    assert run(script).returncode == 0
    assert (tmp_path / f'issues_{today_name()}.xlsx').exists()
    assert not (tmp_path / 'issues (7).xlsx').exists()
    assert len(messages(tmp_path)) == 1
    assert 'Дашборд обновлён' in messages(tmp_path)[0]


def test_second_wake_does_not_rerun(tmp_path):
    """Повторное пробуждение launchd от собственной записи прогон не запускает."""
    script = make_sandbox(tmp_path)
    redmine_xlsx(tmp_path, 'issues.xlsx')

    run(script)
    run(script)
    assert len(messages(tmp_path)) == 1


# ───────────────── сценарии, найденные независимым ревью ─────────────────

def test_failed_deploy_is_not_repeated(tmp_path):
    """Упавший прогон не повторяется сам: отпечаток пишется до работы.

    Иначе launchd (около шести пробуждений в минуту) гонял бы полный цикл
    коммит-пуш-сообщение по кругу, пока владелец не вмешается.
    """
    script = make_sandbox(tmp_path, deploy=DEPLOY_FAIL)
    redmine_xlsx(tmp_path, 'issues.xlsx')

    assert run(script).returncode == 3
    run(script)
    run(script)

    msgs = messages(tmp_path)
    assert len(msgs) == 1, 'сообщение об ошибке повторилось на каждое пробуждение'
    assert 'упал' in msgs[0]
    assert '--force' in msgs[0], 'в сообщении нет способа повторить прогон'


def test_foreign_file_does_not_clobber_snapshot(tmp_path):
    """Файл на «issues*», не являющийся выгрузкой, не затирает снимок дня.

    Выгрузки в git не хранятся: затёртый `mv -f` снимок восстановить неоткуда.
    """
    script = make_sandbox(tmp_path)
    snapshot = tmp_path / f'issues_{today_name()}.xlsx'
    redmine_xlsx(tmp_path, snapshot.name)
    original = snapshot.read_bytes()

    time.sleep(1)
    redmine_xlsx(tmp_path, 'issues расшифровка ЦТ.xlsx', broken=True)

    run(script)
    assert snapshot.read_bytes() == original, 'сегодняшняя выгрузка затёрта'
    assert (tmp_path / 'issues расшифровка ЦТ.xlsx').exists(), 'чужой файл тронут'
    msgs = messages(tmp_path)
    assert len(msgs) == 1 and 'не взят в работу' in msgs[0]


def test_old_snapshot_is_not_published(tmp_path):
    """Старый снимок, возвращённый в корень, не уходит в публикацию.

    `cp archive/issues/issues_10.06.xlsx .` даёт свежий mtime, и без проверки
    даты в имени июньские данные уехали бы на дашборд как сегодняшние.
    """
    script = make_sandbox(tmp_path)
    redmine_xlsx(tmp_path, 'issues_10.06.xlsx')     # mtime = сейчас

    assert run(script).returncode == 0
    assert (tmp_path / 'issues_10.06.xlsx').exists(), 'старый снимок переименован'
    assert not (tmp_path / f'issues_{today_name()}.xlsx').exists()
    msgs = messages(tmp_path)
    assert len(msgs) == 1 and 'пропущена' in msgs[0]
    assert '--force' in msgs[0]


def test_stale_file_is_reported_not_silently_dropped(tmp_path):
    """Отбракованный по дате файл не пропадает молча.

    Скачан вечером, перенесён в папку утром — mtime остаётся вчерашним.
    Тишина в Telegram владельцем читается как «всё прошло».
    """
    script = make_sandbox(tmp_path)
    stale = redmine_xlsx(tmp_path, 'issues (3).xlsx')
    yesterday = time.time() - 36 * 3600
    os.utime(stale, (yesterday, yesterday))

    assert run(script).returncode == 0
    msgs = messages(tmp_path)
    assert len(msgs) == 1, 'об отбраковке не сообщено'
    assert 'пропущена' in msgs[0] and '--force' in msgs[0]

    run(script)   # повторное пробуждение не должно спамить
    assert len(messages(tmp_path)) == 1


def test_force_takes_stale_file(tmp_path):
    """`--force` — осознанный обход отбраковки по дате."""
    script = make_sandbox(tmp_path)
    stale = redmine_xlsx(tmp_path, 'issues (3).xlsx')
    yesterday = time.time() - 36 * 3600
    os.utime(stale, (yesterday, yesterday))

    assert run(script, '--force').returncode == 0
    assert (tmp_path / f'issues_{today_name()}.xlsx').exists()


# ─────────────────────────────── замок ───────────────────────────────

def test_lock_of_live_process_holds(tmp_path):
    """Замок живого прогона не снимается по возрасту: долгий push — не смерть."""
    script = make_sandbox(tmp_path)
    redmine_xlsx(tmp_path, 'issues.xlsx')

    lock = tmp_path / 'logs' / '.lock'
    lock.mkdir(parents=True)
    (lock / 'pid').write_text(str(os.getpid()))     # заведомо живой процесс
    old = time.time() - 3600
    os.utime(lock, (old, old))

    assert run(script).returncode == 0
    assert messages(tmp_path) == [], 'прогон пошёл поверх живого замка'


def test_lock_of_dead_process_is_removed(tmp_path):
    """Замок умершего процесса снимается, работа продолжается."""
    script = make_sandbox(tmp_path)
    redmine_xlsx(tmp_path, 'issues.xlsx')

    dead = subprocess.run(['/bin/echo'], capture_output=True)   # заведомо мёртвый pid
    lock = tmp_path / 'logs' / '.lock'
    lock.mkdir(parents=True)
    (lock / 'pid').write_text(str(dead.returncode + 999_000))

    assert run(script).returncode == 0
    assert len(messages(tmp_path)) == 1


@pytest.mark.parametrize('flag', ['--dry-run'])
def test_dry_run_changes_nothing(tmp_path, flag):
    """Сухой прогон не переименовывает файл и ничего не отправляет."""
    script = make_sandbox(tmp_path)
    redmine_xlsx(tmp_path, 'issues (9).xlsx')

    assert run(script, flag).returncode == 0
    assert (tmp_path / 'issues (9).xlsx').exists()
    assert not (tmp_path / f'issues_{today_name()}.xlsx').exists()
    assert messages(tmp_path) == []


# ────────── дефекты, внесённые самими исправлениями (круг 2) ──────────

def test_unavailable_lock_dir_does_not_spin(tmp_path):
    """Недоступный `logs/` завершает прогон, а не крутит его вечно.

    Метка агента одна: зациклившийся экземпляр занял бы её навсегда,
    launchd не поднял бы второй, и автопрогон встал бы молча.
    """
    script = make_sandbox(tmp_path)
    redmine_xlsx(tmp_path, 'issues.xlsx')
    logs = tmp_path / 'logs'
    logs.mkdir()
    logs.chmod(0o500)                      # каталог есть, записать в него нельзя
    try:
        r = subprocess.run([str(script)], capture_output=True, text=True,
                           cwd=str(tmp_path), timeout=20)
    finally:
        logs.chmod(0o700)
    assert r.returncode == 1


def test_broken_environment_does_not_consume_upload(tmp_path):
    """Сломанная среда не помечает выгрузку обработанной.

    Проверка колонок падает не потому, что файл чужой (в проекте уже был
    рассинхрон numpy/pandas). Диагноз неизвестен — значит после починки
    выгрузка должна подхватиться сама.
    """
    script = make_sandbox(tmp_path)
    redmine_xlsx(tmp_path, 'issues.xlsx')
    good = (tmp_path / 'extract_data.py').read_text()
    (tmp_path / 'extract_data.py').write_text(
        'raise ImportError("numpy.core.multiarray failed to import")\n')

    assert run(script).returncode == 0
    assert not (tmp_path / f'issues_{today_name()}.xlsx').exists()
    msgs = messages(tmp_path)
    assert len(msgs) == 1 and 'не проверена' in msgs[0]

    run(script)                             # пока среда сломана — не спамим
    assert len(messages(tmp_path)) == 1

    (tmp_path / 'extract_data.py').write_text(good)   # среда починена
    assert run(script).returncode == 0
    assert (tmp_path / f'issues_{today_name()}.xlsx').exists(), \
        'после починки среды выгрузка не подхватилась'
    assert 'Дашборд обновлён' in messages(tmp_path)[-1]


def test_interrupted_run_is_retried(tmp_path):
    """Прогон, убитый сигналом, повторяется, а не считается обработанным.

    launchd шлёт SIGTERM при выходе из системы. Без статуса в отпечатке
    выгрузка выглядела бы обработанной, `data.json` остался бы вчерашним,
    и владелец не получил бы ни одного сообщения.
    """
    script = make_sandbox(tmp_path)
    upload = redmine_xlsx(tmp_path, 'issues.xlsx')
    st = upload.stat()
    fingerprint = f'{int(st.st_mtime)}|{st.st_size}'

    logs = tmp_path / 'logs'
    logs.mkdir()
    # прогон начат и оборван: pid заведомо мёртвый
    (logs / '.processed').write_text(f'started {fingerprint} 999123')

    assert run(script).returncode == 0
    msgs = messages(tmp_path)
    assert len(msgs) == 1
    assert 'оборван' in msgs[0], 'о повторе оборванного прогона не сказано'
    assert (tmp_path / f'issues_{today_name()}.xlsx').exists()


def test_finished_run_is_not_retried(tmp_path):
    """Завершённая попытка (в том числе неудачная) сама не повторяется."""
    script = make_sandbox(tmp_path, deploy=DEPLOY_FAIL)
    upload = redmine_xlsx(tmp_path, 'issues.xlsx')
    st = upload.stat()
    fingerprint = f'{int(st.st_mtime)}|{st.st_size}'

    logs = tmp_path / 'logs'
    logs.mkdir()
    (logs / '.processed').write_text(f'failed {fingerprint} 999123')

    assert run(script).returncode == 0
    assert messages(tmp_path) == []
