from typing import Optional, Dict, Any

from open_webui.config import DEFAULT_USER_PERMISSIONS
import json


def get_permissions(
    user_id: str,
    default_permissions: Dict[str, Any],
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    return json.loads(json.dumps(default_permissions))


def has_permission(
    user_id: str,
    permission_key: str,
    default_permissions: Dict[str, Any] = {},
    db: Optional[Any] = None,
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
