"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { ChartProps } from "./Chart.schema";

/**
 * Chart widget — time-series and category comparison.
 *
 * Receives: kind, xKey, series[], data[] (injected by bind_data).
 * The title lives on the UINode and is rendered by DynamicRenderer.
 *
 * ECharts option is built deterministically from the whitelist props;
 * the LLM never touches the raw ECharts option object.
 */

function buildOption(
  kind: "line" | "bar" | "area",
  xKey: string,
  series: ChartProps["series"],
  data: ChartProps["data"],
): EChartsOption {
  const xData = data.map((row) => String(row[xKey] ?? ""));

  const seriesDefs = series.map((s) => ({
    name: s.label,
    type: (kind === "bar" ? "bar" : "line") as "line" | "bar",
    areaStyle: kind === "area" ? {} : undefined,
    smooth: kind !== "bar",
    data: data.map((row) => {
      const v = row[s.key];
      return typeof v === "number" ? v : null;
    }),
    ...(s.color ? { itemStyle: { color: s.color } } : {}),
  }));

  const hasLegend = series.length > 1;

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
    },
    legend: hasLegend
      ? { data: series.map((s) => s.label), bottom: 0, textStyle: { fontSize: 11 } }
      : undefined,
    grid: {
      top: 8,
      right: 16,
      bottom: hasLegend ? 36 : 8,
      left: 0,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: xData,
      axisLabel: {
        fontSize: 11,
        rotate: xData.length > 20 ? 30 : 0,
        // Show every Nth label when there are many points.
        interval: xData.length > 60 ? Math.floor(xData.length / 30) : "auto",
      },
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 11 },
    },
    series: seriesDefs,
  };
}

export function Chart({ kind, xKey, series, data }: ChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-52 items-center justify-center border-t border-rule">
        <p className="text-xs text-muted-foreground/50 select-none">Sin datos</p>
      </div>
    );
  }

  return (
    <div className="border-t border-rule pt-4">
      <ReactECharts
        option={buildOption(kind, xKey, series, data)}
        style={{ height: 240 }}
        notMerge
      />
    </div>
  );
}
