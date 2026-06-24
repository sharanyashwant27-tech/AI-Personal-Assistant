"""Application runtime — bootstrap Cursor agent, tools, and MCP."""

from __future__ import annotations

from dataclasses import dataclass

from agent_memory import AgentMemory
from config import Settings, load_settings
from cursor_agent_assistant import CursorAgentAssistant
from memory import ConversationMemory
from mcp_client.bridge import register_mcp_tools
from mcp_client.manager import MCPManager
from tools import ToolRegistry


@dataclass
class RuntimeState:
    """Live application state shared by CLI and API."""

    settings: Settings
    conversation: ConversationMemory
    agent_memory: AgentMemory
    tool_registry: ToolRegistry
    mcp_manager: MCPManager | None
    assistant: CursorAgentAssistant
    mcp_tool_count: int


def create_runtime() -> RuntimeState:
    """Initialize Cursor-only agent runtime with optional MCP tools."""
    settings = load_settings()
    conversation = ConversationMemory(settings.conversation_path)
    agent_memory = AgentMemory(settings.agent_memory_path)
    tool_registry = ToolRegistry(None, agent_memory)

    mcp_manager: MCPManager | None = None
    mcp_tool_count = 0

    if settings.mcp_enabled:
        mcp_manager = MCPManager(
            transport=settings.mcp_transport,
            server_url=settings.mcp_server_url,
            stdio_command=settings.mcp_stdio_command,
            stdio_args=settings.mcp_stdio_args,
        )
        try:
            mcp_tool_count = register_mcp_tools(tool_registry, mcp_manager)
        except Exception:
            mcp_manager = None

    assistant = CursorAgentAssistant(
        settings,
        conversation,
        tool_registry,
        agent_memory,
        retrieval=None,
    )

    return RuntimeState(
        settings=settings,
        conversation=conversation,
        agent_memory=agent_memory,
        tool_registry=tool_registry,
        mcp_manager=mcp_manager,
        assistant=assistant,
        mcp_tool_count=mcp_tool_count,
    )


def status_payload(state: RuntimeState) -> dict:
    """Serialize runtime status for the UI."""
    mcp_online = False
    if state.mcp_manager is not None:
        try:
            mcp_online = state.mcp_manager.health_check()
        except Exception:
            mcp_online = False

    return {
        "backend": "cursor",
        "agent_mode": state.settings.agent_mode,
        "cursor_model": state.settings.cursor_model,
        "ghost_mode": state.settings.cursor_ghost_mode,
        "mcp_enabled": state.settings.mcp_enabled,
        "mcp_online": mcp_online,
        "mcp_url": state.settings.mcp_server_url,
        "mcp_tool_count": state.mcp_tool_count,
        "tools": state.tool_registry.get_tool_names(),
        "message_count": len(state.conversation.get_messages()),
        "fact_count": len(state.agent_memory.get_facts()),
        "auto_mode": state.settings.cursor_agent_protocol,
        "auto_note": (
            "wire = Cursor Auto (chatModeEnum=2) with IDE tool execution. "
            "react = Ask mode + local JSON/MCP loop."
        ),
    }
