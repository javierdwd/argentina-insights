"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import {
  useAgent,
  useCopilotKit,
  CopilotChatConfigurationProvider,
  UseAgentUpdate,
} from "@copilotkit/react-core/v2";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { DynamicRenderer } from "@/components/registry/DynamicRenderer";
import { AGENT_RUNTIME_ID, AGENT_SESSION_ID } from "@/lib/agent";
import { trackQuerySubmitted } from "@/lib/analytics";
import {
  followUpsFor,
  getDestination,
  queryForDestination,
} from "@/lib/destinations";
import {
  clearChatIntent,
  takeChatIntent,
  type ChatIntent,
} from "@/lib/chat-intent";
import type { UINode } from "@/lib/uitree";
import {
  clearWorkspace,
  EMPTY_WORKSPACE,
  getWorkspace,
  saveLastCanvas,
  saveWorkspaceSession,
  type Workspace,
} from "@/lib/workspace";
import { CanvasPending } from "./CanvasPending";
import { HomeStage } from "./HomeStage";
import { DestinationFollowUps } from "./DestinationFollowUps";
import { AssistantWithActions } from "./AssistantWithActions";
import {
  ChatRunErrors,
  ChatToolActivity,
  ReasoningContent,
  ReasoningHeader,
  ThinkingCursor,
} from "./ChatActivity";
import { CanvasActionProvider } from "./useCanvasAction";
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
  startedQuery,
  showInitialProgress,
}: {
  onHasCanvas?: (has: boolean) => void;
  onHasStarted?: (has: boolean) => void;
  startedQuery?: string | null;
  showInitialProgress?: boolean;
}) {
  "use no memo";
  const { agent } = useAgent({
    agentId: AGENT_SESSION_ID,
    // OnRunStatusChanged: re-read state when a turn finishes — catches
    // ui_tree updates that landed without a separate OnStateChanged tick.
    updates: [
      UseAgentUpdate.OnStateChanged,
      UseAgentUpdate.OnMessagesChanged,
      UseAgentUpdate.OnRunStatusChanged,
    ],
  });
  const workspace = useWorkspace();
  const reduceMotion = useReducedMotion();
  const persistTimerRef = useRef<number | null>(null);

  const agentTree = isUiTree(
    (agent.state as Record<string, unknown> | undefined)?.ui_tree,
  )
    ? ((agent.state as Record<string, unknown>).ui_tree as UINode)
    : null;

  const displayTree = agentTree ?? workspace.lastCanvas?.uiTree ?? null;
  const userQuery = lastUserQuery(agent.messages);
  const activeQuery = userQuery ?? startedQuery ?? null;
  const pendingQuery = showInitialProgress ? startedQuery : null;
  const visibleTree = pendingQuery ? null : displayTree;
  const query =
    pendingQuery ??
    activeQuery ??
    workspace.lastCanvas?.query ??
    queryForDestination(agentTree ?? displayTree);
  const followUps = followUpsFor(visibleTree);
  const stageKey = visibleTree
    ? "canvas"
    : pendingQuery || activeQuery
      ? "pending"
      : "empty";

  useEffect(() => {
    onHasCanvas?.(Boolean(visibleTree));
  }, [onHasCanvas, visibleTree]);

  useEffect(() => {
    onHasStarted?.(
      Boolean(visibleTree || agent.isRunning || activeQuery),
    );
  }, [activeQuery, agent.isRunning, onHasStarted, visibleTree]);

  useEffect(() => {
    if (!agentTree || pendingQuery) return;
    const timer = window.setTimeout(() => {
      if (persistTimerRef.current !== timer) return;
      persistTimerRef.current = null;
      saveLastCanvas(agentTree, query);
    }, 400);
    persistTimerRef.current = timer;
    return () => {
      window.clearTimeout(timer);
      if (persistTimerRef.current === timer) persistTimerRef.current = null;
    };
  }, [agentTree, pendingQuery, query]);

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      {/* Horizontal inset so widget rings/shadows are not clipped by overflow-y. */}
      <div
        className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-1 pt-6 pb-6 md:pt-8 md:pb-8"
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
                : { opacity: 0, y: -14, scale: 0.992 }
            }
            transition={{
              duration: reduceMotion ? 0 : 0.32,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            {visibleTree ? (
              <>
                <MemoCanvasTree tree={visibleTree} />
                {followUps.length ? (
                  <DestinationFollowUps prompts={followUps} />
                ) : null}
              </>
            ) : pendingQuery || activeQuery ? (
              <CanvasPending
                query={pendingQuery ?? activeQuery ?? undefined}
                running={
                  Boolean(showInitialProgress) || Boolean(agent.isRunning)
                }
              />
            ) : (
              <div className="mx-auto flex min-h-[18rem] max-w-lg flex-col items-center justify-center px-6 text-center">
                <p className="font-display text-xl font-semibold text-foreground">
                  Empezá una conversación
                </p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  Escribí en el chat para construir una vista con datos.
                </p>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      {visibleTree ? <CanvasInspector /> : null}
    </div>
  );
}

const MemoCanvasTree = memo(function MemoCanvasTree({
  tree,
}: {
  tree: UINode;
}) {
  return <DynamicRenderer node={tree} />;
});

const CopilotChatPanel = memo(function CopilotChatPanel({
  threadId,
}: {
  threadId: string;
}) {
  "use no memo";
  return (
    <CopilotChat
      agentId={AGENT_SESSION_ID}
      threadId={threadId}
      className="h-full"
      messageView={CHAT_MESSAGE_VIEW}
      labels={CHAT_LABELS}
    />
  );
});

function ChatPanel({
  threadId,
  onMounted,
}: {
  threadId: string;
  onMounted: () => void;
}) {
  "use no memo";
  useEffect(() => {
    onMounted();
  }, [onMounted]);

  return (
    <div className="relative h-full min-h-0">
      <ChatToolActivity />
      <ChatRunErrors />
      <CopilotChatPanel threadId={threadId} />
    </div>
  );
}

function LoadingStage() {
  return (
    <main
      className="flex min-h-[100dvh] flex-1 items-center justify-center bg-background"
      aria-busy="true"
      aria-label="Restaurando conversación"
    >
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-accent" />
    </main>
  );
}

function initialAgentState(workspace: Workspace): Record<string, unknown> {
  const state = { ...workspace.agentState };
  const tree = workspace.lastCanvas?.uiTree;
  if (tree && !isUiTree(state.ui_tree)) {
    state.ui_tree = structuredClone(tree);
    state.ui_tree_unbound = structuredClone(tree);
  }
  return state;
}

function AgentSession({
  workspace,
  threadId,
  onReset,
}: {
  workspace: Workspace;
  threadId: string;
  onReset: () => void;
}) {
  "use no memo";
  const { agent, isReady } = useAgent({
    agentId: AGENT_SESSION_ID,
    runtimeAgentId: AGENT_RUNTIME_ID,
    threadId,
    updates: [
      UseAgentUpdate.OnStateChanged,
      UseAgentUpdate.OnMessagesChanged,
      UseAgentUpdate.OnRunStatusChanged,
    ],
  });
  const { copilotkit } = useCopilotKit();
  const hydratedRef = useRef(false);
  const intentRef = useRef<ChatIntent | null>(null);
  const pendingRunRef = useRef<string | null>(null);
  const pendingMessageRef = useRef<{
    id: string;
    role: "user";
    content: string;
  } | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [chatReady, setChatReady] = useState(false);
  const [chatMounted, setChatMounted] = useState(false);
  const [hasCanvas, setHasCanvas] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [startedQuery, setStartedQuery] = useState<string | null>(null);
  const [showInitialProgress, setShowInitialProgress] = useState(false);
  const [trackedQueries] = useState(() => {
    const ids = new Set<string>();
    let count = 0;
    for (const message of workspace.messages) {
      if (!message || typeof message !== "object") continue;
      const record = message as Record<string, unknown>;
      if (record.role !== "user") continue;
      count += 1;
      if (typeof record.id === "string") ids.add(record.id);
    }
    return { ids, count };
  });

  useEffect(() => {
    if (!isReady || hydratedRef.current) return;
    hydratedRef.current = true;
    const intent = takeChatIntent();
    intentRef.current = intent;
    const messages = [...workspace.messages];
    if (intent?.type === "query") {
      const message = {
        id: crypto.randomUUID(),
        role: "user" as const,
        content: intent.query,
      };
      pendingRunRef.current = message.id;
      pendingMessageRef.current = message;
      messages.push(message);
      queueMicrotask(() => {
        setStartedQuery(intent.query);
        setShowInitialProgress(true);
      });
    }
    agent.setMessages(
      messages as Parameters<typeof agent.setMessages>[0],
    );
    agent.setState(
      initialAgentState(workspace) as Parameters<typeof agent.setState>[0],
    );
    queueMicrotask(() => {
      setHydrated(true);
      if (intent?.type !== "query") setChatReady(true);
    });
  }, [agent, isReady, workspace]);

  useEffect(() => {
    if (!hydrated) return;
    const timer = window.setTimeout(() => {
      saveWorkspaceSession({
        threadId,
        messages: agent.messages as unknown[],
        agentState:
          agent.state && typeof agent.state === "object"
            ? (agent.state as Record<string, unknown>)
            : {},
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [agent.messages, agent.state, hydrated, threadId]);

  useEffect(() => {
    if (!hydrated) return;
    for (const message of agent.messages) {
      if (!message || typeof message !== "object") continue;
      const record = message as unknown as Record<string, unknown>;
      if (
        record.role !== "user" ||
        typeof record.id !== "string" ||
        typeof record.content !== "string" ||
        trackedQueries.ids.has(record.id)
      ) {
        continue;
      }
      trackedQueries.ids.add(record.id);
      trackQuerySubmitted(
        record.content,
        trackedQueries.count === 0 ? "initial" : "follow_up",
      );
      trackedQueries.count += 1;
    }
  }, [agent.messages, hydrated, trackedQueries]);

  useEffect(() => {
    if (!hydrated || !chatMounted) return;
    const intent = intentRef.current;
    if (!intent || intent.type === "query") return;
    intentRef.current = null;

    const start = async () => {
      try {
        const destination = getDestination(intent.destinationId);
        const tree = await destination.build();
        const current =
          agent.state && typeof agent.state === "object"
            ? (agent.state as Record<string, unknown>)
            : {};
        agent.setState({
          ...current,
          ui_tree: tree,
          ui_tree_unbound: tree,
        });
        saveLastCanvas(tree, destination.title);
      } catch {
        agent.addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "No pudimos abrir la consulta. Volvé al inicio e intentá nuevamente.",
        });
      }
    };
    void start();
  }, [agent, chatMounted, hydrated]);

  useEffect(() => {
    const messageId = pendingRunRef.current;
    const pendingMessage = pendingMessageRef.current;
    if (!hydrated || !messageId || !pendingMessage) return;
    pendingRunRef.current = null;

    const runPendingQuery = async () => {
      try {
        await agent.connectAgent();
        agent.setState(
          initialAgentState(workspace) as Parameters<typeof agent.setState>[0],
        );
        agent.setMessages(
          [...workspace.messages, pendingMessage] as Parameters<
            typeof agent.setMessages
          >[0],
        );
        await copilotkit.runAgent({ agent });
      } finally {
        pendingMessageRef.current = null;
        setShowInitialProgress(false);
        setChatReady(true);
      }
    };
    void runPendingQuery();
  }, [agent, copilotkit, hydrated, workspace]);

  const onHasCanvas = useCallback((has: boolean) => {
    setHasCanvas(has);
  }, []);
  const onHasStarted = useCallback((has: boolean) => {
    setHasStarted(has);
  }, []);
  const onChatMounted = useCallback(() => {
    setChatMounted(true);
  }, []);
  const onClear = useCallback(() => {
    if (agent.isRunning) agent.abortRun();
    onReset();
  }, [agent, onReset]);

  if (!hydrated) return <LoadingStage />;

  return (
    <HomeStage
      hasCanvas={hasCanvas}
      hasStarted={hasStarted}
      onClear={onClear}
      chat={
        chatReady ? (
          <ChatPanel threadId={threadId} onMounted={onChatMounted} />
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-sm text-muted-foreground">
            Preparando la conversación…
          </div>
        )
      }
      stage={
        <CanvasActionProvider>
          <AgentCanvas
            onHasCanvas={onHasCanvas}
            onHasStarted={onHasStarted}
            startedQuery={startedQuery}
            showInitialProgress={showInitialProgress}
          />
        </CanvasActionProvider>
      }
    />
  );
}

/**
 * Restores one browser-local conversation before mounting CopilotChat. A reset
 * rotates the thread and remounts the complete agent subtree.
 */
export function AgentStage() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);

  useEffect(() => {
    const saved = getWorkspace();
    queueMicrotask(() => {
      setWorkspace({
        ...saved,
        threadId: saved.threadId ?? crypto.randomUUID(),
      });
    });
  }, []);

  const onReset = useCallback(() => {
    clearChatIntent();
    clearWorkspace();
    setWorkspace({
      ...EMPTY_WORKSPACE,
      threadId: crypto.randomUUID(),
      messages: [],
      agentState: {},
      lastCanvas: null,
    });
  }, []);

  if (!workspace?.threadId) return <LoadingStage />;

  return (
    <CopilotChatConfigurationProvider
      key={workspace.threadId}
      agentId={AGENT_SESSION_ID}
      threadId={workspace.threadId}
    >
      <AgentSession
        workspace={workspace}
        threadId={workspace.threadId}
        onReset={onReset}
      />
    </CopilotChatConfigurationProvider>
  );
}
