"""Verify grep/ripgrep tool param normalization and search execution."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cursor_client._vendor import ensure_vendor_path
from cursor_client.tool_call_parser import normalize_tool_params, parse_redacted_tool_calls
from cursor_client.workspace_executor import WorkspaceToolExecutor

ensure_vendor_path()
from cursor_agent_client import ToolCall  # noqa: E402

SAMPLE = (
    "<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>\n"
    "Grep\n"
    "<｜tool▁sep｜>pattern\n"
    "CursorWireAgent\n"
    "<｜tool▁sep｜>path\n"
    "src\n"
    "<｜tool▁call▁end｜>"
)


def main() -> None:
    parsed = parse_redacted_tool_calls(SAMPLE)
    assert parsed, "expected parsed grep tool call"
    assert parsed[0]["name"] == "ripgrep_search"
    assert parsed[0]["params"]["pattern"] == "CursorWireAgent"
    assert parsed[0]["params"]["search_path"] == "src"

    query_params = normalize_tool_params("grep", {"query": "def main", "path": "src"})
    assert query_params["pattern"] == "def main"
    assert query_params["search_path"] == "src"

    nested = normalize_tool_params(
        "ripgrep_search",
        {"pattern_info": {"pattern": "FastAPI"}},
    )
    assert nested["pattern"] == "FastAPI"

    executor = WorkspaceToolExecutor(ROOT)
    tc = ToolCall(
        tool=3,
        tool_call_id="test",
        name="ripgrep_search",
        raw_args="{}",
        params={"query": "CursorWireAgent", "path": "src"},
    )
    result = executor.execute(tc)
    if not result.success:
        raise SystemExit(f"grep failed: {result.error}")
    print(f"matches={result.data.get('total_matches')} engine path ok")
    print("PASS")


if __name__ == "__main__":
    main()
