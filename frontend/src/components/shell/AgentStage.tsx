"use client";

import { memo, useCallback, useEffect, useId, useRef, useState } from "react";
import {
  useAgent,
  CopilotChatConfigurationProvider,
  UseAgentUpdate,
} from "@copilotkit/react-core/v2";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { DynamicRenderer } from "@/components/registry/DynamicRenderer";
import {
  followUpsFor,
  queryForDestination,
} from "@/lib/destinations";
import type { UINode } from "@/lib/uitree";
import {
  clearLastCanvas,
  getWorkspace,
  saveLastCanvas,
} from "@/lib/workspace";
import { CanvasPending } from "./CanvasPending";
import { HomeStage } from "./HomeStage";
import { StarterBubbles } from "./StarterBubbles";
import { DestinationFollowUps } from "./DestinationFollowUps";
import { AssistantWithActions } from "./AssistantWithActions";
import {
  ChatRunErrors,
  ChatToolActivity,
  ReasoningContent,
  ReasoningHeader,
  ThinkingCursor,
} from "./ChatActivity";
import { CanvasActionProvider, useCanvasAction } from "./useCanvasAction";
import { CanvasInspector } from "./CanvasInspector";
import { lastUserQuery, useWorkspace } from "./useWorkspace";

const CHAT_LABELS = {
  chatInputPlaceholder: "Cotización, fútbol, cine, senadores…",
  welcomeMessageText:
    "¿Economía, política, fútbol, cine argentino, un día histórico o un cruce?",
  chatDisclaimerText:
    "La IA puede cometer errores. Verificá la información importante.",
};

const CHAT_MESSAGE_VIEW = {
  assistantMessage: AssistantWithActions,
  reasoningMessage: {
    header: ReasoningHeader,
    contentView: ReasoningContent,
  },
  cursor: ThinkingCursor,
};

function isUiTree(value: unknown): value is UINode {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as UINode).type === "string"
  );
}

/**
 * Left canvas only — subscribed to agent state.
 *
 * Must stay a sibling of CopilotChat, not its parent: OnStateChanged
 * re-renders would otherwise remount/update the chat during React's render
 * phase and trip "flushSync was called from inside a lifecycle method",
 * which can stall canvas updates.
 */
function AgentCanvas({
  onHasCanvas,
  onHasStarted,
  clearSignal,
}: {
  onHasCanvas?: (has: boolean) => void;
  onHasStarted?: (has: boolean) => void;
  clearSignal: number;
}) {
  "use no memo";
  const { agent, isReady } = useAgent({
    agentId: "argentina_insights",
    // OnRunStatusChanged: re-read state when a turn finishes — catches
    // ui_tree updates that landed without a separate OnStateChanged tick.
    updates: [
      UseAgentUpdate.OnStateChanged,
      UseAgentUpdate.OnMessagesChanged,
      UseAgentUpdate.OnRunStatusChanged,
    ],
  });
  const canvas = useCanvasAction();
  const workspace = useWorkspace();
  const reduceMotion = useReducedMotion();
  const hydratedRef = useRef(false);
  const handledClearRef = useRef(clearSignal);
  const [startedQuery, setStartedQuery] = useState<string | null>(null);
  const [clearedQuery, setClearedQuery] = useState<string | null>(null);
  // CopilotKit can briefly publish the previous thread state after
  // startNewThread. Keep a local tombstone so that stale tree cannot win the
  // agentTree/workspace fallback and paint again after the user clears.
  const [canvasCleared, setCanvasCleared] = useState(false);

  const agentTree = isUiTree(
    (agent.state as Record<string, unknown> | undefined)?.ui_tree,
  )
    ? ((agent.state as Record<string, unknown>).ui_tree as UINode)
    : null;

  const displayTree = canvasCleared
    ? null
    : agentTree ?? workspace.lastCanvas?.uiTree ?? null;
  const userQuery = lastUserQuery(agent.messages);
  const activeQuery =
    userQuery && userQuery !== clearedQuery ? userQuery : startedQuery;
  const query =
    activeQuery ??
    workspace.lastCanvas?.query ??
    queryForDestination(agentTree ?? displayTree);
  const followUps = followUpsFor(displayTree);
  const stageKey = displayTree
    ? "canvas"
    : activeQuery
      ? "pending"
      : "onboarding";

  useEffect(() => {
    onHasCanvas?.(Boolean(displayTree));
  }, [displayTree, onHasCanvas]);

  useEffect(() => {
    onHasStarted?.(
      Boolean(displayTree || agent.isRunning || activeQuery),
    );
  }, [activeQuery, agent.isRunning, displayTree, onHasStarted]);

  useEffect(() => {
    if (handledClearRef.current === clearSignal) return;
    handledClearRef.current = clearSignal;
    if (agent.isRunning) agent.abortRun();
    agent.setMessages([]);
    // A new thread must not inherit any client state that runAgent could send
    // as its initial snapshot. Clear the complete graph state, not only UI.
    agent.setState({
      query_type: "data",
      ui_tree: null,
      ui_tree_unbound: null,
      datasets: {},
      has_tool_calls: false,
      skip_compose: false,
      respond_note: "",
      statistical_report: null,
    });
    setCanvasCleared(true);
    clearLastCanvas();
    canvas.clearSelected();
    setClearedQuery(userQuery ?? startedQuery);
    setStartedQuery(null);
    onHasCanvas?.(false);
    onHasStarted?.(false);
  }, [
    agent,
    canvas,
    clearSignal,
    onHasCanvas,
    onHasStarted,
    startedQuery,
    userQuery,
  ]);

  useEffect(() => {
    if (!isReady || hydratedRef.current || canvasCleared) return;
    hydratedRef.current = true;
    if (agentTree) return;
    const saved = getWorkspace().lastCanvas?.uiTree;
    if (!saved) return;
    const current =
      agent.state && typeof agent.state === "object"
        ? (agent.state as Record<string, unknown>)
        : {};
    const tree = structuredClone(saved);
    const next = { ...current, ui_tree: tree, ui_tree_unbound: tree };
    // CopilotChat flushSyncs on state notifications. Push after this
    // commit so hydrate does not nest inside the chat's lifecycle.
    queueMicrotask(() => {
      agent.setState(next);
    });
  }, [agent, agentTree, canvasCleared, isReady]);

  useEffect(() => {
    if (!agentTree || canvasCleared) return;
    const timer = window.setTimeout(() => {
      saveLastCanvas(agentTree, query);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [agentTree, canvasCleared, query]);

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      {/* Horizontal inset so widget rings/shadows are not clipped by overflow-y. */}
      <div
        className={[
          "min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-1 pt-6 pb-6 md:pt-8 md:pb-8",
          stageKey === "onboarding" ? "md:overflow-visible" : "",
        ].join(" ")}
      >
        <AnimatePresence initial={false} mode="wait">
          <motion.div
            key={stageKey}
            initial={
              reduceMotion ? false : { opacity: 0, y: 20, scale: 0.992 }
            }
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={
              reduceMotion
                ? { opacity: 1 }
                : stageKey === "onboarding"
                  ? { opacity: 0 }
                : { opacity: 0, y: -14, scale: 0.992 }
            }
            transition={{
              // Remove the wide home composition before the shell opens its
              // chat column. Keeping it mounted during the grid resize makes
              // the preview slide over the incoming stage and chat.
              duration:
                reduceMotion || stageKey === "onboarding" ? 0 : 0.52,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            {displayTree ? (
              <>
                <MemoCanvasTree tree={displayTree} />
                {followUps.length ? (
                  <DestinationFollowUps prompts={followUps} />
                ) : null}
              </>
            ) : activeQuery ? (
              <CanvasPending
                query={activeQuery}
                running={Boolean(agent.isRunning)}
              />
            ) : (
              <StarterBubbles
                onStart={(nextQuery) => {
                  setCanvasCleared(false);
                  setClearedQuery(null);
                  setStartedQuery(nextQuery);
                }}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      {displayTree ? <CanvasInspector /> : null}
    </div>
  );
}

const MemoCanvasTree = memo(function MemoCanvasTree({
  tree,
}: {
  tree: UINode;
}) {
  return (
    <div className="canvas-transition-surface">
      <DynamicRenderer node={tree} />
    </div>
  );
});

const CopilotChatPanel = memo(function CopilotChatPanel({
  threadId,
}: {
  threadId: string;
}) {
  "use no memo";
  return (
    <CopilotChat
      agentId="argentina_insights"
      threadId={threadId}
      className="h-full"
      messageView={CHAT_MESSAGE_VIEW}
      labels={CHAT_LABELS}
    />
  );
});

function ChatPanel({ threadId }: { threadId: string }) {
  "use no memo";
  return (
    <div className="relative h-full min-h-0">
      <ChatToolActivity />
      <ChatRunErrors />
      <CopilotChatPanel threadId={threadId} />
    </div>
  );
}

/**
 * Full-page orchestrator — brand + stage (left) · CopilotChat (right / mobile dock).
 *
 * CanvasActionProvider wraps ONLY the stage so run-status re-renders do not
 * remount the chat. Agent turns reopen the desktop column or expand the
 * mobile dock if it was collapsed.
 */
export function AgentStage() {
  "use no memo";
  const threadSeed = useId();
  const [threadId, setThreadId] = useState(
    () => `argentina-insights-${threadSeed.replaceAll(":", "")}`,
  );
  const [hasCanvas, setHasCanvas] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [clearSignal, setClearSignal] = useState(0);
  const onHasCanvas = useCallback((has: boolean) => {
    setHasCanvas(has);
  }, []);
  const onHasStarted = useCallback((has: boolean) => {
    setHasStarted(has);
  }, []);
  const onClear = useCallback(() => {
    setThreadId(crypto.randomUUID());
    setClearSignal((current) => current + 1);
  }, []);
  return (
    <CopilotChatConfigurationProvider
      agentId="argentina_insights"
      threadId={threadId}
    >
      <HomeStage
        hasCanvas={hasCanvas}
        hasStarted={hasStarted}
        onClear={onClear}
        chat={<ChatPanel threadId={threadId} />}
        stage={
          <CanvasActionProvider>
            <AgentCanvas
              onHasCanvas={onHasCanvas}
              onHasStarted={onHasStarted}
              clearSignal={clearSignal}
            />
          </CanvasActionProvider>
        }
      />
    </CopilotChatConfigurationProvider>
  );
}
