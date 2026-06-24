"""Bridge MCP tool definitions into the local ToolRegistry."""

from __future__ import annotations

from typing import Any

from mcp_client.manager import MCPManager, MCPToolDefinition
from tools import ToolRegistry


def register_mcp_tools(registry: ToolRegistry, manager: MCPManager) -> int:
    """Register MCP tools on the registry with an mcp_ name prefix."""
    tools = manager.list_tools()
    for tool in tools:
        registry.register_external_tool(
            name=f"mcp_{tool.name}",
            description=tool.description or f"MCP tool: {tool.name}",
            parameters=_normalize_schema(tool.input_schema),
            handler=_make_handler(manager, tool.name),
        )
    return len(tools)


def _make_handler(manager: MCPManager, tool_name: str):
    def handler(**arguments: Any) -> str:
        return manager.call_tool(tool_name, arguments)

    return handler


def _normalize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Ensure tool schema is valid OpenAI function parameters JSON schema."""
    if not schema:
        return {"type": "object", "properties": {}}

    normalized = dict(schema)
    if normalized.get("type") is None:
        normalized["type"] = "object"
    normalized.setdefault("properties", {})
    return normalized
