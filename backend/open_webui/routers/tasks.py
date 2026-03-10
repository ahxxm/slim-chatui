from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse

from pydantic import BaseModel
from typing import Optional
import logging

from open_webui.routers.openai import generate_chat_completion
from open_webui.utils.task import (
    get_task_model_id,
    title_generation_template,
    follow_up_generation_template,
)
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.constants import TASKS

from open_webui.config import (
    DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE,
)

log = logging.getLogger(__name__)

router = APIRouter()


TASK_CONFIG_FIELDS = (
    "TASK_MODEL",
    "ENABLE_TITLE_GENERATION",
    "TITLE_GENERATION_PROMPT_TEMPLATE",
    "ENABLE_FOLLOW_UP_GENERATION",
    "FOLLOW_UP_GENERATION_PROMPT_TEMPLATE",
)


async def _run_task(
    request: Request,
    form_data: dict,
    user,
    *,
    task_type: TASKS,
    content: str,
):
    models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    task_model_id = get_task_model_id(
        model_id, request.app.state.config.TASK_MODEL, models
    )

    log.debug(f"generating {task_type} using model {task_model_id} for {user.email}")

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(task_type),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


class ActiveChatsForm(BaseModel):
    chat_ids: list[str]


@router.post("/active/chats")
async def check_active_chats(
    request: Request, form_data: ActiveChatsForm, user=Depends(get_verified_user)
):
    """Check which chat IDs have active tasks."""
    from open_webui.tasks import get_active_chat_ids

    active = get_active_chat_ids(form_data.chat_ids)
    return {"active_chat_ids": active}


@router.get("/config")
async def get_task_config(request: Request, user=Depends(get_verified_user)):
    return {
        field: getattr(request.app.state.config, field) for field in TASK_CONFIG_FIELDS
    }


class TaskConfigForm(BaseModel):
    TASK_MODEL: Optional[str]
    ENABLE_TITLE_GENERATION: bool
    TITLE_GENERATION_PROMPT_TEMPLATE: str
    FOLLOW_UP_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_FOLLOW_UP_GENERATION: bool


@router.post("/config/update")
async def update_task_config(
    request: Request,
    form_data: TaskConfigForm,
    user=Depends(get_admin_user),
):
    config = request.app.state.config
    for field in TASK_CONFIG_FIELDS:
        setattr(config, field, getattr(form_data, field))
    config.persist()

    return {field: getattr(config, field) for field in TASK_CONFIG_FIELDS}


@router.post("/title/completions")
async def generate_title(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    if not request.app.state.config.ENABLE_TITLE_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Title generation is disabled"},
        )

    template = (
        request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE
        or DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE
    )
    content = title_generation_template(template, form_data["messages"])

    return await _run_task(
        request,
        form_data,
        user,
        task_type=TASKS.TITLE_GENERATION,
        content=content,
    )


@router.post("/follow_up/completions")
async def generate_follow_ups(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    if not request.app.state.config.ENABLE_FOLLOW_UP_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Follow-up generation is disabled"},
        )

    template = (
        request.app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE
        or DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE
    )
    content = follow_up_generation_template(template, form_data["messages"])

    return await _run_task(
        request,
        form_data,
        user,
        task_type=TASKS.FOLLOW_UP_GENERATION,
        content=content,
    )
