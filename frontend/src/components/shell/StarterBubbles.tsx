"use client";

import { useCallback, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowRight,
  BookOpenText,
  CalendarDots,
  ChartBar,
  ChartDonut,
  ChartLine,
  ChartLineUp,
  CloudSun,
  FilmSlate,
  GitMerge,
  Hash,
  HourglassHigh,
  IdentificationCard,
  MapTrifold,
  Scales,
  Table,
  type Icon,
} from "@phosphor-icons/react";
import {
  useAgent,
  useCopilotKit,
  UseAgentUpdate,
} from "@copilotkit/react-core/v2";
import {
  DESTINATIONS,
  type DestinationId,
} from "@/lib/destinations";
import { saveLastCanvas } from "@/lib/workspace";
import {
  PREVIEW_LABEL,
  STARTER_PROMPTS,
  TOPIC_LABEL,
  TOPIC_ORDER,
  type StarterPreview,
  type StarterPrompt,
  type StarterTopic,
} from "./starter-prompts";

const EASE = [0.32, 0.72, 0, 1] as const;

const TOPIC_ICON: Record<StarterTopic, Icon> = {
  historico: HourglassHigh,
  cruce: GitMerge,
  economia: ChartLineUp,
  politica: Scales,
  cine: FilmSlate,
};

const DEST_ICON: Record<DestinationId, Icon> = {
  economia: ChartLineUp,
  politica: Scales,
  cine: FilmSlate,
};

const PREVIEW_ICON: Record<StarterPreview, Icon> = {
  bars: ChartBar,
  line: ChartLine,
  metrics: Hash,
  people: IdentificationCard,
  map: MapTrifold,
  donut: ChartDonut,
  list: Table,
  timeline: CalendarDots,
  text: BookOpenText,
  weather: CloudSun,
};

function byTopic(topic: StarterTopic): StarterPrompt[] {
  return STARTER_PROMPTS.filter((prompt) => prompt.topic === topic);
}

function TopicIcon({ icon: PhosphorIcon }: { icon: Icon }) {
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent">
      <PhosphorIcon size={15} weight="regular" className="shrink-0" />
    </span>
  );
}

/**
 * Empty-stage starters: destination dashboards (Economía · Política · Cine)
 * plus the topic prompt grid as secondary onboarding.
 */
export function StarterBubbles() {
  const reduce = useReducedMotion();
  const { agent } = useAgent({
    agentId: "argentina_insights",
    updates: [UseAgentUpdate.OnMessagesChanged, UseAgentUpdate.OnRunStatusChanged],
  });
  const { copilotkit } = useCopilotKit();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [destinoBusy, setDestinoBusy] = useState<DestinationId | null>(null);

  const busy =
    Boolean(agent.isRunning) || pendingId !== null || destinoBusy !== null;

  const onOpenDestination = useCallback(
    async (id: DestinationId) => {
      if (busy) return;
      const dest = DESTINATIONS.find((d) => d.id === id);
      if (!dest) return;
      setDestinoBusy(id);
      try {
        const tree = await dest.build();
        const current =
          agent.state && typeof agent.state === "object"
            ? (agent.state as Record<string, unknown>)
            : {};
        const next = {
          ...current,
          ui_tree: tree,
          ui_tree_unbound: tree,
        };
        queueMicrotask(() => {
          agent.setState(next);
        });
        saveLastCanvas(tree, dest.title);
      } catch (error) {
        console.error(`StarterBubbles: ${dest.title} destination failed`, error);
      } finally {
        setDestinoBusy(null);
      }
    },
    [agent, busy],
  );

  const onPick = useCallback(
    async (prompt: StarterPrompt) => {
      if (busy) return;
      setPendingId(prompt.id);
      try {
        agent.addMessage({
          id: crypto.randomUUID(),
          role: "user",
          content: prompt.text,
        });
        await copilotkit.runAgent({ agent });
      } catch (error) {
        console.error("StarterBubbles: runAgent failed", error);
      } finally {
        setPendingId(null);
      }
    },
    [agent, busy, copilotkit],
  );

  return (
    <div className="flex w-full max-w-4xl flex-col gap-5 pb-10">
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: EASE }}
        className="flex flex-col gap-3"
      >
        <div className="flex flex-wrap gap-2">
          {DESTINATIONS.map((dest) => {
            const Icon = DEST_ICON[dest.id];
            const loading = destinoBusy === dest.id;
            return (
              <button
                key={dest.id}
                type="button"
                disabled={busy}
                onClick={() => void onOpenDestination(dest.id)}
                className={[
                  "inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-left",
                  "bg-accent text-accent-foreground shadow-[0_14px_36px_-20px_color-mix(in_oklab,var(--accent)_70%,transparent)]",
                  "transition-[transform,opacity] duration-200 ease-[cubic-bezier(0.32,0.72,0,1)]",
                  "hover:opacity-95 active:scale-[0.99]",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
                  "disabled:cursor-not-allowed disabled:opacity-45",
                ].join(" ")}
              >
                <Icon size={18} weight="regular" className="shrink-0" />
                <span className="font-display text-sm font-semibold tracking-tight">
                  {loading ? `Cargando ${dest.title}…` : dest.title}
                </span>
                <ArrowRight size={14} weight="regular" className="opacity-80" />
              </button>
            );
          })}
        </div>
        <p className="max-w-[42ch] text-xs leading-relaxed text-muted-foreground">
          {DESTINATIONS.map((d) => d.title).join(" · ")} — dashboards listos;
          abajo, preguntas para el chat.
        </p>
      </motion.div>

      <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
        {TOPIC_ORDER.map((topic, sectionIndex) => {
          const items = byTopic(topic);
          const Icon = TOPIC_ICON[topic];
          return (
            <motion.section
              key={topic}
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.4,
                ease: EASE,
                delay: reduce ? 0 : 0.06 * sectionIndex,
              }}
              className="min-h-0"
            >
              <div className="flex h-full flex-col rounded-2xl bg-card p-3 ring-1 ring-border/80">
                <h2 className="flex items-center gap-2 px-1.5 font-display text-sm font-semibold tracking-tight text-foreground">
                  <TopicIcon icon={Icon} />
                  {TOPIC_LABEL[topic]}
                </h2>
                <ul className="mt-2 flex min-h-0 flex-1 flex-col gap-0.5">
                  {items.map((prompt) => {
                    const active = pendingId === prompt.id;
                    const PreviewIcon = PREVIEW_ICON[prompt.preview];
                    return (
                      <li key={prompt.id}>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void onPick(prompt)}
                          className={[
                            "group flex w-full items-start gap-2 rounded-xl px-1.5 py-2 text-left",
                            "transition-[color,background-color,transform] duration-200 ease-[cubic-bezier(0.32,0.72,0,1)]",
                            "hover:bg-accent-soft active:scale-[0.995]",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
                            "disabled:cursor-not-allowed disabled:opacity-45",
                            active
                              ? "bg-accent-soft text-accent"
                              : "text-foreground",
                          ].join(" ")}
                        >
                          <span
                            aria-hidden
                            title={PREVIEW_LABEL[prompt.preview]}
                            className={[
                              "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border",
                              active
                                ? "border-accent/30 bg-card text-accent"
                                : "border-border bg-secondary/70 text-accent group-hover:border-accent/25 group-hover:bg-card",
                            ].join(" ")}
                          >
                            <PreviewIcon size={13} weight="regular" />
                          </span>
                          <span className="min-w-0 flex-1 text-[0.82rem] leading-snug group-hover:text-accent sm:text-[0.88rem]">
                            {prompt.text}
                          </span>
                          <ArrowRight
                            aria-hidden
                            size={14}
                            weight="regular"
                            className="mt-1 shrink-0 text-accent opacity-0 transition-[opacity,transform] duration-200 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-0.5 group-hover:opacity-100 group-focus-visible:opacity-100"
                          />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </motion.section>
          );
        })}
      </div>
    </div>
  );
}
