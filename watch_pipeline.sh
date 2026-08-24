#!/bin/bash
#
# watch_pipeline.sh — автопрогон пайплайна по появлению свежей выгрузки Redmine.
#
# Владелец кладёт скачанный из Redmine файл (issues.xlsx / «issues (1).xlsx»)
# в корень проекта; LaunchAgent com.vz.transformation-pipeline будит этот скрипт
# на любое изменение папки, а решение «работать или выйти» скрипт принимает сам:
#
#   1. выгрузка переименовывается в issues_ДД.ММ.xlsx по СЕГОДНЯШНЕЙ дате;
#   2. ./deploy.sh — extract_data.py → overdue_report.py → коммит → пуш;
#   3. upcoming_report.py — справка по срокам от сегодня до конца недели (пятница).
#
# Повторный заброс в тот же день проходит весь цикл заново: вечерняя картина
# замещает утреннюю (решение владельца 24.08.2026 — старый файл дня перезаписывается).
#
# Еженедельная telegram-сводка (process_report.py) здесь НЕ запускается:
# она собирается по ОТЧЕТ_ДД.ММ.md, и автопрогон в середине недели собрал бы её
# по прошлонедельному отчёту. Сводку владелец делает отдельно — ./deploy.sh с $2.
#
# Режимы:
#   ./watch_pipeline.sh            — рабочий (так его зовёт launchd)
#   ./watch_pipeline.sh --force    — прогнать, даже если выгрузка уже обработана
#   ./watch_pipeline.sh --dry-run  — показать, что было бы сделано (пишет только в лог)
#
set -uo pipefail

PROJECT_DIR="/Users/valeriy/Projects/transformation"

# launchd даёт голый PATH — python3 и git иначе не находятся
export PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
# Даты — по рабочей зоне владельца: машина стоит в America/New_York, выгрузка
# приходит утром по Москве. Тот же TZ у соседнего агента LIFE/bin/redmine_watch.py,
# иначе имена снимков issues_ДД.ММ.xlsx разъедутся между ними.
export TZ="Europe/Moscow"

cd "$PROJECT_DIR" || exit 1

LOG_DIR="$PROJECT_DIR/logs"
LOG="$LOG_DIR/auto-pipeline.log"
STATE="$LOG_DIR/.processed"      # отпечаток последней взятой в работу выгрузки
SKIPPED="$LOG_DIR/.skipped"      # отпечаток отброшенной — чтобы не повторять сообщение
LOCK="$LOG_DIR/.lock"            # каталог-замок: mkdir атомарен
mkdir -p "$LOG_DIR"

FORCE=0
DRY=0
for arg in "$@"; do
  case "$arg" in
    --force)   FORCE=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "неизвестный аргумент: $arg" >&2; exit 2 ;;
  esac
done

log() {
  printf '%s  %s\n' "$(date '+%d.%m %H:%M:%S')" "$*" >>"$LOG"
  [ "$DRY" -eq 1 ] && printf '%s\n' "$*"
  return 0
}

notify() {  # notify «заголовок» «текст» — всплывашка macOS
  [ "$DRY" -eq 1 ] && return 0
  # текст передаём аргументами: в него попадает имя файла от владельца,
  # а склейка строк выполнила бы кавычку в имени как AppleScript
  osascript - "$1" "$2" >/dev/null 2>&1 <<'APPLESCRIPT'
on run argv
  display notification (item 2 of argv) with title (item 1 of argv)
end run
APPLESCRIPT
  return 0
}

# Telegram — тот же канал, которым шлёт LIFE/bin/redmine_watch.py:
# токен в keychain (vz-telegram-bot), chat_id в shared/telegram/state.json.
TG="/Users/valeriy/Projects/LIFE/bin/tg.py"

tg() {  # tg «текст» — недоставленное сообщение не должно ронять прогон
  if [ "$DRY" -eq 1 ]; then
    printf '\n--- telegram ---\n%s\n----------------\n' "$1"
    return 0
  fi
  if [ ! -f "$TG" ]; then
    log "⚠️  $TG не найден — сообщение не отправлено"
    return 0
  fi
  if ! python3 "$TG" "$1" >>"$LOG" 2>&1; then
    log "⚠️  Telegram не принял сообщение (см. лог выше)"
  fi
  return 0
}

# ── состояние обработки выгрузки ──────────────────────────────────────
# `.processed` хранит «<статус> <отпечаток> <pid>». Статус нужен, чтобы отличить
# завершённую попытку (done/failed — повтор только по --force) от ОБОРВАННОЙ
# (started + мёртвый pid): launchd шлёт SIGTERM при выходе из системы, и без
# статуса убитый на середине прогон выглядел бы обработанным — выгрузка молча
# пропала бы, а `data.json` остался вчерашним.
state_read() {
  local raw rest
  st_status=""; st_fp=""; st_pid=""
  raw=$(cat "$STATE" 2>/dev/null) || return 0
  [ -z "$raw" ] && return 0
  case "$raw" in
    *" "*) st_status=${raw%% *}; rest=${raw#* }; st_fp=${rest%% *}; st_pid=${rest##* } ;;
    *)     st_status="done"; st_fp="$raw" ;;   # формат до 24.08.2026
  esac
}

state_write() {  # state_write <started|done|failed>
  [ "$DRY" -eq 1 ] && return 0
  printf '%s %s %s' "$1" "$fingerprint" "$$" >"$STATE"
}

# Хвост лога для сообщения об ошибке: только строки ТЕКУЩЕГО прогона —
# от последнего маркера «новая выгрузка». Иначе в сообщение затекает
# история прошлых прогонов и разобрать причину нельзя.
log_tail() {
  awk '/─── новая выгрузка/ {buf=""} {buf = buf $0 "\n"} END {printf "%s", buf}' "$LOG" \
    | tail -n 15 | sed 's/^/   /'
}

# Сообщение о падении + всплывашка. Зовётся перед каждым аварийным выходом,
# чтобы «тишина в Telegram» никогда не значила «прогон прошёл».
fail() {  # fail «шаг» «код»
  local step="$1" code="$2"
  # попытка завершена (пусть и неудачно) — иначе следующий прогон примет её
  # за оборванную и повторит, а это тот самый бесконечный цикл
  [ -n "${fingerprint:-}" ] && state_write failed
  notify "Дашборд: ошибка" "$step · код $code"
  tg "$(printf '%s\n\n📄 %s\n🧩 Шаг: %s (код %s)\n\n⌄ хвост лога:\n%s\n\n🔁 Повторить: ./watch_pipeline.sh --force\n📓 Полный лог: logs/auto-pipeline.log' \
        "❌ Автопрогон дашборда упал · $(date '+%d.%m %H:%M')" \
        "${target:-${latest:-выгрузка не определена}}" "$step" "$code" "$(log_tail)")"
}

# ─────────────────────────────── замок ───────────────────────────────
# Прогон длится минуту и сам пишет в папку (data.json, отчёты, справки),
# что снова будит launchd — а будит он часто: замер 24.08 дал ~6 пробуждений
# в минуту. Без замка это наложение прогонов друг на друга.
#
# Замок держит PID: возраст сам по себе о смерти процесса не говорит —
# застрявший на 40 минут `git push` жив, и снимать его замок нельзя.
if [ "$DRY" -eq 0 ]; then
  # Попыток ровно три: `mkdir` может не выполняться и по причине, не связанной
  # с чужим замком (каталог недоступен на запись, кончилось место). Бесконечный
  # цикл в этом случае занял бы метку агента навсегда — launchd не поднимет
  # второй экземпляр, и автопрогон встанет молча.
  locked=0
  for _ in 1 2 3; do
    if mkdir "$LOCK" 2>/dev/null; then
      printf '%s' "$$" >"$LOCK/pid"
      locked=1
      break
    fi
    owner=$(cat "$LOCK/pid" 2>/dev/null)
    if [ -n "$owner" ] && kill -0 "$owner" 2>/dev/null; then
      exit 0   # прогон реально идёт — молча уходим
    fi
    log "⚠️  снимаю замок мёртвого процесса (pid ${owner:-неизвестен})"
    rm -rf "$LOCK" 2>/dev/null
  done
  if [ "$locked" -eq 0 ]; then
    log "❌ не удалось взять замок $LOCK — каталог недоступен на запись?"
    notify "Дашборд: автопрогон встал" "Не удалось взять замок — см. logs/"
    exit 1
  fi
  # снимаем только СВОЙ замок: чужой мог быть создан после того, как наш сняли
  trap '[ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ] && rm -rf "$LOCK"' EXIT

  # Подрезка лога — под замком: иначе параллельное пробуждение подменит файл
  # под работающим прогоном и хвост для сообщения об ошибке соберётся не тот.
  # В сухом прогоне замка нет, поэтому подрезку он не делает вовсе.
  if [ -f "$LOG" ] && [ "$(stat -f %z "$LOG")" -gt 1048576 ]; then
    tail -n 2000 "$LOG" >"$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
  fi
fi

# ────────────────────────── поиск выгрузки ───────────────────────────
shopt -s nullglob
candidates=(issues*.xlsx)
if [ ${#candidates[@]} -eq 0 ]; then
  [ "$DRY" -eq 1 ] && log "нет ни одного issues*.xlsx"
  exit 0
fi
latest=$(ls -t -- "${candidates[@]}" 2>/dev/null | head -n1)
[ -n "$latest" ] || exit 0

fingerprint=$(stat -f '%m|%z' -- "$latest" 2>/dev/null)
if [ -z "$fingerprint" ]; then
  log "⚠️  не удалось прочитать $latest — пропускаю"
  exit 0
fi

# Уже обработанное (в том числе неудачно) второй раз не берём: отпечаток
# пишется до работы. Исключение — оборванный прогон: его надо доделать.
interrupted=0
state_read
if [ "$FORCE" -eq 0 ] && [ "$st_fp" = "$fingerprint" ]; then
  if [ "$st_status" = "started" ]; then
    if [ -n "$st_pid" ] && kill -0 "$st_pid" 2>/dev/null; then
      exit 0   # прогон идёт прямо сейчас
    fi
    log "↻ прошлый прогон этой выгрузки оборван (pid ${st_pid:-?}) — повторяю"
    interrupted=1
  else
    [ "$DRY" -eq 1 ] && log "выгрузка $latest уже обработана — выход"
    exit 0
  fi
fi

# ───────────────────── отбраковка: не сегодняшняя ─────────────────────
# Только сегодняшняя выгрузка: иначе постороннее изменение папки (правка кода,
# запись отчёта) заставило бы переименовать вчерашний файл в сегодняшний и
# прогнать пайплайн на устаревших данных.
#
# Об отбраковке нужно СКАЗАТЬ: файл, скачанный вечером и перенесённый в папку
# утром, сохраняет старый mtime, и молчание владелец прочитает как «всё прошло».
# Чтобы не повторять это на каждое пробуждение, отпечаток отброшенного файла
# запоминается отдельно.
mtime=$(stat -f %m -- "$latest" 2>/dev/null)
day_start=$(date -j -f '%Y-%m-%d %H:%M:%S' "$(date '+%Y-%m-%d') 00:00:00" '+%s')
if [ -n "$mtime" ] && [ "$mtime" -lt "$day_start" ] && [ "$FORCE" -eq 0 ]; then
  log "⏭  $latest не сегодняшний (изменён $(date -r "$mtime" '+%d.%m %H:%M')) — пропускаю"
  if [ "$DRY" -eq 0 ] && [ "$(cat "$SKIPPED" 2>/dev/null)" != "$fingerprint" ]; then
    printf '%s' "$fingerprint" >"$SKIPPED"
    tg "$(printf '⏭ Выгрузка пропущена · %s\n\n📄 %s\n📆 Файл изменён %s — не сегодня, поэтому автопрогон его не взял.\n\nЕсли выгрузка всё-таки актуальна:\n🔁 ./watch_pipeline.sh --force' \
          "$(date '+%d.%m %H:%M')" "$latest" "$(date -r "$mtime" '+%d.%m %H:%M')")"
  fi
  exit 0
fi

# Старый снимок, вернувшийся в корень (например, `cp archive/issues/…`), получает
# свежий mtime и прошёл бы проверку выше — а дальше был бы переименован в сегодня
# и опубликован как актуальные данные. Дата в имени старше сегодняшней — стоп.
name_day=$(printf '%s' "$latest" | sed -n 's/^issues_\([0-9][0-9]\)\.\([0-9][0-9]\).*/\1.\2/p')
today_day=$(date '+%d.%m')
if [ -n "$name_day" ] && [ "$name_day" != "$today_day" ] && [ "$FORCE" -eq 0 ]; then
  log "⏭  $latest — снимок за $name_day, не за $today_day; пропускаю"
  if [ "$DRY" -eq 0 ] && [ "$(cat "$SKIPPED" 2>/dev/null)" != "$fingerprint" ]; then
    printf '%s' "$fingerprint" >"$SKIPPED"
    tg "$(printf '⏭ Выгрузка пропущена · %s\n\n📄 %s\n📆 В имени файла дата %s, а сегодня %s — похоже на старый снимок, публиковать его как свежие данные автопрогон не стал.\n\nЕсли это всё-таки актуальная выгрузка:\n🔁 ./watch_pipeline.sh --force' \
          "$(date '+%d.%m %H:%M')" "$latest" "$name_day" "$today_day")"
  fi
  exit 0
fi

# Файл мог ещё дописываться (копирование, докачка браузером) — ждём,
# пока размер перестанет меняться, максимум ~10 с.
size_prev=$(stat -f %z -- "$latest")
for _ in 1 2 3 4 5; do
  sleep 2
  size_now=$(stat -f %z -- "$latest")
  [ "$size_now" = "$size_prev" ] && break
  size_prev="$size_now"
done
# отпечаток — после ожидания: снятый раньше принадлежал недокачанному файлу
# и не совпал бы с итоговым, давая лишний полный прогон
fingerprint=$(stat -f '%m|%z' -- "$latest")

log "─── новая выгрузка: $latest ($((size_prev / 1024)) КБ)"

# ─────────────────── проверка, что это выгрузка Redmine ───────────────
# Маска issues*.xlsx ловит любой файл, начинающийся на «issues», а `mv -f` ниже
# затирает сегодняшний снимок безвозвратно — выгрузки в git не хранятся.
# Поэтому проверяем колонки ДО переименования, теми же требованиями,
# что и сам пайплайн (extract_data.validate_source_columns).
#
# Код возврата различает два разных исхода: 2 — файл действительно чужой,
# 3 — проверка не выполнилась (сломанная среда, недоступный файл). Во втором
# случае помечать выгрузку обработанной нельзя: диагноз неизвестен, и после
# починки среды она должна подхватиться сама.
check_out=$(python3 - "$latest" <<'PYCHECK' 2>&1
import sys
try:
    import pandas as pd
    from extract_data import validate_source_columns
except Exception as exc:                       # numpy/pandas рассинхронизированы и т.п.
    print(f'проверка не выполнилась: {exc!r}')
    sys.exit(3)
try:
    df = pd.read_excel(sys.argv[1])
    validate_source_columns(
        df, ['Трекер', '#', 'Проект', 'Статус', 'Родительская задача'], sys.argv[1]
    )
except OSError as exc:                         # файл занят, права, диск
    print(f'проверка не выполнилась: {exc!r}')
    sys.exit(3)
except Exception as exc:
    # только суть: полный текст содержит все колонки файла, а он уходит в Telegram
    print(str(exc).split('. Есть:')[0])
    sys.exit(2)
PYCHECK
)
check_rc=$?

if [ "$check_rc" -eq 2 ]; then
  log "❌ $latest не похож на выгрузку Redmine — файл не тронут"
  log "   $check_out"
  if [ "$DRY" -eq 0 ]; then
    state_write failed
    notify "Дашборд: чужой файл" "$latest — не выгрузка Redmine"
    tg "$(printf '⚠️ Файл не взят в работу · %s\n\n📄 %s\n\nВ нём нет обязательных колонок Redmine, поэтому автопрогон его не тронул — сегодняшний снимок цел.\n\nЕсли это всё-таки выгрузка:\n🔁 ./watch_pipeline.sh --force\n📓 Подробности: logs/auto-pipeline.log' \
          "$(date '+%d.%m %H:%M')" "$latest")"
  fi
  exit 0
elif [ "$check_rc" -ne 0 ]; then
  # Отпечаток НЕ пишем: выгрузка не отвергнута, её просто не удалось проверить.
  # Сообщение гасим через .skipped, иначе оно повторится на каждом пробуждении.
  log "⚠️  не удалось проверить $latest — выгрузка не тронута"
  log "   $check_out"
  if [ "$DRY" -eq 0 ] && [ "$(cat "$SKIPPED" 2>/dev/null)" != "$fingerprint" ]; then
    printf '%s' "$fingerprint" >"$SKIPPED"
    notify "Дашборд: проверка не выполнилась" "$latest — см. logs/"
    tg "$(printf '⚠️ Выгрузка не проверена · %s\n\n📄 %s\n\n%s\n\nФайл оставлен как есть. Как только причина уйдёт, он подхватится сам — или запустите вручную:\n🔁 ./watch_pipeline.sh --force' \
          "$(date '+%d.%m %H:%M')" "$latest" "$check_out")"
  fi
  exit 0
fi
log "✅ проверка колонок Redmine пройдена"

# ───────────────────── переименование в текущую дату ──────────────────
target="issues_$(date '+%d.%m').xlsx"

# Отпечаток пишем ДО работы: если пайплайн упадёт, launchd разбудит скрипт
# снова (и снова — пробуждений порядка шести в минуту), и та же выгрузка
# уходила бы в бесконечный цикл коммитов, пушей и сообщений об ошибке.
# Статус «started» при этом отличает идущую работу от завершённой попытки:
# прогон, убитый сигналом, будет повторён, а не сочтён обработанным.
state_write started

if [ "$latest" != "$target" ]; then
  if [ "$DRY" -eq 1 ]; then
    log "→ переименовал бы: $latest → $target"
  else
    # -f: файл за сегодня перезаписывается молча (решение владельца)
    if mv -f -- "$latest" "$target"; then
      log "📄 $latest → $target"
    else
      log "❌ не удалось переименовать $latest"
      fail "переименование $latest → $target" 1
      exit 1
    fi
  fi
else
  log "📄 имя уже актуально: $target"
fi

# ───────────────────────────── deploy.sh ──────────────────────────────
# Без md-отчёта: process_report.py не вызывается, telegram-сводки не трогаются.
if [ "$DRY" -eq 1 ]; then
  log "→ запустил бы: ./deploy.sh $target"
else
  log "🚀 ./deploy.sh $target"
  out="$LOG_DIR/.deploy-out"
  ./deploy.sh "$target" >"$out" 2>&1
  code=$?
  cat "$out" >>"$LOG"

  if [ "$code" -eq 0 ]; then
    if grep -q "не изменился" "$out"; then
      log "ℹ️  данные не изменились — коммита не было"
      deploy_note="данные без изменений"
      deploy_line="ℹ️ data.json не изменился — коммита и пуша не было"
    else
      log "✅ deploy прошёл"
      deploy_note="данные обновлены и запушены"
      deploy_line="🚀 data.json закоммичен и запушен"
    fi
  elif grep -q "ошибками пуша" "$out"; then
    # Пайплайн отработал, коммит сделан, но один из remotes отказал
    # (у upstream уже слетал доступ — 403). Дашборд при этом мог обновиться:
    # это предупреждение, а не провал прогона.
    failed=$(grep "ошибками пуша" "$out" | sed 's/.*пуша://')
    log "⚠️  пуш не прошёл в:$failed (данные пересчитаны и закоммичены)"
    notify "Дашборд: пуш не прошёл" "Не отправлено в:$failed"
    deploy_note="пуш не прошёл в:$failed"
    deploy_line="⚠️ Пуш не прошёл в:$failed — данные пересчитаны и закоммичены, но на Amvera уедут только после ручного пуша"
  else
    log "❌ deploy завершился с кодом $code — см. лог выше"
    fail "deploy.sh" "$code"
    exit "$code"
  fi
fi

# ─────────────────── справка по срокам до конца недели ────────────────
# Конец недели = ближайшая пятница; в субботу и воскресенье — следующая.
dow=$(date '+%u')
if [ "$dow" -le 5 ]; then add=$((5 - dow)); else add=$((12 - dow)); fi
week_end=$(date -v+"${add}"d '+%d.%m.%Y')

if [ "$DRY" -eq 1 ]; then
  log "→ собрал бы справку: сегодня .. $week_end"
else
  log "📅 справка по срокам: сегодня .. $week_end"
  rep_out="$LOG_DIR/.report-out"
  if python3 upcoming_report.py --to "$week_end" --format both >"$rep_out" 2>&1; then
    cat "$rep_out" >>"$LOG"
    log "✅ справка собрана"
    # первая строка скрипта уже сводка: «✅ Справка 24.08–28.08.2026: 59 задач в 9 проектах»
    report_line=$(head -n1 "$rep_out")
    report_file=$(grep -o '[^/]*\.md$' "$rep_out" | head -n1)
    [ -n "$report_file" ] && report_line="$report_line
   $report_file"
  else
    cat "$rep_out" >>"$LOG"
    log "⚠️  справка не собралась (данные обновлены)"
    notify "Дашборд обновлён" "Справка по срокам не собралась — см. лог"
    report_line="⚠️ Справка по срокам не собралась — см. logs/auto-pipeline.log"
  fi
fi

# ───────────────────────────── завершение ─────────────────────────────
# Итог в Telegram: владелец должен видеть, что работа закончилась, не заглядывая
# в папку. Цифры берём из свежесобранного data.json — «готово» без чисел не даёт
# понять, тот ли файл обработан.
stats=$(python3 - <<'PYSTATS' 2>/dev/null
import json
try:
    s = json.load(open('data.json'))['summary']
except Exception:
    raise SystemExit(0)
print('📊 Проекты {} (в работе {}) · задачи {} (активных {})'.format(
    s.get('projects_total', '—'), s.get('projects_active', '—'),
    s.get('tasks_total', '—'), s.get('tasks_active', '—')))
print('⏰ Просрочено {} · срок сегодня {}'.format(
    s.get('tasks_overdue', '—'), s.get('tasks_today', '—')))
if s.get('vysv_pct_total') is not None:
    print('📈 Высвобождение {}%'.format(s['vysv_pct_total']))
PYSTATS
)

if [ -n "${failed:-}" ]; then
  head_line="⚠️ Дашборд обновлён с замечанием · $(date '+%d.%m %H:%M')"
else
  head_line="✅ Дашборд обновлён · $(date '+%d.%m %H:%M')"
fi

[ "$interrupted" -eq 1 ] && head_line="$head_line
↻ прошлый прогон был оборван, выгрузка обработана заново"

tg "$(printf '%s\n\n📄 %s\n%s\n\n%s\n\n%s' \
      "$head_line" "$target" "$stats" "${report_line:-—}" "${deploy_line:-—}")"

state_write done
if [ "$DRY" -eq 0 ]; then
  notify "Дашборд: прогон завершён" "$target · ${deploy_note:-готово} · справка до $week_end"
fi
log "─── готово"
