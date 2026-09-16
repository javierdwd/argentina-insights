"use client";

import { memo, useCallback, useEffect, useMemo, useRef } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption, EChartsType } from "echarts";
import type { VoteBreakdownProps } from "./VoteBreakdown.schema";
import { ChartEmpty, ACCENT_HEX } from "./chart-utils";

const VOTE_COLORS: Record<string, string> = {
  AFIRMATIVO: ACCENT_HEX,
  POSITIVO: ACCENT_HEX,
  SI: ACCENT_HEX,
  NEGATIVO: "#9b3b3b",
  NO: "#9b3b3b",
  ABSTENCION: "#5c6b7a",
  ABSTENCIÓN: "#5c6b7a",
  AUSENTE: "#c9d3de",
  PRESENTE: "#8a9aab",
};

const CHART_STYLE = { width: "100%", height: 260 } as const;

function normalizeVote(raw: string): string {
  return raw.trim().toUpperCase();
}

function buildOption(
  kind: "donut" | "pie",
  voteKey: string,
  data: VoteBreakdownProps["data"],
): EChartsOption {
  const counts = new Map<string, number>();
  for (const row of data) {
    const label = normalizeVote(String(row[voteKey] ?? ""));
    if (!label) continue;
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }

  const pieData = [...counts.entries()].map(([name, value]) => ({
    name,
    value,
    itemStyle: { color: VOTE_COLORS[name] ?? "#5c6b7a" },
  }));

  return {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: {
      bottom: 0,
      textStyle: { fontSize: 11 },
    },
    series: [
      {
        type: "pie",
        radius: kind === "donut" ? ["42%", "68%"] : "68%",
        center: ["50%", "46%"],
        label: { fontSize: 11 },
        data: pieData,
      },
    ],
  };
}

export const VoteBreakdown = memo(function VoteBreakdown({
  voteKey = "voto",
  kind = "donut",
  data,
}: VoteBreakdownProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const option = useMemo(
    () => (data?.length ? buildOption(kind, voteKey, data) : null),
    [kind, voteKey, data],
  );
  const chartVisible = Boolean(data?.length && option);

  const resizeChart = useCallback(() => {
    chartRef.current?.resize({ width: "auto", height: "auto" });
  }, []);

  const onChartReady = useCallback(
    (chart: EChartsType) => {
      chartRef.current = chart;
      requestAnimationFrame(resizeChart);
    },
    [resizeChart],
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(resizeChart);
    });
    observer.observe(container);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      chartRef.current = null;
    };
  }, [chartVisible, resizeChart]);

  if (!chartVisible || !option) return <ChartEmpty />;

  return (
    <div
      ref={containerRef}
      className="w-full min-w-0 max-w-full overflow-hidden border-t border-rule pt-4"
    >
      <ReactECharts
        className="w-full min-w-0 max-w-full"
        option={option}
        style={CHART_STYLE}
        notMerge
        lazyUpdate
        onChartReady={onChartReady}
      />
    </div>
  );
});
