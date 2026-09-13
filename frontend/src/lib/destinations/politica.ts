/**
 * Destino Política — fixed UI tree loaded via /api/data (no LLM turn).
 */

import { fetchData } from "@/lib/data-api";
import type { UINode } from "@/lib/uitree";
import {
  asRows,
  fechaKey,
  filterDesde,
  latestActas,
  monthsAgoIso,
  num,
  str,
  type SeriesRow,
} from "./shared";

export { latestActas } from "./shared";

export const POLITICA_QUERY = "Política";
export const POLITICA_DESTINATION_ID = "politica";

export const POLITICA_FOLLOW_UPS = [
  "En la modernización laboral del Senado, ¿cómo se partió el voto por bloque parlamentario?",
  "En la modernización laboral del Senado, ¿qué provincias inclinaron más al negativo?",
  "Mostrame quiénes votaron en contra en la modernización laboral, con bloque y provincia",
  "Poné confianza en el gobierno y riesgo país en la misma línea de tiempo para 2026",
] as const;

function icgMetrics(rows: SeriesRow[]): {
  last: number;
  delta: number | null;
} | null {
  const sorted = [...rows]
    .map((row) => ({
      fecha: fechaKey(row),
      valor: num(row.valor),
      variacion: num(row.variacion),
    }))
    .filter(
      (r): r is { fecha: string; valor: number; variacion: number | null } =>
        r.fecha != null && r.valor != null,
    )
    .sort((a, b) => a.fecha.localeCompare(b.fecha));
  if (!sorted.length) return null;
  const last = sorted[sorted.length - 1]!;
  const delta =
    last.variacion != null
      ? last.variacion
      : sorted.length >= 2
        ? last.valor - sorted[sorted.length - 2]!.valor
        : null;
  return { last: last.valor, delta };
}

function formatIcg(n: number): string {
  return n.toLocaleString("es-AR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

/**
 * Fetch ICG, Senado actas, modernización laboral votos → Política stack.
 */
export async function buildPoliticaTree(): Promise<UINode> {
  const desde = monthsAgoIso(18);

  const [icgRaw, actasRaw, heroRaw] = await Promise.all([
    fetchData("/v1/politica/indices/confianza-gobierno", { desde }),
    fetchData("/v1/senado/actas", {
      desde: "2025-01-01",
      fields: "actaId,titulo,fecha,resultado",
    }),
    fetchData("/v1/senado/actas", {
      title: "modernización laboral",
      fields: "actaId,titulo,fecha,resultado",
    }),
  ]);

  const icgRows = filterDesde(asRows(icgRaw), desde)
    .map((row) => ({
      fecha: fechaKey(row),
      valor: num(row.valor),
      variacion: num(row.variacion),
    }))
    .filter(
      (r): r is { fecha: string; valor: number; variacion: number | null } =>
        r.fecha != null && r.valor != null,
    );
  const icgChart = icgRows.map(({ fecha, valor }) => ({ fecha, valor }));
  const icg = icgMetrics(asRows(icgRaw));
  const actas = latestActas(asRows(actasRaw), 12);

  const hero = asRows(heroRaw)[0];
  const actaId = hero ? str(hero.actaId ?? hero.id) : null;
  const heroTitle = hero ? str(hero.titulo) : null;

  let votos: SeriesRow[] = [];
  if (actaId) {
    votos = asRows(
      await fetchData("/v1/senado/actas/id/{actaId}/votos", {
        actaId,
        fields: "nombre,voto",
      }),
    );
  }

  const delta = icg?.delta ?? null;
  const metricItems = [
    {
      label: "Confianza (ICG)",
      value: icg ? formatIcg(icg.last) : "—",
      unit: "pts",
      ...(delta != null
        ? {
            delta: Math.round(delta * 100) / 100,
            trend:
              delta > 0
                ? ("up" as const)
                : delta < 0
                  ? ("down" as const)
                  : ("flat" as const),
          }
        : {}),
    },
    {
      label: "Δ mensual",
      value:
        delta != null
          ? `${delta > 0 ? "+" : ""}${formatIcg(delta)}`
          : "—",
      unit: "pts",
    },
  ];

  const children: UINode[] = [
    {
      id: "politica-icg",
      type: "Chart",
      title: "Confianza en el gobierno",
      props: {
        kind: "line",
        xKey: "fecha",
        selectAs: "fecha",
        series: [{ key: "valor", label: "ICG", color: "var(--accent)" }],
        data: icgChart,
      },
    },
    {
      id: "politica-icg-metrics",
      type: "MetricRow",
      title: "ICG hoy",
      props: { items: metricItems },
    },
    {
      id: "politica-actas",
      type: "List",
      title: "Últimas votaciones del Senado",
      props: {
        columns: [
          { key: "fecha", label: "Fecha", kind: "date" },
          { key: "titulo", label: "Título" },
          { key: "resultado", label: "Resultado" },
        ],
        data: actas,
      },
    },
  ];

  if (votos.length > 0) {
    children.push({
      id: "politica-laboral",
      type: "VoteBreakdown",
      title: heroTitle
        ? `Votos — ${heroTitle.slice(0, 72)}${heroTitle.length > 72 ? "…" : ""}`
        : "Modernización laboral — Senado",
      props: {
        voteKey: "voto",
        kind: "donut",
        data: votos,
      },
    });
  }

  return {
    id: "destino-politica",
    type: "Stack",
    title: POLITICA_QUERY,
    props: { gap: "md", destinationId: POLITICA_DESTINATION_ID },
    children,
  };
}

export function isPoliticaDestination(tree: UINode | null | undefined): boolean {
  if (!tree) return false;
  if (tree.title === POLITICA_QUERY) return true;
  return tree.props?.destinationId === POLITICA_DESTINATION_ID;
}
