"""Chat middleware: payload preparation, stream processing, background tasks."""

import time
import logging
import asyncio
import json
import html
import re
from typing import Any
from collections.abc import AsyncIterator
from uuid import uuid4

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
from open_webui.utils.payload import apply_system_prompt_to_body, DeltaBatcher, EventEmitter
from open_webui.utils.response import normalize_usage
from open_webui.env import CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE
from open_webui.constants import TASKS

log = logging.getLogger(__name__)

# Backward-compat re-exports
from open_webui.utils.response import extract_task_text, parse_task_json  # noqa: F401

OutputList = list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Output item builders
# ---------------------------------------------------------------------------


def output_id(prefix: str) -> str:
    """Generate OR-style ID: prefix + 24-char hex UUID."""
    return f"{prefix}_{uuid4().hex[:24]}"


def make_message_item(text: str, status: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": output_id("msg"),
        "status": status,
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }


def make_reasoning_item(status: str) -> dict[str, Any]:
    return {
        "type": "reasoning",
        "id": output_id("r"),
        "status": status,
        "start_tag": "<think>",
        "end_tag": "</think>",
        "attributes": {"type": "reasoning_content"},
        "content": [],
        "summary": None,
        "started_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Pure output processing
# ---------------------------------------------------------------------------


def serialize_output(output: OutputList) -> str:
    """
    Convert OR-aligned output items to HTML for display.
    For LLM consumption, use convert_output_to_messages() instead.
    """
    parts: list[str] = []

    for idx, item in enumerate(output):
        item_type = item.get("type", "")

        if item_type == "message":
            for content_part in item.get("content", []):
                text = content_part.get("text", "").strip()
                if text:
                    parts.append(text)

        elif item_type == "web_search_call":
            status = item.get("status", "in_progress")
            action = item.get("action", {})

            def _esc(s: str) -> str:
                return s.strip().replace('"', "'")

            query = _esc(action.get("query", ""))
            url = _esc(action.get("url", ""))
            pattern = _esc(action.get("pattern", ""))
            done = "true" if status == "completed" else "false"
            action_type = action.get("type", "")
            attrs = (
                f'type="web_search" done="{done}" action="{action_type}" '
                f'query="{query}" url="{url}" pattern="{pattern}"'
            )
            parts.append(
                f"<details {attrs}>\n"
                "<summary>Searched the web</summary>\n"
                "</details>"
            )

        elif item_type == "reasoning":
            # 'summary' (new structure) or 'content' (legacy/fallback)
            source_list = item.get("summary", []) or item.get("content", [])
            reasoning_parts = [cp.get("text", "") for cp in source_list if "text" in cp]
            reasoning_text = "\n\n".join(reasoning_parts).strip()
            duration = item.get("duration")
            status = item.get("status", "in_progress")
            # If this reasoning item is NOT the last item, render as done
            # (a subsequent item means reasoning is complete)
            is_last_item = idx == len(output) - 1

            display = html.escape(
                "\n".join(
                    (f"> {line}" if not line.startswith(">") else line)
                    for line in reasoning_text.splitlines()
                )
            )

            if status == "completed" or duration is not None or not is_last_item:
                d = round(duration, 1) if duration else 0
                parts.append(
                    f'<details type="reasoning" done="true" duration="{d}">\n'
                    f"<summary>Thought for {d} seconds</summary>\n"
                    f"{display}\n</details>"
                )
            else:
                parts.append(
                    '<details type="reasoning" done="false">\n'
                    "<summary>Thinking\u2026</summary>\n"
                    f"{display}\n</details>"
                )

    return "\n".join(parts).strip()


def deep_merge(target: Any, source: Any) -> Any:
    """Merge source into target: dicts recurse, strings concat, else overwrite."""
    if isinstance(target, dict) and isinstance(source, dict):
        merged = target.copy()
        for k, v in source.items():
            merged[k] = deep_merge(merged[k], v) if k in merged else v
        return merged
    if isinstance(target, str) and isinstance(source, str):
        return target + source
    return source


def close_reasoning_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return a closed copy of a reasoning item. Idempotent."""
    if item.get("ended_at") is not None:
        return item
    now = time.time()
    return {
        **item,
        "ended_at": now,
        "duration": now - item.get("started_at", now),
        "status": "completed",
    }


def finalize_output(output: OutputList) -> OutputList:
    """Post-stream cleanup: strip whitespace, close reasoning, mark completed."""
    if output:
        last = output[-1]
        if last.get("type") == "message":
            content_parts = last.get("content", [])
            if content_parts and content_parts[-1].get("type") == "output_text":
                content_parts[-1]["text"] = content_parts[-1]["text"].strip()
                if not content_parts[-1]["text"]:
                    output.pop()
                    if not output:
                        output.append(make_message_item("", "in_progress"))

        if output and output[-1].get("type") == "reasoning":
            output[-1] = close_reasoning_item(output[-1])

    for item in output:
        if item.get("status") == "in_progress":
            item["status"] = "completed"

    return output


# ---------------------------------------------------------------------------
# Shared: merge delta into a list field's entry at index
# ---------------------------------------------------------------------------


def _merge_delta_into_list(
    item: dict[str, Any],
    field: str,
    index: int,
    key: str,
    delta: Any,
    default_entry: dict[str, Any],
) -> None:
    """Merge a delta value into a list field's entry at the given index.

    Copies the list and the target entry before mutating (the item itself
    is already a shallow copy in every call-site).
    """
    if field not in item:
        item[field] = []
    else:
        item[field] = list(item[field])
    entries = item[field]
    while len(entries) <= index:
        entries.append(dict(default_entry))
    entry = entries[index].copy()
    entries[index] = entry
    current = entry.get(key)
    if current is None:
        current = {} if isinstance(delta, dict) else ""
    entry[key] = deep_merge(current, delta)


# ---------------------------------------------------------------------------
# Responses API stream processing — helpers
# ---------------------------------------------------------------------------


def _replace_output_item_by_id(
    data: dict[str, Any], current_output: OutputList
) -> tuple[OutputList, dict[str, Any] | None]:
    item = data.get("item")
    if not item or not item.get("id"):
        return current_output, None

    new_output = list(current_output)
    for idx, existing in enumerate(new_output):
        if existing.get("id") == item["id"]:
            if "started_at" in existing and "started_at" not in item:
                item = {**item, "started_at": existing["started_at"]}
            new_output[idx] = item
            return new_output, {}
    return current_output, None


def _responses_item_added(
    data: dict[str, Any], current_output: OutputList
) -> tuple[OutputList, dict[str, Any] | None]:
    item = data.get("item", {})
    if not item:
        return current_output, None

    now = time.time()
    new_output = list(current_output)

    # Close the previous reasoning block's duration
    if new_output:
        prev = new_output[-1]
        if (
            prev.get("type") == "reasoning"
            and "started_at" in prev
            and "duration" not in prev
        ):
            new_output[-1] = {**prev, "duration": now - prev["started_at"]}

    if item.get("type") == "reasoning":
        item = {**item, "started_at": now}

    new_output.append(item)
    return new_output, None


def _responses_part_added(
    data: dict[str, Any],
    current_output: OutputList,
    field: str,
    skip_item_type: str | None = None,
) -> tuple[OutputList, dict[str, Any] | None]:
    part = data.get("part", {})
    output_index = data.get("output_index", len(current_output) - 1)

    if not current_output or not (0 <= output_index < len(current_output)):
        return current_output, None

    new_output = list(current_output)
    item = new_output[output_index].copy()
    new_output[output_index] = item

    if skip_item_type and item.get("type") == skip_item_type:
        return current_output, None

    item[field] = [*item.get(field, []), part]
    return new_output, None


# --- delta sub-handlers ---


def _delta_message(
    delta_type: str,
    data: dict[str, Any],
    delta: Any,
    item: dict[str, Any],
    new_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    if delta_type in ("reasoning_text", "reasoning_summary_text"):
        return new_output, None

    key = "text" if delta_type in ("text", "output_text") else delta_type
    _merge_delta_into_list(
        item,
        "content",
        data.get("content_index", 0),
        key,
        delta,
        {"type": "text", "text": ""},
    )
    return new_output, None


def _delta_reasoning(
    delta_type: str,
    data: dict[str, Any],
    delta: Any,
    item: dict[str, Any],
    new_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    if delta_type == "reasoning_summary_text":
        _merge_delta_into_list(
            item,
            "summary",
            data.get("summary_index", 0),
            "text",
            delta,
            {"type": "summary_text", "text": ""},
        )
        return new_output, None

    if delta_type == "reasoning_text":
        _merge_delta_into_list(
            item,
            "content",
            data.get("content_index", 0),
            "text",
            delta,
            {"type": "text", "text": ""},
        )
        return new_output, None

    # text/output_text deltas don't belong on reasoning items
    return new_output, None


def _responses_delta(
    event_type: str,
    data: dict[str, Any],
    current_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    parts = event_type.split(".")
    if len(parts) < 3:
        return current_output, None

    delta_type = parts[1]
    delta = data.get("delta", "")
    output_index = data.get("output_index", len(current_output) - 1)

    if not current_output or not (0 <= output_index < len(current_output)):
        return current_output, None

    new_output = list(current_output)
    item = new_output[output_index].copy()
    new_output[output_index] = item
    item_type = item.get("type", "")

    if delta_type == "function_call_arguments":
        if item_type == "function_call":
            item["arguments"] = item.get("arguments", "") + str(delta)
        return new_output, None

    if item_type == "message":
        return _delta_message(delta_type, data, delta, item, new_output)

    if item_type == "reasoning":
        return _delta_reasoning(delta_type, data, delta, item, new_output)

    # Fallback for other item types
    key = "text" if delta_type in ("text", "output_text") else delta_type
    current_val = item.get(key)
    if current_val is None:
        current_val = {} if isinstance(delta, dict) else ""
    item[key] = deep_merge(current_val, delta)
    return new_output, None


# --- done sub-handlers ---


def _replace_part_in_list(
    data: dict[str, Any],
    current_output: OutputList,
    field: str,
    index_key: str,
) -> tuple[OutputList, dict[str, Any] | None]:
    part = data.get("part")
    output_index = data.get("output_index", len(current_output) - 1)

    if not part or not current_output or not (0 <= output_index < len(current_output)):
        return current_output, None

    new_output = list(current_output)
    item = new_output[output_index].copy()
    new_output[output_index] = item

    if field not in item:
        return current_output, None

    item[field] = list(item[field])
    idx = data.get(index_key, len(item[field]) - 1)
    if 0 <= idx < len(item[field]):
        item[field][idx] = part
        return new_output, {}

    return current_output, None


def _done_generic_field(
    type_name: str,
    data: dict[str, Any],
    current_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    output_index = data.get("output_index", len(current_output) - 1)
    if not current_output or not (0 <= output_index < len(current_output)):
        return current_output, None

    key = type_name
    if type_name in ("text", "output_text", "reasoning_text", "reasoning_summary_text"):
        key = "text"
    elif type_name == "function_call_arguments":
        key = "arguments"

    if key not in data:
        return current_output, None

    final_value = data[key]
    new_output = list(current_output)
    item = new_output[output_index].copy()
    new_output[output_index] = item
    item_type = item.get("type", "")

    if type_name == "function_call_arguments" and item_type == "function_call":
        item["arguments"] = final_value
    elif item_type == "message":
        content_index = data.get("content_index", 0)
        if "content" in item:
            item["content"] = list(item["content"])
            if len(item["content"]) > content_index:
                part = item["content"][content_index].copy()
                item["content"][content_index] = part
                part[key] = final_value
    elif item_type == "reasoning":
        item["status"] = "completed"
    else:
        item[key] = final_value

    return new_output, {}


def _responses_done(
    event_type: str,
    data: dict[str, Any],
    current_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    parts = event_type.split(".")
    if len(parts) < 3:
        return current_output, None

    type_name = parts[1]

    if type_name == "content_part":
        return _replace_part_in_list(data, current_output, "content", "content_index")

    if type_name == "reasoning_summary_part":
        return _replace_part_in_list(data, current_output, "summary", "summary_index")

    # Replace by id, not output_index — index may not match our array
    # if we inserted extra items (e.g. reasoning blocks)
    if type_name == "output_item":
        return _replace_output_item_by_id(data, current_output)

    if type_name in ("completed", "failed"):
        return current_output, None

    # Generic field done (text.done, function_call_arguments.done, etc.)
    return _done_generic_field(type_name, data, current_output)


def _responses_completed(
    data: dict[str, Any], current_output: OutputList
) -> tuple[OutputList, dict[str, Any] | None]:
    response_data = data.get("response", {})
    final_output = response_data.get("output")

    # Carry over per-block timing from streaming state.
    # Match reasoning items by ordinal position (IDs may differ).
    streamed_reasoning = [
        item for item in current_output if item.get("type") == "reasoning"
    ]

    new_output = final_output if final_output is not None else current_output

    now = time.time()
    ordinal = 0
    for item in new_output or []:
        if item.get("type") != "reasoning":
            continue
        if item.get("status") != "completed":
            item["status"] = "completed"
        if "duration" not in item and ordinal < len(streamed_reasoning):
            started = streamed_reasoning[ordinal].get("started_at")
            precomputed = streamed_reasoning[ordinal].get("duration")
            item["duration"] = (
                precomputed
                if precomputed is not None
                else ((now - started) if started else 0)
            )
        ordinal += 1

    return new_output, {"usage": response_data.get("usage"), "done": True}


# ---------------------------------------------------------------------------
# Responses API stream processing — top-level dispatch
# ---------------------------------------------------------------------------


def handle_responses_streaming_event(
    data: dict[str, Any],
    current_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    """
    Handle Responses API streaming events (pure).

    Returns (new_output, metadata):
      - metadata with keys -> meaningful event (usage, done, error)
      - {} -> update occurred (emit to frontend)
      - None -> skip / no-op
    """
    event_type = data.get("type", "")

    if event_type == "response.output_item.added":
        return _responses_item_added(data, current_output)

    if event_type == "response.content_part.added":
        return _responses_part_added(
            data, current_output, "content", skip_item_type="reasoning"
        )

    if event_type == "response.reasoning_summary_part.added":
        return _responses_part_added(data, current_output, "summary")

    if event_type.endswith(".delta"):
        return _responses_delta(event_type, data, current_output)

    if event_type.endswith(".done"):
        return _responses_done(event_type, data, current_output)

    if event_type == "response.completed":
        return _responses_completed(data, current_output)

    if event_type == "response.failed":
        error = data.get("response", {}).get("error", {})
        return current_output, {"error": error}

    # response.in_progress, etc.
    return current_output, None


# ---------------------------------------------------------------------------
# Chat Completions stream processing (pure output state update)
# ---------------------------------------------------------------------------


def apply_completions_delta(
    delta: dict[str, Any],
    output: OutputList,
    content: str,
) -> tuple[OutputList, str]:
    """Apply a Chat Completions delta to output state.  Mutates items in-place."""
    reasoning_text = (
        delta.get("reasoning_content")
        or delta.get("reasoning")
        or delta.get("thinking")
    )

    if reasoning_text:
        if not output or output[-1].get("type") != "reasoning":
            output.append(make_reasoning_item("in_progress"))
        reasoning_item = output[-1]
        parts = reasoning_item.get("content", [])
        if parts and parts[-1].get("type") == "output_text":
            parts[-1]["text"] += reasoning_text
        else:
            reasoning_item["content"] = [
                {"type": "output_text", "text": reasoning_text}
            ]

    value = delta.get("content")
    if value:
        # Transition: close reasoning block, open message
        if (
            output
            and output[-1].get("type") == "reasoning"
            and output[-1].get("attributes", {}).get("type") == "reasoning_content"
        ):
            output[-1] = close_reasoning_item(output[-1])
            output.append(make_message_item("", "in_progress"))

        content += value

        if not output or output[-1].get("type") != "message":
            output.append(make_message_item("", "in_progress"))

        msg_parts = output[-1].get("content", [])
        if msg_parts and msg_parts[-1].get("type") == "output_text":
            msg_parts[-1]["text"] += value
        else:
            output[-1]["content"] = [{"type": "output_text", "text": value}]

    return output, content


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


async def parse_sse_lines(
    body_iterator: AsyncIterator[bytes | str],
) -> AsyncIterator[dict[str, Any]]:
    """Parse SSE data: lines from a streaming response body."""
    async for line in body_iterator:
        line = line.decode("utf-8", "replace") if isinstance(line, bytes) else line
        if not line.strip():
            continue
        if not line.startswith("data:"):
            log.debug("[stream] non-data line: %s", line[:200])
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            log.debug("[stream] got [DONE] sentinel")
            return
        try:
            yield json.loads(payload)
        except json.JSONDecodeError as e:
            log.info("[stream] parse error: %s — %s", line[:200], e)


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

    system_message = get_system_message(form_data.get("messages", []))
    if system_message:  # Chat Controls/User Settings
        try:
            form_data = apply_system_prompt_to_body(
                system_message.get("content"), form_data, replace=True
            )
        except:
            pass

    form_data = await convert_url_images_to_base64(form_data)

    # Folder "Project" handling
    # Uses lightweight column query — only fetches folder_id, not the full chat JSON blob
    chat_id = metadata.get("chat_id")
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
        return [make_message_item(content)]
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

    if tasks.get(TASKS.FOLLOW_UP_GENERATION):
        await _generate_follow_ups(
            request, message, messages, metadata, user, event_emitter, is_ephemeral
        )

    if is_ephemeral:
        return

    if tasks.get(TASKS.TITLE_GENERATION):
        await _generate_title(request, message, messages, metadata, user, event_emitter)


# ---------------------------------------------------------------------------
# Non-streaming response handler
# ---------------------------------------------------------------------------


async def non_streaming_chat_response_handler(
    response: Any, ctx: dict[str, Any]
) -> Any:
    metadata: dict[str, Any] = ctx["metadata"]
    event_emitter: EventEmitter | None = ctx["event_emitter"]

    response, response_data = get_response_data(response)
    if response_data is None:
        return response

    if not event_emitter:
        return response_data if isinstance(response, dict) else response

    try:
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
    except Exception as e:
        log.debug(f"Error in non-streaming handler: {e}")

    return build_response_object(response, response_data)


# ---------------------------------------------------------------------------
# Streaming response handler (flat — no nested closures)
# ---------------------------------------------------------------------------


async def streaming_chat_response_handler(
    response: StreamingResponse, ctx: dict[str, Any]
) -> StreamingResponse | None:
    event_emitter: EventEmitter | None = ctx["event_emitter"]

    if not event_emitter:
        return StreamingResponse(
            response.body_iterator,
            headers=dict(response.headers),
            background=response.background,
        )

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
                await batcher.emit_now(data)
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
                    await batcher.emit_now(processed)
                else:
                    await batcher.add(processed)
                continue

            # --- Chat Completions events ---
            choices = data.get("choices", [])

            raw_usage = data.get("usage") or {}
            if raw_usage:
                usage = normalize_usage(raw_usage)
                await batcher.emit_now({"usage": usage})

            if not choices:
                error = data.get("error")
                if error:
                    await batcher.emit_now({"error": error})
                continue

            delta = choices[0].get("delta", {})

            # Side effects: annotations, images
            await _emit_annotations(delta, event_emitter)
            await _emit_images(delta, request, metadata, user, event_emitter)

            # State update
            output, content = apply_completions_delta(
                delta, output, content
            )

            emit_data = {"content": serialize_output(output)}
            if delta:
                await batcher.add(emit_data)
            else:
                await event_emitter({"type": "chat:completion", "data": emit_data})

        # Stream fully consumed
        await batcher.flush()

        if response.background:
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
        await event_emitter({"type": "chat:tasks:cancel"})
        Chats.upsert_message_to_chat_by_id_and_message_id(
            metadata["chat_id"],
            metadata["message_id"],
            {"content": serialize_output(output), "output": output},
        )

        if response.background is not None:
            await response.background()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def process_chat_response(response: Any, ctx: dict[str, Any]) -> Any:
    if not isinstance(response, StreamingResponse):
        return await non_streaming_chat_response_handler(response, ctx)

    if not any(
        ct in response.headers.get("Content-Type", "")
        for ct in ("text/event-stream", "application/x-ndjson")
    ):
        return response

    return await streaming_chat_response_handler(response, ctx)
