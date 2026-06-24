"""Data handling — persists conversation history to JSON."""

import json
from pathlib import Path
from typing import Any


class ConversationMemory:
    """Manages read/write of chat message history."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._messages: list[dict[str, str]] = []
        self.load()

    def load(self) -> None:
        """Load conversation history from disk."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._file_path.exists():
            self._messages = []
            self.save()
            return

        try:
            with self._file_path.open(encoding="utf-8") as f:
                data: Any = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in conversation file: {self._file_path}"
            ) from e

        if not isinstance(data, list):
            raise ValueError(
                f"Conversation file must contain a JSON array: {self._file_path}"
            )

        self._messages = data

    def get_messages(self) -> list[dict[str, str]]:
        """Return a copy of the current message history."""
        return list(self._messages)

    def add_message(self, role: str, content: str) -> None:
        """Append a message to in-memory history."""
        self._messages.append({"role": role, "content": content})

    def remove_last_message(self) -> None:
        """Remove the most recent message (used to roll back on API failure)."""
        if self._messages:
            self._messages.pop()

    def save(self) -> None:
        """Persist conversation history to disk."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with self._file_path.open("w", encoding="utf-8") as f:
            json.dump(self._messages, f, indent=2, ensure_ascii=False)

    def clear(self) -> None:
        """Remove all messages and save empty history."""
        self._messages = []
        self.save()
