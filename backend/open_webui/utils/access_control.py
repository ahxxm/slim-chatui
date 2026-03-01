from open_webui.config import DEFAULT_USER_PERMISSIONS


def has_permission(permission_key: str, user_permissions: dict) -> bool:
    """Check a dot-path permission key against user_permissions merged over defaults."""
    merged = {**DEFAULT_USER_PERMISSIONS}
    for key, value in user_permissions.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    current = merged
    for key in permission_key.split("."):
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    return bool(current)
