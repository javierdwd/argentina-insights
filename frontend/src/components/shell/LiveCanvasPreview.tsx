"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, Broadcast } from "@phosphor-icons/react";
import { DynamicRenderer } from "@/components/registry/DynamicRenderer";
import type { UINode } from "@/lib/uitree";
import { runViewTransition } from "@/lib/view-transition";
import {
  loadEntryPreview,
  type EntryPreviewKind,
} from "./entry-preview";

const PREVIEW_OPTIONS: { id: EntryPreviewKind; label: string }[] = [
  { id: "fx", label: "Dólar" },
  { id: "inflacion", label: "Inflación" },
  { id: "riesgo", label: "Riesgo país" },
];

interface LiveCanvasPreviewProps {
  busy: boolean;
  onExplore: () => void;
}

export function LiveCanvasPreview({
  busy,
  onExplore,
}: LiveCanvasPreviewProps) {
  const [kind, setKind] = useState<EntryPreviewKind>("fx");
  const [result, setResult] = useState<{
    kind: EntryPreviewKind;
    tree: UINode | null;
    failed: boolean;
  }>({ kind: "fx", tree: null, failed: false });

  useEffect(() => {
    let active = true;
    loadEntryPreview(kind)
      .then((next) => {
        if (active) setResult({ kind, tree: next, failed: false });
      })
      .catch(() => {
        if (active) setResult({ kind, tree: null, failed: true });
      });
    return () => {
      active = false;
    };
  }, [kind]);
  const tree = result.kind === kind ? result.tree : null;
  const failed = result.kind === kind && result.failed;

  return (
    <div className="relative min-w-0 lg:pt-10">
      <div
        aria-hidden
        className="absolute -inset-8 -z-10 rounded-[3rem] bg-[radial-gradient(circle_at_45%_35%,color-mix(in_oklab,var(--sky)_30%,transparent),transparent_68%)]"
      />
      <div className="entry-preview-transition-surface overflow-hidden rounded-3xl border border-border/85 bg-card/85 p-3 shadow-[0_30px_75px_-52px_color-mix(in_oklab,var(--foreground)_40%,transparent),inset_0_1px_0_rgba(255,255,255,0.72)] backdrop-blur-sm md:p-4 lg:rotate-[0.7deg]">
        <div className="flex flex-wrap items-center justify-between gap-3 px-2 pb-3 pt-1">
          <span className="inline-flex items-center gap-2 text-xs font-semibold text-accent">
            <Broadcast size={14} weight="bold" aria-hidden />
            Datos reales
          </span>
          <button
            type="button"
            onClick={onExplore}
            disabled={busy}
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-accent disabled:opacity-45"
          >
            Abrir Economía
            <ArrowUpRight size={14} aria-hidden />
          </button>
        </div>
        <div
          className="mb-3 flex gap-1 px-2"
          role="tablist"
          aria-label="Visualización de ejemplo"
        >
          {PREVIEW_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              role="tab"
              aria-selected={kind === option.id}
              onClick={() =>
                void runViewTransition(() => setKind(option.id))
              }
              className={[
                "rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                kind === option.id
                  ? "bg-accent-soft text-foreground"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground",
              ].join(" ")}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="min-h-[22rem] lg:-rotate-[0.7deg]">
          {tree ? (
            <DynamicRenderer node={tree} />
          ) : failed ? (
            <div className="flex min-h-[22rem] items-center justify-center rounded-2xl bg-secondary/55 px-8 text-center text-sm text-muted-foreground">
              La visualización en vivo no está disponible ahora.
            </div>
          ) : (
            <div
              className="flex min-h-[22rem] flex-col rounded-2xl border border-border/70 bg-secondary/45 px-6 pb-6 pt-7"
              aria-label="Cargando visualización en vivo"
            >
              <div className="h-3 w-44 animate-pulse rounded bg-border/80" />
              <div className="mt-8 flex flex-1 gap-4">
                <div className="w-7 shrink-0 space-y-12 pt-1">
                  <div className="h-2 rounded bg-border/65" />
                  <div className="h-2 rounded bg-border/65" />
                  <div className="h-2 rounded bg-border/65" />
                </div>
                <div className="relative flex-1 border-b border-l border-border/80">
                  <div className="absolute inset-x-0 top-1/4 border-t border-border/45" />
                  <div className="absolute inset-x-0 top-1/2 border-t border-border/45" />
                  <div className="absolute inset-x-0 top-3/4 border-t border-border/45" />
                  <div className="absolute inset-x-[6%] bottom-[24%] h-[2px] origin-left -rotate-3 animate-pulse bg-accent/35" />
                  <div className="absolute inset-x-[42%] bottom-[38%] h-[2px] origin-left rotate-2 animate-pulse bg-sky/55" />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
