import { Wrench } from "lucide-react";
import type { AgentEvent } from "../lib/api";

interface Props {
  events: AgentEvent[];
  tools: string[];
}

export function AgentPlane({ events, tools }: Props) {
  const toolEvents = events.filter(
    (e) => e.type === "tool_start" || e.type === "tool_result" || e.type === "thinking",
  );

  return (
    <aside className="flex w-80 shrink-0 flex-col border-l border-plane-border bg-plane-surface">
      <div className="border-b border-plane-border px-3 py-2">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-plane-muted">
          <Wrench size={14} />
          Agent plane
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 font-mono text-xs">
        {toolEvents.length === 0 ? (
          <p className="text-plane-muted">Tool activity appears here during runs.</p>
        ) : (
          toolEvents.map((ev, i) => (
            <div
              key={`${ev.type}-${i}`}
              className="mb-2 rounded border border-plane-border bg-plane-bg p-2"
            >
              <div className="mb-1 text-plane-accent">
                {ev.type}
                {ev.iteration != null ? ` #${ev.iteration}` : ""}
              </div>
              {ev.tool && <div className="text-plane-warn">{ev.tool}</div>}
              {ev.arguments && (
                <pre className="mt-1 overflow-x-auto text-plane-muted">
                  {JSON.stringify(ev.arguments, null, 2)}
                </pre>
              )}
              {ev.result && (
                <pre className="mt-1 max-h-32 overflow-auto text-plane-success">
                  {ev.result.slice(0, 500)}
                  {ev.result.length > 500 ? "…" : ""}
                </pre>
              )}
            </div>
          ))
        )}
      </div>

      <div className="border-t border-plane-border p-3">
        <p className="mb-2 text-xs font-medium text-plane-muted">
          Tools ({tools.length})
        </p>
        <div className="flex max-h-28 flex-wrap gap-1 overflow-y-auto">
          {tools.map((t) => (
            <span
              key={t}
              className="rounded bg-plane-bg px-1.5 py-0.5 text-[10px] text-plane-muted"
            >
              {t}
            </span>
          ))}
        </div>
      </div>
    </aside>
  );
}
