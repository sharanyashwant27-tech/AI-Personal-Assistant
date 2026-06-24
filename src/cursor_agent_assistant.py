"""AI logic — Cursor-backed agent with wire-protocol Auto or local ReAct fallback."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from action_parser import build_agent_system_prompt, parse_agent_response
from agent_memory import AgentMemory
from config import PROJECT_ROOT, Settings
from cursor_client import CursorChatClient
from cursor_client.agent_wire import CursorWireAgent
from memory import ConversationMemory
from prompts import load_system_prompt
from retrieval import RetrievalPipeline
from tools import ToolRegistry

EventCallback = Callable[[dict[str, Any]], None]


class CursorAgentAssistant:
    """Agent using Cursor Auto wire protocol (default) or local ReAct fallback."""

    def __init__(
        self,
        settings: Settings,
        memory: ConversationMemory,
        tool_registry: ToolRegistry,
        agent_memory: AgentMemory,
        retrieval: RetrievalPipeline | None = None,
    ) -> None:
        self._settings = settings
        self._memory = memory
        self._tools = tool_registry
        self._agent_memory = agent_memory
        self._retrieval = retrieval
        self._base_prompt = load_system_prompt(settings.system_prompt_path)
        self._max_iterations = settings.agent_max_tool_iterations

        self._wire = CursorWireAgent(
            workspace_root=PROJECT_ROOT,
            model=settings.cursor_model,
            ghost_mode=settings.cursor_ghost_mode,
            max_tool_iterations=settings.agent_max_tool_iterations,
            backend_url=settings.cursor_backend_url,
        )
        self._chat = CursorChatClient(
            model=settings.cursor_model,
            ghost_mode=settings.cursor_ghost_mode,
            backend_url=settings.cursor_backend_url,
        )

    @property
    def protocol(self) -> str:
        return self._settings.cursor_agent_protocol

    def run(self, user_message: str, on_event: EventCallback | None = None) -> str:
        user_message = user_message.strip()
        if not user_message:
            raise ValueError("Message cannot be empty.")

        self._emit(on_event, "user", {"content": user_message})
        self._memory.add_message("user", user_message)

        try:
            if self.protocol == "wire":
                final_reply = self._run_wire(user_message, on_event)
            else:
                final_reply = self._run_react(user_message, on_event)
        except RuntimeError as e:
            self._memory.remove_last_message()
            self._emit(on_event, "error", {"message": str(e)})
            raise RuntimeError(f"Cursor agent error: {e}") from e

        self._memory.add_message("assistant", final_reply)
        self._memory.save()
        self._agent_memory.log_task(
            goal=user_message,
            plan=[f"{self.protocol} agent loop"],
            result=final_reply,
        )
        self._emit(on_event, "final", {"content": final_reply})
        return final_reply

    def chat(self, user_message: str, on_event: EventCallback | None = None) -> str:
        return self.run(user_message, on_event=on_event)

    def _run_wire(self, user_message: str, on_event: EventCallback | None) -> str:
        memory_ctx = self._agent_memory.recall_context()
        prompt = user_message
        if memory_ctx.strip():
            prompt = f"{user_message}\n\nAgent memory:\n{memory_ctx}"
        return self._wire.run(prompt, on_event=on_event)

    def _run_react(self, user_message: str, on_event: EventCallback | None) -> str:
        tool_names = self._tools.get_tool_names()
        system_prompt = (
            f"{self._base_prompt}\n\n"
            f"{build_agent_system_prompt(tool_names)}\n\n"
            f"Agent memory:\n{self._agent_memory.recall_context()}"
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        history = self._memory.get_messages()
        if history and history[-1]["role"] == "user":
            history = history[:-1]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return self._react_loop(messages, on_event)

    def _react_loop(
        self,
        messages: list[dict[str, str]],
        on_event: EventCallback | None,
    ) -> str:
        for iteration in range(1, self._max_iterations + 1):
            self._emit(on_event, "thinking", {"iteration": iteration})
            response = self._chat.complete(messages)
            parsed = parse_agent_response(response)

            if parsed.is_final:
                text = parsed.final_text or response.strip()
                self._emit(on_event, "assistant", {"content": text, "iteration": iteration})
                return text

            if parsed.tool_action is None:
                return response.strip()

            action = parsed.tool_action
            self._emit(
                on_event,
                "tool_start",
                {
                    "iteration": iteration,
                    "tool": action.name,
                    "arguments": action.arguments,
                },
            )
            if action.name not in self._tools.get_tool_names():
                tool_result = f"Error: unknown tool '{action.name}'."
            else:
                tool_result = self._tools.execute(action.name, action.arguments)

            self._emit(
                on_event,
                "tool_result",
                {
                    "iteration": iteration,
                    "tool": action.name,
                    "result": tool_result[:4000],
                },
            )
            messages.append({"role": "assistant", "content": response})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Tool result for {action.name}:\n{tool_result}\n\n"
                        "Continue with another tool JSON or FINAL: answer."
                    ),
                }
            )

        raise RuntimeError(
            f"Agent exceeded max tool iterations ({self._max_iterations})."
        )

    @staticmethod
    def _emit(on_event: EventCallback | None, kind: str, data: dict[str, Any]) -> None:
        if on_event:
            on_event({"type": kind, **data})

    def clear_history(self) -> None:
        self._memory.clear()

    def clear_agent_memory(self) -> None:
        self._agent_memory.clear()
