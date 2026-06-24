"""FastAPI server — backend for Plane desktop UI."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.models import ChatRequest, ChatResponse, HistoryResponse, StatusResponse
from api.service import AgentService
from runtime import create_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = create_runtime()
    app.state.service = AgentService(state)
    yield


app = FastAPI(title="Plane API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status", response_model=StatusResponse)
def get_status() -> dict:
    return app.state.service.get_status()


@app.get("/api/history", response_model=HistoryResponse)
def get_history() -> dict:
    return {"messages": app.state.service.get_history()}


@app.post("/api/chat", response_model=ChatResponse)
async def post_chat(body: ChatRequest) -> dict:
    reply, events = await app.state.service.run_chat(body.message)
    return {"reply": reply, "events": events}


@app.post("/api/clear")
def clear_history() -> dict:
    app.state.service.clear_history()
    return {"ok": True}


@app.post("/api/forget")
def clear_memory() -> dict:
    app.state.service.clear_memory()
    return {"ok": True}


@app.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket) -> None:
    await websocket.accept()
    service: AgentService = websocket.app.state.service

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            message = str(payload.get("message", "")).strip()
            if not message:
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            async for event in service.stream_chat(message):
                await websocket.send_json(event)
            await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        return


def _ui_dist_dir() -> Path | None:
    dist = Path(__file__).resolve().parents[2] / "apps" / "plane" / "dist"
    if dist.is_dir() and (dist / "index.html").is_file():
        return dist
    return None


def _mount_ui(app: FastAPI) -> None:
    dist = _ui_dist_dir()
    if dist is not None:
        app.mount("/", StaticFiles(directory=dist, html=True), name="plane-ui")
        return

    @app.get("/", response_class=HTMLResponse)
    def ui_missing() -> str:
        return """<!doctype html>
<html><head><meta charset="utf-8"><title>Plane</title></head>
<body style="font-family:system-ui;max-width:40rem;margin:3rem auto;padding:0 1rem">
<h1>Plane UI not built</h1>
<p>Run from the project root:</p>
<pre>cd apps/plane && npm install && npm run build</pre>
<p>Or start the dev server:</p>
<pre>cd apps/plane && npm run dev</pre>
<p>Then open <a href="http://localhost:5173">http://localhost:5173</a></p>
</body></html>"""


_mount_ui(app)


def main() -> None:
    import uvicorn

    from config import load_settings

    settings = load_settings()
    uvicorn.run(
        "api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        app_dir="src",
    )


if __name__ == "__main__":
    main()
