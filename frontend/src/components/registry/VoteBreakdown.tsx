"use client";

import { memo, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
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

const CHART_STYLE = { height: 260 } as const;

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
  const option = useMemo(
    () => (data?.length ? buildOption(kind, voteKey, data) : null),
    [kind, voteKey, data],
  );

  if (!data?.length || !option) return <ChartEmpty />;

  return (
    <div className="border-t border-rule pt-4">
      <ReactECharts
        option={option}
        style={CHART_STYLE}
        notMerge
        lazyUpdate
      />
    </div>
  );
});
