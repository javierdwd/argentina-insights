import { formatNumber } from "@/lib/format";
import {
  normalizeProvinceName,
  PROVINCE_CENTROIDS,
} from "@/components/registry/geo/provinces";

/** Selection kinds the inspector + Profundizar already understand. */
export const CANVAS_TIPOS = ["fecha", "persona", "provincia", "fila"] as const;
export type CanvasTipo = (typeof CANVAS_TIPOS)[number];

const ISO_DAY = /^\d{4}-\d{2}-\d{2}/;

const PERSON_CATEGORY_KEYS = new Set([
  "nombre",
  "name",
  "persona",
  "presidente",
  "diputado",
  "senador",
  "legislador",
  "apellido",
]);

const PERSON_ATTR_KEYS = new Set([
  "partido",
  "bloque",
  "apellido",
  "email",
  "telefono",
]);

const NAME_PARTICLES = new Set([
  "de",
  "del",
  "la",
  "las",
  "los",
  "y",
  "da",
  "do",
  "von",
  "van",
  "di",
]);

const SKIP_FACT_KEYS = new Set([
  "entity",
  "imagen",
  "foto",
  "photoUrl",
  "image",
  "url",
  "links",
  "redes",
  "id",
]);

const FACT_LABELS: Record<string, string> = {
  value: "Valor",
  sublabel: "Período",
  partido: "Partido",
  bloque: "Bloque",
  delta: "Variación",
  periodoPresidencial: "Mandato",
  provincia: "Provincia",
  role: "Rol",
  cargo: "Cargo",
  titulo: "Título",
  title: "Título",
  valor: "Rating",
  votos: "Votos",
  popularidad: "Popularidad",
  runtime: "Duración",
};

export function isCanvasTipo(value: unknown): value is CanvasTipo {
  return (
    value === "fecha" ||
    value === "persona" ||
    value === "provincia" ||
    value === "fila"
  );
}

/** Exact province match — fuzzy centroid lookup is too loose for labels. */
export function isProvinceName(name: string): boolean {
  return Boolean(PROVINCE_CENTROIDS[normalizeProvinceName(name)]);
}

export function looksLikePersonName(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > 80) return false;
  if (ISO_DAY.test(trimmed)) return false;
  if (/[→\d%/@]/.test(trimmed)) return false;
  const words = trimmed.split(/\s+/);
  if (words.length < 2 || words.length > 7) return false;
  let capped = 0;
  for (const word of words) {
    if (NAME_PARTICLES.has(word.toLowerCase())) continue;
    if (!/^[\p{L}'’.+-]+$/u.test(word)) return false;
    const first = word[0];
    if (
      first &&
      first === first.toUpperCase() &&
      first !== first.toLowerCase()
    ) {
      capped += 1;
    }
  }
  return capped >= 2;
}

function rowHasPersonAttrs(row: Record<string, unknown> | undefined): boolean {
  if (!row) return false;
  for (const key of PERSON_ATTR_KEYS) {
    const raw = row[key];
    if (raw === null || raw === undefined || raw === "") continue;
    return true;
  }
  return false;
}

/**
 * Classify a clicked category without widget-specific (president, etc.) code.
 *
 * Priority: explicit selectAs → row.entity → date → column key → province
 * name → person-like attrs/name → fila.
 */
export function inferCanvasTipo(input: {
  valor: string;
  row?: Record<string, unknown>;
  categoryKey?: string;
  selectAs?: CanvasTipo;
}): CanvasTipo {
  if (input.selectAs) return input.selectAs;
  if (isCanvasTipo(input.row?.entity)) return input.row.entity;

  const valor = input.valor.trim();
  if (!valor) return "fila";
  if (ISO_DAY.test(valor)) return "fecha";
  // Poster / CDN URLs must never become "persona" (Profundizar used to send them).
  if (/^https?:\/\//i.test(valor)) return "fila";

  const key = (input.categoryKey ?? "").trim().toLowerCase();
  if (key === "provincia" || key === "province") return "provincia";
  if (PERSON_CATEGORY_KEYS.has(key)) return "persona";
  if (key === "titulo" || key === "title" || key === "pelicula") return "fila";

  if (isProvinceName(valor)) return "provincia";
  if (rowHasPersonAttrs(input.row)) return "persona";
  if (looksLikePersonName(valor)) return "persona";
  return "fila";
}

/** Inspector rows from a category/period data row (skip ids, photos, entity). */
export function factsFromCategoryRow(
  row: Record<string, unknown> | undefined,
  opts?: {
    skip?: Iterable<string>;
    labels?: Record<string, string>;
  },
): { label: string; value: string }[] {
  if (!row) return [];
  const skip = new Set([...(opts?.skip ?? []), ...SKIP_FACT_KEYS]);
  const labels = opts?.labels ?? {};
  const out: { label: string; value: string }[] = [];
  for (const [key, raw] of Object.entries(row)) {
    if (skip.has(key)) continue;
    if (raw === null || raw === undefined || raw === "") continue;
    if (typeof raw === "object") continue;
    const n =
      typeof raw === "number"
        ? raw
        : typeof raw === "string" && raw.trim() !== ""
          ? Number(raw)
          : NaN;
    const looksIso = typeof raw === "string" && ISO_DAY.test(raw);
    const value =
      Number.isFinite(n) && !looksIso ? formatNumber(n) : String(raw);
    out.push({
      label: labels[key] || FACT_LABELS[key] || key,
      value,
    });
  }
  return out;
}
