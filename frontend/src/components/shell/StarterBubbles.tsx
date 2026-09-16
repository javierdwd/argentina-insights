"use client";

import { useCallback, useState } from "react";
import { motion } from "motion/react";
import {
  useAgent,
  useCopilotKit,
  UseAgentUpdate,
} from "@copilotkit/react-core/v2";
import { DESTINATIONS, type DestinationId } from "@/lib/destinations";
import { runViewTransition } from "@/lib/view-transition";
import { saveLastCanvas } from "@/lib/workspace";
import { DestinationStrip } from "./DestinationStrip";
import { LiveCanvasPreview } from "./LiveCanvasPreview";
import { PromptComposer } from "./PromptComposer";
import { FEATURED_STARTERS } from "./starter-prompts";

/** Editorial entry state: question first, live proof second, destinations below. */
export function StarterBubbles({
  onStart,
}: {
  onStart?: (query: string) => void;
}) {
  const { agent } = useAgent({
    agentId: "argentina_insights",
    updates: [
      UseAgentUpdate.OnMessagesChanged,
      UseAgentUpdate.OnRunStatusChanged,
    ],
  });
  const { copilotkit } = useCopilotKit();
  const [pending, setPending] = useState(false);
  const [destinationBusy, setDestinationBusy] =
    useState<DestinationId | null>(null);
  const [destinationError, setDestinationError] = useState<string | null>(null);
  const busy = Boolean(agent.isRunning) || pending || destinationBusy !== null;

  const submitQuery = useCallback(
    async (text: string) => {
      if (busy) return;
      setPending(true);
      try {
        await runViewTransition(() => {
          onStart?.(text);
          agent.addMessage({
            id: crypto.randomUUID(),
            role: "user",
            content: text,
          });
        });
        await copilotkit.runAgent({ agent });
      } finally {
        setPending(false);
      }
    },
    [agent, busy, copilotkit, onStart],
  );

  const openDestination = useCallback(
    async (id: DestinationId) => {
      if (busy) return;
      const destination = DESTINATIONS.find((item) => item.id === id);
      if (!destination) return;
      setDestinationError(null);
      setDestinationBusy(id);
      try {
        onStart?.(destination.title);
        const tree = await destination.build();
        const current =
          agent.state && typeof agent.state === "object"
            ? (agent.state as Record<string, unknown>)
            : {};
        const next = {
          ...current,
          ui_tree: tree,
          ui_tree_unbound: tree,
        };
        await runViewTransition(() => {
          queueMicrotask(() => agent.setState(next));
        });
        saveLastCanvas(tree, destination.title);
      } catch {
        setDestinationError(
          `No pudimos abrir ${destination.title}. Probá nuevamente.`,
        );
      } finally {
        setDestinationBusy(null);
      }
    },
    [agent, busy, onStart],
  );

  return (
    <div className="mx-auto w-full max-w-[86rem] pb-12">
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,0.92fr)_minmax(28rem,1.08fr)] lg:gap-16 xl:gap-20">
        <motion.div
          initial={false}
          className="entry-reveal entry-reveal-delay-1 lg:pt-12"
        >
          <PromptComposer
            busy={busy}
            featured={FEATURED_STARTERS}
            onSubmit={submitQuery}
          />
        </motion.div>
        <motion.div
          initial={false}
          className="entry-reveal entry-reveal-delay-2"
        >
          <LiveCanvasPreview
            busy={busy}
            onExplore={() => void openDestination("economia")}
          />
        </motion.div>
      </div>

      <motion.div
        initial={false}
        className="entry-reveal entry-reveal-delay-3"
      >
        <DestinationStrip
          busy={busy}
          activeId={destinationBusy}
          error={destinationError}
          onOpen={(id) => void openDestination(id)}
        />
      </motion.div>
    </div>
  );
}
