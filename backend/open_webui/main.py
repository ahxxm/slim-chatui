import asyncio
import json
import logging
import mimetypes
import os
import sys
import time
import re


from contextlib import asynccontextmanager
from urllib.parse import urlencode, parse_qs, urlparse
from pydantic import BaseModel
from sqlalchemy import text

import anyio.to_thread
import requests
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    status,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response, StreamingResponse

from open_webui.utils.logger import configure_logging
from open_webui.socket.main import (
    MODELS,
    app as socket_app,
    periodic_session_pool_cleanup,
    get_event_emitter,
)
from open_webui.routers import (
    openai,
    tasks,
    auths,
    chats,
    folders,
    configs,
    files,
    models,
    users,
    utils,
)

from open_webui.internal.db import get_db

from open_webui.models.models import Models
from open_webui.models.users import Users
from open_webui.models.chats import Chats

from open_webui.config import (
    # OpenAI
    OPENAI_API_BASE_URLS,
    OPENAI_API_KEYS,
    OPENAI_API_CONFIGS,
    # Direct Connections
    ENABLE_DIRECT_CONNECTIONS,
    # Thread pool size for FastAPI/AnyIO
    THREAD_POOL_SIZE,
    # File
    FILE_IMAGE_COMPRESSION_WIDTH,
    FILE_IMAGE_COMPRESSION_HEIGHT,
    # WebUI
    WEBUI_AUTH,
    WEBUI_NAME,
    WEBUI_BANNERS,
    ADMIN_EMAIL,
    SHOW_ADMIN_DETAILS,
    JWT_EXPIRES_IN,
    ENABLE_SIGNUP,
    DEFAULT_USER_ROLE,
    PENDING_USER_OVERLAY_CONTENT,
    PENDING_USER_OVERLAY_TITLE,
    DEFAULT_PROMPT_SUGGESTIONS,
    DEFAULT_MODELS,
    DEFAULT_PINNED_MODELS,
    MODEL_ORDER_LIST,
    DEFAULT_MODEL_METADATA,
    DEFAULT_MODEL_PARAMS,
    # Misc
    CACHE_DIR,
    STATIC_DIR,
    FRONTEND_BUILD_DIR,
    CORS_ALLOW_ORIGIN,
    DEFAULT_LOCALE,
    WEBUI_URL,
    # Tasks
    TASK_MODEL,
    ENABLE_TITLE_GENERATION,
    ENABLE_FOLLOW_UP_GENERATION,
    TITLE_GENERATION_PROMPT_TEMPLATE,
    FOLLOW_UP_GENERATION_PROMPT_TEMPLATE,
    AppConfig,
)
from open_webui.env import (
    ENV,
    ENABLE_CUSTOM_MODEL_FALLBACK,
    GLOBAL_LOG_LEVEL,
    SAFE_MODE,
    VERSION,
    DEPLOYMENT_ID,
    INSTANCE_ID,
    WEBUI_BUILD_HASH,
    ENABLE_SIGNUP_PASSWORD_CONFIRMATION,
    ENABLE_WEBSOCKET_SUPPORT,
    EXTERNAL_PWA_MANIFEST_URL,
    # Admin Account Runtime Creation
    WEBUI_ADMIN_EMAIL,
    WEBUI_ADMIN_PASSWORD,
    WEBUI_ADMIN_NAME,
    ENABLE_EASTER_EGGS,
    LOG_FORMAT,
)


from open_webui.utils.models import (
    get_all_models,
    get_all_base_models,
)
from open_webui.utils.chat import (
    generate_chat_completion as chat_completion_handler,
)
from open_webui.utils.middleware import (
    build_chat_response_context,
    process_chat_payload,
    process_chat_response,
)
from open_webui.utils.auth import (
    get_http_authorization_cred,
    decode_token,
    get_admin_user,
    get_verified_user,
    create_admin_user,
)
from open_webui.utils.security_headers import SecurityHeadersMiddleware
from open_webui.tasks import (
    list_task_ids_by_item_id,
    create_task,
    stop_task,
    list_tasks,
)


from open_webui.constants import ERROR_MESSAGES

if SAFE_MODE:
    print("SAFE MODE ENABLED")

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as ex:
            if ex.status_code == 404:
                if path.endswith(".js"):
                    # Return 404 for javascript files
                    raise ex
                else:
                    return await super().get_response("index.html", scope)
            else:
                raise ex


if LOG_FORMAT != "json":
    print(rf"""
 ██████╗ ██████╗ ███████╗███╗   ██╗    ██╗    ██╗███████╗██████╗ ██╗   ██╗██╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║    ██║    ██║██╔════╝██╔══██╗██║   ██║██║
██║   ██║██████╔╝█████╗  ██╔██╗ ██║    ██║ █╗ ██║█████╗  ██████╔╝██║   ██║██║
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║    ██║███╗██║██╔══╝  ██╔══██╗██║   ██║██║
╚██████╔╝██║     ███████╗██║ ╚████║    ╚███╔███╔╝███████╗██████╔╝╚██████╔╝██║
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝     ╚══╝╚══╝ ╚══════╝╚═════╝  ╚═════╝ ╚═╝


v{VERSION} - building the best AI user interface.
{f"Commit: {WEBUI_BUILD_HASH}" if WEBUI_BUILD_HASH != "dev-build" else ""}
https://github.com/open-webui/open-webui
""")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Store reference to main event loop for sync->async calls (e.g., embedding generation)
    # This allows sync functions to schedule work on the main loop without blocking health checks
    app.state.main_loop = asyncio.get_running_loop()
    app.state.instance_id = INSTANCE_ID
    configure_logging()

    # Create admin account from env vars if specified and no users exist
    if WEBUI_ADMIN_EMAIL and WEBUI_ADMIN_PASSWORD:
        if create_admin_user(WEBUI_ADMIN_EMAIL, WEBUI_ADMIN_PASSWORD, WEBUI_ADMIN_NAME):
            # Disable signup since we now have an admin
            app.state.config.ENABLE_SIGNUP = False

    if THREAD_POOL_SIZE and THREAD_POOL_SIZE > 0:
        limiter = anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens = THREAD_POOL_SIZE

    asyncio.create_task(periodic_session_pool_cleanup())

    yield


app = FastAPI(
    title="Open WebUI",
    docs_url=None,
    openapi_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.state.instance_id = None
app.state.config = AppConfig()

app.state.WEBUI_NAME = WEBUI_NAME


########################################
#
# OPENAI
#
########################################

app.state.config.OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS
app.state.config.OPENAI_API_KEYS = OPENAI_API_KEYS
app.state.config.OPENAI_API_CONFIGS = OPENAI_API_CONFIGS

app.state.OPENAI_MODELS = {}

########################################
#
# DIRECT CONNECTIONS
#
########################################

app.state.config.ENABLE_DIRECT_CONNECTIONS = ENABLE_DIRECT_CONNECTIONS

########################################
#
# MODELS
#
########################################

app.state.BASE_MODELS = []

########################################
#
# WEBUI
#
########################################

app.state.config.WEBUI_URL = WEBUI_URL
app.state.config.ENABLE_SIGNUP = ENABLE_SIGNUP

app.state.config.JWT_EXPIRES_IN = JWT_EXPIRES_IN

app.state.config.SHOW_ADMIN_DETAILS = SHOW_ADMIN_DETAILS
app.state.config.ADMIN_EMAIL = ADMIN_EMAIL


app.state.config.DEFAULT_MODELS = DEFAULT_MODELS
app.state.config.DEFAULT_PINNED_MODELS = DEFAULT_PINNED_MODELS
app.state.config.MODEL_ORDER_LIST = MODEL_ORDER_LIST
app.state.config.DEFAULT_MODEL_METADATA = DEFAULT_MODEL_METADATA
app.state.config.DEFAULT_MODEL_PARAMS = DEFAULT_MODEL_PARAMS


app.state.config.DEFAULT_PROMPT_SUGGESTIONS = DEFAULT_PROMPT_SUGGESTIONS
app.state.config.DEFAULT_USER_ROLE = DEFAULT_USER_ROLE

app.state.config.PENDING_USER_OVERLAY_CONTENT = PENDING_USER_OVERLAY_CONTENT
app.state.config.PENDING_USER_OVERLAY_TITLE = PENDING_USER_OVERLAY_TITLE

app.state.config.BANNERS = WEBUI_BANNERS

app.state.EXTERNAL_PWA_MANIFEST_URL = EXTERNAL_PWA_MANIFEST_URL


########################################
#
# FILES
#
########################################

app.state.config.FILE_IMAGE_COMPRESSION_WIDTH = FILE_IMAGE_COMPRESSION_WIDTH
app.state.config.FILE_IMAGE_COMPRESSION_HEIGHT = FILE_IMAGE_COMPRESSION_HEIGHT

########################################
#
# TASKS
#
########################################


app.state.config.TASK_MODEL = TASK_MODEL


app.state.config.ENABLE_TITLE_GENERATION = ENABLE_TITLE_GENERATION
app.state.config.ENABLE_FOLLOW_UP_GENERATION = ENABLE_FOLLOW_UP_GENERATION


app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = TITLE_GENERATION_PROMPT_TEMPLATE
app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE = (
    FOLLOW_UP_GENERATION_PROMPT_TEMPLATE
)


########################################
#
# WEBUI
#
########################################

app.state.MODELS = MODELS


class RedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check if the request is a GET request
        if request.method == "GET":
            path = request.url.path
            query_params = dict(parse_qs(urlparse(str(request.url)).query))

            redirect_params = {}

            # Check for the specific watch path and the presence of 'v' parameter
            if path.endswith("/watch") and "v" in query_params:
                # Extract the first 'v' parameter
                youtube_video_id = query_params["v"][0]
                redirect_params["youtube"] = youtube_video_id

            if "shared" in query_params and len(query_params["shared"]) > 0:
                # PWA share_target support

                text = query_params["shared"][0]
                if text:
                    urls = re.match(r"https://\S+", text)
                    if urls:
                        yt_match = re.search(
                            r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", urls[0]
                        )
                        if yt_match:
                            redirect_params["youtube"] = yt_match.group(1)
                        else:
                            redirect_params["load-url"] = urls[0]
                    else:
                        redirect_params["q"] = text

            if redirect_params:
                redirect_url = f"/?{urlencode(redirect_params)}"
                return RedirectResponse(url=redirect_url)

        # Proceed with the normal flow of other requests
        response = await call_next(request)
        return response


app.add_middleware(RedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def check_url(request: Request, call_next):
    start_time = int(time.time())
    request.state.token = get_http_authorization_cred(
        request.headers.get("Authorization")
    )
    # Fallback to cookie token for browser sessions
    if request.state.token is None and request.cookies.get("token"):
        from fastapi.security import HTTPAuthorizationCredentials

        request.state.token = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=request.cookies.get("token")
        )

    # Fallback to x-api-key header for Anthropic Messages API routes
    if request.state.token is None and request.headers.get("x-api-key"):
        request_path = request.url.path
        if request_path in ("/api/message", "/api/v1/messages"):
            from fastapi.security import HTTPAuthorizationCredentials

            request.state.token = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=request.headers.get("x-api-key")
            )

    response = await call_next(request)
    process_time = int(time.time()) - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def inspect_websocket(request: Request, call_next):
    if (
        "/ws/socket.io" in request.url.path
        and request.query_params.get("transport") == "websocket"
    ):
        upgrade = (request.headers.get("Upgrade") or "").lower()
        connection = (request.headers.get("Connection") or "").lower().split(",")
        # Check that there's the correct headers for an upgrade, else reject the connection
        # This is to work around this upstream issue: https://github.com/miguelgrinberg/python-engineio/issues/367
        if upgrade != "websocket" or "upgrade" not in connection:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid WebSocket upgrade request"},
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/ws", socket_app)


app.include_router(openai.router, prefix="/openai", tags=["openai"])


app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(configs.router, prefix="/api/v1/configs", tags=["configs"])

app.include_router(auths.router, prefix="/api/v1/auths", tags=["auths"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])


app.include_router(chats.router, prefix="/api/v1/chats", tags=["chats"])

app.include_router(models.router, prefix="/api/v1/models", tags=["models"])
app.include_router(folders.router, prefix="/api/v1/folders", tags=["folders"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(utils.router, prefix="/api/v1/utils", tags=["utils"])


##################################
#
# Chat Endpoints
#
##################################


@app.get("/api/models")
@app.get("/api/v1/models")  # Experimental: Compatibility with OpenAI API
async def get_models(request: Request, user=Depends(get_verified_user)):
    all_models = await get_all_models(request, user=user)

    models = []
    for model in all_models:
        # Remove profile image URL to reduce payload size
        if model.get("info", {}).get("meta", {}).get("profile_image_url"):
            model["info"]["meta"].pop("profile_image_url", None)

        try:
            model_tags = [
                tag.get("name")
                for tag in model.get("info", {}).get("meta", {}).get("tags", [])
            ]
            tags = [tag.get("name") for tag in model.get("tags", [])]

            tags = list(set(model_tags + tags))
            model["tags"] = [{"name": tag} for tag in tags]
        except Exception as e:
            log.debug(f"Error processing model tags: {e}")
            model["tags"] = []
            pass

        models.append(model)

    model_order_list = request.app.state.config.MODEL_ORDER_LIST
    if model_order_list:
        model_order_dict = {model_id: i for i, model_id in enumerate(model_order_list)}
        # Sort models by order list priority, with fallback for those not in the list
        models.sort(
            key=lambda model: (
                model_order_dict.get(model.get("id", ""), float("inf")),
                (model.get("name", "") or ""),
            )
        )

    log.debug(
        f"/api/models returned filtered models accessible to the user: {json.dumps([model.get('id') for model in models])}"
    )
    return {"data": models}


@app.get("/api/models/base")
async def get_base_models(request: Request, user=Depends(get_admin_user)):
    models = await get_all_base_models(request, user=user)
    return {"data": models}


@app.post("/api/chat/completions")
@app.post("/api/v1/chat/completions")  # Experimental: Compatibility with OpenAI API
async def chat_completion(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    if not request.app.state.MODELS:
        await get_all_models(request, user=user)

    model_id = form_data.get("model", None)
    model_item = form_data.pop("model_item", {})
    tasks = form_data.pop("background_tasks", None)

    metadata = {}
    try:
        model_info = None
        if not model_item.get("direct", False):
            if model_id not in request.app.state.MODELS:
                raise Exception("Model not found")

            model = request.app.state.MODELS[model_id]
            model_info = Models.get_model_by_id(model_id)
        else:
            model = model_item

            request.state.direct = True
            request.state.model = model

        # Model params: global defaults as base, per-model overrides win
        default_model_params = (
            getattr(request.app.state.config, "DEFAULT_MODEL_PARAMS", None) or {}
        )
        model_info_params = {
            **default_model_params,
            **(
                model_info.params.model_dump()
                if model_info and model_info.params
                else {}
            ),
        }

        # Check base model existence for custom models
        if model_info_params.get("base_model_id"):
            base_model_id = model_info_params.get("base_model_id")
            if base_model_id not in request.app.state.MODELS:
                if ENABLE_CUSTOM_MODEL_FALLBACK:
                    default_models = (
                        request.app.state.config.DEFAULT_MODELS or ""
                    ).split(",")

                    fallback_model_id = (
                        default_models[0].strip() if default_models[0] else None
                    )

                    if (
                        fallback_model_id
                        and fallback_model_id in request.app.state.MODELS
                    ):
                        # Update model and form_data so routing uses the fallback model's type
                        model = request.app.state.MODELS[fallback_model_id]
                        form_data["model"] = fallback_model_id
                    else:
                        raise Exception("Model not found")
                else:
                    raise Exception("Model not found")

        # Chat Params
        stream_delta_chunk_size = form_data.get("params", {}).get(
            "stream_delta_chunk_size"
        )
        # Model Params
        if model_info_params.get("stream_response") is not None:
            form_data["stream"] = model_info_params.get("stream_response")

        if model_info_params.get("stream_delta_chunk_size"):
            stream_delta_chunk_size = model_info_params.get("stream_delta_chunk_size")

        metadata = {
            "user_id": user.id,
            "chat_id": form_data.pop("chat_id", None),
            "message_id": form_data.pop("id", None),
            "parent_message": form_data.pop("parent_message", None),
            "parent_message_id": form_data.pop("parent_id", None),
            "session_id": form_data.pop("session_id", None),
            "files": form_data.get("files", None),
            "features": form_data.get("features", {}),
            "variables": form_data.get("variables", {}),
            "model": model,
            "direct": model_item.get("direct", False),
            "params": {
                "stream_delta_chunk_size": stream_delta_chunk_size,
            },
        }

        if metadata.get("chat_id") and user:
            if not metadata["chat_id"].startswith(
                "local:"
            ):  # temporary chats are not stored

                # Verify chat ownership — lightweight EXISTS check avoids
                # deserializing the full chat JSON blob just to confirm the row exists
                if (
                    not Chats.is_chat_owner(metadata["chat_id"], user.id)
                    and user.role != "admin"
                ):  # admins can access any chat
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=ERROR_MESSAGES.DEFAULT(),
                    )

                # Insert chat files from parent message if any
                parent_message = metadata.get("parent_message") or {}
                parent_message_files = parent_message.get("files", [])
                if parent_message_files:
                    try:
                        Chats.insert_chat_files(
                            metadata["chat_id"],
                            parent_message.get("id"),
                            [
                                file_item.get("id")
                                for file_item in parent_message_files
                                if file_item.get("type") == "file"
                            ],
                            user.id,
                        )
                    except Exception as e:
                        log.debug(f"Error inserting chat files: {e}")
                        pass

        request.state.metadata = metadata
        form_data["metadata"] = metadata

    except Exception as e:
        log.debug(f"Error processing chat metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    async def process_chat(request, form_data, user, metadata, model):
        try:
            form_data, metadata = await process_chat_payload(
                request, form_data, user, metadata, model
            )

            response = await chat_completion_handler(request, form_data, user)
            if metadata.get("chat_id") and metadata.get("message_id"):
                try:
                    if not metadata["chat_id"].startswith("local:"):
                        Chats.upsert_message_to_chat_by_id_and_message_id(
                            metadata["chat_id"],
                            metadata["message_id"],
                            {
                                "parentId": metadata.get("parent_message_id", None),
                                "model": model_id,
                            },
                        )
                except:
                    pass

            ctx = build_chat_response_context(
                request, form_data, user, model, metadata, tasks
            )

            return await process_chat_response(response, ctx)
        except asyncio.CancelledError:
            log.info("Chat processing was cancelled")
            try:
                event_emitter = get_event_emitter(metadata)
                await asyncio.shield(
                    event_emitter(
                        {"type": "chat:tasks:cancel"},
                    )
                )
            except Exception as e:
                pass
            finally:
                raise  # re-raise to ensure proper task cancellation handling
        except Exception as e:
            log.debug(f"Error processing chat payload: {e}")
            if metadata.get("chat_id") and metadata.get("message_id"):
                # Update the chat message with the error
                try:
                    if not metadata["chat_id"].startswith("local:"):
                        Chats.upsert_message_to_chat_by_id_and_message_id(
                            metadata["chat_id"],
                            metadata["message_id"],
                            {
                                "parentId": metadata.get("parent_message_id", None),
                                "error": {"content": str(e)},
                            },
                        )

                    event_emitter = get_event_emitter(metadata)
                    await event_emitter(
                        {
                            "type": "chat:message:error",
                            "data": {"error": {"content": str(e)}},
                        }
                    )
                    await event_emitter(
                        {"type": "chat:tasks:cancel"},
                    )

                except:
                    pass
        finally:
            # Emit chat:active=false when task completes
            try:
                if metadata.get("chat_id"):
                    event_emitter = get_event_emitter(metadata, update_db=False)
                    if event_emitter:
                        await event_emitter(
                            {"type": "chat:active", "data": {"active": False}}
                        )
            except Exception as e:
                log.debug(f"Error emitting chat:active: {e}")

    if (
        metadata.get("session_id")
        and metadata.get("chat_id")
        and metadata.get("message_id")
    ):
        # Asynchronous Chat Processing
        task_id, _ = await create_task(
            process_chat(request, form_data, user, metadata, model),
            id=metadata["chat_id"],
        )
        # Emit chat:active=true when task starts
        event_emitter = get_event_emitter(metadata, update_db=False)
        if event_emitter:
            await event_emitter({"type": "chat:active", "data": {"active": True}})
        return {"status": True, "task_id": task_id}
    else:
        return await process_chat(request, form_data, user, metadata, model)


# Alias for chat_completion (Legacy)
generate_chat_completions = chat_completion
generate_chat_completion = chat_completion


##################################
#
# Anthropic Messages API Compatible Endpoint
#
##################################


from open_webui.utils.anthropic import (
    convert_anthropic_to_openai_payload,
    convert_openai_to_anthropic_response,
    openai_stream_to_anthropic_stream,
)


@app.post("/api/message")
@app.post("/api/v1/messages")  # Anthropic Messages API compatible endpoint
async def generate_messages(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """
    Anthropic Messages API compatible endpoint.

    Accepts the Anthropic Messages API format, converts internally to OpenAI
    Chat Completions format, routes through the existing chat completion
    handler, then converts the response back to Anthropic Messages format.

    Supports both streaming and non-streaming requests.
    All models configured in Open WebUI are accessible via this endpoint.

    Authentication: Supports both standard Authorization header and
    Anthropic's x-api-key header (via middleware translation).
    """
    # Convert Anthropic payload to OpenAI format
    requested_model = form_data.get("model", "")

    openai_payload = convert_anthropic_to_openai_payload(form_data)

    # Route through the existing chat_completion handler
    response = await chat_completion(request, openai_payload, user)

    # Convert response back to Anthropic format
    if isinstance(response, StreamingResponse):
        # Streaming response: wrap the generator to convert SSE format
        return StreamingResponse(
            openai_stream_to_anthropic_stream(
                response.body_iterator, model=requested_model
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    elif isinstance(response, dict):
        return convert_openai_to_anthropic_response(response, model=requested_model)
    else:
        # Passthrough for error responses (JSONResponse, PlainTextResponse, etc.)
        return response


@app.post("/api/chat/completed")
async def chat_completed(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    try:
        model_item = form_data.pop("model_item", {})

        if model_item.get("direct", False):
            models = {model_item["id"]: model_item}
        else:
            if not request.app.state.MODELS:
                await get_all_models(request, user=user)
            models = request.app.state.MODELS

        if form_data.get("model") not in models:
            raise Exception("Model not found")

        return form_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post("/api/tasks/stop/{task_id}")
async def stop_task_endpoint(
    request: Request, task_id: str, user=Depends(get_verified_user)
):
    try:
        result = await stop_task(task_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.get("/api/tasks")
async def list_tasks_endpoint(request: Request, user=Depends(get_verified_user)):
    return {"tasks": list_tasks()}


@app.get("/api/tasks/chat/{chat_id}")
async def list_tasks_by_chat_id_endpoint(
    request: Request, chat_id: str, user=Depends(get_verified_user)
):
    chat = Chats.get_chat_by_id(chat_id)
    if chat is None or chat.user_id != user.id:
        return {"task_ids": []}

    task_ids = list_task_ids_by_item_id(chat_id)

    log.debug(f"Task IDs for chat {chat_id}: {task_ids}")
    return {"task_ids": task_ids}


##################################
#
# Config Endpoints
#
##################################


@app.get("/api/config")
async def get_app_config(request: Request):
    user = None
    token = None

    auth_header = request.headers.get("Authorization")
    if auth_header:
        cred = get_http_authorization_cred(auth_header)
        if cred:
            token = cred.credentials

    if not token and "token" in request.cookies:
        token = request.cookies.get("token")

    if token:
        try:
            data = decode_token(token)
        except Exception as e:
            log.debug(e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        if data is not None and "id" in data:
            user = Users.get_user_by_id(data["id"])

    user_count = Users.get_num_users()
    onboarding = False

    if user is None:
        onboarding = user_count == 0

    return {
        **({"onboarding": True} if onboarding else {}),
        "status": True,
        "name": app.state.WEBUI_NAME,
        "version": VERSION,
        "default_locale": str(DEFAULT_LOCALE),
        "features": {
            "auth": WEBUI_AUTH,
            "enable_signup_password_confirmation": ENABLE_SIGNUP_PASSWORD_CONFIRMATION,
            "enable_signup": app.state.config.ENABLE_SIGNUP,
            "enable_websocket": ENABLE_WEBSOCKET_SUPPORT,
            "enable_easter_eggs": ENABLE_EASTER_EGGS,
            **(
                {
                    "enable_direct_connections": app.state.config.ENABLE_DIRECT_CONNECTIONS,
                }
                if user is not None
                else {}
            ),
        },
        **(
            {
                "default_models": app.state.config.DEFAULT_MODELS,
                "default_pinned_models": app.state.config.DEFAULT_PINNED_MODELS,
                "default_prompt_suggestions": app.state.config.DEFAULT_PROMPT_SUGGESTIONS,
                "user_count": user_count,
                "file": {
                    "image_compression": {
                        "width": app.state.config.FILE_IMAGE_COMPRESSION_WIDTH,
                        "height": app.state.config.FILE_IMAGE_COMPRESSION_HEIGHT,
                    },
                },
                "ui": {
                    "pending_user_overlay_title": app.state.config.PENDING_USER_OVERLAY_TITLE,
                    "pending_user_overlay_content": app.state.config.PENDING_USER_OVERLAY_CONTENT,
                },
            }
            if user is not None and (user.role in ["admin", "user"])
            else {
                **(
                    {
                        "ui": {
                            "pending_user_overlay_title": app.state.config.PENDING_USER_OVERLAY_TITLE,
                            "pending_user_overlay_content": app.state.config.PENDING_USER_OVERLAY_CONTENT,
                        }
                    }
                    if user and user.role == "pending"
                    else {}
                ),
            }
        ),
    }


@app.get("/api/version")
async def get_app_version():
    return {
        "version": VERSION,
        "deployment_id": DEPLOYMENT_ID,
    }


@app.get("/manifest.json")
async def get_manifest_json():
    if app.state.EXTERNAL_PWA_MANIFEST_URL:
        return requests.get(app.state.EXTERNAL_PWA_MANIFEST_URL).json()
    else:
        return {
            "name": app.state.WEBUI_NAME,
            "short_name": app.state.WEBUI_NAME,
            "description": f"{app.state.WEBUI_NAME} is an open, extensible, user-friendly interface for AI that adapts to your workflow.",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#343541",
            "icons": [
                {
                    "src": "/static/logo.png",
                    "type": "image/png",
                    "sizes": "500x500",
                    "purpose": "any",
                },
                {
                    "src": "/static/logo.png",
                    "type": "image/png",
                    "sizes": "500x500",
                    "purpose": "maskable",
                },
            ],
            "share_target": {
                "action": "/",
                "method": "GET",
                "params": {"text": "shared"},
            },
        }


@app.get("/health")
async def healthcheck():
    return {"status": True}


@app.get("/health/db")
async def healthcheck_with_db():
    with get_db() as db:
        db.execute(text("SELECT 1;")).all()
    return {"status": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/cache/{path:path}")
async def serve_cache_file(
    path: str,
    user=Depends(get_verified_user),
):
    file_path = os.path.abspath(os.path.join(CACHE_DIR, path))
    # prevent path traversal
    if not file_path.startswith(os.path.abspath(CACHE_DIR)):
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


if os.path.exists(FRONTEND_BUILD_DIR):
    mimetypes.add_type("text/javascript", ".js")
    app.mount(
        "/",
        SPAStaticFiles(directory=FRONTEND_BUILD_DIR, html=True),
        name="spa-static-files",
    )
else:
    log.warning(
        f"Frontend build directory not found at '{FRONTEND_BUILD_DIR}'. Serving API only."
    )
