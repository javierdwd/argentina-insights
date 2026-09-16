import { fetchData } from "@/lib/data-api";
import {
  alignBlueOficial,
  fechaKey,
  num,
  type SeriesRow,
} from "@/lib/destinations/economia-shared";
import { asRows, monthsAgoIso } from "@/lib/destinations/shared";
import type { UINode } from "@/lib/uitree";

export type EntryPreviewKind = "fx" | "inflacion" | "riesgo";

const previewCache = new Map<EntryPreviewKind, Promise<UINode>>();

function chartRows(raw: unknown): SeriesRow[] {
  return asRows(raw)
    .map((row) => ({ fecha: fechaKey(row), valor: num(row.valor) }))
    .filter(
      (row): row is { fecha: string; valor: number } =>
        row.fecha != null && row.valor != null,
    );
}

async function buildPreview(kind: EntryPreviewKind): Promise<UINode> {
  const desde = monthsAgoIso(kind === "fx" ? 6 : 12);
  if (kind === "fx") {
    const [blueRaw, oficialRaw] = await Promise.all([
      fetchData("/v1/cotizaciones/dolares/{casa}", { casa: "blue", desde }),
      fetchData("/v1/cotizaciones/dolares/{casa}", { casa: "oficial", desde }),
    ]);
    return {
      id: "entrada_fx_preview",
      type: "Chart",
      title: "Blue y oficial, últimos 6 meses",
      props: {
        kind: "line",
        xKey: "fecha",
        selectAs: "fecha",
        series: [
          { key: "blue", label: "Blue", color: "var(--sky)" },
          { key: "oficial", label: "Oficial", color: "var(--accent)" },
        ],
        data: alignBlueOficial(asRows(blueRaw), asRows(oficialRaw)),
      },
    };
  }

  const endpoint =
    kind === "inflacion"
      ? "/v1/finanzas/indices/inflacion"
      : "/v1/finanzas/indices/riesgo-pais";
  const raw = await fetchData(endpoint, { desde });
  const inflation = kind === "inflacion";
  return {
    id: `entrada_${kind}_preview`,
    type: "Chart",
    title: inflation ? "Inflación mensual, último año" : "Riesgo país, último año",
    props: {
      kind: inflation ? "bar" : "line",
      xKey: "fecha",
      selectAs: "fecha",
      series: [
        {
          key: "valor",
          label: inflation ? "Inflación %" : "Riesgo país",
          color: inflation ? "var(--accent)" : "var(--sky)",
        },
      ],
      data: chartRows(raw),
    },
  };
}

/** Live preview with in-memory request de-duplication and a bounded wait. */
export function loadEntryPreview(kind: EntryPreviewKind): Promise<UINode> {
  const cached = previewCache.get(kind);
  if (cached) return cached;

  const request = Promise.race([
    buildPreview(kind),
    new Promise<never>((_, reject) => {
      window.setTimeout(() => reject(new Error("Preview timed out")), 9000);
    }),
  ]).catch((error) => {
    previewCache.delete(kind);
    throw error;
  });
  previewCache.set(kind, request);
  return request;
}
