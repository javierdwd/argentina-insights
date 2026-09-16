"use client";

import { useCallback, useState } from "react";
import {
  CopilotChatAssistantMessage,
  type CopilotChatAssistantMessageProps,
  useAgent,
  useCopilotKit,
  UseAgentUpdate,
} from "@copilotkit/react-core/v2";
import { AGENT_SESSION_ID } from "@/lib/agent";
import {
  embedOffersInProse,
  hasInlineButtons,
  parseChatActions,
  parseInlineButtons,
  stripInlineButtons,
} from "./parse-chat-actions";

const ASK_BTN = [
  "mx-0.5 my-0.5 inline max-w-full rounded-md border px-2 py-0.5",
  "align-baseline text-[0.9rem] leading-snug",
  "transition-[color,background-color,border-color] duration-150",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
  "disabled:cursor-not-allowed disabled:opacity-45",
].join(" ");

const ASK_BTN_IDLE = [
  "!border-accent-soft !bg-accent-soft !text-foreground",
  "hover:!border-accent hover:!bg-accent hover:!text-accent-foreground",
].join(" ");

const ASK_BTN_ACTIVE =
  "!border-accent !bg-accent !text-accent-foreground";

function ProseWithButtons({
  prose,
  busy,
  pending,
  onPick,
}: {
  prose: string;
  busy: boolean;
  pending: string | null;
  onPick: (text: string) => void;
}) {
  const paragraphs = prose.split(/\n{2,}/).filter((p) => p.trim());
  return (
    <div className="flex flex-col gap-3 text-[0.95rem] leading-relaxed">
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="whitespace-pre-wrap">
          {parseInlineButtons(paragraph).map((segment, segIndex) => {
            if (segment.type === "text") {
              return <span key={segIndex}>{segment.text}</span>;
            }
            const active = pending === segment.text;
            return (
              <button
                key={segIndex}
                type="button"
                disabled={busy}
                onClick={() => onPick(segment.text)}
                className={[
                  ASK_BTN,
                  active ? ASK_BTN_ACTIVE : ASK_BTN_IDLE,
                ].join(" ")}
              >
                {segment.text}
              </button>
            );
          })}
        </p>
      ))}
    </div>
  );
}

/**
 * Assistant bubble: inline ``[boton]…[/boton]`` plus optional ``[[actions]]``.
 */
function AssistantWithActionsImpl(props: CopilotChatAssistantMessageProps) {
  const raw =
    typeof props.message.content === "string" ? props.message.content : "";
  const { prose: rawProse, actions } = parseChatActions(raw);
  const prose = embedOffersInProse(rawProse, actions);
  const copyText = stripInlineButtons(prose);
  const inline = hasInlineButtons(prose);
  const { agent } = useAgent({
    agentId: AGENT_SESSION_ID,
    updates: [UseAgentUpdate.OnRunStatusChanged],
  });
  const { copilotkit } = useCopilotKit();
  const [pending, setPending] = useState<string | null>(null);

  const busy = Boolean(agent.isRunning) || pending !== null;

  const onPick = useCallback(
    async (text: string) => {
      if (busy) return;
      setPending(text);
      try {
        agent.addMessage({
          id: crypto.randomUUID(),
          role: "user",
          content: text,
        });
        await copilotkit.runAgent({ agent });
      } catch (error) {
        console.error("AssistantWithActions: runAgent failed", error);
      } finally {
        setPending(null);
      }
    },
    [agent, busy, copilotkit],
  );

  const message = {
    ...props.message,
    content: copyText || " ",
  };

  return (
    <div className="flex flex-col gap-3">
      <CopilotChatAssistantMessage {...props} message={message}>
        {(slots) => (
          <div
            data-copilotkit
            data-testid="copilot-assistant-message"
            className="copilotKitMessage copilotKitAssistantMessage"
          >
            <div className="cpk:prose cpk:max-w-full cpk:break-words cpk:dark:prose-invert">
              {inline ? (
                <ProseWithButtons
                  prose={prose}
                  busy={busy}
                  pending={pending}
                  onPick={(text) => void onPick(text)}
                />
              ) : (
                slots.markdownRenderer
              )}
            </div>
            {slots.toolCallsView}
            {slots.toolbarVisible ? slots.toolbar : null}
          </div>
        )}
      </CopilotChatAssistantMessage>
    </div>
  );
}

/** Slot-compatible wrapper — CopilotKit expects the same static members. */
export const AssistantWithActions = Object.assign(AssistantWithActionsImpl, {
  MarkdownRenderer: CopilotChatAssistantMessage.MarkdownRenderer,
  Toolbar: CopilotChatAssistantMessage.Toolbar,
  ToolbarButton: CopilotChatAssistantMessage.ToolbarButton,
  CopyButton: CopilotChatAssistantMessage.CopyButton,
  InspectorButton: CopilotChatAssistantMessage.InspectorButton,
  ThumbsUpButton: CopilotChatAssistantMessage.ThumbsUpButton,
  ThumbsDownButton: CopilotChatAssistantMessage.ThumbsDownButton,
  ReadAloudButton: CopilotChatAssistantMessage.ReadAloudButton,
  RegenerateButton: CopilotChatAssistantMessage.RegenerateButton,
}) as typeof CopilotChatAssistantMessage;
