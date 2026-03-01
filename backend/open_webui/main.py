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
    applications,
)
from fastapi.openapi.docs import get_swagger_ui_html

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from starlette_compress import CompressMiddleware

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse
from starlette.datastructures import Headers

from open_webui.utils import logger
from open_webui.utils.audit import AuditLevel, AuditLoggingMiddleware
from open_webui.utils.logger import start_logger
from open_webui.socket.main import (
    MODELS,
    app as socket_app,
    periodic_usage_pool_cleanup,
    periodic_session_pool_cleanup,
    get_event_emitter,
    get_models_in_use,
)
from open_webui.routers import (
    ollama,
    openai,
    pipelines,
    tasks,
    auths,
    chats,
    folders,
    configs,
    groups,
    files,
    functions,
    models,
    prompts,
    skills,
    users,
    utils,
)

from sqlalchemy.orm import Session
from open_webui.internal.db import ScopedSession, get_session

from open_webui.models.functions import Functions
from open_webui.models.models import Models
from open_webui.models.users import Users
from open_webui.models.chats import Chats

from open_webui.config import (
    # Ollama
    ENABLE_OLLAMA_API,
    OLLAMA_BASE_URLS,
    OLLAMA_API_CONFIGS,
    # OpenAI
    ENABLE_OPENAI_API,
    OPENAI_API_BASE_URLS,
    OPENAI_API_KEYS,
    OPENAI_API_CONFIGS,
    # Direct Connections
    ENABLE_DIRECT_CONNECTIONS,
    # Model list
    ENABLE_BASE_MODELS_CACHE,
    # Thread pool size for FastAPI/AnyIO
    THREAD_POOL_SIZE,
    # File
    FILE_IMAGE_COMPRESSION_WIDTH,
    FILE_IMAGE_COMPRESSION_HEIGHT,
    # WebUI
    WEBUI_AUTH,
    WEBUI_NAME,
    WEBUI_BANNERS,
    WEBHOOK_URL,
    ADMIN_EMAIL,
    SHOW_ADMIN_DETAILS,
    JWT_EXPIRES_IN,
    ENABLE_SIGNUP,
    ENABLE_API_KEYS,
    ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS,
    API_KEYS_ALLOWED_ENDPOINTS,
    ENABLE_FOLDERS,
    FOLDER_MAX_FILE_COUNT,
    ENABLE_USER_STATUS,
    ENABLE_USER_WEBHOOKS,
    BYPASS_ADMIN_ACCESS_CONTROL,
    USER_PERMISSIONS,
    DEFAULT_USER_ROLE,
    DEFAULT_GROUP_ID,
    PENDING_USER_OVERLAY_CONTENT,
    PENDING_USER_OVERLAY_TITLE,
    DEFAULT_PROMPT_SUGGESTIONS,
    DEFAULT_MODELS,
    DEFAULT_PINNED_MODELS,
    MODEL_ORDER_LIST,
    DEFAULT_MODEL_METADATA,
    DEFAULT_MODEL_PARAMS,
    # Misc
    ENV,
    CACHE_DIR,
    STATIC_DIR,
    FRONTEND_BUILD_DIR,
    CORS_ALLOW_ORIGIN,
    DEFAULT_LOCALE,
    WEBUI_URL,
    RESPONSE_WATERMARK,
    # Admin
    ENABLE_ADMIN_CHAT_ACCESS,
    BYPASS_ADMIN_ACCESS_CONTROL,
    ENABLE_ADMIN_EXPORT,
    # Tasks
    TASK_MODEL,
    TASK_MODEL_EXTERNAL,
    ENABLE_TAGS_GENERATION,
    ENABLE_TITLE_GENERATION,
    ENABLE_FOLLOW_UP_GENERATION,
    ENABLE_AUTOCOMPLETE_GENERATION,
    TITLE_GENERATION_PROMPT_TEMPLATE,
    FOLLOW_UP_GENERATION_PROMPT_TEMPLATE,
    TAGS_GENERATION_PROMPT_TEMPLATE,
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE,
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
    AppConfig,
    reset_config,
)
from open_webui.env import (
    ENABLE_CUSTOM_MODEL_FALLBACK,
    AUDIT_EXCLUDED_PATHS,
    AUDIT_LOG_LEVEL,
    GLOBAL_LOG_LEVEL,
    MAX_BODY_LOG_SIZE,
    SAFE_MODE,
    VERSION,
    DEPLOYMENT_ID,
    INSTANCE_ID,
    WEBUI_BUILD_HASH,
    ENABLE_SIGNUP_PASSWORD_CONFIRMATION,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_AUTH_TRUSTED_NAME_HEADER,
    ENABLE_COMPRESSION_MIDDLEWARE,
    ENABLE_WEBSOCKET_SUPPORT,
    BYPASS_MODEL_ACCESS_CONTROL,
    RESET_CONFIG_ON_START,
    EXTERNAL_PWA_MANIFEST_URL,
    ENABLE_PUBLIC_ACTIVE_USERS_COUNT,
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
    check_model_access,
    get_filtered_models,
)
from open_webui.utils.chat import (
    generate_chat_completion as chat_completion_handler,
    chat_completed as chat_completed_handler,
)
from open_webui.utils.actions import chat_action as chat_action_handler
from open_webui.utils.embeddings import generate_embeddings
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
from open_webui.utils.plugin import install_tool_and_function_dependencies
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
    Functions.deactivate_all_functions()

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
    start_logger()

    if RESET_CONFIG_ON_START:
        reset_config()

    # Create admin account from env vars if specified and no users exist
    if WEBUI_ADMIN_EMAIL and WEBUI_ADMIN_PASSWORD:
        if create_admin_user(WEBUI_ADMIN_EMAIL, WEBUI_ADMIN_PASSWORD, WEBUI_ADMIN_NAME):
            # Disable signup since we now have an admin
            app.state.config.ENABLE_SIGNUP = False

    # This should be blocking (sync) so functions are not deactivated on first /get_models calls
    # when the first user lands on the / route.
    log.info("Installing external dependencies of functions...")
    install_tool_and_function_dependencies()

    if THREAD_POOL_SIZE and THREAD_POOL_SIZE > 0:
        limiter = anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens = THREAD_POOL_SIZE

    asyncio.create_task(periodic_usage_pool_cleanup())
    asyncio.create_task(periodic_session_pool_cleanup())

    if app.state.config.ENABLE_BASE_MODELS_CACHE:
        try:
            await get_all_models(
                Request(
                    # Creating a mock request object to pass to get_all_models
                    {
                        "type": "http",
                        "asgi.version": "3.0",
                        "asgi.spec_version": "2.0",
                        "method": "GET",
                        "path": "/internal",
                        "query_string": b"",
                        "headers": Headers({}).raw,
                        "client": ("127.0.0.1", 12345),
                        "server": ("127.0.0.1", 80),
                        "scheme": "http",
                        "app": app,
                    }
                ),
                None,
            )
        except Exception as e:
            log.warning(f"Failed to pre-fetch models at startup: {e}")

    yield


app = FastAPI(
    title="Open WebUI",
    docs_url="/docs" if ENV == "dev" else None,
    openapi_url="/openapi.json" if ENV == "dev" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.state.instance_id = None
app.state.config = AppConfig()

app.state.WEBUI_NAME = WEBUI_NAME


########################################
#
# OLLAMA
#
########################################


app.state.config.ENABLE_OLLAMA_API = ENABLE_OLLAMA_API
app.state.config.OLLAMA_BASE_URLS = OLLAMA_BASE_URLS
app.state.config.OLLAMA_API_CONFIGS = OLLAMA_API_CONFIGS

app.state.OLLAMA_MODELS = {}

########################################
#
# OPENAI
#
########################################

app.state.config.ENABLE_OPENAI_API = ENABLE_OPENAI_API
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

app.state.config.ENABLE_BASE_MODELS_CACHE = ENABLE_BASE_MODELS_CACHE
app.state.BASE_MODELS = []

########################################
#
# WEBUI
#
########################################

app.state.config.WEBUI_URL = WEBUI_URL
app.state.config.ENABLE_SIGNUP = ENABLE_SIGNUP

app.state.config.ENABLE_API_KEYS = ENABLE_API_KEYS
app.state.config.ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS = (
    ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS
)
app.state.config.API_KEYS_ALLOWED_ENDPOINTS = API_KEYS_ALLOWED_ENDPOINTS

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
app.state.config.DEFAULT_GROUP_ID = DEFAULT_GROUP_ID

app.state.config.PENDING_USER_OVERLAY_CONTENT = PENDING_USER_OVERLAY_CONTENT
app.state.config.PENDING_USER_OVERLAY_TITLE = PENDING_USER_OVERLAY_TITLE

app.state.config.RESPONSE_WATERMARK = RESPONSE_WATERMARK

app.state.config.USER_PERMISSIONS = USER_PERMISSIONS
app.state.config.WEBHOOK_URL = WEBHOOK_URL
app.state.config.BANNERS = WEBUI_BANNERS


app.state.config.ENABLE_FOLDERS = ENABLE_FOLDERS
app.state.config.FOLDER_MAX_FILE_COUNT = FOLDER_MAX_FILE_COUNT
app.state.config.ENABLE_USER_WEBHOOKS = ENABLE_USER_WEBHOOKS
app.state.config.ENABLE_USER_STATUS = ENABLE_USER_STATUS

app.state.AUTH_TRUSTED_EMAIL_HEADER = WEBUI_AUTH_TRUSTED_EMAIL_HEADER
app.state.AUTH_TRUSTED_NAME_HEADER = WEBUI_AUTH_TRUSTED_NAME_HEADER
app.state.EXTERNAL_PWA_MANIFEST_URL = EXTERNAL_PWA_MANIFEST_URL


app.state.FUNCTIONS = {}
app.state.FUNCTION_CONTENTS = {}

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
app.state.config.TASK_MODEL_EXTERNAL = TASK_MODEL_EXTERNAL


app.state.config.ENABLE_AUTOCOMPLETE_GENERATION = ENABLE_AUTOCOMPLETE_GENERATION
app.state.config.ENABLE_TAGS_GENERATION = ENABLE_TAGS_GENERATION
app.state.config.ENABLE_TITLE_GENERATION = ENABLE_TITLE_GENERATION
app.state.config.ENABLE_FOLLOW_UP_GENERATION = ENABLE_FOLLOW_UP_GENERATION


app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = TITLE_GENERATION_PROMPT_TEMPLATE
app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE = TAGS_GENERATION_PROMPT_TEMPLATE
app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE = (
    FOLLOW_UP_GENERATION_PROMPT_TEMPLATE
)

app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = (
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
)
app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = (
    AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE
)
app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = (
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
)


########################################
#
# WEBUI
#
########################################

app.state.MODELS = MODELS

# Add the middleware to the app
if ENABLE_COMPRESSION_MIDDLEWARE:
    app.add_middleware(CompressMiddleware)


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


class APIKeyRestrictionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization")
        token = None

        if auth_header:
            parts = auth_header.split(" ", 1)
            if len(parts) == 2:
                token = parts[1]

        # Only apply restrictions if an sk- API key is used
        if token and token.startswith("sk-"):
            # Check if restrictions are enabled
            if request.app.state.config.ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS:
                allowed_paths = [
                    path.strip()
                    for path in str(
                        request.app.state.config.API_KEYS_ALLOWED_ENDPOINTS
                    ).split(",")
                    if path.strip()
                ]

                request_path = request.url.path

                # Match exact path or prefix path
                is_allowed = any(
                    request_path == allowed or request_path.startswith(allowed + "/")
                    for allowed in allowed_paths
                )

                if not is_allowed:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "detail": "API key not allowed to access this endpoint."
                        },
                    )

        response = await call_next(request)
        return response


app.add_middleware(APIKeyRestrictionMiddleware)


@app.middleware("http")
async def commit_session_after_request(request: Request, call_next):
    response = await call_next(request)
    # log.debug("Commit session after request")
    try:
        ScopedSession.commit()
    finally:
        # CRITICAL: remove() returns the connection to the pool.
        # Without this, connections remain "checked out" and accumulate
        # as "idle in transaction" in PostgreSQL.
        ScopedSession.remove()
    return response


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

    request.state.enable_api_keys = app.state.config.ENABLE_API_KEYS
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


app.include_router(ollama.router, prefix="/ollama", tags=["ollama"])
app.include_router(openai.router, prefix="/openai", tags=["openai"])


app.include_router(pipelines.router, prefix="/api/v1/pipelines", tags=["pipelines"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(configs.router, prefix="/api/v1/configs", tags=["configs"])

app.include_router(auths.router, prefix="/api/v1/auths", tags=["auths"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])


app.include_router(chats.router, prefix="/api/v1/chats", tags=["chats"])

app.include_router(models.router, prefix="/api/v1/models", tags=["models"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
app.include_router(skills.router, prefix="/api/v1/skills", tags=["skills"])

app.include_router(folders.router, prefix="/api/v1/folders", tags=["folders"])
app.include_router(groups.router, prefix="/api/v1/groups", tags=["groups"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(functions.router, prefix="/api/v1/functions", tags=["functions"])
app.include_router(utils.router, prefix="/api/v1/utils", tags=["utils"])


try:
    audit_level = AuditLevel(AUDIT_LOG_LEVEL)
except ValueError as e:
    logger.error(f"Invalid audit level: {AUDIT_LOG_LEVEL}. Error: {e}")
    audit_level = AuditLevel.NONE

if audit_level != AuditLevel.NONE:
    app.add_middleware(
        AuditLoggingMiddleware,
        audit_level=audit_level,
        excluded_paths=AUDIT_EXCLUDED_PATHS,
        max_body_size=MAX_BODY_LOG_SIZE,
    )
##################################
#
# Chat Endpoints
#
##################################


@app.get("/api/models")
@app.get("/api/v1/models")  # Experimental: Compatibility with OpenAI API
async def get_models(
    request: Request, refresh: bool = False, user=Depends(get_verified_user)
):
    all_models = await get_all_models(request, refresh=refresh, user=user)

    models = []
    for model in all_models:
        # Filter out filter pipelines
        if "pipeline" in model and model["pipeline"].get("type", None) == "filter":
            continue

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

    models = get_filtered_models(models, user)

    log.debug(
        f"/api/models returned filtered models accessible to the user: {json.dumps([model.get('id') for model in models])}"
    )
    return {"data": models}


@app.get("/api/models/base")
async def get_base_models(request: Request, user=Depends(get_admin_user)):
    models = await get_all_base_models(request, user=user)
    return {"data": models}


##################################
# Embeddings
##################################


@app.post("/api/embeddings")
@app.post("/api/v1/embeddings")  # Experimental: Compatibility with OpenAI API
async def embeddings(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """
    OpenAI-compatible embeddings endpoint.

    This handler:
      - Performs user/model checks and dispatches to the correct backend.
      - Supports OpenAI, Ollama, pipelines, and any compatible provider.

    Args:
        request (Request): Request context.
        form_data (dict): OpenAI-like payload (e.g., {"model": "...", "input": [...]})
        user: Authenticated user.

    Returns:
        dict: OpenAI-compatible embeddings response.
    """
    # Make sure models are loaded in app state
    if not request.app.state.MODELS:
        await get_all_models(request, user=user)
    # Use generic dispatcher in utils.embeddings
    return await generate_embeddings(request, form_data, user)


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

            # Check if user has access to the model
            if not BYPASS_MODEL_ACCESS_CONTROL and (
                user.role != "admin" or not BYPASS_ADMIN_ACCESS_CONTROL
            ):
                try:
                    check_model_access(user, model)
                except Exception as e:
                    raise e
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
        reasoning_tags = form_data.get("params", {}).get("reasoning_tags")

        # Model Params
        if model_info_params.get("stream_response") is not None:
            form_data["stream"] = model_info_params.get("stream_response")

        if model_info_params.get("stream_delta_chunk_size"):
            stream_delta_chunk_size = model_info_params.get("stream_delta_chunk_size")

        if model_info_params.get("reasoning_tags") is not None:
            reasoning_tags = model_info_params.get("reasoning_tags")

        metadata = {
            "user_id": user.id,
            "chat_id": form_data.pop("chat_id", None),
            "message_id": form_data.pop("id", None),
            "parent_message": form_data.pop("parent_message", None),
            "parent_message_id": form_data.pop("parent_id", None),
            "session_id": form_data.pop("session_id", None),
            "filter_ids": form_data.pop("filter_ids", []),
            "files": form_data.get("files", None),
            "features": form_data.get("features", {}),
            "variables": form_data.get("variables", {}),
            "model": model,
            "direct": model_item.get("direct", False),
            "params": {
                "stream_delta_chunk_size": stream_delta_chunk_size,
                "reasoning_tags": reasoning_tags,
                "function_calling": (
                    "native"
                    if (
                        form_data.get("params", {}).get("function_calling") == "native"
                        or model_info_params.get("function_calling") == "native"
                    )
                    else "default"
                ),
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
            form_data, metadata, events = await process_chat_payload(
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
                request, form_data, user, model, metadata, tasks, events
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
    pipeline, then converts the response back to Anthropic Messages format.

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
            request.state.direct = True
            request.state.model = model_item

        return await chat_completed_handler(request, form_data, user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post("/api/chat/actions/{action_id}")
async def chat_action(
    request: Request, action_id: str, form_data: dict, user=Depends(get_verified_user)
):
    try:
        model_item = form_data.pop("model_item", {})

        if model_item.get("direct", False):
            request.state.direct = True
            request.state.model = model_item

        return await chat_action_handler(request, action_id, form_data, user)
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
            "auth_trusted_header": bool(app.state.AUTH_TRUSTED_EMAIL_HEADER),
            "enable_signup_password_confirmation": ENABLE_SIGNUP_PASSWORD_CONFIRMATION,
            "enable_api_keys": app.state.config.ENABLE_API_KEYS,
            "enable_signup": app.state.config.ENABLE_SIGNUP,
            "enable_websocket": ENABLE_WEBSOCKET_SUPPORT,
            "enable_public_active_users_count": ENABLE_PUBLIC_ACTIVE_USERS_COUNT,
            "enable_easter_eggs": ENABLE_EASTER_EGGS,
            **(
                {
                    "enable_direct_connections": app.state.config.ENABLE_DIRECT_CONNECTIONS,
                    "enable_folders": app.state.config.ENABLE_FOLDERS,
                    "folder_max_file_count": app.state.config.FOLDER_MAX_FILE_COUNT,
                    "enable_autocomplete_generation": app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
                    "enable_user_webhooks": app.state.config.ENABLE_USER_WEBHOOKS,
                    "enable_user_status": app.state.config.ENABLE_USER_STATUS,
                    "enable_admin_export": ENABLE_ADMIN_EXPORT,
                    "enable_admin_chat_access": ENABLE_ADMIN_CHAT_ACCESS,
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
                "permissions": {**app.state.config.USER_PERMISSIONS},
                "ui": {
                    "pending_user_overlay_title": app.state.config.PENDING_USER_OVERLAY_TITLE,
                    "pending_user_overlay_content": app.state.config.PENDING_USER_OVERLAY_CONTENT,
                    "response_watermark": app.state.config.RESPONSE_WATERMARK,
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


class UrlForm(BaseModel):
    url: str


@app.get("/api/webhook")
async def get_webhook_url(user=Depends(get_admin_user)):
    return {
        "url": app.state.config.WEBHOOK_URL,
    }


@app.post("/api/webhook")
async def update_webhook_url(form_data: UrlForm, user=Depends(get_admin_user)):
    app.state.config.WEBHOOK_URL = form_data.url
    app.state.WEBHOOK_URL = app.state.config.WEBHOOK_URL
    return {"url": app.state.config.WEBHOOK_URL}


@app.get("/api/version")
async def get_app_version():
    return {
        "version": VERSION,
        "deployment_id": DEPLOYMENT_ID,
    }


@app.get("/api/usage")
async def get_current_usage(user=Depends(get_verified_user)):
    """
    Get current usage statistics for Open WebUI.
    This is an experimental endpoint and subject to change.
    """
    try:
        # If public visibility is disabled, only allow admins to access this endpoint
        if not ENABLE_PUBLIC_ACTIVE_USERS_COUNT and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only administrators can view usage statistics.",
            )

        return {
            "model_ids": get_models_in_use(),
            "user_count": Users.get_active_user_count(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting usage statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


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


@app.get("/opensearch.xml")
async def get_opensearch_xml():
    xml_content = rf"""
    <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/" xmlns:moz="http://www.mozilla.org/2006/browser/search/">
    <ShortName>{app.state.WEBUI_NAME}</ShortName>
    <Description>Search {app.state.WEBUI_NAME}</Description>
    <InputEncoding>UTF-8</InputEncoding>
    <Image width="16" height="16" type="image/x-icon">{app.state.config.WEBUI_URL}/static/favicon.png</Image>
    <Url type="text/html" method="get" template="{app.state.config.WEBUI_URL}/?q={"{searchTerms}"}"/>
    <moz:SearchForm>{app.state.config.WEBUI_URL}</moz:SearchForm>
    </OpenSearchDescription>
    """
    return Response(content=xml_content, media_type="application/xml")


@app.get("/health")
async def healthcheck():
    return {"status": True}


@app.get("/health/db")
async def healthcheck_with_db():
    ScopedSession.execute(text("SELECT 1;")).all()
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


def swagger_ui_html(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/static/swagger-ui/favicon.png",
    )


applications.get_swagger_ui_html = swagger_ui_html

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
