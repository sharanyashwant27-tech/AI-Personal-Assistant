"""FastMCP server — file and command tools scoped to WORKSPACE_ROOT."""

from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_servers.agent_tools.paths import WORKSPACE_ROOT, resolve_workspace_path

HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "8765"))

ALLOWED_COMMAND_PREFIXES = (
    "python ",
    "python3 ",
    "pip ",
    "pip3 ",
    "dir",
    "ls",
    "type ",
    "cat ",
    "echo ",
    "git ",
    "pytest ",
    "node ",
    "npm ",
)

mcp = FastMCP(
    "agent-tools",
    instructions=(
        "Workspace-scoped tools for reading, writing, listing files, "
        "searching by glob, and running sandboxed shell commands."
    ),
    host=HOST,
    port=PORT,
)


@mcp.tool()
def read_file(path: str) -> str:
    """Read a UTF-8 text file relative to the workspace root."""
    target = resolve_workspace_path(path)
    if not target.is_file():
        return f"Error: file not found: {path}"
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: {path} is not a UTF-8 text file."


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write UTF-8 text to a file relative to the workspace root."""
    target = resolve_workspace_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} character(s) to {path}."


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List files and directories under a workspace-relative path."""
    target = resolve_workspace_path(path)
    if not target.is_dir():
        return f"Error: directory not found: {path}"

    entries: list[str] = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        suffix = "/" if item.is_dir() else ""
        rel = item.relative_to(WORKSPACE_ROOT).as_posix()
        entries.append(f"{rel}{suffix}")

    if not entries:
        return f"(empty directory: {path})"
    return "\n".join(entries)


@mcp.tool()
def search_files(pattern: str, path: str = ".") -> str:
    """Glob-search file names under a workspace directory (e.g. '*.py')."""
    root = resolve_workspace_path(path)
    if not root.is_dir():
        return f"Error: directory not found: {path}"

    matches: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "venv", "__pycache__", "node_modules"}]
        for name in filenames:
            if fnmatch.fnmatch(name, pattern):
                rel = Path(dirpath, name).relative_to(WORKSPACE_ROOT).as_posix()
                matches.append(rel)

    if not matches:
        return f"No files matching '{pattern}' under {path}."
    return "\n".join(sorted(matches)[:200])


@mcp.tool()
def run_command(command: str, timeout_seconds: int = 30) -> str:
    """Run a sandboxed shell command inside the workspace root."""
    command = command.strip()
    if not command:
        return "Error: command cannot be empty."

    lowered = command.lower()
    if not any(lowered.startswith(prefix) for prefix in ALLOWED_COMMAND_PREFIXES):
        allowed = ", ".join(repr(p.strip()) for p in ALLOWED_COMMAND_PREFIXES[:6])
        return f"Error: command not allowed. Must start with one of: {allowed}, ..."

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            timeout=max(5, min(timeout_seconds, 120)),
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout_seconds}s."

    parts = [f"exit_code: {completed.returncode}"]
    if completed.stdout.strip():
        parts.append(f"stdout:\n{completed.stdout.strip()}")
    if completed.stderr.strip():
        parts.append(f"stderr:\n{completed.stderr.strip()}")
    return "\n".join(parts)


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
