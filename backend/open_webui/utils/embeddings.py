import logging
import sys

from fastapi import Request
from open_webui.models.users import UserModel
from open_webui.utils.models import check_model_access
from open_webui.env import GLOBAL_LOG_LEVEL

from open_webui.routers.openai import embeddings as openai_embeddings

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


async def generate_embeddings(
    request: Request,
    form_data: dict,
    user: UserModel,
):
    # Attach extra metadata from request.state if present
    if hasattr(request.state, "metadata"):
        if "metadata" not in form_data:
            form_data["metadata"] = request.state.metadata
        else:
            form_data["metadata"] = {
                **form_data["metadata"],
                **request.state.metadata,
            }

    # If "direct" flag present, use only that model
    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data.get("model")
    if model_id not in models:
        raise Exception("Model not found")
    model = models[model_id]

    if not getattr(request.state, "direct", False):
        if user.role == "user":
            check_model_access(model)

    return await openai_embeddings(
        request=request,
        form_data=form_data,
        user=user,
    )
