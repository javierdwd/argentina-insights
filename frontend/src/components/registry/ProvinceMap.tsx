"use client";

import { memo, useCallback, useMemo } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";
import argentinaOutline from "./geo/argentina-outline.json";
import { provinceCentroid } from "./geo/provinces";
import type { ProvinceMapProps } from "./ProvinceMap.schema";
import { ResponsiveEChart } from "./ResponsiveEChart";
import { asNumber, ACCENT_HEX } from "./chart-utils";
import {
  useCanvasBrush,
  useCanvasNode,
  useCanvasWriteOptional,
} from "@/components/shell/useCanvasAction";

let mapRegistered = false;

function ensureMap() {
  if (mapRegistered) return;
  echarts.registerMap("argentina", argentinaOutline as never);
  mapRegistered = true;
}

function canon(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .trim();
}

/** When valueKey looks like a vote label, treat it as a filter on voto. */
function voteFilterFromKey(valueKey: string): string | null {
  const key = canon(valueKey).replace(/s$/, "");
  const known = ["negativo", "afirmativo", "abstencion", "ausente"];
  return known.find((v) => key === v || key.includes(v)) ?? null;
}

type Ranked = { name: string; value: number };

/**
 * Resolve province totals. Prefer a numeric valueKey; if rows are a raw
 * roll call (provincia + voto), count per province (optionally filtered).
 */
function resolveRanked(
  nameKey: string,
  valueKey: string,
  data: ProvinceMapProps["data"],
): Ranked[] {
  const numeric: Ranked[] = [];
  for (const row of data) {
    const name = String(row[nameKey] ?? "").trim();
    const value = asNumber(row[valueKey]);
    if (!name || value === null) continue;
    numeric.push({ name, value });
  }
  if (numeric.length > 0) {
    // Merge duplicate province names.
    const merged = new Map<string, number>();
    for (const row of numeric) {
      merged.set(row.name, (merged.get(row.name) ?? 0) + row.value);
    }
    return [...merged.entries()].map(([name, value]) => ({ name, value }));
  }

  // Fallbacks when compose bound vote rows without a pre-aggregated count.
  const voteFilter = voteFilterFromKey(valueKey);
  const countKeys = ["count", "total", "n", "cantidad", "value", "negativos"];
  const hasCountCol = data.some((row) =>
    countKeys.some((k) => asNumber(row[k]) !== null),
  );
  if (hasCountCol) {
    const merged = new Map<string, number>();
    for (const row of data) {
      const name = String(row[nameKey] ?? "").trim();
      if (!name) continue;
      for (const k of countKeys) {
        const n = asNumber(row[k]);
        if (n === null) continue;
        merged.set(name, (merged.get(name) ?? 0) + n);
        break;
      }
    }
    if (merged.size > 0) {
      return [...merged.entries()].map(([name, value]) => ({ name, value }));
    }
  }

  const counts = new Map<string, number>();
  for (const row of data) {
    const name = String(
      row[nameKey] ?? row.provincia ?? row.province ?? "",
    ).trim();
    if (!name) continue;
    if (voteFilter) {
      const voto = canon(String(row.voto ?? row.vote ?? row.role ?? ""));
      if (!voto || (!voto.includes(voteFilter) && voto !== voteFilter)) {
        continue;
      }
    }
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts.entries()].map(([name, value]) => ({ name, value }));
}

function buildOption(
  ranked: Ranked[],
  brushName: string | null,
): EChartsOption | null {
  if (ranked.length === 0) return null;

  ensureMap();

  const brushNorm = brushName
    ? brushName
        .normalize("NFD")
        .replace(/\p{M}/gu, "")
        .toLowerCase()
        .trim()
    : null;

  const points: {
    name: string;
    value: [number, number, number];
    itemStyle?: { opacity: number; borderWidth: number };
  }[] = [];

  for (const row of ranked) {
    const centroid = provinceCentroid(row.name);
    if (!centroid) continue;
    const [lat, lon] = centroid;
    const match =
      brushNorm &&
      row.name
        .normalize("NFD")
        .replace(/\p{M}/gu, "")
        .toLowerCase()
        .trim() === brushNorm;
    points.push({
      name: row.name,
      value: [lon, lat, row.value],
      itemStyle: match
        ? { opacity: 1, borderWidth: 2 }
        : brushNorm
          ? { opacity: 0.35, borderWidth: 1 }
          : undefined,
    });
  }

  ranked = [...ranked].sort((a, b) => b.value - a.value);
  const max = Math.max(...ranked.map((r) => r.value), 1);

  // Prefer geo bubbles when we can place ≥ half the provinces; else bars.
  if (points.length >= Math.max(3, ranked.length * 0.4)) {
    return {
      tooltip: {
        trigger: "item",
        formatter: (p: unknown) => {
          const item = p as {
            name?: string;
            value?: number | number[];
          };
          const v = Array.isArray(item.value) ? item.value[2] : item.value;
          return `${item.name ?? ""}: ${v ?? "—"}`;
        },
      },
      geo: {
        map: "argentina",
        roam: false,
        aspectScale: 0.85,
        layoutCenter: ["50%", "46%"],
        layoutSize: "95%",
        itemStyle: {
          areaColor: "#e8eef2",
          borderColor: "#c9d3de",
          borderWidth: 1,
        },
        emphasis: { disabled: true },
        silent: true,
      },
      visualMap: {
        min: 0,
        max,
        calculable: false,
        show: true,
        orient: "horizontal",
        left: "center",
        bottom: 4,
        inRange: { color: ["#d6e8f6", ACCENT_HEX] },
        textStyle: { fontSize: 10 },
      },
      series: [
        {
          type: "scatter",
          coordinateSystem: "geo",
          data: points,
          symbolSize: (val: number[]) =>
            10 + (Math.sqrt(Math.max(val[2], 0)) / Math.sqrt(max)) * 32,
          itemStyle: {
            color: ACCENT_HEX,
            opacity: 0.88,
            borderColor: "#f7fafc",
            borderWidth: 1,
          },
          label: {
            show: points.length <= 12,
            formatter: "{b}",
            fontSize: 9,
            color: "#5a6b7c",
            position: "right",
          },
        },
      ],
    };
  }

  return {
    tooltip: { trigger: "axis" },
    grid: { top: 8, right: 24, bottom: 8, left: 0, containLabel: true },
    xAxis: { type: "value", axisLabel: { fontSize: 11 }, minInterval: 1 },
    yAxis: {
      type: "category",
      data: ranked.map((r) => r.name).reverse(),
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: "bar",
        data: ranked.map((r) => r.value).reverse(),
        itemStyle: { color: ACCENT_HEX },
      },
    ],
  };
}

const MAP_STYLE = { height: 360, width: "100%" } as const;
const MAP_STYLE_POINTER = {
  height: 360,
  width: "100%",
  cursor: "pointer",
} as const;
const MAP_OPTS = { renderer: "canvas" as const };

export const ProvinceMap = memo(function ProvinceMap({
  nameKey = "provincia",
  valueKey,
  data,
}: ProvinceMapProps) {
  const canvas = useCanvasWriteOptional();
  const brush = useCanvasBrush();
  const node = useCanvasNode();

  const ranked = useMemo(
    () =>
      data?.length && valueKey
        ? resolveRanked(nameKey, valueKey, data)
        : [],
    [nameKey, valueKey, data],
  );

  const brushName =
    brush?.tipo === "provincia" ? brush.valor : null;

  const option = useMemo(
    () => (ranked.length ? buildOption(ranked, brushName) : null),
    [ranked, brushName],
  );

  const onMapClick = useCallback(
    (params: Record<string, unknown>) => {
      if (!canvas) return;
      const name = params.name;
      const valor = typeof name === "string" ? name.trim() : "";
      if (!valor) return;
      const hit = ranked.find((r) => r.name === valor);
      const facts = hit
        ? [
            {
              label: "Cantidad",
              value: hit.value.toLocaleString("es-AR"),
            },
          ]
        : [];
      canvas.selectLocal({
        tipo: "provincia",
        valor,
        widget: "ProvinceMap",
        contexto: node?.title,
        facts,
      });
    },
    [canvas, node?.title, ranked],
  );

  const onEvents = useMemo(
    () => (canvas ? { click: onMapClick } : undefined),
    [canvas, onMapClick],
  );

  if (!option) {
    return (
      <div className="flex min-h-52 flex-col items-center justify-center gap-1 border-t border-rule px-4 py-6 text-center">
        <p className="text-xs text-muted-foreground/70 select-none">
          Sin totales por provincia para el mapa
        </p>
        <p className="max-w-sm text-[0.7rem] leading-snug text-muted-foreground/45 select-none">
          Hace falta un conteo numérico por provincia (o filas con provincia y
          voto). Pedí de nuevo el mapa o profundizá.
        </p>
      </div>
    );
  }

  return (
    <div className="border-t border-rule pt-4">
      <ResponsiveEChart
        option={option}
        style={canvas ? MAP_STYLE_POINTER : MAP_STYLE}
        notMerge
        lazyUpdate
        opts={MAP_OPTS}
        onEvents={onEvents}
      />
    </div>
  );
});
