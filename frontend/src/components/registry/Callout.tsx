import { cn } from "@/lib/utils";
import { Info, Lightbulb, WarningCircle } from "@phosphor-icons/react";
import type { CalloutProps } from "./Callout.schema";

const TONE: Record<string, string> = {
  insight: "border-accent text-foreground",
  info: "border-rule text-foreground",
  warning: "border-destructive text-foreground",
};

const TONE_ICON = {
  insight: Lightbulb,
  info: Info,
  warning: WarningCircle,
} as const;

const TONE_ICON_CLASS: Record<string, string> = {
  insight: "text-accent",
  info: "text-muted-foreground",
  warning: "text-destructive",
};

/**
 * Short anchored finding under a chart — not a chat answer substitute.
 */
export function Callout({
  eyebrow,
  content,
  tone = "insight",
}: CalloutProps) {
  const Glyph =
    tone === "warning"
      ? WarningCircle
      : tone === "info"
        ? Info
        : Lightbulb;

  return (
    <aside
      className={cn(
        "flex gap-3 border-l-2 py-1 pl-4",
        TONE[tone] ?? TONE.insight,
      )}
    >
      <Glyph
        size={16}
        weight="regular"
        className={cn("mt-0.5 shrink-0", TONE_ICON_CLASS[tone] ?? TONE_ICON_CLASS.insight)}
        aria-hidden
      />
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {eyebrow}
          </p>
        ) : null}
        <p className="mt-1 text-base leading-snug text-foreground">{content}</p>
      </div>
    </aside>
  );
}
