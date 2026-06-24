"""Cursor IDE Auto mode — chatModeEnum=2 wire protocol with local tool execution."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from cursor_client._vendor import ensure_vendor_path
from cursor_client.decoder_utils import _unescape_thinking_chunk
from cursor_client.tool_call_parser import (
    parse_redacted_tool_calls,
    strip_tool_markup,
)

EventCallback = Callable[[dict[str, Any]], None]


class CursorWireAgent:
    """Agent mode client (chatModeEnum=2) with local tool round-trip."""

    def __init__(
        self,
        workspace_root: str | Path,
        model: str = "default",
        ghost_mode: bool = True,
        max_tool_iterations: int = 10,
        backend_url: str | None = None,
    ) -> None:
        self._workspace = Path(workspace_root).resolve()
        self._model = model
        self._ghost_mode = ghost_mode
        self._max_iterations = max_tool_iterations
        self._backend_url = backend_url

    def run(self, prompt: str, on_event: EventCallback | None = None) -> str:
        return asyncio.run(self.run_async(prompt, on_event))

    async def run_async(
        self,
        prompt: str,
        on_event: EventCallback | None = None,
    ) -> str:
        ensure_vendor_path()
        from cursor_agent_client import (  # noqa: WPS433
            ClientSideToolV2,
            CursorAgentClient,
            ToolCall,
        )
        from cursor_chat_proto import ToolCallDecoder  # noqa: WPS433
        from cursor_streaming_decoder import CursorStreamDecoder  # noqa: WPS433

        client = CursorAgentClient(workspace_root=str(self._workspace))
        client.ghost_mode = self._ghost_mode
        if self._backend_url:
            client.base_url = self._backend_url.rstrip("/")
            client.base_host = client.runtime._extract_host(client.base_url)  # noqa: SLF001

        auth_token = client.runtime.get_active_token() or client.token
        if not auth_token:
            raise RuntimeError(
                "No Cursor auth token. Log in to the Cursor IDE first."
            )
        if "::" in auth_token:
            auth_token = auth_token.split("::", 1)[1]

        session_id = client.generate_session_id(auth_token)
        client_key = client.generate_hashed_64_hex(auth_token)
        cursor_checksum = client.generate_cursor_checksum(auth_token)
        conversation_id = None

        name_to_enum = _build_name_to_enum(ClientSideToolV2)
        decoder = CursorStreamDecoder()
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
        url = f"{client.base_url}/aiserver.v1.ChatService/StreamUnifiedChatWithTools"

        self._emit(on_event, "agent_start", {"mode": "wire", "model": self._model})

        async with httpx.AsyncClient(http2=True, timeout=120.0) as http:
            for iteration in range(1, self._max_iterations + 1):
                self._emit(on_event, "thinking", {"iteration": iteration})

                headers = client.get_headers(
                    auth_token, session_id, client_key, cursor_checksum
                )
                if conversation_id:
                    headers["x-conversation-id"] = conversation_id

                body = client.generate_request_body(messages, self._model)
                decoder.buffer = bytearray()

                stream_messages: list[tuple[str, str]] = []
                raw_chunks: list[bytes] = []
                tool_calls: list[ToolCall] = []
                seen_ids: set[str] = set()

                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                    io.StringIO()
                ):
                    async with http.stream(
                        "POST", url, headers=headers, content=body
                    ) as response:
                        if response.status_code == 401:
                            raise RuntimeError(
                                "Cursor auth expired. Re-login in Cursor IDE."
                            )
                        if response.status_code != 200:
                            err = (await response.aread()).decode(
                                "utf-8", errors="ignore"
                            )[:400]
                            raise RuntimeError(
                                f"Cursor agent failed ({response.status_code}): {err}"
                            )

                        async for chunk in response.aiter_bytes():
                            raw_chunks.append(chunk)
                            for msg in decoder.feed_data(chunk):
                                stream_messages.append((msg.msg_type, msg.content))
                                if msg.msg_type == "tool_call":
                                    tc = _tool_call_from_debug_str(
                                        msg.content, name_to_enum
                                    )
                                    if tc and tc.tool_call_id not in seen_ids:
                                        seen_ids.add(tc.tool_call_id)
                                        tool_calls.append(tc)

                            for tc_dict in ToolCallDecoder.find_tool_calls(chunk):
                                tc = _dict_to_tool_call(tc_dict, name_to_enum)
                                if tc.tool_call_id not in seen_ids:
                                    seen_ids.add(tc.tool_call_id)
                                    tool_calls.append(tc)

                thinking_parts = [t for k, t in stream_messages if k == "thinking" and t]
                thinking_text = _merge_thinking_text(thinking_parts)

                if not tool_calls:
                    for tc_dict in parse_redacted_tool_calls(thinking_text):
                        tc = _dict_to_tool_call(tc_dict, name_to_enum)
                        if tc.tool_call_id not in seen_ids:
                            seen_ids.add(tc.tool_call_id)
                            tool_calls.append(tc)

                if not tool_calls:
                    answer = _final_from_thinking(thinking_text)
                    answer = strip_tool_markup(answer)
                    if answer:
                        self._emit(
                            on_event,
                            "assistant",
                            {"content": answer, "iteration": iteration},
                        )
                        self._emit(on_event, "final", {"content": answer})
                        return answer
                    continue

                for tool_call in tool_calls:
                    self._emit(
                        on_event,
                        "tool_start",
                        {
                            "iteration": iteration,
                            "tool": tool_call.name,
                            "arguments": tool_call.params,
                        },
                    )
                    result = client.tool_executor.execute(tool_call)
                    result_text = (
                        json.dumps(result.data, indent=2)
                        if result.success
                        else f"Error: {result.error}"
                    )
                    self._emit(
                        on_event,
                        "tool_result",
                        {
                            "iteration": iteration,
                            "tool": tool_call.name,
                            "result": result_text[:4000],
                        },
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Tool `{tool_call.name}` completed.\n"
                                f"Result:\n{result_text}\n\n"
                                "Continue the original task. "
                                "If done, reply with the final answer only."
                            ),
                        }
                    )

        raise RuntimeError(
            f"Wire agent exceeded max tool iterations ({self._max_iterations})."
        )

    @staticmethod
    def _emit(on_event: EventCallback | None, kind: str, data: dict[str, Any]) -> None:
        if on_event:
            on_event({"type": kind, **data})


def _build_name_to_enum(ClientSideToolV2) -> dict[str, int]:
    return {
        "list_dir": ClientSideToolV2.LIST_DIR,
        "read_file": ClientSideToolV2.READ_FILE,
        "ripgrep_search": ClientSideToolV2.RIPGREP_SEARCH,
        "grep_search": ClientSideToolV2.RIPGREP_SEARCH,
        "run_terminal_command": ClientSideToolV2.RUN_TERMINAL_COMMAND_V2,
        "edit_file": ClientSideToolV2.EDIT_FILE,
        "file_search": ClientSideToolV2.FILE_SEARCH,
        "glob_file_search": ClientSideToolV2.GLOB_FILE_SEARCH,
        "glob": ClientSideToolV2.GLOB_FILE_SEARCH,
    }


def _dict_to_tool_call(data: dict[str, Any], name_to_enum: dict[str, int]):
    from cursor_agent_client import ToolCall  # noqa: WPS433

    name = (data.get("name") or "").lower()
    params = data.get("params") or {}
    raw_args = data.get("raw_args") or ""
    if not params and raw_args:
        try:
            params = json.loads(raw_args)
        except json.JSONDecodeError:
            params = {}
    tool_id = int(data.get("tool") or 0) or name_to_enum.get(name, 0)
    return ToolCall(
        tool=int(tool_id),
        tool_call_id=data.get("tool_call_id") or f"toolu_{id(data)}",
        name=name or "unknown",
        raw_args=raw_args or json.dumps(params),
        params=params if isinstance(params, dict) else {},
    )


def _merge_thinking_text(thinking_parts: list[str]) -> str:
    combined = "".join(thinking_parts)
    quoted = re.findall(r'text:\s*"((?:\\.|[^"\\])*)"', combined)
    if quoted:
        return "".join(_unescape_thinking_chunk(chunk) for chunk in quoted)
    return combined


def _final_from_thinking(text: str) -> str:
    """Extract user-visible answer from thinking stream tail."""
    if not text:
        return ""
    text = strip_tool_markup(text)
    for marker in (
        "<" + "\uff5c" + "final" + "\uff5c" + ">",
        "<|final|>",
        "FINAL:",
    ):
        if marker in text:
            tail = text.split(marker, 1)[-1].strip()
            if tail and "tool_call_begin" not in tail.lower():
                return tail
    close_think = "</" + "redacted_thinking" + ">"
    if close_think in text:
        tail = text.split(close_think, 1)[-1].strip()
        if tail and "tool_call_begin" not in tail.lower():
            return tail
    if "tool_call_begin" in text.lower():
        return ""
    return text.strip()


def _tool_call_from_debug_str(text: str, name_to_enum: dict[str, int]):
    from cursor_agent_client import ToolCall  # noqa: WPS433

    if not text:
        return None
    name_match = re.search(r"name:\s*\"?([^\"\n]+)\"?", text)
    id_match = re.search(r"tool_call_id:\s*\"?([^\"\n]+)\"?", text)
    args_match = re.search(r"raw_args:\s*\"((?:\\.|[^\"\\])*)\"", text)
    tool_match = re.search(r"tool:\s*(\d+)", text)

    name = name_match.group(1).strip() if name_match else ""
    tool_call_id = id_match.group(1).strip() if id_match else f"toolu_{hash(text)}"
    raw_args = args_match.group(1) if args_match else "{}"
    tool_num = int(tool_match.group(1)) if tool_match else name_to_enum.get(name, 0)

    try:
        params = json.loads(raw_args.replace("\\\"", '"').replace("\\n", "\n"))
    except json.JSONDecodeError:
        params = {}

    if not name and not tool_num:
        return None

    return ToolCall(
        tool=tool_num,
        tool_call_id=tool_call_id,
        name=name,
        raw_args=raw_args,
        params=params if isinstance(params, dict) else {},
    )
