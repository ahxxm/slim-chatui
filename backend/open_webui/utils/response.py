"""Response data structures and their transformations.

Pure functions — no DB, no HTTP, no event emission.
"""

import time
import logging
import json
import html
from typing import Any
from collections.abc import AsyncIterator
from uuid import uuid4

log = logging.getLogger(__name__)

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
    """Merge source into target: None is identity, dicts recurse, strings concat, else overwrite."""
    if target is None:
        return source
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
    if not output:
        return output

    last = output[-1]

    # Strip trailing whitespace from last message; drop if empty
    if last.get("type") == "message":
        parts = last.get("content", [])
        if parts and parts[-1].get("type") == "output_text":
            parts[-1]["text"] = parts[-1]["text"].strip()
            if not parts[-1]["text"]:
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
# Task text extraction / JSON parsing
# ---------------------------------------------------------------------------


def extract_task_text(res: dict) -> str:
    """Extract text (skip reasoning) from Completions and Responses.
    LiteLLM proxies may convert extended thinking (e.g. Claude) into
    reasoning_content (Chat Completions) or reasoning output items (Responses API).
    We skip those and return only the actual text output.
    """
    # Chat Completions: choices[0].message.content (not reasoning_content)
    choices = res.get("choices") or []
    if len(choices) == 1:
        msg = choices[0].get("message") or {}
        return msg.get("content", "")
    # Responses API: first non-reasoning output_text
    for item in res.get("output") or []:
        if item.get("type") == "reasoning":
            continue
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


def normalize_usage(usage: dict) -> dict:
    """
    Normalize usage statistics to standard format.
    Handles OpenAI Chat Completions and Responses API formats.

    Adds standardized token fields to the original data:
    - input_tokens: Number of tokens in the prompt
    - output_tokens: Number of tokens generated
    - total_tokens: Sum of input and output tokens
    """
    if not usage:
        return {}

    input_tokens = (
        usage.get("input_tokens")  # Responses API
        or usage.get("prompt_tokens")  # OpenAI Chat Completions
        or 0
    )

    output_tokens = (
        usage.get("output_tokens")  # Responses API
        or usage.get("completion_tokens")  # OpenAI Chat Completions
        or 0
    )

    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)

    result = dict(usage)
    result["input_tokens"] = int(input_tokens)
    result["output_tokens"] = int(output_tokens)
    result["total_tokens"] = int(total_tokens)

    return result


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

    new_output = list(current_output)

    # Close the previous reasoning block
    if new_output and new_output[-1].get("type") == "reasoning":
        new_output[-1] = close_reasoning_item(new_output[-1])

    if item.get("type") == "reasoning":
        item = {**item, "started_at": time.time()}

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
        log.warning(f"[stream] part_added has invalid output_index {output_index}")
        return current_output, None

    new_output = list(current_output)
    item = new_output[output_index].copy()
    new_output[output_index] = item

    if skip_item_type and item.get("type") == skip_item_type:
        return current_output, None

    item[field] = [*item.get(field, []), part]
    return new_output, None


# --- delta sub-handlers ---


# (field, index_key, default entry type) — keyed by (item_type, delta_type).
_DELTA_ROUTES = {
    ("message", "text"): ("content", "content_index", "text"),
    ("message", "output_text"): ("content", "content_index", "text"),
    ("reasoning", "reasoning_summary_text"): (
        "summary",
        "summary_index",
        "summary_text",
    ),
    ("reasoning", "reasoning_text"): ("content", "content_index", "text"),
    # LiteLLM chat→responses bridge mislabels reasoning content as output_text
    ("reasoning", "output_text"): ("content", "content_index", "text"),
}


def _apply_item_delta(
    item_type: str,
    delta_type: str,
    data: dict[str, Any],
    delta: Any,
    item: dict[str, Any],
    new_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    field, index_key, entry_type = _DELTA_ROUTES[(item_type, delta_type)]
    idx = data.get(index_key, 0)
    entries = item[field] = list(item.get(field, []))
    while len(entries) <= idx:
        entries.append({"type": entry_type, "text": ""})
    entries[idx] = {**entries[idx], "text": deep_merge(entries[idx].get("text"), delta)}
    return new_output, None


def _responses_delta(
    event_type: str,
    data: dict[str, Any],
    current_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    parts = event_type.split(".")
    if len(parts) < 3:
        log.warning(f"[stream] malformed delta event?: {event_type}")
        return current_output, None

    delta_type = parts[1]
    delta = data.get("delta", "")
    output_index = data.get("output_index", len(current_output) - 1)

    if not current_output or not (0 <= output_index < len(current_output)):
        log.warning(
            f"[stream] delta event {event_type} has invalid output_index {output_index}"
        )
        return current_output, None

    new_output = list(current_output)
    item = new_output[output_index].copy()
    new_output[output_index] = item
    item_type = item.get("type", "")

    if delta_type == "function_call_arguments":
        if item_type == "function_call":
            item["arguments"] = item.get("arguments", "") + str(delta)
        return new_output, None

    if (item_type, delta_type) in _DELTA_ROUTES:
        return _apply_item_delta(item_type, delta_type, data, delta, item, new_output)

    log.warning(f"[stream] unrouted delta {delta_type} on {item_type} item")
    return new_output, None


# --- done sub-handlers ---


def _resolve_done_item(
    data: dict[str, Any], current_output: OutputList
) -> dict[str, Any] | None:
    """Return the output item targeted by a .done event, or None."""
    output_index = data.get("output_index", len(current_output) - 1)
    if current_output and 0 <= output_index < len(current_output):
        return current_output[output_index]
    return None


# .done events that replace a part in a list field
_DONE_PART_FIELDS = {
    "content_part": ("content", "content_index"),
    "reasoning_summary_part": ("summary", "summary_index"),
}

# .done events that finalize a scalar field
_DONE_KEY_MAP = {
    "text": "text",
    "output_text": "text",
    "reasoning_text": "text",
    "reasoning_summary_text": "text",
    "function_call_arguments": "arguments",
}


def _responses_done(
    event_type: str,
    data: dict[str, Any],
    current_output: OutputList,
) -> tuple[OutputList, dict[str, Any] | None]:
    parts = event_type.split(".")
    if len(parts) < 3:
        log.warning(f"[stream] malformed done event: {event_type}")
        return current_output, None

    type_name = parts[1]

    # Replace by id, not output_index — index may not match our array
    # if we inserted extra items (e.g. reasoning blocks)
    if type_name == "output_item":
        return _replace_output_item_by_id(data, current_output)

    if type_name in ("completed", "failed"):
        return current_output, None

    item = _resolve_done_item(data, current_output)
    if not item:
        log.warning(f"[stream] done event {event_type} has no target item")
        return current_output, None

    # Part list replacement (content_part.done, reasoning_summary_part.done)
    if type_name in _DONE_PART_FIELDS:
        part = data.get("part")
        if not part:
            return current_output, None
        field, index_key = _DONE_PART_FIELDS[type_name]
        field_list = item.get(field, [])
        idx = data.get(index_key, len(field_list) - 1)
        if 0 <= idx < len(field_list):
            field_list[idx] = part
            return current_output, {}
        return current_output, None

    # Scalar field finalization (text.done, function_call_arguments.done, etc.)
    key = _DONE_KEY_MAP.get(type_name, type_name)
    if key not in data:
        return current_output, None

    final_value = data[key]
    item_type = item.get("type", "")

    if item_type == "function_call":
        item["arguments"] = final_value
    elif item_type == "message":
        content = item.get("content", [])
        idx = data.get("content_index", 0)
        if idx < len(content):
            content[idx][key] = final_value
    elif item_type == "reasoning":
        item["status"] = "completed"
    else:
        item[key] = final_value

    return current_output, {}


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
