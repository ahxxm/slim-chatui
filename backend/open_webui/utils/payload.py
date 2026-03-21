from typing import Any, Optional
from collections.abc import Awaitable, Callable

from open_webui.utils.misc import (
    add_or_update_system_message,
    replace_system_message_content,
)

EventEmitter = Callable[[dict[str, Any]], Awaitable[None]]


class DeltaBatcher:
    """Batch delta emissions to reduce WebSocket traffic."""

    def __init__(self, emit: EventEmitter, chunk_size: int) -> None:
        self._emit = emit
        self._chunk_size = chunk_size
        self._count = 0
        self._pending: dict[str, Any] | None = None

    async def add(self, data: dict[str, Any]) -> None:
        self._count += 1
        self._pending = data
        if self._count >= self._chunk_size:
            await self.flush()

    async def flush(self) -> None:
        if self._pending is not None:
            await self._emit({"type": "chat:completion", "data": self._pending})
            self._count = 0
            self._pending = None

    async def emit_now(self, data: dict[str, Any]) -> None:
        await self.flush()
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
