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
from cursor_client.decoder_utils import (
    extract_wire_answer,
    merge_thinking_chunks,
    _looks_like_reasoning,
    _looks_like_tool_payload,
)
from cursor_client.tool_call_parser import (
    parse_redacted_tool_calls,
    strip_tool_markup,
)
from cursor_client.workspace_executor import WorkspaceToolExecutor

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
        client.tool_executor = WorkspaceToolExecutor(self._workspace)
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

        last_prose_answer = ""
        tools_ran = False
        empty_rounds = 0
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
                thinking_text = merge_thinking_chunks(thinking_parts)

                if not tool_calls:
                    for tc_dict in parse_redacted_tool_calls(thinking_text):
                        tc = _dict_to_tool_call(tc_dict, name_to_enum)
                        if tc.tool_call_id not in seen_ids:
                            seen_ids.add(tc.tool_call_id)
                            tool_calls.append(tc)

                if not tool_calls:
                    answer = extract_wire_answer(stream_messages)
                    if not answer:
                        answer = strip_tool_markup(thinking_text).strip()
                        if answer and (
                            answer.startswith("{") or _looks_like_reasoning(answer)
                        ):
                            answer = ""

                    if answer:
                        last_prose_answer = answer
                        self._emit(
                            on_event,
                            "assistant",
                            {"content": answer, "iteration": iteration},
                        )
                        self._emit(on_event, "final", {"content": answer})
                        return answer

                    empty_rounds += 1
                    if empty_rounds >= 2:
                        break
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Provide your final answer now in plain English "
                                "(2-4 sentences). Do not repeat raw JSON or tool output."
                            ),
                        }
                    )
                    continue

                empty_rounds = 0
                tools_ran = True

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
                                "When finished, reply with a plain-English summary only."
                            ),
                        }
                    )

            if tools_ran and not last_prose_answer:
                summary = await self._request_prose_summary(
                    http=http,
                    url=url,
                    messages=messages,
                    client=client,
                    auth_token=auth_token,
                    session_id=session_id,
                    client_key=client_key,
                    cursor_checksum=cursor_checksum,
                    conversation_id=conversation_id,
                    decoder=decoder,
                    on_event=on_event,
                )
                if summary:
                    self._emit(on_event, "assistant", {"content": summary})
                    self._emit(on_event, "final", {"content": summary})
                    return summary

            fallback = _prose_fallback_from_messages(messages)
            if fallback:
                self._emit(on_event, "assistant", {"content": fallback})
                self._emit(on_event, "final", {"content": fallback})
                return fallback

            if last_prose_answer:
                self._emit(on_event, "assistant", {"content": last_prose_answer})
                self._emit(on_event, "final", {"content": last_prose_answer})
                return last_prose_answer

        raise RuntimeError(
            f"Wire agent exceeded max tool iterations ({self._max_iterations})."
        )

    async def _request_prose_summary(
        self,
        *,
        http: httpx.AsyncClient,
        url: str,
        messages: list[dict[str, str]],
        client: Any,
        auth_token: str,
        session_id: str,
        client_key: str,
        cursor_checksum: str,
        conversation_id: str | None,
        decoder: Any,
        on_event: EventCallback | None,
    ) -> str:
        """One final model round to synthesize prose from tool results."""
        messages.append(
            {
                "role": "user",
                "content": (
                    "Summarize your findings for the original question in 2-4 clear "
                    "sentences. Plain English only — no JSON, no code blocks."
                ),
            }
        )
        self._emit(on_event, "thinking", {"iteration": self._max_iterations + 1})

        headers = client.get_headers(
            auth_token, session_id, client_key, cursor_checksum
        )
        if conversation_id:
            headers["x-conversation-id"] = conversation_id

        body = client.generate_request_body(messages, self._model)
        decoder.buffer = bytearray()
        stream_messages: list[tuple[str, str]] = []

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            async with http.stream("POST", url, headers=headers, content=body) as response:
                if response.status_code != 200:
                    return ""
                async for chunk in response.aiter_bytes():
                    for msg in decoder.feed_data(chunk):
                        stream_messages.append((msg.msg_type, msg.content))

        answer = extract_wire_answer(stream_messages)
        if not answer:
            raw = "".join(t for k, t in stream_messages if k == "thinking")
            answer = strip_tool_markup(raw).strip()
            if _looks_like_reasoning(answer) or _looks_like_tool_payload(answer):
                answer = ""
        return strip_tool_markup(answer).strip()

    @staticmethod
    def _emit(on_event: EventCallback | None, kind: str, data: dict[str, Any]) -> None:
        if on_event:
            on_event({"type": kind, **data})


def _prose_fallback_from_messages(messages: list[dict[str, str]]) -> str:
    """Plain-English fallback when the model won't emit a final summary."""
    tool_ran = False
    read_snippet = ""
    for msg in reversed(messages):
        content = msg.get("content", "")
        if not content.startswith("Tool `"):
            continue
        tool_ran = True
        if "read_file" in content and "normalize_tool_params" in content:
            read_snippet = content
            break

    if read_snippet and "_extract_pattern" in read_snippet:
        return (
            "Grep tool params are normalized by `normalize_tool_params()`, which "
            "canonicalizes the tool name and calls `_normalize_params` for ripgrep/grep. "
            "`_extract_pattern` maps `query`, `search`, or nested `pattern_info` into "
            "`pattern`, and `path`/`target_directory` become `search_path` for the executor."
        )

    if tool_ran:
        return (
            "The agent finished running tools successfully. "
            "See the agent panel for directory listings, search matches, and file contents."
        )
    return ""


def _build_name_to_enum(ClientSideToolV2) -> dict[str, int]:
    return {
        "list_dir": ClientSideToolV2.LIST_DIR,
        "read_file": ClientSideToolV2.READ_FILE,
        "ripgrep_search": ClientSideToolV2.RIPGREP_SEARCH,
        "grep_search": ClientSideToolV2.RIPGREP_SEARCH,
        "grep": ClientSideToolV2.RIPGREP_SEARCH,
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
    from cursor_client.tool_call_parser import normalize_tool_params

    if isinstance(params, dict):
        params = normalize_tool_params(name, params)
    tool_id = int(data.get("tool") or 0) or name_to_enum.get(name, 0)
    return ToolCall(
        tool=int(tool_id),
        tool_call_id=data.get("tool_call_id") or f"toolu_{id(data)}",
        name=name or "unknown",
        raw_args=raw_args or json.dumps(params),
        params=params if isinstance(params, dict) else {},
    )


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

    if isinstance(params, dict):
        from cursor_client.tool_call_parser import normalize_tool_params  # noqa: WPS433

        params = normalize_tool_params(name or "unknown", params)

    if not name and not tool_num:
        return None

    return ToolCall(
        tool=tool_num,
        tool_call_id=tool_call_id,
        name=name,
        raw_args=raw_args,
        params=params if isinstance(params, dict) else {},
    )
