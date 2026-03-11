import re
import uuid
import time
import datetime
import logging


from open_webui.models.auths import (
    AddUserForm,
    Auths,
    Token,
    SigninForm,
    SigninResponse,
    SignupForm,
    UpdatePasswordForm,
)
from open_webui.models.users import (
    UserModel,
    UserProfileImageResponse,
    Users,
    UpdateProfileForm,
)
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import (
    WEBUI_AUTH,
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_COOKIE_SECURE,
    WEBUI_AUTH_SIGNOUT_REDIRECT_URL,
    ENABLE_INITIAL_ADMIN_SIGNUP,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

from open_webui.utils.misc import parse_duration, validate_email_format
from open_webui.utils.auth import (
    validate_password,
    verify_password,
    decode_token,
    create_token,
    get_admin_user,
    get_verified_user,
    get_current_user,
    get_password_hash,
    get_http_authorization_cred,
)
from open_webui.internal.db import get_session
from sqlalchemy.orm import Session
from open_webui.utils.rate_limit import RateLimiter
from open_webui.utils.route import route_error_handler


from typing import Optional

router = APIRouter()

log = logging.getLogger(__name__)

signin_rate_limiter = RateLimiter(limit=5 * 3, window=60 * 3)


def create_session_response(
    request: Request, user, db, response: Response = None, set_cookie: bool = False
) -> dict:
    """
    Create JWT token and build session response for a user.
    Shared helper for signin, signup, add_user, and token_exchange endpoints.

    Args:
        request: FastAPI request object
        user: User object
        db: Database session
        response: FastAPI response object (required if set_cookie is True)
        set_cookie: Whether to set the auth cookie on the response
    """
    expires_delta = parse_duration(request.app.state.config.JWT_EXPIRES_IN)
    expires_at = None
    if expires_delta:
        expires_at = int(time.time()) + int(expires_delta.total_seconds())

    token = create_token(
        data={"id": user.id},
        expires_delta=expires_delta,
    )

    if set_cookie and response:
        datetime_expires_at = (
            datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
            if expires_at
            else None
        )
        response.set_cookie(
            key="token",
            value=token,
            expires=datetime_expires_at,
            httponly=True,
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
        )

    return {
        "token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }


############################
# GetSessionUser
############################


class SessionUserResponse(Token, UserProfileImageResponse):
    expires_at: Optional[int] = None


@router.get("/", response_model=SessionUserResponse)
async def get_session_user(
    request: Request,
    response: Response,
    user=Depends(get_current_user),
):

    auth_header = request.headers.get("Authorization")
    auth_token = get_http_authorization_cred(auth_header)
    token = auth_token.credentials
    data = decode_token(token)

    expires_at = None

    if data:
        expires_at = data.get("exp")

        if (expires_at is not None) and int(time.time()) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.INVALID_TOKEN,
            )

        # Set the cookie token
        response.set_cookie(
            key="token",
            value=token,
            expires=(
                datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
                if expires_at
                else None
            ),
            httponly=True,  # Ensures the cookie is not accessible via JavaScript
            samesite=WEBUI_AUTH_COOKIE_SAME_SITE,
            secure=WEBUI_AUTH_COOKIE_SECURE,
        )

    return {
        "token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }


############################
# Update Profile
############################


@router.post("/update/profile", response_model=UserProfileImageResponse)
async def update_profile(
    form_data: UpdateProfileForm,
    session_user=Depends(get_verified_user),
):
    user = Users.update_user_by_id(
        session_user.id,
        form_data.model_dump(),
    )
    if not user:
        raise HTTPException(400, detail=ERROR_MESSAGES.DEFAULT())

    return user


############################
# Update Password
############################


@router.post("/update/password", response_model=bool)
async def update_password(
    form_data: UpdatePasswordForm,
    session_user=Depends(get_current_user),
):
    user = Auths.authenticate_user(
        session_user.email,
        lambda pw: verify_password(form_data.password, pw),
    )
    if not user:
        raise HTTPException(400, detail=ERROR_MESSAGES.INCORRECT_PASSWORD)

    validate_password(form_data.password)
    hashed = get_password_hash(form_data.new_password)
    return Auths.update_user_password_by_id(user.id, hashed)


############################
# SignIn
############################


@router.post("/signin", response_model=SessionUserResponse)
async def signin(
    request: Request,
    response: Response,
    form_data: SigninForm,
    db: Session = Depends(get_session),
):
    if WEBUI_AUTH == False:
        admin_email = "admin@localhost"
        admin_password = "admin"

        if Users.get_user_by_email(admin_email.lower(), db=db):
            user = Auths.authenticate_user(
                admin_email.lower(),
                lambda pw: verify_password(admin_password, pw),
                db=db,
            )
        else:
            if Users.has_users(db=db):
                raise HTTPException(400, detail=ERROR_MESSAGES.EXISTING_USERS)

            user = signup_handler(
                request,
                admin_email,
                admin_password,
                "User",
                db=db,
            )
    else:
        if signin_rate_limiter.is_limited(form_data.email.lower()):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ERROR_MESSAGES.RATE_LIMIT_EXCEEDED,
            )

        password_bytes = form_data.password.encode("utf-8")
        if len(password_bytes) > 72:
            # TODO: Implement other hashing algorithms that support longer passwords
            log.info("Password too long, truncating to 72 bytes for bcrypt")
            password_bytes = password_bytes[:72]

            # decode safely — ignore incomplete UTF-8 sequences
            form_data.password = password_bytes.decode("utf-8", errors="ignore")

        user = Auths.authenticate_user(
            form_data.email.lower(),
            lambda pw: verify_password(form_data.password, pw),
            db=db,
        )

    if not user:
        raise HTTPException(400, detail=ERROR_MESSAGES.INVALID_CRED)

    return create_session_response(request, user, db, response, set_cookie=True)


############################
# SignUp
############################


def signup_handler(
    request: Request,
    email: str,
    password: str,
    name: str,
    *,
    db: Session,
) -> UserModel:
    # Create a user. Used by signin (no-auth auto-create) and signup.
    # Safe from concurrent first-signup race: insert's flush() escalates
    # the DEFERRED transaction to RESERVED, blocking other writers until commit.
    first_user = not Users.has_users(db=db)
    role = "admin" if first_user else request.app.state.config.DEFAULT_USER_ROLE

    hashed = get_password_hash(password)
    user = Auths.insert_new_auth(
        email=email.lower(),
        password=hashed,
        name=name,
        role=role,
        db=db,
    )
    if not user:
        raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)

    if first_user:
        request.app.state.config.ENABLE_SIGNUP = False

    return user


@router.post("/signup", response_model=SessionUserResponse)
@route_error_handler(
    detail="An internal error occurred during signup.", status_code=500
)
async def signup(
    request: Request,
    response: Response,
    form_data: SignupForm,
    db: Session = Depends(get_session),
):
    has_users = Users.has_users(db=db)

    if WEBUI_AUTH:
        if not request.app.state.config.ENABLE_SIGNUP:
            if has_users or not ENABLE_INITIAL_ADMIN_SIGNUP:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
                )
    else:
        if has_users:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED
            )

    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower(), db=db):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    validate_password(form_data.password)

    user = signup_handler(
        request,
        form_data.email,
        form_data.password,
        form_data.name,
        db=db,
    )
    return create_session_response(request, user, db, response, set_cookie=True)


@router.get("/signout")
async def signout(request: Request, response: Response):
    response.delete_cookie("token")

    if WEBUI_AUTH_SIGNOUT_REDIRECT_URL:
        return JSONResponse(
            status_code=200,
            content={
                "status": True,
                "redirect_url": WEBUI_AUTH_SIGNOUT_REDIRECT_URL,
            },
            headers=response.headers,
        )

    return JSONResponse(
        status_code=200, content={"status": True}, headers=response.headers
    )


############################
# AddUser
############################


@router.post("/add", response_model=SigninResponse)
@route_error_handler(
    detail="An internal error occurred while adding the user.", status_code=500
)
async def add_user(
    request: Request,
    form_data: AddUserForm,
    user=Depends(get_admin_user),
    db: Session = Depends(get_session),
):
    if not validate_email_format(form_data.email.lower()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.INVALID_EMAIL_FORMAT
        )

    if Users.get_user_by_email(form_data.email.lower(), db=db):
        raise HTTPException(400, detail=ERROR_MESSAGES.EMAIL_TAKEN)

    validate_password(form_data.password)

    hashed = get_password_hash(form_data.password)
    user = Auths.insert_new_auth(
        form_data.email.lower(),
        hashed,
        form_data.name,
        form_data.role,
        db=db,
    )

    if user:
        token = create_token(data={"id": user.id})
        return {
            "token": token,
            "token_type": "Bearer",
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }

    raise HTTPException(500, detail=ERROR_MESSAGES.CREATE_USER_ERROR)


############################
# GetAdminDetails
############################


@router.get("/admin/details")
async def get_admin_details(request: Request, user=Depends(get_current_user)):
    admin_email = request.app.state.config.ADMIN_EMAIL
    admin_name = None

    log.info(f"Admin details - Email: {admin_email}, Name: {admin_name}")

    if admin_email:
        admin = Users.get_user_by_email(admin_email)
        if admin:
            admin_name = admin.name
    else:
        admin = Users.get_first_user()
        if admin:
            admin_email = admin.email
            admin_name = admin.name

    return {
        "name": admin_name,
        "email": admin_email,
    }


############################
# AdminConfig
############################


@router.get("/admin/config")
async def get_admin_config(request: Request, user=Depends(get_admin_user)):
    return {
        "ADMIN_EMAIL": request.app.state.config.ADMIN_EMAIL,
        "WEBUI_URL": request.app.state.config.WEBUI_URL,
        "ENABLE_SIGNUP": request.app.state.config.ENABLE_SIGNUP,
        "DEFAULT_USER_ROLE": request.app.state.config.DEFAULT_USER_ROLE,
        "JWT_EXPIRES_IN": request.app.state.config.JWT_EXPIRES_IN,
        "PENDING_USER_OVERLAY_TITLE": request.app.state.config.PENDING_USER_OVERLAY_TITLE,
        "PENDING_USER_OVERLAY_CONTENT": request.app.state.config.PENDING_USER_OVERLAY_CONTENT,
    }


class AdminConfig(BaseModel):
    ADMIN_EMAIL: Optional[str] = None
    WEBUI_URL: str
    ENABLE_SIGNUP: bool
    DEFAULT_USER_ROLE: str
    JWT_EXPIRES_IN: str
    PENDING_USER_OVERLAY_TITLE: Optional[str] = None
    PENDING_USER_OVERLAY_CONTENT: Optional[str] = None


@router.post("/admin/config")
async def update_admin_config(
    request: Request,
    form_data: AdminConfig,
    user=Depends(get_admin_user),
):
    request.app.state.config.ADMIN_EMAIL = form_data.ADMIN_EMAIL
    request.app.state.config.WEBUI_URL = form_data.WEBUI_URL
    request.app.state.config.ENABLE_SIGNUP = form_data.ENABLE_SIGNUP

    if form_data.DEFAULT_USER_ROLE in ["pending", "user", "admin"]:
        request.app.state.config.DEFAULT_USER_ROLE = form_data.DEFAULT_USER_ROLE

    pattern = r"^(-1|0|(-?\d+(\.\d+)?)(ms|s|m|h|d|w))$"

    # Check if the input string matches the pattern
    if re.match(pattern, form_data.JWT_EXPIRES_IN):
        request.app.state.config.JWT_EXPIRES_IN = form_data.JWT_EXPIRES_IN

    request.app.state.config.PENDING_USER_OVERLAY_TITLE = (
        form_data.PENDING_USER_OVERLAY_TITLE
    )
    request.app.state.config.PENDING_USER_OVERLAY_CONTENT = (
        form_data.PENDING_USER_OVERLAY_CONTENT
    )
    request.app.state.config.persist()

    return {
        "ADMIN_EMAIL": request.app.state.config.ADMIN_EMAIL,
        "WEBUI_URL": request.app.state.config.WEBUI_URL,
        "ENABLE_SIGNUP": request.app.state.config.ENABLE_SIGNUP,
        "DEFAULT_USER_ROLE": request.app.state.config.DEFAULT_USER_ROLE,
        "JWT_EXPIRES_IN": request.app.state.config.JWT_EXPIRES_IN,
        "PENDING_USER_OVERLAY_TITLE": request.app.state.config.PENDING_USER_OVERLAY_TITLE,
        "PENDING_USER_OVERLAY_CONTENT": request.app.state.config.PENDING_USER_OVERLAY_CONTENT,
    }
