"""
Tailscale, the network provider shipped in v1.

Manifest keys, all optional, in the `[network.tailscale]` table:

    tailnet   string   the tailnet name `tailscale status` reports for this
                       device. Checked when set and not "(specify)".
    ssh       boolean  whether Tailscale SSH should be on for this device.

What the audit checks, in order:

1. Installed. macOS: the app at /Applications/Tailscale.app or a `tailscale`
   command on PATH (Homebrew's standalone build). Linux: `tailscale` on PATH.
2. On macOS with the app installed, the command-line tool is on PATH and runs.
   A failure with the app's bundle-identifier error is the known mismatch
   between the app and a CLI linked out of its bundle. A version that differs
   from the app's is reported, not flagged.
3. The background service answers `tailscale status --json`, and its
   BackendState: Running is fine; Stopped is a note (stopping it can be
   deliberate); NeedsLogin is missing, with `tailscale up` as a step for you.
4. The tailnet equals `tailnet`, when one is declared.
5. Tailscale SSH is on, when `ssh = true` and the device is running.
6. The device's MagicDNS name, as a note.

Only these JSON fields are read: BackendState, CurrentTailnet.Name,
CurrentTailnet.MagicDNSEnabled, Self.DNSName, and whether Self.sshHostKeys is
present (its contents are not read). `tailscale debug prefs` is never run,
because its output can carry node key material.
"""
from __future__ import annotations

import json
import plistlib
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

import audit_device
from audit_device import INFO, Finding, missing, note, wrong

SECTION = "Network"
TIMEOUT = 5.0
MAC_APP = Path("/Applications/Tailscale.app")
UNSET = "(specify)"
BUNDLE_SYMPTOM = "BundleIdentifiers"

MAC_INSTALL = "brew install --cask tailscale-app"
LINUX_INSTALL = "curl -fsSL https://tailscale.com/install.sh | sh"

CLI_REPAIR = (
    "The app is installed but its command-line tool cannot be used from a shell. The usual\n"
    "cause is a `tailscale` link that points into the app bundle, which macOS refuses to run\n"
    "that way. Swap it for Homebrew's standalone build:\n"
    "ls -l /usr/local/bin/tailscale   # if this is a link into /Applications/Tailscale.app,\n"
    "rm /usr/local/bin/tailscale      # remove that link\n"
    "brew install tailscale\n"
    "Open a new shell and confirm `tailscale version` prints a version. A small version\n"
    "difference between the app and this tool is expected and harmless."
)


# --------------------------------------------------------------------------
# probes
# --------------------------------------------------------------------------

def _system() -> str:
    return audit_device._system()


def _run(args: list[str]) -> tuple[str, Optional[subprocess.CompletedProcess]]:
    """("ok", result), ("absent", None), or ("timeout", None)."""
    try:
        return "ok", subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT,
                                    stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return "timeout", None
    except (FileNotFoundError, OSError):
        return "absent", None


def app_version() -> Optional[str]:
    """The app's CFBundleShortVersionString, or None."""
    plist = MAC_APP / "Contents" / "Info.plist"
    try:
        with plist.open("rb") as handle:
            value = plistlib.load(handle).get("CFBundleShortVersionString")
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    return value if isinstance(value, str) else None


def _cli() -> Optional[str]:
    return shutil.which("tailscale")


def status() -> tuple[str, Optional[dict], str]:
    """(state, parsed, detail) from `tailscale status --json`.

    state is one of: ok, absent, timeout, bundle, daemon, unparsable.
    """
    kind, result = _run(["tailscale", "status", "--json"])
    if result is None:
        return kind, None, ""
    combined = f"{result.stdout}\n{result.stderr}"
    if BUNDLE_SYMPTOM in combined:
        return "bundle", None, ""
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        data = None
    if isinstance(data, dict) and isinstance(data.get("BackendState"), str):
        return "ok", data, ""
    err = result.stderr.strip().splitlines()
    first = err[0][:200] if err else ""
    if result.returncode != 0 and "tailscaled" in combined.lower():
        return "daemon", None, first
    return "unparsable", None, first


def _installed() -> bool:
    if _system() == "Darwin" and MAC_APP.is_dir():
        return True
    return _cli() is not None


# --------------------------------------------------------------------------
# interface
# --------------------------------------------------------------------------

def detect() -> dict[str, Any]:
    """installed, running, and the tailnet name when the service reports one."""
    info: dict[str, Any] = {"installed": _installed(), "running": False}
    if not info["installed"] or _cli() is None:
        return info
    state, data, _ = status()
    if state == "ok" and data is not None:
        info["running"] = data.get("BackendState") == "Running"
        tailnet = (data.get("CurrentTailnet") or {}).get("Name")
        if isinstance(tailnet, str) and tailnet:
            info["tailnet"] = tailnet
        info["ssh"] = "sshHostKeys" in (data.get("Self") or {})
    return info


def _up_command() -> str:
    return "sudo tailscale up" if _system() == "Linux" else "tailscale up"


def handoff(table: dict) -> list[str]:
    """The sign-in commands `--install` prints as `you` steps."""
    steps = [_up_command()]
    if table.get("ssh") is True:
        steps.append("tailscale set --ssh")
    return steps


def _note_with_step(message: str, step: str) -> Finding:
    return Finding(INFO, None, message, None, section=SECTION, you=step)


def _check_table(table: dict) -> list[Finding]:
    findings = []
    if "tailnet" in table and not isinstance(table["tailnet"], str):
        findings.append(wrong(SECTION, None, "network.tailscale.tailnet must be a string.",
                              'In device.toml: tailnet = "<your tailnet name>"'))
    if "ssh" in table and not isinstance(table["ssh"], bool):
        findings.append(wrong(SECTION, None, "network.tailscale.ssh must be true or false.",
                              "In device.toml: ssh = true"))
    unknown = sorted(set(table) - {"tailnet", "ssh"})
    if unknown:
        findings.append(wrong(SECTION, None,
                              f"Unknown key(s) in [network.tailscale]: {', '.join(unknown)}.",
                              "Remove them; the known keys are tailnet and ssh."))
    return findings


def audit(table: dict, ctx: Any) -> list[Finding]:
    table = dict(table or {})
    findings = _check_table(table)
    if findings:
        return findings
    system = _system()

    if not _installed():
        remedy = MAC_INSTALL if system == "Darwin" else LINUX_INSTALL
        return [missing(SECTION, None, "Tailscale is not installed.", remedy,
                        you=f"Then sign in: {_up_command()}")]

    if system == "Darwin" and MAC_APP.is_dir():
        if _cli() is None:
            return [wrong(SECTION, None,
                          "The Tailscale app is installed but `tailscale` is not on PATH.",
                          CLI_REPAIR)]
        kind, result = _run(["tailscale", "version"])
        if kind == "timeout":
            return [wrong(SECTION, None, "`tailscale version` did not answer in time.",
                          "Quit and reopen the Tailscale app, then run `tailscale version`.")]
        if result is None or result.returncode != 0 or \
                BUNDLE_SYMPTOM in f"{result.stdout}{result.stderr}":
            return [wrong(SECTION, None,
                          "`tailscale` on PATH fails with the app bundle mismatch.",
                          CLI_REPAIR)]
        cli_version = (result.stdout.strip().splitlines() or [""])[0].strip()
        app = app_version()
        if app and cli_version and app != cli_version:
            findings.append(note(SECTION, f"The Tailscale app is {app} and the command-line "
                                          f"tool is {cli_version}; a small difference is "
                                          f"harmless."))

    state, data, detail = status()
    if state == "bundle":
        return findings + [wrong(SECTION, None,
                                 "`tailscale status` fails with the app bundle mismatch.",
                                 CLI_REPAIR)]
    if state == "daemon":
        start = "Open the Tailscale app." if system == "Darwin" else \
            "sudo systemctl enable --now tailscaled"
        return findings + [missing(SECTION, None,
                                   "The Tailscale background service is not running"
                                   + (f" ({detail})." if detail else "."),
                                   None, you=f"{start} Then: {_up_command()}")]
    if state != "ok" or data is None:
        why = "did not answer in time" if state == "timeout" else \
            "is not on PATH" if state == "absent" else "returned output that is not status JSON"
        return findings + [wrong(SECTION, None, f"`tailscale status --json` {why}.",
                                 "Run `tailscale status` by hand to see the error, then restart "
                                 "Tailscale (the app on macOS, `sudo systemctl restart "
                                 "tailscaled` on Linux).")]

    backend = data.get("BackendState")
    running = backend == "Running"
    if backend == "Stopped":
        findings.append(_note_with_step("Tailscale is installed and stopped.", _up_command()))
    elif backend == "NeedsLogin":
        findings.append(missing(SECTION, None, "Tailscale is installed but not signed in.",
                                None, you=f"Browser step: {_up_command()}"))
        return findings
    elif backend == "NeedsMachineAuth":
        findings.append(missing(SECTION, None,
                                "This device is waiting for approval in the tailnet.",
                                None, you="Approve the device in the Tailscale admin console."))
    elif not running:
        findings.append(note(SECTION, f"Tailscale reports state {backend}."))

    tailnet_info = data.get("CurrentTailnet") if isinstance(data.get("CurrentTailnet"),
                                                            dict) else {}
    expected = table.get("tailnet")
    actual = tailnet_info.get("Name") if isinstance(tailnet_info.get("Name"), str) else None
    if isinstance(expected, str) and expected.strip() and expected != UNSET:
        if actual is None:
            findings.append(note(SECTION, "Tailscale did not report a tailnet, so it was not "
                                          "compared with the manifest."))
        elif actual != expected:
            findings.append(wrong(SECTION, None,
                                  f"This device is on tailnet {actual}, the manifest expects "
                                  f"{expected}.",
                                  f"tailscale switch {expected}",
                                  you="If that tailnet is not signed in on this device yet, "
                                      "run `tailscale login` and choose it in the browser."))

    self_node = data.get("Self") if isinstance(data.get("Self"), dict) else {}
    if table.get("ssh") is True:
        if running and "sshHostKeys" not in self_node:
            findings.append(missing(SECTION, None, "Tailscale SSH is not on for this device.",
                                    "tailscale set --ssh"))
        elif not running:
            findings.append(note(SECTION, "Tailscale SSH is expected; it can be checked once "
                                          "Tailscale is running."))

    dns = self_node.get("DNSName")
    if isinstance(dns, str) and dns.strip("."):
        magic = tailnet_info.get("MagicDNSEnabled")
        suffix = "" if magic is not False else " (MagicDNS is off on this tailnet)"
        findings.append(note(SECTION, f"MagicDNS name: {dns.rstrip('.')}{suffix}."))
    return findings
