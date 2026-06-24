"""MCP client — connects to streamable HTTP or stdio MCP servers."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import TextContent

_EXECUTOR = ThreadPoolExecutor(max_workers=2)


@dataclass(frozen=True)
class MCPToolDefinition:
    """Tool metadata fetched from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


def _run_async(coro):
    """Run async MCP code from sync callers (including inside FastAPI)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    future = _EXECUTOR.submit(asyncio.run, coro)
    return future.result()


class MCPManager:
    """Sync wrapper around an MCP ClientSession."""

    def __init__(
        self,
        transport: str = "http",
        server_url: str | None = None,
        stdio_command: str | None = None,
        stdio_args: list[str] | None = None,
    ) -> None:
        self._transport = transport
        self._server_url = server_url or "http://localhost:8765/mcp"
        self._stdio_command = stdio_command or "docker"
        self._stdio_args = stdio_args or [
            "compose",
            "-f",
            "docker/docker-compose.yml",
            "run",
            "--rm",
            "-i",
            "mcp-agent-tools",
        ]

    def list_tools(self) -> list[MCPToolDefinition]:
        return _run_async(self._list_tools_async())

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return _run_async(self._call_tool_async(name, arguments))

    def health_check(self) -> bool:
        try:
            return len(self.list_tools()) > 0
        except Exception:
            return False

    async def _list_tools_async(self) -> list[MCPToolDefinition]:
        async with self._session() as session:
            response = await session.list_tools()
            return [
                MCPToolDefinition(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema or {"type": "object", "properties": {}},
                )
                for tool in response.tools
            ]

    async def _call_tool_async(self, name: str, arguments: dict[str, Any]) -> str:
        async with self._session() as session:
            result = await session.call_tool(name, arguments=arguments)
            return _format_tool_result(result)

    def _session(self):
        if self._transport == "stdio":
            params = StdioServerParameters(
                command=self._stdio_command,
                args=self._stdio_args,
            )
            return _stdio_session(params)
        return _http_session(self._server_url)


class _stdio_session:
    def __init__(self, params: StdioServerParameters) -> None:
        self._params = params
        self._stack = None

    async def __aenter__(self) -> ClientSession:
        self._read_write = stdio_client(self._params)
        read, write = await self._read_write.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._session.__aexit__(exc_type, exc, tb)
        await self._read_write.__aexit__(exc_type, exc, tb)


class _http_session:
    def __init__(self, url: str) -> None:
        self._url = url

    async def __aenter__(self) -> ClientSession:
        from mcp.client.streamable_http import streamable_http_client

        self._client = streamable_http_client(self._url)
        read, write, _ = await self._client.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._session.__aexit__(exc_type, exc, tb)
        await self._client.__aexit__(exc_type, exc, tb)


def _format_tool_result(result: Any) -> str:
    if result.isError:
        return f"Error: {_extract_text(result.content)}"

    if result.structuredContent is not None:
        content = result.structuredContent
        if isinstance(content, dict) and "result" in content:
            return str(content["result"])
        return json.dumps(content, indent=2)

    text = _extract_text(result.content)
    return text or "(empty tool result)"


def _extract_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if isinstance(block, TextContent):
            parts.append(block.text)
        elif hasattr(block, "text"):
            parts.append(str(block.text))
        else:
            parts.append(str(block))
    return "\n".join(parts).strip()
