"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import {
  useAgent,
  UseAgentUpdate,
  useConfigureSuggestions,
} from "@copilotkit/react-core/v2";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { DynamicRenderer } from "@/components/registry/DynamicRenderer";
import {
  followUpsFor,
  queryForDestination,
} from "@/lib/destinations";
import type { UINode } from "@/lib/uitree";
import { getWorkspace, saveLastCanvas } from "@/lib/workspace";
import { HomeStage } from "./HomeStage";
import { StarterBubbles } from "./StarterBubbles";
import { DestinationFollowUps } from "./DestinationFollowUps";
import { AssistantWithActions } from "./AssistantWithActions";
import {
  ChatToolActivity,
  ReasoningContent,
  ReasoningHeader,
  ThinkingCursor,
} from "./ChatActivity";
import { chatSuggestionPrompts } from "./starter-prompts";
import { CanvasActionProvider } from "./useCanvasAction";
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
  chatInputPlaceholder: "Cotización, inflación, cine, senadores…",
  welcomeMessageText:
    "¿Economía, política, cine argentino, un día histórico, o un cruce?",
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
}: {
  onHasCanvas?: (has: boolean) => void;
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
  const workspace = useWorkspace();
  const hydratedRef = useRef(false);

  const agentTree = isUiTree(
    (agent.state as Record<string, unknown> | undefined)?.ui_tree,
  )
    ? ((agent.state as Record<string, unknown>).ui_tree as UINode)
    : null;

  const displayTree = agentTree ?? workspace.lastCanvas?.uiTree ?? null;
  const query =
    lastUserQuery(agent.messages) ??
    workspace.lastCanvas?.query ??
    queryForDestination(agentTree ?? displayTree);
  const followUps = followUpsFor(displayTree);

  useEffect(() => {
    onHasCanvas?.(Boolean(displayTree));
  }, [displayTree, onHasCanvas]);

  useEffect(() => {
    if (!isReady || hydratedRef.current) return;
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
  }, [agent, agentTree, isReady]);

  useEffect(() => {
    if (!agentTree) return;
    const timer = window.setTimeout(() => {
      saveLastCanvas(agentTree, query);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [agentTree, query]);

  return (
    <div className="relative flex h-full min-h-0 flex-col">
      <WorkspaceDock uiTree={displayTree} query={query} />
      {/* Horizontal inset so widget rings/shadows are not clipped by overflow-y. */}
      <div className="min-h-0 flex-1 overflow-y-auto px-1 pt-6 pb-6 md:pt-8 md:pb-8">
        {displayTree ? (
          <>
            <MemoCanvasTree tree={displayTree} />
            {followUps.length ? (
              <DestinationFollowUps prompts={followUps} />
            ) : null}
          </>
        ) : (
          <StarterBubbles />
        )}
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
  return <DynamicRenderer node={tree} />;
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
      <CopilotChatPanel />
    </div>
  );
}

/**
 * Full-page orchestrator — brand + stage (left) · CopilotChat (right).
 *
 * CanvasActionProvider wraps ONLY the stage so run-status re-renders do not
 * remount the chat. FloatingComposer talks to the agent directly.
 */
export function AgentStage() {
  "use no memo";
  const [hasCanvas, setHasCanvas] = useState(false);
  const onHasCanvas = useCallback((has: boolean) => {
    setHasCanvas(has);
  }, []);

  return (
    <HomeStage
      hasCanvas={hasCanvas}
      chat={<ChatWithStarters />}
      stage={
        <CanvasActionProvider>
          <AgentCanvas onHasCanvas={onHasCanvas} />
        </CanvasActionProvider>
      }
    />
  );
}
