# Bounded local audit runner

Resolve CORE to the directory containing lastmilefirst/SKILL.md, then run:

```sh
python3 -B "$CORE/scripts/audit.py" --project "$APPROVED_PROJECT"
python3 -B "$CORE/scripts/audit.py" --project "$APPROVED_PROJECT" --org "$APPROVED_ORG"
python3 -B "$CORE/scripts/audit.py" --project "$APPROVED_PROJECT" --org "$APPROVED_ORG" --workspace "$APPROVED_WORKSPACE"
python3 -B "$CORE/scripts/audit.py" --project "$APPROVED_PROJECT" --context-name CLAUDE.md
```

Only pass approved readable roots. Do not infer approval from placeholders in examples.
Project defaults to the current directory and must be inside the supplied org. For an org-only review, pass the org root as both --project and --org; the org itself is not counted as a project. Org enables direct projects plus one marked client
tier; workspace adds context and direct org identity claims, not all-workspace project discovery.
The runner prints JSON to stdout and never saves the report. Exit 0 means a report was produced,
not that findings passed; exit 2 means invalid scope or unavailable dependencies. Read the
status, coverage, limitations, findings, and per-project evidence before summarizing.

JSON schema_version 1 includes mode, status, scope, coverage, hierarchy, organization, projects,
and findings. Status is complete, partial, or error; findings contain severity, code, path, and
message. Review project/org context and inspected hierarchy independently of the coverage label.

The wrapper uses only local reads and bounded Git metadata queries. It does not run repo code,
network checks, hooks, secret scans, or canonical stateful CLIs. It disables Python bytecode
writes itself; -B also protects imports when run through unusual launchers. Git inherited
identity may be unresolved because home/global config and includes are outside the bounded
inspection; disclose this instead of claiming the effective commit identity is known.

Only headings, inventory, local contract fields, and artifact metadata are machine-checked.
Read content for meaning where authorized. Don't equate file age, an old record, or an empty
heading with a stale project or a successful semantic review.
