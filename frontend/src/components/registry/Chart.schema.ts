import { z } from "zod";

export const ChartSeriesSchema = z.object({
  /** Data key to read from each row */
  key: z.string(),
  /** Human-readable label for legend + tooltip */
  label: z.string(),
  /** Optional CSS / ECharts color string */
  color: z.string().optional(),
  /** Dual-axis: 0 = left (default), 1 = right */
  yAxisIndex: z.union([z.literal(0), z.literal(1)]).optional(),
});

export const ChartPropsSchema = z.object({
  /** Chart variety */
  kind: z.enum(["line", "bar", "area", "scatter", "heatmap"]),
  /** Key in each data row used as the x-axis (e.g. "fecha") */
  xKey: z.string(),
  /**
   * Second dimension: required for scatter (y numeric) and heatmap
   * (y category). Ignored for line/bar/area.
   */
  yKey: z.string().optional(),
  /**
   * Heatmap cell value key. Defaults to series[0].key when omitted.
   */
  valueKey: z.string().optional(),
  /** One entry per series (line / bar / scatter y). Heatmap usually one. */
  series: z.array(ChartSeriesSchema).min(1),
  /**
   * Optional click-to-deepen kind when the category axis is people/places.
   * Omit to infer from row.entity / column keys / label shape.
   */
  selectAs: z.enum(["fecha", "persona", "provincia", "fila"]).optional(),
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
