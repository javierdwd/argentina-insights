import type { ReactNode } from "react";
import type { BoxProps } from "./Box.schema";
import { sanitizeHostClass } from "./host";

/**
 * Last-resort layout container when no catalog leaf fits.
 *
 * Children come from DynamicRenderer (host tags or nested widgets).
 * `suggests` is intentionally unused here — signal for future promotion only.
 */
export function Box({
  className,
  children,
}: BoxProps & { children?: ReactNode }) {
  const safe = sanitizeHostClass(className);
  return <div className={safe}>{children}</div>;
}
