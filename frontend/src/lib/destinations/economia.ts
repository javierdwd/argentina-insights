/**
 * Destino Economía — fixed UI tree loaded via /api/data (no LLM turn).
 *
 * Macro snapshot (FX / inflación / riesgo) plus a light "estratega" block:
 * top plazos fijos and hipotecarios UVA.
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
import { asRows, filterDesde, monthsAgoIso, str } from "./shared";

export {
  alignBlueOficial,
  ECONOMIA_DESTINATION_ID,
  ECONOMIA_QUERY,
  isEconomiaDestination,
} from "./economia-shared";

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

function formatPct(n: number): string {
  return (Math.round(n * 10) / 10).toLocaleString("es-AR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

type PlazoRow = { entidad: string; tna: number; plazoDias?: number };
type HipotecarioRow = {
  entidad: string;
  tna: number;
  plazoMaxAnios?: number;
  financiamiento?: string;
};

function polishPlazos(rows: SeriesRow[], limit = 8): PlazoRow[] {
  const out: PlazoRow[] = [];
  for (const row of rows) {
    const entidad = str(row.entidad);
    const tna = num(row.tna) ?? num(row.valor);
    if (!entidad || tna == null) continue;
    const plazoDias = num(row.plazoDias);
    out.push({
      entidad,
      tna,
      ...(plazoDias != null ? { plazoDias } : {}),
    });
  }
  return out.sort((a, b) => b.tna - a.tna).slice(0, limit);
}

function polishHipotecarios(rows: SeriesRow[], limit = 8): HipotecarioRow[] {
  const out: HipotecarioRow[] = [];
  for (const row of rows) {
    const entidad = str(row.entidad);
    const tna = num(row.tna) ?? num(row.valor);
    if (!entidad || tna == null) continue;
    const plazoMaxAnios = num(row.plazoMaxAnios);
    const financiamiento = str(row.financiamiento);
    out.push({
      entidad,
      tna,
      ...(plazoMaxAnios != null ? { plazoMaxAnios } : {}),
      ...(financiamiento ? { financiamiento } : {}),
    });
  }
  return out.sort((a, b) => a.tna - b.tna).slice(0, limit);
}

function latestInflacion(rows: SeriesRow[]): number | null {
  const sorted = [...rows]
    .map((row) => ({ fecha: fechaKey(row), valor: num(row.valor) }))
    .filter(
      (r): r is { fecha: string; valor: number } =>
        r.fecha != null && r.valor != null,
    )
    .sort((a, b) => a.fecha.localeCompare(b.fecha));
  return sorted.length ? sorted[sorted.length - 1]!.valor : null;
}

/**
 * Fetch blue, oficial, inflación, riesgo, plazos and hipotecarios;
 * build the fixed Economía stack.
 */
export async function buildEconomiaTree(): Promise<UINode> {
  const desde = monthsAgoIso(18);

  const [
    blueRaw,
    oficialRaw,
    inflacionRaw,
    inflacionIaRaw,
    riesgoRaw,
    plazosRaw,
    hipotecariosRaw,
  ] = await Promise.all([
    fetchData("/v1/cotizaciones/dolares/{casa}", { casa: "blue", desde }),
    fetchData("/v1/cotizaciones/dolares/{casa}", { casa: "oficial", desde }),
    fetchData("/v1/finanzas/indices/inflacion", { desde }),
    fetchData("/v1/finanzas/indices/inflacionInteranual", { desde }),
    fetchData("/v1/finanzas/indices/riesgo-pais", { desde }),
    fetchData("/v1/plazos/ranking", { limit: "12" }),
    fetchData("/v1/hipotecarios-uva", {}),
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
  const plazos = polishPlazos(asRows(plazosRaw));
  const hipotecarios = polishHipotecarios(asRows(hipotecariosRaw));
  const topTna = plazos[0]?.tna ?? null;
  const lastInfIa = latestInflacion(filterDesde(asRows(inflacionIaRaw), desde));
  const realSpread =
    topTna != null && lastInfIa != null ? topTna - lastInfIa : null;

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
    {
      label: "Mejor plazo fijo",
      value: topTna != null ? formatPct(topTna) : "—",
      unit: "% TNA",
    },
    {
      label: "Vs infl. interanual",
      value:
        realSpread != null
          ? `${realSpread > 0 ? "+" : ""}${formatPct(realSpread)}`
          : "—",
      unit: "pp",
    },
  ];

  const children: UINode[] = [
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
      title: "Macro y tasas",
      props: {
        items: metricItems,
      },
    },
  ];

  if (plazos.length) {
    children.push({
      id: "economia-plazos",
      type: "ComparisonTable",
      title: "Plazos fijos — mejores TNA",
      props: {
        primaryKey: "entidad",
        columns: [
          { key: "entidad", label: "Banco" },
          { key: "tna", label: "TNA", kind: "percent" },
          { key: "plazoDias", label: "Plazo (días)", kind: "number" },
        ],
        highlight: { key: "tna", direction: "max" },
        data: plazos,
      },
    });
  }

  if (hipotecarios.length) {
    children.push({
      id: "economia-hipotecarios",
      type: "ComparisonTable",
      title: "Hipotecarios UVA — TNA más bajas",
      props: {
        primaryKey: "entidad",
        columns: [
          { key: "entidad", label: "Banco" },
          { key: "tna", label: "TNA", kind: "percent" },
          { key: "plazoMaxAnios", label: "Plazo máx.", kind: "number" },
          { key: "financiamiento", label: "Financiamiento" },
        ],
        highlight: { key: "tna", direction: "min" },
        data: hipotecarios,
      },
    });
  }

  return {
    id: "destino-economia",
    type: "Stack",
    title: ECONOMIA_QUERY,
    props: { gap: "md", destinationId: ECONOMIA_DESTINATION_ID },
    children,
  };
}
