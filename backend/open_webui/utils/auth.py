import logging
import jwt
import bcrypt


from datetime import datetime, timedelta
from pytz import UTC
from typing import Optional, Union

from open_webui.models.users import Users
from open_webui.models.auths import Auths


from open_webui.constants import ERROR_MESSAGES

from open_webui.env import (
    ENABLE_PASSWORD_VALIDATION,
    PASSWORD_VALIDATION_HINT,
    PASSWORD_VALIDATION_REGEX_PATTERN,
    WEBUI_SECRET_KEY,
)

from fastapi import BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger(__name__)

SESSION_SECRET = WEBUI_SECRET_KEY
ALGORITHM = "HS256"

##############
# Auth Utils
##############


bearer_security = HTTPBearer(auto_error=False)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def validate_password(password: str) -> bool:
    # The password passed to bcrypt must be 72 bytes or fewer. If it is longer, it will be truncated before hashing.
    if len(password.encode("utf-8")) > 72:
        raise Exception(
            ERROR_MESSAGES.PASSWORD_TOO_LONG,
        )

    if ENABLE_PASSWORD_VALIDATION:
        if not PASSWORD_VALIDATION_REGEX_PATTERN.match(password):
            raise Exception(ERROR_MESSAGES.INVALID_PASSWORD(PASSWORD_VALIDATION_HINT))

    return True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return (
        bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
        if hashed_password
        else None
    )


def create_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    payload = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
        payload.update({"exp": expire})

    encoded_jwt = jwt.encode(payload, SESSION_SECRET, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        decoded = jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITHM])
        return decoded
    except Exception:
        return None


def extract_token_from_auth_header(auth_header: str):
    return auth_header[len("Bearer ") :]


def get_http_authorization_cred(auth_header: Optional[str]):
    if not auth_header:
        return None
    try:
        scheme, credentials = auth_header.split(" ")
        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)
    except Exception:
        return None


async def get_current_user(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    auth_token: HTTPAuthorizationCredentials = Depends(bearer_security),
    # NOTE: We intentionally do NOT use Depends(get_session) here.
    # Sessions are managed internally with short-lived context managers.
    # This ensures connections are released immediately after auth queries,
    # not held for the entire request duration (e.g., during 30+ second LLM calls).
):
    token = None

    if auth_token is not None:
        token = auth_token.credentials

    if token is None and "token" in request.cookies:
        token = request.cookies.get("token")

    # Fallback to request.state.token (set by middleware, e.g. for x-api-key)
    if token is None and hasattr(request.state, "token") and request.state.token:
        token = request.state.token.credentials

    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # auth by jwt token
    try:
        try:
            data = decode_token(token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        if data is not None and "id" in data:
            user = Users.get_user_by_id(data["id"])
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ERROR_MESSAGES.INVALID_TOKEN,
                )
            else:
                return user
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.UNAUTHORIZED,
            )
    except Exception as e:
        # Delete the token cookie
        if request.cookies.get("token"):
            response.delete_cookie("token")

        raise e


def get_verified_user(user=Depends(get_current_user)):
    if user.role not in {"user", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return user


def get_admin_user(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    return user


def create_admin_user(email: str, password: str, name: str = "Admin"):
    """
    Create an admin user from environment variables.
    Used for headless/automated deployments.
    Returns the created user or None if creation failed.
    """

    if not email or not password:
        return None

    if Users.has_users():
        log.debug("Users already exist, skipping admin creation")
        return None

    log.info(f"Creating admin account from environment variables: {email}")
    try:
        hashed = get_password_hash(password)
        user = Auths.insert_new_auth(
            email=email.lower(),
            password=hashed,
            name=name,
            role="admin",
        )
        if user:
            log.info(f"Admin account created successfully: {email}")
            return user
        else:
            log.error("Failed to create admin account from environment variables")
            return None
    except Exception as e:
        log.error(f"Error creating admin account: {e}")
        return None
