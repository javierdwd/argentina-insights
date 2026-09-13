"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MagnifyingGlass, X } from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { formatNumber } from "@/lib/format";
import { useCanvasAction, type CanvasSelection } from "./useCanvasAction";

const EASE = [0.32, 0.72, 0, 1] as const;
const CARD_W = 320;
const GAP = 12;
const MARGIN = 12;

function clampPopover(
  x: number,
  y: number,
  height: number,
): { left: number; top: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let left = x + GAP;
  let top = y + GAP;
  if (left + CARD_W > vw - MARGIN) left = x - CARD_W - GAP;
  if (left < MARGIN) left = MARGIN;
  if (top + height > vh - MARGIN) top = y - height - GAP;
  if (top < MARGIN) top = MARGIN;
  return { left, top };
}

/**
 * Selection popover — fixed near the click (portaled to body), dismisses
 * on scroll / outside click / Esc.
 */
export function CanvasInspector() {
  const { selected, anchor, busy, deepenSelection, clearSelected } =
    useCanvasAction();
  const reduce = useReducedMotion();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!selected) return;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        clearSelected();
        return;
      }
      if (event.key === "Enter" && !busy) {
        event.preventDefault();
        void deepenSelection();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, busy, clearSelected, deepenSelection]);

  useEffect(() => {
    if (!selected) return;
    const onScroll = () => clearSelected();
    window.addEventListener("scroll", onScroll, true);
    return () => window.removeEventListener("scroll", onScroll, true);
  }, [selected, clearSelected]);

  if (!mounted) return null;

  return createPortal(
    <AnimatePresence>
      {selected && anchor ? (
        <InspectorPopover
          key={`${selected.widget}:${selected.valor}:${anchor.x}:${anchor.y}`}
          selected={selected}
          anchor={anchor}
          busy={busy}
          reduce={Boolean(reduce)}
          onClose={clearSelected}
          onDeepen={() => void deepenSelection()}
        />
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}

function InspectorPopover({
  selected,
  anchor,
  busy,
  reduce,
  onClose,
  onDeepen,
}: {
  selected: CanvasSelection;
  anchor: { x: number; y: number };
  busy: boolean;
  reduce: boolean;
  onClose: () => void;
  onDeepen: () => void;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState(() =>
    clampPopover(anchor.x, anchor.y, 220),
  );
  const facts = selected.facts?.filter((f) => f.label && f.value) ?? [];

  useLayoutEffect(() => {
    const h = cardRef.current?.offsetHeight ?? 220;
    setPos(clampPopover(anchor.x, anchor.y, h));
  }, [anchor.x, anchor.y, selected.valor, facts.length]);

  useEffect(() => {
    const onPointer = (event: PointerEvent) => {
      const node = cardRef.current;
      if (!node) return;
      if (node.contains(event.target as Node)) return;
      onClose();
    };
    const timer = window.setTimeout(() => {
      window.addEventListener("pointerdown", onPointer, true);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("pointerdown", onPointer, true);
    };
  }, [onClose]);

  return (
    <motion.div
      ref={cardRef}
      role="dialog"
      aria-label="Selección"
      data-canvas-inspector
      initial={reduce ? false : { opacity: 0, y: 8, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={reduce ? undefined : { opacity: 0, y: 6, scale: 0.97 }}
      transition={{ duration: 0.22, ease: EASE }}
      style={{
        position: "fixed",
        left: pos.left,
        top: pos.top,
        width: CARD_W,
        zIndex: 60,
      }}
      className={[
        "overflow-y-auto rounded-xl border border-border/90 bg-secondary p-3.5",
        "shadow-[0_22px_48px_-14px_color-mix(in_oklab,var(--foreground)_60%,transparent),0_8px_20px_-8px_color-mix(in_oklab,var(--foreground)_35%,transparent)]",
        "ring-1 ring-foreground/8",
        "max-h-[min(42vh,22rem)]",
      ].join(" ")}
    >
      <div className="flex flex-col gap-3">
        <div className="flex min-w-0 items-start gap-3">
          {selected.imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- external CDN posters
            <img
              src={selected.imageUrl}
              alt=""
              width={48}
              height={72}
              className="h-[4.25rem] w-11 shrink-0 rounded-md border border-rule object-cover"
            />
          ) : null}
          <div className="min-w-0 flex-1">
            <p className="font-display text-[0.6rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Selección
            </p>
            <p className="mt-1 text-sm font-medium leading-snug text-foreground">
              {selected.valor}
            </p>
            {selected.contexto ? (
              <p className="mt-0.5 text-[0.7rem] leading-relaxed text-muted-foreground">
                {selected.contexto}
              </p>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
          >
            <X size={12} weight="regular" />
            Cerrar
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onDeepen}
            className={[
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
              "border-accent/30 bg-card text-foreground",
              "hover:border-accent hover:bg-accent hover:text-accent-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
              "disabled:cursor-not-allowed disabled:opacity-45",
            ].join(" ")}
          >
            <MagnifyingGlass size={12} weight="regular" />
            {busy ? "Consultando…" : "Profundizar"}
          </button>
        </div>

        {facts.length > 0 ? (
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-rule">
                <th
                  scope="col"
                  className="pb-1.5 pr-3 font-display text-[0.6rem] font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  Indicador
                </th>
                <th
                  scope="col"
                  className="pb-1.5 font-display text-[0.6rem] font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  Valor
                </th>
              </tr>
            </thead>
            <tbody>
              {facts.map((fact) => (
                <tr
                  key={`${fact.label}:${fact.value}`}
                  className="border-b border-rule/50 last:border-0"
                >
                  <td className="py-1.5 pr-3 text-muted-foreground">
                    {fact.label}
                  </td>
                  <td className="py-1.5 tabular-nums text-foreground">
                    {fact.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-xs text-muted-foreground">
            Pulsá Profundizar para cruzar más datos.
          </p>
        )}
      </div>
    </motion.div>
  );
}

/** Build inspector rows from a chart data row + series defs. */
export function factsFromSeriesRow(
  row: Record<string, unknown> | undefined,
  series: { key: string; label: string }[],
): { label: string; value: string }[] {
  if (!row || !series?.length) return [];
  const out: { label: string; value: string }[] = [];
  for (const s of series) {
    const raw = row[s.key];
    if (raw === null || raw === undefined || raw === "") continue;
    const n =
      typeof raw === "number"
        ? raw
        : typeof raw === "string" && raw.trim() !== ""
          ? Number(raw)
          : NaN;
    const value = Number.isFinite(n) ? formatNumber(n) : String(raw);
    out.push({ label: s.label || s.key, value });
  }
  return out;
}
