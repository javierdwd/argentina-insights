import type { ReactNode } from "react";
import { Sparkle } from "@phosphor-icons/react";
import type { BoxProps } from "./Box.schema";
import { sanitizeHostClass } from "./host";

/**
 * Authored layout container generated for the current query.
 *
 * Children come from DynamicRenderer (host tags or nested widgets).
 * `suggests` is intentionally unused here — signal for future promotion only.
 */
export function Box({
  className,
  children,
}: BoxProps & { children?: ReactNode }) {
  const safe = sanitizeHostClass(className);
  return (
    <div>
      <div className={safe}>{children}</div>
      <div className="mt-2 flex justify-end">
        <span className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-secondary/55 px-2 py-1 text-[10px] font-medium tracking-wide text-muted-foreground">
          <Sparkle size={11} weight="fill" aria-hidden />
          Visualización generada por IA
        </span>
      </div>
    </div>
  );
}
