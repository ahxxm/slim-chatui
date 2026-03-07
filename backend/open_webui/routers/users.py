import logging
from typing import Optional
from sqlalchemy.orm import Session


from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from open_webui.models.auths import Auths

from open_webui.models.chats import Chats
from open_webui.models.users import (
    UserModel,
    UserModelResponse,
    UserListResponse,
    UserInfoResponse,
    UserInfoListResponse,
    Users,
    UserSettings,
    UserUpdateForm,
)

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import STATIC_DIR
from open_webui.internal.db import get_session


from open_webui.utils.auth import (
    get_admin_user,
    get_password_hash,
    get_verified_user,
    validate_password,
)

log = logging.getLogger(__name__)

router = APIRouter()


############################
# GetUsers
############################


PAGE_ITEM_COUNT = 30


@router.get("/", response_model=UserListResponse)
async def get_users(
    query: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    page: Optional[int] = 1,
    user=Depends(get_admin_user),
):
    limit = PAGE_ITEM_COUNT

    page = max(1, page)
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    return Users.get_users(filter=filter, skip=skip, limit=limit)


@router.get("/all", response_model=UserInfoListResponse)
async def get_all_users(
    user=Depends(get_admin_user),
):
    return Users.get_users()


@router.get("/search", response_model=UserInfoListResponse)
async def search_users(
    query: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    page: Optional[int] = 1,
    user=Depends(get_verified_user),
):
    limit = PAGE_ITEM_COUNT

    page = max(1, page)
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    return Users.get_users(filter=filter, skip=skip, limit=limit)


############################
# GetUserSettingsBySessionUser
############################


@router.get("/user/settings", response_model=Optional[UserSettings])
async def get_user_settings_by_session_user(
    user=Depends(get_verified_user),
):
    user = Users.get_user_by_id(user.id)
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserSettingsBySessionUser
############################


@router.post("/user/settings/update", response_model=UserSettings)
async def update_user_settings_by_session_user(
    request: Request,
    form_data: UserSettings,
    user=Depends(get_verified_user),
):
    updated_user_settings = form_data.model_dump()
    user = Users.update_user_settings_by_id(user.id, updated_user_settings)
    if user:
        return user.settings
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserById
############################


@router.get("/{user_id}", response_model=UserModelResponse)
async def get_user_by_id(user_id: str, user=Depends(get_admin_user)):
    # Check if user_id is a shared chat
    # If it is, get the user_id from the chat
    if user_id.startswith("shared-"):
        chat_id = user_id.replace("shared-", "")
        chat = Chats.get_chat_by_id(chat_id)
        if chat:
            user_id = chat.user_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.USER_NOT_FOUND,
            )

    user = Users.get_user_by_id(user_id)
    if user:
        return user
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


@router.get("/{user_id}/info", response_model=UserInfoResponse)
async def get_user_info_by_id(user_id: str, user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user_id)
    if user:
        return UserInfoResponse(**user.model_dump())
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# GetUserProfileImageById
############################


@router.get("/{user_id}/profile/image")
def get_user_profile_image_by_id(user_id: str, user=Depends(get_verified_user)):
    user = Users.get_user_by_id(user_id)
    if user:
        return FileResponse(f"{STATIC_DIR}/user.png")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.USER_NOT_FOUND,
        )


############################
# UpdateUserById
############################


@router.post("/{user_id}/update", response_model=Optional[UserModel])
async def update_user_by_id(
    user_id: str,
    form_data: UserUpdateForm,
    session_user=Depends(get_admin_user),
    db: Session = Depends(get_session),
):
    # Prevent modification of the primary admin user by other admins
    try:
        first_user = Users.get_first_user(db=db)
        if first_user:
            if user_id == first_user.id:
                if session_user.id != user_id:
                    # If the user trying to update is the primary admin, and they are not the primary admin themselves
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
                    )

                if form_data.role != "admin":
                    # If the primary admin is trying to change their own role, prevent it
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
                    )

    except Exception as e:
        log.error(f"Error checking primary admin status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify primary admin status.",
        )

    user = Users.get_user_by_id(user_id, db=db)

    if user:
        if form_data.email.lower() != user.email:
            email_user = Users.get_user_by_email(form_data.email.lower(), db=db)
            if email_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.EMAIL_TAKEN,
                )

        if form_data.password:
            try:
                validate_password(form_data.password)
            except Exception as e:
                raise HTTPException(400, detail=str(e))

            hashed = get_password_hash(form_data.password)
            Auths.update_user_password_by_id(user_id, hashed, db=db)

        Auths.update_email_by_id(user_id, form_data.email.lower(), db=db)
        updated_user = Users.update_user_by_id(
            user_id,
            {
                "role": form_data.role,
                "name": form_data.name,
                "email": form_data.email.lower(),
            },
            db=db,
        )

        if updated_user:
            return updated_user

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=ERROR_MESSAGES.USER_NOT_FOUND,
    )


############################
# DeleteUserById
############################


@router.delete("/{user_id}", response_model=bool)
async def delete_user_by_id(user_id: str, user=Depends(get_admin_user)):
    # Prevent deletion of the primary admin user
    try:
        first_user = Users.get_first_user()
        if first_user and user_id == first_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ERROR_MESSAGES.ACTION_PROHIBITED,
            )
    except Exception as e:
        log.error(f"Error checking primary admin status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify primary admin status.",
        )

    if user.id != user_id:
        result = Auths.delete_auth_by_id(user_id)

        if result:
            return True

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DELETE_USER_ERROR,
        )

    # Prevent self-deletion
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.ACTION_PROHIBITED,
    )
