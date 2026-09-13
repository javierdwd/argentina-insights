import { z } from "zod";
import { MetricPropsSchema } from "./Metric.schema";

export const MetricRowPropsSchema = z.object({
  /** Spot metrics shown in a horizontal strip */
  items: z.array(MetricPropsSchema).min(2).max(6),
});

export type MetricRowProps = z.infer<typeof MetricRowPropsSchema>;

export const MetricRowNodeSchema = z.object({
  id: z.string(),
  type: z.literal("MetricRow"),
  title: z.string().optional(),
  props: MetricRowPropsSchema,
  children: z.array(z.unknown()).optional(),
});
