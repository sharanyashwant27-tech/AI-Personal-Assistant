"""Data handling — persistent vector database using ChromaDB."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb


@dataclass(frozen=True)
class StoredChunk:
    """A chunk retrieved from the vector database."""

    content: str
    source: str
    chunk_index: int
    score: float


class VectorStore:
    """Manages document embeddings in a local ChromaDB collection."""

    def __init__(self, persist_path: Path, collection_name: str = "documents") -> None:
        persist_path.mkdir(parents=True, exist_ok=True)
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(path=str(persist_path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        """Return the number of indexed chunks."""
        return self._collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection."""
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Insert document chunks with their embeddings."""
        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(self, query_embedding: list[float], top_k: int) -> list[StoredChunk]:
        """Find the most similar chunks to a query embedding."""
        if self.count() == 0:
            return []

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.count()),
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        chunks: list[StoredChunk] = []
        for content, metadata, distance in zip(documents, metadatas, distances):
            if not content or not metadata:
                continue
            # Chroma cosine distance: lower is more similar; convert to similarity score
            score = 1.0 - float(distance)
            chunks.append(
                StoredChunk(
                    content=content,
                    source=str(metadata.get("source", "unknown")),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    score=score,
                )
            )

        return chunks
