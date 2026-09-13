"use client";

import { useCallback, useState } from "react";
import { ArrowRight } from "@phosphor-icons/react";
import { useCanvasAction } from "./useCanvasAction";

const FOLLOW_UPS = [
  "Superponé EMAE al blue",
  "Compará el blue por mandato presidencial",
  "Semana con el pico de brecha: ¿qué votó el Congreso?",
  "Cruzá riesgo país con confianza en el gobierno",
] as const;

/**
 * LLM follow-up chips under the Economía destination canvas.
 */
export function DestinationFollowUps() {
  const { busy, runCanvasAction } = useCanvasAction();
  const [pending, setPending] = useState<string | null>(null);

  const onPick = useCallback(
    async (text: string) => {
      if (busy || pending) return;
      setPending(text);
      try {
        await runCanvasAction(text);
      } finally {
        setPending(null);
      }
    },
    [busy, pending, runCanvasAction],
  );

  return (
    <div className="mt-6 border-t border-border/70 pt-4">
      <p className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Seguí explorando
      </p>
      <ul className="flex flex-wrap gap-2">
        {FOLLOW_UPS.map((text) => {
          const active = pending === text;
          const disabled = busy || pending !== null;
          return (
            <li key={text}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => void onPick(text)}
                className={[
                  "group inline-flex max-w-full items-center gap-1.5 rounded-xl px-3 py-2 text-left text-[0.8rem] leading-snug",
                  "bg-card ring-1 ring-border/80 transition-colors",
                  "hover:bg-accent-soft hover:text-accent",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
                  "disabled:cursor-not-allowed disabled:opacity-45",
                  active ? "bg-accent-soft text-accent" : "text-foreground",
                ].join(" ")}
              >
                <span className="min-w-0">{text}</span>
                <ArrowRight
                  size={12}
                  weight="regular"
                  className="shrink-0 opacity-50 group-hover:opacity-100"
                  aria-hidden
                />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
