import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cursor_client.tool_call_parser import parse_redacted_tool_calls

SAMPLE = (
    "<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>\n"
    "list_dir\n"
    "<｜tool▁sep｜>relative_workspace_path\n"
    "documents\n"
    "<｜tool▁call▁end｜>"
)

print("sample contains tool_call:", "tool_call" in SAMPLE)
print("parsed:", parse_redacted_tool_calls(SAMPLE))
