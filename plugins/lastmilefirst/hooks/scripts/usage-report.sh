#!/bin/bash
# Generate usage report from invocation logs
# Shows stats for the past 7 days

INVOCATIONS_FILE="${HOME}/.claude/lastmilefirst/invocations.log"

if [ ! -f "$INVOCATIONS_FILE" ]; then
  exit 0
fi

# Get timestamp for 7 days ago
WEEK_AGO=$(( $(date +%s) - 604800 ))

# Count invocations in the past week
WEEKLY_COUNT=$(awk -F'|' -v cutoff="$WEEK_AGO" '$1 >= cutoff' "$INVOCATIONS_FILE" 2>/dev/null | wc -l | tr -d ' ')

if [ "$WEEKLY_COUNT" -gt 0 ]; then
  echo "📊 ${WEEKLY_COUNT} skill invocations this week"

  # Show top skills if we have detailed data
  TOP_SKILLS=$(awk -F'|' -v cutoff="$WEEK_AGO" '$1 >= cutoff {print $2}' "$INVOCATIONS_FILE" 2>/dev/null | \
    grep -v "^unknown$" | sort | uniq -c | sort -rn | head -3)

  if [ -n "$TOP_SKILLS" ] && [ "$(echo "$TOP_SKILLS" | grep -v "unknown" | wc -l)" -gt 0 ]; then
    echo "   Top: $(echo "$TOP_SKILLS" | awk '{printf "%s (%d) ", $2, $1}' | sed 's/ $//')"
  fi

  # Occasionally prompt to share the love (roughly 1 in 10 sessions)
  if [ $(( RANDOM % 10 )) -eq 0 ] && [ "$WEEKLY_COUNT" -ge 10 ]; then
    echo "   💜 Enjoying these plugins? Consider starring their repos!"
  fi
fi

# Prune old entries (older than 30 days) to prevent unbounded growth
MONTH_AGO=$(( $(date +%s) - 2592000 ))
if [ -f "$INVOCATIONS_FILE" ]; then
  TEMP_FILE="${INVOCATIONS_FILE}.tmp"
  awk -F'|' -v cutoff="$MONTH_AGO" '$1 >= cutoff' "$INVOCATIONS_FILE" > "$TEMP_FILE" 2>/dev/null
  mv "$TEMP_FILE" "$INVOCATIONS_FILE" 2>/dev/null || true
fi
