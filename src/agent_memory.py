"""Data handling — persistent agent memory for facts and task history."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AgentMemory:
    """Stores long-term facts and completed task records for the agent."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._facts: list[dict[str, str]] = []
        self._task_history: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        """Load agent memory from disk."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._file_path.exists():
            self._facts = []
            self._task_history = []
            self.save()
            return

        with self._file_path.open(encoding="utf-8") as f:
            data = json.load(f)

        self._facts = data.get("facts", [])
        self._task_history = data.get("task_history", [])

    def save(self) -> None:
        """Persist agent memory to disk."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with self._file_path.open("w", encoding="utf-8") as f:
            json.dump(
                {"facts": self._facts, "task_history": self._task_history},
                f,
                indent=2,
                ensure_ascii=False,
            )

    def remember_fact(self, key: str, value: str) -> None:
        """Store or update a fact keyed by name."""
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError("Fact key and value cannot be empty.")

        for fact in self._facts:
            if fact["key"] == key:
                fact["value"] = value
                fact["updated_at"] = self._timestamp()
                self.save()
                return

        self._facts.append(
            {
                "key": key,
                "value": value,
                "created_at": self._timestamp(),
            }
        )
        self.save()

    def get_facts(self) -> list[dict[str, str]]:
        """Return all stored facts."""
        return list(self._facts)

    def recall_context(self) -> str:
        """Format stored facts as context for the planner and agent."""
        if not self._facts:
            return "No stored facts."

        lines = [f"- {fact['key']}: {fact['value']}" for fact in self._facts]
        return "Stored facts:\n" + "\n".join(lines)

    def log_task(
        self, goal: str, plan: list[str], result: str
    ) -> None:
        """Record a completed task in history."""
        self._task_history.append(
            {
                "goal": goal,
                "plan": plan,
                "result": result,
                "completed_at": self._timestamp(),
            }
        )
        # Keep recent history bounded
        if len(self._task_history) > 20:
            self._task_history = self._task_history[-20:]
        self.save()

    def clear(self) -> None:
        """Clear all agent memory."""
        self._facts = []
        self._task_history = []
        self.save()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
