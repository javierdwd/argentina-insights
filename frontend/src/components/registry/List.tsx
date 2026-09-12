"use client";

import { useEffect, useMemo, useState } from "react";
import type { ListProps } from "./List.schema";

/**
 * List widget — compact table for structured records that don't fit Chart,
 * Metric, PersonCard, or Acta. Columns + scalar cells + client pagination.
 *
 * Nested values stringify; rich formatting (%, logos, deep trees) belongs
 * in projection or a dedicated widget — not heuristics here.
 */

const PAGE_SIZE = 10;

function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toLocaleString("es-AR");
  }
  if (typeof value === "string") {
    if (/^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10);
    return value;
  }
  if (Array.isArray(value) || (typeof value === "object" && value !== null)) {
    try {
      return JSON.stringify(value);
    } catch {
      return "—";
    }
  }
  return String(value);
}

export function List({ columns, data }: ListProps) {
  const rows = data ?? [];
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const [page, setPage] = useState(0);
  const leadKey = columns?.[0]?.key;
  const dataKey = `${rows.length}:${leadKey ? String(rows[0]?.[leadKey] ?? "") : ""}`;

  useEffect(() => {
    setPage(0);
  }, [dataKey]);

  const safePage = Math.min(page, pageCount - 1);

  const slice = useMemo(() => {
    const start = safePage * PAGE_SIZE;
    return rows.slice(start, start + PAGE_SIZE);
  }, [rows, safePage]);

  if (!columns || columns.length === 0) return null;

  if (rows.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center border-t border-rule">
        <p className="text-xs text-muted-foreground/50 select-none">Sin datos</p>
      </div>
    );
  }

  const from = safePage * PAGE_SIZE + 1;
  const to = Math.min(rows.length, (safePage + 1) * PAGE_SIZE);
  const showPager = rows.length > PAGE_SIZE;

  return (
    <div className="border-t border-rule pt-4">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-rule">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className="whitespace-nowrap pb-2 pr-4 font-display text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.map((row, i) => (
              <tr
                key={safePage * PAGE_SIZE + i}
                className="border-b border-rule/60 last:border-0"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className="max-w-xs truncate py-2 pr-4 align-top text-foreground tabular-nums"
                    title={formatCell(row[col.key])}
                  >
                    {formatCell(row[col.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showPager ? (
        <nav
          aria-label="Paginación de la tabla"
          className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground"
        >
          <p>
            {from}–{to} de {rows.length}
          </p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={safePage === 0}
              onClick={() => setPage(safePage - 1)}
              className="rounded px-2 py-1 font-medium text-foreground enabled:hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              type="button"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage(safePage + 1)}
              className="rounded px-2 py-1 font-medium text-foreground enabled:hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-40"
            >
              Siguiente
            </button>
          </div>
        </nav>
      ) : null}
    </div>
  );
}
