"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import {
  useAgent,
  useCopilotChatConfiguration,
  UseAgentUpdate,
  useConfigureSuggestions,
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
  compactTitle,
  getWorkspace,
  saveLastCanvas,
  saveView,
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
import { chatSuggestionPrompts } from "./starter-prompts";
import { CanvasActionProvider, useCanvasAction } from "./useCanvasAction";
import { CanvasInspector } from "./CanvasInspector";
import { lastUserQuery, useWorkspace } from "./useWorkspace";
import { WorkspaceDock } from "./WorkspaceRail";

const CHAT_SUGGESTIONS = {
  suggestions: chatSuggestionPrompts(6).map((prompt) => ({
    title: prompt.text,
    message: prompt.text,
  })),
};

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
  saveSignal,
}: {
  onHasCanvas?: (has: boolean) => void;
  onHasStarted?: (has: boolean) => void;
  clearSignal: number;
  saveSignal: number;
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
  const chatConfiguration = useCopilotChatConfiguration();
  const workspace = useWorkspace();
  const reduceMotion = useReducedMotion();
  const hydratedRef = useRef(false);
  const handledClearRef = useRef(clearSignal);
  const handledSaveRef = useRef(saveSignal);
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
    chatConfiguration?.startNewThread();
    agent.setMessages([]);
    // CopilotKit can merge state updates, so an empty object does not remove
    // the previous canvas. Explicitly clear both the rendered and source tree.
    agent.setState({
      ui_tree: null,
      ui_tree_unbound: null,
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
    chatConfiguration,
    clearSignal,
    onHasCanvas,
    onHasStarted,
    startedQuery,
    userQuery,
  ]);

  useEffect(() => {
    if (handledSaveRef.current === saveSignal) return;
    handledSaveRef.current = saveSignal;
    if (!displayTree) return;
    const title = compactTitle(query || displayTree.title || "Vista guardada");
    saveView({ title, uiTree: displayTree, query });
  }, [displayTree, query, saveSignal]);

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
      <WorkspaceDock query={query} />
      {/* Horizontal inset so widget rings/shadows are not clipped by overflow-y. */}
      <div className="min-h-0 flex-1 overflow-y-auto px-1 pt-6 pb-6 md:pt-8 md:pb-8">
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

/**
 * Welcome pills. Lives beside CopilotChat (not as its parent) so
 * reloadSuggestions cannot flushSync during the chat's first commit.
 */
function ChatSuggestions() {
  "use no memo";
  useConfigureSuggestions(CHAT_SUGGESTIONS, []);
  return null;
}

const CopilotChatPanel = memo(function CopilotChatPanel() {
  "use no memo";
  return (
    <CopilotChat
      agentId="argentina_insights"
      className="h-full"
      messageView={CHAT_MESSAGE_VIEW}
      labels={CHAT_LABELS}
    />
  );
});

function ChatWithStarters() {
  "use no memo";
  return (
    <div className="relative h-full min-h-0">
      <ChatSuggestions />
      <ChatToolActivity />
      <ChatRunErrors />
      <CopilotChatPanel />
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
  const [hasCanvas, setHasCanvas] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [clearSignal, setClearSignal] = useState(0);
  const [saveSignal, setSaveSignal] = useState(0);
  const onHasCanvas = useCallback((has: boolean) => {
    setHasCanvas(has);
  }, []);
  const onHasStarted = useCallback((has: boolean) => {
    setHasStarted(has);
  }, []);
  const onClear = useCallback(() => {
    setClearSignal((current) => current + 1);
  }, []);
  const onSave = useCallback(() => {
    setSaveSignal((current) => current + 1);
  }, []);

  return (
    <HomeStage
      hasCanvas={hasCanvas}
      hasStarted={hasStarted}
      onClear={onClear}
      onSave={onSave}
      chat={<ChatWithStarters />}
      stage={
        <CanvasActionProvider>
          <AgentCanvas
            onHasCanvas={onHasCanvas}
            onHasStarted={onHasStarted}
            clearSignal={clearSignal}
            saveSignal={saveSignal}
          />
        </CanvasActionProvider>
      }
    />
  );
}
