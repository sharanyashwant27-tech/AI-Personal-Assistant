"""AI logic — chat assistant powered by the Cursor IDE wire protocol."""

from config import Settings
from cursor_client import CursorChatClient
from memory import ConversationMemory
from prompts import build_rag_context, load_system_prompt
from retrieval import RetrievalPipeline


class CursorAssistant:
    """Chat assistant using Cursor subscription auth (same backend as the IDE)."""

    def __init__(
        self,
        settings: Settings,
        memory: ConversationMemory,
        retrieval: RetrievalPipeline | None = None,
    ) -> None:
        self._client = CursorChatClient(
            model=settings.cursor_model,
            ghost_mode=settings.cursor_ghost_mode,
            backend_url=settings.cursor_backend_url,
        )
        self._system_prompt = load_system_prompt(settings.system_prompt_path)
        self._memory = memory
        self._retrieval = retrieval

    def chat(self, user_message: str) -> str:
        """Send user message via Cursor backend and return the reply."""
        user_message = user_message.strip()
        if not user_message:
            raise ValueError("Message cannot be empty.")

        self._memory.add_message("user", user_message)

        messages = self._build_messages(user_message)

        try:
            reply = self._client.complete(messages)
        except RuntimeError as e:
            self._memory.remove_last_message()
            raise RuntimeError(f"Cursor API error: {e}") from e

        self._memory.add_message("assistant", reply)
        self._memory.save()
        return reply

    def _build_messages(self, user_message: str) -> list[dict[str, str]]:
        """Assemble system prompt, RAG context, history, and user turn."""
        system_content = self._system_prompt

        if self._retrieval and self._retrieval.indexed_chunks > 0:
            chunks = self._retrieval.retrieve(user_message)
            rag_context = build_rag_context(chunks)
            if rag_context:
                system_content = f"{system_content}\n\n{rag_context}"

        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]

        history = self._memory.get_messages()
        # Exclude the latest user message already added for this turn
        if history and history[-1]["role"] == "user":
            history = history[:-1]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def clear_history(self) -> None:
        """Clear stored conversation history."""
        self._memory.clear()

    def clear_agent_memory(self) -> None:
        """No-op in chat-only mode (no agent memory)."""
