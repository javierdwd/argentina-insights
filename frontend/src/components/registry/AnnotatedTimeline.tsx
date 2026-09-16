"use client";

import { memo, useCallback, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { AnnotatedTimelineProps } from "./AnnotatedTimeline.schema";
import {
  useCanvasNode,
  useCanvasWriteOptional,
} from "@/components/shell/useCanvasAction";
import { factsFromSeriesRow } from "@/components/shell/CanvasInspector";
import {
  asNumber,
  axisLabelsAreMultiYear,
  categoryAxisLabel,
  ChartEmpty,
  CHART_COLORS,
  downsampleRows,
  formatAxisLabel,
  resolveChartSeries,
  seriesColor,
  ACCENT_HEX,
} from "./chart-utils";

function buildOption({
  xKey,
  series,
  marks = [],
  bands = [],
  data,
}: AnnotatedTimelineProps): EChartsOption {
  // Keep full resolution when marks/bands need exact category matches.
  const rows =
    marks.length > 0 || bands.length > 0 ? data : downsampleRows(data);
  const xData = rows.map((row) => String(row[xKey] ?? ""));
  const multiYear = axisLabelsAreMultiYear(xData);
  const showSymbol = rows.length <= 16;
  const axisLabel = categoryAxisLabel(xData.length);

  const markLine =
    marks.length > 0
      ? {
          symbol: "none",
          label: { fontSize: 10, color: "#5c6b7a" },
          lineStyle: { type: "dashed" as const, color: ACCENT_HEX },
          data: marks.map((m) => ({
            xAxis: m.x,
            name: m.label,
            label: { formatter: m.label },
          })),
        }
      : undefined;

  const markArea =
    bands.length > 0
      ? {
          itemStyle: { color: "rgba(31, 107, 92, 0.08)" },
          data: bands.map(
            (b) =>
              [
                {
                  xAxis: b.from,
                  itemStyle: b.color ? { color: b.color } : undefined,
                  name: b.label,
                },
                { xAxis: b.to },
              ] as [
                {
                  xAxis: string;
                  name: string;
                  itemStyle?: { color: string };
                },
                { xAxis: string },
              ],
          ),
        }
      : undefined;

  const seriesDefs = series.map((s, i) => {
    const color = seriesColor(i, s.color);
    const entry: Record<string, unknown> = {
      name: s.label,
      type: "line",
      smooth: true,
      showSymbol,
      connectNulls: true,
      data: rows.map((row) => asNumber(row[s.key])),
      itemStyle: { color },
      lineStyle: { color, width: 2 },
    };
    if (i === 0 && markLine) entry.markLine = markLine;
    if (i === 0 && markArea) entry.markArea = markArea;
    return entry;
  });

  const hasLegend = series.length > 1;

  return {
    color: CHART_COLORS,
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    legend: hasLegend
      ? {
          data: series.map((s) => s.label),
          bottom: 0,
          textStyle: { fontSize: 11 },
        }
      : undefined,
    grid: {
      top: 16,
      right: 16,
      bottom: hasLegend ? 36 : 8,
      left: 0,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: xData,
      axisLabel: {
        ...axisLabel,
        formatter: (value: string) => formatAxisLabel(value, { multiYear }),
      },
    },
    yAxis: { type: "value", axisLabel: { fontSize: 11 } },
    series: seriesDefs,
  } as EChartsOption;
}

const CHART_STYLE = { height: 260 } as const;
const CHART_STYLE_POINTER = { height: 260, cursor: "pointer" } as const;
const EMPTY_MARKS: NonNullable<AnnotatedTimelineProps["marks"]> = [];
const EMPTY_BANDS: NonNullable<AnnotatedTimelineProps["bands"]> = [];

export const AnnotatedTimeline = memo(function AnnotatedTimeline(
  props: AnnotatedTimelineProps,
) {
  const canvas = useCanvasWriteOptional();
  const node = useCanvasNode();
  const { data, series: seriesProp, xKey } = props;
  const series = useMemo(
    () => resolveChartSeries(seriesProp, data),
    [seriesProp, data],
  );
  const marks = props.marks ?? EMPTY_MARKS;
  const bands = props.bands ?? EMPTY_BANDS;

  const option = useMemo(
    () =>
      data?.length && series?.length
        ? buildOption({ xKey, series, marks, bands, data })
        : null,
    [data, series, xKey, marks, bands],
  );

  const onChartClick = useCallback(
    (params: Record<string, unknown>) => {
      if (!canvas) return;
      const name = params.name;
      const valor =
        typeof name === "string" && name.trim()
          ? name.trim()
          : typeof params.value === "string"
            ? params.value
            : null;
      if (!valor) return;
      const row = data?.find((r) => String(r[xKey] ?? "") === valor);
      canvas.selectLocal({
        tipo: "fecha",
        valor,
        widget: "AnnotatedTimeline",
        contexto: node?.title,
        facts: factsFromSeriesRow(row, series ?? []),
      });
    },
    [canvas, node?.title, data, series, xKey],
  );

  const onEvents = useMemo(
    () => (canvas ? { click: onChartClick } : undefined),
    [canvas, onChartClick],
  );

  if (!data?.length || !series?.length || !option) return <ChartEmpty />;

  return (
    <div className="border-t border-rule pt-4">
      <ReactECharts
        option={option}
        style={canvas ? CHART_STYLE_POINTER : CHART_STYLE}
        notMerge
        lazyUpdate
        onEvents={onEvents}
      />
    </div>
  );
});
