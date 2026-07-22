#!/usr/bin/env bash
# preview.sh — прогон пайплайна дашборда на КОПИЯХ и сравнение «до/после».
#
# Скрипты пайплайна пишут результат в текущий каталог, поэтому проверочный
# запуск в корне проекта затирает рабочие data.json / telegram_*.txt.
# Здесь всё делается в песочнице: текущая рабочая версия скриптов и базовая
# версия (по умолчанию HEAD) гоняются на одних и тех же входах, результаты
# сравниваются.
#
# Использование:
#   .claude/skills/pipeline-preview/preview.sh                       # авто: свежий отчёт + предыдущий
#   .claude/skills/pipeline-preview/preview.sh --report ОТЧЕТ_22.07.md --prev ОТЧЕТ_15.07.md
#   .claude/skills/pipeline-preview/preview.sh --stage report        # только process_report.py
#   .claude/skills/pipeline-preview/preview.sh --stage extract       # только extract_data.py
#   .claude/skills/pipeline-preview/preview.sh --base HEAD~3         # сравнить с другой ревизией
#   .claude/skills/pipeline-preview/preview.sh --keep                # не удалять песочницу
set -euo pipefail
shopt -s nullglob

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

STAGE=all
BASE=HEAD
REPORT=""
PREV=""
REDMINE=""
KEEP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage)   STAGE="$2"; shift 2 ;;
    --base)    BASE="$2"; shift 2 ;;
    --report)  REPORT="$2"; shift 2 ;;
    --prev)    PREV="$2"; shift 2 ;;
    --redmine) REDMINE="$2"; shift 2 ;;
    --keep)    KEEP=1; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "❌ неизвестный аргумент: $1" >&2; exit 1 ;;
  esac
done

# ── Входные файлы: по умолчанию самые свежие ─────────────────────────
pick_latest() { local files=("$@"); [[ ${#files[@]} -gt 0 ]] && ls -t "${files[@]}" 2>/dev/null | head -1; }

REPORTS=($(ls -t ОТЧЕТ_*.md 2>/dev/null || true))
[[ -z "$REPORT" && ${#REPORTS[@]} -gt 0 ]] && REPORT="${REPORTS[0]}"
[[ -z "$PREV"   && ${#REPORTS[@]} -gt 1 ]] && PREV="${REPORTS[1]}"
[[ -z "$REDMINE" ]] && REDMINE="$(pick_latest issues*.xlsx)"
SHTATKA="$(pick_latest ШТАТКА_ДБ*.xlsx)"
VYSV="$(pick_latest *"Данные по высвобождению"*.xlsx)"

echo "📋 Входные данные"
echo "   отчёт:         ${REPORT:-—}"
echo "   предыдущий:    ${PREV:-— (без diff-режима)}"
[[ "$STAGE" != report ]] && {
  echo "   Redmine:       ${REDMINE:-—}"
  echo "   штатка:        ${SHTATKA:-—}"
  echo "   высвобождение: ${VYSV:-—}"
}
echo "   сравнение с:   $BASE"
echo

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/pipeline-preview.XXXXXX")"
trap '[[ $KEEP -eq 0 ]] && rm -rf "$SANDBOX"' EXIT

run_version() {   # run_version <имя> <каталог> <как достать скрипты: work|base>
  local label="$1" dir="$2" mode="$3"
  mkdir -p "$dir"

  for f in config.py extract_data.py process_report.py overdue_report.py; do
    if [[ "$mode" == base ]]; then
      git show "$BASE:$f" > "$dir/$f" 2>/dev/null || cp "$f" "$dir/$f"
    else
      cp "$f" "$dir/$f"
    fi
  done
  cp data.json "$dir/data.json"
  [[ -n "$REPORT" ]] && cp "$REPORT" "$dir/"
  [[ -n "$PREV"   ]] && cp "$PREV"   "$dir/"
  for x in "$REDMINE" "$SHTATKA" "$VYSV"; do [[ -n "$x" && -f "$x" ]] && cp "$x" "$dir/"; done

  (
    cd "$dir"
    if [[ "$STAGE" == all || "$STAGE" == extract ]]; then
      python3 extract_data.py "$REDMINE" "$SHTATKA" "$VYSV" > extract.log 2>&1 \
        || { echo "❌ [$label] extract_data.py упал:"; tail -20 extract.log; exit 1; }
    fi
    if [[ "$STAGE" == all || "$STAGE" == report ]] && [[ -n "$REPORT" ]]; then
      local prev_arg=()
      [[ -n "$PREV" ]] && prev_arg=(--prev "$PREV")
      python3 process_report.py "$REPORT" --telegram-only "${prev_arg[@]}" > report.log 2>&1 \
        || { echo "❌ [$label] process_report.py упал:"; tail -20 report.log; exit 1; }
    fi
  )
}

echo "⚙️  Прогон базовой версии ($BASE)…"
run_version base "$SANDBOX/base" base
echo "⚙️  Прогон текущей версии (рабочее дерево)…"
run_version work "$SANDBOX/work" work

# ── Что нового сказал сам пайплайн ───────────────────────────────────
echo
echo "🗒  Лог текущей версии (диагностики пайплайна):"
grep -hE '^\s*(Σ|~|⚠️|✅ Реализованы)' "$SANDBOX/work"/*.log 2>/dev/null | sed 's/^/   /' || echo "   (нет)"

# ── Сравнение data.json ──────────────────────────────────────────────
if [[ "$STAGE" == all || "$STAGE" == extract ]]; then
  echo
  echo "📊 Изменения в data.json (base → work):"
  python3 "$ROOT/.claude/skills/pipeline-preview/compare_data.py" \
    "$SANDBOX/base/data.json" "$SANDBOX/work/data.json" | sed 's/^/   /'
fi

# ── Сравнение telegram-сообщений ─────────────────────────────────────
if [[ "$STAGE" == all || "$STAGE" == report ]]; then
  echo
  echo "💬 Изменения в telegram-сообщениях (base → work):"
  changed=0
  for f in "$SANDBOX/work"/telegram_*.txt; do
    name="$(basename "$f")"
    if [[ -f "$SANDBOX/base/$name" ]]; then
      if diff -q "$SANDBOX/base/$name" "$f" >/dev/null; then continue; fi
      changed=1
      echo "   ── $name"
      diff -u "$SANDBOX/base/$name" "$f" | tail -n +3 | grep -E '^[+-]' | sed 's/^/      /' | head -60
    else
      changed=1
      echo "   ── $name (новый файл)"
    fi
  done
  [[ $changed -eq 0 ]] && echo "   без изменений"
fi

echo
if [[ $KEEP -eq 1 ]]; then
  echo "📁 Песочница сохранена: $SANDBOX"
  echo "   base: $SANDBOX/base | work: $SANDBOX/work"
else
  echo "🧹 Песочница удалена (--keep — чтобы сохранить)."
fi
echo "✅ Рабочие data.json и telegram_*.txt в корне НЕ тронуты."
