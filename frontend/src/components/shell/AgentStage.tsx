"use client";

import { useAgent, UseAgentUpdate } from "@copilotkit/react-core/v2";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { DynamicRenderer } from "@/components/registry/DynamicRenderer";
import type { UINode } from "@/lib/uitree";
import { HomeStage } from "./HomeStage";

/**
 * Full-page orchestrator — brand + stage (left) · CopilotChat (right).
 *
 * Subscribes to agent state via useAgent.  Whenever compose_ui + bind_data
 * complete, agent.state.ui_tree is updated and DynamicRenderer re-renders
 * the canvas on the left.
 *
 * CopilotChat on the right shows the brief messages produced by compose_ui
 * (and normal conversation turns).  The raw JSON of the UI tree is never
 * present in the chat thread.
 */
export function AgentStage() {
  const { agent } = useAgent({
    agentId: "argentina_insights",
    // Re-render whenever the agent updates any part of its state.
    updates: [UseAgentUpdate.OnStateChanged],
  });

  // agent.state is the full AgentState dict from the LangGraph backend.
  // ui_tree is set by bind_data at the end of each turn.
  const uiTree = (agent.state as Record<string, unknown> | undefined)
    ?.ui_tree as UINode | null | undefined;

  return (
    <HomeStage
      chat={
        <CopilotChat
          agentId="argentina_insights"
          className="h-full"
          labels={{
            chatInputPlaceholder: "Cotización, inflación, senadores…",
            welcomeMessageText: "¿En qué te puedo ayudar hoy?",
            chatDisclaimerText:
              "La IA puede cometer errores. Verificá la información importante.",
          }}
        />
      }
      stage={
        uiTree ? (
          <DynamicRenderer node={uiTree} />
        ) : undefined
      }
    />
  );
}
