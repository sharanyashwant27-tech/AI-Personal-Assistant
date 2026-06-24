import { useEffect, useRef } from "react";
import type { ChatMessage } from "../lib/api";

interface Props {
  messages: ChatMessage[];
}

export function ChatPanel({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
        <p className="font-mono text-sm text-plane-muted">
          plane@cursor ~ agent ready
        </p>
        <p className="max-w-md text-sm text-plane-muted">
          Ask to read files, run commands, explore your workspace. Tools execute
          via MCP Docker sandbox.
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {[
            "List files in src/",
            "Read config/system_prompt.txt",
            "Search for *.py in src",
          ].map((hint) => (
            <span
              key={hint}
              className="rounded border border-plane-border bg-plane-surface px-2 py-1 font-mono text-xs text-plane-muted"
            >
              {hint}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 font-mono text-sm">
      {messages.map((msg) => (
        <div key={msg.id} className="mb-4">
          <div className="mb-1 flex items-center gap-2 text-xs text-plane-muted">
            <span
              className={
                msg.role === "user"
                  ? "text-plane-accent"
                  : msg.role === "tool"
                    ? "text-plane-warn"
                    : "text-plane-success"
              }
            >
              {msg.role === "user" ? "you" : msg.role === "tool" ? "tool" : "agent"}
            </span>
            <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
          </div>
          <div
            className={`whitespace-pre-wrap rounded-lg border border-plane-border px-3 py-2 ${
              msg.role === "user"
                ? "bg-plane-user"
                : msg.role === "tool"
                  ? "bg-plane-bg opacity-90"
                  : "bg-plane-agent"
            }`}
          >
            {msg.content}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
