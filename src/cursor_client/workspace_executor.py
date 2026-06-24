"""Workspace-safe tool executor for Plane wire agent."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from cursor_client._vendor import ensure_vendor_path
from cursor_client.tool_call_parser import normalize_tool_params


class WorkspaceToolExecutor:
    """Wrap vendor ToolExecutor with reliable workspace paths for shell/search tools."""

    def __init__(self, workspace_root: str | Path) -> None:
        ensure_vendor_path()
        from cursor_agent_client import ToolExecutor  # noqa: WPS433

        self.workspace_root = Path(workspace_root).resolve()
        self._inner = ToolExecutor(workspace_root=str(self.workspace_root))

    def execute(self, tool_call: Any) -> Any:
        from cursor_agent_client import ClientSideToolV2  # noqa: WPS433

        name = (tool_call.name or "").lower()
        tool_call.params = normalize_tool_params(name or "unknown", tool_call.params)

        if tool_call.tool in (
            ClientSideToolV2.RUN_TERMINAL_COMMAND_V2,
            ClientSideToolV2.WRITE_SHELL_STDIN,
        ) or name in {"run_terminal_command", "run_terminal_cmd"}:
            return self._run_terminal(tool_call.params)

        if tool_call.tool in (
            ClientSideToolV2.RIPGREP_SEARCH,
            ClientSideToolV2.RIPGREP_RAW_SEARCH,
        ) or name in {"ripgrep_search", "grep_search", "grep"}:
            return self._grep_search(tool_call.params)

        return self._inner.execute(tool_call)

    def _grep_search(self, params: dict[str, Any]) -> Any:
        from cursor_agent_client import ToolResult  # noqa: WPS433

        pattern = str(params.get("pattern") or "").strip()
        if not pattern:
            return ToolResult(False, {}, "No search pattern provided")

        search_root = self._resolve_search_path(
            params.get("search_path") or params.get("path")
        )

        try:
            rg = self._find_ripgrep()
        except FileNotFoundError:
            return self._grep_findstr(pattern, search_root)

        try:
            cmd = [rg, "--json", "-m", "50", pattern, str(search_root)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return ToolResult(False, {}, "Search timed out")
        except OSError as exc:
            return ToolResult(False, {}, str(exc))

        matches: list[dict[str, Any]] = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("type") != "match":
                continue
            match_data = data.get("data", {})
            matches.append(
                {
                    "path": match_data.get("path", {}).get("text", ""),
                    "line_number": match_data.get("line_number", 0),
                    "line_content": match_data.get("lines", {}).get("text", "").strip(),
                }
            )

        if result.returncode not in (0, 1):
            detail = (result.stderr or result.stdout or "").strip()
            return ToolResult(
                False,
                {"matches": matches, "pattern": pattern},
                detail or f"ripgrep failed with exit code {result.returncode}",
            )

        return ToolResult(
            True,
            {
                "matches": matches,
                "pattern": pattern,
                "total_matches": len(matches),
                "search_path": str(search_root),
            },
        )

    def _grep_findstr(self, pattern: str, search_root: Path) -> Any:
        from cursor_agent_client import ToolResult  # noqa: WPS433

        try:
            completed = subprocess.run(
                ["findstr", "/s", "/n", "/i", "/c:" + pattern, "*.*"],
                cwd=str(search_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return ToolResult(False, {}, str(exc))

        matches: list[dict[str, Any]] = []
        for line in completed.stdout.splitlines()[:50]:
            parts = line.split(":", 2)
            if len(parts) == 3:
                matches.append(
                    {
                        "path": parts[0],
                        "line_number": int(parts[1]) if parts[1].isdigit() else 0,
                        "line_content": parts[2].strip(),
                    }
                )

        return ToolResult(
            True,
            {
                "matches": matches,
                "pattern": pattern,
                "total_matches": len(matches),
                "search_path": str(search_root),
                "engine": "findstr",
            },
        )

    def _find_ripgrep(self) -> str:
        found = shutil.which("rg")
        if found:
            return found

        local_app = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(local_app) / "Programs/Cursor/resources/app/node_modules/@vscode/ripgrep/bin/rg.exe",
            Path(local_app) / "Programs/cursor/resources/app/node_modules/@vscode/ripgrep/bin/rg.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        raise FileNotFoundError("ripgrep not found")

    def _resolve_search_path(self, path: str | None) -> Path:
        root = self.workspace_root
        if path is None or not str(path).strip():
            return root

        candidate = Path(str(path).strip())
        if not candidate.is_absolute():
            candidate = (root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        try:
            if candidate == root or root in candidate.parents:
                return candidate
        except OSError:
            pass
        return root

    def _run_terminal(self, params: dict[str, Any]) -> Any:
        from cursor_agent_client import ToolResult  # noqa: WPS433

        command = (
            params.get("command")
            or params.get("cmd")
            or params.get("terminal_command")
            or ""
        ).strip()
        if not command:
            return ToolResult(False, {}, "No command provided")

        cwd = self._resolve_search_path(params.get("cwd") or params.get("working_directory"))
        patched = dict(params)
        patched["command"] = command
        patched["cwd"] = str(cwd)

        result = self._inner._run_terminal(patched)  # noqa: SLF001
        exit_code = int((result.data or {}).get("exit_code", 0))
        if exit_code != 0:
            detail = (result.data or {}).get("stderr") or (result.data or {}).get(
                "stdout"
            )
            return ToolResult(
                False,
                result.data,
                (detail or f"Command failed with exit code {exit_code}").strip(),
            )
        return result
