"""Parse assistant text from Cursor Connect stream messages."""

from __future__ import annotations

import re

# Cursor embeds the user-visible answer after a closing thinking tag.
_THINKING_END = re.compile(r"</(?:think|redacted_thinking)>\s*", re.IGNORECASE)
_FINAL_ANSWER = re.compile(
    r"(?:<[\uff5c|]final[\uff5c|]>|<\|final\|>|``)\s*(.+)$",
    re.DOTALL,
)
_QUOTED_THINKING = re.compile(r'text:\s*"((?:\\.|[^"\\])*)"')

_REASONING_PREFIXES = (
    "the user",
    "i need to",
    "i should",
    "i'll",
    "i will",
    "let me",
    "first,",
    "next,",
    "they want",
    "this is a straightforward",
    "i'm going",
    "i am going",
    "now i",
    "okay,",
    "alright,",
)


def merge_thinking_chunks(thinking_parts: list[str]) -> str:
    """Merge protobuf thinking fragments into one string."""
    combined = "".join(thinking_parts)
    quoted = _QUOTED_THINKING.findall(combined)
    if quoted:
        return "".join(_unescape_thinking_chunk(chunk) for chunk in quoted)
    return combined


def extract_assistant_text(messages: list[tuple[str, str]]) -> str | None:
    """Extract user-visible assistant text from decoded stream messages."""
    answer = extract_wire_answer(messages)
    return answer or None


def extract_wire_answer(stream_messages: list[tuple[str, str]]) -> str:
    """Best-effort user-visible answer from a wire-agent stream."""
    content_parts = [
        text for msg_type, text in stream_messages if msg_type == "content" and text
    ]
    if content_parts:
        answer = "".join(content_parts).strip()
        if answer and not _looks_like_tool_payload(answer):
            return _clean_answer(answer)

    thinking_parts = [
        text for msg_type, text in stream_messages if msg_type == "thinking" and text
    ]
    if not thinking_parts:
        return ""

    merged = merge_thinking_chunks(thinking_parts)
    raw = "".join(thinking_parts)
    for candidate_src in (raw, merged):
        candidate = _extract_from_merged_thinking(candidate_src)
        if candidate:
            return candidate
    return ""


def _extract_from_merged_thinking(merged: str) -> str:
    if not merged.strip():
        return ""

    merged = _strip_tool_markup_light(merged)

    for marker in (
        "<" + "\uff5c" + "final" + "\uff5c" + ">",
        "<|final|>",
        "FINAL:",
    ):
        if marker in merged:
            tail = merged.split(marker, 1)[-1].strip()
            if tail and "tool_call_begin" not in tail.lower():
                cleaned = _clean_answer(tail)
                if cleaned and not _looks_like_tool_payload(cleaned):
                    return cleaned

    if 'text: "' in merged:
        merged = merge_thinking_chunks([merged])

    merged = _strip_tool_markup_light(merged)

    parts = _THINKING_END.split(merged)
    if len(parts) > 1:
        tail = parts[-1].strip()
        cleaned = _clean_answer(tail)
        if cleaned and not _looks_like_tool_payload(cleaned):
            return cleaned

    if "tool_call_begin" in merged.lower():
        return ""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", merged) if p.strip()]
    for paragraph in reversed(paragraphs):
        cleaned = _clean_answer(paragraph)
        if not cleaned or _looks_like_tool_payload(cleaned):
            continue
        if not _looks_like_reasoning(cleaned):
            return cleaned

    cleaned = _clean_answer(merged.strip())
    if cleaned and not _looks_like_reasoning(cleaned) and not _looks_like_tool_payload(
        cleaned
    ):
        return cleaned
    return ""


def _clean_answer(text: str) -> str:
    text = text.strip()
    if text.upper().startswith("FINAL:"):
        text = text[6:].strip()
    return text


def _looks_like_reasoning(text: str) -> bool:
    first = text.strip().lower().split("\n", 1)[0].strip()
    if not first:
        return True
    return any(first.startswith(prefix) for prefix in _REASONING_PREFIXES)


def _looks_like_tool_payload(text: str) -> bool:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return False
    markers = (
        '"matches"',
        '"entries"',
        '"directory_path"',
        '"total_matches"',
        '"exit_code"',
    )
    return any(marker in stripped for marker in markers)


def _strip_tool_markup_light(text: str) -> str:
    text = text.replace("\uff5c", "|").replace("\u2581", "_")
    text = re.sub(
        r"<\|(?:redacted_)?tool_calls?_begin\|>.*?<\|(?:redacted_)?tool_calls?_end\|>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text.strip()


def _unescape_thinking_chunk(chunk: str) -> str:
    """Unescape thinking text fragments from protobuf debug strings."""
    return (
        chunk.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )
