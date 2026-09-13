"use client";

import { BookmarkSimple, Broom, X } from "@phosphor-icons/react";
import { useAgent, UseAgentUpdate } from "@copilotkit/react-core/v2";
import type { UINode } from "@/lib/uitree";
import {
  clearLastCanvas,
  compactTitle,
  removeView,
  saveLastCanvas,
  saveView,
  type WorkspaceView,
} from "@/lib/workspace";
import { useCanvasAction } from "./useCanvasAction";
import { useWorkspace } from "./useWorkspace";

function patchUiTree(
  agent: { state: unknown; setState: (state: Record<string, unknown>) => void },
  uiTree: UINode | null,
) {
  const current =
    agent.state && typeof agent.state === "object"
      ? (agent.state as Record<string, unknown>)
      : {};
  // Keep ui_tree and ui_tree_unbound in sync — compose stacks onto unbound,
  // so clearing only the bound tree lets the next turn restore everything.
  const tree = uiTree ? structuredClone(uiTree) : null;
  agent.setState({
    ...current,
    ui_tree: tree,
    ui_tree_unbound: tree,
  });
}

function useWorkspaceAgent() {
  const { agent } = useAgent({
    agentId: "argentina_insights",
    updates: [UseAgentUpdate.OnRunStatusChanged],
  });
  return agent;
}

/**
 * Saved views — horizontal tabs above the canvas (explicit saves only).
 */
export function WorkspaceDock({
  uiTree,
  query,
}: {
  uiTree: UINode | null;
  query?: string;
}) {
  const workspace = useWorkspace();
  const agent = useWorkspaceAgent();
  const canvas = useCanvasAction();

  const hasItems = workspace.views.length > 0;

  if (!uiTree && !hasItems) return null;

  const onSaveView = () => {
    if (!uiTree) return;
    const title = compactTitle(query || uiTree.title || "Vista guardada");
    saveView({ title, uiTree, query });
  };

  const onRestoreView = (view: WorkspaceView) => {
    saveLastCanvas(view.uiTree, view.query);
    patchUiTree(agent, view.uiTree);
  };

  return (
    <div className="sticky top-0 z-10 shrink-0 pb-3 md:static">
      {uiTree ? (
        <div className="flex flex-wrap items-center gap-x-1 gap-y-1">
          <button
            type="button"
            onClick={onSaveView}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-accent transition-colors hover:bg-accent-soft hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
          >
            <BookmarkSimple size={15} weight="regular" />
            Guardar vista
          </button>
          <button
            type="button"
            onClick={() => {
              clearLastCanvas();
              canvas.clearSelected();
              patchUiTree(agent, null);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
          >
            <Broom size={15} weight="regular" />
            Limpiar
          </button>
        </div>
      ) : null}

      {hasItems ? (
        <div
          role="tablist"
          aria-label="Vistas guardadas"
          className={`flex gap-1 overflow-x-auto pb-0.5 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden ${
            uiTree ? "mt-2.5" : ""
          }`}
        >
          {workspace.views.map((view) => {
            const active =
              Boolean(query) &&
              Boolean(view.query) &&
              view.query === query;
            return (
              <div
                key={view.id}
                role="tab"
                aria-selected={active}
                className={[
                  "flex shrink-0 items-stretch rounded-lg",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "bg-accent-soft text-accent hover:bg-accent-soft-hover",
                ].join(" ")}
              >
                <button
                  type="button"
                  onClick={() => onRestoreView(view)}
                  aria-label={`Abrir vista: ${view.title}`}
                  className="max-w-[14rem] truncate px-2.5 py-1.5 text-left text-[0.8rem] leading-snug focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/50"
                >
                  {view.title}
                </button>
                <button
                  type="button"
                  onClick={() => removeView(view.id)}
                  aria-label={`Quitar ${view.title}`}
                  className={[
                    "shrink-0 px-2 text-sm leading-none opacity-55 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/50",
                    active ? "text-accent-foreground" : "",
                  ].join(" ")}
                >
                  <X size={12} weight="regular" />
                </button>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
