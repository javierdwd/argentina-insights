"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { CommandBar } from "./CommandBar";

const EASE = [0.32, 0.72, 0, 1] as const;

interface HomeStageProps {
  /** Pre-rendered generative UI (e.g. DynamicRenderer output). */
  children: ReactNode;
}

/**
 * Cold bulletin shell — asymmetric brand + command + response stage.
 */
export function HomeStage({ children }: HomeStageProps) {
  const reduce = useReducedMotion();

  return (
    <main className="relative flex min-h-[100dvh] flex-col bg-background">
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-4 py-16 md:px-8 md:py-20 lg:px-10">
        <div className="grid grid-cols-1 items-end gap-12 md:grid-cols-2 md:gap-16 lg:gap-24">
          {/* Brand column */}
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE }}
            className="max-w-md"
          >
            <h1 className="font-display text-4xl font-semibold tracking-tight text-foreground md:text-5xl lg:text-6xl">
              Argentina Insights
            </h1>
            <p className="mt-4 max-w-[36ch] text-base leading-relaxed text-muted-foreground md:text-lg">
              Preguntá en lenguaje natural. El agente arma la vista.
            </p>
          </motion.div>

          {/* Interaction + response stage */}
          <div className="flex flex-col gap-10">
            <CommandBar />

            <motion.div
              initial={reduce ? false : { opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, ease: EASE, delay: 0.16 }}
              className="space-y-1"
            >
              <p className="text-xs text-muted-foreground">Respuesta de muestra</p>
              {children}
            </motion.div>
          </div>
        </div>
      </div>
    </main>
  );
}
