from open_webui.utils.misc import (
    deep_update,
    add_or_update_system_message,
    replace_system_message_content,
)

from typing import Optional
import json


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


OPEN_WEBUI_PARAMS = {
    "stream_delta_chunk_size",
    "system",
}

OPENAI_PARAM_CASTS = {
    "temperature": float,
    "top_p": float,
    "reasoning_effort": str,
    "seed": lambda x: x,
    "stop": lambda x: [bytes(s, "utf-8").decode("unicode_escape") for s in x],
    "response_format": dict,
}


# inplace function: form_data is modified
def apply_model_params_to_body_openai(params: dict, form_data: dict) -> dict:
    if not params:
        return form_data

    for key in OPEN_WEBUI_PARAMS:
        params.pop(key, None)

    custom_params = params.pop("custom_params", {})
    if custom_params:
        for key, value in custom_params.items():
            if isinstance(value, str):
                try:
                    custom_params[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass
        params = deep_update(params, custom_params)

    for key, value in params.items():
        if value is not None:
            cast_func = OPENAI_PARAM_CASTS.get(key)
            if cast_func is not None:
                form_data[key] = cast_func(value)
            else:
                form_data[key] = value

    return form_data
