import { z } from "zod";
import { ChartSeriesSchema } from "./Chart.schema";

export const TimelineMarkSchema = z.object({
  /** x-axis category value (usually a fecha ISO) */
  x: z.string(),
  label: z.string(),
});

export const TimelineBandSchema = z.object({
  from: z.string(),
  to: z.string(),
  label: z.string(),
  color: z.string().optional(),
});

export const AnnotatedTimelinePropsSchema = z.object({
  xKey: z.string(),
  series: z.array(ChartSeriesSchema).min(1),
  /** Event markers (vote day, peak, etc.) — authored by compose, not data */
  marks: z.array(TimelineMarkSchema).optional(),
  /** Mandate / era overlays */
  bands: z.array(TimelineBandSchema).optional(),
  data: z.array(z.record(z.string(), z.unknown())).default([]),
});

export type AnnotatedTimelineProps = z.infer<typeof AnnotatedTimelinePropsSchema>;

export const AnnotatedTimelineNodeSchema = z.object({
  id: z.string(),
  type: z.literal("AnnotatedTimeline"),
  title: z.string().optional(),
  props: AnnotatedTimelinePropsSchema,
  children: z.array(z.unknown()).optional(),
});
