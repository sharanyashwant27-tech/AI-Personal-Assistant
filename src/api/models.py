"""API request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32_000)


class ChatResponse(BaseModel):
    reply: str
    events: list[dict] = Field(default_factory=list)


class StatusResponse(BaseModel):
    backend: str
    agent_mode: bool
    cursor_model: str
    ghost_mode: bool
    mcp_enabled: bool
    mcp_online: bool
    mcp_url: str
    mcp_tool_count: int
    tools: list[str]
    message_count: int
    fact_count: int
    auto_mode: str
    auto_note: str


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]
