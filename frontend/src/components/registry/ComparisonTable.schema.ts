import { z } from "zod";

export const ComparisonColumnSchema = z.object({
  /** Key to read from each data row */
  key: z.string(),
  /** Column header shown to the user */
  label: z.string(),
  /**
   * How to render the cell. Author explicitly for percent/money/date/url.
   * If omitted, numeric values → number, everything else → text.
   */
  kind: z
    .enum(["text", "number", "percent", "money", "date", "url"])
    .optional(),
  /** Mark the entity / name column (stronger type, left emphasis). */
  primary: z.boolean().optional(),
});

export const ComparisonHighlightSchema = z.object({
  /** Numeric column to score */
  key: z.string(),
  /** `min` = cheapest / lowest wins; `max` = highest wins */
  direction: z.enum(["min", "max"]),
});

export const ComparisonTablePropsSchema = z.object({
  columns: z.array(ComparisonColumnSchema).min(2).max(8),
  /** Data rows — injected by bind_data; never authored by the LLM directly */
  data: z.array(z.record(z.string(), z.unknown())).default([]),
  /** Soft-highlight the winning cell in one numeric column */
  highlight: ComparisonHighlightSchema.optional(),
});

export type ComparisonColumn = z.infer<typeof ComparisonColumnSchema>;
export type ComparisonHighlight = z.infer<typeof ComparisonHighlightSchema>;
export type ComparisonTableProps = z.infer<typeof ComparisonTablePropsSchema>;

export const ComparisonTableNodeSchema = z.object({
  id: z.string(),
  type: z.literal("ComparisonTable"),
  title: z.string().optional(),
  props: ComparisonTablePropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type ComparisonTableNode = z.infer<typeof ComparisonTableNodeSchema>;
