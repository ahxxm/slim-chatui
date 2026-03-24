"""Chat middleware: payload preparation, response handling, background tasks.

Orchestration layer — wires DB, events, and HTTP to the pure stream
processors in response.py.
"""

import logging
import asyncio
import json
import re
from typing import Any

from fastapi import Request
from starlette.responses import StreamingResponse, JSONResponse

from open_webui.models.chats import Chats
from open_webui.models.folders import Folders
from open_webui.socket.main import get_event_emitter
from open_webui.routers.tasks import generate_title, generate_follow_ups
from open_webui.utils.files import (
    get_image_base64_from_url,
    get_image_url_from_base64,
)
from open_webui.utils.misc import (
    get_message_list,
    get_last_user_message,
    get_last_user_message_item,
    get_last_assistant_message,
    get_system_message,
    convert_output_to_messages,
)
from open_webui.utils.payload import (
    apply_system_prompt_to_body,
    DeltaBatcher,
    EventEmitter,
)
from open_webui.utils.response import (
    normalize_usage,
    parse_task_json,
    serialize_output,
    make_message_item,
    finalize_output,
    handle_responses_streaming_event,
    apply_completions_delta,
    parse_sse_lines,
    OutputList,
)
from open_webui.env import CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE
from open_webui.constants import TASKS

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def get_image_urls(
    delta_images: Any,
    request: Request,
    metadata: dict[str, Any],
    user: Any,
) -> list[str]:
    if not isinstance(delta_images, list):
        return []
    image_urls: list[str] = []
    for img in delta_images:
        if not isinstance(img, dict) or img.get("type") != "image_url":
            continue
        url = img.get("image_url", {}).get("url")
        if not url:
            continue
        if url.startswith("data:image/png;base64"):
            url = get_image_url_from_base64(request, url, metadata, user)
        image_urls.append(url)
    return image_urls


async def convert_url_images_to_base64(
    form_data: dict[str, Any],
) -> dict[str, Any]:
    for message in form_data.get("messages", []):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        new_content: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "image_url":
                new_content.append(item)
                continue
            image_url = item.get("image_url", {}).get("url", "")
            if image_url.startswith("data:image/"):
                new_content.append(item)
                continue
            try:
                base64_data = await asyncio.to_thread(
                    get_image_base64_from_url, image_url
                )
                new_content.append(
                    {"type": "image_url", "image_url": {"url": base64_data}}
                )
            except Exception as e:
                log.debug(f"Error converting image URL to base64: {e}")
                new_content.append(item)
        message["content"] = new_content
    return form_data


def _normalize_error(error: Any) -> str | dict[str, Any]:
    if isinstance(error, dict):
        return error.get("detail", error)
    return str(error)


def _extract_completion_content(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices", [])
    if not choices:
        return ""
    return choices[0].get("message", {}).get("content", "") or ""


def load_messages_from_db(chat_id: str, message_id: str) -> list[dict[str, Any]] | None:
    """Load message chain from DB, keeping only LLM-relevant fields."""
    messages_map = Chats.get_messages_map_by_chat_id(chat_id)
    if not messages_map:
        return None
    db_messages = get_message_list(messages_map, message_id)
    if not db_messages:
        return None
    return [
        {k: v for k, v in msg.items() if k in ("role", "content", "output", "files")}
        for msg in db_messages
    ]


def process_messages_with_output(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert assistant messages with 'output' to OpenAI-format tool calls."""
    processed: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "assistant" and message.get("output"):
            output_messages = convert_output_to_messages(message["output"])
            if output_messages:
                processed.extend(output_messages)
                continue
        processed.append({k: v for k, v in message.items() if k != "output"})
    return processed


# ---------------------------------------------------------------------------
# Payload processing
# ---------------------------------------------------------------------------


def _inject_image_files(messages: list[dict[str, Any]]) -> None:
    """Inline image files into message content as image_url parts (mirrors frontend logic)."""
    for message in messages:
        image_files = [
            f
            for f in message.get("files", [])
            if f.get("type") == "image"
            or (f.get("content_type") or "").startswith("image/")
        ]
        if message.get("role") == "user" and image_files:
            text_content = message.get("content", "")
            if isinstance(text_content, str):
                message["content"] = [
                    {"type": "text", "text": text_content},
                    *[
                        {"type": "image_url", "image_url": {"url": f["url"]}}
                        for f in image_files
                        if f.get("url")
                    ],
                ]
        message.pop("files", None)


def _expand_folder_files(
    files: list[dict[str, Any]], user: Any
) -> list[dict[str, Any]]:
    """Expand folder entries into their contained files."""
    expanded = list(files)
    for file_item in files:
        if file_item.get("type", "file") != "folder":
            continue
        folder_id = file_item.get("id")
        if not folder_id:
            continue
        folder = Folders.get_folder_by_id_and_user_id(folder_id, user.id)
        if folder and folder.data and "files" in folder.data:
            expanded = [f for f in expanded if f.get("id") != folder_id]
            expanded.extend(folder.data["files"])
    return expanded


async def process_chat_payload(
    request: Request,
    form_data: dict[str, Any],
    user: Any,
    metadata: dict[str, Any],
    model: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    # Non-streaming chat is not supported; tasks.py sets stream=False for its own calls
    form_data.setdefault("stream", True)
    log.debug(f"form_data: {form_data}")

    # Load messages from DB when available — DB preserves structured 'output' items
    # which the frontend strips, causing tool calls to be merged into content.
    chat_id = metadata.get("chat_id")
    parent_message_id = metadata.get("parent_message_id")

    if chat_id and parent_message_id and not chat_id.startswith("local:"):
        db_messages = load_messages_from_db(chat_id, parent_message_id)
        if db_messages:
            system_message = get_system_message(form_data.get("messages", []))
            form_data["messages"] = (
                [system_message, *db_messages] if system_message else db_messages
            )
            _inject_image_files(form_data["messages"])

    form_data["messages"] = process_messages_with_output(form_data.get("messages", []))
    form_data = await convert_url_images_to_base64(form_data)

    # Folder "Project" handling
    # Uses lightweight column query — only fetches folder_id, not the full chat JSON blob
    if chat_id and user:
        folder_id = Chats.get_chat_folder_id(chat_id, user.id)
        if folder_id:
            folder = Folders.get_folder_by_id_and_user_id(folder_id, user.id)
            if folder and folder.data:
                if "system_prompt" in folder.data:
                    form_data = apply_system_prompt_to_body(
                        folder.data["system_prompt"], form_data
                    )
                if "files" in folder.data:
                    form_data["files"] = [
                        *folder.data["files"],
                        *form_data.get("files", []),
                    ]

    form_data.pop("variables", None)
    form_data.pop("features", None)
    files = form_data.pop("files", None)

    if files:
        files = _expand_folder_files(files, user)
        files = list({json.dumps(f, sort_keys=True): f for f in files}.values())

    metadata = {**metadata, "files": files}
    form_data["metadata"] = metadata
    return form_data, metadata


# ---------------------------------------------------------------------------
# Context / response helpers
# ---------------------------------------------------------------------------


def get_event_emitter_or_none(
    metadata: dict[str, Any],
) -> EventEmitter | None:
    required = ("session_id", "chat_id", "message_id")
    if all(metadata.get(k) for k in required):
        return get_event_emitter(metadata)
    return None


def build_chat_response_context(
    request: Request,
    form_data: dict[str, Any],
    user: Any,
    model: Any,
    metadata: dict[str, Any],
    tasks: dict[str, bool],
) -> dict[str, Any]:
    return {
        "request": request,
        "form_data": form_data,
        "user": user,
        "model": model,
        "metadata": metadata,
        "tasks": tasks,
        "event_emitter": get_event_emitter_or_none(metadata),
    }


def get_response_data(
    response: Any,
) -> tuple[Any, dict[str, Any] | None]:
    if isinstance(response, list) and len(response) == 1:  # #17213
        response = response[0]

    if isinstance(response, JSONResponse):
        if isinstance(response.body, bytes):
            try:
                return response, json.loads(response.body.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                return response, {"error": {"detail": "Invalid JSON response"}}
        return response, response
    if isinstance(response, dict):
        return response, response
    return response, None


def build_response_object(response: Any, response_data: dict[str, Any]) -> Any:
    if isinstance(response, dict):
        return response_data
    if isinstance(response, JSONResponse):
        return JSONResponse(
            content=response_data,
            headers=response.headers,
            status_code=response.status_code,
        )
    return response


# ---------------------------------------------------------------------------
# Streaming-handler helpers
# ---------------------------------------------------------------------------


def _log_chunk(data: dict[str, Any]) -> None:
    if not log.isEnabledFor(logging.DEBUG):
        return
    chunk_type = data.get("type", "") if isinstance(data, dict) else type(data).__name__
    extra = ""
    if chunk_type == "response.output_text.delta":
        extra = f" text={data.get('text', '')[:80]!r}"
    elif chunk_type == "response.output_text.done":
        extra = f" text={data.get('text', '<MISSING>')[:80]!r}"
    elif chunk_type in ("response.output_item.added", "response.output_item.done"):
        item = data.get("item", {})
        extra = f" item.type={item.get('type')} item.role={item.get('role')}"
    log.debug("[stream] %s%s", chunk_type, extra)


async def _emit_annotations(delta: dict[str, Any], event_emitter: EventEmitter) -> None:
    for annotation in delta.get("annotations") or []:
        if annotation.get("type") != "url_citation" or "url_citation" not in annotation:
            continue
        url_citation = annotation["url_citation"]
        url = url_citation.get("url", "")
        title = url_citation.get("title", url)
        await event_emitter(
            {
                "type": "source",
                "data": {
                    "source": {"name": title, "url": url},
                    "document": [title],
                    "metadata": [{"source": url, "name": title}],
                },
            }
        )


async def _emit_images(
    delta: dict[str, Any],
    request: Request,
    metadata: dict[str, Any],
    user: Any,
    event_emitter: EventEmitter,
) -> None:
    image_urls = get_image_urls(delta.get("images", []), request, metadata, user)
    if not image_urls:
        return
    message_files = Chats.add_message_files_by_id_and_message_id(
        metadata["chat_id"],
        metadata["message_id"],
        [{"type": "image", "url": url} for url in image_urls],
    )
    await event_emitter({"type": "files", "data": {"files": message_files}})


def _initial_content(message: dict[str, Any] | None, form_data: dict[str, Any]) -> str:
    if message:
        return message.get("content", "")
    messages = form_data.get("messages", [])
    if messages and messages[-1].get("role") == "assistant":
        return get_last_assistant_message(messages) or ""
    return ""


def _initial_output(message: dict[str, Any] | None, content: str) -> OutputList:
    if message and message.get("output"):
        return message["output"]
    if content:
        return [make_message_item(content, "in_progress")]
    return []


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------


def _strip_messages_for_tasks(
    messages_map: dict[str, Any], metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    """Strip details tags and images for task generation prompts."""
    message_list = get_message_list(messages_map, metadata["message_id"])
    stripped: list[dict[str, Any]] = []
    for msg in message_list:
        content = msg.get("content", "")
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    content = item["text"]
                    break
        if isinstance(content, str):
            content = re.sub(
                r"<details\b[^>]*>.*?<\/details>|!\[.*?\]\(.*?\)",
                "",
                content,
                flags=re.S | re.I,
            ).strip()
        stripped.append(
            {**msg, "role": msg.get("role", "assistant"), "content": content}
        )
    return stripped


async def _generate_follow_ups(
    request: Request,
    message: dict[str, Any],
    messages: list[dict[str, Any]],
    metadata: dict[str, Any],
    user: Any,
    event_emitter: EventEmitter,
    is_ephemeral: bool,
) -> None:
    try:
        log.debug(
            "[follow-up] calling generate_follow_ups for model=%s", message["model"]
        )
        res = await generate_follow_ups(
            request,
            {
                "model": message["model"],
                "messages": messages,
                "message_id": metadata["message_id"],
                "chat_id": metadata["chat_id"],
            },
            user,
        )
        log.debug("[follow-up] res type=%s, res=%s", type(res).__name__, res)
        follow_ups = parse_task_json(res, "follow_ups", [])
        log.debug("[follow-up] parsed follow_ups=%s", follow_ups)
        if follow_ups:
            await event_emitter(
                {
                    "type": "chat:message:follow_ups",
                    "data": {"follow_ups": follow_ups},
                }
            )
            if not is_ephemeral:
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {"followUps": follow_ups},
                )
    except Exception as e:
        log.error(f"follow-up generation failed: {e}", exc_info=True)


async def _generate_title(
    request: Request,
    message: dict[str, Any],
    messages: list[dict[str, Any]],
    metadata: dict[str, Any],
    user: Any,
    event_emitter: EventEmitter,
) -> None:
    try:
        res = await generate_title(
            request,
            {
                "model": message["model"],
                "messages": messages,
                "chat_id": metadata["chat_id"],
            },
            user,
        )
        title = res.get("title", "")
    except Exception as e:
        log.error(f"title generation failed: {e}")
        title = ""

    if not title:
        user_message = get_last_user_message(messages) or ""
        title = user_message[:100] or "New Chat"

    Chats.update_chat_title_by_id(metadata["chat_id"], title)
    await event_emitter({"type": "chat:title", "data": title})


async def background_tasks_handler(ctx: dict[str, Any]) -> None:
    request: Request = ctx["request"]
    form_data: dict[str, Any] = ctx["form_data"]
    user = ctx["user"]
    metadata: dict[str, Any] = ctx["metadata"]
    tasks: dict[str, bool] = ctx["tasks"]
    event_emitter: EventEmitter = ctx["event_emitter"]

    is_ephemeral = metadata.get("chat_id", "").startswith("local:")

    if not is_ephemeral and "chat_id" in metadata:
        messages_map = Chats.get_messages_map_by_chat_id(metadata["chat_id"])
        message = messages_map.get(metadata["message_id"]) if messages_map else None
        messages = (
            _strip_messages_for_tasks(messages_map, metadata) if messages_map else []
        )
    else:
        message = get_last_user_message_item(form_data.get("messages", []))
        messages = form_data.get("messages", [])
        if message:
            message["model"] = form_data.get("model")

    if not (message and "model" in message and tasks and messages):
        return

    async with asyncio.TaskGroup() as tg:
        if tasks.get(TASKS.FOLLOW_UP_GENERATION):
            tg.create_task(
                _generate_follow_ups(
                    request,
                    message,
                    messages,
                    metadata,
                    user,
                    event_emitter,
                    is_ephemeral,
                )
            )
        if not is_ephemeral and tasks.get(TASKS.TITLE_GENERATION):
            tg.create_task(
                _generate_title(
                    request, message, messages, metadata, user, event_emitter
                )
            )


# ---------------------------------------------------------------------------
# Non-streaming response handler
# ---------------------------------------------------------------------------


async def non_streaming_chat_response_handler(
    response: Any, ctx: dict[str, Any]
) -> Any:
    metadata: dict[str, Any] = ctx["metadata"]
    event_emitter: EventEmitter = ctx["event_emitter"]

    response, response_data = get_response_data(response)
    if response_data is None:
        return response

    if "error" in response_data:
        error = _normalize_error(response_data["error"])
        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {"error": {"content": error}},
        )
        if isinstance(error, (str, dict)):
            await event_emitter(
                {
                    "type": "chat:message:error",
                    "data": {"error": {"content": error}},
                }
            )

    if "selected_model_id" in response_data:
        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {"selectedModelId": response_data["selected_model_id"]},
        )

    content = _extract_completion_content(response_data)
    if content:
        await event_emitter({"type": "chat:completion", "data": response_data})

        response_output = response_data.get("output") or [
            make_message_item(content, "completed")
        ]
        title = Chats.get_chat_title_by_id(metadata["chat_id"])

        await event_emitter(
            {
                "type": "chat:completion",
                "data": {
                    "done": True,
                    "content": content,
                    "output": response_output,
                    "title": title,
                },
            }
        )

        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {
                "role": "assistant",
                "content": content,
                "output": response_output,
            },
        )

        await background_tasks_handler(ctx)

    return build_response_object(response, response_data)


# ---------------------------------------------------------------------------
# Streaming response handler (flat — no nested closures)
# ---------------------------------------------------------------------------


async def streaming_chat_response_handler(
    response: StreamingResponse, ctx: dict[str, Any]
) -> None:
    event_emitter: EventEmitter = ctx["event_emitter"]
    metadata: dict[str, Any] = ctx["metadata"]
    form_data: dict[str, Any] = ctx["form_data"]
    request: Request = ctx["request"]
    user = ctx["user"]

    # Initialize output state
    message = Chats.get_message_by_id_and_message_id(
        metadata["chat_id"], metadata["message_id"]
    )
    content = _initial_content(message, form_data)
    output = _initial_output(message, content)
    usage: dict[str, Any] | None = None

    batcher = DeltaBatcher(event_emitter, CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE)

    try:
        async for data in parse_sse_lines(response.body_iterator):
            _log_chunk(data)

            # Custom event passthrough
            if "event" in data:
                await event_emitter(data.get("event", {}))

            # Model selection
            if "selected_model_id" in data:
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {"selectedModelId": data["selected_model_id"]},
                )
                await batcher.emit(data, immediate=True)
                continue

            # --- Responses API events ---
            if data.get("type", "").startswith("response."):
                output, response_metadata = handle_responses_streaming_event(
                    data, output
                )

                if (
                    data.get("type") == "response.output_item.done"
                    and data.get("item", {}).get("type") == "web_search_call"
                ):
                    log.debug("[stream] web_search_call done: %s", data.get("item"))

                processed = {
                    "output": output,
                    "content": serialize_output(output),
                }
                if response_metadata:
                    processed.update(response_metadata)
                await batcher.emit(processed, immediate=bool(response_metadata))
                continue

            # --- Chat Completions events ---
            choices = data.get("choices", [])

            raw_usage = data.get("usage") or {}
            if raw_usage:
                usage = normalize_usage(raw_usage)
                await batcher.emit({"usage": usage}, immediate=True)

            if not choices:
                error = data.get("error")
                if error:
                    await batcher.emit({"error": error}, immediate=True)
                continue

            delta = choices[0].get("delta", {})

            # Side effects: annotations, images
            await _emit_annotations(delta, event_emitter)
            await _emit_images(delta, request, metadata, user, event_emitter)

            # State update
            output, content = apply_completions_delta(delta, output, content)

            await batcher.emit(
                {"content": serialize_output(output)}, immediate=not delta
            )

        # Stream fully consumed
        await batcher.flush()

        if response.background is not None:
            await response.background()

        output = finalize_output(output)

        log.debug(
            "[stream] post-handler: content length=%d, output=%s, serialized=%s",
            len(content),
            output,
            serialize_output(output)[:200],
        )

        title = Chats.get_chat_title_by_id(metadata["chat_id"])
        done_data = {
            "done": True,
            "content": serialize_output(output),
            "output": output,
            "title": title,
        }

        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {
                "content": serialize_output(output),
                "output": output,
                **({"usage": usage} if usage else {}),
            },
        )

        # Responses API emits done:True in-loop on response.completed
        # (the only signal if the task is cancelled mid-stream).
        # This second done:True carries the post-processed output
        # (stripped whitespace, closed reasoning blocks, completed statuses).
        await event_emitter({"type": "chat:completion", "data": done_data})
        await background_tasks_handler(ctx)

    except asyncio.CancelledError:
        log.warning("Task was cancelled!")
        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {"content": serialize_output(output), "output": output},
        )
        if response.background is not None:
            await response.background()
        raise


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def process_chat_response(response: Any, ctx: dict[str, Any]) -> Any:
    if not ctx["event_emitter"]:
        if isinstance(response, StreamingResponse):
            return StreamingResponse(
                response.body_iterator,
                headers=dict(response.headers),
                background=response.background,
            )
        _, response_data = get_response_data(response)
        return response_data if isinstance(response, dict) else response

    if not isinstance(response, StreamingResponse):
        return await non_streaming_chat_response_handler(response, ctx)

    if not any(
        ct in response.headers.get("Content-Type", "")
        for ct in ("text/event-stream", "application/x-ndjson")
    ):
        return response

    return await streaming_chat_response_handler(response, ctx)
