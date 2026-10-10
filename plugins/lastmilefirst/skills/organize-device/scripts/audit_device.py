#!/usr/bin/env python3
"""
Audit whether this machine can produce the commits and pushes the org
contracts call for.

organize-orgs answers "do the contracts and repos agree." This script answers
the device half: is the tooling installed, is every declared GitHub account
logged in to `gh`, does each SSH host alias exist with its key on disk, and is
there a git identity include for every org directory that has a contract.

Inputs, all read from local disk:

    <workspace>/<org>/.claude/org.json      identity contracts (authoritative)
    ~/.config/lastmilefirst/device.toml     the device manifest (optional)
    ~/.ssh/config, ~/.gitconfig, includes   what the machine actually does

Every finding is one of two classes (plan 3.9):

    missing   the expected thing is absent        WARNING
    wrong     it exists and disagrees             ACTION REQUIRED

A `wrong` finding's remedy is the full replacement text, because nothing will
ever rewrite an existing line automatically. Informational notes carry no
class and never affect the exit code.

The report is a list of sections, each a function taking the AuditContext and
returning list[Finding], listed in SECTIONS in print order. A new section is
one more entry there.

Exit codes: 0 clean, 1 at least one `wrong`, 2 only `missing`, 3 the audit could
not run (Python older than 3.11, an invalid manifest, or a bad argument).
"""
from __future__ import annotations

import sys

MIN_PYTHON = (3, 11)
EXIT_CANNOT_RUN = 3


def require_python(version: tuple | None = None) -> bool:
    """True on a supported Python; otherwise prints one line and returns False.

    Called from main(), never at import, so a caller that imports this module
    (the Overwatch session-start hook) is not killed on an old interpreter.
    """
    version = tuple(sys.version_info[:2]) if version is None else tuple(version)
    if tuple(version[:2]) >= MIN_PYTHON:
        return True
    sys.stderr.write(
        "organize-device needs Python %d.%d or newer; this is Python %d.%d.\n"
        % (MIN_PYTHON + tuple(version[:2]))
    )
    return False


import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import platform  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable, Iterable, Optional  # noqa: E402

_HERE = Path(__file__).resolve().parent
_ORGS_SCRIPTS = _HERE.parents[1] / "organize-orgs" / "scripts"
_REVIEW_SCRIPTS = _HERE.parents[1] / "review-claude" / "scripts"
_HOOKS_SCRIPTS = _HERE.parents[2] / "hooks" / "scripts"
for _p in (_HERE, _ORGS_SCRIPTS, _HOOKS_SCRIPTS, _REVIEW_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from audit_identity import (  # noqa: E402
    ERROR,
    INFO,
    WARNING,
    Finding as _IdentityFinding,
    iter_org_dirs,
    iter_repos,
)
from check_identity import (  # noqa: E402
    UNGOVERNED_TYPES,
    find_governing_org,
    gh_active_account,
    inspect_identity_contract,
    is_under,
    load_org_config,
    workspace_type,
)
from device_manifest import (  # noqa: E402
    Manifest,
    ManifestError,
    TEMPLATE_PATH,
    default_manifest_path,
    load_manifest,
)

MISSING = "missing"
WRONG = "wrong"

GH_TIMEOUT = 5
SSH_TIMEOUT = 10

LABELS = {ERROR: "ACTION REQUIRED", WARNING: "WARNING", INFO: "note"}
REMEDY_PREFIX = "       → "
CONTINUATION = " " * len(REMEDY_PREFIX)


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------

class Finding(_IdentityFinding):
    """audit_identity's Finding plus a class, a section, and a `you` note.

    `finding_class` is MISSING, WRONG, or None for an informational note.
    Severity follows from the class (missing is WARNING, wrong is ERROR, which
    the text report labels ACTION REQUIRED). `you` is a step only a person can
    do (a browser sign-in, a key upload), kept apart from `remedy` so a later
    `--install` can tag it.

    `action` is set only on a `missing` finding whose fix is fully determined,
    as a dict with a `kind` and the parameters the installer needs, so the
    installer never has to parse remedy prose. Kinds: package, git_include,
    ssh_block, plugin_marketplace_add, plugin_install, plugin_enable, clone.
    `wrong` findings and notes always carry None.
    """

    def __init__(self, severity: str, org: Optional[str], message: str,
                 remedy: Optional[str] = None, *, finding_class: Optional[str] = None,
                 section: Optional[str] = None, you: Optional[str] = None,
                 action: Optional[dict[str, Any]] = None) -> None:
        super().__init__(severity, org, message, remedy)
        self.finding_class = finding_class
        self.section = section
        self.you = you
        self.action = action if finding_class == MISSING else None

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update({"class": self.finding_class, "section": self.section, "you": self.you,
                     "action": self.action})
        return data


def missing(section: str, org: Optional[str], message: str,
            remedy: Optional[str] = None, you: Optional[str] = None,
            action: Optional[dict[str, Any]] = None) -> Finding:
    return Finding(WARNING, org, message, remedy, finding_class=MISSING,
                   section=section, you=you, action=action)


def wrong(section: str, org: Optional[str], message: str, remedy: str,
          you: Optional[str] = None) -> Finding:
    return Finding(ERROR, org, message, remedy, finding_class=WRONG,
                   section=section, you=you)


def note(section: str, message: str, org: Optional[str] = None,
         remedy: Optional[str] = None) -> Finding:
    return Finding(INFO, org, message, remedy, section=section)


# --------------------------------------------------------------------------
# context
# --------------------------------------------------------------------------

@dataclass
class Contract:
    """One org's identity contract, as read from its org.json."""

    org: str
    org_dir: Path
    github_account: str
    git_user_name: str
    git_email: str
    ssh_host_alias: Optional[str] = None


@dataclass
class AuditContext:
    home: Path
    workspace_root: Path
    manifest: Manifest
    manifest_path: Path
    full: bool = False
    liveness: bool = False
    contracts: list[Contract] = field(default_factory=list)

    @property
    def default_accounts(self) -> list[str]:
        """Accounts with no SSH host alias, so they use the plain github.com host.

        Two orgs sharing one account are one entry here; that is not a conflict.
        """
        return list(dict.fromkeys(c.github_account for c in self.contracts
                                  if not c.ssh_host_alias))

    @property
    def default_contract(self) -> Optional[Contract]:
        accounts = self.default_accounts
        if len(accounts) != 1:
            return None
        return next(c for c in self.contracts
                    if not c.ssh_host_alias and c.github_account == accounts[0])

    def is_default(self, contract: Contract) -> bool:
        return is_default(contract, self.contracts)


def default_accounts(contracts: Iterable[Contract]) -> list[str]:
    """Accounts with no SSH host alias, in contract order, without repeats."""
    return list(dict.fromkeys(c.github_account for c in contracts if not c.ssh_host_alias))


def is_default(contract: Contract, contracts: Iterable[Contract]) -> bool:
    """True when `contract` is the default org's: it has no ssh_host_alias and
    its account is the one account (across `contracts`) without an alias.

    With zero or several alias-less accounts there is no default, so this is
    False for every contract. AuditContext.is_default delegates here.
    """
    accounts = default_accounts(contracts)
    return len(accounts) == 1 and not contract.ssh_host_alias \
        and contract.github_account == accounts[0]


def load_contracts(workspace_root: Path) -> list[Contract]:
    """Every valid identity contract directly under the workspace root.

    Discovery is organize-orgs' own (`iter_org_dirs`, ungoverned types
    skipped). Incomplete or malformed contracts are skipped here because
    organize-orgs already reports them.
    """
    contracts = []
    for org_dir in iter_org_dirs(workspace_root):
        if workspace_type(org_dir) in UNGOVERNED_TYPES:
            continue
        config = load_org_config(org_dir)
        if inspect_identity_contract(config).status != "valid":
            continue
        identity = config["identity"]
        alias = identity.get("ssh_host_alias")
        contracts.append(Contract(
            org=org_dir.name,
            org_dir=org_dir,
            github_account=str(identity["github_account"]),
            git_user_name=str(identity["git_user_name"]),
            git_email=str(identity["git_email"]),
            ssh_host_alias=str(alias) if isinstance(alias, str) and alias.strip() else None,
        ))
    return contracts


# --------------------------------------------------------------------------
# path helpers
# --------------------------------------------------------------------------

def expand(text: str, home: Path) -> Path:
    """Expand a leading `~` against `home` (not the process's real home)."""
    if text == "~":
        return home
    if text.startswith("~/"):
        return home / text[2:]
    return Path(text)


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def tilde(path: Path, home: Path) -> str:
    """`~/...` when the path is inside home, else the path as given."""
    try:
        rel = _resolve(path).relative_to(_resolve(home))
    except ValueError:
        return str(path)
    return "~" if str(rel) == "." else f"~/{rel.as_posix()}"


def is_absolute_home_path(text: str, home: Path) -> bool:
    """An absolute path into a home directory, which breaks on a different login."""
    if text.startswith(("/Users/", "/home/")):
        return True
    for prefix in {str(home), str(_resolve(home))}:
        if text == prefix or text.startswith(prefix.rstrip("/") + "/"):
            return True
    return False


# --------------------------------------------------------------------------
# git config parsing
# --------------------------------------------------------------------------

@dataclass
class GitStanza:
    section: str                 # lowercased
    subsection: Optional[str]    # case preserved
    values: dict[str, list[str]] = field(default_factory=dict)

    def last(self, key: str) -> Optional[str]:
        found = self.values.get(key.lower())
        return found[-1] if found else None


_SECTION_RE = re.compile(r'^\s*\[\s*([A-Za-z0-9.-]+)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\]\s*(.*)$')
_KEY_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9-]*)\s*(?:=\s*(.*))?$")


def _git_value(raw: str) -> str:
    out: list[str] = []
    quoted = False
    i = 0
    while i < len(raw):
        char = raw[i]
        if char == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            out.append({"n": "\n", "t": "\t", "b": "\b"}.get(nxt, nxt))
            i += 2
            continue
        if char == '"':
            quoted = not quoted
        elif char in "#;" and not quoted:
            break
        else:
            out.append(char)
        i += 1
    return "".join(out).strip()


def parse_git_config(text: str) -> list[GitStanza]:
    """Stanzas in file order. Enough of git's format for identity checks."""
    stanzas: list[GitStanza] = []
    current: Optional[GitStanza] = None

    def add_key(line: str) -> None:
        match = _KEY_RE.match(line)
        if not match or current is None:
            return
        value = _git_value(match.group(2)) if match.group(2) is not None else "true"
        current.values.setdefault(match.group(1).lower(), []).append(value)

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        header = _SECTION_RE.match(line)
        if header:
            name, sub, rest = header.group(1), header.group(2), header.group(3)
            if sub is None and "." in name:
                name, _, legacy = name.partition(".")
                sub = legacy.lower()
            elif sub is not None:
                sub = re.sub(r"\\(.)", r"\1", sub)
            current = GitStanza(name.lower(), sub)
            stanzas.append(current)
            if rest.strip() and not rest.strip().startswith(("#", ";")):
                add_key(rest)
            continue
        add_key(line)
    return stanzas


def read_git_config(path: Path) -> Optional[list[GitStanza]]:
    """Parsed stanzas, or None when the file is absent or unreadable."""
    if not path.is_file():
        return None
    try:
        return parse_git_config(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def git_get(stanzas: Iterable[GitStanza], section: str, key: str,
            subsection: Optional[str] = None) -> Optional[str]:
    """Last value of section[.subsection].key, git's last-one-wins rule."""
    value = None
    for stanza in stanzas:
        if stanza.section == section and stanza.subsection == subsection:
            value = stanza.last(key) or value
    return value


# --------------------------------------------------------------------------
# ssh config parsing
# --------------------------------------------------------------------------

@dataclass
class SshBlock:
    patterns: list[str]
    options: list[tuple[str, str, str]] = field(default_factory=list)  # (key, as written, value)

    def get(self, key: str) -> Optional[str]:
        """First value, ssh's first-one-wins rule."""
        for k, _, value in self.options:
            if k == key.lower():
                return value
        return None


_SSH_LINE_RE = re.compile(r"^(\S+?)(?:\s*=\s*|\s+)(.*)$")


def parse_ssh_config(text: str) -> list[SshBlock]:
    """`Host` blocks. `Match` blocks are kept with no patterns so they never
    match by name; `Include` lines are skipped (not followed)."""
    blocks: list[SshBlock] = []
    current: Optional[SshBlock] = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _SSH_LINE_RE.match(stripped)
        written, value = (match.group(1), match.group(2).strip()) if match else (stripped, "")
        key = written.lower()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        if key == "host":
            current = SshBlock(patterns=value.split())
            blocks.append(current)
        elif key == "match":
            current = SshBlock(patterns=[])
            blocks.append(current)
        elif key == "include":
            continue
        elif current is not None:
            current.options.append((key, written, value))
    return blocks


def find_ssh_block(blocks: Iterable[SshBlock], host: str) -> Optional[SshBlock]:
    for block in blocks:
        if any(p.lower() == host.lower() for p in block.patterns):
            return block
    return None


def render_ssh_block(host: str, block: Optional[SshBlock], identity_file: str) -> str:
    """The full, correct block, keeping any other options the existing one has."""
    lines = [f"Host {host}", "    HostName github.com"]
    if block is not None:
        for key, written, value in block.options:
            if key not in ("hostname", "identityfile", "identitiesonly"):
                lines.append(f"    {written} {value}")
    lines.append(f"    IdentityFile {identity_file}")
    lines.append("    IdentitiesOnly yes")
    return "\n".join(lines)


def suggested_key_name(alias: str) -> str:
    stem = alias[len("github-"):] if alias.startswith("github-") and len(alias) > 7 else alias
    return f"id_ed25519_{stem}"


def keygen_note(contract: Contract, key_path: str) -> str:
    return (
        f'Create the key if it does not exist: ssh-keygen -t ed25519 -C "{contract.git_email}" '
        f"-f {key_path}\n"
        f"Then add {key_path}.pub on github.com signed in as {contract.github_account} "
        f"(Settings, SSH and GPG keys). That is a browser step."
    )


# --------------------------------------------------------------------------
# subprocess probes (stubbed in tests)
# --------------------------------------------------------------------------

def _run(args: list[str], timeout: float) -> Optional[subprocess.CompletedProcess]:
    """Run a command; None when the binary is absent or it timed out."""
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def gh_login_present(account: str, timeout: float = GH_TIMEOUT) -> Optional[bool]:
    """Whether `gh` holds a token for the account. None when it cannot tell.

    Uses the exit code of `gh auth token --user` (local keyring, no network)
    and discards stdout, so the token is never kept or printed.
    """
    result = _run(["gh", "auth", "token", "--user", account], timeout)
    if result is None:
        return None
    return result.returncode == 0


_GREETING_RE = re.compile(r"Hi ([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)!")


def ssh_greeting(host: str, timeout: float = SSH_TIMEOUT) -> tuple[bool, Optional[str]]:
    """(ran, username) from GitHub's `ssh -T` greeting. Only the name is parsed."""
    result = _run(["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                   f"git@{host}"], timeout)
    if result is None:
        return False, None
    match = _GREETING_RE.search(f"{result.stdout}\n{result.stderr}")
    return True, match.group(1) if match else None


def _system() -> str:
    return platform.system()


def package_manager() -> Optional[str]:
    if shutil.which("brew"):
        return "brew"
    if shutil.which("apt-get"):
        return "apt"
    return None


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------

def section_manifest(ctx: AuditContext) -> list[Finding]:
    section = "Device manifest"
    if ctx.manifest.found:
        return [note(section, f"Read {tilde(ctx.manifest.path, ctx.home)}.")]
    return [note(
        section,
        f"No device manifest at {tilde(ctx.manifest_path, ctx.home)}; the checks ran on the "
        f"org contracts alone. `--snapshot` writes one from this machine; until then you can "
        f"copy {TEMPLATE_PATH.name} from the skill's scripts/ directory.",
    )]


def _is_windows(system: str) -> bool:
    upper = system.upper()
    return upper == "WINDOWS" or upper.startswith(("CYGWIN", "MSYS", "MINGW"))


def section_platform(ctx: AuditContext) -> list[Finding]:
    section = "Platform"
    system = _system()
    if _is_windows(system):
        return [wrong(
            section, None,
            f"This platform ({system}) is unsupported.",
            "Use WSL2: run `wsl --install` in an administrator PowerShell, then run this "
            "audit inside the WSL2 Linux shell.",
        )]
    if system == "Darwin":
        name = f"macOS {platform.mac_ver()[0]}".strip()
    else:
        name = system or "unknown OS"
    shell = Path(os.environ.get("SHELL", "")).name or "unknown"
    return [note(
        section,
        f"{name} on {platform.machine() or 'unknown architecture'}; package manager: "
        f"{package_manager() or 'none found'}; shell: {shell}.",
    )]


BASELINE_TOOLS = ("git", "gh", "jq", "python3", "node", "rg", "claude")
# A manifest may name a tool by its package; the binary to look for differs.
TOOL_BINARY = {"ripgrep": "rg", "awscli": "aws", "nodejs": "node", "python": "python3"}
PACKAGE_NAME = {
    "brew": {"rg": "ripgrep", "python3": "python", "aws": "awscli",
             "terraform": "hashicorp/tap/terraform"},
    "apt": {"rg": "ripgrep", "node": "nodejs", "aws": "awscli"},
}
CLAUDE_INSTALL = "curl -fsSL https://claude.ai/install.sh | bash"


def package_name(tool: str, manager: str) -> str:
    """The package that provides `tool` under `manager` (brew or apt)."""
    table = PACKAGE_NAME[manager]
    return table.get(tool) or table.get(TOOL_BINARY.get(tool, tool)) or tool


def package_action(tool: str, manager: Optional[str]) -> Optional[dict[str, Any]]:
    if manager is None or TOOL_BINARY.get(tool, tool) == "claude":
        return None
    return {"kind": "package", "manager": manager, "name": package_name(tool, manager)}


def install_command(tool: str, manager: Optional[str]) -> str:
    binary = TOOL_BINARY.get(tool, tool)
    if binary == "claude":
        return CLAUDE_INSTALL
    if manager is None:
        return f"Install {tool} with this system's package manager (no brew or apt found)."
    package = package_name(tool, manager)
    if manager == "brew":
        return f"brew install {package}"
    return f"sudo apt-get install -y {package}"


def section_tools(ctx: AuditContext) -> list[Finding]:
    section = "Tools"
    manager = package_manager()
    findings = []
    wanted = list(dict.fromkeys([*BASELINE_TOOLS, *ctx.manifest.tools_extra]))
    for tool in wanted:
        if shutil.which(TOOL_BINARY.get(tool, tool)):
            continue
        source = "baseline" if tool in BASELINE_TOOLS else "manifest tools.extra"
        findings.append(missing(section, None, f"{tool} is not installed ({source}).",
                                install_command(tool, manager),
                                action=package_action(tool, manager)))
    return findings


def _orgs_for(ctx: AuditContext, account: str) -> str:
    return ", ".join(c.org for c in ctx.contracts if c.github_account == account)


def section_github(ctx: AuditContext) -> list[Finding]:
    section = "GitHub logins"
    accounts = list(dict.fromkeys(c.github_account for c in ctx.contracts))
    if not accounts:
        return [note(section, f"No org contracts under {tilde(ctx.workspace_root, ctx.home)}, "
                              f"so no GitHub logins are expected.")]
    if shutil.which("gh") is None:
        return [note(section, "gh is not installed (see Tools), so GitHub logins cannot be "
                              "checked.")]
    findings = []
    present = []
    for account in accounts:
        state = gh_login_present(account)
        orgs = _orgs_for(ctx, account)
        if state is None:
            findings.append(note(section, f"Could not check the gh login for {account}; gh did "
                                          f"not answer in time.", org=orgs))
        elif state:
            present.append(account)
        else:
            findings.append(missing(
                section, orgs,
                f"No gh login for {account} (needed by {orgs}).",
                "gh auth login --hostname github.com --git-protocol ssh --web",
                you=f"Browser step: when gh opens github.com, sign in as {account}. "
                    f"gh makes the new login active, so switch back afterward if needed.",
            ))
    if present:
        findings.append(note(section, f"gh logins present: {', '.join(present)}."))
    active = gh_active_account()
    if active:
        findings.append(note(
            section,
            f"gh's active account is {active}. `gh auth switch` is machine-global: switching "
            f"in one shell changes it for every shell on this machine.",
        ))
    return findings


def section_ssh(ctx: AuditContext) -> list[Finding]:
    section = "SSH"
    findings: list[Finding] = []
    defaults = ctx.default_accounts
    if len(defaults) > 1:
        detail = "; ".join(f"{a} ({_orgs_for(ctx, a)})" for a in defaults)
        keep = defaults[0]
        fixes = "\n".join(
            f'In {tilde(c.org_dir / ".claude" / "org.json", ctx.home)}, add to "identity": '
            f'"ssh_host_alias": "github-{c.org}"'
            for c in ctx.contracts if not c.ssh_host_alias and c.github_account != keep
        )
        findings.append(wrong(
            section, None,
            f"More than one GitHub account has no ssh_host_alias: {detail}. Only one account "
            f"can own the plain github.com host.",
            fixes,
        ))

    config_path = ctx.home / ".ssh" / "config"
    blocks: list[SshBlock] = []
    if config_path.is_file():
        try:
            blocks = parse_ssh_config(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            blocks = []

    healthy = []
    seen: set[str] = set()
    for contract in ctx.contracts:
        alias = contract.ssh_host_alias
        if not alias or alias.lower() in seen:
            continue
        seen.add(alias.lower())
        suggested = f"~/.ssh/{suggested_key_name(alias)}"
        block = find_ssh_block(blocks, alias)
        if block is None:
            findings.append(missing(
                section, contract.org,
                f"No `Host {alias}` block in ~/.ssh/config (the alias {contract.org} pushes "
                f"through).",
                f"Append to ~/.ssh/config:\n{render_ssh_block(alias, None, suggested)}",
                you=keygen_note(contract, suggested),
                action={"kind": "ssh_block", "host": alias,
                        "block": render_ssh_block(alias, None, suggested),
                        "key_path": suggested},
            ))
            continue
        problems = []
        key_missing = False
        hostname = block.get("hostname")
        if (hostname or "").lower() != "github.com":
            problems.append(f"HostName is {hostname or 'unset'}, not github.com")
        identity_file = block.get("identityfile")
        if not identity_file:
            problems.append("it has no IdentityFile")
            identity_file = suggested
            key_missing = not expand(suggested, ctx.home).exists()
        elif not expand(identity_file, ctx.home).exists():
            problems.append(f"its IdentityFile {identity_file} is not on disk")
            key_missing = True
        if (block.get("identitiesonly") or "").lower() != "yes":
            problems.append("IdentitiesOnly yes is absent")
        if problems:
            findings.append(wrong(
                section, contract.org,
                f"`Host {alias}` in ~/.ssh/config is wrong: {'; '.join(problems)}.",
                f"Replace the block with:\n{render_ssh_block(alias, block, identity_file)}",
                you=keygen_note(contract, identity_file) if key_missing else None,
            ))
        else:
            healthy.append(alias)
    default = ctx.default_contract
    if default is not None:
        block = find_ssh_block(blocks, "github.com")
        if block is None:
            findings.append(note(section, f"No `Host github.com` block; ssh uses its default "
                                          f"keys for {default.github_account}."))
        else:
            identity_file = block.get("identityfile")
            if not identity_file:
                findings.append(note(section, f"`Host github.com` names no IdentityFile; ssh "
                                              f"uses its default keys for "
                                              f"{default.github_account}."))
            elif expand(identity_file, ctx.home).exists():
                healthy.append("github.com")
            else:
                findings.append(wrong(
                    section, default.org,
                    f"`Host github.com` points at {identity_file}, which is not on disk.",
                    f"Replace the block with:\n"
                    f"{render_ssh_block('github.com', block, identity_file)}",
                    you=keygen_note(default, identity_file),
                ))

    if healthy:
        findings.append(note(section, f"Hosts present with keys on disk: "
                                      f"{', '.join(healthy)}."))
    if ctx.full and ctx.liveness:
        findings.extend(_ssh_liveness(ctx, section))
    return findings


def _ssh_liveness(ctx: AuditContext, section: str) -> list[Finding]:
    findings = []
    targets: list[tuple[str, Contract]] = []
    for contract in ctx.contracts:
        if contract.ssh_host_alias and all(h != contract.ssh_host_alias for h, _ in targets):
            targets.append((contract.ssh_host_alias, contract))
    if ctx.default_contract is not None:
        targets.append(("github.com", ctx.default_contract))
    for host, contract in targets:
        ran, user = ssh_greeting(host)
        if not ran:
            findings.append(note(section, f"Could not run `ssh -T git@{host}` (ssh absent or "
                                          f"timed out).", org=contract.org))
        elif user is None:
            findings.append(missing(
                section, contract.org,
                f"`ssh -T git@{host}` did not authenticate.",
                f"Check the IdentityFile for Host {host} and that its key is loaded.",
                you=f"Add the key's .pub on github.com signed in as {contract.github_account}. "
                    f"That is a browser step.",
            ))
        elif user.lower() != contract.github_account.lower():
            findings.append(wrong(
                section, contract.org,
                f"`ssh -T git@{host}` authenticates as {user}, not {contract.github_account}.",
                f"Point IdentityFile in `Host {host}` at the key registered to "
                f"{contract.github_account}, or move this key from {user} to "
                f"{contract.github_account} on github.com.",
            ))
    return findings


# --- git identity -----------------------------------------------------------

_GITDIR_PREFIXES = ("gitdir:", "gitdir/i:")


def _gitdir_target(stanza: GitStanza) -> Optional[str]:
    if stanza.section != "includeif" or not stanza.subsection:
        return None
    for prefix in _GITDIR_PREFIXES:
        if stanza.subsection.startswith(prefix):
            return stanza.subsection[len(prefix):]
    return None


def _gitdir_matches(raw: str, org_dir: Path, home: Path) -> bool:
    text = raw
    for suffix in ("/**", "/"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    if not text.startswith(("/", "~")):
        return False
    return _resolve(expand(text, home)) == _resolve(org_dir)


def has_include_for(stanzas: Iterable[GitStanza], org_dir: Path, home: Path) -> bool:
    """True when any `includeIf "gitdir:..."` stanza targets `org_dir`.

    Right or wrong does not matter here (an absolute home path still counts);
    section_git_identity judges the stanza. Public for the Overwatch check.
    """
    return any(
        (target := _gitdir_target(s)) is not None and _gitdir_matches(target, org_dir, home)
        for s in stanzas
    )


def _include_path(raw: str, home: Path) -> Path:
    """git resolves a relative include path against the including file's directory."""
    path = expand(raw, home)
    return path if path.is_absolute() else home / path


def _stanza_text(gitdir: str, path: str) -> str:
    return f'[includeIf "gitdir:{gitdir}"]\n\tpath = {path}'


def _user_text(contract: Contract) -> str:
    return f"[user]\n\tname = {contract.git_user_name}\n\temail = {contract.git_email}"


def section_git_identity(ctx: AuditContext) -> list[Finding]:
    section = "git identity"
    findings: list[Finding] = []
    home = ctx.home
    global_cfg = read_git_config(home / ".gitconfig") or []
    stanzas = [s for s in global_cfg if _gitdir_target(s) is not None]
    effective: dict[str, list[GitStanza]] = {}

    for contract in ctx.contracts:
        org_gitdir = tilde(contract.org_dir, home).rstrip("/") + "/"
        default_path = f"~/.gitconfig-{contract.org}"
        stanza = next((s for s in stanzas
                       if _gitdir_matches(_gitdir_target(s), contract.org_dir, home)), None)
        if stanza is None:
            effective[contract.org] = global_cfg
            if ctx.is_default(contract):
                continue  # the default org rides the global identity, checked below
            findings.append(missing(
                section, contract.org,
                f"No includeIf stanza for {org_gitdir} in ~/.gitconfig, so commits there use "
                f"the global identity instead of {contract.git_email}.",
                f"Append to ~/.gitconfig:\n{_stanza_text(org_gitdir, default_path)}\n"
                f"Create {default_path} with:\n{_user_text(contract)}",
                action={"kind": "git_include", "org_dir": org_gitdir,
                        "include_path": default_path,
                        "stanza": _stanza_text(org_gitdir, default_path),
                        "file_text": _user_text(contract) + "\n"},
            ))
            continue

        gitdir_raw = _gitdir_target(stanza)
        path_raw = stanza.last("path")
        problems = []
        if is_absolute_home_path(gitdir_raw, home):
            problems.append(f"gitdir uses an absolute home path ({gitdir_raw})")
        if not gitdir_raw.endswith(("/", "/**")):
            problems.append("gitdir lacks the trailing slash, so it matches no repo inside "
                            "the directory")
        if not path_raw:
            problems.append("it has no `path =` line")
            include = None
            fixed_path = default_path
        else:
            include = _include_path(path_raw, home)
            if is_absolute_home_path(path_raw, home):
                problems.append(f"path uses an absolute home path ({path_raw})")
            fixed_path = tilde(include, home) if tilde(include, home).startswith("~") \
                else default_path

        file_problem = None
        include_cfg = read_git_config(include) if include is not None else None
        if include is not None and include_cfg is None:
            file_problem = f"the include file {tilde(include, home)} does not exist"
        elif include_cfg is not None:
            name = git_get(include_cfg, "user", "name")
            email = git_get(include_cfg, "user", "email")
            diffs = []
            if email != contract.git_email:
                diffs.append(f"user.email is {email or 'unset'}, contract says "
                             f"{contract.git_email}")
            if name != contract.git_user_name:
                diffs.append(f"user.name is {name or 'unset'}, contract says "
                             f"{contract.git_user_name}")
            if diffs:
                file_problem = f"{tilde(include, home)} sets " + " and ".join(diffs)
        if file_problem:
            problems.append(file_problem)
        effective[contract.org] = [*global_cfg, *(include_cfg or [])]

        if problems:
            remedy = f"Replace the stanza in ~/.gitconfig with:\n" \
                     f"{_stanza_text(org_gitdir, fixed_path)}"
            if file_problem or fixed_path != (tilde(include, home) if include else None):
                remedy += f"\nMake {fixed_path} contain (other settings in it can stay):\n" \
                          f"{_user_text(contract)}"
            findings.append(wrong(
                section, contract.org,
                f"The includeIf stanza for {org_gitdir} is wrong: {'; '.join(problems)}.",
                remedy,
            ))

    findings.extend(_global_identity(ctx, section, global_cfg))
    findings.extend(_signing_note(ctx, section, effective))
    findings.append(_credential_note(section, global_cfg))
    https = _https_note(ctx, section)
    if https is not None:
        findings.append(https)
    return findings


def _global_identity(ctx: AuditContext, section: str,
                     global_cfg: list[GitStanza]) -> list[Finding]:
    default = ctx.default_contract
    if default is None:
        if ctx.contracts:
            return [note(section, "No single default account (an org with no "
                                  "ssh_host_alias), so the global identity was not checked.")]
        return []
    name = git_get(global_cfg, "user", "name")
    email = git_get(global_cfg, "user", "email")
    differs = [(k, v, want) for k, v, want in (("user.name", name, default.git_user_name),
                                               ("user.email", email, default.git_email))
               if v and v != want]
    if differs:
        detail = "; ".join(f"{k} is {v}, the {default.org} contract says {want}"
                           for k, v, want in differs)
        return [wrong(section, default.org, f"Global git identity is wrong: {detail}.",
                      f"Replace the [user] section in ~/.gitconfig with:\n"
                      f"{_user_text(default)}")]
    unset = [(k, want) for k, v, want in (("user.name", name, default.git_user_name),
                                          ("user.email", email, default.git_email)) if not v]
    if unset:
        return [missing(section, default.org,
                        f"Global {', '.join(k for k, _ in unset)} is not set in ~/.gitconfig.",
                        "\n".join(f'git config --global {k} "{want}"' for k, want in unset))]
    return []


def _signing_note(ctx: AuditContext, section: str,
                  effective: dict[str, list[GitStanza]]) -> list[Finding]:
    """Signing per org, reported and never flagged (plan 8.3)."""
    parts = []
    for contract in ctx.contracts:
        cfg = effective.get(contract.org, [])
        sign = (git_get(cfg, "commit", "gpgsign") or "false").lower() in ("true", "yes", "on", "1")
        key = git_get(cfg, "user", "signingkey")
        if not sign:
            parts.append(f"{contract.org} off")
            continue
        fmt = git_get(cfg, "gpg", "format") or "openpgp"
        if key and (key.startswith(("~", "/")) or "/" in key):
            key_path = expand(key, ctx.home)
            state = "present" if key_path.exists() else "not found"
            parts.append(f"{contract.org} on ({fmt}, key {tilde(key_path, ctx.home)}, {state})")
        else:
            parts.append(f"{contract.org} on ({fmt}{', key id set' if key else ', no key set'})")
    if not parts:
        return []
    return [note(section, f"Commit signing: {'; '.join(parts)}.")]


def _credential_note(section: str, global_cfg: list[GitStanza]) -> Finding:
    helper = git_get(global_cfg, "credential", "helper")
    if helper:
        return note(section, f"credential.helper is {helper} (from ~/.gitconfig).")
    return note(section, "credential.helper is not set in ~/.gitconfig (a system-level "
                         "default may still apply).")


def _origin_url(repo: Path) -> Optional[str]:
    dot_git = repo / ".git"
    git_dir = dot_git
    if dot_git.is_file():
        try:
            line = dot_git.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            return None
        if not line.startswith("gitdir:"):
            return None
        git_dir = Path(line[len("gitdir:"):].strip())
        if not git_dir.is_absolute():
            git_dir = repo / git_dir
        common = git_dir / "commondir"
        if common.is_file():
            try:
                git_dir = git_dir / common.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                return None
    cfg = read_git_config(git_dir / "config")
    return git_get(cfg or [], "remote", "url", subsection="origin")


def _https_note(ctx: AuditContext, section: str) -> Optional[Finding]:
    """How many repos under non-default org directories push over HTTPS. Counts only."""
    counts = []
    total = 0
    seen: set[Path] = set()
    for contract in ctx.contracts:
        if ctx.is_default(contract) or contract.org_dir in seen:
            continue
        seen.add(contract.org_dir)
        repos = list(iter_repos(contract.org_dir))
        https = sum(1 for r in repos if (_origin_url(r) or "").startswith("https://"))
        total += https
        if https:
            counts.append(f"{contract.org} {https} of {len(repos)}")
    if not seen:
        return None
    if not total:
        return note(section, "No repo under a non-default org directory uses an HTTPS origin.")
    return note(
        section,
        f"Repos under non-default org directories with an HTTPS origin: {', '.join(counts)}. "
        f"The keychain holds one HTTPS credential per host, so those pushes go out as "
        f"whichever account is cached.",
    )


# --- Claude Code -------------------------------------------------------------

CLAUDE_TIMEOUT = 10
# Where scan-secrets installs its global dispatchers, relative to home. Mirrors
# hook_installer.HOOKS_DIR, which binds Path.home() at import and so cannot be
# reused against a different home; a test pins the two together.
SCAN_HOOKS_RELATIVE = Path(".claude") / "lastmilefirst" / "git-hooks"
SCAN_HOOK_KINDS = ("pre-commit", "pre-push")
SCAN_HOOKS_REMEDY = "/run-scan-secrets --install-hooks"


def claude_version(timeout: float = CLAUDE_TIMEOUT) -> Optional[str]:
    """First line of `claude --version`, or None."""
    result = _run(["claude", "--version"], timeout)
    if result is None or result.returncode != 0:
        return None
    lines = result.stdout.strip().splitlines()
    return lines[0].strip() if lines else None


def claude_marketplace_list(timeout: float = CLAUDE_TIMEOUT) -> Optional[list[dict]]:
    """`claude plugin marketplace list --json`, or None. Used only under --full."""
    result = _run(["claude", "plugin", "marketplace", "list", "--json"], timeout)
    if result is None or result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else None


def _read_json(path: Path) -> tuple[bool, Any]:
    """(readable, data). An absent file is (True, None); a broken one (False, None)."""
    if not path.is_file():
        return True, None
    try:
        return True, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return False, None


def _marketplace_names(entries: Iterable[tuple[str, Any]]) -> set[str]:
    """Every name a marketplace can be referred to by: its key, repo, url, path."""
    names: set[str] = set()
    for key, source in entries:
        names.add(key.lower())
        if isinstance(source, dict):
            for field_name in ("repo", "url", "path"):
                value = source.get(field_name)
                if isinstance(value, str) and value:
                    names.add(value.lower().removesuffix(".git").rstrip("/"))
    return names


def known_marketplaces(ctx: AuditContext) -> Optional[set[str]]:
    """Names of the marketplaces Claude Code knows, or None when it cannot tell."""
    ok, data = _read_json(ctx.home / ".claude" / "plugins" / "known_marketplaces.json")
    if ok and isinstance(data, dict):
        return _marketplace_names(
            (k, (v or {}).get("source") if isinstance(v, dict) else None)
            for k, v in data.items())
    if ctx.full:
        listed = claude_marketplace_list()
        if listed is not None:
            return _marketplace_names((str(d.get("name", "")), d) for d in listed)
    return set() if ok and data is None else None


def _hooks_path_setting(home: Path) -> Optional[str]:
    return git_get(read_git_config(home / ".gitconfig") or [], "core", "hookspath")


def section_claude(ctx: AuditContext) -> list[Finding]:
    section = "Claude Code"
    findings: list[Finding] = []
    if shutil.which("claude"):
        version = claude_version()
        findings.append(note(section, f"claude --version: {version}." if version else
                             "claude is installed but `claude --version` did not answer."))
    manifest = ctx.manifest

    if manifest.claude_marketplaces:
        known = known_marketplaces(ctx)
        if known is None:
            findings.append(note(section, "Could not read ~/.claude/plugins/"
                                          "known_marketplaces.json, so marketplaces were not "
                                          "checked (--full asks claude instead)."))
        else:
            for entry in manifest.claude_marketplaces:
                wanted = entry.lower().removesuffix(".git").rstrip("/")
                if wanted not in known:
                    findings.append(missing(section, None,
                                            f"Marketplace {entry} is not added (manifest "
                                            f"claude.marketplaces).",
                                            f"claude plugin marketplace add {entry}",
                                            action={"kind": "plugin_marketplace_add",
                                                    "entry": entry}))

    if manifest.claude_plugins:
        ok, settings = _read_json(ctx.home / ".claude" / "settings.json")
        if not ok:
            findings.append(note(section, "~/.claude/settings.json is not readable JSON, so "
                                          "plugins were not checked."))
        else:
            enabled = (settings or {}).get("enabledPlugins") if isinstance(settings, dict) \
                else None
            enabled = enabled if isinstance(enabled, dict) else {}
            for entry in manifest.claude_plugins:
                state = enabled.get(entry)
                if state is True:
                    continue
                if state is None:
                    findings.append(missing(section, None,
                                            f"Plugin {entry} is not installed (manifest "
                                            f"claude.plugins).",
                                            f"claude plugin install {entry}",
                                            action={"kind": "plugin_install",
                                                    "entry": entry}))
                else:
                    findings.append(missing(section, None,
                                            f"Plugin {entry} is installed but disabled.",
                                            f"claude plugin enable {entry}",
                                            action={"kind": "plugin_enable",
                                                    "entry": entry}))

    wanted_hooks = [h for h in manifest.claude_hooks if h in SCAN_HOOK_KINDS]
    for other in (h for h in manifest.claude_hooks if h not in SCAN_HOOK_KINDS):
        findings.append(note(section, f"claude.hooks entry {other} is not a scan-secrets hook "
                                      f"(pre-commit, pre-push); not checked."))
    if wanted_hooks:
        hooks_dir = ctx.home / SCAN_HOOKS_RELATIVE
        absent = [h for h in wanted_hooks if not (hooks_dir / h).is_file()]
        setting = _hooks_path_setting(ctx.home)
        hooks_tilde = tilde(hooks_dir, ctx.home)
        if absent:
            findings.append(missing(section, None,
                                    f"scan-secrets {', '.join(absent)} hook"
                                    f"{'' if len(absent) == 1 else 's'} not installed in "
                                    f"{hooks_tilde}.", SCAN_HOOKS_REMEDY))
        elif setting is None:
            findings.append(missing(section, None,
                                    f"The scan-secrets hooks are in {hooks_tilde} but "
                                    f"core.hooksPath is not set, so git never runs them.",
                                    SCAN_HOOKS_REMEDY))
        elif _resolve(expand(setting, ctx.home)) != _resolve(hooks_dir):
            findings.append(wrong(section, None,
                                  f"core.hooksPath is {setting}, so the scan-secrets hooks in "
                                  f"{hooks_tilde} do not run.",
                                  f"In ~/.gitconfig, set:\n[core]\n\thooksPath = {hooks_tilde}"))
    return findings


# --- AWS ----------------------------------------------------------------------

AWS_TIMEOUT = 15
_INI_HEADER_RE = re.compile(r"^\s*\[\s*([^\]]+?)\s*\]")


def _ini_sections(path: Path) -> list[str]:
    """Section names only. Values (which in credentials are keys) are never kept."""
    if not path.is_file():
        return []
    names = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                match = _INI_HEADER_RE.match(line)
                if match:
                    names.append(match.group(1))
    except (OSError, UnicodeDecodeError):
        return []
    return names


def aws_profiles_on_disk(home: Path) -> set[str]:
    config = Path(os.environ.get("AWS_CONFIG_FILE") or home / ".aws" / "config")
    creds = Path(os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
                 or home / ".aws" / "credentials")
    found = set()
    for name in _ini_sections(config):
        if name == "default":
            found.add(name)
        elif name.startswith("profile "):
            found.add(name[len("profile "):].strip())
    found.update(_ini_sections(creds))
    return found


def aws_account(profile: str, timeout: float = AWS_TIMEOUT) -> Optional[str]:
    """The account alias, else the account id, for a profile. Nothing else is kept.

    Network calls; run only under --full with liveness on.
    """
    result = _run(["aws", "iam", "list-account-aliases", "--profile", profile,
                   "--output", "json"], timeout)
    if result is not None and result.returncode == 0:
        try:
            aliases = json.loads(result.stdout).get("AccountAliases") or []
        except (json.JSONDecodeError, ValueError, AttributeError):
            aliases = []
        if aliases and isinstance(aliases[0], str):
            return aliases[0]
    result = _run(["aws", "sts", "get-caller-identity", "--profile", profile,
                   "--output", "json"], timeout)
    if result is None or result.returncode != 0:
        return None
    try:
        account = json.loads(result.stdout).get("Account")
    except (json.JSONDecodeError, ValueError, AttributeError):
        return None
    return account if isinstance(account, str) else None


def section_aws(ctx: AuditContext) -> list[Finding]:
    section = "AWS"
    profiles = ctx.manifest.aws_profiles
    if not profiles:
        return []
    if shutil.which("aws") is None:
        listed = {TOOL_BINARY.get(t, t) for t in ctx.manifest.tools_extra}
        if "aws" in listed:
            return [note(section, "aws is not installed (see Tools), so profiles were not "
                                  "checked.")]
        return [missing(section, None,
                        f"aws is not installed, and the manifest expects profile"
                        f"{'' if len(profiles) == 1 else 's'} {', '.join(profiles)}.",
                        install_command("awscli", package_manager()))]
    findings = []
    on_disk = aws_profiles_on_disk(ctx.home)
    for name in profiles:
        if name not in on_disk:
            findings.append(missing(section, None,
                                    f"AWS profile {name} is not in ~/.aws/config or "
                                    f"~/.aws/credentials.",
                                    None, you=f"aws configure --profile {name}"))
    label = ctx.manifest.aws_default_profile_is
    if "default" in profiles and "default" in on_disk and label and label != "(specify)":
        findings.append(note(section, f"Profile default is labeled {label} "
                                      f"(aws.default_profile_is)."))
    if ctx.full and ctx.liveness and "default" in on_disk:
        account = aws_account("default")
        findings.append(note(section,
                             f"Profile default answers as account {account}." if account
                             else "Profile default did not answer (expired or no "
                                  "credentials)."))
    return findings


# --- Keychain -----------------------------------------------------------------

KEYCHAIN_TIMEOUT = 5


def keychain_has(command: list[str], timeout: float = KEYCHAIN_TIMEOUT) -> Optional[bool]:
    """Presence by exit code only. stdout and stderr go to /dev/null, so a value
    is never in this process's memory."""
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode == 0:
        return True
    # security: 44 means not found; secret-tool: 1 means not found.
    return False if result.returncode in (1, 44) else None


def section_keychain(ctx: AuditContext) -> list[Finding]:
    section = "Keychain"
    items = ctx.manifest.keychain_items
    if not items:
        return []
    system = _system()
    if system == "Darwin" and shutil.which("security"):
        probe = lambda name: ["security", "find-generic-password", "-s", name]  # noqa: E731
        add = ("Add it by hand in Keychain Access, or run `security add-generic-password "
               "-s {name} -a \"$USER\" -w`, which prompts for the value.")
    elif system == "Linux" and shutil.which("secret-tool"):
        probe = lambda name: ["secret-tool", "lookup", "service", name]  # noqa: E731
        add = ("Add it by hand: `secret-tool store --label {name} service {name}`, which "
               "prompts for the value.")
    else:
        return [note(section, "Cannot check keychain items on this platform.")]
    findings = []
    for name in items:
        state = keychain_has(probe(name))
        if state is None:
            findings.append(note(section, f"Could not check keychain item {name}."))
        elif not state:
            findings.append(missing(section, None, f"Keychain item {name} is not present.",
                                    None, you=add.format(name=name)))
    return findings


# --- Network ------------------------------------------------------------------

def section_network(ctx: AuditContext) -> list[Finding]:
    section = "Network"
    provider = ctx.manifest.network_provider
    if provider == "none":
        return [note(section, "No network provider is configured. To check one, set "
                              "`provider` in the [network] table of "
                              f"{tilde(ctx.manifest_path, ctx.home)} (shipped: tailscale) and "
                              "add its [network.<provider>] table.")]
    import network  # deferred so provider = "none" imports nothing
    shipped = network.available()
    try:
        module = network.load(provider)
    except KeyError:
        choices = ", ".join(f'"{n}"' for n in ["none", *shipped])
        return [wrong(section, None, f'Unknown network provider "{provider}".',
                      f"In [network], set provider to one of: {choices}.")]
    table = ctx.manifest.network_options.get(provider, {})
    try:
        return list(module.audit(table, ctx))
    except Exception as exc:  # a provider bug must not take down the audit
        return [wrong(section, None, f"The {provider} provider failed: "
                                     f"{type(exc).__name__}.",
                      "Report this as a bug in the provider module.")]


# --- Workspace ----------------------------------------------------------------

PROJECT_TABLE_SECTION = "Project Directory Mapping"
_SKIP_ROW_RE = re.compile(r"\b(removed|paused)\b", re.IGNORECASE)


@dataclass
class ProjectRow:
    name: str
    path_text: str
    path: Path
    skipped: bool


def project_rows(content: str, home: Path) -> Optional[list[ProjectRow]]:
    """Rows of the workspace CLAUDE.md project table that carry a path.

    Section and table parsing are review-claude's own. None when the file has
    no such section.
    """
    from review_claude import extract_section, parse_table_rows
    found = extract_section(content, PROJECT_TABLE_SECTION)
    if found is None:
        return None
    rows = []
    for raw in parse_table_rows(found[1]):
        cells = [c.strip().strip("`").strip() for c in raw.strip().strip("|").split("|")]
        path_index = next((i for i, c in enumerate(cells) if c.startswith(("~/", "/"))), None)
        if path_index is None:
            continue
        others = " ".join(c for i, c in enumerate(cells) if i != path_index)
        path_text = cells[path_index].rstrip("/")
        rows.append(ProjectRow(name=cells[0] if path_index else path_text,
                               path_text=path_text,
                               path=expand(path_text, home),
                               skipped=bool(_SKIP_ROW_RE.search(others))))
    return rows


def _org_of(path: Path, root: Path) -> Optional[str]:
    """The first directory under the workspace root on the way to `path`."""
    try:
        parts = _resolve(path).relative_to(_resolve(root)).parts
    except ValueError:
        return None
    return parts[0] if parts else None


def _row_owner(path: Path, root: Path) -> tuple[Optional[str], Optional[str]]:
    """(github_account, ssh_host_alias) of the org governing `path`."""
    _, config = find_governing_org(path, root)
    if inspect_identity_contract(config).status != "valid":
        return None, None
    identity = config["identity"]
    alias = identity.get("ssh_host_alias")
    return str(identity["github_account"]), \
        (alias if isinstance(alias, str) and alias.strip() else None)


def clone_remedy(owner: Optional[str], alias: Optional[str], repo: str, path: str) -> str:
    """Always begins with `gh repo clone` or `git clone` (install keys on that)."""
    if alias and owner:
        return f"git clone git@{alias}:{owner}/{repo}.git {path}"
    return f"gh repo clone {owner or '(specify)'}/{repo} {path}"


def section_workspace(ctx: AuditContext) -> list[Finding]:
    section = "Workspace"
    root, home = ctx.workspace_root, ctx.home
    root_text = tilde(root, home)
    if not root.is_dir():
        return [wrong(section, None, f"The workspace root {root_text} does not exist.",
                      f"mkdir -p {root_text}, then clone the repository that holds your "
                      f"workspace CLAUDE.md into it (or pass --workspace-root).")]
    claude_md = root / "CLAUDE.md"
    md_text = f"{root_text}/CLAUDE.md"
    findings: list[Finding] = []
    if claude_md.is_symlink() and not claude_md.exists():
        target = os.readlink(claude_md)
        return [wrong(section, None, f"{md_text} is a link to {target}, which does not exist.",
                      f"Restore {target}, or re-point the link: ln -sfn <path to your "
                      f"workspace CLAUDE.md> {md_text}")]
    if not claude_md.is_file():
        return [missing(section, None, f"No workspace CLAUDE.md at {md_text}.", None,
                        you=f"Clone the repository that holds your workspace CLAUDE.md into "
                            f"{root_text}, or link the file there.")]
    if claude_md.is_symlink():
        findings.append(note(section, f"{md_text} links to "
                                      f"{tilde(_resolve(claude_md), home)}."))
    try:
        content = claude_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings + [note(section, f"{md_text} is not readable text.")]
    rows = project_rows(content, home)
    if rows is None:
        return findings + [note(section, f"{md_text} has no {PROJECT_TABLE_SECTION} section, "
                                         f"so the layout was not checked.")]

    outside = [r for r in rows if not is_under(r.path, root)]
    rows = [r for r in rows if r not in outside]
    if outside:
        findings.append(note(section, f"{len(outside)} project row"
                                      f"{'' if len(outside) == 1 else 's'} outside "
                                      f"{root_text} not checked."))

    bad_orgs: set[str] = set()
    for org in dict.fromkeys(o for o in (_org_of(r.path, root) for r in rows) if o):
        org_dir = root / org
        org_text = tilde(org_dir, home)
        if not org_dir.is_dir():
            bad_orgs.add(org)
            findings.append(missing(section, org, f"Org directory {org_text} does not exist.",
                                    f"mkdir -p {org_text}",
                                    you="Then run /run-organize-orgs there to write its "
                                        ".claude/org.json."))
        elif not (org_dir / ".claude" / "org.json").is_file() and \
                workspace_type(org_dir) not in UNGOVERNED_TYPES:
            findings.append(wrong(section, org, f"{org_text} has no .claude/org.json.",
                                  "run /run-organize-orgs"))

    present = absent = 0
    for row in rows:
        if row.path.is_dir():
            present += 1
            continue
        if row.skipped:
            findings.append(note(section, f"{row.path_text} is not cloned; its row is marked "
                                          f"removed or paused, so it is skipped."))
            continue
        absent += 1
        org = _org_of(row.path, root)
        owner, alias = _row_owner(row.path, root)
        repo = row.path.name
        you = None
        if owner is None:
            you = (f"The owner is unknown because no identity contract governs "
                   f"{row.path_text}; run /run-organize-orgs for {org} first.")
        command = clone_remedy(owner, alias, repo, row.path_text)
        action = {"kind": "clone", "command": command, "dest": row.path_text} \
            if owner else None
        findings.append(missing(section, org, f"{row.name} is not cloned at {row.path_text}.",
                                command, you=you, action=action))
    findings.append(note(section, f"{present} of {present + absent} project rows present"
                                  f"{f' ({absent} not cloned)' if absent else ''}."))
    return findings


# The report, in print order; each entry is (title, function(ctx) -> list[Finding]).
Section = Callable[[AuditContext], list[Finding]]
SECTIONS: list[tuple[str, Section]] = [
    ("Device manifest", section_manifest),
    ("Platform", section_platform),
    ("Tools", section_tools),
    ("GitHub logins", section_github),
    ("SSH", section_ssh),
    ("git identity", section_git_identity),
    ("Claude Code", section_claude),
    ("AWS", section_aws),
    ("Keychain", section_keychain),
    ("Network", section_network),
    ("Workspace", section_workspace),
]


# --------------------------------------------------------------------------
# running and reporting
# --------------------------------------------------------------------------

def run_audit(ctx: AuditContext,
              sections: Optional[list[tuple[str, Section]]] = None
              ) -> list[tuple[str, list[Finding]]]:
    results = []
    for title, func in sections or SECTIONS:
        found = func(ctx)
        for finding in found:
            finding.section = finding.section or title
        results.append((title, found))
        if title == "Platform" and any(f.finding_class == WRONG for f in found):
            break  # an unsupported platform: the remaining checks do not apply
    return results


def exit_code(findings: Iterable[Finding]) -> int:
    classes = {f.finding_class for f in findings}
    if WRONG in classes:
        return 1
    if MISSING in classes:
        return 2
    return 0


def _print_block(prefix: str, text: str) -> None:
    lines = text.splitlines() or [""]
    print(f"{prefix}{lines[0]}")
    for line in lines[1:]:
        print(f"{CONTINUATION}{line}")


def render_text(ctx: AuditContext, results: list[tuple[str, list[Finding]]]) -> None:
    mode = "full checks, with network liveness" if ctx.full and ctx.liveness \
        else "cheap checks, local disk only"
    print(f"Device audit ({mode})")
    for title, found in results:
        print()
        print(title)
        if not found:
            print("clean")
        for finding in found:
            print(f"{LABELS[finding.severity]}: {finding.message}")
            if finding.remedy:
                _print_block(REMEDY_PREFIX, finding.remedy)
            if finding.you:
                _print_block(f"{CONTINUATION}you: ", finding.you)
    flat = [f for _, found in results for f in found]
    wrongs = sum(1 for f in flat if f.finding_class == WRONG)
    missings = sum(1 for f in flat if f.finding_class == MISSING)
    print()
    if not wrongs and not missings:
        print("Result: clean.")
    else:
        print(f"Result: {wrongs} action required, {missings} warning"
              f"{'' if missings == 1 else 's'}.")


class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on a bad argument, which here means "only missing"."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_CANNOT_RUN, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        description="Audit whether this machine can honor the org identity contracts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit codes:\n"
            "  0  clean (informational notes only)\n"
            "  1  at least one `wrong` finding (ACTION REQUIRED)\n"
            "  2  only `missing` findings (WARNING)\n"
            "  3  the audit could not run (Python older than 3.11, an invalid\n"
            "     manifest, or a bad argument)\n"
        ),
    )
    parser.add_argument("--audit", action="store_true",
                        help="run the audit (the default; accepted for symmetry)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--full", action="store_true",
                        help="add network liveness checks (ssh -T greeting per alias)")
    parser.add_argument("--no-liveness", action="store_true",
                        help="skip the network liveness checks (implied without --full)")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="read the device manifest from this path instead of "
                             "~/.config/lastmilefirst/device.toml")
    parser.add_argument("--workspace-root", type=Path, default=None,
                        help="workspace root holding the org directories "
                             "(default: the manifest's workspace.root, else ~/Code)")
    return parser


_CONTEXT_KEYS = {"manifest": None, "workspace_root": None, "full": False,
                 "no_liveness": False, "home": None}


def build_context(args: Any = None, **kwargs: Any) -> AuditContext:
    """The AuditContext main() audits, from parsed arguments and/or keywords.

    Reads `manifest` (a path or None), `workspace_root` (a path or None),
    `full`, `no_liveness`, and `home` (defaults to Path.home()) from `args`
    attributes, with keywords taking precedence. Raises ManifestError when the
    manifest cannot be used.
    """
    unknown = set(kwargs) - set(_CONTEXT_KEYS)
    if unknown:
        raise TypeError(f"unknown build_context argument(s): {', '.join(sorted(unknown))}")
    opts = {k: kwargs.get(k, getattr(args, k, default)) for k, default in _CONTEXT_KEYS.items()}
    home = Path(opts["home"]) if opts["home"] else Path.home()
    manifest_arg = opts["manifest"]
    manifest_path = expand(str(manifest_arg), home) if manifest_arg else \
        default_manifest_path(home=home)
    manifest = load_manifest(manifest_path if manifest_arg else None)
    root = expand(str(opts["workspace_root"]), home) if opts["workspace_root"] else \
        expand(manifest.workspace_root, home)
    full = bool(opts["full"])
    return AuditContext(
        home=home,
        workspace_root=root,
        manifest=manifest,
        manifest_path=manifest_path,
        full=full,
        liveness=full and not opts["no_liveness"],
        contracts=load_contracts(root),
    )


def main(argv: Optional[list[str]] = None) -> int:
    if not require_python():
        return EXIT_CANNOT_RUN
    args = build_parser().parse_args(argv)
    try:
        ctx = build_context(args)
    except ManifestError as exc:
        print(f"Device manifest error: {exc}", file=sys.stderr)
        return EXIT_CANNOT_RUN
    home, root, manifest = ctx.home, ctx.workspace_root, ctx.manifest
    results = run_audit(ctx)
    flat = [f for _, found in results for f in found]
    code = exit_code(flat)

    if args.json:
        print(json.dumps({
            "mode": "full" if ctx.liveness else "cheap",
            "manifest": tilde(manifest.path, home) if manifest.found else None,
            "workspace_root": tilde(root, home),
            "findings": [f.to_dict() for f in flat],
            "summary": {
                WRONG: sum(1 for f in flat if f.finding_class == WRONG),
                MISSING: sum(1 for f in flat if f.finding_class == MISSING),
            },
            "exit_code": code,
        }, indent=2))
    else:
        render_text(ctx, results)
    return code


# Network providers import this module by name; when it runs as a script, make
# that name resolve to this copy instead of loading a second one.
sys.modules.setdefault("audit_device", sys.modules[__name__])

if __name__ == "__main__":
    sys.exit(main())
