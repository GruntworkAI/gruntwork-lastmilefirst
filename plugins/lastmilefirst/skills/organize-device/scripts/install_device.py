#!/usr/bin/env python3
"""
Turn the device audit into a checklist, optionally perform its deterministic
steps, or write a device manifest from this machine.

Three modes:

    install_device.py [--manifest PATH] [--workspace-root PATH]
        Print the checklist and write nothing. Every `missing` and `wrong`
        finding from the cheap audit becomes one or two numbered steps, in the
        order a person would do them, each tagged `script` (fully determined,
        `--apply` can do it) or `you` (a browser, a secret, or judgment).

    install_device.py --apply [...]
        Print the same checklist, ask once, then perform only the `script`
        steps. It only creates (plan 3.9): it appends an includeIf stanza or an
        SSH Host block after a backup, creates a file that is absent, runs a
        package or plugin install, copies a carried manifest into place, and
        clones a project only after its own confirmation. It never modifies or
        deletes an existing line, never logs in, and never touches a secret.
        A `wrong` finding stays in the checklist as a `you` step.

    install_device.py --apply --yes [--clone DIR_NAME ...] [...]
        The same, without the prompt, for a caller (Claude) that already showed
        the checklist and got the person's yes in conversation. Clone steps run
        only when their destination directory is named with --clone.

    install_device.py --snapshot [--force] [--manifest PATH]
        Write a device manifest from this machine, names only.

Exit codes: 0 done (or nothing to do, or declined), 1 an `--apply` step
failed, 3 could not run (Python older than 3.11, an invalid manifest, a bad
argument, or `--snapshot` refusing to overwrite).

Standard library only.
"""
from __future__ import annotations

import sys

MIN_PYTHON = (3, 11)
EXIT_CANNOT_RUN = 3

if tuple(sys.version_info[:2]) < MIN_PYTHON:  # pragma: no cover - old interpreters only
    sys.stderr.write("organize-device needs Python %d.%d or newer; this is Python %d.%d.\n"
                     % (MIN_PYTHON + tuple(sys.version_info[:2])))
    sys.exit(EXIT_CANNOT_RUN)

import argparse  # noqa: E402
import datetime as _dt  # noqa: E402
import glob  # noqa: E402
import importlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import pkgutil  # noqa: E402
import re  # noqa: E402
import shlex  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tomllib  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable, Optional  # noqa: E402

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import audit_device  # noqa: E402
from audit_device import (  # noqa: E402
    MISSING,
    WRONG,
    AuditContext,
    Finding,
    TOOL_BINARY,
    expand,
    load_contracts,
    parse_git_config,
    parse_ssh_config,
    read_git_config,
    git_get,
    run_audit,
    tilde,
)
from device_manifest import (  # noqa: E402
    DEFAULT_WORKSPACE_ROOT,
    NETWORK_NONE,
    ManifestError,
    default_manifest_path,
    load_manifest,
    parse_manifest,
)

SCRIPT = "script"
YOU = "you"

CLI_TIMEOUT = 30
STEP_INDENT = "      "

# Order a person would work the list in: packages first, keys before SSH
# aliases, aliases before logins, logins before clones. Unknown sections land
# between the known ones and the clones.
_RANK_PLATFORM = -1
_RANK_PACKAGE = 0
_RANK_MANIFEST = 1
_RANK_KEY = 2
_RANK_SSH = 3
_RANK_LOGIN = 4
_RANK_UNKNOWN = 50
_RANK_WORKSPACE = 90
_RANK_CLONE = 99
_SECTION_RANK = {
    "Platform": _RANK_PLATFORM,
    "Tools": _RANK_PACKAGE,
    "Device manifest": _RANK_MANIFEST,
    "SSH": _RANK_SSH,
    "GitHub logins": _RANK_LOGIN,
    "git identity": 5,
    "Claude Code": 6,
    "AWS": 7,
    "Keychain": 8,
    "Network": 9,
    "Workspace": _RANK_WORKSPACE,
}


# --------------------------------------------------------------------------
# steps
# --------------------------------------------------------------------------

@dataclass
class Action:
    """What `--apply` does for one `script` step."""

    kind: str                              # package, git_include, ssh_block, claude, clone, manifest
    run: Callable[["ApplyState"], tuple[bool, str]]
    confirm_each: bool = False             # clones: one more confirmation per row
    dest: Optional[str] = None             # clones: destination directory name, for --clone


@dataclass
class Step:
    tag: str
    section: str
    org: Optional[str]
    message: str
    body: str
    rank: int
    action: Optional[Action] = None
    number: int = 0


@dataclass
class ApplyState:
    """Per-run state: one backup per file, taken before the first write."""

    stamp: str
    workspace_root: Path
    backups: dict[Path, Path] = field(default_factory=dict)


def _strip_code(line: str) -> str:
    line = line.strip()
    if len(line) >= 2 and line[0] == line[-1] == "`":
        line = line[1:-1].strip()
    return line


def _run_command(argv: list[str], cwd: Optional[Path] = None) -> tuple[bool, str]:
    """Run a command with the terminal attached, so installers can prompt."""
    try:
        result = subprocess.run(argv, cwd=str(cwd) if cwd else None)
    except (FileNotFoundError, OSError) as exc:
        return False, f"could not run {argv[0]}: {exc}"
    if result.returncode != 0:
        return False, f"{shlex.join(argv)} exited {result.returncode}"
    return True, shlex.join(argv)


def _expand_args(argv: list[str]) -> list[str]:
    home = Path.home()
    return [str(expand(a, home)) if a == "~" or a.startswith("~/") else a for a in argv]


# --- classifiers: a `missing` remedy the skill can perform -------------------

_PACKAGE_RE = re.compile(r"^(brew install|sudo apt-get install -y) [A-Za-z0-9@/_.+-]+$")
_GIT_INCLUDE_RE = re.compile(
    r'^Append to ~/\.gitconfig:\n'
    r'(?P<stanza>\[includeIf "gitdir:(?P<gitdir>[^"\n]+)"\]\n\tpath = (?P<path>\S+))\n'
    r'Create (?P<create>\S+) with:\n'
    r'(?P<user>\[user\]\n\tname = [^\n]+\n\temail = [^\n]+)$'
)
_SSH_BLOCK_RE = re.compile(
    r"^Append to ~/\.ssh/config:\n(?P<block>Host (?P<host>\S+)(?:\n    [^\n]+)+)$"
)
_CLAUDE_LINE_RE = re.compile(r"^claude plugin (marketplace add|install) \S+(?: \S+)*$")
_CLONE_RE = re.compile(r"^(gh repo clone|git clone) \S+")


def _package_action(command: str) -> Optional[Action]:
    command = _strip_code(command)
    if command == audit_device.CLAUDE_INSTALL:
        return Action("package", lambda state: _run_command(["bash", "-c", command]))
    if _PACKAGE_RE.match(command):
        return Action("package", lambda state: _run_command(shlex.split(command)))
    return None


def _git_include_action(remedy: str) -> Optional[Action]:
    match = _GIT_INCLUDE_RE.match(remedy.strip())
    if not match:
        return None
    stanza, gitdir, path = match["stanza"], match["gitdir"], match["path"]
    if match["create"] != path or not _safe_home_file(path) or not gitdir.startswith("~"):
        return None
    user_text = match["user"]
    return Action("git_include",
                  lambda state: apply_git_include(state, stanza,
                                                  expand(gitdir.rstrip("/"), Path.home()),
                                                  gitdir, path, user_text))


def _ssh_block_action(remedy: str) -> Optional[Action]:
    match = _SSH_BLOCK_RE.match(remedy.strip())
    if not match:
        return None
    block, host = match["block"], match["host"]
    return Action("ssh_block", lambda state: apply_ssh_block(state, host, block))


def _claude_action(remedy: str) -> Optional[Action]:
    lines = [_strip_code(l) for l in remedy.strip().splitlines() if l.strip()]
    if not lines or not all(_CLAUDE_LINE_RE.match(l) for l in lines):
        return None

    def run(state: ApplyState) -> tuple[bool, str]:
        done = []
        for line in lines:
            ok, detail = _run_command(shlex.split(line))
            if not ok:
                return False, detail
            done.append(detail)
        return True, "; ".join(done)

    return Action("claude", run)


def _clone_action(remedy: str) -> Optional[Action]:
    first = _strip_code(remedy.strip().splitlines()[0]) if remedy.strip() else ""
    if not _CLONE_RE.match(first) or "(specify)" in first:
        return None  # an unknown owner is not a determined command

    def run(state: ApplyState) -> tuple[bool, str]:
        cwd = state.workspace_root if state.workspace_root.is_dir() else Path.home()
        return _run_command(_expand_args(shlex.split(first)), cwd=cwd)

    return Action("clone", run, confirm_each=True, dest=_clone_dest(shlex.split(first)))


def _clone_dest(argv: list[str]) -> Optional[str]:
    """The destination directory name of a clone command: its last argument's basename."""
    if len(argv) < 4:
        return None  # no explicit destination; git would pick the repo name
    return Path(argv[-1].rstrip("/")).name or None


# --- structured actions (Finding.action, when the audit provides one) ----------

def _text(value: Any) -> Optional[str]:
    if isinstance(value, Path):
        return str(value)
    return value if isinstance(value, str) and value.strip() else None


def _from_structured(action: Any) -> Optional[Action]:
    """An Action built from the audit's `Finding.action` dict, executed from its fields.

    Returns None for an unknown kind or a malformed payload, so the step falls
    back to the remedy-text path (and from there, most likely, to `you`).
    """
    if not isinstance(action, dict):
        return None
    kind = action.get("kind")
    home = Path.home()
    if kind == "package":
        manager, name = _text(action.get("manager")), _text(action.get("name"))
        if not name or not re.fullmatch(r"[A-Za-z0-9@/_.+-]+", name):
            return None
        if manager == "brew":
            argv = ["brew", "install", name]
        elif manager == "apt":
            argv = ["sudo", "apt-get", "install", "-y", name]
        else:
            return None
        return Action("package", lambda state: _run_command(argv))
    if kind == "git_include":
        org_dir, include = _text(action.get("org_dir")), _text(action.get("include_path"))
        stanza, file_text = _text(action.get("stanza")), _text(action.get("file_text"))
        if not (org_dir and include and stanza and file_text):
            return None
        include_text = tilde(expand(include, home), home)
        if not _safe_home_file(include_text):
            return None
        org_path = expand(org_dir.rstrip("/"), home) if org_dir != "~" else home
        shown = tilde(org_path, home).rstrip("/") + "/"
        return Action("git_include", lambda state: apply_git_include(
            state, stanza.strip(), org_path, shown, include_text, file_text.strip()))
    if kind == "ssh_block":
        host, block = _text(action.get("host")), _text(action.get("block"))
        if not host or not block or not block.lstrip().lower().startswith("host "):
            return None
        return Action("ssh_block", lambda state: apply_ssh_block(state, host, block.strip()))
    if kind in ("plugin_marketplace_add", "plugin_install"):
        entry = _text(action.get("entry"))
        if not entry or any(c.isspace() for c in entry):
            return None
        argv = ["claude", "plugin", "marketplace", "add", entry] \
            if kind == "plugin_marketplace_add" else ["claude", "plugin", "install", entry]
        return Action("claude", lambda state: _run_command(argv))
    if kind == "clone":
        command = action.get("command")
        argv = shlex.split(command) if isinstance(command, str) else \
            list(command) if isinstance(command, (list, tuple)) else None
        if not argv or "(specify)" in " ".join(argv) or \
                not _CLONE_RE.match(" ".join(argv)):
            return None
        dest = _text(action.get("dest"))
        name = Path(dest.rstrip("/")).name if dest else _clone_dest(argv)

        def run(state: ApplyState) -> tuple[bool, str]:
            cwd = state.workspace_root if state.workspace_root.is_dir() else Path.home()
            return _run_command(_expand_args(argv), cwd=cwd)

        return Action("clone", run, confirm_each=True, dest=name)
    return None


# What `--apply` may do is an allow-list. Deliberately left as `you` steps, even
# though each is deterministic:
#   - `git config --global user.name/user.email` for an unset global identity: it
#     writes the global [user] section, which is the default org's identity, so
#     the person sets it.
#   - `claude plugin enable <plugin>`: it flips an existing setting rather than
#     creating something, and apply only creates.
#   - `/run-scan-secrets --install-hooks`: it sets core.hooksPath, an existing
#     global setting other tools may own.
def classify(finding: Finding) -> Optional[Action]:
    """The action for a `missing` finding whose result is fully determined, else None.

    A structured `finding.action` from the audit is preferred and executed from
    its fields. Without one, only allow-listed remedy text shapes qualify (a
    fallback for audits that predate the field). Anything else, including
    every `wrong` finding, is a `you` step.
    """
    if finding.finding_class != MISSING:
        return None
    structured = getattr(finding, "action", None)
    if structured is not None:
        return _from_structured(structured)
    if not finding.remedy:
        return None
    section = finding.section or ""
    remedy = finding.remedy
    if section == "Tools":
        return _package_action(remedy)
    if section == "git identity":
        return _git_include_action(remedy)
    if section == "SSH":
        return _ssh_block_action(remedy)
    if section == "Claude Code":
        return _claude_action(remedy)
    if section == "Workspace":
        return _clone_action(remedy)
    return None


def _rank(finding: Finding, part: str, action: Optional[Action]) -> int:
    section = finding.section or ""
    structured = getattr(finding, "action", None)
    if isinstance(structured, dict) and structured.get("kind") == "clone":
        return _RANK_CLONE
    if isinstance(structured, dict) and structured.get("kind") == "package":
        return _RANK_PACKAGE
    if section == "Workspace" and finding.remedy and \
            _CLONE_RE.match(_strip_code(finding.remedy.strip().splitlines()[0])):
        return _RANK_CLONE  # clones last, runnable or not
    if action is not None and action.kind == "package":
        return _RANK_PACKAGE
    if section == "SSH" and part == "you":
        return _RANK_KEY  # key generation and upload come before the alias that uses the key
    return _SECTION_RANK.get(section, _RANK_UNKNOWN)


def steps_from_findings(findings: list[Finding]) -> list[Step]:
    steps: list[Step] = []
    for finding in findings:
        if finding.finding_class not in (MISSING, WRONG):
            # A note can still hand over a step (a stopped network provider's sign-in
            # command). It is never an alert, so it renders as an optional `you` step.
            if finding.you:
                steps.append(Step(YOU, finding.section or "Other", finding.org,
                                  f"{finding.message} (optional)", finding.you,
                                  _rank(finding, "you", None)))
            continue
        section = finding.section or "Other"
        if finding.remedy or getattr(finding, "action", None) is not None:
            action = classify(finding)
            steps.append(Step(SCRIPT if action else YOU, section, finding.org, finding.message,
                              finding.remedy or "", _rank(finding, "remedy", action), action))
        if finding.you:
            steps.append(Step(YOU, section, finding.org, finding.message, finding.you,
                              _rank(finding, "you", None)))
        if not finding.remedy and not finding.you and getattr(finding, "action", None) is None:
            steps.append(Step(YOU, section, finding.org, finding.message, "",
                              _rank(finding, "remedy", None)))
    steps.sort(key=lambda s: s.rank)  # stable: audit order within a rank
    for number, step in enumerate(steps, start=1):
        step.number = number
    return steps


def manifest_copy_step(source: Optional[Path], target: Path) -> Optional[Step]:
    """A `script` step copying a carried `--manifest` file into place, when none is there."""
    if source is None or not source.is_file() or target.exists():
        return None
    try:
        if source.resolve() == target.resolve():
            return None
    except OSError:
        pass
    home = Path.home()
    shown_target = tilde(target, home)
    return Step(
        SCRIPT, "Device manifest", None,
        f"No device manifest at {shown_target}; the one passed with --manifest can go there.",
        f"cp {shlex.quote(tilde(source, home))} {shown_target}",
        _RANK_MANIFEST,
        Action("manifest", lambda state: apply_manifest_copy(source)),
    )


# --------------------------------------------------------------------------
# writers (create only)
# --------------------------------------------------------------------------

def _safe_home_file(text: str) -> bool:
    """A `~/name` path directly in home, the only shape an include file takes here."""
    return bool(re.fullmatch(r"~/\.[A-Za-z0-9._-]+", text)) and ".." not in text


def _backup(state: ApplyState, path: Path, mode: Optional[int] = None) -> Optional[Path]:
    """Copy `path` beside itself once per run, before the first write to it."""
    if path in state.backups or not path.exists():
        return state.backups.get(path)
    backup = path.with_name(f"{path.name}.bak-{state.stamp}")
    n = 2
    while backup.exists():
        backup = path.with_name(f"{path.name}.bak-{state.stamp}-{n}")
        n += 1
    shutil.copy2(path, backup)
    if mode is not None:
        backup.chmod(mode)
    state.backups[path] = backup
    return backup


def _append(path: Path, text: str) -> None:
    """Append `text` as its own paragraph; existing bytes are left exactly as they were."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lead = ""
    if existing:
        lead = "\n" if existing.endswith("\n") else "\n\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{lead}{text}\n")


def apply_git_include(state: ApplyState, stanza: str, org_dir: Path, gitdir: str,
                      path_text: str, user_text: str) -> tuple[bool, str]:
    """Create the include file if absent, then append the stanza. `gitdir` is for messages."""
    home = Path.home()
    gitconfig = home / ".gitconfig"
    include = expand(path_text, home)

    existing = read_git_config(gitconfig) or []
    for current in existing:
        target = audit_device._gitdir_target(current)
        if target is not None and audit_device._gitdir_matches(target, org_dir, home):
            return False, (f"~/.gitconfig already has an includeIf for {gitdir}; left alone "
                           f"(rerun the audit)")

    want = parse_git_config(user_text)
    created = False
    if include.exists():
        have = read_git_config(include)
        if have is None:
            return False, f"{path_text} exists and cannot be read; left alone"
        for key in ("name", "email"):
            if git_get(have, "user", key) != git_get(want, "user", key):
                return False, (f"{path_text} already exists with a different user.{key}; left "
                               f"alone, and the stanza was not added because it would apply "
                               f"that identity. Fix the file by hand, then rerun")
    else:
        include.write_text(user_text + "\n", encoding="utf-8")
        created = True

    backup = _backup(state, gitconfig)
    _append(gitconfig, stanza)
    parts = []
    if created:
        parts.append(f"created {path_text}")
    parts.append(f"appended the includeIf for {gitdir} to ~/.gitconfig")
    if backup is not None:
        parts.append(f"backup {tilde(backup, home)}")
    return True, "; ".join(parts)


_SSH_KEYWORD_RE = re.compile(r"^\s*(\S+?)(?:\s*=\s*|\s+)(.*)$")


def _ssh_files(config: Path) -> list[Path]:
    """The config plus every file its Include lines name (relative to ~/.ssh)."""
    files = [config]
    ssh_dir = config.parent
    try:
        text = config.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return files
    for line in text.splitlines():
        match = _SSH_KEYWORD_RE.match(line)
        if not match or match.group(1).lower() != "include":
            continue
        for pattern in match.group(2).split():
            expanded = expand(pattern.strip('"'), Path.home())
            if not expanded.is_absolute():
                expanded = ssh_dir / expanded
            files.extend(Path(p) for p in sorted(glob.glob(str(expanded))) if Path(p).is_file())
    return files


def ssh_host_defined(config: Path, host: str) -> Optional[Path]:
    """The file that already names `host` in a Host or Match line, in any case or form."""
    wanted = host.lower()
    for path in _ssh_files(config):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            match = _SSH_KEYWORD_RE.match(line)
            if not match or match.group(1).lower() not in ("host", "match"):
                continue
            tokens = [t.strip('"').lower() for t in re.split(r"[\s,]+", match.group(2)) if t]
            if wanted in tokens:
                return path
        if any(wanted in (p.lower() for p in b.patterns) for b in parse_ssh_config(text)):
            return path
    return None


def apply_ssh_block(state: ApplyState, host: str, block: str) -> tuple[bool, str]:
    home = Path.home()
    ssh_dir = home / ".ssh"
    config = ssh_dir / "config"
    if config.exists():
        where = ssh_host_defined(config, host)
        if where is not None:
            return False, (f"refused: a Host {host} block already exists in "
                           f"{tilde(where, home)}; nothing was written")
    if not ssh_dir.exists():
        ssh_dir.mkdir(mode=0o700, parents=True)
    backup = _backup(state, config, mode=0o600)
    _append(config, block)
    config.chmod(0o600)
    detail = f"appended Host {host} to ~/.ssh/config (mode 600)"
    if backup is not None:
        detail += f"; backup {tilde(backup, home)}"
    return True, detail


def apply_manifest_copy(source: Path) -> tuple[bool, str]:
    home = Path.home()
    target = default_manifest_path(home=home)
    if target.exists():
        return False, f"{tilde(target, home)} already exists; left alone"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True, f"copied {tilde(source, home)} to {tilde(target, home)}"


# --------------------------------------------------------------------------
# checklist and apply
# --------------------------------------------------------------------------

def build_context(manifest_arg: Optional[Path], root_arg: Optional[Path]) -> AuditContext:
    """The same context audit_device.main builds, cheap mode. Raises ManifestError.

    Uses audit_device.build_context. The copy below is a fallback for an
    audit_device that predates it or changes its keywords (U3 and U4 were built
    in parallel, 2026-10-09); it mirrors main() and would drift if main() did.
    """
    shared = getattr(audit_device, "build_context", None)
    if callable(shared):
        try:
            return shared(manifest=manifest_arg, workspace_root=root_arg)
        except TypeError:
            pass  # a different signature than expected; use the local copy
    home = Path.home()
    manifest_path = expand(str(manifest_arg), home) if manifest_arg else \
        default_manifest_path(home=home)
    manifest = load_manifest(manifest_path if manifest_arg else None)
    root = expand(str(root_arg), home) if root_arg else expand(manifest.workspace_root, home)
    return AuditContext(home=home, workspace_root=root, manifest=manifest,
                        manifest_path=manifest_path, full=False, liveness=False,
                        contracts=load_contracts(root))


def build_steps(ctx: AuditContext, manifest_arg: Optional[Path]) -> list[Step]:
    findings = [f for _, found in run_audit(ctx) for f in found]
    steps = steps_from_findings(findings)
    source = expand(str(manifest_arg), ctx.home) if manifest_arg else None
    copy = manifest_copy_step(source, default_manifest_path(home=ctx.home))
    if copy is not None:
        steps.append(copy)
        steps.sort(key=lambda s: s.rank)
        for number, step in enumerate(steps, start=1):
            step.number = number
    return steps


def render_checklist(ctx: AuditContext, steps: list[Step]) -> None:
    print(f"Device checklist for {tilde(ctx.workspace_root, ctx.home)} "
          f"(from the cheap audit; this writes nothing)")
    if not steps:
        print("Nothing to do: the audit found nothing missing or wrong.")
        return
    width = len(str(len(steps)))
    for step in steps:
        where = f"{step.section} ({step.org})" if step.org else step.section
        print()
        print(f"{step.number:>{width}}. [{step.tag}] {where}: {step.message}")
        for line in step.body.splitlines():
            print(f"{STEP_INDENT}{line}")
    scripts = sum(1 for s in steps if s.tag == SCRIPT)
    yours = len(steps) - scripts
    print()
    print(f"{scripts} script step{'' if scripts == 1 else 's'}, "
          f"{yours} you step{'' if yours == 1 else 's'}.")


def ask(prompt: str) -> bool:
    """One yes/no question. A non-interactive stdin is a no."""
    stdin = sys.stdin
    if stdin is None or not stdin.isatty():
        print(f"{prompt}no (stdin is not a terminal, so nothing runs; run --apply in a "
              f"terminal to answer)")
        return False
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def apply_steps(ctx: AuditContext, steps: list[Step], yes: bool = False,
                clones: Optional[list[str]] = None) -> int:
    """Perform the `script` steps.

    Interactive: one confirmation, then one more per clone. With `yes` (the
    caller confirmed in conversation, after showing the checklist) nothing is
    asked; clones run only when their destination name is in `clones`.
    """
    scripts = [s for s in steps if s.tag == SCRIPT and s.action is not None]
    selected = set(clones or [])
    print()
    if not scripts:
        print("No script steps to run.")
        return 0
    if yes:
        print("--yes: running the script steps without asking.")
    elif not ask(f"Run the {len(scripts)} script step{'' if len(scripts) == 1 else 's'} "
                 f"above? [y/N] "):
        print("Nothing was changed.")
        return 0
    state = ApplyState(stamp=_dt.datetime.now().strftime("%Y%m%dT%H%M%S"),
                       workspace_root=ctx.workspace_root)
    done = failed = skipped = 0
    for step in scripts:
        if step.action.confirm_each and yes:
            dest = step.action.dest
            if dest is None or dest not in selected:
                hint = f"--clone {dest}" if dest else "--clone <dir-name>"
                print(f"{step.number}. skipped: clones run under --yes only when named; "
                      f"pass {hint} to run this one")
                skipped += 1
                continue
        elif step.action.confirm_each:
            first = (step.body.strip().splitlines() or [step.message])[0]
            if not ask(f"{step.number}. {_strip_code(first)}? [y/N] "):
                print(f"{step.number}. skipped")
                skipped += 1
                continue
        try:
            ok, detail = step.action.run(state)
        except OSError as exc:
            ok, detail = False, f"{exc.strerror or exc}"
        print(f"{step.number}. {'done' if ok else 'failed'}: {detail}")
        if ok:
            done += 1
        else:
            failed += 1
    yours = sum(1 for s in steps if s.tag == YOU)
    print()
    print(f"{done} done, {failed} failed, {skipped} skipped; {yours} you "
          f"step{'' if yours == 1 else 's'} left as printed. Rerun to see what remains.")
    return 1 if failed else 0


# --------------------------------------------------------------------------
# snapshot
# --------------------------------------------------------------------------

SNAPSHOT_TOOLS = ("uv", "poetry", "terraform", "awscli", "gitleaks", "deno", "ffmpeg",
                  "docker", "shellcheck")
HOOK_KINDS = ("pre-commit", "pre-push")


def _cli_json(args: list[str]) -> Optional[Any]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=CLI_TIMEOUT,
                                stdin=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _read_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _marketplace_ref(name: str, source: Any) -> str:
    """`owner/repo` for a GitHub marketplace (what `marketplace add` takes), else its url,
    path, or name."""
    if isinstance(source, dict):
        for key in ("repo", "url", "path"):
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
    return name


def snapshot_claude(home: Path) -> tuple[list[str], list[str]]:
    marketplaces: Optional[list[str]] = None
    listed = _cli_json(["claude", "plugin", "marketplace", "list", "--json"])
    if isinstance(listed, list):
        marketplaces = []
        for entry in listed:
            if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                marketplaces.append(_marketplace_ref(entry["name"], entry))
    if marketplaces is None:
        known = _read_json(home / ".claude" / "plugins" / "known_marketplaces.json")
        marketplaces = []
        if isinstance(known, dict):
            for name, value in known.items():
                source = value.get("source") if isinstance(value, dict) else None
                marketplaces.append(_marketplace_ref(name, source))

    plugins: Optional[list[str]] = None
    listed = _cli_json(["claude", "plugin", "list", "--json"])
    if isinstance(listed, list):
        plugins = [e["id"] for e in listed
                   if isinstance(e, dict) and isinstance(e.get("id"), str)
                   and e.get("enabled", True) and e.get("scope", "user") == "user"]
    if plugins is None:
        settings = _read_json(home / ".claude" / "settings.json")
        enabled = settings.get("enabledPlugins") if isinstance(settings, dict) else None
        plugins = [k for k, v in enabled.items() if v is True] if isinstance(enabled, dict) \
            else []
    return list(dict.fromkeys(marketplaces)), list(dict.fromkeys(plugins))


def snapshot_hooks(home: Path) -> list[str]:
    """Which scan-secrets global dispatchers exist.

    scan-secrets' hook_installer.py writes them to
    ~/.claude/lastmilefirst/git-hooks/<kind>; its HOOKS_DIR is computed at import
    time, so the location is restated here rather than imported.
    """
    hooks_dir = home / ".claude" / "lastmilefirst" / "git-hooks"
    return [kind for kind in HOOK_KINDS if (hooks_dir / kind).is_file()]


_INI_HEADER_RE = re.compile(r"^\s*\[\s*([^\]]+?)\s*\]\s*$")


def aws_files(home: Path) -> tuple[Path, Path]:
    """(config, credentials), honoring AWS_CONFIG_FILE and AWS_SHARED_CREDENTIALS_FILE.

    Mirrors audit_device.aws_profiles_on_disk, which returns an unordered set;
    the snapshot keeps file order, so the resolution is restated here.
    """
    config = Path(os.environ.get("AWS_CONFIG_FILE") or home / ".aws" / "config")
    creds = Path(os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
                 or home / ".aws" / "credentials")
    return config, creds


def _ini_headers(path: Path) -> list[str]:
    """Section names only. No other line is kept or parsed."""
    names: list[str] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                match = _INI_HEADER_RE.match(line)
                if match:
                    names.append(match.group(1))
    except (OSError, UnicodeDecodeError):
        return []
    return names


def snapshot_aws_profiles(home: Path) -> list[str]:
    """Profile names, by the audit's rule: in config, `default` and `profile <name>`
    (so `sso-session` and `services` sections are skipped); in credentials, every
    section."""
    config, creds = aws_files(home)
    names: list[str] = []
    for name in _ini_headers(config):
        if name == "default":
            names.append(name)
        elif name.startswith("profile "):
            names.append(name[len("profile "):].strip())
    names.extend(_ini_headers(creds))
    return list(dict.fromkeys(n for n in names if n))


def _provider_names(package: Any, package_dir: Path) -> list[str]:
    available = getattr(package, "available", None)
    if callable(available):
        return [n for n in available() if n != NETWORK_NONE]
    return sorted(i.name for i in pkgutil.iter_modules([str(package_dir)])
                  if not i.name.startswith("_") and i.name != NETWORK_NONE)


def snapshot_network() -> tuple[str, Optional[dict[str, Any]], Optional[str]]:
    """(provider, its table or None, a note). The provider package is imported lazily.

    Each provider's `detect()` returns a mapping with at least `installed` and
    `running`; any other keys are names it read safely (a tailnet name) and
    become that provider's `[network.<name>]` table. The first running provider
    wins; with none running, or no provider package, the result is "none".
    """
    package_dir = _HERE / "network"
    if not (package_dir / "__init__.py").is_file():
        return NETWORK_NONE, None, None
    try:
        package = importlib.import_module("network")
        origin = Path(getattr(package, "__file__", "") or "").resolve().parent
        if origin != package_dir.resolve():
            return NETWORK_NONE, None, f"a different module named network is loaded ({origin})"
        names = _provider_names(package, package_dir)
    except Exception as exc:  # a broken provider package must not stop the snapshot
        return NETWORK_NONE, None, f"could not import scripts/network: {exc}"
    for name in names:
        try:
            module = importlib.import_module(f"network.{name}")
            detect = getattr(module, "detect", None)
            if detect is None:
                continue
            result = detect()
        except Exception as exc:
            return NETWORK_NONE, None, f"network provider {name} failed to detect: {exc}"
        if isinstance(result, bool):
            running, table = result, {}
        elif isinstance(result, dict):
            running = bool(result.get("running"))
            table = result.get("table") if isinstance(result.get("table"), dict) else \
                {k: v for k, v in result.items() if k not in ("installed", "running")}
        else:
            running, table = bool(getattr(result, "running", False)), {}
        if running:
            return name, dict(table), None
    return NETWORK_NONE, None, None


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise ValueError(f"cannot write {type(value).__name__} to the manifest")


def _comment_col(line: str, comment: str, width: int = 44) -> str:
    return f"{line.ljust(width - 1)} # {comment}"


def render_snapshot(root: str, tools: list[str], marketplaces: list[str],
                    plugins: list[str], hooks: list[str], profiles: list[str],
                    provider: str, provider_table: Optional[dict[str, Any]],
                    today: str) -> str:
    lines = [
        "# Device manifest for /run-organize-device.",
        f"# Written by install_device.py --snapshot on {today}. Names only: no key, token,",
        "# password, or credential value is read or recorded. Accounts, commit emails, and",
        "# SSH host aliases live in each org's .claude/org.json and are not copied here.",
        "",
        "[workspace]",
        f"root = {_toml_value(root)}",
        "",
        "[tools]",
        _comment_col(f"extra = {_toml_value(tools)}", "beyond the baseline; found on PATH"),
        "",
        "[claude]",
        f"marketplaces = {_toml_value(marketplaces)}",
        f"plugins = {_toml_value(plugins)}",
        _comment_col(f"hooks = {_toml_value(hooks)}", "scan-secrets hooks found installed"),
        "",
        "[aws]",
        _comment_col(f"profiles = {_toml_value(profiles)}", "names only"),
        _comment_col('default_profile_is = "(specify)"',
                     "a label for the default profile; fill in"),
        "",
        "[keychain]",
        "# Left empty on purpose: the skill cannot tell which keychain entries matter to",
        "# you, and it never lists the keychain. Add the item names whose presence the",
        "# audit should check, e.g. items = [\"example-item\"].",
        "items = []",
        "",
        "[network]",
        _comment_col(f"provider = {_toml_value(provider)}",
                     "a running shipped provider, else \"none\""),
    ]
    if provider != NETWORK_NONE and provider_table is not None:
        lines += ["", f"[network.{provider}]"]
        if not provider_table:
            lines.append(f"# Fill in the keys documented in scripts/network/{provider}.py.")
        for key, value in provider_table.items():
            lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def snapshot(manifest_arg: Optional[Path], root_arg: Optional[Path], force: bool) -> int:
    home = Path.home()
    target = expand(str(manifest_arg), home) if manifest_arg else default_manifest_path(home=home)
    if target.exists() and not force:
        print(f"{tilde(target, home)} already exists; pass --force to overwrite it.",
              file=sys.stderr)
        return EXIT_CANNOT_RUN

    tools = [t for t in SNAPSHOT_TOOLS if shutil.which(TOOL_BINARY.get(t, t))]
    marketplaces, plugins = snapshot_claude(home)
    hooks = snapshot_hooks(home)
    profiles = snapshot_aws_profiles(home)
    provider, table, note = snapshot_network()
    if note:
        print(f"note: {note}; wrote provider = \"none\".", file=sys.stderr)
    if root_arg:
        root = tilde(expand(str(root_arg), home), home)
    else:
        root = DEFAULT_WORKSPACE_ROOT
        if target.exists():  # --force over a manifest: keep its root; ignore it if invalid
            try:
                root = load_manifest(target).workspace_root
            except ManifestError:
                pass
    text = render_snapshot(root, tools, marketplaces, plugins, hooks, profiles, provider,
                           table, _dt.date.today().isoformat())
    try:
        parse_manifest(tomllib.loads(text))
    except (tomllib.TOMLDecodeError, ManifestError, ValueError) as exc:
        print(f"Snapshot did not validate, nothing written: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"Wrote {tilde(target, home)}: {len(tools)} extra tools, {len(marketplaces)} "
          f"marketplaces, {len(plugins)} plugins, {len(hooks)} hooks, {len(profiles)} AWS "
          f"profiles, network provider {provider}. Set aws.default_profile_is and "
          f"keychain.items by hand.")
    return 0


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = audit_device._Parser(
        description="Print the device checklist, perform its script steps, or write a "
                    "device manifest from this machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit codes:\n"
            "  0  done, nothing to do, or declined\n"
            "  1  an --apply step failed\n"
            "  3  could not run (Python older than 3.11, an invalid manifest, a bad\n"
            "     argument, or --snapshot refusing to overwrite)\n"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true",
                      help="after one confirmation, perform the script steps (creates only)")
    mode.add_argument("--snapshot", action="store_true",
                      help="write a device manifest from this machine, names only")
    parser.add_argument("--yes", action="store_true",
                        help="with --apply, skip the confirmation (for a caller that already "
                             "showed the checklist and got a yes); clones still need --clone")
    parser.add_argument("--clone", action="append", default=[], metavar="DIR_NAME",
                        help="with --apply --yes, also run the clone step whose destination "
                             "directory is named DIR_NAME (repeatable)")
    parser.add_argument("--install", action="store_true",
                        help="print the checklist (the default; accepted for symmetry)")
    parser.add_argument("--force", action="store_true",
                        help="with --snapshot, overwrite an existing manifest")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="read (or with --snapshot, write) the manifest at this path")
    parser.add_argument("--workspace-root", type=Path, default=None,
                        help="workspace root holding the org directories")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.force and not args.snapshot:
        parser.error("--force only applies to --snapshot")
    if args.yes and not args.apply:
        parser.error("--yes only applies to --apply")
    if args.clone and not args.yes:
        parser.error("--clone only applies to --apply --yes (interactive --apply asks per clone)")
    if args.snapshot:
        return snapshot(args.manifest, args.workspace_root, args.force)
    try:
        ctx = build_context(args.manifest, args.workspace_root)
    except ManifestError as exc:
        print(f"Device manifest error: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN
    steps = build_steps(ctx, args.manifest)
    render_checklist(ctx, steps)
    if args.apply:
        return apply_steps(ctx, steps, yes=args.yes, clones=args.clone)
    if any(s.tag == SCRIPT for s in steps):
        print("Run with --apply to perform the script steps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
