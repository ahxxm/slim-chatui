import logging
from typing import Optional
from pydantic import BaseModel

from open_webui.models.folders import (
    FolderForm,
    FolderUpdateForm,
    FolderModel,
    FolderNameIdResponse,
    Folders,
)
from open_webui.models.chats import Chats
from open_webui.models.files import Files

from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_session
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, Request, status

from open_webui.models.users import UserModel
from open_webui.utils.auth import get_verified_user
from open_webui.utils.route import route_error_handler

log = logging.getLogger(__name__)


router = APIRouter()


def resolve_owned_folder(id: str, user: UserModel = Depends(get_verified_user)) -> FolderModel:
    folder = Folders.get_folder_by_id_and_user_id(id, user.id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return folder


############################
# Get Folders
############################


@router.get("/", response_model=list[FolderNameIdResponse])
def get_folders(
    request: Request,
    user: UserModel = Depends(get_verified_user),
):
    folders = Folders.get_folders_by_user_id(user.id)

    folder_list = []
    for folder in folders:
        if folder.data:
            if "files" in folder.data:
                valid_files = []
                for file in folder.data["files"]:

                    if file.get("type") == "file":
                        if Files.check_access_by_user_id(
                            file.get("id"), user.id, "read"
                        ):
                            valid_files.append(file)
                    else:
                        valid_files.append(file)

                folder.data["files"] = valid_files
                Folders.update_folder_by_id_and_user_id(
                    folder.id, user.id, FolderUpdateForm(data=folder.data)
                )

        folder_list.append(FolderNameIdResponse(**folder.model_dump()))

    return folder_list


############################
# Create Folder
############################


@router.post("/")
@route_error_handler(detail=ERROR_MESSAGES.DEFAULT("Error creating folder"))
def create_folder(
    form_data: FolderForm,
    user: UserModel = Depends(get_verified_user),
):
    folder = Folders.get_folder_by_user_id_and_name(user.id, form_data.name)
    if folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Folder already exists"),
        )

    return Folders.insert_new_folder(user.id, form_data)


############################
# Get Folders By Id
############################


@router.get("/{id}", response_model=Optional[FolderModel])
def get_folder_by_id(folder: FolderModel = Depends(resolve_owned_folder)):
    return folder


############################
# Update Folder Name By Id
############################


@router.post("/{id}/update")
@route_error_handler(detail=ERROR_MESSAGES.DEFAULT("Error updating folder"))
def update_folder_name_by_id(
    form_data: FolderUpdateForm,
    folder: FolderModel = Depends(resolve_owned_folder),
    user: UserModel = Depends(get_verified_user),
):
    if form_data.name is not None:
        existing_folder = Folders.get_folder_by_user_id_and_name(
            user.id, form_data.name
        )
        if existing_folder and existing_folder.id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Folder already exists"),
            )

    return Folders.update_folder_by_id_and_user_id(folder.id, user.id, form_data)


############################
# Update Folder Is Expanded By Id
############################


class FolderIsExpandedForm(BaseModel):
    is_expanded: bool


@router.post("/{id}/update/expanded")
@route_error_handler(detail=ERROR_MESSAGES.DEFAULT("Error updating folder"))
def update_folder_is_expanded_by_id(
    form_data: FolderIsExpandedForm,
    folder: FolderModel = Depends(resolve_owned_folder),
    user: UserModel = Depends(get_verified_user),
):
    return Folders.update_folder_is_expanded_by_id_and_user_id(
        folder.id, user.id, form_data.is_expanded
    )


############################
# Delete Folder By Id
############################


@router.delete("/{id}")
@route_error_handler(detail=ERROR_MESSAGES.DEFAULT("Error deleting folder"))
def delete_folder_by_id(
    delete_contents: Optional[bool] = True,
    folder: FolderModel = Depends(resolve_owned_folder),
    user: UserModel = Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    folder_ids = Folders.delete_folder_by_id_and_user_id(folder.id, user.id, db=db)

    for folder_id in folder_ids:
        if delete_contents:
            Chats.delete_chats_by_user_id_and_folder_id(user.id, folder_id, db=db)
        else:
            Chats.move_chats_by_user_id_and_folder_id(user.id, folder_id, None, db=db)

    return True
