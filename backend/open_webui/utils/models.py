import logging

from fastapi import Request

from open_webui.routers import openai

from open_webui.models.users import UserModel

log = logging.getLogger(__name__)


async def get_all_models(request, user: UserModel = None):
    response = await openai.get_all_models(request, user=user)
    models = response["data"]
    request.app.state.BASE_MODELS = models

    log.debug(f"get_all_models() returned {len(models)} models")

    request.app.state.MODELS = {model["id"]: model for model in models}

    return models
