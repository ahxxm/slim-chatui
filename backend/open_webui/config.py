import json
import logging
import os
import shutil
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Generic, Optional, TypeVar
from urllib.parse import urlparse

from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime, Integer, func

from open_webui.env import (
    DATA_DIR,
    ENABLE_DB_MIGRATIONS,
    ENV,
    FRONTEND_BUILD_DIR,
    OPEN_WEBUI_DIR,
    WEBUI_AUTH,
    WEBUI_FAVICON_URL,
    WEBUI_NAME,
    log,
)
from open_webui.internal.db import Base, get_db


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/health") == -1


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

####################################
# Config helpers
####################################


# Function to run the alembic migrations
def run_migrations():
    log.info("Running migrations")
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(OPEN_WEBUI_DIR / "alembic.ini")

        # Set the script location dynamically
        migrations_path = OPEN_WEBUI_DIR / "migrations"
        alembic_cfg.set_main_option("script_location", str(migrations_path))

        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        log.exception(f"Error running migrations: {e}")


if ENABLE_DB_MIGRATIONS:
    run_migrations()


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


def load_json_config():
    with open(f"{DATA_DIR}/config.json", "r") as file:
        return json.load(file)


def save_to_db(data):
    with get_db() as db:
        existing_config = db.query(Config).first()
        if not existing_config:
            new_config = Config(data=data, version=0)
            db.add(new_config)
        else:
            existing_config.data = data
            existing_config.updated_at = datetime.now()
            db.add(existing_config)
        db.commit()


def reset_config():
    with get_db() as db:
        db.query(Config).delete()
        db.commit()


# When initializing, check if config.json exists and migrate it to the database
if os.path.exists(f"{DATA_DIR}/config.json"):
    data = load_json_config()
    save_to_db(data)
    os.rename(f"{DATA_DIR}/config.json", f"{DATA_DIR}/old_config.json")

DEFAULT_CONFIG = {
    "version": 0,
    "ui": {},
}


def get_config():
    with get_db() as db:
        config_entry = db.query(Config).order_by(Config.id.desc()).first()
        return config_entry.data if config_entry else DEFAULT_CONFIG


CONFIG_DATA = get_config()


def get_config_value(config_path: str):
    path_parts = config_path.split(".")
    cur_config = CONFIG_DATA
    for key in path_parts:
        if key in cur_config:
            cur_config = cur_config[key]
        else:
            return None
    return cur_config


PERSISTENT_CONFIG_REGISTRY = []


def save_config(config):
    global CONFIG_DATA
    global PERSISTENT_CONFIG_REGISTRY
    try:
        save_to_db(config)
        CONFIG_DATA = config

        # Trigger updates on all registered PersistentConfig entries
        for config_item in PERSISTENT_CONFIG_REGISTRY:
            config_item.update()
    except Exception as e:
        log.exception(e)
        return False
    return True


T = TypeVar("T")

ENABLE_PERSISTENT_CONFIG = (
    os.environ.get("ENABLE_PERSISTENT_CONFIG", "True").lower() == "true"
)


class PersistentConfig(Generic[T]):
    def __init__(self, env_name: str, config_path: str, env_value: T):
        self.env_name = env_name
        self.config_path = config_path
        self.env_value = env_value
        self.config_value = get_config_value(config_path)

        if self.config_value is not None and ENABLE_PERSISTENT_CONFIG:
            log.info(f"'{env_name}' loaded from the latest database entry")
            self.value = self.config_value
        else:
            self.value = env_value

        PERSISTENT_CONFIG_REGISTRY.append(self)

    def __str__(self):
        return str(self.value)

    @property
    def __dict__(self):
        raise TypeError(
            "PersistentConfig object cannot be converted to dict, use config_get or .value instead."
        )

    def __getattribute__(self, item):
        if item == "__dict__":
            raise TypeError(
                "PersistentConfig object cannot be converted to dict, use config_get or .value instead."
            )
        return super().__getattribute__(item)

    def update(self):
        new_value = get_config_value(self.config_path)
        if new_value is not None:
            self.value = new_value
            log.info(f"Updated {self.env_name} to new value {self.value}")

    def save(self):
        log.info(f"Saving '{self.env_name}' to the database")
        path_parts = self.config_path.split(".")
        sub_config = CONFIG_DATA
        for key in path_parts[:-1]:
            if key not in sub_config:
                sub_config[key] = {}
            sub_config = sub_config[key]
        sub_config[path_parts[-1]] = self.value
        save_to_db(CONFIG_DATA)
        self.config_value = self.value


class AppConfig:
    _state: dict[str, PersistentConfig]

    def __init__(self):
        super().__setattr__("_state", {})

    def __setattr__(self, key, value):
        if isinstance(value, PersistentConfig):
            self._state[key] = value
        else:
            self._state[key].value = value
            self._state[key].save()

    def __getattr__(self, key):
        if key not in self._state:
            raise AttributeError(f"Config key '{key}' not found")
        return self._state[key].value


####################################
# WEBUI_AUTH (Required for security)
####################################

ENABLE_API_KEYS = PersistentConfig(
    "ENABLE_API_KEYS",
    "auth.enable_api_keys",
    os.environ.get("ENABLE_API_KEYS", "False").lower() == "true",
)

ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS = PersistentConfig(
    "ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS",
    "auth.api_key.endpoint_restrictions",
    os.environ.get(
        "ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS",
        os.environ.get("ENABLE_API_KEY_ENDPOINT_RESTRICTIONS", "False"),
    ).lower()
    == "true",
)

API_KEYS_ALLOWED_ENDPOINTS = PersistentConfig(
    "API_KEYS_ALLOWED_ENDPOINTS",
    "auth.api_key.allowed_endpoints",
    os.environ.get(
        "API_KEYS_ALLOWED_ENDPOINTS", os.environ.get("API_KEY_ALLOWED_ENDPOINTS", "")
    ),
)

JWT_EXPIRES_IN = PersistentConfig(
    "JWT_EXPIRES_IN", "auth.jwt_expiry", os.environ.get("JWT_EXPIRES_IN", "4w")
)

if JWT_EXPIRES_IN.value == "-1":
    log.warning(
        "⚠️  SECURITY WARNING: JWT_EXPIRES_IN is set to '-1'\n"
        "    See: https://docs.openwebui.com/getting-started/env-configuration\n"
    )

####################################
# Static DIR
####################################

STATIC_DIR = Path(os.getenv("STATIC_DIR", OPEN_WEBUI_DIR / "static")).resolve()

try:
    if STATIC_DIR.exists():
        for item in STATIC_DIR.iterdir():
            if item.is_file() or item.is_symlink():
                try:
                    item.unlink()
                except Exception as e:
                    pass
except Exception as e:
    pass

for file_path in (FRONTEND_BUILD_DIR / "static").glob("**/*"):
    if file_path.is_file():
        target_path = STATIC_DIR / file_path.relative_to(
            (FRONTEND_BUILD_DIR / "static")
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(file_path, target_path)
        except Exception as e:
            logging.error(f"An error occurred: {e}")

frontend_favicon = FRONTEND_BUILD_DIR / "static" / "favicon.png"

if frontend_favicon.exists():
    try:
        shutil.copyfile(frontend_favicon, STATIC_DIR / "favicon.png")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

frontend_splash = FRONTEND_BUILD_DIR / "static" / "splash.png"

if frontend_splash.exists():
    try:
        shutil.copyfile(frontend_splash, STATIC_DIR / "splash.png")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

frontend_loader = FRONTEND_BUILD_DIR / "static" / "loader.js"

if frontend_loader.exists():
    try:
        shutil.copyfile(frontend_loader, STATIC_DIR / "loader.js")
    except Exception as e:
        logging.error(f"An error occurred: {e}")


####################################
# File Upload DIR
####################################

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


####################################
# Cache DIR
####################################

CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


####################################
# DIRECT CONNECTIONS
####################################

ENABLE_DIRECT_CONNECTIONS = PersistentConfig(
    "ENABLE_DIRECT_CONNECTIONS",
    "direct.enable",
    os.environ.get("ENABLE_DIRECT_CONNECTIONS", "False").lower() == "true",
)

####################################
# OLLAMA_BASE_URL
####################################

ENABLE_OLLAMA_API = PersistentConfig(
    "ENABLE_OLLAMA_API",
    "ollama.enable",
    os.environ.get("ENABLE_OLLAMA_API", "True").lower() == "true",
)

OLLAMA_API_BASE_URL = os.environ.get(
    "OLLAMA_API_BASE_URL", "http://localhost:11434/api"
)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "")
if OLLAMA_BASE_URL:
    # Remove trailing slash
    OLLAMA_BASE_URL = (
        OLLAMA_BASE_URL[:-1] if OLLAMA_BASE_URL.endswith("/") else OLLAMA_BASE_URL
    )


K8S_FLAG = os.environ.get("K8S_FLAG", "")
USE_OLLAMA_DOCKER = os.environ.get("USE_OLLAMA_DOCKER", "false")

if OLLAMA_BASE_URL == "" and OLLAMA_API_BASE_URL != "":
    OLLAMA_BASE_URL = (
        OLLAMA_API_BASE_URL[:-4]
        if OLLAMA_API_BASE_URL.endswith("/api")
        else OLLAMA_API_BASE_URL
    )

if ENV == "prod":
    if OLLAMA_BASE_URL == "/ollama" and not K8S_FLAG:
        if USE_OLLAMA_DOCKER.lower() == "true":
            # if you use all-in-one docker container (Open WebUI + Ollama)
            # with the docker build arg USE_OLLAMA=true (--build-arg="USE_OLLAMA=true") this only works with http://localhost:11434
            OLLAMA_BASE_URL = "http://localhost:11434"
        else:
            OLLAMA_BASE_URL = "http://host.docker.internal:11434"
    elif K8S_FLAG:
        OLLAMA_BASE_URL = "http://ollama-service.open-webui.svc.cluster.local:11434"


def _resolve_ollama_base_url(url: str) -> str:
    """If the default Ollama port (11434) is unreachable, try the fallback port (12434)."""

    def reachable(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (OSError, TimeoutError):
            return False

    host = urlparse(url).hostname or "localhost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        default = pool.submit(reachable, host, 11434)
        fallback = pool.submit(reachable, host, 12434)

    if not default.result() and fallback.result():
        url = url.replace(":11434", ":12434")
        log.info(f"Ollama port 11434 unreachable on {host}, falling back to 12434")
    elif not default.result():
        log.info(f"Ollama ports 11434 and 12434 both unreachable on {host}")

    return url


# Auto-resolve Ollama port when no explicit URL was provided by the user.
# The Dockerfile default is "/ollama" which the block above rewrites to :11434.
if os.environ.get("OLLAMA_BASE_URL", "") in ("", "/ollama") and not os.environ.get(
    "OLLAMA_BASE_URLS", ""
):
    OLLAMA_BASE_URL = _resolve_ollama_base_url(OLLAMA_BASE_URL)


OLLAMA_BASE_URLS = os.environ.get("OLLAMA_BASE_URLS", "")
OLLAMA_BASE_URLS = OLLAMA_BASE_URLS if OLLAMA_BASE_URLS != "" else OLLAMA_BASE_URL

OLLAMA_BASE_URLS = [url.strip() for url in OLLAMA_BASE_URLS.split(";")]
OLLAMA_BASE_URLS = PersistentConfig(
    "OLLAMA_BASE_URLS", "ollama.base_urls", OLLAMA_BASE_URLS
)

OLLAMA_API_CONFIGS = PersistentConfig(
    "OLLAMA_API_CONFIGS",
    "ollama.api_configs",
    {},
)

####################################
# OPENAI_API
####################################


ENABLE_OPENAI_API = PersistentConfig(
    "ENABLE_OPENAI_API",
    "openai.enable",
    os.environ.get("ENABLE_OPENAI_API", "True").lower() == "true",
)


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_BASE_URL = os.environ.get("OPENAI_API_BASE_URL", "")

if OPENAI_API_BASE_URL == "":
    OPENAI_API_BASE_URL = "https://api.openai.com/v1"
else:
    if OPENAI_API_BASE_URL.endswith("/"):
        OPENAI_API_BASE_URL = OPENAI_API_BASE_URL[:-1]

OPENAI_API_KEYS = os.environ.get("OPENAI_API_KEYS", "")
OPENAI_API_KEYS = OPENAI_API_KEYS if OPENAI_API_KEYS != "" else OPENAI_API_KEY

OPENAI_API_KEYS = [url.strip() for url in OPENAI_API_KEYS.split(";")]
OPENAI_API_KEYS = PersistentConfig(
    "OPENAI_API_KEYS", "openai.api_keys", OPENAI_API_KEYS
)

OPENAI_API_BASE_URLS = os.environ.get("OPENAI_API_BASE_URLS", "")
OPENAI_API_BASE_URLS = (
    OPENAI_API_BASE_URLS if OPENAI_API_BASE_URLS != "" else OPENAI_API_BASE_URL
)

OPENAI_API_BASE_URLS = [
    url.strip() if url != "" else "https://api.openai.com/v1"
    for url in OPENAI_API_BASE_URLS.split(";")
]
OPENAI_API_BASE_URLS = PersistentConfig(
    "OPENAI_API_BASE_URLS", "openai.api_base_urls", OPENAI_API_BASE_URLS
)

OPENAI_API_CONFIGS = PersistentConfig(
    "OPENAI_API_CONFIGS",
    "openai.api_configs",
    {},
)

# Get the actual OpenAI API key based on the base URL
OPENAI_API_KEY = ""
try:
    OPENAI_API_KEY = OPENAI_API_KEYS.value[
        OPENAI_API_BASE_URLS.value.index("https://api.openai.com/v1")
    ]
except Exception:
    pass
OPENAI_API_BASE_URL = "https://api.openai.com/v1"


####################################
# MODELS
####################################

ENABLE_BASE_MODELS_CACHE = PersistentConfig(
    "ENABLE_BASE_MODELS_CACHE",
    "models.base_models_cache",
    os.environ.get("ENABLE_BASE_MODELS_CACHE", "False").lower() == "true",
)


####################################
# TOOL_SERVERS
####################################

try:
    tool_server_connections = json.loads(
        os.environ.get("TOOL_SERVER_CONNECTIONS", "[]")
    )
except Exception as e:
    log.exception(f"Error loading TOOL_SERVER_CONNECTIONS: {e}")
    tool_server_connections = []


TOOL_SERVER_CONNECTIONS = PersistentConfig(
    "TOOL_SERVER_CONNECTIONS",
    "tool_server.connections",
    tool_server_connections,
)

####################################
# WEBUI
####################################


WEBUI_URL = PersistentConfig("WEBUI_URL", "webui.url", os.environ.get("WEBUI_URL", ""))


ENABLE_SIGNUP = PersistentConfig(
    "ENABLE_SIGNUP",
    "ui.enable_signup",
    (
        False
        if not WEBUI_AUTH
        else os.environ.get("ENABLE_SIGNUP", "True").lower() == "true"
    ),
)

ENABLE_LOGIN_FORM = PersistentConfig(
    "ENABLE_LOGIN_FORM",
    "ui.ENABLE_LOGIN_FORM",
    os.environ.get("ENABLE_LOGIN_FORM", "True").lower() == "true",
)


DEFAULT_LOCALE = PersistentConfig(
    "DEFAULT_LOCALE",
    "ui.default_locale",
    os.environ.get("DEFAULT_LOCALE", ""),
)

DEFAULT_MODELS = PersistentConfig(
    "DEFAULT_MODELS", "ui.default_models", os.environ.get("DEFAULT_MODELS", None)
)

DEFAULT_PINNED_MODELS = PersistentConfig(
    "DEFAULT_PINNED_MODELS",
    "ui.default_pinned_models",
    os.environ.get("DEFAULT_PINNED_MODELS", None),
)

try:
    default_prompt_suggestions = json.loads(
        os.environ.get("DEFAULT_PROMPT_SUGGESTIONS", "[]")
    )
except Exception as e:
    log.exception(f"Error loading DEFAULT_PROMPT_SUGGESTIONS: {e}")
    default_prompt_suggestions = []
if default_prompt_suggestions == []:
    default_prompt_suggestions = [
        {
            "title": ["Help me study", "vocabulary for a college entrance exam"],
            "content": "Help me study vocabulary: write a sentence for me to fill in the blank, and I'll try to pick the correct option.",
        },
        {
            "title": ["Give me ideas", "for what to do with my kids' art"],
            "content": "What are 5 creative things I could do with my kids' art? I don't want to throw them away, but it's also so much clutter.",
        },
        {
            "title": ["Tell me a fun fact", "about the Roman Empire"],
            "content": "Tell me a random fun fact about the Roman Empire",
        },
        {
            "title": ["Show me a code snippet", "of a website's sticky header"],
            "content": "Show me a code snippet of a website's sticky header in CSS and JavaScript.",
        },
        {
            "title": [
                "Explain options trading",
                "if I'm familiar with buying and selling stocks",
            ],
            "content": "Explain options trading in simple terms if I'm familiar with buying and selling stocks.",
        },
        {
            "title": ["Overcome procrastination", "give me tips"],
            "content": "Could you start by asking me about instances when I procrastinate the most and then give me some suggestions to overcome it?",
        },
    ]

DEFAULT_PROMPT_SUGGESTIONS = PersistentConfig(
    "DEFAULT_PROMPT_SUGGESTIONS",
    "ui.prompt_suggestions",
    default_prompt_suggestions,
)

MODEL_ORDER_LIST = PersistentConfig(
    "MODEL_ORDER_LIST",
    "ui.model_order_list",
    [],
)

DEFAULT_MODEL_METADATA = PersistentConfig(
    "DEFAULT_MODEL_METADATA",
    "models.default_metadata",
    {},
)

DEFAULT_MODEL_PARAMS = PersistentConfig(
    "DEFAULT_MODEL_PARAMS",
    "models.default_params",
    {},
)

DEFAULT_USER_ROLE = PersistentConfig(
    "DEFAULT_USER_ROLE",
    "ui.default_user_role",
    os.getenv("DEFAULT_USER_ROLE", "pending"),
)

DEFAULT_GROUP_ID = PersistentConfig(
    "DEFAULT_GROUP_ID",
    "ui.default_group_id",
    os.environ.get("DEFAULT_GROUP_ID", ""),
)

PENDING_USER_OVERLAY_TITLE = PersistentConfig(
    "PENDING_USER_OVERLAY_TITLE",
    "ui.pending_user_overlay_title",
    os.environ.get("PENDING_USER_OVERLAY_TITLE", ""),
)

PENDING_USER_OVERLAY_CONTENT = PersistentConfig(
    "PENDING_USER_OVERLAY_CONTENT",
    "ui.pending_user_overlay_content",
    os.environ.get("PENDING_USER_OVERLAY_CONTENT", ""),
)


RESPONSE_WATERMARK = PersistentConfig(
    "RESPONSE_WATERMARK",
    "ui.watermark",
    os.environ.get("RESPONSE_WATERMARK", ""),
)


USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS", "False").lower() == "true"
)

USER_PERMISSIONS_WORKSPACE_SKILLS_ACCESS = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_SKILLS_ACCESS", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_MODELS_IMPORT = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_MODELS_IMPORT", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_MODELS_EXPORT = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_MODELS_EXPORT", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_PROMPTS_IMPORT = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_PROMPTS_IMPORT", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_PROMPTS_EXPORT = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_PROMPTS_EXPORT", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_TOOLS_IMPORT = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_TOOLS_IMPORT", "False").lower() == "true"
)

USER_PERMISSIONS_WORKSPACE_TOOLS_EXPORT = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_TOOLS_EXPORT", "False").lower() == "true"
)


USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_SHARING = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_SHARING", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_PUBLIC_SHARING = (
    os.environ.get(
        "USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_PUBLIC_SHARING", "False"
    ).lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_SHARING = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_SHARING", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_PUBLIC_SHARING = (
    os.environ.get(
        "USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_PUBLIC_SHARING", "False"
    ).lower()
    == "true"
)


USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_SHARING = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_SHARING", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_PUBLIC_SHARING = (
    os.environ.get(
        "USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_PUBLIC_SHARING", "False"
    ).lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_SKILLS_ALLOW_SHARING = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_SKILLS_ALLOW_SHARING", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_SKILLS_ALLOW_PUBLIC_SHARING = (
    os.environ.get(
        "USER_PERMISSIONS_WORKSPACE_SKILLS_ALLOW_PUBLIC_SHARING", "False"
    ).lower()
    == "true"
)


USER_PERMISSIONS_CHAT_CONTROLS = (
    os.environ.get("USER_PERMISSIONS_CHAT_CONTROLS", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_VALVES = (
    os.environ.get("USER_PERMISSIONS_CHAT_VALVES", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_SYSTEM_PROMPT = (
    os.environ.get("USER_PERMISSIONS_CHAT_SYSTEM_PROMPT", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_PARAMS = (
    os.environ.get("USER_PERMISSIONS_CHAT_PARAMS", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_FILE_UPLOAD = (
    os.environ.get("USER_PERMISSIONS_CHAT_FILE_UPLOAD", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_WEB_UPLOAD = (
    os.environ.get("USER_PERMISSIONS_CHAT_WEB_UPLOAD", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_DELETE = (
    os.environ.get("USER_PERMISSIONS_CHAT_DELETE", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_DELETE_MESSAGE = (
    os.environ.get("USER_PERMISSIONS_CHAT_DELETE_MESSAGE", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_CONTINUE_RESPONSE = (
    os.environ.get("USER_PERMISSIONS_CHAT_CONTINUE_RESPONSE", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_REGENERATE_RESPONSE = (
    os.environ.get("USER_PERMISSIONS_CHAT_REGENERATE_RESPONSE", "True").lower()
    == "true"
)

USER_PERMISSIONS_CHAT_RATE_RESPONSE = (
    os.environ.get("USER_PERMISSIONS_CHAT_RATE_RESPONSE", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_EDIT = (
    os.environ.get("USER_PERMISSIONS_CHAT_EDIT", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_SHARE = (
    os.environ.get("USER_PERMISSIONS_CHAT_SHARE", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_EXPORT = (
    os.environ.get("USER_PERMISSIONS_CHAT_EXPORT", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_MULTIPLE_MODELS = (
    os.environ.get("USER_PERMISSIONS_CHAT_MULTIPLE_MODELS", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_TEMPORARY = (
    os.environ.get("USER_PERMISSIONS_CHAT_TEMPORARY", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_TEMPORARY_ENFORCED = (
    os.environ.get("USER_PERMISSIONS_CHAT_TEMPORARY_ENFORCED", "False").lower()
    == "true"
)


USER_PERMISSIONS_FEATURES_DIRECT_TOOL_SERVERS = (
    os.environ.get("USER_PERMISSIONS_FEATURES_DIRECT_TOOL_SERVERS", "False").lower()
    == "true"
)

USER_PERMISSIONS_FEATURES_CODE_INTERPRETER = (
    os.environ.get("USER_PERMISSIONS_FEATURES_CODE_INTERPRETER", "True").lower()
    == "true"
)

USER_PERMISSIONS_FEATURES_FOLDERS = (
    os.environ.get("USER_PERMISSIONS_FEATURES_FOLDERS", "True").lower() == "true"
)

USER_PERMISSIONS_FEATURES_API_KEYS = (
    os.environ.get("USER_PERMISSIONS_FEATURES_API_KEYS", "False").lower() == "true"
)

USER_PERMISSIONS_SETTINGS_INTERFACE = (
    os.environ.get("USER_PERMISSIONS_SETTINGS_INTERFACE", "True").lower() == "true"
)


DEFAULT_USER_PERMISSIONS = {
    "workspace": {
        "models": USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS,
        "prompts": USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS,
        "tools": USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS,
        "skills": USER_PERMISSIONS_WORKSPACE_SKILLS_ACCESS,
        "models_import": USER_PERMISSIONS_WORKSPACE_MODELS_IMPORT,
        "models_export": USER_PERMISSIONS_WORKSPACE_MODELS_EXPORT,
        "prompts_import": USER_PERMISSIONS_WORKSPACE_PROMPTS_IMPORT,
        "prompts_export": USER_PERMISSIONS_WORKSPACE_PROMPTS_EXPORT,
        "tools_import": USER_PERMISSIONS_WORKSPACE_TOOLS_IMPORT,
        "tools_export": USER_PERMISSIONS_WORKSPACE_TOOLS_EXPORT,
    },
    "sharing": {
        "models": USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_SHARING,
        "public_models": USER_PERMISSIONS_WORKSPACE_MODELS_ALLOW_PUBLIC_SHARING,
        "prompts": USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_SHARING,
        "public_prompts": USER_PERMISSIONS_WORKSPACE_PROMPTS_ALLOW_PUBLIC_SHARING,
        "tools": USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_SHARING,
        "public_tools": USER_PERMISSIONS_WORKSPACE_TOOLS_ALLOW_PUBLIC_SHARING,
        "skills": USER_PERMISSIONS_WORKSPACE_SKILLS_ALLOW_SHARING,
        "public_skills": USER_PERMISSIONS_WORKSPACE_SKILLS_ALLOW_PUBLIC_SHARING,
    },
    "chat": {
        "controls": USER_PERMISSIONS_CHAT_CONTROLS,
        "valves": USER_PERMISSIONS_CHAT_VALVES,
        "system_prompt": USER_PERMISSIONS_CHAT_SYSTEM_PROMPT,
        "params": USER_PERMISSIONS_CHAT_PARAMS,
        "file_upload": USER_PERMISSIONS_CHAT_FILE_UPLOAD,
        "web_upload": USER_PERMISSIONS_CHAT_WEB_UPLOAD,
        "delete": USER_PERMISSIONS_CHAT_DELETE,
        "delete_message": USER_PERMISSIONS_CHAT_DELETE_MESSAGE,
        "continue_response": USER_PERMISSIONS_CHAT_CONTINUE_RESPONSE,
        "regenerate_response": USER_PERMISSIONS_CHAT_REGENERATE_RESPONSE,
        "rate_response": USER_PERMISSIONS_CHAT_RATE_RESPONSE,
        "edit": USER_PERMISSIONS_CHAT_EDIT,
        "share": USER_PERMISSIONS_CHAT_SHARE,
        "export": USER_PERMISSIONS_CHAT_EXPORT,
        "multiple_models": USER_PERMISSIONS_CHAT_MULTIPLE_MODELS,
        "temporary": USER_PERMISSIONS_CHAT_TEMPORARY,
        "temporary_enforced": USER_PERMISSIONS_CHAT_TEMPORARY_ENFORCED,
    },
    "features": {
        # General features
        "api_keys": USER_PERMISSIONS_FEATURES_API_KEYS,
        "folders": USER_PERMISSIONS_FEATURES_FOLDERS,
        "direct_tool_servers": USER_PERMISSIONS_FEATURES_DIRECT_TOOL_SERVERS,
        # Chat features
        "code_interpreter": USER_PERMISSIONS_FEATURES_CODE_INTERPRETER,
    },
    "settings": {
        "interface": USER_PERMISSIONS_SETTINGS_INTERFACE,
    },
}

USER_PERMISSIONS = PersistentConfig(
    "USER_PERMISSIONS",
    "user.permissions",
    DEFAULT_USER_PERMISSIONS,
)

ENABLE_FOLDERS = PersistentConfig(
    "ENABLE_FOLDERS",
    "folders.enable",
    os.environ.get("ENABLE_FOLDERS", "True").lower() == "true",
)

FOLDER_MAX_FILE_COUNT = PersistentConfig(
    "FOLDER_MAX_FILE_COUNT",
    "folders.max_file_count",
    os.environ.get("FOLDER_MAX_FILE_COUNT", ""),
)

ENABLE_USER_STATUS = PersistentConfig(
    "ENABLE_USER_STATUS",
    "users.enable_status",
    os.environ.get("ENABLE_USER_STATUS", "True").lower() == "true",
)

WEBHOOK_URL = PersistentConfig(
    "WEBHOOK_URL", "webhook_url", os.environ.get("WEBHOOK_URL", "")
)

ENABLE_ADMIN_EXPORT = os.environ.get("ENABLE_ADMIN_EXPORT", "True").lower() == "true"

ENABLE_ADMIN_WORKSPACE_CONTENT_ACCESS = (
    os.environ.get("ENABLE_ADMIN_WORKSPACE_CONTENT_ACCESS", "True").lower() == "true"
)

BYPASS_ADMIN_ACCESS_CONTROL = (
    os.environ.get(
        "BYPASS_ADMIN_ACCESS_CONTROL",
        os.environ.get("ENABLE_ADMIN_WORKSPACE_CONTENT_ACCESS", "True"),
    ).lower()
    == "true"
)

ENABLE_ADMIN_CHAT_ACCESS = (
    os.environ.get("ENABLE_ADMIN_CHAT_ACCESS", "True").lower() == "true"
)


ENABLE_USER_WEBHOOKS = PersistentConfig(
    "ENABLE_USER_WEBHOOKS",
    "ui.enable_user_webhooks",
    os.environ.get("ENABLE_USER_WEBHOOKS", "True").lower() == "true",
)

# FastAPI / AnyIO settings
THREAD_POOL_SIZE = os.getenv("THREAD_POOL_SIZE", None)

if THREAD_POOL_SIZE is not None and isinstance(THREAD_POOL_SIZE, str):
    try:
        THREAD_POOL_SIZE = int(THREAD_POOL_SIZE)
    except ValueError:
        log.warning(
            f"THREAD_POOL_SIZE is not a valid integer: {THREAD_POOL_SIZE}. Defaulting to None."
        )
        THREAD_POOL_SIZE = None


def validate_cors_origin(origin):
    parsed_url = urlparse(origin)

    # Check if the scheme is either http or https, or a custom scheme
    schemes = ["http", "https"] + CORS_ALLOW_CUSTOM_SCHEME
    if parsed_url.scheme not in schemes:
        raise ValueError(
            f"Invalid scheme in CORS_ALLOW_ORIGIN: '{origin}'. Only 'http' and 'https' and CORS_ALLOW_CUSTOM_SCHEME are allowed."
        )

    # Ensure that the netloc (domain + port) is present, indicating it's a valid URL
    if not parsed_url.netloc:
        raise ValueError(f"Invalid URL structure in CORS_ALLOW_ORIGIN: '{origin}'.")


# For production, you should only need one host as
# fastapi serves the svelte-kit built frontend and backend from the same host and port.
# To test CORS_ALLOW_ORIGIN locally, you can set something like
# CORS_ALLOW_ORIGIN=http://localhost:5173;http://localhost:8080
# in your .env file depending on your frontend port, 5173 in this case.
CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*").split(";")

# Allows custom URL schemes (e.g., app://) to be used as origins for CORS.
# Useful for local development or desktop clients with schemes like app:// or other custom protocols.
# Provide a semicolon-separated list of allowed schemes in the environment variable CORS_ALLOW_CUSTOM_SCHEMES.
CORS_ALLOW_CUSTOM_SCHEME = os.environ.get("CORS_ALLOW_CUSTOM_SCHEME", "").split(";")

if CORS_ALLOW_ORIGIN == ["*"]:
    log.warning(
        "\n\nWARNING: CORS_ALLOW_ORIGIN IS SET TO '*' - NOT RECOMMENDED FOR PRODUCTION DEPLOYMENTS.\n"
    )
else:
    # You have to pick between a single wildcard or a list of origins.
    # Doing both will result in CORS errors in the browser.
    for origin in CORS_ALLOW_ORIGIN:
        validate_cors_origin(origin)


class BannerModel(BaseModel):
    id: str
    type: str
    title: Optional[str] = None
    content: str
    dismissible: bool
    timestamp: int


try:
    banners = json.loads(os.environ.get("WEBUI_BANNERS", "[]"))
    banners = [BannerModel(**banner) for banner in banners]
except Exception as e:
    log.exception(f"Error loading WEBUI_BANNERS: {e}")
    banners = []

WEBUI_BANNERS = PersistentConfig("WEBUI_BANNERS", "ui.banners", banners)


SHOW_ADMIN_DETAILS = PersistentConfig(
    "SHOW_ADMIN_DETAILS",
    "auth.admin.show",
    os.environ.get("SHOW_ADMIN_DETAILS", "true").lower() == "true",
)

ADMIN_EMAIL = PersistentConfig(
    "ADMIN_EMAIL",
    "auth.admin.email",
    os.environ.get("ADMIN_EMAIL", None),
)


####################################
# TASKS
####################################


TASK_MODEL = PersistentConfig(
    "TASK_MODEL",
    "task.model.default",
    os.environ.get("TASK_MODEL", ""),
)

TASK_MODEL_EXTERNAL = PersistentConfig(
    "TASK_MODEL_EXTERNAL",
    "task.model.external",
    os.environ.get("TASK_MODEL_EXTERNAL", ""),
)

TITLE_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "TITLE_GENERATION_PROMPT_TEMPLATE",
    "task.title.prompt_template",
    os.environ.get("TITLE_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate a concise, 3-5 word title with an emoji summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Use emojis that enhance understanding of the topic, but avoid quotation marks or special formatting.
- Write the title in the chat's primary language; default to English if multilingual.
- Prioritize accuracy over excessive creativity; keep it clear and simple.
- Your entire response must consist solely of the JSON object, without any introductory or concluding text.
- The output must be a single, raw JSON object, without any markdown code fences or other encapsulating text.
- Ensure no conversational text, affirmations, or explanations precede or follow the raw JSON output, as this will cause direct parsing failure.
### Output:
JSON format: { "title": "your concise title here" }
### Examples:
- { "title": "📉 Stock Market Trends" },
- { "title": "🍪 Perfect Chocolate Chip Recipe" },
- { "title": "Evolution of Music Streaming" },
- { "title": "Remote Work Productivity Tips" },
- { "title": "Artificial Intelligence in Healthcare" },
- { "title": "🎮 Video Game Development Insights" }
### Chat History:
<chat_history>
{{MESSAGES:END:2}}
</chat_history>"""

TAGS_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "TAGS_GENERATION_PROMPT_TEMPLATE",
    "task.tags.prompt_template",
    os.environ.get("TAGS_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.

### Guidelines:
- Start with high-level domains (e.g. Science, Technology, Philosophy, Arts, Politics, Business, Health, Sports, Entertainment, Education)
- Consider including relevant subfields/subdomains if they are strongly represented throughout the conversation
- If content is too short (less than 3 messages) or too diverse, use only ["General"]
- Use the chat's primary language; default to English if multilingual
- Prioritize accuracy over specificity

### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

FOLLOW_UP_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "FOLLOW_UP_GENERATION_PROMPT_TEMPLATE",
    "task.follow_up.prompt_template",
    os.environ.get("FOLLOW_UP_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE = """### Task:
Suggest 3-5 relevant follow-up questions or prompts that the user might naturally ask next in this conversation as a **user**, based on the chat history, to help continue or deepen the discussion.
### Guidelines:
- Write all follow-up questions from the user’s point of view, directed to the assistant.
- Make questions concise, clear, and directly related to the discussed topic(s).
- Only suggest follow-ups that make sense given the chat content and do not repeat what was already covered.
- If the conversation is very short or not specific, suggest more general (but relevant) follow-ups the user might ask.
- Use the conversation's primary language; default to English if multilingual.
- Response must be a JSON array of strings, no extra text or formatting.
### Output:
JSON format: { "follow_ups": ["Question 1?", "Question 2?", "Question 3?"] }
### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

ENABLE_FOLLOW_UP_GENERATION = PersistentConfig(
    "ENABLE_FOLLOW_UP_GENERATION",
    "task.follow_up.enable",
    os.environ.get("ENABLE_FOLLOW_UP_GENERATION", "True").lower() == "true",
)

ENABLE_TAGS_GENERATION = PersistentConfig(
    "ENABLE_TAGS_GENERATION",
    "task.tags.enable",
    os.environ.get("ENABLE_TAGS_GENERATION", "True").lower() == "true",
)

ENABLE_TITLE_GENERATION = PersistentConfig(
    "ENABLE_TITLE_GENERATION",
    "task.title.enable",
    os.environ.get("ENABLE_TITLE_GENERATION", "True").lower() == "true",
)


ENABLE_AUTOCOMPLETE_GENERATION = PersistentConfig(
    "ENABLE_AUTOCOMPLETE_GENERATION",
    "task.autocomplete.enable",
    os.environ.get("ENABLE_AUTOCOMPLETE_GENERATION", "False").lower() == "true",
)

AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = PersistentConfig(
    "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH",
    "task.autocomplete.input_max_length",
    int(os.environ.get("AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH", "-1")),
)

AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE",
    "task.autocomplete.prompt_template",
    os.environ.get("AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE", ""),
)


DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = """### Task:
You are an autocompletion system. Continue the text in `<text>` based on the **completion type** in `<type>` and the given language.  

### **Instructions**:
1. Analyze `<text>` for context and meaning.  
2. Use `<type>` to guide your output:  
   - **General**: Provide a natural, concise continuation.  
   - **Search Query**: Complete as if generating a realistic search query.  
3. Start as if you are directly continuing `<text>`. Do **not** repeat, paraphrase, or respond as a model. Simply complete the text.  
4. Ensure the continuation:
   - Flows naturally from `<text>`.  
   - Avoids repetition, overexplaining, or unrelated ideas.  
5. If unsure, return: `{ "text": "" }`.  

### **Output Rules**:
- Respond only in JSON format: `{ "text": "<your_completion>" }`.

### **Examples**:
#### Example 1:  
Input:  
<type>General</type>  
<text>The sun was setting over the horizon, painting the sky</text>  
Output:  
{ "text": "with vibrant shades of orange and pink." }

#### Example 2:  
Input:  
<type>Search Query</type>  
<text>Top-rated restaurants in</text>  
Output:  
{ "text": "New York City for Italian cuisine." }  

---
### Context:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
<type>{{TYPE}}</type>  
<text>{{PROMPT}}</text>  
#### Output:
"""


TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = PersistentConfig(
    "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE",
    "task.tools.prompt_template",
    os.environ.get("TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE", ""),
)


DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = """Available Tools: {{TOOLS}}

Your task is to choose and return the correct tool(s) from the list of available tools based on the query. Follow these guidelines:

- Return only the JSON object, without any additional text or explanation.

- If no tools match the query, return an empty array: 
   {
     "tool_calls": []
   }

- If one or more tools match the query, construct a JSON response containing a "tool_calls" array with objects that include:
   - "name": The tool's name.
   - "parameters": A dictionary of required parameters and their corresponding values.

The format for the JSON response is strictly:
{
  "tool_calls": [
    {"name": "toolName1", "parameters": {"key1": "value1"}},
    {"name": "toolName2", "parameters": {"key2": "value2"}}
  ]
}"""


DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE = """Your task is to reflect the speaker's likely facial expression through a fitting emoji. Interpret emotions from the message and reflect their facial expression using fitting, diverse emojis (e.g., 😊, 😢, 😡, 😱).

Message: ```{{prompt}}```"""

DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE = """You have been provided with a set of responses from various models to the latest user query: "{{prompt}}"

Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured, coherent, and adheres to the highest standards of accuracy and reliability.

Responses from models: {{responses}}"""


####################################
# Code Interpreter
####################################

ENABLE_CODE_EXECUTION = PersistentConfig(
    "ENABLE_CODE_EXECUTION",
    "code_execution.enable",
    os.environ.get("ENABLE_CODE_EXECUTION", "True").lower() == "true",
)

CODE_EXECUTION_ENGINE = PersistentConfig(
    "CODE_EXECUTION_ENGINE",
    "code_execution.engine",
    os.environ.get("CODE_EXECUTION_ENGINE", "jupyter"),
)

CODE_EXECUTION_JUPYTER_URL = PersistentConfig(
    "CODE_EXECUTION_JUPYTER_URL",
    "code_execution.jupyter.url",
    os.environ.get("CODE_EXECUTION_JUPYTER_URL", ""),
)

CODE_EXECUTION_JUPYTER_AUTH = PersistentConfig(
    "CODE_EXECUTION_JUPYTER_AUTH",
    "code_execution.jupyter.auth",
    os.environ.get("CODE_EXECUTION_JUPYTER_AUTH", ""),
)

CODE_EXECUTION_JUPYTER_AUTH_TOKEN = PersistentConfig(
    "CODE_EXECUTION_JUPYTER_AUTH_TOKEN",
    "code_execution.jupyter.auth_token",
    os.environ.get("CODE_EXECUTION_JUPYTER_AUTH_TOKEN", ""),
)


CODE_EXECUTION_JUPYTER_AUTH_PASSWORD = PersistentConfig(
    "CODE_EXECUTION_JUPYTER_AUTH_PASSWORD",
    "code_execution.jupyter.auth_password",
    os.environ.get("CODE_EXECUTION_JUPYTER_AUTH_PASSWORD", ""),
)

CODE_EXECUTION_JUPYTER_TIMEOUT = PersistentConfig(
    "CODE_EXECUTION_JUPYTER_TIMEOUT",
    "code_execution.jupyter.timeout",
    int(os.environ.get("CODE_EXECUTION_JUPYTER_TIMEOUT", "60")),
)

ENABLE_CODE_INTERPRETER = PersistentConfig(
    "ENABLE_CODE_INTERPRETER",
    "code_interpreter.enable",
    os.environ.get("ENABLE_CODE_INTERPRETER", "True").lower() == "true",
)

CODE_INTERPRETER_ENGINE = PersistentConfig(
    "CODE_INTERPRETER_ENGINE",
    "code_interpreter.engine",
    os.environ.get("CODE_INTERPRETER_ENGINE", "jupyter"),
)

CODE_INTERPRETER_PROMPT_TEMPLATE = PersistentConfig(
    "CODE_INTERPRETER_PROMPT_TEMPLATE",
    "code_interpreter.prompt_template",
    os.environ.get("CODE_INTERPRETER_PROMPT_TEMPLATE", ""),
)

CODE_INTERPRETER_JUPYTER_URL = PersistentConfig(
    "CODE_INTERPRETER_JUPYTER_URL",
    "code_interpreter.jupyter.url",
    os.environ.get(
        "CODE_INTERPRETER_JUPYTER_URL", os.environ.get("CODE_EXECUTION_JUPYTER_URL", "")
    ),
)

CODE_INTERPRETER_JUPYTER_AUTH = PersistentConfig(
    "CODE_INTERPRETER_JUPYTER_AUTH",
    "code_interpreter.jupyter.auth",
    os.environ.get(
        "CODE_INTERPRETER_JUPYTER_AUTH",
        os.environ.get("CODE_EXECUTION_JUPYTER_AUTH", ""),
    ),
)

CODE_INTERPRETER_JUPYTER_AUTH_TOKEN = PersistentConfig(
    "CODE_INTERPRETER_JUPYTER_AUTH_TOKEN",
    "code_interpreter.jupyter.auth_token",
    os.environ.get(
        "CODE_INTERPRETER_JUPYTER_AUTH_TOKEN",
        os.environ.get("CODE_EXECUTION_JUPYTER_AUTH_TOKEN", ""),
    ),
)


CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD = PersistentConfig(
    "CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD",
    "code_interpreter.jupyter.auth_password",
    os.environ.get(
        "CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD",
        os.environ.get("CODE_EXECUTION_JUPYTER_AUTH_PASSWORD", ""),
    ),
)

CODE_INTERPRETER_JUPYTER_TIMEOUT = PersistentConfig(
    "CODE_INTERPRETER_JUPYTER_TIMEOUT",
    "code_interpreter.jupyter.timeout",
    int(
        os.environ.get(
            "CODE_INTERPRETER_JUPYTER_TIMEOUT",
            os.environ.get("CODE_EXECUTION_JUPYTER_TIMEOUT", "60"),
        )
    ),
)

CODE_INTERPRETER_BLOCKED_MODULES = [
    library.strip()
    for library in os.environ.get("CODE_INTERPRETER_BLOCKED_MODULES", "").split(",")
    if library.strip()
]

DEFAULT_CODE_INTERPRETER_PROMPT = """
#### Tools Available

1. **Code Interpreter**: `<code_interpreter type="code" lang="python"></code_interpreter>`
   - You have access to a Python shell that runs directly in the user's browser, enabling fast execution of code for analysis, calculations, or problem-solving.  Use it in this response.
   - The Python code you write can incorporate a wide array of libraries, handle data manipulation or visualization, perform API calls for web-related tasks, or tackle virtually any computational challenge. Use this flexibility to **think outside the box, craft elegant solutions, and harness Python's full potential**.
   - To use it, **you must enclose your code within `<code_interpreter type="code" lang="python">` XML tags** and stop right away. If you don't, the code won't execute. 
   - When writing code in the code_interpreter XML tag, Do NOT use the triple backticks code block for markdown formatting, example: ```py # python code ``` will cause an error because it is markdown formatting, it is not python code.
   - When coding, **always aim to print meaningful outputs** (e.g., results, tables, summaries, or visuals) to better interpret and verify the findings. Avoid relying on implicit outputs; prioritize explicit and clear print statements so the results are effectively communicated to the user.  
   - After obtaining the printed output, **always provide a concise analysis, interpretation, or next steps to help the user understand the findings or refine the outcome further.**  
   - If the results are unclear, unexpected, or require validation, refine the code and execute it again as needed. Always aim to deliver meaningful insights from the results, iterating if necessary.  
   - **If a link to an image, audio, or any file is provided in markdown format in the output, ALWAYS regurgitate word for word, explicitly display it as part of the response to ensure the user can access it easily, do NOT change the link.**
   - All responses should be communicated in the chat's primary language, ensuring seamless understanding. If the chat is multilingual, default to English for clarity.

Ensure that the tools are effectively utilized to achieve the highest-quality analysis for the user."""


####################################
# File Image Compression
####################################

FILE_IMAGE_COMPRESSION_WIDTH = PersistentConfig(
    "FILE_IMAGE_COMPRESSION_WIDTH",
    "file.image_compression_width",
    (
        int(os.environ.get("FILE_IMAGE_COMPRESSION_WIDTH"))
        if os.environ.get("FILE_IMAGE_COMPRESSION_WIDTH")
        else None
    ),
)

FILE_IMAGE_COMPRESSION_HEIGHT = PersistentConfig(
    "FILE_IMAGE_COMPRESSION_HEIGHT",
    "file.image_compression_height",
    (
        int(os.environ.get("FILE_IMAGE_COMPRESSION_HEIGHT"))
        if os.environ.get("FILE_IMAGE_COMPRESSION_HEIGHT")
        else None
    ),
)
