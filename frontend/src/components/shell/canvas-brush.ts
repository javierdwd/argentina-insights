/**
 * Cross-widget brush helpers — match a canvas selection against row fields.
 */

import type { CanvasTipo } from "@/components/shell/infer-canvas-tipo";

export type CanvasBrush = {
  tipo: CanvasTipo;
  valor: string;
};

const ISO_PREFIX = /^\d{4}-\d{2}-\d{2}/;

export function normalizeBrushText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .trim();
}

export function isoDayPrefix(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  const match = ISO_PREFIX.exec(text);
  return match ? match[0] : null;
}

function rowFieldTexts(row: Record<string, unknown>): string[] {
  const out: string[] = [];
  for (const value of Object.values(row)) {
    if (value === null || value === undefined || value === "") continue;
    if (typeof value === "string" || typeof value === "number") {
      out.push(String(value));
    }
  }
  return out;
}

/** True when this row should highlight under the current brush. */
export function rowMatchesBrush(
  row: Record<string, unknown> | undefined,
  brush: CanvasBrush | null | undefined,
  opts?: { categoryKey?: string },
): boolean {
  if (!row || !brush?.valor) return false;
  const needle = normalizeBrushText(brush.valor);
  if (!needle) return false;

  if (brush.tipo === "fecha") {
    const target = isoDayPrefix(brush.valor);
    if (!target) return false;
    if (opts?.categoryKey) {
      const day = isoDayPrefix(row[opts.categoryKey]);
      if (day === target) return true;
    }
    return rowFieldTexts(row).some((text) => isoDayPrefix(text) === target);
  }

  if (brush.tipo === "provincia" || brush.tipo === "persona") {
    if (opts?.categoryKey) {
      const cell = row[opts.categoryKey];
      if (
        typeof cell === "string" &&
        normalizeBrushText(cell) === needle
      ) {
        return true;
      }
    }
    return rowFieldTexts(row).some(
      (text) => normalizeBrushText(text) === needle,
    );
  }

  // fila — exact match on any scalar cell or category key
  if (opts?.categoryKey) {
    const cell = row[opts.categoryKey];
    if (cell !== undefined && normalizeBrushText(String(cell)) === needle) {
      return true;
    }
  }
  return rowFieldTexts(row).some(
    (text) => normalizeBrushText(text) === needle,
  );
}

export function textMatchesBrush(
  text: string | null | undefined,
  brush: CanvasBrush | null | undefined,
): boolean {
  if (!text || !brush?.valor) return false;
  if (brush.tipo === "fecha") {
    const a = isoDayPrefix(text);
    const b = isoDayPrefix(brush.valor);
    return Boolean(a && b && a === b);
  }
  return normalizeBrushText(text) === normalizeBrushText(brush.valor);
}
