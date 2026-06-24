"""Parse Cursor IDE redacted tool-call blocks from agent stream text."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

# Cursor streams use fullwidth pipe (｜) and sometimes ▁ instead of _
_PIPE = r"[\|\uff5c]"
_US = r"[_\u2581]"

_CALL_BLOCK = re.compile(
    rf"<{_PIPE}(?:redacted{_US})?tool{_US}call{_US}begin{_PIPE}>\s*"
    rf"(.*?)\s*"
    rf"<{_PIPE}(?:redacted{_US})?tool{_US}call{_US}end{_PIPE}>",
    re.DOTALL | re.IGNORECASE,
)
_SEP_LINE = re.compile(
    rf"<{_PIPE}(?:redacted{_US})?tool{_US}sep{_PIPE}>\s*(\w+)\s*\n",
    re.IGNORECASE,
)

_TOOL_ALIASES: dict[str, str] = {
    "glob": "glob_file_search",
    "listdir": "list_dir",
    "list_dir": "list_dir",
    "read": "read_file",
    "read_file": "read_file",
    "grep": "ripgrep_search",
    "grep_search": "ripgrep_search",
    "run_terminal_cmd": "run_terminal_command",
    "run_terminal_command": "run_terminal_command",
    "edit_file": "edit_file",
    "file_search": "file_search",
}


def normalize_cursor_markers(text: str) -> str:
    """Normalize Cursor stream delimiter characters to ASCII for parsing."""
    return text.replace("\uff5c", "|").replace("\u2581", "_")


def has_redacted_tool_calls(text: str) -> bool:
    lowered = normalize_cursor_markers(text).lower()
    return "tool_call_begin" in lowered or "tool_calls_begin" in lowered


def parse_redacted_tool_calls(text: str) -> list[dict[str, Any]]:
    """Return tool call dicts: tool, tool_call_id, name, raw_args, params."""
    text = normalize_cursor_markers(text)
    calls: list[dict[str, Any]] = []
    for block in _CALL_BLOCK.findall(text):
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue

        raw_name = lines[0].strip()
        name = _TOOL_ALIASES.get(raw_name.lower(), raw_name.lower())

        params: dict[str, Any] = {}
        rest = "\n".join(lines[1:])
        sep_positions = [(m.start(), m.group(1), m.end()) for m in _SEP_LINE.finditer(rest)]
        for i, (_start, key, val_start) in enumerate(sep_positions):
            val_end = sep_positions[i + 1][0] if i + 1 < len(sep_positions) else len(rest)
            value = rest[val_start:val_end].strip()
            params[key] = value

        _normalize_params(name, params)
        raw_args = json.dumps(params)
        calls.append(
            {
                "tool": 0,
                "tool_call_id": f"toolu_{uuid.uuid4().hex[:16]}",
                "name": name,
                "raw_args": raw_args,
                "params": params,
            }
        )
    return calls


def _normalize_params(name: str, params: dict[str, Any]) -> None:
    if name == "glob_file_search":
        pattern = params.pop("glob_pattern", params.pop("pattern", "*"))
        target = params.pop("target_directory", "").strip()
        params.pop("explanation", None)
        if target:
            params["glob_pattern"] = f"{target.rstrip('/')}/{pattern}"
        else:
            params["glob_pattern"] = pattern
    elif name == "list_dir":
        params.pop("explanation", None)
        for key in ("relative_workspace_path", "target_directory", "path"):
            if key in params and "directory_path" not in params:
                params["directory_path"] = params.pop(key)
                break
    elif name == "read_file":
        params.pop("explanation", None)
        for key in ("target_file", "path", "relative_workspace_path"):
            if key in params and "relative_workspace_path" not in params:
                params["relative_workspace_path"] = params.pop(key)
                break
    elif name == "file_search":
        params.pop("explanation", None)


def strip_tool_markup(text: str) -> str:
    text = normalize_cursor_markers(text)
    cleaned = _CALL_BLOCK.sub("", text)
    cleaned = re.sub(
        rf"<{_PIPE}(?:redacted{_US})?tool{_US}calls{_US}begin{_PIPE}>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"<{_PIPE}(?:redacted{_US})?tool{_US}calls{_US}end{_PIPE}>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()
