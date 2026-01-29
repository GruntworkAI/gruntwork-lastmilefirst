#!/bin/bash
# Lastmilefirst Overwatch - Session Start Checks
# This script runs at the start of every Claude Code session
# Output becomes part of Claude's context

set -e

OVERWATCH_STATE_DIR="${HOME}/.claude/lastmilefirst"
OVERWATCH_STATE_FILE="${OVERWATCH_STATE_DIR}/overwatch-state.json"
OVERWATCH_LOCK_FILE="${OVERWATCH_STATE_DIR}/overwatch.lock"

# Check if flock is available (not on Windows/Git Bash)
USE_FLOCK=false
if command -v flock &>/dev/null; then
  USE_FLOCK=true
fi

# Ensure state directory exists
mkdir -p "$OVERWATCH_STATE_DIR"

# Initialize state file if missing
if [ ! -f "$OVERWATCH_STATE_FILE" ]; then
  echo '{"last_review": 0, "last_organize": 0, "last_plugin_check": 0}' > "$OVERWATCH_STATE_FILE"
fi

# Get current timestamp
NOW=$(date +%s)

# Read state (with fallback to 0 for missing/empty values)
LAST_REVIEW=$(cat "$OVERWATCH_STATE_FILE" | grep -o '"last_review":[0-9]*' | grep -o '[0-9]*' || true)
LAST_REVIEW=${LAST_REVIEW:-0}
LAST_ORGANIZE=$(cat "$OVERWATCH_STATE_FILE" | grep -o '"last_organize":[0-9]*' | grep -o '[0-9]*' || true)
LAST_ORGANIZE=${LAST_ORGANIZE:-0}

# Calculate days since last actions
DAYS_SINCE_REVIEW=$(( (NOW - LAST_REVIEW) / 86400 ))
DAYS_SINCE_ORGANIZE=$(( (NOW - LAST_ORGANIZE) / 86400 ))

# Collect alerts
ALERTS=""

# --- Check 1: Uncommitted Git Changes ---
if git rev-parse --git-dir > /dev/null 2>&1; then
  UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if [ "$UNCOMMITTED" -gt 0 ]; then
    ALERTS="${ALERTS}⚠️  $UNCOMMITTED uncommitted file(s) in this repo\n"
  fi
fi

# --- Check 2: Days Since Last Review ---
if [ "$LAST_REVIEW" -eq 0 ]; then
  ALERTS="${ALERTS}📋 No project review on record - consider running /review-project\n"
elif [ "$DAYS_SINCE_REVIEW" -ge 7 ]; then
  ALERTS="${ALERTS}📋 ${DAYS_SINCE_REVIEW} days since last /review-project\n"
fi

# --- Check 3: Days Since Last Organize ---
if [ "$LAST_ORGANIZE" -eq 0 ]; then
  # Don't alert on first run, just note it
  :
elif [ "$DAYS_SINCE_ORGANIZE" -ge 14 ]; then
  ALERTS="${ALERTS}🗂️  ${DAYS_SINCE_ORGANIZE} days since last /organize-project\n"
fi

# --- Check 4: Plugin Updates (check all installed plugins) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_UPDATES=$("$SCRIPT_DIR/check-plugin-updates.sh" 2>/dev/null || true)
if [ -n "$PLUGIN_UPDATES" ]; then
  ALERTS="${ALERTS}${PLUGIN_UPDATES}\n"
fi

# --- Check 5: Stale Todos (if .claude/work/todos exists) ---
if [ -d ".claude/work/todos" ]; then
  STALE_TODOS=$(find .claude/work/todos -name "*.md" -mtime +14 2>/dev/null | wc -l | tr -d ' ')
  if [ "$STALE_TODOS" -gt 0 ]; then
    ALERTS="${ALERTS}📝 $STALE_TODOS todo(s) older than 14 days - consider /review-work\n"
  fi
fi

# --- Check 6: Missing CLAUDE.md ---
if [ ! -f "CLAUDE.md" ]; then
  ALERTS="${ALERTS}📄 No CLAUDE.md in this project - consider /organize-claude scaffold\n"
fi

# --- Output ---
if [ -n "$ALERTS" ]; then
  echo ""
  echo "┌─────────────────────────────────────────────────────────┐"
  echo "│  OVERWATCH                                              │"
  echo "└─────────────────────────────────────────────────────────┘"
  echo -e "$ALERTS"
fi

# Clear session change log for fresh tracking
rm -f ~/.claude/tmp/session-changes.log
