"""AI logic — executes plan steps using OpenAI tool calling."""

import json
from dataclasses import dataclass

from openai import OpenAI, OpenAIError

from planner import PlanStep
from tools import ToolRegistry


@dataclass(frozen=True)
class StepResult:
    """Result of executing a single plan step."""

    step_id: int
    description: str
    output: str
    status: str


class TaskExecutor:
    """Runs plan steps by invoking tools through the LLM."""

    def __init__(
        self,
        client: OpenAI,
        model: str,
        tool_registry: ToolRegistry,
        max_tool_iterations: int,
    ) -> None:
        self._client = client
        self._model = model
        self._tools = tool_registry
        self._max_tool_iterations = max_tool_iterations

    def execute_plan(
        self,
        plan: list[PlanStep],
        user_goal: str,
    ) -> list[StepResult]:
        """Execute each plan step sequentially using tool calling."""
        results: list[StepResult] = []
        prior_outputs: list[str] = []

        for step in plan:
            step_prompt = self._build_step_prompt(
                user_goal, step, prior_outputs
            )
            try:
                output = self._run_tool_loop(step_prompt)
                status = "completed"
            except RuntimeError as e:
                output = str(e)
                status = "failed"

            results.append(
                StepResult(
                    step_id=step.step_id,
                    description=step.description,
                    output=output,
                    status=status,
                )
            )
            prior_outputs.append(
                f"Step {step.step_id}: {step.description}\nResult: {output}"
            )

        return results

    def _build_step_prompt(
        self,
        user_goal: str,
        step: PlanStep,
        prior_outputs: list[str],
    ) -> str:
        context = ""
        if prior_outputs:
            context = "Previous step results:\n" + "\n\n".join(prior_outputs)

        tool_hint = ""
        if step.suggested_tool:
            tool_hint = f"Suggested tool: {step.suggested_tool}"

        return (
            f"User goal: {user_goal}\n\n"
            f"Current step ({step.step_id}): {step.description}\n"
            f"{tool_hint}\n\n"
            f"{context}\n\n"
            "Complete this step using available tools if needed. "
            "Return a concise result when done."
        )

    def _run_tool_loop(self, step_prompt: str) -> str:
        """Run an LLM tool-calling loop until the step is complete."""
        messages: list[dict] = [
            {
                "role": "system",
                "content": (
                    "You are a task executor. Use tools to complete the assigned "
                    "step. When finished, reply with a brief summary of what you did."
                ),
            },
            {"role": "user", "content": step_prompt},
        ]

        schemas = self._tools.get_openai_schemas()

        for _ in range(self._max_tool_iterations):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=schemas,
                    tool_choice="auto",
                )
            except OpenAIError as e:
                raise RuntimeError(f"Task executor API error: {e}") from e

            message = response.choices[0].message

            if not message.tool_calls:
                if message.content:
                    return message.content.strip()
                raise RuntimeError("Executor returned empty response.")

            messages.append(message.model_dump(exclude_none=True))

            for tool_call in message.tool_calls:
                arguments = json.loads(tool_call.function.arguments or "{}")
                result = self._tools.execute(
                    tool_call.function.name, arguments
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

        raise RuntimeError(
            f"Step exceeded max tool iterations ({self._max_tool_iterations})."
        )
