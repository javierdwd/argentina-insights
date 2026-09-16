"use client";

import { useEffect, useState } from "react";
import { Check, CircleNotch } from "@phosphor-icons/react";

const STEPS = [
  "Buscando datos relevantes",
  "Cruzando fuentes",
  "Armando la visualización",
];

export function CanvasPending({
  query,
  running,
}: {
  query?: string;
  running: boolean;
}) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => {
      setStep((current) => Math.min(current + 1, STEPS.length - 1));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [running]);

  return (
    <section
      className="canvas-transition-surface mx-auto w-full max-w-2xl rounded-3xl border border-border bg-card/75 p-6 shadow-[0_24px_60px_-48px_color-mix(in_oklab,var(--foreground)_35%,transparent)] md:p-8"
      aria-live="polite"
    >
      <div className="flex items-center gap-3 text-accent">
        {running ? (
          <CircleNotch
            size={20}
            weight="bold"
            className="animate-spin"
            aria-hidden
          />
        ) : null}
        <p className="text-sm font-semibold">
          {running ? STEPS[step] : "La respuesta continúa en el chat"}
        </p>
      </div>
      {query ? (
        <h2 className="mt-4 max-w-[32ch] font-display text-xl font-semibold leading-tight tracking-tight text-foreground md:text-2xl">
          {query}
        </h2>
      ) : null}
      {running ? (
        <div className="mt-7 border-t border-rule pt-5">
          <ol className="space-y-3">
            {STEPS.map((label, index) => {
              const complete = index < step;
              const active = index === step;
              return (
                <li
                  key={label}
                  className={[
                    "flex items-center gap-3 text-sm",
                    complete || active
                      ? "text-foreground"
                      : "text-muted-foreground/55",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
                      complete
                        ? "border-accent bg-accent text-accent-foreground"
                        : active
                          ? "border-accent bg-accent-soft text-accent"
                          : "border-border bg-secondary/60",
                    ].join(" ")}
                  >
                    {complete ? (
                      <Check size={11} weight="bold" aria-hidden />
                    ) : active ? (
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                    ) : null}
                  </span>
                  {label}
                </li>
              );
            })}
          </ol>
          <p className="mt-5 text-xs text-muted-foreground">
            La visualización va a aparecer acá cuando los datos estén listos.
          </p>
        </div>
      ) : null}
    </section>
  );
}
