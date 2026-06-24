export interface AgentEvent {
  type: string;
  content?: string;
  tool?: string;
  arguments?: Record<string, unknown>;
  result?: string;
  iteration?: number;
  message?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  timestamp: number;
}

export interface StatusInfo {
  backend: string;
  agent_mode: boolean;
  cursor_model: string;
  ghost_mode: boolean;
  mcp_enabled: boolean;
  mcp_online: boolean;
  mcp_url: string;
  mcp_tool_count: number;
  tools: string[];
  message_count: number;
  fact_count: number;
  auto_mode: string;
  auto_note: string;
}

export async function fetchStatus(): Promise<StatusInfo> {
  const res = await fetch("/api/status");
  if (!res.ok) throw new Error("Backend offline");
  return res.json();
}

export async function fetchHistory(): Promise<ChatMessage[]> {
  const res = await fetch("/api/history");
  if (!res.ok) return [];
  const data = await res.json();
  return (data.messages ?? []).map((m: { role: string; content: string }, i: number) => ({
    id: `hist-${i}`,
    role: m.role as ChatMessage["role"],
    content: m.content,
    timestamp: Date.now() - (data.messages.length - i) * 1000,
  }));
}

export async function clearHistory(): Promise<void> {
  await fetch("/api/clear", { method: "POST" });
}

export async function clearMemory(): Promise<void> {
  await fetch("/api/forget", { method: "POST" });
}

export function connectAgentSocket(
  message: string,
  onEvent: (event: AgentEvent) => void,
  onDone: () => void,
  onError: (err: string) => void,
): () => void {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const ws = new WebSocket(`${protocol}//${host}/ws/agent`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ message }));
  };

  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data) as AgentEvent;
    if (data.type === "done") {
      onDone();
      ws.close();
      return;
    }
    if (data.type === "error") {
      onError(data.message ?? "Unknown error");
      return;
    }
    onEvent(data);
  };

  ws.onerror = () => onError("WebSocket connection failed");
  ws.onclose = () => onDone();

  return () => ws.close();
}
