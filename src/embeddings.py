"""AI logic — generate text embeddings via OpenAI."""

from openai import OpenAI, OpenAIError


class EmbeddingService:
    """Wraps OpenAI embedding API calls."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []

        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
        except OpenAIError as e:
            raise RuntimeError(f"Embedding API error: {e}") from e

        return [item.embedding for item in response.data]

    def embed_query(self, query: str) -> list[float]:
        """Generate an embedding for a single search query."""
        embeddings = self.embed_texts([query.strip()])
        return embeddings[0]
