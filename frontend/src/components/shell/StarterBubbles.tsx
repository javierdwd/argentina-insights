"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import type { DestinationId } from "@/lib/destinations";
import { saveChatIntent } from "@/lib/chat-intent";
import { DestinationStrip } from "./DestinationStrip";
import { LiveCanvasPreview } from "./LiveCanvasPreview";
import { PromptComposer } from "./PromptComposer";
import { FEATURED_STARTERS } from "./starter-prompts";

/** Editorial entry state: question first, live proof second, destinations below. */
export function StarterBubbles() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [destinationBusy, setDestinationBusy] =
    useState<DestinationId | null>(null);
  const busy = pending || destinationBusy !== null;

  const submitQuery = useCallback(
    async (text: string) => {
      if (busy) return;
      setPending(true);
      saveChatIntent({ type: "query", query: text });
      router.push("/chat");
    },
    [busy, router],
  );

  const openDestination = useCallback(
    (id: DestinationId) => {
      if (busy) return;
      setDestinationBusy(id);
      saveChatIntent({ type: "destination", destinationId: id });
      router.push("/chat");
    },
    [busy, router],
  );

  return (
    <div className="home-onboarding mx-auto w-full max-w-[86rem] pb-12">
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,0.92fr)_minmax(28rem,1.08fr)] lg:gap-16 xl:gap-20">
        <div className="lg:pt-12">
          <PromptComposer
            busy={busy}
            featured={FEATURED_STARTERS}
            onSubmit={submitQuery}
          />
        </div>
        <div>
          <LiveCanvasPreview
            busy={busy}
            onExplore={() => openDestination("economia")}
          />
        </div>
      </div>

      <div>
        <DestinationStrip
          busy={busy}
          activeId={destinationBusy}
          error={null}
          onOpen={openDestination}
        />
      </div>
    </div>
  );
}
