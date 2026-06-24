"""Verify wire agent terminal commands run inside the git workspace."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cursor_client._vendor import ensure_vendor_path
from cursor_client.workspace_executor import WorkspaceToolExecutor

ensure_vendor_path()
from cursor_agent_client import ToolCall  # noqa: E402


def main() -> None:
    executor = WorkspaceToolExecutor(ROOT)
    cases = [
        {"command": "git status -sb", "cwd": ""},
        {"command": "git status -sb"},
        {"command": "git status -sb", "cwd": "src"},
    ]

    for params in cases:
        tc = ToolCall(
            tool=15,
            tool_call_id="test",
            name="run_terminal_command",
            raw_args="{}",
            params=params,
        )
        result = executor.execute(tc)
        label = params.get("cwd", "<default>")
        print(f"cwd={label!r} success={result.success} exit={result.data.get('exit_code')}")
        if not result.success:
            print(f"  error: {result.error}")
            raise SystemExit(1)
        stdout = (result.data.get("stdout") or "").strip()
        if "fatal: not a git repository" in stdout:
            print(f"  stdout: {stdout}")
            raise SystemExit(1)
        print(f"  stdout: {stdout.splitlines()[0] if stdout else '(empty)'}")

    print("PASS")


if __name__ == "__main__":
    main()
