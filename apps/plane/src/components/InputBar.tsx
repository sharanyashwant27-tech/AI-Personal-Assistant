import { ArrowUp, Loader2 } from "lucide-react";
import { type FormEvent, useState } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function InputBar({ onSend, disabled }: Props) {
  const [text, setText] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(e);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="border-t border-plane-border bg-plane-surface p-3"
    >
      <div className="flex items-end gap-2 rounded-lg border border-plane-border bg-plane-bg px-3 py-2 focus-within:border-plane-accent">
        <span className="pb-2 font-mono text-sm text-plane-accent">›</span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
          rows={1}
          placeholder="Ask the agent… (Enter to send, Shift+Enter for newline)"
          className="max-h-32 min-h-[24px] flex-1 resize-none bg-transparent font-mono text-sm outline-none placeholder:text-plane-muted"
        />
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="mb-0.5 rounded-md bg-plane-accent p-1.5 text-white disabled:opacity-40"
        >
          {disabled ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} />}
        </button>
      </div>
      <p className="mt-1.5 text-center text-[10px] text-plane-muted">
        /clear history · Cursor subscription auth · MCP sandbox
      </p>
    </form>
  );
}
