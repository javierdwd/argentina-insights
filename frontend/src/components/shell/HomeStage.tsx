"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  CaretDown,
  CaretUp,
  ChatCircle,
  ChatCircleSlash,
  CircleNotch,
} from "@phosphor-icons/react";
import { motion, useReducedMotion } from "motion/react";
import {
  useAgent,
  UseAgentUpdate,
} from "@copilotkit/react-core/v2";
import { latestTurnReasoning } from "./ChatActivity";

const EASE = [0.32, 0.72, 0, 1] as const;
const CHAT_PREF_KEY = "argentina-insights.chat-collapsed";
const MD_QUERY = "(min-width: 768px)";
/** Peek bar + safe area — stage keeps this clear so content is never covered. */
const MOBILE_DOCK_PEEK =
  "calc(3.75rem + env(safe-area-inset-bottom, 0px))";

type ChatShellValue = {
  chatHidden: boolean;
  /** Reopen chat: desktop column, or expand the mobile dock. */
  showChat: () => void;
};

const ChatShellContext = createContext<ChatShellValue>({
  chatHidden: false,
  showChat: () => {},
});

/** Desktop chat column visibility — reopen when starting an agent turn. */
export function useChatShell(): ChatShellValue {
  return useContext(ChatShellContext);
}

interface HomeStageProps {
  /** CopilotChat panel rendered in the right column. */
  chat: ReactNode;
  /** Generative UI widgets rendered in the left stage area (optional). */
  stage?: ReactNode;
  /** True when the stage is showing a canvas (not empty starters). */
  hasCanvas?: boolean;
}

/** Compact Argentine flag mark: celeste bands + Sol de Mayo. */
function BrandMark({ compact }: { compact?: boolean }) {
  return (
    <span
      aria-hidden
      className={[
        "relative isolate flex shrink-0 items-center justify-center overflow-hidden bg-sky shadow-[inset_0_1px_0_rgba(255,255,255,0.55),0_10px_24px_-14px_color-mix(in_oklab,var(--sky)_80%,transparent)]",
        compact
          ? "h-8 w-8 rounded-[0.65rem]"
          : "h-11 w-11 rounded-[0.85rem]",
      ].join(" ")}
    >
      <span className="absolute inset-x-0 top-0 h-[34%] bg-[#74acdf] dark:bg-[#4a8ec4]" />
      <span className="absolute inset-x-0 top-[34%] h-[32%] bg-[#f7fafc]" />
      <span className="absolute inset-x-0 bottom-0 h-[34%] bg-[#74acdf] dark:bg-[#4a8ec4]" />
      <span
        className={[
          "relative z-[1] rounded-full bg-[#e8b423] shadow-[0_0_0_3px_rgba(232,180,35,0.28)]",
          compact ? "h-1.5 w-1.5" : "h-2.5 w-2.5",
        ].join(" ")}
      />
    </span>
  );
}

function readChatPref(): boolean | null {
  try {
    const raw = localStorage.getItem(CHAT_PREF_KEY);
    if (raw === "1") return true;
    if (raw === "0") return false;
  } catch {
    /* private mode */
  }
  return null;
}

function writeChatPref(collapsed: boolean): void {
  try {
    localStorage.setItem(CHAT_PREF_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore */
  }
}

function useIsDesktop(): boolean {
  const [isDesktop, setIsDesktop] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(MD_QUERY);
    const sync = () => setIsDesktop(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return isDesktop;
}

/**
 * Floating mobile peek — reasoning while the agent works, otherwise a prompt
 * to expand and type. Keeps CopilotChat mounted (hidden) above it.
 */
function MobileChatPeek({ onExpand }: { onExpand: () => void }) {
  const { agent } = useAgent({
    agentId: "argentina_insights",
    updates: [
      UseAgentUpdate.OnMessagesChanged,
      UseAgentUpdate.OnRunStatusChanged,
    ],
  });
  const running = Boolean(agent.isRunning);
  const reasoning = latestTurnReasoning(agent.messages);
  const line = running
    ? reasoning || "Pensando…"
    : reasoning
      ? reasoning
      : "Escribí una pregunta…";

  return (
    <button
      type="button"
      onClick={onExpand}
      className="flex w-full items-center gap-3 border-t border-border bg-card px-4 pt-3 shadow-[0_-12px_32px_-20px_color-mix(in_oklab,var(--foreground)_35%,transparent)] pb-[max(0.75rem,env(safe-area-inset-bottom,0px))] text-left transition-colors hover:bg-secondary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent/50"
      aria-expanded={false}
      aria-controls="mobile-chat-sheet"
    >
      <span
        className={[
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
          running ? "bg-accent-soft text-accent" : "bg-secondary text-muted-foreground",
        ].join(" ")}
        aria-hidden
      >
        {running ? (
          <CircleNotch size={16} weight="bold" className="animate-spin" />
        ) : (
          <ChatCircle size={16} weight="regular" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[0.7rem] leading-none text-muted-foreground">
          {running ? "Trabajando" : "Chat"}
        </span>
        <span
          className="mt-1 block truncate text-sm leading-snug text-foreground"
          aria-live="polite"
        >
          {line}
        </span>
      </span>
      <CaretUp
        size={16}
        weight="bold"
        className="shrink-0 text-muted-foreground"
        aria-hidden
      />
    </button>
  );
}

/**
 * Two-column shell on desktop; on mobile the stage fills the viewport and
 * chat docks as a bottom peek (reasoning) that expands into a sheet.
 */
export function HomeStage({ chat, stage, hasCanvas = false }: HomeStageProps) {
  const reduce = useReducedMotion();
  const isDesktop = useIsDesktop();
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  /** Mobile sheet — start minimized so the canvas stays in view. */
  const [mobileExpanded, setMobileExpanded] = useState(false);

  useEffect(() => {
    const pref = readChatPref();
    // Only honor an explicit user choice — never auto-collapse on canvas.
    if (pref !== null) setCollapsed(pref);
    setHydrated(true);
  }, []);

  // First canvas paint: keep focus on the stage, not a chat buried below.
  useEffect(() => {
    if (hasCanvas) setMobileExpanded(false);
  }, [hasCanvas]);

  const toggleChat = () => {
    setCollapsed((prev) => {
      const next = !prev;
      writeChatPref(next);
      return next;
    });
  };

  const showChat = useCallback(() => {
    if (isDesktop) {
      setCollapsed(false);
      writeChatPref(false);
      return;
    }
    setMobileExpanded(true);
  }, [isDesktop]);

  const chatHidden = hydrated && collapsed && isDesktop;
  const compact = hasCanvas;

  const shell = useMemo<ChatShellValue>(
    () => ({ chatHidden, showChat }),
    [chatHidden, showChat],
  );

  return (
    <ChatShellContext.Provider value={shell}>
      <main
        className={[
          "flex h-[100dvh] min-h-0 flex-col overflow-hidden",
          chatHidden
            ? "md:block"
            : "md:grid md:grid-cols-[minmax(0,11fr)_minmax(0,9fr)]",
        ].join(" ")}
        style={
          {
            "--mobile-chat-peek": MOBILE_DOCK_PEEK,
          } as CSSProperties
        }
      >
        <div
          className={[
            "relative flex min-h-0 flex-1 flex-col overflow-hidden md:h-full",
            compact
              ? "px-6 py-5 md:px-10 md:py-6 lg:px-12"
              : "px-8 py-10 md:px-12 md:py-14 lg:px-16",
            // Clear the floating peek so widgets never sit under it.
            "max-md:pb-[var(--mobile-chat-peek)]",
          ].join(" ")}
        >
          <div
            aria-hidden
            className={[
              "pointer-events-none absolute inset-x-0 top-0 bg-[radial-gradient(ellipse_at_top_left,color-mix(in_oklab,var(--sky)_42%,transparent),transparent_68%)]",
              compact ? "h-40" : "h-72",
            ].join(" ")}
          />
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE }}
            className="relative shrink-0"
          >
            <div
              className={[
                "flex items-start",
                compact ? "gap-2.5" : "gap-3.5",
              ].join(" ")}
            >
              <BrandMark compact={compact} />
              <div className={["min-w-0 flex-1", compact ? "" : "pt-0.5"].join(" ")}>
                <div className="flex items-center justify-between gap-3">
                  <h1
                    className={[
                      "font-display font-semibold tracking-tight text-foreground",
                      compact
                        ? "text-xl md:text-2xl leading-tight"
                        : "text-3xl md:text-4xl lg:text-[2.65rem] lg:leading-[1.05]",
                    ].join(" ")}
                  >
                    Argentina Insights
                  </h1>
                  {isDesktop ? (
                    <button
                      type="button"
                      onClick={toggleChat}
                      className={[
                        "inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
                        chatHidden
                          ? "bg-accent text-accent-foreground hover:opacity-95"
                          : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                      ].join(" ")}
                      aria-pressed={chatHidden}
                      aria-label={chatHidden ? "Mostrar chat" : "Ocultar chat"}
                    >
                      {chatHidden ? (
                        <ChatCircle size={16} weight="regular" />
                      ) : (
                        <ChatCircleSlash size={16} weight="regular" />
                      )}
                      {chatHidden ? "Mostrar chat" : "Ocultar"}
                    </button>
                  ) : null}
                </div>
                {!compact ? (
                  <p className="mt-2.5 max-w-[36ch] text-sm leading-relaxed text-muted-foreground md:text-[0.95rem]">
                    Economía, política, cine argentino, días históricos y cruces
                    entre todo eso. Elegí una pregunta o escribí en el chat.
                  </p>
                ) : null}
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, ease: EASE, delay: 0.2 }}
            className={[
              "relative flex min-h-0 flex-1 flex-col overflow-hidden",
              compact ? "mt-4 md:mt-5" : "mt-10 md:mt-12",
            ].join(" ")}
          >
            {stage ?? (
              <p className="text-xs text-muted-foreground/50 select-none">
                La vista aparece acá.
              </p>
            )}
          </motion.div>
        </div>

        {/*
          Single chat mount: fixed bottom sheet on mobile, grid column on md+.
          Minimized mobile keeps height 0 so CopilotChat stays mounted.
        */}
        <div
          hidden={chatHidden}
          id="mobile-chat-sheet"
          className={[
            "flex flex-col bg-card",
            "max-md:fixed max-md:inset-x-0 max-md:bottom-0 max-md:z-40",
            "max-md:border-t max-md:border-border",
            "max-md:transition-[height] max-md:duration-300 max-md:ease-[cubic-bezier(0.32,0.72,0,1)]",
            mobileExpanded
              ? "max-md:h-[min(85dvh,40rem)]"
              : "max-md:h-0 max-md:overflow-hidden max-md:border-t-0",
            "md:relative md:h-full md:min-h-0 md:border-l md:border-t-0 md:bg-transparent md:p-4 lg:p-5",
          ].join(" ")}
        >
          {mobileExpanded && !isDesktop ? (
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2.5">
              <p className="text-sm font-medium text-foreground">Chat</p>
              <button
                type="button"
                onClick={() => setMobileExpanded(false)}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
                aria-label="Minimizar chat"
              >
                <CaretDown size={14} weight="bold" aria-hidden />
                Minimizar
              </button>
            </div>
          ) : null}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-card pt-4 md:rounded-2xl md:pt-0 md:shadow-[0_24px_56px_-28px_color-mix(in_oklab,var(--foreground)_30%,transparent),inset_0_1px_0_rgba(255,255,255,0.65)] md:ring-1 md:ring-border">
            {chat}
          </div>
        </div>

        {!isDesktop && !mobileExpanded ? (
          <div className="fixed inset-x-0 bottom-0 z-40 md:hidden">
            <MobileChatPeek onExpand={() => setMobileExpanded(true)} />
          </div>
        ) : null}
      </main>
    </ChatShellContext.Provider>
  );
}
