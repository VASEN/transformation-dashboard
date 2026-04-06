#!/bin/bash
set -e

echo "🔄 Извлечение данных..."
python3 extract_data.py

echo "📋 Генерация отчёта..."
python3 process_report.py

echo "📦 Коммит data.json..."
git add data.json
git commit -m "data: обновление $(date '+%d.%m.%Y %H:%M')"

echo "📤 Пуш в репозитории..."
git push -u upstream main
git push -u origin main

echo "✅ Деплой завершён"
