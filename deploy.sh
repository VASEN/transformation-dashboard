#!/bin/bash
set -e

ISSUES_FILE="${1:-issues.xlsx}"
REPORT_FILE="${2:-}"
PREV_FILE="${3:-}"

echo "🔄 Извлечение данных из ${ISSUES_FILE}..."
python3 extract_data.py "$ISSUES_FILE"

echo "📋 Генерация отчёта..."
if [ -n "$REPORT_FILE" ] && [ -n "$PREV_FILE" ]; then
  python3 process_report.py "$REPORT_FILE" --prev "$PREV_FILE"
elif [ -n "$REPORT_FILE" ]; then
  python3 process_report.py "$REPORT_FILE"
fi

echo "📦 Коммит data.json..."
git add .
git commit -m "data: обновление $(date '+%d.%m.%Y %H:%M')"

echo "📤 Пуш в репозитории..."
git push -u upstream main
git push -u origin main

echo "✅ Деплой завершён"
