#!/bin/bash
set -e

ISSUES_FILE="${1:-issues.xlsx}"
REPORT_FILE="${2:-}"
PREV_FILE="${3:-}"

# Штатка и файл высвобождения.
# Можно задать явно ($4 — штатка, $5 — высвобождение),
# иначе берётся самый свежий подходящий файл (по времени изменения),
# иначе — каноническое имя.
shopt -s nullglob

detect_latest() {
  # печатает самый свежий из переданных файлов; ничего — если их нет
  if [ "$#" -gt 0 ]; then
    ls -t -- "$@" 2>/dev/null | head -n1
  fi
}

sh_files=(ШТАТКА_ДБ*.xlsx)
vy_files=(*"Данные по высвобождению"*.xlsx)

SHTATKA_FILE="${4:-$(detect_latest "${sh_files[@]}")}"
SHTATKA_FILE="${SHTATKA_FILE:-ШТАТКА_ДБ.xlsx}"
VYSV_FILE="${5:-$(detect_latest "${vy_files[@]}")}"
VYSV_FILE="${VYSV_FILE:-ПРОЕКТЫ_Данные по высвобождению.xlsx}"

echo "🔄 Извлечение данных:"
echo "   Redmine:       ${ISSUES_FILE}"
echo "   Штатка:        ${SHTATKA_FILE}"
echo "   Высвобождение: ${VYSV_FILE}"
python3 extract_data.py "$ISSUES_FILE" "$SHTATKA_FILE" "$VYSV_FILE"

echo "📋 Генерация отчёта..."
if [ -n "$REPORT_FILE" ] && [ -n "$PREV_FILE" ]; then
  python3 process_report.py "$REPORT_FILE" --prev "$PREV_FILE"
elif [ -n "$REPORT_FILE" ]; then
  python3 process_report.py "$REPORT_FILE"
fi

echo "⏰ Отчёт по просроченным задачам..."
python3 overdue_report.py

echo "📦 Коммит data.json..."
git add .
git commit -m "data: обновление $(date '+%d.%m.%Y %H:%M')"

echo "📤 Пуш в репозитории..."
git push -u upstream main
git push -u origin main

echo "✅ Деплой завершён"
