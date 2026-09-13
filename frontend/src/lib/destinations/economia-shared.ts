/** Pure helpers for the Economía destination (no network). */

import type { UINode } from "../uitree";

export const ECONOMIA_QUERY = "Economía";
export const ECONOMIA_DESTINATION_ID = "economia";

export type SeriesRow = Record<string, unknown>;

export function fechaKey(row: SeriesRow): string | null {
  const raw = row.fecha;
  if (typeof raw !== "string" || !raw.trim()) return null;
  return raw.slice(0, 10);
}

export function num(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** Align blue + oficial venta by fecha for a dual-series chart. */
export function alignBlueOficial(
  blue: SeriesRow[],
  oficial: SeriesRow[],
): SeriesRow[] {
  const ofic = new Map<string, number>();
  for (const row of oficial) {
    const f = fechaKey(row);
    const v = num(row.venta);
    if (f && v != null) ofic.set(f, v);
  }
  const out: SeriesRow[] = [];
  for (const row of blue) {
    const f = fechaKey(row);
    const b = num(row.venta);
    if (!f || b == null) continue;
    const o = ofic.get(f);
    if (o == null) continue;
    out.push({ fecha: f, blue: b, oficial: o });
  }
  out.sort((a, b) => String(a.fecha).localeCompare(String(b.fecha)));
  return out;
}

export function isEconomiaDestination(tree: UINode | null | undefined): boolean {
  if (!tree) return false;
  if (tree.title === ECONOMIA_QUERY) return true;
  const id = tree.props?.destinationId;
  return id === ECONOMIA_DESTINATION_ID;
}
