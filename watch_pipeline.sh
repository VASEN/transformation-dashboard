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
#   ./watch_pipeline.sh --dry-run  — показать, что было бы сделано; ничего не пишет
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
STATE="$LOG_DIR/.processed"      # отпечаток последней обработанной выгрузки
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
  osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1
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
  notify "Дашборд: ошибка" "$step · код $code"
  tg "$(printf '%s\n\n📄 %s\n🧩 Шаг: %s (код %s)\n\n⌄ хвост лога:\n%s\n\n🔁 Повторить: ./watch_pipeline.sh --force\n📓 Полный лог: logs/auto-pipeline.log' \
        "❌ Автопрогон дашборда упал · $(date '+%d.%m %H:%M')" \
        "${target:-${latest:-выгрузка не определена}}" "$step" "$code" "$(log_tail)")"
}

# лог не должен расти бесконечно: раз в прогон подрезаем хвостом
if [ -f "$LOG" ] && [ "$(stat -f %z "$LOG")" -gt 1048576 ]; then
  tail -n 2000 "$LOG" >"$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
fi

# ─────────────────────────────── замок ───────────────────────────────
# Прогон длится минуту и сам пишет в папку (data.json, отчёты, справки),
# что снова будит launchd. Без замка это наложение прогонов друг на друга.
if [ "$DRY" -eq 0 ]; then
  if ! mkdir "$LOCK" 2>/dev/null; then
    if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
      log "⚠️  снимаю зависший замок (старше 30 мин)"
      rm -rf "$LOCK"
      mkdir "$LOCK" 2>/dev/null || exit 0
    else
      exit 0   # прогон уже идёт — молча уходим
    fi
  fi
  trap 'rm -rf "$LOCK"' EXIT
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

# Только сегодняшняя выгрузка. Иначе любое постороннее изменение папки
# (правка кода, запись отчёта) заставило бы переименовать вчерашний файл
# в сегодняшний и прогнать пайплайн на устаревших данных.
mtime=$(stat -f %m -- "$latest")
day_start=$(date -j -f '%Y-%m-%d %H:%M:%S' "$(date '+%Y-%m-%d') 00:00:00" '+%s')
if [ "$mtime" -lt "$day_start" ] && [ "$FORCE" -eq 0 ]; then
  [ "$DRY" -eq 1 ] && log "самая свежая выгрузка $latest не сегодняшняя — выход"
  exit 0
fi

# Отпечаток по mtime+размеру, без имени: переименование его не сбивает,
# поэтому собственная запись скрипта в папку второй прогон не вызывает.
fingerprint=$(stat -f '%m|%z' -- "$latest")
if [ "$FORCE" -eq 0 ] && [ -f "$STATE" ] && [ "$(cat "$STATE")" = "$fingerprint" ]; then
  [ "$DRY" -eq 1 ] && log "выгрузка $latest уже обработана — выход"
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

log "─── новая выгрузка: $latest ($((size_prev / 1024)) КБ)"

# ───────────────────── переименование в текущую дату ──────────────────
target="issues_$(date '+%d.%m').xlsx"
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

tg "$(printf '%s\n\n📄 %s\n%s\n\n%s\n\n%s' \
      "$head_line" "$target" "$stats" "${report_line:-—}" "${deploy_line:-—}")"

if [ "$DRY" -eq 0 ]; then
  printf '%s' "$fingerprint" >"$STATE"
  notify "Дашборд: прогон завершён" "$target · ${deploy_note:-готово} · справка до $week_end"
fi
log "─── готово"
