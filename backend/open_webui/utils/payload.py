from typing import Any, Optional
from collections.abc import Awaitable, Callable

from open_webui.utils.misc import (
    add_or_update_system_message,
    replace_system_message_content,
)

EventEmitter = Callable[[dict[str, Any]], Awaitable[None]]


class ContentStream:
    """Send content as ``content_delta`` appends, or a ``content`` snapshot when
    the new text no longer extends what was already sent (earlier text was rewritten).
    """

    def __init__(
        self, emit: EventEmitter, chunk_size: int, initial_content: str = ""
    ) -> None:
        self._emit = emit
        self._chunk_size = chunk_size
        self._sent = initial_content
        self._pending = ""
        self._count = 0

    async def push(self, content: str) -> None:
        if not content.startswith(self._sent):
            self._sent = content
            await self.flush()
            await self._send({"content": content})
            return

        delta = content[len(self._sent) :]
        if not delta:
            return

        self._sent = content
        self._pending += delta
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
        self._pending = ""
        self._count = 0
        await self._send({"content_delta": content_delta})

    async def _send(self, data: dict[str, Any]) -> None:
        await self._emit({"type": "chat:completion", "data": data})


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
