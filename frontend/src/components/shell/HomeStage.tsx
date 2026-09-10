"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

const EASE = [0.32, 0.72, 0, 1] as const;

interface HomeStageProps {
  /** CopilotChat panel rendered in the right column. */
  chat: ReactNode;
  /** Generative UI widgets rendered in the left stage area (optional). */
  stage?: ReactNode;
}

/**
 * Two-column shell: brand + stage (left) · chat panel (right).
 *
 * Desktop: 50/50 grid, full viewport height.
 * Mobile:  stacked — compact brand, then chat.
 */
export function HomeStage({ chat, stage }: HomeStageProps) {
  const reduce = useReducedMotion();

  return (
    <main className="flex min-h-[100dvh] flex-col md:grid md:grid-cols-2">
      {/* ── Left column: brand + stage ─────────────────────────────────── */}
      <div className="flex flex-col justify-between px-8 py-10 md:px-12 md:py-14 lg:px-16">
        {/* Brand */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE }}
        >
          <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl lg:text-5xl">
            Argentina Insights
          </h1>
          <p className="mt-3 max-w-[34ch] text-sm leading-relaxed text-muted-foreground md:text-base">
            Preguntá en lenguaje natural. El agente arma la vista.
          </p>
        </motion.div>

        {/* Stage area — empty for now, widgets land here */}
        <motion.div
          initial={reduce ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, ease: EASE, delay: 0.2 }}
          className="mt-10 flex-1 md:mt-12"
        >
          {stage ?? (
            <p className="text-xs text-muted-foreground/50 select-none">
              La vista aparece acá.
            </p>
          )}
        </motion.div>
      </div>

      {/* ── Right column: chat ─────────────────────────────────────────── */}
      <div className="flex h-[70dvh] flex-col border-t border-border md:h-[100dvh] md:border-l md:border-t-0">
        {chat}
      </div>
    </main>
  );
}
