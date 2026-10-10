---
name: run-organize-device
description: Audit this machine against your org identity contracts and device manifest, print a setup checklist, or snapshot the manifest
skill: organize-device
user_invocable: true
---

Check whether this machine can produce the commits and pushes your orgs' identity contracts call for, and list what is missing or wrong. See skill for full implementation.

```bash
/run-organize-device                          # audit (the default; nothing is written)
/run-organize-device --json                   # audit, machine-readable
/run-organize-device --full                   # audit plus the checks that go over the network (ssh -T, AWS account, claude marketplaces)
/run-organize-device --install                # ordered checklist, each step tagged script or you; writes nothing
/run-organize-device --install --apply        # run the script steps after your yes; creates missing things only
/run-organize-device --snapshot [--force]     # write device.toml from this machine, names only
/run-organize-device --manifest <path>        # read (or with --snapshot, write) the manifest at a path instead of ~/.config/lastmilefirst/
/run-organize-device --workspace-root <path>  # audit a workspace root other than the manifest's
```

`--install --apply` from here: Claude's shell has no terminal, so the installer's own prompt would read as "no". Run `install_device.py` for the checklist, show it to the user, and get their yes in the conversation. Then run `install_device.py --apply --yes`, adding `--clone <dir-name>` for each clone the user approved by name; a clone that is not named does not run.

Exit codes. Audit: 0 clean, 1 any `wrong` (ACTION REQUIRED), 2 only `missing` (WARNING), 3 could not run (Python below 3.11, a manifest that is not valid, a bad argument). Installer: 0 done, nothing to do, or declined; 1 an apply step failed; 3 could not run (the same causes, or `--snapshot` refusing to overwrite without `--force`).
