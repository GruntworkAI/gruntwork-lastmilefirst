"""Hierarchy rule extraction leaves enumeration and safety policy with readers."""
from pathlib import Path

import workspace_types as wt


def test_supplied_hierarchy_descends_one_client_tier_only():
    org = Path("/unread/example")
    client, flat = org / "counterparty", org / "flat"
    nested = client / "nested-client"
    layout = wt.classify_org_entries(
        org,
        [(client, "client"), (flat, "studio")],
        {client: [nested, client / "plain"], nested: [nested / "too-deep"]},
    )
    assert layout.containers == (client,)
    assert layout.projects == (
        wt.Project(nested, ("example", "counterparty", "nested-client"), "counterparty"),
        wt.Project(client / "plain", ("example", "counterparty", "plain"), "counterparty"),
        wt.Project(flat, ("example", "flat")),
    )


def test_classification_preserves_supplied_order_and_does_not_filter():
    org = Path("/unread/example")
    supplied = [(org / "z", None), (org / ".hidden", "unknown"), (org / "a", "external")]
    layout = wt.classify_org_entries(org, supplied, {})
    assert [project.path for project in layout.projects] == [path for path, _ in supplied]
    assert layout.containers == ()
    # Strict readers may remove malformed/evidence-free entries themselves.
    filtered = wt.classify_org_entries(org, [supplied[0]], {})
    assert [project.path for project in filtered.projects] == [org / "z"]


def test_empty_container_is_classified_and_reports_its_own_layout_issues():
    org = Path("/unread/example")
    container = org / "counterparty"
    assert wt.classify_org_entries(org, [(container, "client")], {}) == wt.ProjectLayout((), (container,))
    issues = wt.container_layout_issues(org, container, has_org_config=True, is_repo=True)
    assert [(issue.path, issue.kind) for issue in issues] == [
        (container, "container-org-json"), (container, "container-is-repo"),
    ]
    assert "example/counterparty" in issues[0].message
    assert "example/counterparty" in issues[1].message


def test_layout_presence_policy_is_supplied_not_inferred():
    org = Path("/unread/example")
    container, nested = org / "counterparty", org / "counterparty" / "nested"
    markers = [(nested, "client"), (container / "ordinary", None)]
    issues = wt.container_layout_issues(
        org, container, has_org_config=False, is_repo=False, child_markers=markers,
    )
    assert [(issue.path, issue.kind) for issue in issues] == [(nested, "nested-container")]
    assert issues[0].message == (
        "example/counterparty/nested is marked as a client directory inside another one. "
        "Only one level is supported, so it is treated as a project."
    )
    stricter = wt.container_layout_issues(
        org, container, has_org_config=True, is_repo=True, child_markers=markers,
    )
    assert [issue.kind for issue in stricter] == ["container-org-json", "container-is-repo", "nested-container"]


def test_pure_hierarchy_helpers_make_no_filesystem_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Pure layout rules must not read the filesystem")

    for name in ("read_text", "resolve", "is_file", "is_dir", "exists", "iterdir"):
        monkeypatch.setattr(Path, name, forbidden)
    org = Path("/not-read/example")
    container = org / "client"
    assert wt.classify_org_entries(org, [(container, "client")], {}).containers == (container,)
    assert len(wt.container_layout_issues(org, container, has_org_config=True, is_repo=True)) == 2


def test_canonical_layout_retains_file_and_exists_presence_policy(tmp_path):
    org = tmp_path / "example"
    container = org / "client"
    (container / ".claude" / "org.json").mkdir(parents=True)
    (container / ".claude-workspace").write_text("type: client\n")
    (container / ".git").write_text("gitdir: elsewhere\n")
    # A directory called org.json was never a canonical container-org-json
    # issue. A .git file is still a repo-presence issue, without following it.
    assert [issue.kind for issue in wt.layout_issues(org)] == ["container-is-repo"]


def test_canonical_loader_preserves_first_marker_type_even_when_repeated(tmp_path):
    org = tmp_path / "example"
    client = org / "client"
    (client / "project").mkdir(parents=True)
    (client / ".claude-workspace").write_text("type: client\ntype: studio\n")
    assert [project.key for project in wt.iter_projects(org)] == ["example/client/project"]


def test_canonical_wrappers_use_shared_classification_and_issue_rules(tmp_path, monkeypatch):
    org = tmp_path / "example"
    container = org / "client"
    container.mkdir(parents=True)
    (container / ".claude-workspace").write_text("type: client\n")
    fake_project = wt.Project(container / "provided", ("example", "client", "provided"), "client")
    fake_issue = wt.LayoutIssue(container, "provided", "shared decision")
    monkeypatch.setattr(wt, "classify_org_entries", lambda *args: wt.ProjectLayout((fake_project,), (container,)))
    monkeypatch.setattr(wt, "container_layout_issues", lambda *args, **kwargs: [fake_issue])
    assert list(wt.iter_projects(org)) == [fake_project]
    assert wt.layout_issues(org) == [fake_issue]
