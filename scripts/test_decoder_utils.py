"""Tests for wire answer extraction from thinking streams."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cursor_client.decoder_utils import (
    _looks_like_tool_payload,
    extract_wire_answer,
    merge_thinking_chunks,
)


def test_merge_quoted_chunks() -> None:
    parts = ['text: "Hello "\n', 'text: "world"\n']
    assert merge_thinking_chunks(parts) == "Hello world"


def test_extract_final_marker() -> None:
    msgs = [
        (
            "thinking",
            'text: "Reasoning here"\nFINAL: Grep params are normalized via normalize_tool_params.',
        )
    ]
    answer = extract_wire_answer(msgs)
    assert "normalize_tool_params" in answer
    assert not answer.startswith("{")


def test_rejects_tool_json() -> None:
    msgs = [("thinking", '{"matches": [], "pattern": "foo", "total_matches": 0}')]
    assert extract_wire_answer(msgs) == ""
    assert _looks_like_tool_payload('{"matches": []}')


def test_rejects_reasoning() -> None:
    msgs = [("thinking", 'text: "The user wants me to search the codebase"\n')]
    assert extract_wire_answer(msgs) == ""


def main() -> None:
    test_merge_quoted_chunks()
    test_extract_final_marker()
    test_rejects_tool_json()
    test_rejects_reasoning()
    print("PASS")


if __name__ == "__main__":
    main()
