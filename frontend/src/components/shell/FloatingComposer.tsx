"use client";

import { useCallback, useState, type FormEvent, type KeyboardEvent } from "react";
import { ChatCircle, PaperPlaneTilt } from "@phosphor-icons/react";
import {
  useAgent,
  useCopilotKit,
  UseAgentUpdate,
} from "@copilotkit/react-core/v2";

interface FloatingComposerProps {
  onShowChat: () => void;
}

/**
 * Fixed bottom prompt when the desktop chat column is hidden.
 * Same path as starters: addMessage + runAgent (no canvas provider required).
 */
export function FloatingComposer({ onShowChat }: FloatingComposerProps) {
  const { agent } = useAgent({
    agentId: "argentina_insights",
    updates: [UseAgentUpdate.OnRunStatusChanged],
  });
  const { copilotkit } = useCopilotKit();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);

  const busy = Boolean(agent.isRunning) || pending;

  const submit = useCallback(async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setPending(true);
    try {
      agent.addMessage({
        id: crypto.randomUUID(),
        role: "user",
        content: text,
      });
      await copilotkit.runAgent({ agent });
    } catch (error) {
      console.error("FloatingComposer: runAgent failed", error);
    } finally {
      setPending(false);
    }
  }, [agent, busy, copilotkit, draft]);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  };

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-30 hidden md:block">
      <div className="pointer-events-auto mx-auto w-full max-w-3xl px-6 pb-5 lg:px-12">
        <form
          onSubmit={onSubmit}
          className="flex items-end gap-2 rounded-2xl bg-card/95 p-2 shadow-[0_18px_48px_-24px_color-mix(in_oklab,var(--foreground)_45%,transparent)] ring-1 ring-border backdrop-blur-md"
        >
          <button
            type="button"
            onClick={onShowChat}
            className="mb-0.5 inline-flex shrink-0 items-center gap-1.5 rounded-xl px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
            aria-label="Mostrar chat"
          >
            <ChatCircle size={18} weight="regular" />
            <span className="hidden sm:inline">Chat</span>
          </button>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={busy}
            placeholder="Preguntá sobre lo que ves…"
            className="max-h-28 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-snug text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="mb-0.5 inline-flex shrink-0 items-center justify-center rounded-xl bg-accent px-3 py-2 text-accent-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Enviar"
          >
            <PaperPlaneTilt size={16} weight="fill" />
          </button>
        </form>
      </div>
    </div>
  );
}
