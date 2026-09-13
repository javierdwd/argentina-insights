/**
 * Destino Cine — fixed UI tree loaded via /api/data (no LLM turn).
 */

import { fetchData } from "@/lib/data-api";
import type { UINode } from "@/lib/uitree";
import {
  asRows,
  fechaKey,
  num,
  polishDiscover,
  str,
  type SeriesRow,
} from "./shared";

export { polishDiscover } from "./shared";

export const CINE_QUERY = "Cine";
export const CINE_DESTINATION_ID = "cine";

export const CINE_FOLLOW_UPS = [
  "Películas argentinas de drama de los últimos años, ordenadas por rating",
  "Ficha de Nueve reinas: sinopsis, rating y elenco",
  "Filmografía argentina de Ricardo Darín",
  "Quién es Lucrecia Martel y qué películas argentinas dirigió",
] as const;

const SPOTLIGHT_Q = "Relatos salvajes";

function formatRating(n: number): string {
  return n.toLocaleString("es-AR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function mapElenco(detail: SeriesRow): Array<{
  name: string;
  photoUrl?: string;
  role?: string;
}> {
  const raw = detail.elenco;
  if (!Array.isArray(raw)) return [];
  const people: Array<{ name: string; photoUrl?: string; role?: string }> = [];
  for (const item of raw) {
    if (typeof item !== "object" || item === null || Array.isArray(item)) {
      continue;
    }
    const row = item as SeriesRow;
    const name = str(row.name) ?? str(row.nombre);
    if (!name) continue;
    people.push({
      name,
      photoUrl: str(row.photoUrl) ?? str(row.foto) ?? undefined,
      role: str(row.role) ?? str(row.cargo) ?? undefined,
    });
  }
  return people.slice(0, 12);
}

/**
 * Fetch discover + Relatos salvajes spotlight → Cine stack.
 */
export async function buildCineTree(): Promise<UINode> {
  const [discoverRaw, searchRaw] = await Promise.all([
    fetchData("/v1/cine/discover", {}),
    fetchData("/v1/cine/search", { q: SPOTLIGHT_Q }),
  ]);

  const films = polishDiscover(asRows(discoverRaw));
  const hit = asRows(searchRaw)[0];
  const filmId = hit ? str(hit.id) : null;

  let detail: SeriesRow | null = null;
  if (filmId) {
    const payload = await fetchData("/v1/cine/pelicula/{id}", { id: filmId });
    if (payload && typeof payload === "object" && !Array.isArray(payload)) {
      detail = payload as SeriesRow;
    }
  }

  const rating = detail ? num(detail.valor) : null;
  const year = detail ? (fechaKey(detail)?.slice(0, 4) ?? null) : null;
  const runtime = detail ? num(detail.runtime) : null;
  const votos = detail ? num(detail.votos) : null;
  const spotlightTitle = detail
    ? (str(detail.titulo) ?? SPOTLIGHT_Q)
    : SPOTLIGHT_Q;

  const metricItems = [
    {
      label: "Rating",
      value: rating != null ? formatRating(rating) : "—",
      unit: "/10",
    },
    {
      label: "Estreno",
      value: year ?? "—",
    },
    {
      label: "Duración",
      value: runtime != null ? String(Math.round(runtime)) : "—",
      unit: "min",
    },
    {
      label: "Votos",
      value:
        votos != null
          ? Math.round(votos).toLocaleString("es-AR")
          : "—",
    },
  ];

  const elenco = detail ? mapElenco(detail) : [];

  const children: UINode[] = [
    {
      id: "cine-discover",
      type: "List",
      title: "Películas argentinas populares",
      props: {
        columns: [
          { key: "foto", label: "Póster", kind: "image" },
          { key: "titulo", label: "Título" },
          { key: "valor", label: "Rating", kind: "number" },
          { key: "fecha", label: "Estreno", kind: "date" },
        ],
        data: films,
      },
    },
  ];

  if (detail) {
    children.push({
      id: "cine-spotlight-metrics",
      type: "MetricRow",
      title: spotlightTitle,
      props: { items: metricItems },
    });
  }

  if (elenco.length > 0) {
    children.push({
      id: "cine-spotlight-cast",
      type: "PersonCard",
      title: "Elenco",
      props: {
        layout: "list",
        people: elenco,
      },
    });
  }

  return {
    id: "destino-cine",
    type: "Stack",
    title: CINE_QUERY,
    props: { gap: "md", destinationId: CINE_DESTINATION_ID },
    children,
  };
}

export function isCineDestination(tree: UINode | null | undefined): boolean {
  if (!tree) return false;
  if (tree.title === CINE_QUERY) return true;
  return tree.props?.destinationId === CINE_DESTINATION_ID;
}
