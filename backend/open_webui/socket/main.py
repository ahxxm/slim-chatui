import asyncio

import socketio
import logging
import sys
import time

from open_webui.models.users import Users
from open_webui.models.chats import Chats

from open_webui.config import (
    CORS_ALLOW_ORIGIN,
)

from open_webui.env import (
    ENABLE_WEBSOCKET_SUPPORT,
    WEBSOCKET_SERVER_PING_TIMEOUT,
    WEBSOCKET_SERVER_PING_INTERVAL,
    WEBSOCKET_SERVER_LOGGING,
    WEBSOCKET_SERVER_ENGINEIO_LOGGING,
)
from open_webui.utils.auth import decode_token


from open_webui.env import (
    GLOBAL_LOG_LEVEL,
)

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


# Configure CORS for Socket.IO
SOCKETIO_CORS_ORIGINS = "*" if CORS_ALLOW_ORIGIN == ["*"] else CORS_ALLOW_ORIGIN

sio = socketio.AsyncServer(
    cors_allowed_origins=SOCKETIO_CORS_ORIGINS,
    async_mode="asgi",
    transports=(["websocket"] if ENABLE_WEBSOCKET_SUPPORT else ["polling"]),
    allow_upgrades=ENABLE_WEBSOCKET_SUPPORT,
    always_connect=True,
    logger=WEBSOCKET_SERVER_LOGGING,
    ping_interval=WEBSOCKET_SERVER_PING_INTERVAL,
    ping_timeout=WEBSOCKET_SERVER_PING_TIMEOUT,
    engineio_logger=WEBSOCKET_SERVER_ENGINEIO_LOGGING,
)


SESSION_POOL_TIMEOUT = 120  # seconds without heartbeat before session is reaped

MODELS = {}
SESSION_POOL = {}


async def periodic_session_pool_cleanup():
    while True:
        now = int(time.time())
        for sid in list(SESSION_POOL.keys()):
            entry = SESSION_POOL.get(sid)
            if entry and now - entry.get("last_seen_at", 0) > SESSION_POOL_TIMEOUT:
                log.warning(f"Reaping orphaned session {sid} (user {entry.get('id')})")
                del SESSION_POOL[sid]
        await asyncio.sleep(SESSION_POOL_TIMEOUT)


app = socketio.ASGIApp(
    sio,
    socketio_path="/ws/socket.io",
)


def get_user_id_from_session_pool(sid):
    user = SESSION_POOL.get(sid)
    if user:
        return user["id"]
    return None


def get_session_ids_from_room(room):
    """Get all session IDs from a specific room."""
    active_session_ids = sio.manager.get_participants(
        namespace="/",
        room=room,
    )
    return [session_id[0] for session_id in active_session_ids]


async def emit_to_users(event: str, data: dict, user_ids: list[str]):
    """
    Send a message to specific users using their user:{id} rooms.

    Args:
        event (str): The event name to emit.
        data (dict): The payload/data to send.
        user_ids (list[str]): The target users' IDs.
    """
    try:
        for user_id in user_ids:
            await sio.emit(event, data, room=f"user:{user_id}")
    except Exception as e:
        log.debug(f"Failed to emit event {event} to users {user_ids}: {e}")


async def enter_room_for_users(room: str, user_ids: list[str]):
    """
    Make all sessions of a user join a specific room.
    Args:
        room (str): The room to join.
        user_ids (list[str]): The target user's IDs.
    """
    try:
        for user_id in user_ids:
            session_ids = get_session_ids_from_room(f"user:{user_id}")
            for sid in session_ids:
                await sio.enter_room(sid, room)
    except Exception as e:
        log.debug(f"Failed to make users {user_ids} join room {room}: {e}")



@sio.event
async def connect(sid, environ, auth):
    user = None
    if auth and "token" in auth:
        data = decode_token(auth["token"])

        if data is not None and "id" in data:
            user = Users.get_user_by_id(data["id"])

        if user:
            SESSION_POOL[sid] = {
                **user.model_dump(
                    exclude=[
                        "profile_image_url",
                        "profile_banner_image_url",
                        "date_of_birth",
                        "bio",
                        "gender",
                    ]
                ),
                "last_seen_at": int(time.time()),
            }
            await sio.enter_room(sid, f"user:{user.id}")


@sio.on("user-join")
async def user_join(sid, data):

    auth = data["auth"] if "auth" in data else None
    if not auth or "token" not in auth:
        return

    data = decode_token(auth["token"])
    if data is None or "id" not in data:
        return

    user = Users.get_user_by_id(data["id"])
    if not user:
        return

    SESSION_POOL[sid] = {
        **user.model_dump(
            exclude=[
                "profile_image_url",
                "profile_banner_image_url",
                "date_of_birth",
                "bio",
                "gender",
            ]
        ),
        "last_seen_at": int(time.time()),
    }

    await sio.enter_room(sid, f"user:{user.id}")

    return {"id": user.id, "name": user.name}


@sio.on("heartbeat")
async def heartbeat(sid, data):
    user = SESSION_POOL.get(sid)
    if user:
        SESSION_POOL[sid] = {**user, "last_seen_at": int(time.time())}


@sio.event
async def disconnect(sid):
    if sid in SESSION_POOL:
        del SESSION_POOL[sid]


def get_event_emitter(request_info, update_db=True):
    async def __event_emitter__(event_data):
        user_id = request_info["user_id"]
        chat_id = request_info["chat_id"]
        message_id = request_info["message_id"]

        await sio.emit(
            "events",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "data": event_data,
            },
            room=f"user:{user_id}",
        )
        if (
            update_db
            and message_id
            and not request_info.get("chat_id", "").startswith("local:")
        ):

            if "type" in event_data and event_data["type"] == "status":
                Chats.add_message_status_to_chat_by_id_and_message_id(
                    request_info["chat_id"],
                    request_info["message_id"],
                    event_data.get("data", {}),
                )

            if "type" in event_data and event_data["type"] == "message":
                message = Chats.get_message_by_id_and_message_id(
                    request_info["chat_id"],
                    request_info["message_id"],
                )

                if message:
                    content = message.get("content", "")
                    content += event_data.get("data", {}).get("content", "")

                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        request_info["chat_id"],
                        request_info["message_id"],
                        {
                            "content": content,
                        },
                    )

            if "type" in event_data and event_data["type"] == "replace":
                content = event_data.get("data", {}).get("content", "")

                Chats.upsert_message_to_chat_by_id_and_message_id(
                    request_info["chat_id"],
                    request_info["message_id"],
                    {
                        "content": content,
                    },
                )

            if "type" in event_data and event_data["type"] == "embeds":
                message = Chats.get_message_by_id_and_message_id(
                    request_info["chat_id"],
                    request_info["message_id"],
                )

                embeds = event_data.get("data", {}).get("embeds", [])
                embeds.extend(message.get("embeds", []))

                Chats.upsert_message_to_chat_by_id_and_message_id(
                    request_info["chat_id"],
                    request_info["message_id"],
                    {
                        "embeds": embeds,
                    },
                )

            if "type" in event_data and event_data["type"] == "files":
                message = Chats.get_message_by_id_and_message_id(
                    request_info["chat_id"],
                    request_info["message_id"],
                )

                files = event_data.get("data", {}).get("files", [])
                files.extend(message.get("files", []))

                Chats.upsert_message_to_chat_by_id_and_message_id(
                    request_info["chat_id"],
                    request_info["message_id"],
                    {
                        "files": files,
                    },
                )

            if event_data.get("type") in ["source", "citation"]:
                data = event_data.get("data", {})
                if data.get("type") == None:
                    message = Chats.get_message_by_id_and_message_id(
                        request_info["chat_id"],
                        request_info["message_id"],
                    )

                    sources = message.get("sources", [])
                    sources.append(data)

                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        request_info["chat_id"],
                        request_info["message_id"],
                        {
                            "sources": sources,
                        },
                    )

    if (
        "user_id" in request_info
        and "chat_id" in request_info
        and "message_id" in request_info
    ):
        return __event_emitter__
    else:
        return None


def get_event_call(request_info):
    async def __event_caller__(event_data):
        response = await sio.call(
            "events",
            {
                "chat_id": request_info.get("chat_id", None),
                "message_id": request_info.get("message_id", None),
                "data": event_data,
            },
            to=request_info["session_id"],
        )
        return response

    if (
        "session_id" in request_info
        and "chat_id" in request_info
        and "message_id" in request_info
    ):
        return __event_caller__
    else:
        return None
