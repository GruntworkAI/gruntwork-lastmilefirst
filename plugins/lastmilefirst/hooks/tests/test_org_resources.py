"""Shared settings keep legacy hook policy separate from bounded audit policy."""
import pytest

from org_resources import RESOURCE_NAMES, resource_defaults, resource_settings
from session_start import check_org_infrastructure


def test_defaults_and_custom_paths():
    assert tuple(resource_defaults("example")) == RESOURCE_NAMES
    assert resource_defaults("example") == {
        "operatives": "example-operatives", "stack_wisdom": "example-stack-wisdom",
        "stack_knowledge": "stack-knowledge",
    }
    for strict in (False, True):
        assert resource_settings("example", "operatives", {}, strict=strict)["relative"] == "example-operatives"
        assert resource_settings("example", "stack_wisdom", {"stack_wisdom": {"repo": "wisdom"}}, strict=strict)["relative"] == "wisdom"
        assert resource_settings("example", "stack_knowledge", {"stack_knowledge": {"path": "facts"}}, strict=strict)["relative"] == "facts"


@pytest.mark.parametrize("name", RESOURCE_NAMES)
def test_opt_out_precedes_other_validation(name):
    assert resource_settings("example", name, {name: {"enabled": False, "repo": 42}}, strict=True)["status"] == "opted-out"


def test_non_boolean_enable_policy_is_explicit():
    config = {"operatives": {"enabled": "false"}}
    assert resource_settings("example", "operatives", config)["status"] == "configured"
    strict = resource_settings("example", "operatives", config, strict=True)
    assert strict["status"] == "malformed"
    assert strict["problem"] == "operatives.enabled must be a boolean."


def test_malformed_resource_policy_is_explicit():
    assert resource_settings("example", "operatives", {"operatives": []}, strict=True)["status"] == "malformed"
    with pytest.raises(AttributeError):
        resource_settings("example", "operatives", {"operatives": []})


def test_external_backend_is_only_resolved_not_accessed():
    result = resource_settings("example", "stack_knowledge", {"stack_knowledge": {"type": "remote"}}, strict=True)
    assert result["status"] == "external"
    assert result["backend"] == "remote"
    assert result["relative"] is None


def test_path_permissions_stay_with_caller():
    result = resource_settings("example", "operatives", {"operatives": {"repo": "../outside"}}, strict=True)
    assert result["relative"] == "../outside"


def test_session_start_keeps_legacy_non_boolean_opt_out_semantics(tmp_path):
    org = tmp_path / "example"
    (org / ".claude").mkdir(parents=True)
    (org / ".claude/org.json").write_text('{"operatives":{"enabled":"false"},"stack_wisdom":{"enabled":false}}')
    assert check_org_infrastructure({"workspace": str(tmp_path), "orgs": ["example"]}) == [
        "WARNING: Org 'example' missing operatives repo — run /run-organize-orgs"
    ]
