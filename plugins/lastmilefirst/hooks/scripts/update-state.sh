#!/bin/bash
# Lastmilefirst Overwatch - Update State
# Usage: update-state.sh <action>
# Actions: review, organize, plugin_check

set -e

ACTION="$1"
OVERWATCH_STATE_DIR="${HOME}/.claude/lastmilefirst"
OVERWATCH_STATE_FILE="${OVERWATCH_STATE_DIR}/overwatch-state.json"
OVERWATCH_LOCK_FILE="${OVERWATCH_STATE_DIR}/overwatch.lock"

# Check if flock is available (not on Windows/Git Bash)
USE_FLOCK=false
if command -v flock &>/dev/null; then
  USE_FLOCK=true
fi

# Helper function for locked state updates
update_state_field() {
  local field="$1"
  local value="$2"
  if [ "$USE_FLOCK" = true ]; then
    (
      flock -x 200
      cat "$OVERWATCH_STATE_FILE" | sed "s/\"${field}\":[0-9]*/\"${field}\":${value}/" > "${OVERWATCH_STATE_FILE}.tmp"
      mv "${OVERWATCH_STATE_FILE}.tmp" "$OVERWATCH_STATE_FILE"
    ) 200>"$OVERWATCH_LOCK_FILE"
  else
    cat "$OVERWATCH_STATE_FILE" | sed "s/\"${field}\":[0-9]*/\"${field}\":${value}/" > "${OVERWATCH_STATE_FILE}.tmp"
    mv "${OVERWATCH_STATE_FILE}.tmp" "$OVERWATCH_STATE_FILE"
  fi
}

# Ensure state directory exists
mkdir -p "$OVERWATCH_STATE_DIR"

# Initialize state file if missing
if [ ! -f "$OVERWATCH_STATE_FILE" ]; then
  echo '{"last_review": 0, "last_organize": 0, "last_plugin_check": 0}' > "$OVERWATCH_STATE_FILE"
fi

NOW=$(date +%s)

case "$ACTION" in
  review)
    update_state_field "last_review" "$NOW"
    echo "✓ Overwatch: recorded review at $(date)"
    ;;
  organize)
    update_state_field "last_organize" "$NOW"
    echo "✓ Overwatch: recorded organize at $(date)"
    ;;
  plugin_check)
    update_state_field "last_plugin_check" "$NOW"
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
