#!/bin/bash
# install.sh — поставить/снять LaunchAgent автопрогона пайплайна.
#
#   ./automation/install.sh            — установить и включить
#   ./automation/install.sh --uninstall — выключить и убрать
#   ./automation/install.sh --status    — проверить, загружен ли агент
#
set -euo pipefail

# Два агента: автопрогон по появлению выгрузки и напоминание о несданных отчётах
LABELS=(com.vz.transformation-pipeline com.vz.transformation-report-reminder)
AUTOMATION="/Users/valeriy/Projects/transformation/automation"

case "${1:-install}" in
  --status)
    for LABEL in "${LABELS[@]}"; do
      if launchctl list | grep -q "$LABEL"; then
        echo "✅ $LABEL загружен"
      else
        echo "⛔️ $LABEL не загружен"
      fi
    done
    ;;
  --uninstall)
    for LABEL in "${LABELS[@]}"; do
      DST="$HOME/Library/LaunchAgents/$LABEL.plist"
      launchctl unload "$DST" 2>/dev/null || true
      rm -f "$DST"
      echo "🗑  $LABEL снят"
    done
    ;;
  install)
    for LABEL in "${LABELS[@]}"; do
      DST="$HOME/Library/LaunchAgents/$LABEL.plist"
      cp "$AUTOMATION/$LABEL.plist" "$DST"
      launchctl unload "$DST" 2>/dev/null || true
      launchctl load "$DST"
      echo "✅ $LABEL установлен"
    done
    echo "   лог автопрогона:   logs/auto-pipeline.log"
    echo "   лог напоминаний:   logs/report-reminder.out"
    ;;
  *)
    echo "неизвестный аргумент: $1" >&2; exit 2 ;;
esac
