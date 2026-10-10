"""Tests for scripts/bootstrap.sh.

The script is never run against the real machine. Each run gets a fresh HOME
under tmp_path, a minimal environment, and a directory of stub binaries placed
first on PATH (uname, brew, curl, python3, claude, jq, git, gh, node, rg, and
apt-get and sudo for the Linux path). Every stub appends its arguments to a
log, so a test can assert what the script did and did not call. Runs start a
new session with stdin closed, so there is no terminal to read from, and a
timeout turns a hang into a failure.
"""
from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "bootstrap.sh"
TIMEOUT = 30


def _write_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class FakeMachine:
    """A temp HOME plus stub binaries that record every call."""

    def __init__(self, root: Path, kernel: str = "Darwin") -> None:
        self.root = root
        self.home = root / "home"
        self.bin = root / "stubs"
        self.state = root / "state"
        self.brew_prefix = root / "brew-prefix"
        self.log = root / "calls.log"
        for d in (self.home, self.bin, self.state, self.brew_prefix / "bin"):
            d.mkdir(parents=True)
        self.log.write_text("")
        self.kernel = kernel
        self.python_upgrades = True
        self.claude_present = True
        self.gh_version = "2.62.0"
        self.curl_fails = False
        self.apt_update_fails = False

    def _rec(self, name: str) -> str:
        return f'printf "%s\\n" "{name} $*" >> "{self.log}"\n'

    def install(self) -> None:
        log, state = self.log, self.state
        _write_stub(self.bin, "uname", self._rec("uname") + f"""
case "$1" in
  -s) echo "{self.kernel}" ;;
  -m) echo arm64 ;;
  *) echo "{self.kernel}" ;;
esac
""")
        _write_stub(self.bin, "brew", self._rec("brew") + f"""
case "$1" in
  --prefix) echo "{self.brew_prefix}" ;;
  shellenv) : ;;
  install)
    if [ "$2" = "python" ] && [ "{int(self.python_upgrades)}" = "1" ]; then
      touch "{state}/python-upgraded"
    fi ;;
esac
exit 0
""")
        _write_stub(self.bin, "python3", self._rec("python3") + f"""
v=3.10
[ -f "{state}/python-upgraded" ] && v=3.12
case "$*" in
  *SystemExit*) [ "$v" = 3.12 ] && exit 0; exit 1 ;;
  *print*) echo "$v" ;;
esac
exit 0
""")
        curl_exit = "exit 22" if self.curl_fails else "echo 'echo stub installer ran'"
        _write_stub(self.bin, "curl", self._rec("curl") + curl_exit + "\n")
        if self.claude_present:
            _write_stub(self.bin, "claude", self._rec("claude") + """
case "$*" in
  --version) echo "2.0.0 (Claude Code)" ;;
  *"--json"*) echo "[]" ;;
esac
exit 0
""")
        # The plugin step pipes `--json` output through jq; "1" means present.
        _write_stub(self.bin, "jq", self._rec("jq") + "cat >/dev/null\necho 1\n")
        _write_stub(self.bin, "git", self._rec("git") + "exit 0\n")
        _write_stub(self.bin, "gh", self._rec("gh") + f"""
[ "$1" = "--version" ] && echo "gh version {self.gh_version} (2024-01-01)"
exit 0
""")
        _write_stub(self.bin, "node", self._rec("node") + "exit 0\n")
        _write_stub(self.bin, "rg", self._rec("rg") + "exit 0\n")
        if self.kernel == "Linux":
            # Reads one line so a run that hands it a terminal would block.
            update_exit = "exit 100" if self.apt_update_fails else "exit 0"
            _write_stub(self.bin, "apt-get", self._rec("apt-get") + f"""
if [ "$1" = "update" ]; then
  if read -r line; then echo "apt-get update read: $line" >> "{log}"; fi
  {update_exit}
fi
exit 0
""")
            _write_stub(self.bin, "sudo", self._rec("sudo") + 'exec "$@"\n')

    def run(self, *args: str) -> subprocess.CompletedProcess:
        self.install()
        env = {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "PATH": f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "LANG": "C",
        }
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), *args],
            env=env, cwd=str(self.root), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=TIMEOUT,
            start_new_session=True,
        )

    def calls(self, name: str) -> list[str]:
        return [line for line in self.log.read_text().splitlines()
                if line.split(" ", 1)[0] == name]


@pytest.fixture
def machine(tmp_path: Path) -> FakeMachine:
    return FakeMachine(tmp_path)


def test_bash_syntax_under_system_bash():
    result = subprocess.run(["/bin/bash", "-n", str(SCRIPT)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_shellcheck_clean():
    shellcheck = shutil.which("shellcheck")
    if not shellcheck:
        pytest.skip("shellcheck is not installed on this machine")
    result = subprocess.run([shellcheck, str(SCRIPT)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_clean_macos_run_reaches_handoff_without_a_terminal(machine):
    result = machine.run()
    assert result.returncode == 0, result.stderr
    assert "Done. The rest needs you." in result.stdout
    assert "WARNING" not in result.stderr


def test_old_python_upgraded_by_homebrew_gives_no_warning(machine):
    result = machine.run()
    assert result.returncode == 0, result.stderr
    assert any(c.startswith("brew install python") for c in machine.calls("brew"))
    assert "using: " in result.stdout and "3.12" in result.stdout
    assert "refuse to run below 3.11" not in result.stderr


def test_old_python_that_stays_old_warns_and_carries_into_handoff(machine):
    machine.python_upgrades = False
    result = machine.run()
    assert result.returncode == 0, result.stderr
    assert "the device audit will refuse to run below 3.11" in result.stderr
    assert "found 3.10" in result.stderr
    handoff = result.stdout.split("Done. The rest needs you.", 1)[1]
    assert "refuse to run below 3.11" in handoff


def test_unknown_platform_stops(tmp_path):
    machine = FakeMachine(tmp_path, kernel="Plan9")
    result = machine.run()
    assert result.returncode == 1
    assert "STOP: unsupported platform 'Plan9'" in result.stderr
    assert machine.calls("brew") == []
    assert machine.calls("curl") == []


def test_present_claude_is_not_reinstalled(machine):
    result = machine.run()
    assert result.returncode == 0, result.stderr
    assert "present: 2.0.0 (Claude Code)" in result.stdout
    assert not any("claude.ai/install.sh" in c for c in machine.calls("curl"))


def test_failed_claude_download_stops_with_a_reason(machine):
    machine.claude_present = False
    machine.curl_fails = True
    result = machine.run()
    assert result.returncode == 1
    assert ("STOP: could not download the Claude Code installer; "
            "check the network and rerun.") in result.stderr
    curl = machine.calls("curl")
    assert curl and "--connect-timeout 15" in curl[0] and "--max-time 300" in curl[0]


def test_apt_update_reads_no_terminal_and_old_gh_warns(tmp_path):
    machine = FakeMachine(tmp_path, kernel="Linux")
    machine.gh_version = "2.23.0"
    result = machine.run()
    assert result.returncode == 0, result.stderr
    assert [c for c in machine.calls("apt-get") if c.startswith("apt-get update")]
    assert "apt-get update read:" not in machine.log.read_text()
    assert "gh is 2.23, older than 2.40" in result.stderr
    handoff = result.stdout.split("Done. The rest needs you.", 1)[1]
    assert "https://github.com/cli/cli/blob/trunk/docs/install_linux.md" in handoff


def test_current_gh_on_apt_gives_no_warning(tmp_path):
    machine = FakeMachine(tmp_path, kernel="Linux")
    machine.python_upgrades = True
    (machine.state / "python-upgraded").touch()
    result = machine.run()
    assert result.returncode == 0, result.stderr
    assert "older than 2.40" not in result.stderr


def test_failed_apt_update_warns_and_continues(tmp_path):
    machine = FakeMachine(tmp_path, kernel="Linux")
    machine.apt_update_fails = True
    (machine.state / "python-upgraded").touch()
    result = machine.run()
    assert result.returncode == 0, result.stderr
    assert "WARNING: apt-get update did not finish" in result.stderr
    assert "Done. The rest needs you." in result.stdout
