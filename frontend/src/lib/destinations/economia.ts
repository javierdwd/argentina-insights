/**
 * Destino Economía — fixed UI tree loaded via /api/data (no LLM turn).
 */

import { fetchData } from "@/lib/data-api";
import type { UINode } from "@/lib/uitree";
import {
  alignBlueOficial,
  ECONOMIA_DESTINATION_ID,
  ECONOMIA_QUERY,
  fechaKey,
  num,
  type SeriesRow,
} from "./economia-shared";

export {
  alignBlueOficial,
  ECONOMIA_DESTINATION_ID,
  ECONOMIA_QUERY,
  isEconomiaDestination,
} from "./economia-shared";

function monthsAgoIso(months: number): string {
  const d = new Date();
  d.setUTCMonth(d.getUTCMonth() - months);
  return d.toISOString().slice(0, 10);
}

function asRows(payload: unknown): SeriesRow[] {
  if (!Array.isArray(payload)) return [];
  return payload.filter(
    (row): row is SeriesRow =>
      typeof row === "object" && row !== null && !Array.isArray(row),
  );
}

function filterDesde(rows: SeriesRow[], desde: string): SeriesRow[] {
  return rows.filter((row) => {
    const f = fechaKey(row);
    return f != null && f >= desde;
  });
}

function riesgoMetrics(rows: SeriesRow[]): {
  last: number;
  delta30: number | null;
} | null {
  const sorted = [...rows]
    .map((row) => ({ fecha: fechaKey(row), valor: num(row.valor) }))
    .filter(
      (r): r is { fecha: string; valor: number } =>
        r.fecha != null && r.valor != null,
    )
    .sort((a, b) => a.fecha.localeCompare(b.fecha));
  if (!sorted.length) return null;
  const last = sorted[sorted.length - 1]!;
  const targetMs = Date.parse(last.fecha) - 30 * 24 * 60 * 60 * 1000;
  let best: { fecha: string; valor: number } | null = null;
  let bestDist = Infinity;
  for (const row of sorted.slice(0, -1)) {
    const dist = Math.abs(Date.parse(row.fecha) - targetMs);
    if (dist < bestDist) {
      bestDist = dist;
      best = row;
    }
  }
  if (!best || bestDist > 45 * 24 * 60 * 60 * 1000) {
    return { last: last.valor, delta30: null };
  }
  return {
    last: last.valor,
    delta30: last.valor - best.valor,
  };
}

function formatPts(n: number): string {
  return Math.round(n).toLocaleString("es-AR");
}

/**
 * Fetch blue, oficial, inflación, riesgo and build the fixed Economía stack.
 */
export async function buildEconomiaTree(): Promise<UINode> {
  const desde = monthsAgoIso(18);

  const [blueRaw, oficialRaw, inflacionRaw, riesgoRaw] = await Promise.all([
    fetchData("/v1/cotizaciones/dolares/{casa}", { casa: "blue", desde }),
    fetchData("/v1/cotizaciones/dolares/{casa}", { casa: "oficial", desde }),
    fetchData("/v1/finanzas/indices/inflacion", { desde }),
    fetchData("/v1/finanzas/indices/riesgo-pais", { desde }),
  ]);

  const fx = alignBlueOficial(asRows(blueRaw), asRows(oficialRaw));
  const inflacion = filterDesde(asRows(inflacionRaw), desde)
    .map((row) => ({
      fecha: fechaKey(row),
      valor: num(row.valor),
    }))
    .filter(
      (r): r is { fecha: string; valor: number } =>
        r.fecha != null && r.valor != null,
    );
  const riesgo = filterDesde(asRows(riesgoRaw), desde);
  const rp = riesgoMetrics(riesgo);
  const delta30 = rp?.delta30 ?? null;

  const metricItems = [
    {
      label: "Riesgo país",
      value: rp ? formatPts(rp.last) : "—",
      unit: "pts",
      ...(delta30 != null
        ? {
            delta: Math.round(delta30 * 10) / 10,
            trend:
              delta30 > 0
                ? ("up" as const)
                : delta30 < 0
                  ? ("down" as const)
                  : ("flat" as const),
          }
        : {}),
    },
    {
      label: "Δ ~30 días",
      value:
        delta30 != null
          ? `${delta30 > 0 ? "+" : ""}${formatPts(delta30)}`
          : "—",
      unit: "pts",
    },
  ];

  return {
    id: "destino-economia",
    type: "Stack",
    title: ECONOMIA_QUERY,
    props: { gap: "md", destinationId: ECONOMIA_DESTINATION_ID },
    children: [
      {
        id: "economia-fx",
        type: "Chart",
        title: "Dólar blue vs oficial",
        props: {
          kind: "line",
          xKey: "fecha",
          selectAs: "fecha",
          series: [
            { key: "blue", label: "Blue", color: "var(--sky)" },
            { key: "oficial", label: "Oficial", color: "var(--accent)" },
          ],
          data: fx,
        },
      },
      {
        id: "economia-inflacion",
        type: "Chart",
        title: "Inflación mensual",
        props: {
          kind: "line",
          xKey: "fecha",
          selectAs: "fecha",
          series: [
            { key: "valor", label: "Inflación %", color: "var(--accent)" },
          ],
          data: inflacion,
        },
      },
      {
        id: "economia-riesgo",
        type: "MetricRow",
        title: "Riesgo país",
        props: {
          items: metricItems,
        },
      },
    ],
  };
}
