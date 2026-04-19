#!/usr/bin/env bash
# Regenerate contract_full.json from a real Griffith invocation.
#
# Hand-minimal fixtures (tier1_*.json, tier2_*.json) are authored
# directly against the schema doc and do NOT need regeneration.
# Only the contract fixture captures Griffith's live output format.
#
# Run this script any time Griffith's schema_version bumps, or when
# the Griffith fixture at GRIFFITH_FIXTURE_PATH changes meaningfully.
#
# Usage:
#   ./regen.sh          # write contract_full.json
#   ./regen.sh --check  # validate env without writing (exit 0 if ready)

set -euo pipefail

GRIFFITH_REPO="${GRIFFITH_REPO:-$HOME/Code/gruntwork/gruntwork-griffith}"
GRIFFITH_FIXTURE="${GRIFFITH_FIXTURE:-tests/fixtures/deps-python-plugin}"
EXPECTED_SCHEMA_VERSION="${EXPECTED_SCHEMA_VERSION:-0.1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="$SCRIPT_DIR/contract_full.json"

CHECK_ONLY=0
if [[ "${1:-}" == "--check" ]]; then
    CHECK_ONLY=1
fi

fail() {
    echo "regen.sh: ERROR: $*" >&2
    exit 1
}

# 1. Verify Griffith repo exists.
if [[ ! -d "$GRIFFITH_REPO" ]]; then
    fail "GRIFFITH_REPO=$GRIFFITH_REPO does not exist. " \
         "Clone it or set GRIFFITH_REPO to the correct path."
fi

# 2. Verify Griffith fixture exists.
if [[ ! -d "$GRIFFITH_REPO/$GRIFFITH_FIXTURE" ]]; then
    fail "Griffith fixture not found at $GRIFFITH_REPO/$GRIFFITH_FIXTURE. " \
         "Check Griffith's tests/fixtures layout or set GRIFFITH_FIXTURE."
fi

# 3. Verify Poetry venv is healthy (poetry installed and griffith runnable).
if ! command -v poetry >/dev/null 2>&1; then
    fail "poetry not found on PATH. Install: pipx install poetry"
fi

cd "$GRIFFITH_REPO"
if ! poetry env info --path >/dev/null 2>&1; then
    fail "Poetry venv not set up at $GRIFFITH_REPO. " \
         "Run: cd $GRIFFITH_REPO && poetry install"
fi

# 4. Dry-run: verify we can produce JSON and it has the expected schema version.
echo "regen.sh: running griffith analyze --json for schema verification..." >&2
OUT="$(poetry run griffith analyze "$GRIFFITH_FIXTURE" --json 2>/dev/null)"

if [[ -z "$OUT" ]]; then
    fail "griffith produced empty output. Check stderr: " \
         "cd $GRIFFITH_REPO && poetry run griffith analyze $GRIFFITH_FIXTURE --json"
fi

# Extract schema_version from the JSON without a JSON parser (awk is enough).
OBSERVED_VERSION="$(echo "$OUT" | awk -F'"' '/"schema_version":/ {print $4; exit}')"
if [[ "$OBSERVED_VERSION" != "$EXPECTED_SCHEMA_VERSION" ]]; then
    fail "schema_version drift: observed '$OBSERVED_VERSION', " \
         "expected '$EXPECTED_SCHEMA_VERSION'. " \
         "Update EXPECTED_SCHEMA_VERSION and the wrapper's " \
         "SUPPORTED_SCHEMA_VERSIONS before re-recording."
fi

if [[ "$CHECK_ONLY" == "1" ]]; then
    echo "regen.sh: environment ready; schema_version=$OBSERVED_VERSION" >&2
    exit 0
fi

# 5. Write the fixture.
echo "$OUT" > "$OUTPUT"
echo "regen.sh: wrote $OUTPUT (schema_version=$OBSERVED_VERSION)" >&2
