import logging
from typing import Optional


from open_webui.socket.main import get_event_emitter
from open_webui.models.chats import (
    ChatForm,
    ChatImportForm,
    ChatsImportForm,
    ChatResponse,
    Chats,
    ChatTitleIdResponse,
)
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel


from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.route import route_error_handler

log = logging.getLogger(__name__)

router = APIRouter()

############################
# GetChatList
############################


@router.get("/", response_model=list[ChatTitleIdResponse])
@router.get("/list", response_model=list[ChatTitleIdResponse])
@route_error_handler(detail=ERROR_MESSAGES.DEFAULT())
def get_session_user_chat_list(
    user=Depends(get_verified_user),
    page: Optional[int] = None,
    include_pinned: Optional[bool] = False,
    include_folders: Optional[bool] = False,
):
    if page is not None:
        limit = 60
        skip = (page - 1) * limit

        return Chats.get_chat_title_id_list_by_user_id(
            user.id,
            include_folders=include_folders,
            include_pinned=include_pinned,
            skip=skip,
            limit=limit,
        )
    else:
        return Chats.get_chat_title_id_list_by_user_id(
            user.id,
            include_folders=include_folders,
            include_pinned=include_pinned,
        )


@router.delete("/", response_model=bool)
async def delete_all_user_chats(
    user=Depends(get_verified_user),
):

    result = Chats.delete_chats_by_user_id(user.id)
    return result


############################
# GetUserChatList
############################


@router.get("/list/user/{user_id}", response_model=list[ChatTitleIdResponse])
async def get_user_chat_list_by_user_id(
    user_id: str,
    page: Optional[int] = None,
    query: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    user=Depends(get_admin_user),
):
    if page is None:
        page = 1

    limit = 60
    skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    return Chats.get_chat_list_by_user_id(
        user_id, filter=filter, skip=skip, limit=limit
    )


############################
# CreateNewChat
############################


@router.post("/new", response_model=Optional[ChatResponse])
@route_error_handler(detail=ERROR_MESSAGES.DEFAULT())
async def create_new_chat(
    form_data: ChatForm,
    user=Depends(get_verified_user),
):
    chat = Chats.insert_new_chat(user.id, form_data)
    return ChatResponse(**chat.model_dump())


############################
# ImportChats
############################


@router.post("/import", response_model=list[ChatResponse])
@route_error_handler(detail=ERROR_MESSAGES.DEFAULT())
async def import_chats(
    form_data: ChatsImportForm,
    user=Depends(get_verified_user),
):
    return Chats.import_chats(user.id, form_data.chats)


############################
# GetChats
############################


@router.get("/search", response_model=list[ChatTitleIdResponse])
def search_user_chats(
    text: str,
    page: Optional[int] = None,
    user=Depends(get_verified_user),
):
    if page is None:
        page = 1

    limit = 60
    skip = (page - 1) * limit

    chat_list = [
        ChatTitleIdResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_user_id_and_search_text(
            user.id, text, skip=skip, limit=limit
        )
    ]

    return chat_list


############################
# GetChatsByFolderId
############################


@router.get("/folder/{folder_id}", response_model=list[ChatResponse])
async def get_chats_by_folder_id(folder_id: str, user=Depends(get_verified_user)):
    return [
        ChatResponse(**chat.model_dump())
        for chat in Chats.get_chats_by_folder_ids_and_user_id([folder_id], user.id)
    ]


@router.get("/folder/{folder_id}/list")
@route_error_handler(detail=ERROR_MESSAGES.DEFAULT())
async def get_chat_list_by_folder_id(
    folder_id: str,
    page: Optional[int] = 1,
    user=Depends(get_verified_user),
):
    limit = 10
    skip = (page - 1) * limit

    return [
        {"title": chat.title, "id": chat.id, "updated_at": chat.updated_at}
        for chat in Chats.get_chats_by_folder_id_and_user_id(
            folder_id, user.id, skip=skip, limit=limit
        )
    ]


############################
# GetPinnedChats
############################


@router.get("/pinned", response_model=list[ChatTitleIdResponse])
async def get_user_pinned_chats(user=Depends(get_verified_user)):
    return Chats.get_pinned_chats_by_user_id(user.id)


############################
# GetChats
############################


@router.get("/all", response_model=list[ChatResponse])
async def get_user_chats(user=Depends(get_verified_user)):
    result = Chats.get_chats_by_user_id(user.id)
    return [ChatResponse(**chat.model_dump()) for chat in result.items]


############################
# GetAllChatsInDB
############################


@router.get("/all/db", response_model=list[ChatResponse])
async def get_all_user_chats_in_db(
    user=Depends(get_admin_user),
):
    return [ChatResponse(**chat.model_dump()) for chat in Chats.get_chats()]


############################
# GetChatById
############################


@router.get("/{id}", response_model=Optional[ChatResponse])
async def get_chat_by_id(id: str, user=Depends(get_verified_user)):
    if user.role == "admin":
        chat = Chats.get_chat_by_id(id)
    else:
        chat = Chats.get_chat_by_id_and_user_id(id, user.id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.NOT_FOUND
        )

    return ChatResponse(**chat.model_dump())


############################
# UpdateChatById
############################


@router.post("/{id}", response_model=Optional[ChatResponse])
async def update_chat_by_id(
    id: str,
    form_data: ChatForm,
    user=Depends(get_verified_user),
):
    from open_webui.utils.middleware import serialize_output

    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    updated_chat = {**chat.chat, **form_data.chat}
    # Re-serialize content from output for messages that have it,
    # since the frontend may send stale content from intermediate
    # streaming states (e.g. web_search queries only arrive at end)
    for msg in updated_chat.get("history", {}).get("messages", {}).values():
        if msg.get("output"):
            msg["content"] = serialize_output(msg["output"])
    chat = Chats.update_chat_by_id(id, updated_chat)
    return ChatResponse(**chat.model_dump())


############################
# UpdateChatMessageById
############################
class MessageForm(BaseModel):
    content: str


@router.post("/{id}/messages/{message_id}", response_model=Optional[ChatResponse])
async def update_chat_message_by_id(
    id: str,
    message_id: str,
    form_data: MessageForm,
    user=Depends(get_verified_user),
):
    chat = Chats.get_chat_by_id(id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    if chat.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    chat = Chats.upsert_message_to_chat_by_id_and_message_id(
        id,
        message_id,
        {
            "content": form_data.content,
        },
    )

    event_emitter = get_event_emitter(
        {
            "user_id": user.id,
            "chat_id": id,
            "message_id": message_id,
        },
        False,
    )

    if event_emitter:
        await event_emitter(
            {
                "type": "chat:message",
                "data": {
                    "chat_id": id,
                    "message_id": message_id,
                    "content": form_data.content,
                },
            }
        )

    return ChatResponse(**chat.model_dump())


############################
# SendChatMessageEventById
############################
class EventForm(BaseModel):
    type: str
    data: dict


@router.post("/{id}/messages/{message_id}/event", response_model=Optional[bool])
async def send_chat_message_event_by_id(
    id: str,
    message_id: str,
    form_data: EventForm,
    user=Depends(get_verified_user),
):
    chat = Chats.get_chat_by_id(id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    if chat.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    event_emitter = get_event_emitter(
        {
            "user_id": user.id,
            "chat_id": id,
            "message_id": message_id,
        }
    )

    if not event_emitter:
        return False

    await event_emitter(form_data.model_dump())
    return True


############################
# DeleteChatById
############################


@router.delete("/{id}", response_model=bool)
async def delete_chat_by_id(
    id: str,
    user=Depends(get_verified_user),
):
    if user.role == "admin":
        chat = Chats.get_chat_by_id(id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )

        result = Chats.delete_chat_by_id(id)

        return result
    else:
        chat = Chats.get_chat_by_id_and_user_id(id, user.id)
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )

        result = Chats.delete_chat_by_id_and_user_id(id, user.id)
        return result


############################
# GetPinnedStatusById
############################


@router.get("/{id}/pinned", response_model=Optional[bool])
async def get_pinned_status_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )

    return chat.pinned


############################
# PinChatById
############################


@router.post("/{id}/pin", response_model=Optional[ChatResponse])
async def pin_chat_by_id(id: str, user=Depends(get_verified_user)):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )

    return Chats.toggle_chat_pinned_by_id(id)


############################
# CloneChat
############################


class CloneForm(BaseModel):
    title: Optional[str] = None


@router.post("/{id}/clone", response_model=Optional[ChatResponse])
async def clone_chat_by_id(
    form_data: CloneForm,
    id: str,
    user=Depends(get_verified_user),
):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )

    updated_chat = {
        **chat.chat,
        "originalChatId": chat.id,
        "branchPointMessageId": chat.chat["history"]["currentId"],
        "title": form_data.title if form_data.title else f"Clone of {chat.title}",
    }

    cloned = Chats.import_chats(
        user.id,
        [
            ChatImportForm(
                **{
                    "chat": updated_chat,
                    "meta": chat.meta,
                    "pinned": chat.pinned,
                    "folder_id": chat.folder_id,
                }
            )
        ],
    )

    if not cloned:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    return ChatResponse(**cloned[0].model_dump())


############################
# UpdateChatFolderIdById
############################


class ChatFolderIdForm(BaseModel):
    folder_id: Optional[str] = None


@router.post("/{id}/folder", response_model=Optional[ChatResponse])
async def update_chat_folder_id_by_id(
    id: str,
    form_data: ChatFolderIdForm,
    user=Depends(get_verified_user),
):
    chat = Chats.get_chat_by_id_and_user_id(id, user.id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.DEFAULT()
        )

    chat = Chats.update_chat_folder_id_by_id_and_user_id(
        id, user.id, form_data.folder_id
    )
    return ChatResponse(**chat.model_dump())
