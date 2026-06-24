"""Configuration — Cursor-only settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "config" / "system_prompt.txt"
CONVERSATION_PATH = PROJECT_ROOT / "data" / "conversation.json"
AGENT_MEMORY_PATH = PROJECT_ROOT / "data" / "agent_memory.json"
DOCKER_COMPOSE_PATH = PROJECT_ROOT / "docker" / "docker-compose.yml"


@dataclass(frozen=True)
class Settings:
    """Application settings — Cursor subscription + MCP only."""

    agent_mode: bool
    cursor_agent_protocol: str
    cursor_model: str
    cursor_ghost_mode: bool
    cursor_backend_url: str | None
    mcp_enabled: bool
    mcp_transport: str
    mcp_server_url: str
    mcp_stdio_command: str
    mcp_stdio_args: list[str]
    system_prompt_path: Path
    conversation_path: Path
    agent_memory_path: Path
    agent_max_tool_iterations: int
    api_host: str
    api_port: int


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    load_dotenv(ENV_FILE)

    return Settings(
        agent_mode=_env_bool("AGENT_MODE", True),
        cursor_agent_protocol=os.getenv("CURSOR_AGENT_PROTOCOL", "wire")
        .strip()
        .lower(),
        cursor_model=os.getenv("CURSOR_MODEL", "default"),
        cursor_ghost_mode=_env_bool("CURSOR_GHOST_MODE", True),
        cursor_backend_url=os.getenv("CURSOR_BACKEND_URL", "").strip() or None,
        mcp_enabled=_env_bool("MCP_ENABLED", True),
        mcp_transport=os.getenv("MCP_TRANSPORT", "http").strip().lower(),
        mcp_server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8765/mcp").strip(),
        mcp_stdio_command=os.getenv("MCP_STDIO_COMMAND", "docker").strip(),
        mcp_stdio_args=os.getenv(
            "MCP_STDIO_ARGS",
            f"compose -f {DOCKER_COMPOSE_PATH} run --rm -i -e MCP_TRANSPORT=stdio mcp-agent-tools",
        ).split(),
        system_prompt_path=SYSTEM_PROMPT_PATH,
        conversation_path=CONVERSATION_PATH,
        agent_memory_path=AGENT_MEMORY_PATH,
        agent_max_tool_iterations=int(os.getenv("AGENT_MAX_TOOL_ITERATIONS", "8")),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8787")),
    )
