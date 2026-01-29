#!/bin/bash
# Log skill/command invocations for usage tracking
# Usage: log-invocation.sh <skill-name>

INVOCATIONS_DIR="${HOME}/.claude/lastmilefirst"
INVOCATIONS_FILE="${INVOCATIONS_DIR}/invocations.log"

mkdir -p "$INVOCATIONS_DIR"

# Log format: timestamp|skill_name
echo "$(date +%s)|${1:-unknown}" >> "$INVOCATIONS_FILE"
