"""The --all walk through client directories (plan 2026-09-28-001, U2).

gitleaks, the per-repo scan, and the GitHub posture sweep are replaced with
stand-ins, and the Overwatch state directory is redirected to tmp_path, so the
test measures only which repos the walk opens and which keys it records.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import github_protections
import overwatch
import scanner


def mark(directory: Path, kind: str = "client") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".claude-workspace").write_text(f"type: {kind}\n")
    return directory


def fake_repo(path: Path) -> Path:
    (path / ".git").mkdir(parents=True)
    return path


@pytest.fixture
def scanned(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr(overwatch, "get_state_dir", lambda: state_dir)
    monkeypatch.setattr(scanner, "_check_gitleaks", lambda: None)
    monkeypatch.setattr(github_protections, "sweep_accounts", lambda _ws: [])
    opened = []

    def fake_scan(repo, *args, **kwargs):
        opened.append(repo)
        return 0, ""

    monkeypatch.setattr(scanner, "scan_repo", fake_scan)
    return opened


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "Code"
    fake_repo(ws / "acme" / "practice")
    mark(ws / "acme" / "northwind")
    fake_repo(ws / "acme" / "northwind" / "web")
    (ws / "acme" / "northwind" / "notes").mkdir()  # no .git
    fake_repo(ws / "flat" / "alpha")
    return ws


def test_depth_three_repo_under_a_client_directory_is_scanned(workspace, scanned):
    code, report = scanner.scan_workspace(workspace)

    assert code == 0
    assert workspace / "acme" / "northwind" / "web" in scanned
    assert "acme/northwind/web: clean" in report
    assert "Scanned 3 repos" in report


def test_client_directory_without_git_is_not_scanned(workspace, scanned):
    scanner.scan_workspace(workspace)

    assert workspace / "acme" / "northwind" not in scanned
    assert workspace / "acme" / "northwind" / "notes" not in scanned


def test_scan_records_the_nested_key(workspace, scanned):
    scanner.scan_workspace(workspace)

    projects = overwatch.load_state()["projects"]
    assert set(projects) == {"acme/northwind/web", "acme/practice", "flat/alpha"}
    assert projects["acme/northwind/web"]["last_secret_scan"] > 0
