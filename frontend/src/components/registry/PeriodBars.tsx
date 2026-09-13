"use client";

import { memo, useCallback, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { formatNumber } from "@/lib/format";
import type { PeriodBarsProps } from "./PeriodBars.schema";
import { asNumber, ChartEmpty, CHART_COLORS } from "./chart-utils";
import {
  CanvasSelectionCaption,
  useCanvasNode,
  useCanvasWriteOptional,
} from "@/components/shell/useCanvasAction";
import {
  factsFromCategoryRow,
  inferCanvasTipo,
} from "@/components/shell/infer-canvas-tipo";

function buildOption({
  labelKey,
  valueKey,
  sublabelKey,
  data,
}: PeriodBarsProps): EChartsOption {
  const labels = data.map((row) => {
    const main = String(row[labelKey] ?? "");
    if (!sublabelKey) return main;
    const sub = String(row[sublabelKey] ?? "");
    return sub ? `${main}\n${sub}` : main;
  });
  const values = data.map((row) => asNumber(row[valueKey]));

  return {
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const first = list[0] as { name?: string; value?: number } | undefined;
        if (!first) return "";
        const v =
          typeof first.value === "number"
            ? formatNumber(first.value)
            : String(first.value ?? "");
        return `${String(first.name ?? "").replace("\n", " · ")}\n${v}`;
      },
    },
    grid: { top: 8, right: 16, bottom: 8, left: 0, containLabel: true },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: {
        fontSize: 11,
        lineHeight: 14,
        interval: 0,
      },
    },
    yAxis: { type: "value", axisLabel: { fontSize: 11 } },
    series: [
      {
        type: "bar",
        data: values,
        barMaxWidth: 48,
        itemStyle: { color: CHART_COLORS[0] },
        label: {
          show: true,
          position: "top",
          fontSize: 11,
          formatter: (p: { value?: unknown }) =>
            typeof p.value === "number" ? formatNumber(p.value) : "",
        },
      },
    ],
  };
}

function rowFromEvent(
  params: Record<string, unknown>,
  data: PeriodBarsProps["data"],
  labelKey: string,
): Record<string, unknown> | undefined {
  const index = params.dataIndex;
  if (typeof index === "number" && data[index]) return data[index];
  const rawName =
    typeof params.name === "string"
      ? params.name
      : typeof params.value === "string"
        ? params.value
        : "";
  const main = rawName.split("\n")[0]?.trim() ?? "";
  if (!main) return undefined;
  const matches = data.filter((row) => String(row[labelKey] ?? "") === main);
  if (matches.length <= 1) return matches[0];
  const rest = rawName.split("\n").slice(1).join("\n").trim();
  if (rest) {
    const hit = matches.find((row) =>
      Object.values(row).some((value) => String(value ?? "").includes(rest)),
    );
    if (hit) return hit;
  }
  return matches[0];
}

const CHART_STYLE = { height: 260 } as const;
const CHART_STYLE_POINTER = { height: 260, cursor: "pointer" } as const;

export const PeriodBars = memo(function PeriodBars(props: PeriodBarsProps) {
  const { data, labelKey, valueKey, sublabelKey, selectAs } = props;
  const canvas = useCanvasWriteOptional();
  const node = useCanvasNode();

  const option = useMemo(
    () =>
      data?.length
        ? buildOption({ labelKey, valueKey, sublabelKey, data })
        : null,
    [data, labelKey, valueKey, sublabelKey],
  );

  const onChartClick = useCallback(
    (params: Record<string, unknown>) => {
      if (!canvas || !data?.length) return;
      const row = rowFromEvent(params, data, labelKey);
      const valor = String(row?.[labelKey] ?? "").trim();
      if (!valor) return;
      canvas.selectLocal({
        tipo: inferCanvasTipo({
          valor,
          row,
          categoryKey: labelKey,
          selectAs,
        }),
        valor,
        widget: "PeriodBars",
        contexto: node?.title,
        facts: factsFromCategoryRow(row, {
          skip: [labelKey],
          labels: {
            [valueKey]: "Valor",
            ...(sublabelKey ? { [sublabelKey]: "Período" } : {}),
          },
        }),
      });
    },
    [canvas, data, labelKey, valueKey, sublabelKey, selectAs, node?.title],
  );

  const onEvents = useMemo(
    () => (canvas ? { click: onChartClick } : undefined),
    [canvas, onChartClick],
  );

  if (!data?.length || !option) return <ChartEmpty />;

  return (
    <div className="border-t border-rule pt-4">
      <ReactECharts
        option={option}
        style={canvas ? CHART_STYLE_POINTER : CHART_STYLE}
        notMerge
        lazyUpdate
        onEvents={onEvents}
      />
      <CanvasSelectionCaption widget="PeriodBars" />
    </div>
  );
});
