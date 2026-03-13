import hashlib
import re
import logging
from datetime import timedelta
from typing import Optional
import aiohttp


from open_webui.env import CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE

log = logging.getLogger(__name__)


def get_message_list(messages_map, message_id):
    """
    Reconstructs a list of messages in order up to the specified message_id.

    :param message_id: ID of the message to reconstruct the chain
    :param messages: Message history dict containing all messages
    :return: List of ordered messages starting from the root to the given message
    """

    # Handle case where messages is None
    if not messages_map:
        return []  # Return empty list instead of None to prevent iteration errors

    # Find the message by its id
    current_message = messages_map.get(message_id)

    if not current_message:
        return []  # Return empty list instead of None to prevent iteration errors

    # Reconstruct the chain by following the parentId links
    message_list = []
    visited_message_ids = set()

    while current_message:
        message_id = current_message.get("id")
        if message_id in visited_message_ids:
            # Cycle detected, break to prevent infinite loop
            break

        if message_id is not None:
            visited_message_ids.add(message_id)

        message_list.append(current_message)
        parent_id = current_message.get("parentId")  # Use .get() for safety
        current_message = messages_map.get(parent_id) if parent_id else None

    message_list.reverse()
    return message_list


def get_messages_content(messages: list[dict]) -> str:
    return "\n".join(
        [
            f"{message['role'].upper()}: {get_content_from_message(message)}"
            for message in messages
        ]
    )


def get_last_user_message_item(messages: list[dict]) -> Optional[dict]:
    for message in reversed(messages):
        if message["role"] == "user":
            return message
    return None


def get_content_from_message(message: dict) -> Optional[str]:
    if isinstance(message.get("content"), list):
        for item in message["content"]:
            if item["type"] == "text":
                return item["text"]
    else:
        return message.get("content")
    return None


def convert_output_to_messages(output: list, raw: bool = False) -> list[dict]:
    """
    Convert OR-aligned output items to OpenAI Chat Completion-format messages.

    Handles message and reasoning item types from the Responses API format.

    Args:
        output: List of OR-aligned output items (Responses API format).
        raw: If True, include reasoning blocks (with original tags) for
             LLM re-processing follow-ups.
    """
    if not output or not isinstance(output, list):
        return []

    messages = []
    pending_content = []

    for item in output:
        item_type = item.get("type", "")

        if item_type == "message":
            content_parts = item.get("content", [])
            text = ""
            for part in content_parts:
                if part.get("type") == "output_text":
                    text += part.get("text", "")
            if text:
                pending_content.append(text)

        elif item_type == "reasoning":
            if raw:
                reasoning_text = ""
                source_list = item.get("summary", []) or item.get("content", [])
                for part in source_list:
                    if part.get("type") == "output_text":
                        reasoning_text += part.get("text", "")
                    elif "text" in part:
                        reasoning_text += part.get("text", "")

                if reasoning_text:
                    start_tag = item.get("start_tag", "<think>")
                    end_tag = item.get("end_tag", "</think>")
                    pending_content.append(f"{start_tag}{reasoning_text}{end_tag}")

    if pending_content:
        messages.append(
            {
                "role": "assistant",
                "content": "\n".join(pending_content),
            }
        )

    return messages


def get_last_user_message(messages: list[dict]) -> Optional[str]:
    message = get_last_user_message_item(messages)
    if message is None:
        return None
    return get_content_from_message(message)


def get_last_assistant_message(messages: list[dict]) -> Optional[str]:
    for message in reversed(messages):
        if message["role"] == "assistant":
            return get_content_from_message(message)
    return None


def get_system_message(messages: list[dict]) -> Optional[dict]:
    for message in messages:
        if message["role"] == "system":
            return message
    return None


def update_message_content(message: dict, content: str, append: bool = True) -> dict:
    if isinstance(message["content"], list):
        for item in message["content"]:
            if item["type"] == "text":
                if append:
                    item["text"] = f"{item['text']}\n{content}"
                else:
                    item["text"] = f"{content}\n{item['text']}"
    else:
        if append:
            message["content"] = f"{message['content']}\n{content}"
        else:
            message["content"] = f"{content}\n{message['content']}"
    return message


def replace_system_message_content(content: str, messages: list[dict]) -> dict:
    for message in messages:
        if message["role"] == "system":
            message["content"] = content
            break
    return messages


def add_or_update_system_message(
    content: str, messages: list[dict], append: bool = False
):
    """
    Adds a new system message at the beginning of the messages list
    or updates the existing system message at the beginning.

    :param msg: The message to be added or appended.
    :param messages: The list of message dictionaries.
    :return: The updated list of message dictionaries.
    """

    if messages and messages[0].get("role") == "system":
        messages[0] = update_message_content(messages[0], content, append)
    else:
        # Insert at the beginning
        messages.insert(0, {"role": "system", "content": content})

    return messages


def get_gravatar_url(email):
    # Trim leading and trailing whitespace from
    # an email address and force all characters
    # to lower case
    address = str(email).strip().lower()

    # Create a SHA256 hash of the final string
    hash_object = hashlib.sha256(address.encode())
    hash_hex = hash_object.hexdigest()

    # Grab the actual image URL
    return f"https://www.gravatar.com/avatar/{hash_hex}?d=mp"


def validate_email_format(email: str) -> bool:
    if email.endswith("@localhost"):
        return True

    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))


def sanitize_text_for_db(text: str) -> str:
    """Remove null bytes and invalid UTF-8 surrogates from text for PostgreSQL storage."""
    if not isinstance(text, str):
        return text
    # Remove null bytes
    text = text.replace("\x00", "").replace("\u0000", "")
    # Remove invalid UTF-8 surrogate characters that can cause encoding errors
    # This handles cases where binary data or encoding issues introduced surrogates
    try:
        text = text.encode("utf-8", errors="surrogatepass").decode(
            "utf-8", errors="ignore"
        )
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


def sanitize_data_for_db(obj):
    """Recursively sanitize all strings in a data structure for database storage."""
    if isinstance(obj, str):
        return sanitize_text_for_db(obj)
    elif isinstance(obj, dict):
        return {k: sanitize_data_for_db(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_data_for_db(v) for v in obj]
    return obj


def parse_duration(duration: str) -> Optional[timedelta]:
    if duration == "-1" or duration == "0":
        return None

    # Regular expression to find number and unit pairs
    pattern = r"(-?\d+(\.\d+)?)(ms|s|m|h|d|w)"
    matches = re.findall(pattern, duration)

    if not matches:
        raise ValueError("Invalid duration string")

    total_duration = timedelta()

    for number, _, unit in matches:
        number = float(number)
        if unit == "ms":
            total_duration += timedelta(milliseconds=number)
        elif unit == "s":
            total_duration += timedelta(seconds=number)
        elif unit == "m":
            total_duration += timedelta(minutes=number)
        elif unit == "h":
            total_duration += timedelta(hours=number)
        elif unit == "d":
            total_duration += timedelta(days=number)
        elif unit == "w":
            total_duration += timedelta(weeks=number)

    return total_duration


async def cleanup_response(
    response: Optional[aiohttp.ClientResponse],
    session: Optional[aiohttp.ClientSession],
):
    if response:
        response.close()
    if session:
        await session.close()


async def stream_wrapper(response, session, content_handler=None):
    """
    Wrap a stream to ensure cleanup happens even if streaming is interrupted.
    This is more reliable than BackgroundTask which may not run if client disconnects.
    """
    try:
        stream = (
            content_handler(response.content) if content_handler else response.content
        )
        async for chunk in stream:
            yield chunk
    finally:
        await cleanup_response(response, session)


def stream_chunks_handler(stream: aiohttp.StreamReader):
    """
    Handle stream response chunks, supporting large data chunks that exceed the original 16kb limit.
    When a single line exceeds max_buffer_size, returns an empty JSON string {} and skips subsequent data
    until encountering normally sized data.

    :param stream: The stream reader to handle.
    :return: An async generator that yields the stream data.
    """

    max_buffer_size = CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE
    if max_buffer_size is None or max_buffer_size <= 0:
        return stream

    async def yield_safe_stream_chunks():
        buffer = b""
        skip_mode = False

        async for data, _ in stream.iter_chunks():
            if not data:
                continue

            # In skip_mode, if buffer already exceeds the limit, clear it (it's part of an oversized line)
            if skip_mode and len(buffer) > max_buffer_size:
                buffer = b""

            lines = (buffer + data).split(b"\n")

            # Process complete lines (except the last possibly incomplete fragment)
            for i in range(len(lines) - 1):
                line = lines[i]

                if skip_mode:
                    # Skip mode: check if current line is small enough to exit skip mode
                    if len(line) <= max_buffer_size:
                        skip_mode = False
                        yield line
                    else:
                        yield b"data: {}"
                        yield b"\n"
                else:
                    # Normal mode: check if line exceeds limit
                    if len(line) > max_buffer_size:
                        skip_mode = True
                        yield b"data: {}"
                        yield b"\n"
                        log.info(f"Skip mode triggered, line size: {len(line)}")
                    else:
                        yield line
                        yield b"\n"

            # Save the last incomplete fragment
            buffer = lines[-1]

            # Check if buffer exceeds limit
            if not skip_mode and len(buffer) > max_buffer_size:
                skip_mode = True
                log.info(f"Skip mode triggered, buffer size: {len(buffer)}")
                # Clear oversized buffer to prevent unlimited growth
                buffer = b""

        # Process remaining buffer data
        if buffer and not skip_mode:
            yield buffer
            yield b"\n"

    return yield_safe_stream_chunks()
