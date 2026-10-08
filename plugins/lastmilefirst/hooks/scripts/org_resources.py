"""Pure shared-resource settings; callers own filesystem access and reporting.

Legacy session-start accepts truthy/non-boolean enabled values. Bounded audits
opt into strict shape validation without changing that existing hook policy.
"""

RESOURCE_NAMES = ("operatives", "stack_wisdom", "stack_knowledge")


def resource_defaults(org_name):
    return {"operatives": org_name + "-operatives",
            "stack_wisdom": org_name + "-stack-wisdom",
            "stack_knowledge": "stack-knowledge"}


def resource_settings(org_name, name, config, *, strict=False):
    """Resolve one resource's defaults, opt-out, and backend from read data.

    ``relative`` is untrusted configuration, not permission to open a path.
    Each caller must apply its own path/access policy before using it.
    """
    default = resource_defaults(org_name)[name]
    value = config.get(name, {})
    result = {"name": name, "status": "configured", "relative": None,
              "backend": "local", "problem": None}
    if strict and not isinstance(value, dict):
        result.update(status="malformed", problem=f"{name} must be an object.")
    elif value.get("enabled") is False:
        result["status"] = "opted-out"
    elif strict and "enabled" in value and not isinstance(value["enabled"], bool):
        result.update(status="malformed", problem=f"{name}.enabled must be a boolean.")
    elif name == "stack_knowledge" and value.get("type", "local") != "local":
        result.update(status="external", backend=value.get("type"))
    else:
        result["relative"] = value.get("path" if name == "stack_knowledge" else "repo", default)
    return result
