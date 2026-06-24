import { Moon, Sun, Terminal } from "lucide-react";
import { useTheme } from "../theme/ThemeContext";
import type { StatusInfo } from "../lib/api";

interface Props {
  status: StatusInfo | null;
  busy: boolean;
}

export function Header({ status, busy }: Props) {
  const { theme, toggle } = useTheme();

  return (
    <header className="flex items-center justify-between border-b border-plane-border bg-plane-surface px-4 py-2.5">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-plane-accent/15 text-plane-accent">
          <Terminal size={18} />
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-tight">Plane</h1>
          <p className="text-xs text-plane-muted">Cursor agent terminal</p>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs text-plane-muted">
        <span className="hidden sm:inline">
          {status?.cursor_model ?? "—"} · {status?.auto_mode ?? "agent"}
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className={`h-2 w-2 rounded-full ${
              busy
                ? "animate-pulse bg-plane-warn"
                : status?.mcp_online
                  ? "bg-plane-success"
                  : "bg-plane-muted"
            }`}
          />
          MCP {status?.mcp_online ? "online" : "offline"}
        </span>
        <button
          type="button"
          onClick={toggle}
          className="rounded-md border border-plane-border p-1.5 hover:bg-plane-bg"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  );
}
