/** Shared helpers for destination builders (no network). */

import type { UINode } from "../uitree";

export type SeriesRow = Record<string, unknown>;

export function monthsAgoIso(months: number): string {
  const d = new Date();
  d.setUTCMonth(d.getUTCMonth() - months);
  return d.toISOString().slice(0, 10);
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function asRows(payload: unknown): SeriesRow[] {
  if (!Array.isArray(payload)) return [];
  return payload.filter(
    (row): row is SeriesRow =>
      typeof row === "object" && row !== null && !Array.isArray(row),
  );
}

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

export function str(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return null;
}

export function filterDesde(rows: SeriesRow[], desde: string): SeriesRow[] {
  return rows.filter((row) => {
    const f = fechaKey(row);
    return f != null && f >= desde;
  });
}

export function destinationIdOf(tree: UINode | null | undefined): string | null {
  if (!tree) return null;
  const id = tree.props?.destinationId;
  return typeof id === "string" && id.trim() ? id.trim() : null;
}

/** Newest-first actas directory rows, capped. */
export function latestActas(rows: SeriesRow[], limit = 12): SeriesRow[] {
  return [...rows]
    .filter((row) => fechaKey(row) && str(row.titulo))
    .sort((a, b) => String(fechaKey(b)).localeCompare(String(fechaKey(a))))
    .slice(0, limit)
    .map((row) => ({
      actaId: row.actaId ?? row.id,
      titulo: str(row.titulo),
      fecha: fechaKey(row),
      resultado: str(row.resultado) ?? "—",
    }));
}

/** Prefer released films with some vote mass; cap for the landing List. */
export function polishDiscover(
  rows: SeriesRow[],
  today = todayIso(),
  limit = 16,
): SeriesRow[] {
  const scored = rows
    .map((row) => {
      const fecha = fechaKey(row);
      const titulo = str(row.titulo);
      if (!fecha || !titulo || fecha > today) return null;
      const votos = num(row.votos) ?? 0;
      const valor = num(row.valor);
      return {
        id: row.id,
        foto: str(row.foto) ?? undefined,
        titulo,
        valor: valor ?? undefined,
        fecha,
        votos,
      };
    })
    .filter((r): r is NonNullable<typeof r> => r != null)
    .sort((a, b) => {
      if (b.votos !== a.votos) return b.votos - a.votos;
      return (b.valor ?? 0) - (a.valor ?? 0);
    });
  return scored.slice(0, limit).map(({ votos: _v, ...rest }) => rest);
}
