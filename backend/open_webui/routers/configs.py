from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from typing import Optional

from open_webui.utils.auth import get_admin_user
from open_webui.config import get_config, save_config


router = APIRouter()


############################
# ImportConfig
############################


class ImportConfigForm(BaseModel):
    config: dict


@router.post("/import", response_model=dict)
async def import_config(form_data: ImportConfigForm, user=Depends(get_admin_user)):
    save_config(form_data.config)
    return get_config()


############################
# ExportConfig
############################


@router.get("/export", response_model=dict)
async def export_config(user=Depends(get_admin_user)):
    return get_config()


############################
# SetDefaultModels
############################
class ModelsConfigForm(BaseModel):
    DEFAULT_MODELS: Optional[str]
    DEFAULT_PINNED_MODELS: Optional[str]
    DEFAULT_MODEL_METADATA: Optional[dict] = None


@router.get("/models", response_model=ModelsConfigForm)
async def get_models_config(request: Request, user=Depends(get_admin_user)):
    return {
        "DEFAULT_MODELS": request.app.state.config.DEFAULT_MODELS,
        "DEFAULT_PINNED_MODELS": request.app.state.config.DEFAULT_PINNED_MODELS,
        "DEFAULT_MODEL_METADATA": request.app.state.config.DEFAULT_MODEL_METADATA,
    }


@router.post("/models", response_model=ModelsConfigForm)
async def set_models_config(
    request: Request,
    form_data: ModelsConfigForm,
    user=Depends(get_admin_user),
):
    request.app.state.config.DEFAULT_MODELS = form_data.DEFAULT_MODELS
    request.app.state.config.DEFAULT_PINNED_MODELS = form_data.DEFAULT_PINNED_MODELS
    request.app.state.config.DEFAULT_MODEL_METADATA = form_data.DEFAULT_MODEL_METADATA
    request.app.state.config.persist()
    return {
        "DEFAULT_MODELS": request.app.state.config.DEFAULT_MODELS,
        "DEFAULT_PINNED_MODELS": request.app.state.config.DEFAULT_PINNED_MODELS,
        "DEFAULT_MODEL_METADATA": request.app.state.config.DEFAULT_MODEL_METADATA,
    }


class PromptSuggestion(BaseModel):
    title: list[str]
    content: str


class SetDefaultSuggestionsForm(BaseModel):
    suggestions: list[PromptSuggestion]


@router.post("/suggestions", response_model=list[PromptSuggestion])
async def set_default_suggestions(
    request: Request,
    form_data: SetDefaultSuggestionsForm,
    user=Depends(get_admin_user),
):
    data = form_data.model_dump()
    request.app.state.config.DEFAULT_PROMPT_SUGGESTIONS = data["suggestions"]
    request.app.state.config.persist()
    return request.app.state.config.DEFAULT_PROMPT_SUGGESTIONS


