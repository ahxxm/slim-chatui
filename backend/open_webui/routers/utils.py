import os

import logging

from open_webui.config import ENABLE_ADMIN_EXPORT
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.background import BackgroundTask
from starlette.responses import FileResponse


from open_webui.utils.misc import get_gravatar_url
from open_webui.utils.auth import get_admin_user, get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gravatar")
async def get_gravatar(email: str, user=Depends(get_verified_user)):
    return get_gravatar_url(email)


@router.get("/db/download")
async def download_db(user=Depends(get_admin_user)):
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    from open_webui.internal.db import backup_db

    backup_path = backup_db()
    return FileResponse(
        backup_path,
        media_type="application/octet-stream",
        filename="webui.db",
        background=BackgroundTask(os.unlink, backup_path),
    )
