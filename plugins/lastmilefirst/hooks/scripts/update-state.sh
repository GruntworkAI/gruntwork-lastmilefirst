#!/bin/bash
# Lastmilefirst Overwatch - Update State
# Usage: update-state.sh <action>
# Actions: review, organize, plugin_check

set -e

ACTION="$1"
OVERWATCH_STATE_DIR="${HOME}/.claude/lastmilefirst"
OVERWATCH_STATE_FILE="${OVERWATCH_STATE_DIR}/overwatch-state.json"

# Ensure state directory exists
mkdir -p "$OVERWATCH_STATE_DIR"

# Initialize state file if missing
if [ ! -f "$OVERWATCH_STATE_FILE" ]; then
  echo '{"last_review": 0, "last_organize": 0, "last_plugin_check": 0}' > "$OVERWATCH_STATE_FILE"
fi

NOW=$(date +%s)

case "$ACTION" in
  review)
    cat "$OVERWATCH_STATE_FILE" | sed "s/\"last_review\":[0-9]*/\"last_review\":$NOW/" > "${OVERWATCH_STATE_FILE}.tmp"
    mv "${OVERWATCH_STATE_FILE}.tmp" "$OVERWATCH_STATE_FILE"
    echo "✓ Overwatch: recorded review at $(date)"
    ;;
  organize)
    cat "$OVERWATCH_STATE_FILE" | sed "s/\"last_organize\":[0-9]*/\"last_organize\":$NOW/" > "${OVERWATCH_STATE_FILE}.tmp"
    mv "${OVERWATCH_STATE_FILE}.tmp" "$OVERWATCH_STATE_FILE"
    echo "✓ Overwatch: recorded organize at $(date)"
    ;;
  plugin_check)
    cat "$OVERWATCH_STATE_FILE" | sed "s/\"last_plugin_check\":[0-9]*/\"last_plugin_check\":$NOW/" > "${OVERWATCH_STATE_FILE}.tmp"
    mv "${OVERWATCH_STATE_FILE}.tmp" "$OVERWATCH_STATE_FILE"
    echo "✓ Overwatch: recorded plugin check at $(date)"
    ;;
  status)
    echo "Overwatch State:"
    cat "$OVERWATCH_STATE_FILE"
    ;;
  *)
    echo "Usage: update-state.sh <review|organize|plugin_check|status>"
    exit 1
    ;;
esac
