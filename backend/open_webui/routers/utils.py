import os

import logging

from fastapi import APIRouter, Depends
from starlette.background import BackgroundTask
from starlette.responses import FileResponse


from open_webui.utils.misc import get_gravatar_url
from open_webui.utils.auth import get_admin_user, get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gravatar")
def get_gravatar(email: str, user=Depends(get_verified_user)):
    return get_gravatar_url(email)


@router.get("/db/download")
def download_db(user=Depends(get_admin_user)):
    from open_webui.internal.db import backup_db

    backup_path = backup_db()
    return FileResponse(
        backup_path,
        media_type="application/octet-stream",
        filename="webui.db",
        background=BackgroundTask(os.unlink, backup_path),
    )
