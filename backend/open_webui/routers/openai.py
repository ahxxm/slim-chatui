import asyncio
import hashlib
import json
import logging
from typing import Optional

import aiohttp
from aiocache import cached
import requests

from fastapi import Depends, HTTPException, Request, APIRouter
from fastapi.responses import (
    FileResponse,
    StreamingResponse,
    JSONResponse,
    PlainTextResponse,
)
from pydantic import BaseModel, ConfigDict

from open_webui.config import (
    CACHE_DIR,
)
from open_webui.env import (
    AIOHTTP_CLIENT_SESSION_SSL,
    AIOHTTP_CLIENT_TIMEOUT,
    AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
)
from open_webui.models.users import UserModel

from open_webui.constants import ERROR_MESSAGES


from open_webui.utils.misc import (
    cleanup_response,
    stream_chunks_handler,
    stream_wrapper,
)

from open_webui.utils.auth import get_admin_user, get_verified_user

log = logging.getLogger(__name__)


##########################################
#
# Utility functions
#
##########################################


async def send_get_request(url, key=None):
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            headers = {
                **({"Authorization": f"Bearer {key}"} if key else {}),
            }

            async with session.get(
                url,
                headers=headers,
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
            ) as response:
                return await response.json()
    except Exception as e:
        log.error(f"Connection error: {e}")
        return None


async def _proxy_request(
    *,
    method: str,
    url: str,
    data: str | bytes | None = None,
    headers: dict,
    cookies: dict,
    stream_handler=None,
    timeout: int = AIOHTTP_CLIENT_TIMEOUT,
):
    """Make an aiohttp request with streaming support and automatic cleanup.

    For SSE responses, returns StreamingResponse (session stays open for streaming).
    For non-streaming success, returns the parsed response (dict/list/str).
    For upstream errors (status >= 400), returns JSONResponse or PlainTextResponse.
    """
    r = None
    session = None
    streaming = False

    try:
        session = aiohttp.ClientSession(
            trust_env=True, timeout=aiohttp.ClientTimeout(total=timeout)
        )
        r = await session.request(
            method=method,
            url=url,
            data=data,
            headers=headers,
            cookies=cookies,
            ssl=AIOHTTP_CLIENT_SESSION_SSL,
        )

        if "text/event-stream" in r.headers.get("Content-Type", ""):
            streaming = True
            wrapper_args = (
                (r, session, stream_handler) if stream_handler else (r, session)
            )
            return StreamingResponse(
                stream_wrapper(*wrapper_args),
                status_code=r.status,
                headers=dict(r.headers),
            )

        try:
            response_data = await r.json()
        except Exception:
            response_data = await r.text()

        if r.status >= 400:
            if isinstance(response_data, (dict, list)):
                return JSONResponse(status_code=r.status, content=response_data)
            return PlainTextResponse(status_code=r.status, content=response_data)

        return response_data

    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=r.status if r else 500,
            detail="Open WebUI: Server Connection Error",
        )
    finally:
        if not streaming:
            await cleanup_response(r, session)


def fix_openai_system_role(model: str, payload):
    if not model.lower().startswith(("o1", "o3", "o4", "gpt-5")):
        return payload

    if model.lower().startswith("o1"):
        log.warning(f"{model}, seriously? ")

    # Handle system role conversion based on model type
    if payload["messages"][0]["role"] == "system":
        model_lower = payload["model"].lower()
        # Legacy models use "user" role instead of "system"
        if model_lower.startswith("o1-mini") or model_lower.startswith("o1-preview"):
            payload["messages"][0]["role"] = "user"
        else:
            payload["messages"][0]["role"] = "developer"

    return payload


async def get_headers_and_cookies(
    request: Request,
    url,
    key=None,
    config=None,
    metadata: Optional[dict] = None,
    user: UserModel = None,
):
    cookies = {}
    headers = {
        "Content-Type": "application/json",
        **(
            {
                "HTTP-Referer": "https://openwebui.com/",
                "X-Title": "Open WebUI",
            }
            if "openrouter.ai" in url
            else {}
        ),
    }

    token = None
    auth_type = config.get("auth_type")

    if auth_type == "bearer" or auth_type is None:
        # Default to bearer if not specified
        token = f"{key}"
    elif auth_type == "none":
        token = None
    elif auth_type == "session":
        cookies = request.cookies
        token = request.state.token.credentials
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if config.get("headers") and isinstance(config.get("headers"), dict):
        headers = {**headers, **config.get("headers")}

    return headers, cookies


##########################################
#
# API routes
#
##########################################

router = APIRouter()


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    return {
        "OPENAI_API_BASE_URLS": request.app.state.config.OPENAI_API_BASE_URLS,
        "OPENAI_API_KEYS": request.app.state.config.OPENAI_API_KEYS,
        "OPENAI_API_CONFIGS": request.app.state.config.OPENAI_API_CONFIGS,
    }


class OpenAIConfigForm(BaseModel):
    OPENAI_API_BASE_URLS: list[str]
    OPENAI_API_KEYS: list[str]
    OPENAI_API_CONFIGS: dict


@router.post("/config/update")
async def update_config(
    request: Request,
    form_data: OpenAIConfigForm,
    user=Depends(get_admin_user),
):
    request.app.state.config.OPENAI_API_BASE_URLS = form_data.OPENAI_API_BASE_URLS
    request.app.state.config.OPENAI_API_KEYS = form_data.OPENAI_API_KEYS

    # Check if API KEYS length is same than API URLS length
    if len(request.app.state.config.OPENAI_API_KEYS) != len(
        request.app.state.config.OPENAI_API_BASE_URLS
    ):
        if len(request.app.state.config.OPENAI_API_KEYS) > len(
            request.app.state.config.OPENAI_API_BASE_URLS
        ):
            request.app.state.config.OPENAI_API_KEYS = (
                request.app.state.config.OPENAI_API_KEYS[
                    : len(request.app.state.config.OPENAI_API_BASE_URLS)
                ]
            )
        else:
            request.app.state.config.OPENAI_API_KEYS += [""] * (
                len(request.app.state.config.OPENAI_API_BASE_URLS)
                - len(request.app.state.config.OPENAI_API_KEYS)
            )

    request.app.state.config.OPENAI_API_CONFIGS = form_data.OPENAI_API_CONFIGS

    # Remove the API configs that are not in the API URLS
    keys = list(map(str, range(len(request.app.state.config.OPENAI_API_BASE_URLS))))
    request.app.state.config.OPENAI_API_CONFIGS = {
        key: value
        for key, value in request.app.state.config.OPENAI_API_CONFIGS.items()
        if key in keys
    }
    request.app.state.config.persist()
    await get_all_models.cache.clear()

    return {
        "OPENAI_API_BASE_URLS": request.app.state.config.OPENAI_API_BASE_URLS,
        "OPENAI_API_KEYS": request.app.state.config.OPENAI_API_KEYS,
        "OPENAI_API_CONFIGS": request.app.state.config.OPENAI_API_CONFIGS,
    }


@router.post("/audio/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    idx = None
    try:
        idx = request.app.state.config.OPENAI_API_BASE_URLS.index(
            "https://api.openai.com/v1"
        )

        body = await request.body()
        name = hashlib.sha256(body).hexdigest()

        SPEECH_CACHE_DIR = CACHE_DIR / "audio" / "speech"
        SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = SPEECH_CACHE_DIR.joinpath(f"{name}.mp3")
        file_body_path = SPEECH_CACHE_DIR.joinpath(f"{name}.json")

        # Check if the file already exists in the cache
        if file_path.is_file():
            return FileResponse(file_path)

        url = request.app.state.config.OPENAI_API_BASE_URLS[idx]
        key = request.app.state.config.OPENAI_API_KEYS[idx]
        api_config = request.app.state.config.OPENAI_API_CONFIGS.get(
            str(idx),
            request.app.state.config.OPENAI_API_CONFIGS.get(url, {}),  # Legacy support
        )

        headers, cookies = await get_headers_and_cookies(
            request, url, key, api_config, user=user
        )

        r = None
        try:
            r = requests.post(
                url=f"{url}/audio/speech",
                data=body,
                headers=headers,
                cookies=cookies,
                stream=True,
            )

            r.raise_for_status()

            # Save the streaming content to a file
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            with open(file_body_path, "w") as f:
                json.dump(json.loads(body.decode("utf-8")), f)

            # Return the saved file
            return FileResponse(file_path)

        except Exception as e:
            log.exception(e)

            detail = None
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        detail = f"External: {res['error']}"
                except Exception:
                    detail = f"External: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500,
                detail=detail if detail else "Open WebUI: Server Connection Error",
            )

    except ValueError:
        raise HTTPException(status_code=401, detail=ERROR_MESSAGES.OPENAI_NOT_FOUND)


async def get_all_models_responses(request: Request) -> list:
    api_base_urls = request.app.state.config.OPENAI_API_BASE_URLS
    api_keys = list(request.app.state.config.OPENAI_API_KEYS)
    api_configs = request.app.state.config.OPENAI_API_CONFIGS

    # Check if API KEYS length is same than API URLS length
    num_urls = len(api_base_urls)
    num_keys = len(api_keys)

    if num_keys != num_urls:
        # if there are more keys than urls, remove the extra keys
        if num_keys > num_urls:
            api_keys = api_keys[:num_urls]
            request.app.state.config.OPENAI_API_KEYS = api_keys
        # if there are more urls than keys, add empty keys
        else:
            api_keys += [""] * (num_urls - num_keys)
            request.app.state.config.OPENAI_API_KEYS = api_keys

    request_tasks = []
    for idx, url in enumerate(api_base_urls):
        model_url = f"{url}/models"
        if (str(idx) not in api_configs) and (url not in api_configs):  # Legacy support
            request_tasks.append(send_get_request(model_url, api_keys[idx]))
        else:
            api_config = api_configs.get(
                str(idx),
                api_configs.get(url, {}),  # Legacy support
            )

            enable = api_config.get("enable", True)
            model_ids = api_config.get("model_ids", [])

            if enable:
                if len(model_ids) == 0:
                    request_tasks.append(send_get_request(model_url, api_keys[idx]))
                else:
                    model_list = {
                        "object": "list",
                        "data": [
                            {
                                "id": model_id,
                                "name": model_id,
                                "owned_by": "openai",
                                "openai": {"id": model_id},
                                "urlIdx": idx,
                            }
                            for model_id in model_ids
                        ],
                    }

                    request_tasks.append(
                        asyncio.ensure_future(asyncio.sleep(0, model_list))
                    )
            else:
                request_tasks.append(asyncio.ensure_future(asyncio.sleep(0, None)))

    responses = await asyncio.gather(*request_tasks)

    for idx, response in enumerate(responses):
        if response:
            url = api_base_urls[idx]
            api_config = api_configs.get(
                str(idx),
                api_configs.get(url, {}),  # Legacy support
            )

            prefix_id = api_config.get("prefix_id", None)

            model_list = (
                response if isinstance(response, list) else response.get("data", [])
            )
            if not isinstance(model_list, list):
                # Catch non-list responses
                model_list = []

            for model in model_list:
                # Remove name key if its value is None #16689
                if "name" in model and model["name"] is None:
                    del model["name"]

                if prefix_id:
                    model["id"] = (
                        f"{prefix_id}.{model.get('id', model.get('name', ''))}"
                    )

    log.debug(f"get_all_models:responses() {responses}")
    return responses


@cached(
    ttl=60,
    key=lambda _, user: f"openai_all_models_{user.id}" if user else "openai_all_models",
)
async def get_all_models(request: Request, user: UserModel) -> dict[str, list]:
    log.info("get_all_models()")
    responses = await get_all_models_responses(request)

    def extract_data(response):
        if response and "data" in response:
            return response["data"]
        if isinstance(response, list):
            return response
        return None

    def get_merged_models(model_lists):
        log.debug(f"merge_models_lists {model_lists}")
        models = {}

        for idx, model_list in enumerate(model_lists):
            if model_list is not None and "error" not in model_list:
                for model in model_list:
                    model_id = model.get("id") or model.get("name")
                    if model_id and model_id not in models:
                        models[model_id] = {
                            **model,
                            "name": model.get("name", model_id),
                            "owned_by": "openai",
                            "openai": model,
                            "urlIdx": idx,
                        }

        return models

    models = get_merged_models(map(extract_data, responses))
    log.debug(f"models: {models}")

    request.app.state.OPENAI_MODELS = models
    return {"data": list(models.values())}


@router.get("/models")
@router.get("/models/{url_idx}")
async def get_models(
    request: Request, url_idx: Optional[int] = None, user=Depends(get_verified_user)
):
    models = {
        "data": [],
    }

    if url_idx is None:
        models = await get_all_models(request, user=user)
    else:
        url = request.app.state.config.OPENAI_API_BASE_URLS[url_idx]
        key = request.app.state.config.OPENAI_API_KEYS[url_idx]

        api_config = request.app.state.config.OPENAI_API_CONFIGS.get(
            str(url_idx),
            request.app.state.config.OPENAI_API_CONFIGS.get(url, {}),  # Legacy support
        )

        r = None
        async with aiohttp.ClientSession(
            trust_env=True,
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST),
        ) as session:
            try:
                headers, cookies = await get_headers_and_cookies(
                    request, url, key, api_config, user=user
                )

                async with session.get(
                    f"{url}/models",
                    headers=headers,
                    cookies=cookies,
                    ssl=AIOHTTP_CLIENT_SESSION_SSL,
                ) as r:
                    if r.status != 200:
                        error_detail = f"HTTP Error: {r.status}"
                        try:
                            res = await r.json()
                            if "error" in res:
                                error_detail = f"External Error: {res['error']}"
                        except Exception:
                            pass
                        raise Exception(error_detail)

                    models = await r.json()
            except aiohttp.ClientError as e:
                # ClientError covers all aiohttp requests issues
                log.exception(f"Client error: {str(e)}")
                raise HTTPException(
                    status_code=500, detail="Open WebUI: Server Connection Error"
                )
            except Exception as e:
                log.exception(f"Unexpected error: {e}")
                error_detail = f"Unexpected error: {str(e)}"
                raise HTTPException(status_code=500, detail=error_detail)

    models["data"] = models.get("data", [])

    return models


class ConnectionVerificationForm(BaseModel):
    url: str
    key: str

    config: Optional[dict] = None


@router.post("/verify")
async def verify_connection(
    request: Request,
    form_data: ConnectionVerificationForm,
    user=Depends(get_admin_user),
):
    url = form_data.url
    key = form_data.key

    api_config = form_data.config or {}

    headers, cookies = await get_headers_and_cookies(
        request, url, key, api_config, user=user
    )

    return await _proxy_request(
        method="GET",
        url=f"{url}/models",
        headers=headers,
        cookies=cookies,
        timeout=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
    )


def is_openai_reasoning_model(model: str) -> bool:
    return model.lower().startswith(("o1", "o3", "o4", "gpt-5"))


def convert_to_responses_payload(payload: dict) -> dict:
    """
    Convert Chat Completions payload to Responses API format.

    Chat Completions: { messages: [{role, content}], ... }
    Responses API: { input: [{type: "message", role, content: [...]}], instructions: "system" }
    """
    messages = payload.pop("messages", [])

    system_content = ""
    input_items = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Check for stored output items (from previous Responses API turn)
        stored_output = msg.get("output")
        if stored_output and isinstance(stored_output, list):
            input_items.extend(stored_output)
            continue

        if role == "system":
            if isinstance(content, str):
                system_content = content
            elif isinstance(content, list):
                system_content = "\n".join(
                    p.get("text", "") for p in content if p.get("type") == "text"
                )
            continue

        # Convert content format
        text_type = "output_text" if role == "assistant" else "input_text"

        if isinstance(content, str):
            content_parts = [{"type": text_type, "text": content}]
        elif isinstance(content, list):
            content_parts = []
            for part in content:
                if part.get("type") == "text":
                    content_parts.append(
                        {"type": text_type, "text": part.get("text", "")}
                    )
                elif part.get("type") == "image_url":
                    url_data = part.get("image_url", {})
                    url = (
                        url_data.get("url", "")
                        if isinstance(url_data, dict)
                        else url_data
                    )
                    content_parts.append({"type": "input_image", "image_url": url})
        else:
            content_parts = [{"type": text_type, "text": str(content)}]

        input_items.append({"type": "message", "role": role, "content": content_parts})

    responses_payload = {**payload, "input": input_items}

    if system_content:
        responses_payload["instructions"] = system_content

    # Remove Chat Completions-only parameters not supported by the Responses API
    for unsupported_key in ("stream_options",):
        responses_payload.pop(unsupported_key, None)

    # Convert Chat Completions tools format to Responses API format
    # Chat Completions: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    # Responses API:    {"type": "function", "name": ..., "description": ..., "parameters": ...}
    if "tools" in responses_payload and isinstance(responses_payload["tools"], list):
        converted_tools = []
        for tool in responses_payload["tools"]:
            if isinstance(tool, dict) and "function" in tool:
                func = tool["function"]
                converted_tool = {"type": tool.get("type", "function")}
                if isinstance(func, dict):
                    converted_tool["name"] = func.get("name", "")
                    if "description" in func:
                        converted_tool["description"] = func["description"]
                    if "parameters" in func:
                        converted_tool["parameters"] = func["parameters"]
                    if "strict" in func:
                        converted_tool["strict"] = func["strict"]
                converted_tools.append(converted_tool)
            else:
                # Already in correct format or unknown format, pass through
                converted_tools.append(tool)
        responses_payload["tools"] = converted_tools

    return responses_payload


def convert_responses_result(response: dict) -> dict:
    """
    Convert non-streaming Responses API result.
    Just add done flag - pass through raw response, frontend handles output.
    """
    response["done"] = True
    return response


@router.post("/chat/completions")
async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    idx = 0

    payload = {**form_data}
    metadata = payload.pop("metadata", {})

    model_id = form_data.get("model")

    # metadata["model"] is from app.state.MODELS (set in main.py chat_completion)
    model_info = metadata.get("model", {}).get("info", {})
    base_model_id = model_info.get("base_model_id")
    if base_model_id:
        base_model_id = (
            request.base_model_id
            if hasattr(request, "base_model_id")
            else base_model_id
        )
        payload["model"] = base_model_id
        model_id = base_model_id

    # User system prompt (injected by middleware) wins; model's is fallback
    messages = payload.get("messages", [])
    has_system = messages and messages[0].get("role") == "system"
    model_system = model_info.get("params", {}).get("system")
    if model_system and not has_system:
        messages.insert(0, {"role": "system", "content": model_system})

    # Check if model is already in app state cache to avoid expensive get_all_models() call
    models = request.app.state.OPENAI_MODELS
    if not models or model_id not in models:
        await get_all_models(request, user=user)
        models = request.app.state.OPENAI_MODELS
    model = models.get(model_id)

    if model:
        idx = model["urlIdx"]
    else:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    # Get the API config for the model
    api_config = request.app.state.config.OPENAI_API_CONFIGS.get(
        str(idx),
        request.app.state.config.OPENAI_API_CONFIGS.get(
            request.app.state.config.OPENAI_API_BASE_URLS[idx], {}
        ),  # Legacy support
    )

    prefix_id = api_config.get("prefix_id", None)
    if prefix_id:
        payload["model"] = payload["model"].replace(f"{prefix_id}.", "")

    url = request.app.state.config.OPENAI_API_BASE_URLS[idx]
    key = request.app.state.config.OPENAI_API_KEYS[idx]

    payload = fix_openai_system_role(payload["model"], payload)
    headers, cookies = await get_headers_and_cookies(
        request, url, key, api_config, metadata, user=user
    )

    is_responses = api_config.get("api_type") == "responses"

    if is_responses:
        payload = convert_to_responses_payload(payload)
        request_url = f"{url}/responses"
    else:
        request_url = f"{url}/chat/completions"

    payload = json.dumps(payload)

    response = await _proxy_request(
        method="POST",
        url=request_url,
        data=payload,
        headers=headers,
        cookies=cookies,
        stream_handler=stream_chunks_handler,
    )

    if is_responses and isinstance(response, dict):
        response = convert_responses_result(response)

    return response


class ResponsesForm(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    input: Optional[list | str] = None
    instructions: Optional[str] = None
    stream: Optional[bool] = None
    tools: Optional[list] = None
    tool_choice: Optional[str | dict] = None
    text: Optional[dict] = None
    truncation: Optional[str] = None
    metadata: Optional[dict] = None
    store: Optional[bool] = None
    reasoning: Optional[dict] = None
    previous_response_id: Optional[str] = None


@router.post("/responses")
async def responses(
    request: Request,
    form_data: ResponsesForm,
    user=Depends(get_verified_user),
):
    """
    Forward requests to the OpenAI Responses API endpoint.
    Routes to the correct upstream backend based on the model field.
    """
    payload = form_data.model_dump(exclude_none=True)
    body = json.dumps(payload)

    idx = 0
    model_id = form_data.model
    if model_id:
        models = request.app.state.OPENAI_MODELS
        if not models or model_id not in models:
            await get_all_models(request, user=user)
            models = request.app.state.OPENAI_MODELS
        if model_id in models:
            idx = models[model_id]["urlIdx"]

    url = request.app.state.config.OPENAI_API_BASE_URLS[idx]
    key = request.app.state.config.OPENAI_API_KEYS[idx]
    api_config = request.app.state.config.OPENAI_API_CONFIGS.get(
        str(idx),
        request.app.state.config.OPENAI_API_CONFIGS.get(url, {}),  # Legacy support
    )

    headers, cookies = await get_headers_and_cookies(
        request, url, key, api_config, user=user
    )

    return await _proxy_request(
        method="POST",
        url=f"{url}/responses",
        data=body,
        headers=headers,
        cookies=cookies,
    )
