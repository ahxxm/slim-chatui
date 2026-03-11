from open_webui.utils.misc import (
    add_or_update_system_message,
    replace_system_message_content,
)

from typing import Optional


# inplace function: form_data is modified
def apply_system_prompt_to_body(
    system: Optional[str],
    form_data: dict,
    replace: bool = False,
) -> dict:
    if not system:
        return form_data

    if replace:
        form_data["messages"] = replace_system_message_content(
            system, form_data.get("messages", [])
        )
    else:
        form_data["messages"] = add_or_update_system_message(
            system, form_data.get("messages", [])
        )

    return form_data
