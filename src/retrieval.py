"""AI logic — retrieval pipeline for RAG."""

from pathlib import Path

from document_loader import chunk_documents, load_documents
from embeddings import EmbeddingService
from vector_store import StoredChunk, VectorStore


class RetrievalPipeline:
    """Indexes documents and retrieves relevant context for queries."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        documents_dir: Path,
        chunk_size: int,
        chunk_overlap: int,
        top_k: int,
    ) -> None:
        self._embeddings = embedding_service
        self._store = vector_store
        self._documents_dir = documents_dir
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._top_k = top_k

    def index_documents(self) -> int:
        """Load, chunk, embed, and store all documents. Returns chunk count."""
        documents = load_documents(self._documents_dir)
        if not documents:
            raise ValueError(
                f"No documents found in {self._documents_dir}. "
                f"Add .txt, .md, or .pdf files and try again."
            )

        chunks = chunk_documents(
            documents, self._chunk_size, self._chunk_overlap
        )
        if not chunks:
            raise ValueError("Documents loaded but no text chunks were produced.")

        texts = [chunk.content for chunk in chunks]
        embeddings = self._embeddings.embed_texts(texts)

        self._store.reset()

        ids = [
            f"{chunk.source}::{chunk.chunk_index}" for chunk in chunks
        ]
        metadatas = [
            {"source": chunk.source, "chunk_index": chunk.chunk_index}
            for chunk in chunks
        ]

        self._store.add_chunks(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return len(chunks)

    def retrieve(self, query: str) -> list[StoredChunk]:
        """Retrieve the top-k most relevant chunks for a query."""
        query = query.strip()
        if not query or self._store.count() == 0:
            return []

        query_embedding = self._embeddings.embed_query(query)
        return self._store.search(query_embedding, self._top_k)

    @property
    def indexed_chunks(self) -> int:
        """Number of chunks currently in the vector store."""
        return self._store.count()
