import { z } from "zod";

export const MetricPropsSchema = z.object({
  /** Short human-readable label (e.g. "Blue dollar") */
  label: z.string(),
  /** Numeric or formatted string value */
  value: z.union([z.string(), z.number()]),
  /** Optional unit shown after the value (e.g. "ARS/USD") */
  unit: z.string().optional(),
  /** Percentage change relative to a reference (e.g. 2.3 for +2.3 %) */
  delta: z.number().optional(),
  /** Direction hint for delta coloring */
  trend: z.enum(["up", "down", "flat"]).optional(),
});

export type MetricProps = z.infer<typeof MetricPropsSchema>;

export const MetricNodeSchema = z.object({
  type: z.literal("Metric"),
  props: MetricPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type MetricNode = z.infer<typeof MetricNodeSchema>;
