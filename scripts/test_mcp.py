"""Test MCP Docker server connectivity and tool execution."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mcp_client.manager import MCPManager


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/mcp"
    manager = MCPManager(transport="http", server_url=url)

    print(f"Connecting to MCP server: {url}")
    tools = manager.list_tools()
    print(f"Tools ({len(tools)}): {[tool.name for tool in tools]}")

    result = manager.call_tool(
        "write_file",
        {
            "path": "data/mcp_test_output.txt",
            "content": "MCP agent-tools server is working.\n",
        },
    )
    print("write_file:", result)

    read_back = manager.call_tool(
        "read_file",
        {"path": "data/mcp_test_output.txt"},
    )
    print("read_file:", read_back.strip())

    listing = manager.call_tool("list_directory", {"path": "src"})
    print("list_directory src (first 5 lines):")
    for line in listing.splitlines()[:5]:
        print(" ", line)

    print("\nMCP test passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"MCP test failed: {e}", file=sys.stderr)
        raise SystemExit(1)
