import copy
import logging
import sys

from fastapi import Request

from open_webui.routers import openai

from open_webui.models.models import Models

from open_webui.env import GLOBAL_LOG_LEVEL
from open_webui.models.users import UserModel

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


async def get_all_base_models(request: Request, user: UserModel = None):
    response = await openai.get_all_models(request, user=user)
    return response["data"]


async def get_all_models(request, user: UserModel = None):
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
                if custom_model.id == model["id"]:
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
                if custom_model.base_model_id == m["id"]:
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
