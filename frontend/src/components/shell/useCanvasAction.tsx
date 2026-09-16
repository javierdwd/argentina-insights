"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  useAgent,
  useCopilotKit,
  UseAgentUpdate,
} from "@copilotkit/react-core/v2";
import type { CanvasTipo } from "./infer-canvas-tipo";
import type { CanvasBrush } from "./canvas-brush";
import { useChatShell } from "./HomeStage";

export type { CanvasTipo } from "./infer-canvas-tipo";
export type { CanvasBrush } from "./canvas-brush";

/** One local key-value row shown in the inspector (no agent roundtrip). */
export type CanvasFact = {
  label: string;
  value: string;
};

/** Stable selection fact — UI owns it; agent only when user deepens. */
export type CanvasSelection = {
  tipo: CanvasTipo;
  valor: string;
  widget: string;
  /** Optional node title for short context. */
  contexto?: string;
  /** Instant inspector rows from data already on the canvas. */
  facts?: CanvasFact[];
  /** Optional poster / avatar URL — shown in the inspector, never as valor. */
  imageUrl?: string;
  /**
   * Optional human follow-up line (e.g. authored later by compose).
   * When set, this is what Profundizar sends to the agent / shows in chat.
   */
  prompt?: string;
};

/** Natural Spanish line for chat + agent — never the machine key=value form. */
export function formatCanvasSelection(s: CanvasSelection): string {
  const authored = s.prompt?.trim();
  if (authored) return authored;

  const titleFact = s.facts?.find((f) =>
    /t[ií]tulo|^title$/i.test(f.label),
  )?.value;
  // Never deepen on a poster CDN URL — prefer título from facts.
  const rawValor = s.valor.trim();
  const valor =
    /^https?:\/\//i.test(rawValor) && titleFact?.trim()
      ? titleFact.trim()
      : rawValor;
  const ctx = s.contexto?.trim();
  const quote = (text: string) => `«${text}»`;

  switch (s.tipo) {
    case "fecha":
      return ctx
        ? `Profundizá el ${valor} de ${quote(ctx)}: ¿qué más hay ese día?`
        : `Profundizá el ${valor}: ¿qué más hay ese día?`;
    case "persona":
      return ctx
        ? `Profundizá sobre ${valor} (en ${quote(ctx)}): ficha y otras estadísticas.`
        : `Profundizá sobre ${valor}: ficha y otras estadísticas.`;
    case "provincia":
      return ctx
        ? `Profundizá ${valor} en ${quote(ctx)}.`
        : `Profundizá la provincia ${valor}.`;
    case "fila": {
      const voteDetail =
        s.widget === "Acta" || Boolean(titleFact && titleFact !== valor);
      if (voteDetail && s.widget === "Acta") {
        const short =
          titleFact && titleFact.length > 90
            ? `${titleFact.slice(0, 87)}…`
            : titleFact ?? valor;
        return ctx
          ? `Quiero el detalle de ${quote(short)} (${valor}) en ${quote(ctx)}: mostrá cómo votó cada legislador.`
          : `Quiero el detalle de ${quote(short)} (${valor}): mostrá cómo votó cada legislador.`;
      }
      // Film / titled list row — ask for the ficha by title.
      if (titleFact || s.widget === "List") {
        return ctx
          ? `Profundizá sobre ${quote(valor)} (en ${quote(ctx)}): ficha y otras estadísticas.`
          : `Profundizá sobre ${quote(valor)}: ficha y otras estadísticas.`;
      }
      return ctx
        ? `Quiero profundizar en ${quote(valor)} de ${quote(ctx)}.`
        : `Quiero profundizar en ${quote(valor)}.`;
    }
  }
}

type CanvasActionValue = {
  busy: boolean;
  selected: CanvasSelection | null;
  /** Viewport coords where the selection click landed (for the popover). */
  anchor: { x: number; y: number } | null;
  /** Cross-widget highlight derived from the current selection. */
  brush: CanvasBrush | null;
  selectedText: string | null;
  /** Update local inspector only — does not call the agent. */
  selectLocal: (selection: CanvasSelection) => void;
  /** Send the current selection to the agent for a deeper follow-up. */
  deepenSelection: () => Promise<void>;
  runCanvasAction: (text: string) => Promise<void>;
  clearSelected: () => void;
};

/**
 * Write-only API for canvas widgets (charts, lists, maps).
 * Intentionally excludes `selected` / `busy` so ECharts instances do not
 * re-render — and call setOption — on every inspector click or run tick.
 */
type CanvasWriteValue = {
  selectLocal: (selection: CanvasSelection) => void;
};

const CanvasActionContext = createContext<CanvasActionValue | null>(null);
const CanvasWriteContext = createContext<CanvasWriteValue | null>(null);
const CanvasBrushContext = createContext<CanvasBrush | null>(null);

/** Per-node chrome (type + title) for optional `contexto=` on selections. */
type CanvasNodeMeta = { type: string; title?: string };
const CanvasNodeContext = createContext<CanvasNodeMeta | null>(null);

export function useCanvasNode(): CanvasNodeMeta | null {
  return useContext(CanvasNodeContext);
}

export function CanvasNodeProvider({
  type,
  title,
  children,
}: {
  type: string;
  title?: string;
  children: ReactNode;
}) {
  const value = useMemo(() => ({ type, title }), [type, title]);
  return (
    <CanvasNodeContext.Provider value={value}>
      {children}
    </CanvasNodeContext.Provider>
  );
}

export function CanvasActionProvider({ children }: { children: ReactNode }) {
  const { agent } = useAgent({
    agentId: "argentina_insights",
    updates: [UseAgentUpdate.OnRunStatusChanged],
  });
  const { copilotkit } = useCopilotKit();
  const { showChat } = useChatShell();
  const [pending, setPending] = useState<string | null>(null);
  const [selected, setSelected] = useState<CanvasSelection | null>(null);
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null);
  const lastPointerRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const track = (event: PointerEvent) => {
      lastPointerRef.current = { x: event.clientX, y: event.clientY };
    };
    window.addEventListener("pointerdown", track, true);
    return () => window.removeEventListener("pointerdown", track, true);
  }, []);

  const busy = Boolean(agent.isRunning) || pending !== null;
  const busyRef = useRef(busy);
  busyRef.current = busy;
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const brush = useMemo<CanvasBrush | null>(() => {
    if (!selected?.valor.trim()) return null;
    return { tipo: selected.tipo, valor: selected.valor.trim() };
  }, [selected]);

  const runCanvasAction = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busyRef.current) return;
      // Replies live in chat — reopen desktop column / expand mobile dock.
      showChat();
      setPending(trimmed);
      try {
        agent.addMessage({
          id: crypto.randomUUID(),
          role: "user",
          content: trimmed,
        });
        await copilotkit.runAgent({ agent });
      } catch (error) {
        console.error("CanvasAction: runAgent failed", error);
      } finally {
        setPending(null);
      }
    },
    [agent, copilotkit, showChat],
  );

  const selectLocal = useCallback((selection: CanvasSelection) => {
    if (!selection.valor.trim()) return;
    const { x, y } = lastPointerRef.current;
    setAnchor({
      x: x || Math.round(window.innerWidth * 0.55),
      y: y || Math.round(window.innerHeight * 0.45),
    });
    setSelected(selection);
  }, []);

  const deepenSelection = useCallback(async () => {
    const current = selectedRef.current;
    if (!current || busyRef.current) return;
    await runCanvasAction(formatCanvasSelection(current));
  }, [runCanvasAction]);

  const clearSelected = useCallback(() => {
    setSelected(null);
    setAnchor(null);
  }, []);

  // Stable across selection/busy — charts subscribe only here.
  const writeValue = useMemo<CanvasWriteValue>(
    () => ({ selectLocal }),
    [selectLocal],
  );

  const value = useMemo<CanvasActionValue>(
    () => ({
      busy,
      selected,
      anchor,
      brush,
      selectedText: selected ? formatCanvasSelection(selected) : null,
      selectLocal,
      deepenSelection,
      runCanvasAction,
      clearSelected,
    }),
    [
      busy,
      selected,
      anchor,
      brush,
      selectLocal,
      deepenSelection,
      runCanvasAction,
      clearSelected,
    ],
  );

  return (
    <CanvasWriteContext.Provider value={writeValue}>
      <CanvasBrushContext.Provider value={brush}>
        <CanvasActionContext.Provider value={value}>
          {children}
        </CanvasActionContext.Provider>
      </CanvasBrushContext.Provider>
    </CanvasWriteContext.Provider>
  );
}

export function useCanvasAction(): CanvasActionValue {
  const ctx = useContext(CanvasActionContext);
  if (!ctx) {
    throw new Error("useCanvasAction must be used within CanvasActionProvider");
  }
  return ctx;
}

/** Safe hook for widgets that may render outside the provider (tests). */
export function useCanvasActionOptional(): CanvasActionValue | null {
  return useContext(CanvasActionContext);
}

/**
 * Write-only canvas API. Prefer this in ECharts widgets so selection /
 * run-status updates do not rebuild chart options.
 */
export function useCanvasWriteOptional(): CanvasWriteValue | null {
  return useContext(CanvasWriteContext);
}

/** Brush for highlight-only consumers (List, Acta, Timeline). */
export function useCanvasBrush(): CanvasBrush | null {
  return useContext(CanvasBrushContext);
}

/** Caption under a selectable widget — re-renders cheaply on selection only. */
export function CanvasSelectionCaption({
  widget,
  label = "Selección",
}: {
  widget: string;
  label?: string;
}) {
  const canvas = useCanvasActionOptional();
  const selected =
    canvas?.selected?.widget === widget ? canvas.selected.valor : null;
  if (!selected) return null;
  return (
    <p className="mt-2 text-xs text-muted-foreground">
      {label}:{" "}
      <span className="font-medium tabular-nums text-foreground">
        {selected}
      </span>
    </p>
  );
}
