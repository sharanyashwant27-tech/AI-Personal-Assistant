"""Prompt management — loads system instructions and builds RAG context."""

from pathlib import Path

from vector_store import StoredChunk


def load_system_prompt(path: Path) -> str:
    """Read system instructions from the given file path."""
    if not path.exists():
        raise FileNotFoundError(f"System prompt file not found: {path}")

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"System prompt file is empty: {path}")

    return content


def build_rag_context(chunks: list[StoredChunk]) -> str:
    """Format retrieved document chunks as context for the LLM."""
    if not chunks:
        return ""

    sections = []
    for index, chunk in enumerate(chunks, start=1):
        sections.append(
            f"[Source {index}: {chunk.source} | relevance: {chunk.score:.2f}]\n"
            f"{chunk.content}"
        )

    context_body = "\n\n---\n\n".join(sections)

    return (
        "Use the following retrieved context to answer the user when relevant. "
        "If the context does not contain the answer, say so and answer from "
        "general knowledge.\n\n"
        f"{context_body}"
    )


def build_execution_summary(plan, step_results) -> str:
    """Format plan steps and execution results for final synthesis."""
    lines = ["Plan:"]
    for step in plan:
        tool_note = f" (tool: {step.suggested_tool})" if step.suggested_tool else ""
        lines.append(f"  {step.step_id}. {step.description}{tool_note}")

    lines.append("\nStep results:")
    for result in step_results:
        lines.append(
            f"  [{result.status}] Step {result.step_id}: {result.description}\n"
            f"    → {result.output}"
        )

    return "\n".join(lines)
