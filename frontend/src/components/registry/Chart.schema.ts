import { z } from "zod";

export const ChartSeriesSchema = z.object({
  /** Data key to read from each row */
  key: z.string(),
  /** Human-readable label for legend + tooltip */
  label: z.string(),
  /** Optional CSS / ECharts color string */
  color: z.string().optional(),
});

export const ChartPropsSchema = z.object({
  /** Chart variety */
  kind: z.enum(["line", "bar", "area"]),
  /** Key in each data row used as the x-axis (e.g. "fecha") */
  xKey: z.string(),
  /** One entry per series (line / bar) to render */
  series: z.array(ChartSeriesSchema).min(1),
  /** Data rows — injected by bind_data; never authored by the LLM directly */
  data: z.array(z.record(z.string(), z.unknown())),
});

export type ChartSeries = z.infer<typeof ChartSeriesSchema>;
export type ChartProps = z.infer<typeof ChartPropsSchema>;

export const ChartNodeSchema = z.object({
  id: z.string(),
  type: z.literal("Chart"),
  title: z.string().optional(),
  props: ChartPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type ChartNode = z.infer<typeof ChartNodeSchema>;
