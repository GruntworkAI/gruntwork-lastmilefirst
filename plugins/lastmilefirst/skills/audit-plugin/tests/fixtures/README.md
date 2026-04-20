# audit-plugin test fixtures

This directory holds two categories of fixtures, deliberately separated.

## Hand-minimal fixtures

Authored directly against Griffith's `docs/json-schema.md` contract, each exercising one render branch:

| File | Branch under test |
|------|------|
| `tier1_python.json` | Tier 1 full: Python packages across `requirements.txt` + `pyproject.toml` |
| `tier1_empty.json` | Tier 1 empty: no dep manifests — Dependencies section should be omitted |
| `tier1_symlink_only.json` | Tier 1 symlink-only: every manifest is a symlink; refusal line |
| `tier1_unscanned_only.json` | Tier 1 parser-failure: only `unscanned_manifests` populated |
| `tier1_multi_ecosystem.json` | Ecosystem sort + dedup (`PyPI`, `npm`) |
| *(Tier 2 fixtures land in Unit 3)* | |

**When to edit:** when adding a new render branch test, author a new minimal fixture that exercises only that branch. Do not re-run Griffith for these — they're deliberately independent of Griffith's live output format so render-logic tests don't rot when Griffith reformats an unrelated field.

## Contract fixture

`contract_full.json` is a single captured run of `griffith analyze --json` against a real Griffith fixture. Its role is to detect Griffith format drift — when the shape of Griffith's output changes in a way the wrapper doesn't expect, the corresponding test fails loudly.

**When to regenerate:** any Griffith `schema_version` bump, or when Griffith's fixture layout meaningfully changes. Run:

```bash
./regen.sh           # writes contract_full.json
./regen.sh --check   # validates environment without writing
```

Environment variables the script honors:

| Var | Default | Purpose |
|-----|---------|---------|
| `GRIFFITH_REPO` | `~/Code/gruntwork/gruntwork-griffith` | Local checkout of Griffith |
| `GRIFFITH_FIXTURE` | `tests/fixtures/deps-python-plugin` | Path (relative to repo) of the fixture to scan |
| `EXPECTED_SCHEMA_VERSION` | `0.1` | Fails loudly if Griffith's schema bumps |

The script fails loudly (non-zero exit, stderr message) when:
- `GRIFFITH_REPO` doesn't exist
- Griffith's Poetry venv isn't set up
- `poetry run griffith analyze` returns empty output
- `schema_version` drifts from `EXPECTED_SCHEMA_VERSION`

These are the exact failures a contributor needs to see before committing a stale fixture.
