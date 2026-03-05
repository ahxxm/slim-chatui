import logging
import sys

from typing import Any

from fastapi import Request

from open_webui.routers.openai import (
    generate_chat_completion as generate_openai_chat_completion,
)

from open_webui.env import GLOBAL_LOG_LEVEL

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user: Any,
    bypass_system_prompt: bool = False,
):
    log.debug(f"generate_chat_completion: {form_data}")

    if hasattr(request.state, "metadata"):
        if "metadata" not in form_data:
            form_data["metadata"] = request.state.metadata
        else:
            form_data["metadata"] = {
                **form_data["metadata"],
                **request.state.metadata,
            }

    model_id = form_data["model"]
    if model_id not in request.app.state.MODELS:
        raise Exception("Model not found")

    return await generate_openai_chat_completion(
        request=request,
        form_data=form_data,
        user=user,
        bypass_system_prompt=bypass_system_prompt,
    )
