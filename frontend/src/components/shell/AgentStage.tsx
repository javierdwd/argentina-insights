"use client";

import { CopilotChat } from "@copilotkit/react-core/v2";
import { HomeStage } from "./HomeStage";

/**
 * Full-page orchestrator — brand + stage (left) · CopilotChat (right).
 *
 * CopilotChat handles the full conversation lifecycle: input field, user
 * messages, streaming assistant replies, running state.  The stage column
 * is reserved for generative UI widgets in a future iteration.
 */
export function AgentStage() {
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
    />
  );
}
