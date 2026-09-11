import type { ReactNode } from "react";
import type { StackProps } from "./Stack.schema";

const GAP: Record<string, string> = {
  sm: "gap-4",
  md: "gap-6",
  lg: "gap-10",
};

/**
 * Stack container — vertical flex column.
 *
 * Accepts DynamicRenderer-rendered children.
 * No card chrome; consistent with the cold-bulletin shell.
 */
export function Stack({ gap = "md", children }: StackProps & { children?: ReactNode }) {
  return (
    <div className={`flex flex-col ${GAP[gap] ?? GAP.md}`}>
      {children}
    </div>
  );
}
