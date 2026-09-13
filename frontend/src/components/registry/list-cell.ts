/** Cell kinds a List column can declare — or that we infer from keys/values. */
export const LIST_CELL_KINDS = ["text", "image", "date", "url", "number"] as const;
export type ListCellKind = (typeof LIST_CELL_KINDS)[number];

const IMAGE_KEYS = new Set([
  "imagen",
  "image",
  "foto",
  "photo",
  "photourl",
  "thumbnail",
  "thumb",
  "avatar",
  "picture",
  "retrato",
]);

const NAME_KEYS = new Set([
  "nombre",
  "name",
  "persona",
  "apellido",
  "diputado",
  "senador",
  "legislador",
]);

/** Row labels for selection / photo fold — people OR titled records (films). */
const LABEL_KEYS = new Set([
  ...NAME_KEYS,
  "titulo",
  "title",
  "pelicula",
  "film",
  "movie",
]);

const IMAGE_EXT = /\.(avif|bmp|gif|jpe?g|png|svg|webp)(\?|#|$)/i;

export function looksLikeImageUrl(value: unknown): boolean {
  if (typeof value !== "string") return false;
  const trimmed = value.trim();
  if (!/^https?:\/\//i.test(trimmed)) return false;
  try {
    const path = new URL(trimmed).pathname;
    return IMAGE_EXT.test(path);
  } catch {
    return false;
  }
}

export function looksLikeHttpUrl(value: unknown): boolean {
  if (typeof value !== "string") return false;
  return /^https?:\/\/\S+$/i.test(value.trim());
}

function keyNorm(key: string): string {
  return key.trim().toLowerCase().replace(/[\s_-]+/g, "");
}

function sampleValues(
  data: Record<string, unknown>[] | undefined,
  key: string,
  limit = 8,
): unknown[] {
  if (!data?.length) return [];
  const out: unknown[] = [];
  for (const row of data) {
    const raw = row[key];
    if (raw === null || raw === undefined || raw === "") continue;
    out.push(raw);
    if (out.length >= limit) break;
  }
  return out;
}

/**
 * Resolve a column's cell kind. Explicit `kind` wins; otherwise key names
 * (imagen/foto/…) and the shape of values (`.jpg` URLs) — not a specific API.
 */
export function inferColumnKind(
  column: { key: string; kind?: ListCellKind },
  data?: Record<string, unknown>[],
): ListCellKind {
  if (column.kind) return column.kind;
  const key = keyNorm(column.key);
  if (IMAGE_KEYS.has(key) || (key.endsWith("url") && IMAGE_KEYS.has(key.replace(/url$/, "")))) {
    return "image";
  }
  const samples = sampleValues(data, column.key);
  if (samples.length > 0 && samples.every(looksLikeImageUrl)) return "image";
  if (samples.length > 0 && samples.every(looksLikeHttpUrl)) return "url";
  return "text";
}

export function isNameColumnKey(key: string): boolean {
  return NAME_KEYS.has(keyNorm(key));
}

/** Name or title column — used to fold posters and pick a selection lead. */
export function isLabelColumnKey(key: string): boolean {
  return LABEL_KEYS.has(keyNorm(key));
}

/** Generic image header (the raw key) — hide it; the thumbnail is the label. */
export function isGenericImageLabel(label: string, key: string): boolean {
  const n = label.trim().toLowerCase();
  const k = key.trim().toLowerCase();
  if (n === k) return true;
  return IMAGE_KEYS.has(keyNorm(label));
}

/**
 * If the table has a photo column and a name/title column, fold the photo into
 * that cell and drop the URL column so it does not render as truncated text.
 */
export function foldImageColumns<T extends { key: string; kind?: ListCellKind }>(
  columns: T[],
  data?: Record<string, unknown>[],
): { columns: T[]; imageKey: string | null; nameKey: string | null } {
  const kinds = columns.map((col) => inferColumnKind(col, data));
  const imageIdx = kinds.findIndex((kind) => kind === "image");
  const labelIdx = columns.findIndex((col) => isLabelColumnKey(col.key));
  if (imageIdx < 0) {
    return {
      columns,
      imageKey: null,
      nameKey: labelIdx >= 0 ? columns[labelIdx].key : null,
    };
  }
  const imageKey = columns[imageIdx].key;
  if (labelIdx < 0) {
    return { columns, imageKey, nameKey: null };
  }
  return {
    columns: columns.filter((_, i) => i !== imageIdx),
    imageKey,
    nameKey: columns[labelIdx].key,
  };
}

/**
 * Prefer a human label (titulo/nombre/…) over image URLs for canvas selection.
 */
export function pickListSelectionLead(
  row: Record<string, unknown>,
  columns: { key: string; kind?: ListCellKind }[],
  data?: Record<string, unknown>[],
  format: (value: unknown) => string = (v) =>
    v == null || v === "" ? "" : String(v),
): { key: string; valor: string; imageUrl?: string } | null {
  const folded = foldImageColumns(columns, data);
  const preferred = [
    folded.nameKey,
    ...folded.columns.map((col) => col.key),
  ].filter((key): key is string => Boolean(key));

  let leadKey: string | null = null;
  let valor = "";
  for (const key of preferred) {
    if (inferColumnKind({ key }, data) === "image") continue;
    const formatted = format(row[key]).trim();
    if (!formatted || formatted === "—") continue;
    if (looksLikeImageUrl(formatted) || looksLikeHttpUrl(formatted)) continue;
    leadKey = key;
    valor = formatted;
    break;
  }
  if (!leadKey || !valor) return null;

  const rawImage = folded.imageKey ? row[folded.imageKey] : undefined;
  const imageUrl =
    typeof rawImage === "string" &&
    (looksLikeImageUrl(rawImage) || looksLikeHttpUrl(rawImage))
      ? rawImage.trim()
      : undefined;

  return { key: leadKey, valor, imageUrl };
}
