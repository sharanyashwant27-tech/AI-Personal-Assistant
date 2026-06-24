import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cursor_client._vendor import ensure_vendor_path

ensure_vendor_path()
from cursor_agent_client import CursorAgentClient  # noqa: E402
from cursor_streaming_decoder import CursorStreamDecoder  # noqa: E402
import httpx  # noqa: E402


async def main() -> None:
    client = CursorAgentClient(workspace_root=Path(__file__).resolve().parent.parent)
    auth = client.runtime.get_active_token().split("::", 1)[-1]
    sid = client.generate_session_id(auth)
    ck = client.generate_hashed_64_hex(auth)
    cs = client.generate_cursor_checksum(auth)
    body = client.generate_request_body(
        [{"role": "user", "content": "List files in documents/ only"}],
        "default",
    )
    url = f"{client.base_url}/aiserver.v1.ChatService/StreamUnifiedChatWithTools"
    headers = client.get_headers(auth, sid, ck, cs)
    dec = CursorStreamDecoder()
    thinking: list[str] = []
    types: dict[str, int] = {}

    async with httpx.AsyncClient(http2=True, timeout=120.0) as http:
        async with http.stream("POST", url, headers=headers, content=body) as resp:
            async for ch in resp.aiter_bytes():
                for m in dec.feed_data(ch):
                    types[m.msg_type] = types.get(m.msg_type, 0) + 1
                    if m.msg_type == "thinking":
                        thinking.append(m.content)

    print("message types:", types)
    combined = "".join(thinking)
    chunks = re.findall(r'text:\s*"((?:\\.|[^"\\])*)"', combined)
    merged = "".join(c.replace("\\n", "\n").replace('\\"', '"') for c in chunks)
    print("merged tail:", repr(merged[-500:]))


if __name__ == "__main__":
    asyncio.run(main())
