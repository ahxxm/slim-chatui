from typing import Dict, Any

from open_webui.config import DEFAULT_USER_PERMISSIONS
import json


def get_permissions(
    default_permissions: Dict[str, Any],
) -> Dict[str, Any]:
    return json.loads(json.dumps(default_permissions))


def has_permission(
    permission_key: str,
    default_permissions: Dict[str, Any] = {},
) -> bool:
    merged = json.loads(json.dumps(DEFAULT_USER_PERMISSIONS))
    for key, value in default_permissions.items():
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
