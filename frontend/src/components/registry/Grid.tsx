import type { ReactNode } from "react";
import type { GridProps } from "./Grid.schema";

const GAP: Record<string, string> = {
  sm: "gap-4",
  md: "gap-6",
  lg: "gap-10",
};

/**
 * Responsive multi-column layout for 2–6 leaf widgets (chart + roster, etc.).
 */
export function Grid({
  columns = 2,
  gap = "md",
  children,
}: GridProps & { children?: ReactNode }) {
  const cols =
    columns === 3
      ? "md:grid-cols-3"
      : "md:grid-cols-2";

  return (
    <div className={`grid grid-cols-1 ${cols} ${GAP[gap] ?? GAP.md}`}>
      {children}
    </div>
  );
}
