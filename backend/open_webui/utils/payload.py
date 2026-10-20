from typing import Any, Optional
from collections.abc import Awaitable, Callable

from open_webui.utils.misc import (
    add_or_update_system_message,
    replace_system_message_content,
)

EventEmitter = Callable[[dict[str, Any]], Awaitable[None]]


class ContentStream:
    """Send content as ``content_delta`` insertions at ``offset``, or a ``content``
    snapshot when earlier text was rewritten."""

    def __init__(
        self, emit: EventEmitter, chunk_size: int, initial_content: str = ""
    ) -> None:
        self._emit = emit
        self._chunk_size = chunk_size
        self._sent = initial_content
        self._pending = ""
        self._pending_offset = 0
        self._count = 0

    async def push(self, content: str) -> None:
        if content == self._sent:
            return

        insertion = _insertion(self._sent, content)
        self._sent = content

        if insertion is None:
            await self.flush()
            await self._send({"content": content})
            return

        await self._enqueue(*insertion)

    async def _enqueue(self, offset: int, text: str) -> None:
        if self._pending and offset != self._pending_offset + len(self._pending):
            await self.flush()

        if not self._pending:
            self._pending_offset = offset

        self._pending += text
        self._count += 1
        if self._count >= self._chunk_size:
            await self.flush()

    async def emit_metadata(self, data: dict[str, Any]) -> None:
        await self.flush()
        await self._send(data)

    async def flush(self) -> None:
        if not self._pending:
            return

        content_delta = self._pending
        offset = self._pending_offset
        self._pending = ""
        self._count = 0
        await self._send({"content_delta": content_delta, "offset": offset})

    async def _send(self, data: dict[str, Any]) -> None:
        await self._emit({"type": "chat:completion", "data": data})


def _insertion(old: str, new: str) -> tuple[int, str] | None:
    """Return (offset, text) when ``new`` equals ``old`` plus an insertion, else None."""
    prefix = 0
    limit = min(len(old), len(new))
    while prefix < limit and old[prefix] == new[prefix]:
        prefix += 1

    suffix = old[prefix:]
    if not new.endswith(suffix):
        return None

    end = len(new) - len(suffix)
    if end <= prefix:
        return None

    return prefix, new[prefix:end]


# inplace function: form_data is modified
def apply_system_prompt_to_body(
    system: Optional[str],
    form_data: dict,
    replace: bool = False,
) -> dict:
    if not system:
        return form_data

    if replace:
        form_data["messages"] = replace_system_message_content(
            system, form_data.get("messages", [])
        )
    else:
        form_data["messages"] = add_or_update_system_message(
            system, form_data.get("messages", [])
        )

    return form_data
