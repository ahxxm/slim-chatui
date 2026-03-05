import time
import logging
import sys
import asyncio
from typing import Optional
import json
import html
import re
from uuid import uuid4


from fastapi import Request
from starlette.responses import StreamingResponse, JSONResponse


from open_webui.models.chats import Chats
from open_webui.models.folders import Folders
from open_webui.socket.main import get_event_emitter
from open_webui.routers.tasks import (
    generate_title,
    generate_follow_ups,
)
from open_webui.utils.files import (
    convert_markdown_base64_images,
    get_image_base64_from_url,
    get_image_url_from_base64,
)


from open_webui.utils.misc import (
    deep_update,
    get_message_list,
    get_last_user_message,
    get_last_user_message_item,
    get_last_assistant_message,
    get_system_message,
    convert_logit_bias_input_to_json,
    convert_output_to_messages,
)
from open_webui.utils.payload import apply_system_prompt_to_body
from open_webui.utils.response import normalize_usage


from open_webui.env import (
    GLOBAL_LOG_LEVEL,
    ENABLE_CHAT_RESPONSE_BASE64_IMAGE_URL_CONVERSION,
    CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE,
)
from open_webui.constants import TASKS

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


def extract_task_text(res: dict) -> str:
    """Extract text content from Chat Completions or Responses API result."""
    # Chat Completions: choices[0].message.content
    choices = res.get("choices") or []
    if len(choices) == 1:
        msg = choices[0].get("message") or {}
        return msg.get("content") or msg.get("reasoning_content", "")
    # Responses API: output[0].content[0].text
    for item in res.get("output") or []:
        for block in item.get("content") or []:
            if block.get("type") == "output_text":
                return block.get("text", "")
    return ""


def parse_task_json(res, key, default):
    """Extract task text from LLM response, parse JSON, return value for key."""
    if not isinstance(res, dict):
        return default
    text = extract_task_text(res)
    text = text[text.find("{") : text.rfind("}") + 1]
    if not text:
        return default
    return json.loads(text).get(key, default)


def output_id(prefix: str) -> str:
    """Generate OR-style ID: prefix + 24-char hex UUID."""
    return f"{prefix}_{uuid4().hex[:24]}"


def serialize_output(output: list) -> str:
    """
    Convert OR-aligned output items to HTML for display.
    For LLM consumption, use convert_output_to_messages() instead.
    """
    content = ""

    for idx, item in enumerate(output):
        item_type = item.get("type", "")

        if item_type == "message":
            for content_part in item.get("content", []):
                if "text" in content_part:
                    text = content_part.get("text", "").strip()
                    if text:
                        content = f"{content}{text}\n"

        elif item_type == "web_search_call":
            status = item.get("status", "in_progress")
            action = item.get("action", {})
            query = action.get("query", "").strip().replace('"', "'")
            if content and not content.endswith("\n"):
                content += "\n"
            if status == "completed":
                content = f'{content}<details type="web_search" done="true" query="{query}">\n<summary>Searched the web</summary>\n</details>\n'
            else:
                content = f'{content}<details type="web_search" done="false" query="{query}">\n<summary>Searching the web…</summary>\n</details>\n'

        elif item_type == "reasoning":
            reasoning_content = ""
            # Check for 'summary' (new structure) or 'content' (legacy/fallback)
            source_list = item.get("summary", []) or item.get("content", [])
            for content_part in source_list:
                if "text" in content_part:
                    reasoning_content += content_part.get("text", "")
                elif "summary" in content_part:  # Handle potential nested logic if any
                    pass

            reasoning_content = reasoning_content.strip()

            duration = item.get("duration")
            status = item.get("status", "in_progress")

            # Infer completion: if this reasoning item is NOT the last item,
            # render as done (a subsequent item means reasoning is complete)
            is_last_item = idx == len(output) - 1

            if content and not content.endswith("\n"):
                content += "\n"

            display = html.escape(
                "\n".join(
                    (f"> {line}" if not line.startswith(">") else line)
                    for line in reasoning_content.splitlines()
                )
            )

            if status == "completed" or duration is not None or not is_last_item:
                d = round(duration, 1) if duration else 0
                content = f'{content}<details type="reasoning" done="true" duration="{d}">\n<summary>Thought for {d} seconds</summary>\n{display}\n</details>\n'
            else:
                content = f'{content}<details type="reasoning" done="false">\n<summary>Thinking…</summary>\n{display}\n</details>\n'

    return content.strip()


def deep_merge(target, source):
    """
    Merge source into target recursively (returning new structure).
    - Dicts: Recursive merge.
    - Strings: Concatenation.
    - Others: Overwrite.
    """
    if isinstance(target, dict) and isinstance(source, dict):
        new_target = target.copy()
        for k, v in source.items():
            if k in new_target:
                new_target[k] = deep_merge(new_target[k], v)
            else:
                new_target[k] = v
        return new_target
    elif isinstance(target, str) and isinstance(source, str):
        return target + source
    else:
        return source


def _replace_output_item_by_id(
    data: dict, current_output: list
) -> tuple[list, dict | None]:
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


def handle_responses_streaming_event(
    data: dict,
    current_output: list,
) -> tuple[list, dict | None]:
    """
    Handle Responses API streaming events in a pure functional way.

    Args:
        data: The event data
        current_output: List of output items (treated as immutable)

    Returns:
        tuple[list, dict | None]: (new_output, metadata)
        - new_output: The updated output list.
        - metadata: Metadata to emit (e.g. usage), {} if update occurred, None if skip.
    """
    # Default: no change
    # Note: treating current_output as immutable, but avoiding full deepcopy for perf.
    # We will shallow copy only if we need to modify the list structure or items.

    event_type = data.get("type", "")

    if event_type == "response.output_item.added":
        item = data.get("item", {})
        if item:
            now = time.time()
            new_output = list(current_output)
            # Close the previous reasoning block's duration when a new item arrives
            if new_output:
                prev = new_output[-1]
                if (
                    prev.get("type") == "reasoning"
                    and "started_at" in prev
                    and "duration" not in prev
                ):
                    prev = {**prev, "duration": now - prev["started_at"]}
                    new_output[-1] = prev
            if item.get("type") == "reasoning":
                item = {**item, "started_at": now}
            new_output.append(item)
            return new_output, None
        return current_output, None

    elif event_type == "response.content_part.added":
        part = data.get("part", {})
        output_index = data.get("output_index", len(current_output) - 1)

        if current_output and 0 <= output_index < len(current_output):
            new_output = list(current_output)
            # Copy the item to mutate it
            item = new_output[output_index].copy()
            new_output[output_index] = item

            if "content" not in item:
                item["content"] = []
            else:
                # Copy content list
                item["content"] = list(item["content"])

            if item.get("type") == "reasoning":
                # Reasoning items should not have content parts
                pass
            else:
                item["content"].append(part)
            return new_output, None
        return current_output, None

    elif event_type == "response.reasoning_summary_part.added":
        part = data.get("part", {})
        output_index = data.get("output_index", len(current_output) - 1)

        if current_output and 0 <= output_index < len(current_output):
            new_output = list(current_output)
            item = new_output[output_index].copy()
            new_output[output_index] = item

            if "summary" not in item:
                item["summary"] = []
            else:
                item["summary"] = list(item["summary"])

            item["summary"].append(part)
            return new_output, None
        return current_output, None

    elif event_type.startswith("response.") and event_type.endswith(".delta"):
        # Generic Delta Handling
        parts = event_type.split(".")
        if len(parts) >= 3:
            delta_type = parts[1]
            delta = data.get("delta", "")

            output_index = data.get("output_index", len(current_output) - 1)

            if current_output and 0 <= output_index < len(current_output):
                new_output = list(current_output)
                item = new_output[output_index].copy()
                new_output[output_index] = item
                item_type = item.get("type", "")

                # Determine target field and object based on delta_type and item_type
                if delta_type == "function_call_arguments":
                    key = "arguments"
                    if item_type == "function_call":
                        # Function call args are usually strings
                        item[key] = item.get(key, "") + str(delta)
                else:
                    # Generic handling, refined by item type below
                    pass

                    if item_type == "message":
                        # Message items: "text"/"output_text" -> "text"
                        # "reasoning_text" -> Skipped (should use reasoning item)
                        if delta_type in ["text", "output_text"]:
                            key = "text"
                        elif delta_type in ["reasoning_text", "reasoning_summary_text"]:
                            # Skip reasoning updates for message items
                            return new_output, None
                        else:
                            key = delta_type

                        content_index = data.get("content_index", 0)
                        if "content" not in item:
                            item["content"] = []
                        else:
                            item["content"] = list(item["content"])
                        content_list = item["content"]

                        while len(content_list) <= content_index:
                            content_list.append({"type": "text", "text": ""})

                        # Copy the part to mutate it
                        part = content_list[content_index].copy()
                        content_list[content_index] = part

                        current_val = part.get(key)
                        if current_val is None:
                            # Initialize based on delta type
                            current_val = {} if isinstance(delta, dict) else ""

                        part[key] = deep_merge(current_val, delta)

                    elif item_type == "reasoning":
                        # Reasoning items: "reasoning_text"/"reasoning_summary_text" -> "text"
                        # "text"/"output_text" -> Skipped (should use message item)
                        if delta_type == "reasoning_summary_text":
                            # Summary updates -> item['summary']
                            key = "text"
                            summary_index = data.get("summary_index", 0)
                            if "summary" not in item:
                                item["summary"] = []
                            else:
                                item["summary"] = list(item["summary"])
                            summary_list = item["summary"]

                            while len(summary_list) <= summary_index:
                                summary_list.append(
                                    {"type": "summary_text", "text": ""}
                                )

                            part = summary_list[summary_index].copy()
                            summary_list[summary_index] = part

                            target_val = part.get(key, "")
                            part[key] = deep_merge(target_val, delta)

                        elif delta_type == "reasoning_text":
                            # Reasoning body updates -> item['content']
                            key = "text"
                            content_index = data.get("content_index", 0)
                            if "content" not in item:
                                item["content"] = []
                            else:
                                item["content"] = list(item["content"])
                            content_list = item["content"]

                            while len(content_list) <= content_index:
                                # Reasoning content parts default to text
                                content_list.append({"type": "text", "text": ""})

                            part = content_list[content_index].copy()
                            content_list[content_index] = part

                            target_val = part.get(key, "")
                            part[key] = deep_merge(target_val, delta)

                        elif delta_type in ["text", "output_text"]:
                            return new_output, None
                        else:
                            # Fallback just in case other deltas target reasoning?
                            pass

                    else:
                        # Fallback for other item types
                        if delta_type in ["text", "output_text"]:
                            key = "text"
                        else:
                            key = delta_type

                        current_val = item.get(key)
                        if current_val is None:
                            current_val = {} if isinstance(delta, dict) else ""
                        item[key] = deep_merge(current_val, delta)

            return new_output, None

    elif event_type.startswith("response.") and event_type.endswith(".done"):
        # Delta Events: response.content_part.done, response.text.done, etc.
        parts = event_type.split(".")
        if len(parts) >= 3:
            type_name = parts[1]

            # 1. Handle specific Delta "done" signals
            if type_name == "content_part":
                # "Signaling that no further changes will occur to a content part"
                # If payloads contains the full part, we could update it.
                # Usually purely signaling in standard implementation, but we check payload.
                part = data.get("part")
                output_index = data.get("output_index", len(current_output) - 1)

                if part and current_output and 0 <= output_index < len(current_output):
                    new_output = list(current_output)
                    item = new_output[output_index].copy()
                    new_output[output_index] = item

                    if "content" in item:
                        item["content"] = list(item["content"])
                        content_index = data.get(
                            "content_index", len(item["content"]) - 1
                        )
                        if 0 <= content_index < len(item["content"]):
                            item["content"][content_index] = part
                            return new_output, {}
                return current_output, None

            elif type_name == "reasoning_summary_part":
                part = data.get("part")
                output_index = data.get("output_index", len(current_output) - 1)

                if part and current_output and 0 <= output_index < len(current_output):
                    new_output = list(current_output)
                    item = new_output[output_index].copy()
                    new_output[output_index] = item

                    if "summary" in item:
                        item["summary"] = list(item["summary"])
                        summary_index = data.get(
                            "summary_index", len(item["summary"]) - 1
                        )
                        if 0 <= summary_index < len(item["summary"]):
                            item["summary"][summary_index] = part
                            return new_output, {}
                return current_output, None

            # 2. Output Item done — replace by id (not output_index, which
            #    may not match our array if we inserted extra items)
            if type_name == "output_item":
                return _replace_output_item_by_id(data, current_output)

            # 3. Generic Field Done (text.done, audio.done)
            elif type_name not in ["completed", "failed"]:
                output_index = data.get("output_index", len(current_output) - 1)
                if current_output and 0 <= output_index < len(current_output):

                    key = (
                        "text"
                        if type_name
                        in [
                            "text",
                            "output_text",
                            "reasoning_text",
                            "reasoning_summary_text",
                        ]
                        else type_name
                    )
                    if type_name == "function_call_arguments":
                        key = "arguments"

                    if key in data:
                        final_value = data[key]
                        new_output = list(current_output)
                        item = new_output[output_index].copy()
                        new_output[output_index] = item
                        item_type = item.get("type", "")

                        if type_name == "function_call_arguments":
                            if item_type == "function_call":
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

        return current_output, None

    elif event_type == "response.completed":
        # State Machine Event: Completed
        response_data = data.get("response", {})
        final_output = response_data.get("output")

        # Carry over per-block timing and durations already computed
        timing = {}
        computed_durations = {}
        for item in current_output:
            if item.get("type") == "reasoning":
                item_id = item.get("id")
                if "started_at" in item:
                    timing[item_id] = item["started_at"]
                if "duration" in item:
                    computed_durations[item_id] = item["duration"]

        new_output = final_output if final_output is not None else current_output

        now = time.time()
        if new_output:
            for item in new_output:
                if item.get("type") == "reasoning":
                    if item.get("status") != "completed":
                        item["status"] = "completed"
                    item_id = item.get("id")
                    if item_id in computed_durations:
                        item["duration"] = computed_durations[item_id]
                    elif "duration" not in item:
                        started = timing.get(item_id)
                        item["duration"] = (now - started) if started else 0

        return new_output, {"usage": response_data.get("usage"), "done": True}

    elif event_type == "response.in_progress":
        # State Machine Event: In Progress
        # We could extract metadata if needed, but for now just acknowledge iteration
        return current_output, None

    elif event_type == "response.failed":
        # State Machine Event: Failed
        error = data.get("response", {}).get("error", {})
        return current_output, {"error": error}

    else:
        return current_output, None


def get_image_urls(delta_images, request, metadata, user) -> list[str]:
    if not isinstance(delta_images, list):
        return []

    image_urls = []
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


def apply_params_to_form_data(form_data):
    params = form_data.pop("params", {})
    custom_params = params.pop("custom_params", {})

    open_webui_only_keys = {"stream_delta_chunk_size", "system"}
    for key in open_webui_only_keys:
        params.pop(key, None)

    if custom_params:
        # Attempt to parse custom_params if they are strings
        for key, value in custom_params.items():
            if isinstance(value, str):
                try:
                    # Attempt to parse the string as JSON
                    custom_params[key] = json.loads(value)
                except json.JSONDecodeError:
                    # If it fails, keep the original string
                    pass

        # If custom_params are provided, merge them into params
        params = deep_update(params, custom_params)

    if isinstance(params, dict):
        for key, value in params.items():
            if value is not None:
                form_data[key] = value

    if "logit_bias" in params and params["logit_bias"] is not None:
        try:
            logit_bias = convert_logit_bias_input_to_json(params["logit_bias"])

            if logit_bias:
                form_data["logit_bias"] = json.loads(logit_bias)
        except Exception as e:
            log.exception(f"Error parsing logit_bias: {e}")

    return form_data


async def convert_url_images_to_base64(form_data):
    messages = form_data.get("messages", [])

    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue

        new_content = []

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
                    {
                        "type": "image_url",
                        "image_url": {"url": base64_data},
                    }
                )
            except Exception as e:
                log.debug(f"Error converting image URL to base64: {e}")
                new_content.append(item)

        message["content"] = new_content

    return form_data


def load_messages_from_db(chat_id: str, message_id: str) -> Optional[list[dict]]:
    """
    Load the message chain from DB up to message_id,
    keeping only LLM-relevant fields (role, content, output).
    """
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


def process_messages_with_output(messages: list[dict]) -> list[dict]:
    """
    Process messages with OR-aligned output items for LLM consumption.

    For assistant messages with 'output' field, produces properly formatted
    OpenAI-style messages (tool_calls + tool results). Strips 'output' before LLM.
    """
    processed = []

    for message in messages:
        if message.get("role") == "assistant" and message.get("output"):
            # Use output items for clean OpenAI-format messages
            output_messages = convert_output_to_messages(message["output"])
            if output_messages:
                processed.extend(output_messages)
                continue

        # Strip 'output' field before adding (LLM shouldn't see it)
        clean_message = {k: v for k, v in message.items() if k != "output"}
        processed.append(clean_message)

    return processed


async def process_chat_payload(request, form_data, user, metadata, model):
    form_data = apply_params_to_form_data(form_data)
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

            # Inject image files into content as image_url parts (mirrors frontend logic)
            for message in form_data["messages"]:
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
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f["url"]},
                                }
                                for f in image_files
                                if f.get("url")
                            ],
                        ]
                # Strip files field — it's been incorporated into content
                message.pop("files", None)

    # Process messages with OR-aligned output items for clean LLM messages
    form_data["messages"] = process_messages_with_output(form_data.get("messages", []))

    system_message = get_system_message(form_data.get("messages", []))
    if system_message:  # Chat Controls/User Settings
        try:
            form_data = apply_system_prompt_to_body(
                system_message.get("content"), form_data, metadata, user, replace=True
            )  # Required to handle system prompt variables
        except:
            pass

    form_data = await convert_url_images_to_base64(form_data)

    # Folder "Project" handling
    # Check if the request has chat_id and is inside of a folder
    # Uses lightweight column query — only fetches folder_id, not the full chat JSON blob
    chat_id = metadata.get("chat_id", None)
    if chat_id and user:
        folder_id = Chats.get_chat_folder_id(chat_id, user.id)
        if folder_id:
            folder = Folders.get_folder_by_id_and_user_id(folder_id, user.id)

            if folder and folder.data:
                if "system_prompt" in folder.data:
                    form_data = apply_system_prompt_to_body(
                        folder.data["system_prompt"], form_data, metadata, user
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
        for file_item in files:
            if file_item.get("type", "file") == "folder":
                # Get folder files
                folder_id = file_item.get("id", None)
                if folder_id:
                    folder = Folders.get_folder_by_id_and_user_id(folder_id, user.id)
                    if folder and folder.data and "files" in folder.data:
                        files = [f for f in files if f.get("id", None) != folder_id]
                        files = [*files, *folder.data["files"]]

        # files = [*files, *[{"type": "url", "url": url, "name": url} for url in urls]]
        # Remove duplicate files based on their content
        files = list({json.dumps(f, sort_keys=True): f for f in files}.values())

    metadata = {
        **metadata,
        "files": files,
    }
    form_data["metadata"] = metadata

    return form_data, metadata


def get_event_emitter_or_none(metadata):
    if (
        "session_id" in metadata
        and metadata["session_id"]
        and "chat_id" in metadata
        and metadata["chat_id"]
        and "message_id" in metadata
        and metadata["message_id"]
    ):
        return get_event_emitter(metadata)
    return None


def build_chat_response_context(request, form_data, user, model, metadata, tasks):
    event_emitter = get_event_emitter_or_none(metadata)
    return {
        "request": request,
        "form_data": form_data,
        "user": user,
        "model": model,
        "metadata": metadata,
        "tasks": tasks,
        "event_emitter": event_emitter,
    }


def get_response_data(response):
    if isinstance(response, list) and len(response) == 1:
        # If the response is a single-item list, unwrap it #17213
        response = response[0]

    if isinstance(response, JSONResponse):
        if isinstance(response.body, bytes):
            try:
                response_data = json.loads(response.body.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                response_data = {"error": {"detail": "Invalid JSON response"}}
        else:
            response_data = response
    elif isinstance(response, dict):
        response_data = response
    else:
        response_data = None

    return response, response_data


def build_response_object(response, response_data):
    if isinstance(response, dict):
        return response_data
    if isinstance(response, JSONResponse):
        return JSONResponse(
            content=response_data,
            headers=response.headers,
            status_code=response.status_code,
        )
    return response


async def background_tasks_handler(ctx):
    request = ctx["request"]
    form_data = ctx["form_data"]
    user = ctx["user"]
    metadata = ctx["metadata"]
    tasks = ctx["tasks"]
    event_emitter = ctx["event_emitter"]

    message = None
    messages = []
    is_ephemeral_chat = metadata.get("chat_id", "").startswith("local:")

    if "chat_id" in metadata and not is_ephemeral_chat:
        messages_map = Chats.get_messages_map_by_chat_id(metadata["chat_id"])
        message = messages_map.get(metadata["message_id"]) if messages_map else None

        message_list = get_message_list(messages_map, metadata["message_id"])

        # Strip details tags, images, and files for task generation prompts
        messages = []
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

            messages.append(
                {
                    **msg,
                    "role": msg.get("role", "assistant"),
                    "content": content,
                }
            )
    else:
        # Ephemeral chat — get the model and message from form_data
        message = get_last_user_message_item(form_data.get("messages", []))
        messages = form_data.get("messages", [])
        if message:
            message["model"] = form_data.get("model")

    if not (message and "model" in message and tasks and messages):
        return

    if tasks.get(TASKS.FOLLOW_UP_GENERATION):
        try:
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
            follow_ups = parse_task_json(res, "follow_ups", [])
            if follow_ups:
                await event_emitter(
                    {
                        "type": "chat:message:follow_ups",
                        "data": {"follow_ups": follow_ups},
                    }
                )
                if not is_ephemeral_chat:
                    Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata["chat_id"],
                        metadata["message_id"],
                        {"followUps": follow_ups},
                    )
        except Exception as e:
            log.error(f"follow-up generation failed: {e}")

    if is_ephemeral_chat:
        return

    if tasks.get(TASKS.TITLE_GENERATION):
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
            title = parse_task_json(res, "title", "")
        except Exception as e:
            log.error(f"title generation failed: {e}")
            title = ""

        if not title:
            user_message = get_last_user_message(messages) or ""
            title = user_message[:100] or "New Chat"

        Chats.update_chat_title_by_id(metadata["chat_id"], title)
        await event_emitter({"type": "chat:title", "data": title})


async def non_streaming_chat_response_handler(response, ctx):
    request = ctx["request"]

    user = ctx["user"]
    metadata = ctx["metadata"]

    event_emitter = ctx["event_emitter"]

    response, response_data = get_response_data(response)
    if response_data is None:
        return response

    if event_emitter:
        try:
            if "error" in response_data:
                error = response_data.get("error")

                if isinstance(error, dict):
                    error = error.get("detail", error)
                else:
                    error = str(error)

                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {
                        "error": {"content": error},
                    },
                )
                if isinstance(error, str) or isinstance(error, dict):
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
                    {
                        "selectedModelId": response_data["selected_model_id"],
                    },
                )

            choices = response_data.get("choices", [])
            if choices and choices[0].get("message", {}).get("content"):
                content = response_data["choices"][0]["message"]["content"]

                if content:
                    await event_emitter(
                        {
                            "type": "chat:completion",
                            "data": response_data,
                        }
                    )

                    title = Chats.get_chat_title_by_id(metadata["chat_id"])

                    # Use output from backend if provided (OR-compliant backends),
                    # otherwise generate from response content
                    response_output = response_data.get("output")
                    if not response_output:
                        response_output = [
                            {
                                "type": "message",
                                "id": output_id("msg"),
                                "status": "completed",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": content}],
                            }
                        ]

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

                    # Save message in the database
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

            response = build_response_object(response, response_data)
        except Exception as e:
            log.debug(f"Error occurred while processing request: {e}")
            pass

        return response

    if isinstance(response, dict):
        response = response_data

    return response


async def streaming_chat_response_handler(response, ctx):
    request = ctx["request"]

    form_data = ctx["form_data"]

    user = ctx["user"]

    metadata = ctx["metadata"]

    event_emitter = ctx["event_emitter"]

    # Standard streaming response handler
    if event_emitter:

        # Handle as a background task
        async def response_handler(response):
            message = Chats.get_message_by_id_and_message_id(
                metadata["chat_id"], metadata["message_id"]
            )

            last_assistant_message = None
            try:
                if form_data["messages"][-1]["role"] == "assistant":
                    last_assistant_message = get_last_assistant_message(
                        form_data["messages"]
                    )
            except Exception as e:
                pass

            content = (
                message.get("content", "")
                if message
                else last_assistant_message if last_assistant_message else ""
            )

            # Initialize output: use existing from message if continuing, else create new
            existing_output = message.get("output") if message else None
            if existing_output:
                output = existing_output
            else:
                # Only create an initial message item if there is content to initialize with
                if content:
                    output = [
                        {
                            "type": "message",
                            "id": output_id("msg"),
                            "status": "in_progress",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": content}],
                        }
                    ]
                else:
                    output = []

            usage = None

            try:

                async def stream_body_handler(response, form_data):
                    nonlocal content
                    nonlocal usage
                    nonlocal output

                    delta_count = 0
                    delta_chunk_size = max(
                        CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE,
                        int(
                            metadata.get("params", {}).get("stream_delta_chunk_size")
                            or 1
                        ),
                    )
                    last_delta_data = None

                    async def flush_pending_delta_data(threshold: int = 0):
                        nonlocal delta_count
                        nonlocal last_delta_data

                        if delta_count >= threshold and last_delta_data:
                            await event_emitter(
                                {
                                    "type": "chat:completion",
                                    "data": last_delta_data,
                                }
                            )
                            delta_count = 0
                            last_delta_data = None

                    async for line in response.body_iterator:
                        line = (
                            line.decode("utf-8", "replace")
                            if isinstance(line, bytes)
                            else line
                        )
                        data = line

                        # Skip empty lines
                        if not data.strip():
                            continue

                        # "data:" is the prefix for each event
                        if not data.startswith("data:"):
                            continue

                        # Remove the prefix
                        data = data[len("data:") :].strip()

                        try:
                            data = json.loads(data)

                            if data:
                                if "event" in data:
                                    await event_emitter(data.get("event", {}))

                                if "selected_model_id" in data:
                                    model_id = data["selected_model_id"]
                                    Chats.upsert_message_to_chat_by_id_and_message_id(
                                        metadata["chat_id"],
                                        metadata["message_id"],
                                        {
                                            "selectedModelId": model_id,
                                        },
                                    )
                                    await event_emitter(
                                        {
                                            "type": "chat:completion",
                                            "data": data,
                                        }
                                    )
                                # Check for Responses API events (type field starts with "response.")
                                elif data.get("type", "").startswith("response."):
                                    output, response_metadata = (
                                        handle_responses_streaming_event(data, output)
                                    )

                                    processed_data = {
                                        "output": output,
                                        "content": serialize_output(output),
                                    }

                                    # print(data)
                                    # print(processed_data)

                                    # Merge any metadata (usage, done, etc.)
                                    if response_metadata:
                                        processed_data.update(response_metadata)

                                    await event_emitter(
                                        {
                                            "type": "chat:completion",
                                            "data": processed_data,
                                        }
                                    )
                                    continue
                                else:
                                    choices = data.get("choices", [])

                                    raw_usage = data.get("usage", {}) or {}
                                    if raw_usage:
                                        usage = normalize_usage(raw_usage)
                                        await event_emitter(
                                            {
                                                "type": "chat:completion",
                                                "data": {
                                                    "usage": usage,
                                                },
                                            }
                                        )

                                    if not choices:
                                        error = data.get("error", {})
                                        if error:
                                            await event_emitter(
                                                {
                                                    "type": "chat:completion",
                                                    "data": {
                                                        "error": error,
                                                    },
                                                }
                                            )
                                        continue

                                    delta = choices[0].get("delta", {})

                                    # Handle delta annotations
                                    annotations = delta.get("annotations")
                                    if annotations:
                                        for annotation in annotations:
                                            if (
                                                annotation.get("type") == "url_citation"
                                                and "url_citation" in annotation
                                            ):
                                                url_citation = annotation[
                                                    "url_citation"
                                                ]

                                                url = url_citation.get("url", "")
                                                title = url_citation.get("title", url)

                                                await event_emitter(
                                                    {
                                                        "type": "source",
                                                        "data": {
                                                            "source": {
                                                                "name": title,
                                                                "url": url,
                                                            },
                                                            "document": [title],
                                                            "metadata": [
                                                                {
                                                                    "source": url,
                                                                    "name": title,
                                                                }
                                                            ],
                                                        },
                                                    }
                                                )

                                    image_urls = get_image_urls(
                                        delta.get("images", []), request, metadata, user
                                    )
                                    if image_urls:
                                        message_files = Chats.add_message_files_by_id_and_message_id(
                                            metadata["chat_id"],
                                            metadata["message_id"],
                                            [
                                                {"type": "image", "url": url}
                                                for url in image_urls
                                            ],
                                        )

                                        await event_emitter(
                                            {
                                                "type": "files",
                                                "data": {"files": message_files},
                                            }
                                        )

                                    value = delta.get("content")

                                    reasoning_content = (
                                        delta.get("reasoning_content")
                                        or delta.get("reasoning")
                                        or delta.get("thinking")
                                    )
                                    if reasoning_content:
                                        if (
                                            not output
                                            or output[-1].get("type") != "reasoning"
                                        ):
                                            reasoning_item = {
                                                "type": "reasoning",
                                                "id": output_id("r"),
                                                "status": "in_progress",
                                                "start_tag": "<think>",
                                                "end_tag": "</think>",
                                                "attributes": {
                                                    "type": "reasoning_content"
                                                },
                                                "content": [],
                                                "summary": None,
                                                "started_at": time.time(),
                                            }
                                            output.append(reasoning_item)
                                        else:
                                            reasoning_item = output[-1]

                                        # Append to reasoning content
                                        parts = reasoning_item.get("content", [])
                                        if (
                                            parts
                                            and parts[-1].get("type") == "output_text"
                                        ):
                                            parts[-1]["text"] += reasoning_content
                                        else:
                                            reasoning_item["content"] = [
                                                {
                                                    "type": "output_text",
                                                    "text": reasoning_content,
                                                }
                                            ]

                                        data = {"content": serialize_output(output)}

                                    if value:
                                        if (
                                            output
                                            and output[-1].get("type") == "reasoning"
                                            and output[-1]
                                            .get("attributes", {})
                                            .get("type")
                                            == "reasoning_content"
                                        ):
                                            reasoning_item = output[-1]
                                            reasoning_item["ended_at"] = time.time()
                                            reasoning_item["duration"] = (
                                                reasoning_item["ended_at"]
                                                - reasoning_item["started_at"]
                                            )
                                            reasoning_item["status"] = "completed"

                                            output.append(
                                                {
                                                    "type": "message",
                                                    "id": output_id("msg"),
                                                    "status": "in_progress",
                                                    "role": "assistant",
                                                    "content": [
                                                        {
                                                            "type": "output_text",
                                                            "text": "",
                                                        }
                                                    ],
                                                }
                                            )

                                        if ENABLE_CHAT_RESPONSE_BASE64_IMAGE_URL_CONVERSION:
                                            value = convert_markdown_base64_images(
                                                request,
                                                value,
                                                {
                                                    "chat_id": metadata.get(
                                                        "chat_id", None
                                                    ),
                                                    "message_id": metadata.get(
                                                        "message_id", None
                                                    ),
                                                },
                                                user,
                                            )

                                        content = f"{content}{value}"

                                        if (
                                            not output
                                            or output[-1].get("type") != "message"
                                        ):
                                            output.append(
                                                {
                                                    "type": "message",
                                                    "id": output_id("msg"),
                                                    "status": "in_progress",
                                                    "role": "assistant",
                                                    "content": [
                                                        {
                                                            "type": "output_text",
                                                            "text": "",
                                                        }
                                                    ],
                                                }
                                            )

                                        msg_parts = output[-1].get("content", [])
                                        if (
                                            msg_parts
                                            and msg_parts[-1].get("type")
                                            == "output_text"
                                        ):
                                            msg_parts[-1]["text"] += value
                                        else:
                                            output[-1]["content"] = [
                                                {
                                                    "type": "output_text",
                                                    "text": value,
                                                }
                                            ]

                                        data = {
                                            "content": serialize_output(output),
                                        }

                                if delta:
                                    delta_count += 1
                                    last_delta_data = data
                                    if delta_count >= delta_chunk_size:
                                        await flush_pending_delta_data(delta_chunk_size)
                                else:
                                    await event_emitter(
                                        {
                                            "type": "chat:completion",
                                            "data": data,
                                        }
                                    )
                        except Exception as e:
                            done = "data: [DONE]" in line
                            if done:
                                pass
                            else:
                                log.debug(f"Error: {e}")
                                continue
                    await flush_pending_delta_data()

                    if output:
                        # Clean up the last message item
                        if output[-1].get("type") == "message":
                            parts = output[-1].get("content", [])
                            if parts and parts[-1].get("type") == "output_text":
                                parts[-1]["text"] = parts[-1]["text"].strip()

                                if not parts[-1]["text"]:
                                    output.pop()

                                    if not output:
                                        output.append(
                                            {
                                                "type": "message",
                                                "id": output_id("msg"),
                                                "status": "in_progress",
                                                "role": "assistant",
                                                "content": [
                                                    {"type": "output_text", "text": ""}
                                                ],
                                            }
                                        )

                        if output[-1].get("type") == "reasoning":
                            reasoning_item = output[-1]
                            if reasoning_item.get("ended_at") is None:
                                reasoning_item["ended_at"] = time.time()
                                reasoning_item["duration"] = round(
                                    reasoning_item["ended_at"]
                                    - reasoning_item["started_at"]
                                )
                                reasoning_item["status"] = "completed"

                    if response.background:
                        await response.background()

                await stream_body_handler(response, form_data)

                # Mark all in-progress items as completed
                for item in output:
                    if item.get("status") == "in_progress":
                        item["status"] = "completed"

                title = Chats.get_chat_title_by_id(metadata["chat_id"])
                data = {
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

                await event_emitter(
                    {
                        "type": "chat:completion",
                        "data": data,
                    }
                )

                await background_tasks_handler(ctx)
            except asyncio.CancelledError:
                log.warning("Task was cancelled!")
                await event_emitter({"type": "chat:tasks:cancel"})
                # Save unfinished message in the database
                Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata["chat_id"],
                    metadata["message_id"],
                    {
                        "content": serialize_output(output),
                        "output": output,
                    },
                )

            if response.background is not None:
                await response.background()

        return await response_handler(response)

    else:
        # Fallback to the original response
        return StreamingResponse(
            response.body_iterator,
            headers=dict(response.headers),
            background=response.background,
        )


async def process_chat_response(response, ctx):
    # Non-streaming response
    if not isinstance(response, StreamingResponse):
        return await non_streaming_chat_response_handler(response, ctx)

    # Non standard response
    if not any(
        content_type in response.headers["Content-Type"]
        for content_type in ["text/event-stream", "application/x-ndjson"]
    ):
        return response

    # Streaming response
    return await streaming_chat_response_handler(response, ctx)
