"""AI logic — agent orchestrator with planner, tools, memory, and task execution."""

from openai import OpenAI, OpenAIError

from agent_memory import AgentMemory
from config import Settings
from memory import ConversationMemory
from planner import PlannerAgent
from prompts import build_execution_summary, load_system_prompt
from task_executor import TaskExecutor
from tools import ToolRegistry


class AIAgent:
    """Autonomous agent: plan → execute tools → synthesize response."""

    def __init__(
        self,
        settings: Settings,
        conversation_memory: ConversationMemory,
        agent_memory: AgentMemory,
        tool_registry: ToolRegistry,
        planner: PlannerAgent,
        executor: TaskExecutor,
    ) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._system_prompt = load_system_prompt(settings.system_prompt_path)
        self._conversation = conversation_memory
        self._agent_memory = agent_memory
        self._planner = planner
        self._executor = executor
        self._tool_registry = tool_registry
        self._max_plan_steps = settings.agent_max_plan_steps

    def run(self, user_message: str) -> str:
        """Process a user request through the full agent pipeline."""
        user_message = user_message.strip()
        if not user_message:
            raise ValueError("Message cannot be empty.")

        self._conversation.add_message("user", user_message)
        memory_context = self._agent_memory.recall_context()

        try:
            plan = self._planner.create_plan(
                user_goal=user_message,
                memory_context=memory_context,
                available_tools=self._tool_registry.get_tool_names(),
            )
        except RuntimeError as e:
            self._conversation.remove_last_message()
            raise RuntimeError(f"Planning failed: {e}") from e

        plan = plan[: self._max_plan_steps]
        step_results = self._executor.execute_plan(plan, user_message)

        final_reply = self._synthesize_response(
            user_message, plan, step_results, memory_context
        )

        self._conversation.add_message("assistant", final_reply)
        self._conversation.save()

        self._agent_memory.log_task(
            goal=user_message,
            plan=[step.description for step in plan],
            result=final_reply,
        )

        return final_reply

    def _synthesize_response(
        self,
        user_message: str,
        plan,
        step_results,
        memory_context: str,
    ) -> str:
        """Combine execution results into a final user-facing answer."""
        execution_summary = build_execution_summary(plan, step_results)

        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": (
                    f"User request: {user_message}\n\n"
                    f"Agent memory:\n{memory_context}\n\n"
                    f"Execution summary:\n{execution_summary}\n\n"
                    "Provide a clear, helpful final answer to the user based on "
                    "the execution results. Mention tools or sources used when relevant."
                ),
            },
        ]

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.4,
            )
        except OpenAIError as e:
            self._conversation.remove_last_message()
            raise RuntimeError(f"Synthesis API error: {e}") from e

        content = response.choices[0].message.content
        if not content:
            self._conversation.remove_last_message()
            raise RuntimeError("Agent returned an empty final response.")

        return content.strip()

    def clear_history(self) -> None:
        """Clear conversation history only."""
        self._conversation.clear()

    def clear_agent_memory(self) -> None:
        """Clear long-term agent memory (facts and task log)."""
        self._agent_memory.clear()
