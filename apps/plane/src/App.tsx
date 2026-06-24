import { useCallback, useEffect, useState } from "react";
import { AgentPlane } from "./components/AgentPlane";
import { ChatPanel } from "./components/ChatPanel";
import { Header } from "./components/Header";
import { InputBar } from "./components/InputBar";
import {
  clearHistory,
  connectAgentSocket,
  fetchHistory,
  fetchStatus,
  type AgentEvent,
  type ChatMessage,
  type StatusInfo,
} from "./lib/api";

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function App() {
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([fetchStatus(), fetchHistory()]);
      setStatus(s);
      setMessages(h);
      setError(null);
    } catch {
      setError("Backend offline — start: python src/main.py serve");
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, [refresh]);

  const send = useCallback((text: string) => {
    if (text === "/clear") {
      clearHistory().then(() => {
        setMessages([]);
        setEvents([]);
      });
      return;
    }

    setBusy(true);
    setEvents([]);
    setError(null);

    const userMsg: ChatMessage = {
      id: uid(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages((m) => [...m, userMsg]);

    let assistantText = "";

    const cleanup = connectAgentSocket(
      text,
      (ev) => {
        setEvents((e) => [...e, ev]);
        if (ev.type === "assistant" || ev.type === "final") {
          assistantText = ev.content ?? assistantText;
        }
        if (ev.type === "tool_result" && ev.tool && ev.result) {
          const result = ev.result;
          setMessages((m) => [
            ...m,
            {
              id: uid(),
              role: "tool",
              content: `${ev.tool}\n${result.slice(0, 800)}`,
              timestamp: Date.now(),
            },
          ]);
        }
      },
      () => {
        if (assistantText) {
          setMessages((m) => [
            ...m,
            {
              id: uid(),
              role: "assistant",
              content: assistantText,
              timestamp: Date.now(),
            },
          ]);
        }
        setBusy(false);
        refresh();
      },
      (err) => {
        setError(err);
        setBusy(false);
      },
    );

    return cleanup;
  }, [refresh]);

  return (
    <div className="flex h-full flex-col bg-plane-bg text-plane-text">
      <Header status={status} busy={busy} />

      {error && (
        <div className="border-b border-plane-warn/30 bg-plane-warn/10 px-4 py-2 text-center text-xs text-plane-warn">
          {error}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">
          <ChatPanel messages={messages} />
          <InputBar onSend={send} disabled={busy || !status} />
        </main>
        <AgentPlane events={events} tools={status?.tools ?? []} />
      </div>
    </div>
  );
}
