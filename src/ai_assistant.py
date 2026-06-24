"""AI logic layer — orchestrates RAG retrieval, memory, and OpenAI API calls."""

from openai import OpenAI, OpenAIError

from config import Settings
from memory import ConversationMemory
from prompts import build_rag_context, load_system_prompt
from retrieval import RetrievalPipeline


class AIAssistant:
    """Handles LLM chat using RAG context, system prompt, and conversation history."""

    def __init__(
        self,
        settings: Settings,
        memory: ConversationMemory,
        retrieval: RetrievalPipeline | None = None,
    ) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._system_prompt = load_system_prompt(settings.system_prompt_path)
        self._memory = memory
        self._retrieval = retrieval

    def _build_system_message(self, user_message: str) -> str:
        """Combine base system prompt with retrieved document context."""
        if self._retrieval is None or self._retrieval.indexed_chunks == 0:
            return self._system_prompt

        chunks = self._retrieval.retrieve(user_message)
        rag_context = build_rag_context(chunks)
        if not rag_context:
            return self._system_prompt

        return f"{self._system_prompt}\n\n{rag_context}"

    def chat(self, user_message: str) -> str:
        """Send user message to the LLM and return the assistant reply."""
        user_message = user_message.strip()
        if not user_message:
            raise ValueError("Message cannot be empty.")

        self._memory.add_message("user", user_message)

        messages = [
            {"role": "system", "content": self._build_system_message(user_message)},
            *self._memory.get_messages(),
        ]

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except OpenAIError as e:
            self._memory.remove_last_message()
            raise RuntimeError(f"OpenAI API error: {e}") from e

        assistant_reply = response.choices[0].message.content
        if not assistant_reply:
            self._memory.remove_last_message()
            raise RuntimeError("OpenAI returned an empty response.")

        self._memory.add_message("assistant", assistant_reply)
        self._memory.save()

        return assistant_reply

    def clear_history(self) -> None:
        """Clear stored conversation history."""
        self._memory.clear()
