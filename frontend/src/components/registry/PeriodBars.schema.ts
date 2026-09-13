import { z } from "zod";

export const PeriodBarsPropsSchema = z.object({
  labelKey: z.string(),
  valueKey: z.string(),
  /** Optional date range / secondary line under the label */
  sublabelKey: z.string().optional(),
  /**
   * Optional click-to-deepen kind when the category axis is people/places.
   * Omit to infer from row.entity / column keys / label shape.
   */
  selectAs: z.enum(["fecha", "persona", "provincia", "fila"]).optional(),
  data: z.array(z.record(z.string(), z.unknown())).default([]),
});

export type PeriodBarsProps = z.infer<typeof PeriodBarsPropsSchema>;

export const PeriodBarsNodeSchema = z.object({
  id: z.string(),
  type: z.literal("PeriodBars"),
  title: z.string().optional(),
  props: PeriodBarsPropsSchema,
  children: z.array(z.unknown()).optional(),
});
