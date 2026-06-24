"""Parse assistant text from Cursor Connect stream messages."""

from __future__ import annotations

import re

# Cursor embeds the user-visible answer after a closing thinking tag.
_THINKING_END = re.compile(r"</(?:think|redacted_thinking)>\s*", re.IGNORECASE)
_FINAL_ANSWER = re.compile(
    r"(?:<[\uff5c|]final[\uff5c|]>|<\|final\|>|``)\s*(.+)$",
    re.DOTALL,
)


def extract_assistant_text(messages: list[tuple[str, str]]) -> str | None:
    """Extract user-visible assistant text from decoded stream messages."""
    content_parts: list[str] = []
    thinking_parts: list[str] = []

    for msg_type, text in messages:
        if not text:
            continue
        if msg_type == "content":
            content_parts.append(text)
        elif msg_type == "thinking":
            thinking_parts.append(text)

    if content_parts:
        return "".join(content_parts).strip()

    if not thinking_parts:
        return None

    combined = "".join(thinking_parts)
    quoted_chunks = re.findall(r'text:\s*"((?:\\.|[^"\\])*)"', combined)
    merged = "".join(_unescape_thinking_chunk(chunk) for chunk in quoted_chunks)

    thinking_parts_split = _THINKING_END.split(merged)
    if len(thinking_parts_split) > 1:
        answer = thinking_parts_split[-1].strip()
        if answer:
            return answer

    final_match = _FINAL_ANSWER.search(merged)
    if final_match:
        return final_match.group(1).strip()

    cleaned = merged.strip()
    return cleaned or None


def _unescape_thinking_chunk(chunk: str) -> str:
    """Unescape thinking text fragments from protobuf debug strings."""
    return (
        chunk.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )
