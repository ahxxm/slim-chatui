import copy
import time
import logging
import asyncio
import sys

from fastapi import Request

from open_webui.routers import openai, ollama

from open_webui.models.models import Models
from open_webui.models.access_grants import AccessGrants
from open_webui.models.groups import Groups

from open_webui.config import (
    BYPASS_ADMIN_ACCESS_CONTROL,
)

from open_webui.env import BYPASS_MODEL_ACCESS_CONTROL, GLOBAL_LOG_LEVEL
from open_webui.models.users import UserModel

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


async def fetch_ollama_models(request: Request, user: UserModel = None):
    raw_ollama_models = await ollama.get_all_models(request, user=user)
    return [
        {
            "id": model["model"],
            "name": model["name"],
            "object": "model",
            "created": int(time.time()),
            "owned_by": "ollama",
            "ollama": model,
            "connection_type": model.get("connection_type", "local"),
            "tags": model.get("tags", []),
        }
        for model in raw_ollama_models["models"]
    ]


async def fetch_openai_models(request: Request, user: UserModel = None):
    openai_response = await openai.get_all_models(request, user=user)
    return openai_response["data"]


async def get_all_base_models(request: Request, user: UserModel = None):
    openai_task = (
        fetch_openai_models(request, user)
        if request.app.state.config.ENABLE_OPENAI_API
        else asyncio.sleep(0, result=[])
    )
    ollama_task = (
        fetch_ollama_models(request, user)
        if request.app.state.config.ENABLE_OLLAMA_API
        else asyncio.sleep(0, result=[])
    )

    openai_models, ollama_models = await asyncio.gather(openai_task, ollama_task)

    return openai_models + ollama_models


async def get_all_models(request, refresh: bool = False, user: UserModel = None):
    if (
        request.app.state.MODELS
        and request.app.state.BASE_MODELS
        and (request.app.state.config.ENABLE_BASE_MODELS_CACHE and not refresh)
    ):
        base_models = request.app.state.BASE_MODELS
    else:
        base_models = await get_all_base_models(request, user=user)
        request.app.state.BASE_MODELS = base_models

    # deep copy the base models to avoid modifying the original list
    models = [model.copy() for model in base_models]

    # If there are no models, return an empty list
    if len(models) == 0:
        return []

    custom_models = Models.get_all_models()
    for custom_model in custom_models:
        if custom_model.base_model_id is None:
            # Applied directly to a base model
            for model in models:
                if custom_model.id == model["id"] or (
                    model.get("owned_by") == "ollama"
                    and custom_model.id
                    == model["id"].split(":")[
                        0
                    ]  # Ollama may return model ids in different formats (e.g., 'llama3' vs. 'llama3:7b')
                ):
                    if custom_model.is_active:
                        model["name"] = custom_model.name
                        model["info"] = custom_model.model_dump()

                        if "info" in model:
                            if "params" in model["info"]:
                                del model["info"]["params"]
                    else:
                        models.remove(model)

        elif custom_model.is_active and (
            custom_model.id not in [model["id"] for model in models]
        ):
            # Custom model based on a base model
            owned_by = "openai"
            connection_type = None

            for m in models:
                if (
                    custom_model.base_model_id == m["id"]
                    or custom_model.base_model_id == m["id"].split(":")[0]
                ):
                    owned_by = m.get("owned_by", "unknown")
                    connection_type = m.get("connection_type", None)
                    break

            model = {
                "id": f"{custom_model.id}",
                "name": custom_model.name,
                "object": "model",
                "created": custom_model.created_at,
                "owned_by": owned_by,
                "connection_type": connection_type,
                "preset": True,
            }

            info = custom_model.model_dump()
            if "params" in info:
                del info["params"]

            model["info"] = info

            models.append(model)

    # Apply global model defaults to all models
    # Per-model overrides take precedence over global defaults
    default_metadata = (
        getattr(request.app.state.config, "DEFAULT_MODEL_METADATA", None) or {}
    )

    if default_metadata:
        for model in models:
            info = model.get("info")

            if info is None:
                model["info"] = {"meta": copy.deepcopy(default_metadata)}
                continue

            meta = info.setdefault("meta", {})
            for key, value in default_metadata.items():
                if key == "capabilities":
                    # Merge capabilities: defaults as base, per-model overrides win
                    existing = meta.get("capabilities") or {}
                    meta["capabilities"] = {**value, **existing}
                elif meta.get(key) is None:
                    meta[key] = copy.deepcopy(value)

    log.debug(f"get_all_models() returned {len(models)} models")

    models_dict = {model["id"]: model for model in models}
    request.app.state.MODELS = models_dict

    return models


def check_model_access(user, model, db=None):
    model_info = Models.get_model_by_id(model.get("id"), db=db)
    if not model_info:
        raise Exception("Model not found")
    elif not (
        user.id == model_info.user_id
        or AccessGrants.has_access(
            user_id=user.id,
            resource_type="model",
            resource_id=model_info.id,
            permission="read",
            db=db,
        )
    ):
        raise Exception("Model not found")


def get_filtered_models(models, user, db=None):
    # Filter out models that the user does not have access to
    if (
        user.role == "user"
        or (user.role == "admin" and not BYPASS_ADMIN_ACCESS_CONTROL)
    ) and not BYPASS_MODEL_ACCESS_CONTROL:
        model_infos = {}
        for model in models:
            info = model.get("info")
            if info:
                model_infos[model["id"]] = info

        user_group_ids = {
            group.id for group in Groups.get_groups_by_member_id(user.id, db=db)
        }

        # Batch-fetch accessible resource IDs in a single query instead of N has_access calls
        accessible_model_ids = AccessGrants.get_accessible_resource_ids(
            user_id=user.id,
            resource_type="model",
            resource_ids=list(model_infos.keys()),
            permission="read",
            user_group_ids=user_group_ids,
            db=db,
        )

        filtered_models = []
        for model in models:
            model_info = model_infos.get(model["id"])
            if model_info:
                if (
                    user.id == model_info.get("user_id")
                    or model["id"] in accessible_model_ids
                ):
                    filtered_models.append(model)

        return filtered_models
    else:
        return models
