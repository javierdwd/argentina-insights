"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ChatCircle, ChatCircleSlash } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "motion/react";
import { FloatingComposer } from "./FloatingComposer";

const EASE = [0.32, 0.72, 0, 1] as const;
const CHAT_PREF_KEY = "argentina-insights.chat-collapsed";
const MD_QUERY = "(min-width: 768px)";

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
 * Two-column shell: brand + stage (left) · chat panel (right).
 *
 * With a canvas: compact brand (smaller mark + title, no blurb) so the
 * stage gets the vertical room. Chat collapse on desktop uses `hidden`
 * so the tray never stacks under the stage. When chat is hidden, a
 * floating composer stays available at the bottom of the stage.
 */
export function HomeStage({ chat, stage, hasCanvas = false }: HomeStageProps) {
  const reduce = useReducedMotion();
  const isDesktop = useIsDesktop();
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const pref = readChatPref();
    if (pref !== null) {
      setCollapsed(pref);
    } else {
      setCollapsed(hasCanvas);
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || !hasCanvas) return;
    if (readChatPref() !== null) return;
    setCollapsed(true);
  }, [hasCanvas, hydrated]);

  const toggleChat = () => {
    setCollapsed((prev) => {
      const next = !prev;
      writeChatPref(next);
      return next;
    });
  };

  const showChat = () => {
    setCollapsed(false);
    writeChatPref(false);
  };

  const chatHidden = hydrated && collapsed && isDesktop;
  const compact = hasCanvas;

  return (
    <main
      className={[
        "flex min-h-[100dvh] flex-col md:h-[100dvh] md:min-h-0 md:overflow-hidden",
        chatHidden
          ? "md:block"
          : "md:grid md:grid-cols-[minmax(0,11fr)_minmax(0,9fr)]",
      ].join(" ")}
    >
      <div
        className={[
          "relative flex flex-col md:h-full md:min-h-0 md:overflow-hidden",
          compact
            ? "px-6 py-5 md:px-10 md:py-6 lg:px-12"
            : "px-8 py-10 md:px-12 md:py-14 lg:px-16",
          chatHidden ? "pb-24" : "",
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
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
                    aria-pressed={chatHidden}
                    aria-label={chatHidden ? "Mostrar chat" : "Ocultar chat"}
                  >
                    {chatHidden ? (
                      <ChatCircle size={16} weight="regular" />
                    ) : (
                      <ChatCircleSlash size={16} weight="regular" />
                    )}
                    {chatHidden ? "Chat" : "Ocultar"}
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
            "relative flex min-h-0 flex-1 flex-col md:overflow-hidden",
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

      <div
        hidden={chatHidden}
        className="flex h-[70dvh] shrink-0 flex-col border-t border-border bg-card md:h-full md:min-h-0 md:border-l md:border-t-0 md:bg-transparent md:p-4 lg:p-5"
      >
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-card pt-4 md:rounded-2xl md:pt-0 md:shadow-[0_24px_56px_-28px_color-mix(in_oklab,var(--foreground)_30%,transparent),inset_0_1px_0_rgba(255,255,255,0.65)] md:ring-1 md:ring-border">
          {chat}
        </div>
      </div>

      {chatHidden ? <FloatingComposer onShowChat={showChat} /> : null}
    </main>
  );
}
