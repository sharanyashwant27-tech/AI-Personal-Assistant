"""AI logic — planner agent that decomposes user goals into executable steps."""

import json
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI, OpenAIError

from prompts import load_system_prompt


@dataclass(frozen=True)
class PlanStep:
    """A single step in an execution plan."""

    step_id: int
    description: str
    suggested_tool: str | None


class PlannerAgent:
    """Breaks user requests into ordered, tool-aware execution steps."""

    def __init__(
        self,
        client: OpenAI,
        model: str,
        planner_prompt_path: Path,
    ) -> None:
        self._client = client
        self._model = model
        self._planner_prompt = load_system_prompt(planner_prompt_path)

    def create_plan(
        self,
        user_goal: str,
        memory_context: str,
        available_tools: list[str],
    ) -> list[PlanStep]:
        """Generate an execution plan for the user's goal."""
        tools_list = ", ".join(available_tools) if available_tools else "none"

        messages = [
            {"role": "system", "content": self._planner_prompt},
            {
                "role": "user",
                "content": (
                    f"Goal: {user_goal}\n\n"
                    f"Agent memory:\n{memory_context}\n\n"
                    f"Available tools: {tools_list}\n\n"
                    "Return a JSON object with key 'steps' containing an array of "
                    "objects with: step_id (int), description (str), "
                    "suggested_tool (str or null)."
                ),
            },
        ]

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except OpenAIError as e:
            raise RuntimeError(f"Planner API error: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Planner returned an empty response.")

        return self._parse_plan(content)

    @staticmethod
    def _parse_plan(content: str) -> list[PlanStep]:
        """Parse planner JSON output into PlanStep objects."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Planner returned invalid JSON: {e}") from e

        raw_steps = data.get("steps", [])
        if not isinstance(raw_steps, list) or not raw_steps:
            raise RuntimeError("Planner returned no steps.")

        steps: list[PlanStep] = []
        for item in raw_steps:
            steps.append(
                PlanStep(
                    step_id=int(item.get("step_id", len(steps) + 1)),
                    description=str(item.get("description", "")).strip(),
                    suggested_tool=item.get("suggested_tool"),
                )
            )

        return steps
