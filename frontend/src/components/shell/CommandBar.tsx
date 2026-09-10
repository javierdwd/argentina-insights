"use client";

import { MagnifyingGlassIcon } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "motion/react";
import { useState } from "react";

const EASE = [0.32, 0.72, 0, 1] as const;

/**
 * Fake command surface for the scaffold.
 * Visual double-bezel affordance; real Cmd+K wiring comes later.
 */
export function CommandBar() {
  const reduce = useReducedMotion();
  const [pressed, setPressed] = useState(false);

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: EASE, delay: 0.08 }}
    >
      {/* Outer shell — double-bezel */}
      <button
        type="button"
        onMouseDown={() => setPressed(true)}
        onMouseUp={() => setPressed(false)}
        onMouseLeave={() => setPressed(false)}
        onClick={() => {
          /* Scaffold: command palette not wired yet */
        }}
        className="group w-full max-w-md rounded-[1.25rem] border border-foreground/5 bg-foreground/[0.04] p-1.5 text-left transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.98]"
        style={{ transform: pressed ? "scale(0.98)" : undefined }}
        aria-label="Open command. Shortcut Command K coming soon."
      >
        {/* Inner field */}
        <span className="flex items-center gap-3 rounded-[calc(1.25rem-0.375rem)] border border-border/80 bg-card px-4 py-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
          <MagnifyingGlassIcon
            weight="light"
            className="size-5 shrink-0 text-muted-foreground"
            aria-hidden
          />
          <span className="flex-1 truncate text-[15px] text-muted-foreground">
            Cotización, inflación, un senador…
          </span>
          <kbd className="hidden items-center gap-0.5 rounded-md border border-border bg-background px-1.5 py-0.5 font-sans text-[11px] text-muted-foreground sm:inline-flex">
            <span className="text-xs">⌘</span>K
          </kbd>
        </span>
      </button>
    </motion.div>
  );
}
