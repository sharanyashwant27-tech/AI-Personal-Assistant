"""Test Cursor wire-protocol Auto agent."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cursor_client.agent_wire import CursorWireAgent


def main() -> int:
    events: list[str] = []

    def on_event(ev: dict) -> None:
        events.append(ev["type"])
        if ev["type"] in {"tool_start", "tool_result", "final"}:
            print(f"  [{ev['type']}]", ev.get("tool") or ev.get("content", "")[:80])

    agent = CursorWireAgent(workspace_root=ROOT, max_tool_iterations=6)
    print("Wire agent test — list workspace documents/\n")
    reply = agent.run(
        'Use list_dir with directory_path "documents" (workspace-relative). '
        "The folder contains sample.txt. Reply FINAL: sample.txt only.",
        on_event=on_event,
    )
    print("\n--- REPLY ---")
    print(reply)
    print("\n--- EVENTS ---", events)
    if "sample" in reply.lower() or "txt" in reply.lower():
        print("\nPASS")
        return 0
    print("\nFAIL — expected sample.txt in reply")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
