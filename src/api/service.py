"""Agent service layer for HTTP and WebSocket clients."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from runtime import RuntimeState


class AgentService:
    """Wraps Cursor agent runtime for async API handlers."""

    def __init__(self, state: RuntimeState) -> None:
        self._state = state

    @property
    def state(self) -> RuntimeState:
        return self._state

    def get_status(self) -> dict[str, Any]:
        from runtime import status_payload

        return status_payload(self._state)

    def get_history(self) -> list[dict[str, str]]:
        return self._state.conversation.get_messages()

    def clear_history(self) -> None:
        self._state.conversation.clear()

    def clear_memory(self) -> None:
        self._state.agent_memory.clear()

    async def run_chat(self, message: str) -> tuple[str, list[dict[str, Any]]]:
        """Run agent in a thread pool; collect streaming events."""
        events: list[dict[str, Any]] = []

        def on_event(event: dict[str, Any]) -> None:
            events.append(event)

        reply = await asyncio.to_thread(
            self._state.assistant.run,
            message,
            on_event,
        )
        return reply, events

    async def stream_chat(self, message: str) -> AsyncGenerator[dict[str, Any], None]:
        """Stream agent events as they occur."""
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_event(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        async def worker() -> None:
            try:
                await asyncio.to_thread(
                    self._state.assistant.run,
                    message,
                    on_event,
                )
            except Exception as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "message": str(e)},
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        task = asyncio.create_task(worker())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

        await task
