"""Data handling — load and chunk documents for indexing."""

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


@dataclass(frozen=True)
class Document:
    """A loaded document with source metadata."""

    content: str
    source: str


@dataclass(frozen=True)
class DocumentChunk:
    """A text chunk derived from a document."""

    content: str
    source: str
    chunk_index: int


def _load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _load_pdf_file(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def load_documents(documents_dir: Path) -> list[Document]:
    """Load all supported documents from the given directory."""
    if not documents_dir.exists():
        documents_dir.mkdir(parents=True, exist_ok=True)
        return []

    documents: list[Document] = []
    for path in sorted(documents_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        try:
            if path.suffix.lower() == ".pdf":
                content = _load_pdf_file(path)
            else:
                content = _load_text_file(path)
        except OSError as e:
            raise ValueError(f"Failed to read document: {path}") from e

        if not content:
            continue

        documents.append(
            Document(content=content, source=str(path.relative_to(documents_dir)))
        )

    return documents


def chunk_document(
    document: Document, chunk_size: int, chunk_overlap: int
) -> list[DocumentChunk]:
    """Split a document into overlapping text chunks."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    text = document.content
    chunks: list[DocumentChunk] = []
    start = 0
    index = 0

    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append(
                DocumentChunk(
                    content=piece,
                    source=document.source,
                    chunk_index=index,
                )
            )
            index += 1
        start = end - chunk_overlap

    return chunks


def chunk_documents(
    documents: list[Document], chunk_size: int, chunk_overlap: int
) -> list[DocumentChunk]:
    """Chunk all documents into retrieval-ready pieces."""
    all_chunks: list[DocumentChunk] = []
    for document in documents:
        all_chunks.extend(chunk_document(document, chunk_size, chunk_overlap))
    return all_chunks
