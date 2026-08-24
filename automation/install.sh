#!/bin/bash
# install.sh — поставить/снять LaunchAgent автопрогона пайплайна.
#
#   ./automation/install.sh            — установить и включить
#   ./automation/install.sh --uninstall — выключить и убрать
#   ./automation/install.sh --status    — проверить, загружен ли агент
#
set -euo pipefail

LABEL="com.vz.transformation-pipeline"
SRC="/Users/valeriy/Projects/transformation/automation/$LABEL.plist"
DST="$HOME/Library/LaunchAgents/$LABEL.plist"

case "${1:-install}" in
  --status)
    if launchctl list | grep -q "$LABEL"; then
      echo "✅ агент загружен"
      launchctl list | grep "$LABEL"
    else
      echo "⛔️ агент не загружен"
    fi
    ;;
  --uninstall)
    launchctl unload "$DST" 2>/dev/null || true
    rm -f "$DST"
    echo "🗑  агент снят"
    ;;
  install)
    cp "$SRC" "$DST"
    launchctl unload "$DST" 2>/dev/null || true
    launchctl load "$DST"
    echo "✅ агент установлен: $DST"
    echo "   лог прогонов: logs/auto-pipeline.log"
    ;;
  *)
    echo "неизвестный аргумент: $1" >&2; exit 2 ;;
esac
