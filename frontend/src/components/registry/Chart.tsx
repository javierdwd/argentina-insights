"use client";

import { memo, useCallback, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { ChartProps } from "./Chart.schema";
import {
  CanvasSelectionCaption,
  useCanvasBrush,
  useCanvasNode,
  useCanvasWriteOptional,
} from "@/components/shell/useCanvasAction";
import { factsFromSeriesRow } from "@/components/shell/CanvasInspector";
import { inferCanvasTipo } from "@/components/shell/infer-canvas-tipo";
import { isoDayPrefix, textMatchesBrush } from "@/components/shell/canvas-brush";
import {
  asNumber,
  axisLabelsAreMultiYear,
  categoryAxisLabel,
  ChartEmpty,
  CHART_COLORS,
  downsampleRows,
  downsampleRowsPreferFilled,
  formatAxisLabel,
  resolveChartSeries,
  seriesColor,
  trimEmptyMeasureEdges,
  ACCENT_HEX,
  SKY_HEX,
  withAutoDualAxis,
} from "./chart-utils";
import {
  availableChartRangeOptions,
  filterRowsByRelativeRange,
  xKeyLooksDated,
  type ChartRangeId,
} from "./chart-local-controls";
import {
  pivotCategoryVoteCounts,
  seriesLookLikeVotes,
  sortVoteCategoryRows,
} from "./vote-pivot";
import { pivotLongSeries } from "./chart-series";

/**
 * Chart widget — time-series, category bars, dual-axis, scatter, heatmap.
 *
 * ECharts option is built deterministically from whitelist props;
 * the LLM never touches the raw ECharts option object.
 */

function buildCartesian(
  kind: "line" | "bar" | "area",
  xKey: string,
  series: ChartProps["series"],
  data: ChartProps["data"],
  opts?: { stack?: boolean },
): EChartsOption {
  const measureKeys = series.map((s) => s.key);
  const trimmed = trimEmptyMeasureEdges(data, measureKeys);
  const rows =
    series.length > 1
      ? downsampleRowsPreferFilled(trimmed, measureKeys)
      : downsampleRows(trimmed);
  const seriesAxis = withAutoDualAxis(series, rows);
  const xData = rows.map((row) => String(row[xKey] ?? ""));
  const dated = xData.some((value) => /^\d{4}-\d{2}-\d{2}/.test(value));
  const multiYear = dated && axisLabelsAreMultiYear(xData);
  const dual = seriesAxis.some((s) => s.yAxisIndex === 1);
  const isLine = kind !== "bar";
  const showSymbol = isLine && rows.length <= 16;
  const stack = kind === "bar" && opts?.stack ? "votes" : undefined;

  const seriesDefs = seriesAxis.map((s, i) => {
    const color = seriesColor(i, s.color);
    return {
      name: s.label,
      type: (kind === "bar" ? "bar" : "line") as "line" | "bar",
      stack,
      barMaxWidth: kind === "bar" ? 48 : undefined,
      areaStyle: kind === "area" ? { color, opacity: 0.15 } : undefined,
      smooth: isLine,
      showSymbol,
      connectNulls: isLine,
      yAxisIndex: s.yAxisIndex ?? 0,
      data: rows.map((row) => asNumber(row[s.key])),
      itemStyle: { color },
      lineStyle: kind === "bar" ? undefined : { color, width: 2 },
    };
  });

  const hasLegend = seriesAxis.length > 1;
  const axisLabel = categoryAxisLabel(xData.length);
  const longCats = !dated && xData.some((value) => value.length > 14);

  return {
    color: CHART_COLORS,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
    },
    legend: hasLegend
      ? {
          data: seriesAxis.map((s) => s.label),
          bottom: 0,
          textStyle: { fontSize: 11 },
        }
      : undefined,
    grid: {
      top: 8,
      // Keep plot + last tick labels inside the canvas (overflow clips otherwise).
      right: dual ? 56 : 28,
      bottom: hasLegend ? 36 : 24,
      left: 8,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: xData,
      // Inset categories so first/last points (and tick labels) are not clipped.
      boundaryGap: true,
      axisLabel: {
        ...axisLabel,
        interval: kind === "bar" && xData.length <= 20 ? 0 : axisLabel.interval,
        rotate: kind === "bar" && longCats ? 28 : 0,
        formatter: dated
          ? (value: string) => formatAxisLabel(value, { multiYear })
          : (value: string) => value,
      },
    },
    yAxis: dual
      ? [
          { type: "value", axisLabel: { fontSize: 11 } },
          { type: "value", axisLabel: { fontSize: 11 }, splitLine: { show: false } },
        ]
      : { type: "value", axisLabel: { fontSize: 11 } },
    series: seriesDefs,
  };
}

function buildScatter(
  xKey: string,
  yKey: string,
  series: ChartProps["series"],
  data: ChartProps["data"],
): EChartsOption {
  const points = data
    .map((row) => {
      const x = asNumber(row[xKey]);
      const y = asNumber(row[yKey]);
      if (x === null || y === null) return null;
      return [x, y] as [number, number];
    })
    .filter((p): p is [number, number] => p !== null);

  return {
    tooltip: { trigger: "item" },
    grid: { top: 8, right: 28, bottom: 28, left: 8, containLabel: true },
    xAxis: {
      type: "value",
      name: series[0]?.label ?? xKey,
      nameLocation: "middle",
      nameGap: 28,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: series[1]?.label ?? yKey,
      nameLocation: "middle",
      nameGap: 36,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: "scatter",
        symbolSize: 8,
        data: points,
        itemStyle: {
          color: seriesColor(0, series[0]?.color),
        },
      },
    ],
  };
}

function buildHeatmap(
  xKey: string,
  yKey: string,
  valueKey: string,
  data: ChartProps["data"],
): EChartsOption {
  const xCats = [...new Set(data.map((r) => String(r[xKey] ?? "")))];
  const yCats = [...new Set(data.map((r) => String(r[yKey] ?? "")))];
  const xIndex = new Map(xCats.map((v, i) => [v, i]));
  const yIndex = new Map(yCats.map((v, i) => [v, i]));

  let min = Infinity;
  let max = -Infinity;
  const cells: [number, number, number][] = [];
  for (const row of data) {
    const xi = xIndex.get(String(row[xKey] ?? ""));
    const yi = yIndex.get(String(row[yKey] ?? ""));
    const v = asNumber(row[valueKey]);
    if (xi === undefined || yi === undefined || v === null) continue;
    cells.push([xi, yi, v]);
    min = Math.min(min, v);
    max = Math.max(max, v);
  }
  if (!Number.isFinite(min)) {
    min = 0;
    max = 1;
  }

  return {
    tooltip: { position: "top" },
    grid: { top: 8, right: 28, bottom: 48, left: 8, containLabel: true },
    xAxis: {
      type: "category",
      data: xCats,
      splitArea: { show: true },
      axisLabel: {
        fontSize: 10,
        rotate: xCats.length > 12 ? 40 : 0,
        hideOverlap: true,
      },
    },
    yAxis: {
      type: "category",
      data: yCats,
      splitArea: { show: true },
      axisLabel: { fontSize: 10 },
    },
    visualMap: {
      min,
      max,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: {
        color: ["#e8eef2", SKY_HEX, ACCENT_HEX],
      },
      textStyle: { fontSize: 10 },
    },
    series: [
      {
        type: "heatmap",
        data: cells,
        label: { show: cells.length <= 80, fontSize: 9 },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: "rgba(0,0,0,0.2)" },
        },
      },
    ],
  };
}

function resolveCartesianRows(
  kind: ChartProps["kind"],
  xKey: string,
  series: ChartProps["series"],
  data: ChartProps["data"] | null | undefined,
): { data: ChartProps["data"]; stack: boolean } {
  const rows = data ?? [];
  if (kind === "scatter" || kind === "heatmap") {
    return { data: rows, stack: false };
  }
  const pivoted = pivotCategoryVoteCounts(rows, xKey, series);
  if (pivoted) {
    return { data: sortVoteCategoryRows(pivoted, series), stack: true };
  }
  return { data: rows, stack: kind === "bar" && seriesLookLikeVotes(series) };
}

function buildOption(props: ChartProps): EChartsOption | null {
  const { kind, xKey, yKey, valueKey, series, data } = props;
  if (kind === "scatter") {
    if (!yKey) return null;
    return buildScatter(xKey, yKey, series, data);
  }
  if (kind === "heatmap") {
    if (!yKey) return null;
    const vk = valueKey ?? series[0]?.key;
    if (!vk) return null;
    return buildHeatmap(xKey, yKey, vk, data);
  }
  const resolved = resolveCartesianRows(kind, xKey, series, data);
  return buildCartesian(kind, xKey, series, resolved.data, {
    stack: resolved.stack,
  });
}

function chartClickValor(params: Record<string, unknown>): string | null {
  const name = params.name;
  if (typeof name === "string" && name.trim()) return name.trim();
  const value = params.value;
  if (Array.isArray(value) && value.length > 0) {
    const x = value[0];
    if (typeof x === "string" || typeof x === "number") return String(x);
  }
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return null;
}

const CHART_STYLE = { height: 240 } as const;
const CHART_STYLE_POINTER = { height: 240, cursor: "pointer" } as const;

function withCategoryBrushMark(
  option: EChartsOption,
  brushValor: string | null,
): EChartsOption {
  if (!brushValor) return option;
  const series = option.series;
  if (!Array.isArray(series) || series.length === 0) return option;
  const marked = series.map((entry, index) => {
    if (!entry || typeof entry !== "object") return entry;
    if (index !== 0) return entry;
    return {
      ...entry,
      markLine: {
        symbol: "none" as const,
        label: { show: false },
        lineStyle: {
          color: ACCENT_HEX,
          type: "dashed" as const,
          width: 1.5,
        },
        data: [{ xAxis: brushValor }],
      },
    };
  });
  return { ...option, series: marked as EChartsOption["series"] };
}

export const Chart = memo(function Chart(props: ChartProps) {
  const {
    data,
    series: seriesProp,
    seriesBy,
    valueKey,
    kind,
    xKey,
    selectAs,
  } = props;
  const canvas = useCanvasWriteOptional();
  const brush = useCanvasBrush();
  const node = useCanvasNode();
  const [range, setRange] = useState<ChartRangeId>("all");
  const [hiddenKeys, setHiddenKeys] = useState<string[]>([]);

  const chartSource = useMemo(
    () => pivotLongSeries(data, xKey, seriesBy, valueKey, seriesProp),
    [data, seriesBy, seriesProp, valueKey, xKey],
  );

  const series = useMemo(
    () => resolveChartSeries(seriesProp, chartSource),
    [seriesProp, chartSource],
  );

  const dated = useMemo(
    () =>
      kind !== "scatter" &&
      kind !== "heatmap" &&
      xKeyLooksDated(chartSource, xKey),
    [chartSource, kind, xKey],
  );

  const rangeOptions = useMemo(
    () => (dated ? availableChartRangeOptions(chartSource, xKey) : []),
    [chartSource, dated, xKey],
  );
  const effectiveRange = rangeOptions.some((option) => option.id === range)
    ? range
    : "all";

  const rangedSource = useMemo(() => {
    if (!chartSource.length) return chartSource;
    if (!dated || effectiveRange === "all") return chartSource;
    return filterRowsByRelativeRange(chartSource, xKey, effectiveRange);
  }, [chartSource, dated, effectiveRange, xKey]);

  const visibleSeries = useMemo(() => {
    if (!hiddenKeys.length) return series;
    const hidden = new Set(hiddenKeys);
    return series.filter((s) => !hidden.has(s.key));
  }, [series, hiddenKeys]);

  const resolved = useMemo(
    () => resolveCartesianRows(kind, xKey, visibleSeries, rangedSource),
    [kind, xKey, visibleSeries, rangedSource],
  );
  const chartRows = resolved.data;

  const yKey = props.yKey;
  const brushValor = useMemo(() => {
    if (!brush?.valor || kind === "scatter" || kind === "heatmap") return null;
    const match = chartRows.find((row) => {
      const cell = String(row[xKey] ?? "");
      if (brush.tipo === "fecha") {
        return isoDayPrefix(cell) === isoDayPrefix(brush.valor);
      }
      return textMatchesBrush(cell, brush);
    });
    return match ? String(match[xKey] ?? "") : null;
  }, [brush, chartRows, kind, xKey]);

  const option = useMemo(() => {
    if (!rangedSource?.length || !visibleSeries?.length) return null;
    const built = buildOption({
      kind,
      xKey,
      yKey,
      valueKey,
      series: visibleSeries,
      data: chartRows,
    });
    if (!built) return null;
    return withCategoryBrushMark(built, brushValor);
  }, [
    chartRows,
    rangedSource?.length,
    visibleSeries,
    kind,
    xKey,
    yKey,
    valueKey,
    brushValor,
  ]);

  const onChartClick = useCallback(
    (params: Record<string, unknown>) => {
      if (!canvas) return;
      if (kind === "scatter" || kind === "heatmap") return;
      const valor = chartClickValor(params);
      if (!valor) return;
      const row = chartRows?.find((r) => String(r[xKey] ?? "") === valor);
      canvas.selectLocal({
        tipo: inferCanvasTipo({
          valor,
          row,
          categoryKey: xKey,
          selectAs,
        }),
        valor,
        widget: "Chart",
        contexto: node?.title,
        facts: factsFromSeriesRow(row, series ?? []),
      });
    },
    [canvas, kind, node?.title, chartRows, series, xKey, selectAs],
  );

  const onEvents = useMemo(
    () => (canvas ? { click: onChartClick } : undefined),
    [canvas, onChartClick],
  );

  const toggleSeries = (key: string) => {
    setHiddenKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  if (!chartSource.length || !series.length) return <ChartEmpty />;
  if (!option) return <ChartEmpty />;

  const showRange = rangeOptions.length > 1;
  const showSeriesToggle = series.length > 1 && kind !== "scatter" && kind !== "heatmap";

  return (
    <div className="border-t border-rule pt-4">
      {showRange || showSeriesToggle ? (
        <div className="mb-3 flex flex-col gap-2">
          {showRange ? (
            <div className="flex flex-wrap gap-1" role="group" aria-label="Rango">
              {rangeOptions.map((opt) => {
                const active = effectiveRange === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setRange(opt.id)}
                    className={[
                      "rounded-md px-2 py-1 text-xs font-medium transition-colors",
                      active
                        ? "bg-accent-soft text-foreground"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                    ].join(" ")}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          ) : null}
          {showSeriesToggle ? (
            <div
              className="flex flex-wrap gap-1"
              role="group"
              aria-label="Series"
            >
              {series.map((s) => {
                const on = !hiddenKeys.includes(s.key);
                return (
                  <button
                    key={s.key}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleSeries(s.key)}
                    className={[
                      "rounded-md px-2 py-1 text-xs transition-colors",
                      on
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground/50 line-through hover:text-muted-foreground",
                    ].join(" ")}
                  >
                    {s.label || s.key}
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}
      <ReactECharts
        option={option}
        style={canvas ? CHART_STYLE_POINTER : CHART_STYLE}
        notMerge
        lazyUpdate
        onEvents={onEvents}
      />
      <CanvasSelectionCaption widget="Chart" label="Punto marcado" />
    </div>
  );
});
