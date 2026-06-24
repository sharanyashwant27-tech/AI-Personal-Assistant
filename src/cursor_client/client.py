"""High-level Cursor IDE chat client using the reverse-engineered wire protocol."""

from __future__ import annotations

import asyncio
import contextlib
import io
from typing import Any

import httpx

from cursor_client._vendor import ensure_vendor_path
from cursor_client.decoder_utils import extract_assistant_text


class CursorChatClient:
    """Send chat requests through Cursor's backend using local IDE auth tokens."""

    def __init__(
        self,
        model: str = "default",
        ghost_mode: bool = True,
        backend_url: str | None = None,
    ) -> None:
        ensure_vendor_path()
        from cursor_http2_client import CursorHTTP2Client  # noqa: WPS433
        from cursor_streaming_decoder import CursorStreamDecoder  # noqa: WPS433

        self._engine_cls = CursorHTTP2Client
        self._decoder_cls = CursorStreamDecoder
        self._model = model
        self._ghost_mode = ghost_mode
        self._backend_url = backend_url

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Run a chat completion synchronously and return assistant text."""
        return asyncio.run(self.complete_async(messages))

    async def complete_async(self, messages: list[dict[str, str]]) -> str:
        """Run a chat completion asynchronously and return assistant text."""
        prompt = self._flatten_messages(messages)
        if not prompt.strip():
            raise ValueError("Message cannot be empty.")

        client = self._engine_cls()
        if self._backend_url:
            client.base_url = self._backend_url.rstrip("/")
            client.base_host = client._extract_host(client.base_url)  # noqa: SLF001
        client.ghost_mode = self._ghost_mode

        auth_token = client.get_active_token()
        if not auth_token:
            raise RuntimeError(
                "No Cursor auth token found. Log in to the Cursor IDE first."
            )
        if "::" in auth_token:
            auth_token = auth_token.split("::", 1)[1]

        session_id = client.generate_session_id(auth_token)
        client_key = client.generate_hashed_64_hex(auth_token)
        cursor_checksum = client.generate_cursor_checksum(auth_token)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            session_ok = await client.establish_session_http2(
                auth_token, session_id, client_key, cursor_checksum
            )
            if not session_ok:
                raise RuntimeError(
                    "Cursor session preflight failed (AvailableModels). "
                    "Ensure Cursor IDE is logged in and your subscription is active."
                )

            payload = [{"role": "user", "content": prompt}]
            result = await self._send_chat(
                client,
                payload,
                auth_token,
                session_id,
                client_key,
                cursor_checksum,
            )
        if not result or not result.strip():
            raise RuntimeError("Cursor returned an empty response.")
        return result.strip()

    async def _send_chat(
        self,
        client: Any,
        messages: list[dict[str, str]],
        auth_token: str,
        session_id: str,
        client_key: str,
        cursor_checksum: str,
    ) -> str | None:
        """Stream chat over HTTP/2 and decode assistant content."""
        cursor_body = client.generate_cursor_body_exact(messages, self._model)
        chat_url = (
            f"{client.base_url}/aiserver.v1.ChatService/StreamUnifiedChatWithTools"
        )
        headers = client.build_common_headers(
            auth_token, session_id, client_key, cursor_checksum
        )
        headers["connect-accept-encoding"] = "gzip"
        headers["content-type"] = "application/connect+proto"

        decoder = self._decoder_cls()
        stream_messages: list[tuple[str, str]] = []

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            async with httpx.AsyncClient(http2=True, timeout=120.0) as http_client:
                async with http_client.stream(
                    "POST", chat_url, headers=headers, content=cursor_body
                ) as response:
                    if response.status_code == 401:
                        refreshed = client.refresh_access_token()
                        if refreshed and refreshed != auth_token:
                            auth_token = refreshed.split("::", 1)[-1]
                            session_id = client.generate_session_id(auth_token)
                            client_key = client.generate_hashed_64_hex(auth_token)
                            cursor_checksum = client.generate_cursor_checksum(auth_token)
                            headers = client.build_common_headers(
                                auth_token, session_id, client_key, cursor_checksum
                            )
                            headers["connect-accept-encoding"] = "gzip"
                            headers["content-type"] = "application/connect+proto"
                            return await self._send_chat(
                                client,
                                messages,
                                auth_token,
                                session_id,
                                client_key,
                                cursor_checksum,
                            )
                        raise RuntimeError(
                            "Cursor auth token expired and refresh failed."
                        )

                    if response.status_code != 200:
                        error_body = await response.aread()
                        snippet = error_body.decode("utf-8", errors="ignore")[:300]
                        raise RuntimeError(
                            f"Cursor chat failed ({response.status_code}): {snippet}"
                        )

                    async for chunk in response.aiter_bytes():
                        for message in decoder.feed_data(chunk):
                            stream_messages.append((message.msg_type, message.content))
                            if message.msg_type == "error":
                                raise RuntimeError(message.content)
                            if message.msg_type == "stream_end":
                                break

        return extract_assistant_text(stream_messages)

    @staticmethod
    def _flatten_messages(messages: list[dict[str, str]]) -> str:
        """Convert OpenAI-style messages into one Cursor user prompt."""
        sections: list[str] = []
        for message in messages:
            role = message.get("role", "user").strip().lower()
            content = message.get("content", "").strip()
            if not content:
                continue
            if role == "system":
                sections.append(f"System instructions:\n{content}")
            elif role == "assistant":
                sections.append(f"Assistant:\n{content}")
            else:
                sections.append(f"User:\n{content}")
        return "\n\n".join(sections)
