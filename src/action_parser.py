"""Parse structured tool actions from Cursor agent responses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolAction:
    """A tool invocation parsed from an agent response."""

    name: str
    arguments: dict


@dataclass(frozen=True)
class ParsedAgentResponse:
    """Parsed agent output — either a final answer or a tool call."""

    is_final: bool
    final_text: str | None = None
    tool_action: ToolAction | None = None


_TOOL_JSON_PATTERN = re.compile(
    r'\{\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}',
    re.DOTALL,
)
_FINAL_PREFIX = re.compile(r"^FINAL:\s*", re.IGNORECASE | re.MULTILINE)
_CURSOR_FINAL = re.compile(r"^<[\uff5c|]final[\uff5c|]>\s*", re.IGNORECASE)


def _clean_response_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = _CURSOR_FINAL.sub("", cleaned)
    return cleaned.strip()


def parse_agent_response(text: str) -> ParsedAgentResponse:
    """Extract a tool call or final answer from a Cursor agent message."""
    cleaned = _clean_response_text(text)
    if not cleaned:
        return ParsedAgentResponse(is_final=True, final_text="")

    final_match = _FINAL_PREFIX.search(cleaned)
    if final_match:
        return ParsedAgentResponse(
            is_final=True,
            final_text=cleaned[final_match.end() :].strip(),
        )

    tool_match = _TOOL_JSON_PATTERN.search(cleaned)
    if tool_match:
        tool_name = tool_match.group(1)
        try:
            arguments = json.loads(tool_match.group(2))
        except json.JSONDecodeError:
            return ParsedAgentResponse(is_final=True, final_text=cleaned)
        if not isinstance(arguments, dict):
            arguments = {}
        return ParsedAgentResponse(
            is_final=False,
            tool_action=ToolAction(name=tool_name, arguments=arguments),
        )

    if cleaned.startswith("{") and '"tool"' in cleaned:
        try:
            payload = json.loads(cleaned)
            if isinstance(payload, dict) and "tool" in payload:
                arguments = payload.get("arguments", {})
                if not isinstance(arguments, dict):
                    arguments = {}
                return ParsedAgentResponse(
                    is_final=False,
                    tool_action=ToolAction(
                        name=str(payload["tool"]),
                        arguments=arguments,
                    ),
                )
        except json.JSONDecodeError:
            pass

    return ParsedAgentResponse(is_final=True, final_text=cleaned)


def build_agent_system_prompt(tool_names: list[str]) -> str:
    """Build ReAct instructions for Cursor-backed agent mode."""
    tools_list = ", ".join(tool_names) if tool_names else "(none)"
    return (
        "You are an autonomous agent with access to tools.\n"
        "When you need a tool, respond with ONLY a JSON object:\n"
        '{"tool": "<tool_name>", "arguments": {<args>}}\n\n'
        "When the task is complete, respond with:\n"
        "FINAL: <your answer to the user>\n\n"
        f"Available tools: {tools_list}\n"
        "Use workspace-relative paths for file tools (e.g. src/main.py).\n"
        "Do not invent tool names. Prefer mcp_read_file, mcp_write_file, "
        "mcp_list_directory, mcp_search_files, and mcp_run_command for files."
    )
