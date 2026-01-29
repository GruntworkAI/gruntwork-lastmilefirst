#!/bin/bash
# Lastmilefirst Overwatch - Plugin Update Checker
# Compares installed plugin versions against available versions in marketplaces
#
# Compatibility: macOS, Linux, WSL
# Note: May not work on Windows Git Bash due to path differences

set -e

# Determine plugins directory (handles different OS conventions)
if [ -n "$CLAUDE_PLUGINS_DIR" ]; then
  PLUGINS_DIR="$CLAUDE_PLUGINS_DIR"
elif [ -d "${HOME}/.claude/plugins" ]; then
  PLUGINS_DIR="${HOME}/.claude/plugins"
else
  # Can't find plugins directory, exit silently
  exit 0
fi

INSTALLED_FILE="${PLUGINS_DIR}/installed_plugins.json"
MARKETPLACES_DIR="${PLUGINS_DIR}/marketplaces"

# Check if required files exist
if [ ! -f "$INSTALLED_FILE" ]; then
  exit 0
fi

if [ ! -d "$MARKETPLACES_DIR" ]; then
  exit 0
fi

# Simple version comparison (works without sort -V)
# Returns 0 if $1 < $2, 1 otherwise
version_lt() {
  local v1="$1"
  local v2="$2"

  # If equal, not less than
  [ "$v1" = "$v2" ] && return 1

  # Use sort -V if available, otherwise fall back to simple comparison
  if echo | sort -V >/dev/null 2>&1; then
    [ "$(printf '%s\n%s' "$v1" "$v2" | sort -V | head -1)" = "$v1" ]
  else
    # Fallback: simple string comparison (works for most semver)
    [ "$(printf '%s\n%s' "$v1" "$v2" | sort -t. -k1,1n -k2,2n -k3,3n | head -1)" = "$v1" ]
  fi
}

# Check for updates
# Output format: plugin@marketplace installed available
check_updates() {
  # Get list of installed plugins using Python if available, otherwise grep
  if command -v python3 &>/dev/null; then
    python3 -c "
import json
import sys
import os

installed_file = '$INSTALLED_FILE'
marketplaces_dir = '$MARKETPLACES_DIR'

try:
    with open(installed_file) as f:
        data = json.load(f)
except:
    sys.exit(0)

plugins = data.get('plugins', {})
for plugin_id, installs in plugins.items():
    if not installs:
        continue

    installed = installs[0].get('version', '')
    if not installed:
        continue

    parts = plugin_id.split('@')
    if len(parts) != 2:
        continue

    plugin_name, marketplace = parts

    # Check marketplace for available version
    marketplace_json = os.path.join(
        marketplaces_dir, marketplace, 'plugins', plugin_name,
        '.claude-plugin', 'plugin.json'
    )

    if not os.path.exists(marketplace_json):
        continue

    try:
        with open(marketplace_json) as f:
            mp_data = json.load(f)
        available = mp_data.get('version', '')
    except:
        continue

    if available and installed != available:
        print(f'{plugin_name}@{marketplace} {installed} {available}')
"
  else
    # Fallback to grep-based parsing (less reliable)
    local plugins=$(grep -o '"[^"]*@[^"]*"' "$INSTALLED_FILE" 2>/dev/null | tr -d '"' | sort -u)

    for plugin_id in $plugins; do
      local plugin_name=$(echo "$plugin_id" | cut -d'@' -f1)
      local marketplace=$(echo "$plugin_id" | cut -d'@' -f2)

      local installed=$(grep -A5 "\"$plugin_id\"" "$INSTALLED_FILE" 2>/dev/null | grep '"version"' | head -1 | grep -o '"[0-9][^"]*"' | tr -d '"')

      local mp_json="${MARKETPLACES_DIR}/${marketplace}/plugins/${plugin_name}/.claude-plugin/plugin.json"

      if [ -f "$mp_json" ]; then
        local available=$(grep '"version"' "$mp_json" 2>/dev/null | head -1 | grep -o '"[0-9][^"]*"' | tr -d '"')

        if [ -n "$installed" ] && [ -n "$available" ] && [ "$installed" != "$available" ]; then
          echo "${plugin_name}@${marketplace} ${installed} ${available}"
        fi
      fi
    done
  fi
}

# Filter to only show actual updates (available > installed)
filter_updates() {
  while read -r line; do
    [ -z "$line" ] && continue

    local plugin=$(echo "$line" | cut -d' ' -f1)
    local installed=$(echo "$line" | cut -d' ' -f2)
    local available=$(echo "$line" | cut -d' ' -f3)

    if version_lt "$installed" "$available"; then
      echo "$line"
    fi
  done
}

# Main
UPDATES=$(check_updates | filter_updates)

if [ -n "$UPDATES" ]; then
  echo "🔄 Plugin updates available:"
  echo "$UPDATES" | while read -r line; do
    [ -z "$line" ] && continue
    plugin=$(echo "$line" | cut -d' ' -f1)
    installed=$(echo "$line" | cut -d' ' -f2)
    available=$(echo "$line" | cut -d' ' -f3)
    echo "   ${plugin}: ${installed} → ${available}"
  done
  echo "   Run: claude /plugin update <name>"
fi
