import importlib.metadata
import json
import logging
import os
import sys
import shutil
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from pathlib import Path
import re


from open_webui.constants import ERROR_MESSAGES

####################################
# Load .env file
####################################

# Use .resolve() to get the canonical path, removing any '..' or '.' components
ENV_FILE_PATH = Path(__file__).resolve()

# OPEN_WEBUI_DIR should be the directory where env.py resides (open_webui/)
OPEN_WEBUI_DIR = ENV_FILE_PATH.parent

# BACKEND_DIR is the parent of OPEN_WEBUI_DIR (backend/)
BACKEND_DIR = OPEN_WEBUI_DIR.parent

# BASE_DIR is the parent of BACKEND_DIR (open-webui-dev/)
BASE_DIR = BACKEND_DIR.parent

try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(str(BASE_DIR / ".env")))
except ImportError:
    print("dotenv not installed, skipping...")

DOCKER = os.environ.get("DOCKER", "False").lower() == "true"

####################################
# LOGGING
####################################

_LEVEL_MAP = {
    "DEBUG": "debug",
    "INFO": "info",
    "WARNING": "warn",
    "ERROR": "error",
    "CRITICAL": "fatal",
}


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": _LEVEL_MAP.get(record.levelname, record.levelname.lower()),
            "msg": record.getMessage(),
            "caller": record.name,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["error"] = "".join(
                traceback.format_exception(*record.exc_info)
            ).rstrip()
        elif record.exc_text:
            log_entry["error"] = record.exc_text

        if record.stack_info:
            log_entry["stacktrace"] = record.stack_info

        return json.dumps(log_entry, ensure_ascii=False, default=str)


LOG_FORMAT = os.environ.get("LOG_FORMAT", "").lower()

GLOBAL_LOG_LEVEL = os.environ.get("GLOBAL_LOG_LEVEL", "").upper()
if GLOBAL_LOG_LEVEL in logging.getLevelNamesMapping():
    if LOG_FORMAT == "json":
        _handler = logging.StreamHandler(sys.stdout)
        _handler.setFormatter(JSONFormatter())
        logging.basicConfig(handlers=[_handler], level=GLOBAL_LOG_LEVEL, force=True)
    else:
        logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL, force=True)
else:
    GLOBAL_LOG_LEVEL = "INFO"

log = logging.getLogger(__name__)
log.info(f"GLOBAL_LOG_LEVEL: {GLOBAL_LOG_LEVEL}")

SRC_LOG_LEVELS = {}  # Legacy variable, do not remove

WEBUI_NAME = os.environ.get("WEBUI_NAME", "Open WebUI")
if WEBUI_NAME != "Open WebUI":
    WEBUI_NAME += " (Open WebUI)"

WEBUI_FAVICON_URL = "https://openwebui.com/favicon.png"

TRUSTED_SIGNATURE_KEY = os.environ.get("TRUSTED_SIGNATURE_KEY", "")

####################################
# ENV (dev,test,prod)
####################################

ENV = os.environ.get("ENV", "dev")

FROM_INIT_PY = os.environ.get("FROM_INIT_PY", "False").lower() == "true"

if FROM_INIT_PY:
    PACKAGE_DATA = {"version": importlib.metadata.version("open-webui")}
else:
    try:
        PACKAGE_DATA = json.loads((BASE_DIR / "package.json").read_text())
    except Exception:
        PACKAGE_DATA = {"version": "0.0.0"}

VERSION = PACKAGE_DATA["version"]


DEPLOYMENT_ID = os.environ.get("DEPLOYMENT_ID", "")
INSTANCE_ID = os.environ.get("INSTANCE_ID", str(uuid4()))

ENABLE_DB_MIGRATIONS = os.environ.get("ENABLE_DB_MIGRATIONS", "True").lower() == "true"


####################################
# SAFE_MODE
####################################

SAFE_MODE = os.environ.get("SAFE_MODE", "false").lower() == "true"


####################################
# ENABLE_FORWARD_USER_INFO_HEADERS
####################################

ENABLE_FORWARD_USER_INFO_HEADERS = (
    os.environ.get("ENABLE_FORWARD_USER_INFO_HEADERS", "False").lower() == "true"
)

# Header names for user info forwarding (customizable via environment variables)
FORWARD_USER_INFO_HEADER_USER_NAME = os.environ.get(
    "FORWARD_USER_INFO_HEADER_USER_NAME", "X-OpenWebUI-User-Name"
)
FORWARD_USER_INFO_HEADER_USER_ID = os.environ.get(
    "FORWARD_USER_INFO_HEADER_USER_ID", "X-OpenWebUI-User-Id"
)
FORWARD_USER_INFO_HEADER_USER_EMAIL = os.environ.get(
    "FORWARD_USER_INFO_HEADER_USER_EMAIL", "X-OpenWebUI-User-Email"
)
FORWARD_USER_INFO_HEADER_USER_ROLE = os.environ.get(
    "FORWARD_USER_INFO_HEADER_USER_ROLE", "X-OpenWebUI-User-Role"
)

# Header name for chat ID forwarding (customizable via environment variable)
FORWARD_SESSION_INFO_HEADER_MESSAGE_ID = os.environ.get(
    "FORWARD_SESSION_INFO_HEADER_MESSAGE_ID", "X-OpenWebUI-Message-Id"
)
FORWARD_SESSION_INFO_HEADER_CHAT_ID = os.environ.get(
    "FORWARD_SESSION_INFO_HEADER_CHAT_ID", "X-OpenWebUI-Chat-Id"
)

ENABLE_EASTER_EGGS = os.environ.get("ENABLE_EASTER_EGGS", "True").lower() == "true"

####################################
# WEBUI_BUILD_HASH
####################################

WEBUI_BUILD_HASH = os.environ.get("WEBUI_BUILD_HASH", "dev-build")

####################################
# DATA/FRONTEND BUILD DIR
####################################

DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data")).resolve()

if FROM_INIT_PY:
    NEW_DATA_DIR = Path(os.getenv("DATA_DIR", OPEN_WEBUI_DIR / "data")).resolve()
    NEW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check if the data directory exists in the package directory
    if DATA_DIR.exists() and DATA_DIR != NEW_DATA_DIR:
        log.info(f"Moving {DATA_DIR} to {NEW_DATA_DIR}")
        for item in DATA_DIR.iterdir():
            dest = NEW_DATA_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        # Zip the data directory
        shutil.make_archive(DATA_DIR.parent / "open_webui_data", "zip", DATA_DIR)

        # Remove the old data directory
        shutil.rmtree(DATA_DIR)

    DATA_DIR = Path(os.getenv("DATA_DIR", OPEN_WEBUI_DIR / "data"))

STATIC_DIR = Path(os.getenv("STATIC_DIR", OPEN_WEBUI_DIR / "static"))

FRONTEND_BUILD_DIR = Path(os.getenv("FRONTEND_BUILD_DIR", BASE_DIR / "build")).resolve()

if FROM_INIT_PY:
    FRONTEND_BUILD_DIR = Path(
        os.getenv("FRONTEND_BUILD_DIR", OPEN_WEBUI_DIR / "frontend")
    ).resolve()

####################################
# Database
####################################

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR}/webui.db")

ENABLE_REALTIME_CHAT_SAVE = (
    os.environ.get("ENABLE_REALTIME_CHAT_SAVE", "False").lower() == "true"
)

####################################
# UVICORN WORKERS
####################################

# Number of uvicorn worker processes for handling requests
UVICORN_WORKERS = os.environ.get("UVICORN_WORKERS", "1")
try:
    UVICORN_WORKERS = int(UVICORN_WORKERS)
    if UVICORN_WORKERS < 1:
        UVICORN_WORKERS = 1
except ValueError:
    UVICORN_WORKERS = 1
    log.info(f"Invalid UVICORN_WORKERS value, defaulting to {UVICORN_WORKERS}")

####################################
# WEBUI_AUTH (Required for security)
####################################

WEBUI_AUTH = os.environ.get("WEBUI_AUTH", "True").lower() == "true"

ENABLE_INITIAL_ADMIN_SIGNUP = (
    os.environ.get("ENABLE_INITIAL_ADMIN_SIGNUP", "False").lower() == "true"
)
ENABLE_SIGNUP_PASSWORD_CONFIRMATION = (
    os.environ.get("ENABLE_SIGNUP_PASSWORD_CONFIRMATION", "False").lower() == "true"
)

####################################
# Admin Account Runtime Creation
####################################

# Optional env vars for creating an admin account on startup
# Useful for headless/automated deployments
WEBUI_ADMIN_EMAIL = os.environ.get("WEBUI_ADMIN_EMAIL", "")
WEBUI_ADMIN_PASSWORD = os.environ.get("WEBUI_ADMIN_PASSWORD", "")
WEBUI_ADMIN_NAME = os.environ.get("WEBUI_ADMIN_NAME", "Admin")

ENABLE_PASSWORD_VALIDATION = (
    os.environ.get("ENABLE_PASSWORD_VALIDATION", "False").lower() == "true"
)
PASSWORD_VALIDATION_REGEX_PATTERN = os.environ.get(
    "PASSWORD_VALIDATION_REGEX_PATTERN",
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$",
)


try:
    PASSWORD_VALIDATION_REGEX_PATTERN = rf"{PASSWORD_VALIDATION_REGEX_PATTERN}"
    PASSWORD_VALIDATION_REGEX_PATTERN = re.compile(PASSWORD_VALIDATION_REGEX_PATTERN)
except Exception as e:
    log.error(f"Invalid PASSWORD_VALIDATION_REGEX_PATTERN: {e}")
    PASSWORD_VALIDATION_REGEX_PATTERN = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$"
    )

PASSWORD_VALIDATION_HINT = os.environ.get("PASSWORD_VALIDATION_HINT", "")


WEBUI_AUTH_SIGNOUT_REDIRECT_URL = os.environ.get(
    "WEBUI_AUTH_SIGNOUT_REDIRECT_URL", None
)

####################################
# WEBUI_SECRET_KEY
####################################

WEBUI_SECRET_KEY = os.environ.get(
    "WEBUI_SECRET_KEY",
    os.environ.get(
        "WEBUI_JWT_SECRET_KEY", "t0p-s3cr3t"
    ),  # DEPRECATED: remove at next major version
)

WEBUI_SESSION_COOKIE_SAME_SITE = os.environ.get("WEBUI_SESSION_COOKIE_SAME_SITE", "lax")

WEBUI_SESSION_COOKIE_SECURE = (
    os.environ.get("WEBUI_SESSION_COOKIE_SECURE", "false").lower() == "true"
)

WEBUI_AUTH_COOKIE_SAME_SITE = os.environ.get(
    "WEBUI_AUTH_COOKIE_SAME_SITE", WEBUI_SESSION_COOKIE_SAME_SITE
)

WEBUI_AUTH_COOKIE_SECURE = (
    os.environ.get(
        "WEBUI_AUTH_COOKIE_SECURE",
        os.environ.get("WEBUI_SESSION_COOKIE_SECURE", "false"),
    ).lower()
    == "true"
)

if WEBUI_AUTH and WEBUI_SECRET_KEY == "":
    raise ValueError(ERROR_MESSAGES.ENV_VAR_NOT_FOUND)

####################################
# MODELS
####################################

ENABLE_CUSTOM_MODEL_FALLBACK = (
    os.environ.get("ENABLE_CUSTOM_MODEL_FALLBACK", "False").lower() == "true"
)


####################################
# CHAT
####################################

ENABLE_CHAT_RESPONSE_BASE64_IMAGE_URL_CONVERSION = (
    os.environ.get("ENABLE_CHAT_RESPONSE_BASE64_IMAGE_URL_CONVERSION", "False").lower()
    == "true"
)

CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE = os.environ.get(
    "CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE", "1"
)

if CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE == "":
    CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE = 1
else:
    try:
        CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE = int(
            CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE
        )
    except Exception:
        CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE = 1


CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE = os.environ.get(
    "CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE", ""
)

if CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE == "":
    CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE = None
else:
    try:
        CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE = int(
            CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE
        )
    except Exception:
        CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE = None


####################################
# WEBSOCKET SUPPORT
####################################

ENABLE_WEBSOCKET_SUPPORT = (
    os.environ.get("ENABLE_WEBSOCKET_SUPPORT", "True").lower() == "true"
)


WEBSOCKET_SERVER_LOGGING = (
    os.environ.get("WEBSOCKET_SERVER_LOGGING", "False").lower() == "true"
)
WEBSOCKET_SERVER_ENGINEIO_LOGGING = (
    os.environ.get(
        "WEBSOCKET_SERVER_ENGINEIO_LOGGING",
        os.environ.get("WEBSOCKET_SERVER_LOGGING", "False"),
    ).lower()
    == "true"
)
WEBSOCKET_SERVER_PING_TIMEOUT = os.environ.get("WEBSOCKET_SERVER_PING_TIMEOUT", "20")
try:
    WEBSOCKET_SERVER_PING_TIMEOUT = int(WEBSOCKET_SERVER_PING_TIMEOUT)
except ValueError:
    WEBSOCKET_SERVER_PING_TIMEOUT = 20

WEBSOCKET_SERVER_PING_INTERVAL = os.environ.get("WEBSOCKET_SERVER_PING_INTERVAL", "25")
try:
    WEBSOCKET_SERVER_PING_INTERVAL = int(WEBSOCKET_SERVER_PING_INTERVAL)
except ValueError:
    WEBSOCKET_SERVER_PING_INTERVAL = 25


REQUESTS_VERIFY = os.environ.get("REQUESTS_VERIFY", "True").lower() == "true"

AIOHTTP_CLIENT_TIMEOUT = os.environ.get("AIOHTTP_CLIENT_TIMEOUT", "")

if AIOHTTP_CLIENT_TIMEOUT == "":
    AIOHTTP_CLIENT_TIMEOUT = None
else:
    try:
        AIOHTTP_CLIENT_TIMEOUT = int(AIOHTTP_CLIENT_TIMEOUT)
    except Exception:
        AIOHTTP_CLIENT_TIMEOUT = 300


AIOHTTP_CLIENT_SESSION_SSL = (
    os.environ.get("AIOHTTP_CLIENT_SESSION_SSL", "True").lower() == "true"
)

AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST = os.environ.get(
    "AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST",
    os.environ.get("AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST", "10"),
)

if AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST == "":
    AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST = None
else:
    try:
        AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST = int(AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST)
    except Exception:
        AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST = 10

####################################
# AUDIT LOGGING
####################################
ENABLE_AUDIT_STDOUT = os.getenv("ENABLE_AUDIT_STDOUT", "False").lower() == "true"
ENABLE_AUDIT_LOGS_FILE = os.getenv("ENABLE_AUDIT_LOGS_FILE", "True").lower() == "true"

# Where to store log file
# Defaults to the DATA_DIR/audit.log. To set AUDIT_LOGS_FILE_PATH you need to
# provide the whole path, like: /app/audit.log
AUDIT_LOGS_FILE_PATH = os.getenv("AUDIT_LOGS_FILE_PATH", f"{DATA_DIR}/audit.log")
# Maximum size of a file before rotating into a new log file
AUDIT_LOG_FILE_ROTATION_SIZE = os.getenv("AUDIT_LOG_FILE_ROTATION_SIZE", "10MB")

# Comma separated list of logger names to use for audit logging
# Default is "uvicorn.access" which is the access log for Uvicorn
# You can add more logger names to this list if you want to capture more logs
AUDIT_UVICORN_LOGGER_NAMES = os.getenv(
    "AUDIT_UVICORN_LOGGER_NAMES", "uvicorn.access"
).split(",")

# METADATA | REQUEST | REQUEST_RESPONSE
AUDIT_LOG_LEVEL = os.getenv("AUDIT_LOG_LEVEL", "NONE").upper()
try:
    MAX_BODY_LOG_SIZE = int(os.environ.get("MAX_BODY_LOG_SIZE") or 2048)
except ValueError:
    MAX_BODY_LOG_SIZE = 2048

# Comma separated list for urls to exclude from audit
AUDIT_EXCLUDED_PATHS = os.getenv("AUDIT_EXCLUDED_PATHS", "/chats,/chat,/folders").split(
    ","
)
AUDIT_EXCLUDED_PATHS = [path.strip() for path in AUDIT_EXCLUDED_PATHS]
AUDIT_EXCLUDED_PATHS = [path.lstrip("/") for path in AUDIT_EXCLUDED_PATHS]


####################################
# PROGRESSIVE WEB APP OPTIONS
####################################

EXTERNAL_PWA_MANIFEST_URL = os.environ.get("EXTERNAL_PWA_MANIFEST_URL")
