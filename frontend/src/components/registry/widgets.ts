import type { ComponentType } from "react";
import type { z } from "zod";
import { Metric } from "./Metric";
import { MetricNodeSchema } from "./Metric.schema";

/**
 * Component registry — map UITree `type` → React component.
 * Add a line here when you add a widget (+ its *.schema.ts).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const REGISTRY: Record<string, ComponentType<any>> = {
  Metric,
};

/**
 * Per-type Zod node schemas (for validation / agent catalog later).
 */
export const NODE_SCHEMAS = {
  Metric: MetricNodeSchema,
} as const satisfies Record<string, z.ZodType>;
