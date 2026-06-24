"""AI logic — tool definitions and registry for agent tool calling."""

import ast
import operator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from agent_memory import AgentMemory
from retrieval import RetrievalPipeline


@dataclass(frozen=True)
class Tool:
    """A callable tool exposed to the agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]


class ToolRegistry:
    """Registers tools and executes them from LLM tool calls."""

    def __init__(
        self,
        retrieval: RetrievalPipeline | None,
        agent_memory: AgentMemory,
    ) -> None:
        self._retrieval = retrieval
        self._agent_memory = agent_memory
        self._tools: dict[str, Tool] = {}
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all available agent tools."""
        self._add(
            name="search_documents",
            description="Search indexed documents for relevant information.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the document index.",
                    }
                },
                "required": ["query"],
            },
            handler=self._search_documents,
        )
        self._add(
            name="index_documents",
            description="Load and index all files from the documents folder.",
            parameters={"type": "object", "properties": {}},
            handler=self._index_documents,
        )
        self._add(
            name="remember_fact",
            description="Store a fact in long-term agent memory for future sessions.",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Fact identifier."},
                    "value": {"type": "string", "description": "Fact value."},
                },
                "required": ["key", "value"],
            },
            handler=self._remember_fact,
        )
        self._add(
            name="recall_facts",
            description="Retrieve all facts stored in agent memory.",
            parameters={"type": "object", "properties": {}},
            handler=self._recall_facts,
        )
        self._add(
            name="get_current_time",
            description="Get the current UTC date and time.",
            parameters={"type": "object", "properties": {}},
            handler=self._get_current_time,
        )
        self._add(
            name="calculate",
            description="Evaluate a basic math expression (numbers and + - * / parentheses).",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, e.g. '(2 + 3) * 4'.",
                    }
                },
                "required": ["expression"],
            },
            handler=self._calculate,
        )

    def _add(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., str],
    ) -> None:
        self._tools[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    def register_external_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., str],
    ) -> None:
        """Register a tool from an external provider such as MCP."""
        self._add(name, description, parameters, handler)

    def get_openai_schemas(self) -> list[dict[str, Any]]:
        """Return tool schemas in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def get_tool_names(self) -> list[str]:
        """Return registered tool names."""
        return list(self._tools.keys())

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name with parsed arguments."""
        if name not in self._tools:
            return f"Error: unknown tool '{name}'."

        try:
            return self._tools[name].handler(**arguments)
        except TypeError as e:
            return f"Error: invalid arguments for '{name}': {e}"
        except Exception as e:
            return f"Error executing '{name}': {e}"

    def _search_documents(self, query: str) -> str:
        if self._retrieval is None or self._retrieval.indexed_chunks == 0:
            return "No documents indexed. Run index_documents first."

        chunks = self._retrieval.retrieve(query)
        if not chunks:
            return "No relevant documents found."

        parts = []
        for chunk in chunks:
            parts.append(
                f"[{chunk.source} | score: {chunk.score:.2f}]\n{chunk.content}"
            )
        return "\n\n---\n\n".join(parts)

    def _index_documents(self) -> str:
        if self._retrieval is None:
            return "Error: retrieval pipeline not configured."
        try:
            count = self._retrieval.index_documents()
        except (ValueError, RuntimeError) as e:
            return f"Indexing failed: {e}"
        return f"Successfully indexed {count} chunk(s)."

    def _remember_fact(self, key: str, value: str) -> str:
        try:
            self._agent_memory.remember_fact(key, value)
        except ValueError as e:
            return f"Error: {e}"
        return f"Stored fact '{key}'."

    def _recall_facts(self) -> str:
        return self._agent_memory.recall_context()

    def _get_current_time(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _calculate(self, expression: str) -> str:
        try:
            result = _safe_eval(expression)
        except ValueError as e:
            return f"Calculation error: {e}"
        return str(result)


def _safe_eval(expression: str) -> float:
    """Safely evaluate a math expression using AST."""
    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
    }

    def _eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_operators:
            return allowed_operators[type(node.op)](_eval_node(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_operators:
            return allowed_operators[type(node.op)](
                _eval_node(node.left), _eval_node(node.right)
            )
        raise ValueError("Unsupported expression.")

    tree = ast.parse(expression.strip(), mode="eval")
    return _eval_node(tree.body)
