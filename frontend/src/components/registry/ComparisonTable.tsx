"use client";

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  ComparisonColumn,
  ComparisonTableProps,
} from "./ComparisonTable.schema";
import {
  useCanvasActionOptional,
  useCanvasNode,
} from "@/components/shell/useCanvasAction";
import { inferCanvasTipo } from "@/components/shell/infer-canvas-tipo";

/**
 * ComparisonTable — side-by-side product / fee / REM error comparison.
 *
 * Unlike List (generic records), this widget assumes rows are alternatives
 * the user is weighing: entity column + numeric attributes, optional
 * highlight of the best value in one column.
 */

const PAGE_SIZE = 12;

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value.replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function resolveKind(
  col: ComparisonColumn,
  rows: Record<string, unknown>[],
): NonNullable<ComparisonColumn["kind"]> {
  if (col.kind) return col.kind;
  const sample = rows
    .map((r) => r[col.key])
    .find((v) => v !== null && v !== undefined && v !== "");
  if (asFiniteNumber(sample) !== null) return "number";
  return "text";
}

function formatCell(
  value: unknown,
  kind: NonNullable<ComparisonColumn["kind"]>,
): string {
  if (value === null || value === undefined || value === "") return "—";
  if (kind === "date" && typeof value === "string") return value.slice(0, 10);
  if (kind === "url" && typeof value === "string") {
    try {
      return new URL(value).hostname.replace(/^www\./, "");
    } catch {
      return value;
    }
  }
  const num = asFiniteNumber(value);
  if (num !== null && (kind === "number" || kind === "money")) {
    return formatNumber(num);
  }
  if (num !== null && kind === "percent") {
    return `${formatNumber(num)}%`;
  }
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (Array.isArray(value)) {
    return value.length === 0 ? "—" : String(value.length);
  }
  if (typeof value === "object") return "—";
  return String(value);
}

function winningIndices(
  rows: Record<string, unknown>[],
  key: string,
  direction: "min" | "max",
): Set<number> {
  let best: number | null = null;
  const values = rows.map((row) => asFiniteNumber(row[key]));
  for (const v of values) {
    if (v === null) continue;
    if (
      best === null ||
      (direction === "min" ? v < best : v > best)
    ) {
      best = v;
    }
  }
  if (best === null) return new Set();
  const winners = new Set<number>();
  values.forEach((v, i) => {
    if (v !== null && v === best) winners.add(i);
  });
  return winners;
}

export function ComparisonTable({
  columns,
  data,
  highlight,
}: ComparisonTableProps) {
  const rows = data ?? [];
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const [page, setPage] = useState(0);
  const primary =
    columns.find((c) => c.primary) ?? columns[0] ?? null;
  const leadKey = primary?.key;
  const dataKey = `${rows.length}:${leadKey ? String(rows[0]?.[leadKey] ?? "") : ""}`;
  const canvas = useCanvasActionOptional();
  const node = useCanvasNode();

  useEffect(() => {
    setPage(0);
  }, [dataKey]);

  const safePage = Math.min(page, pageCount - 1);
  const slice = useMemo(() => {
    const start = safePage * PAGE_SIZE;
    return rows.slice(start, start + PAGE_SIZE);
  }, [rows, safePage]);

  const winners = useMemo(() => {
    if (!highlight?.key) return new Set<number>();
    // Highlight indices are absolute within the full dataset.
    return winningIndices(rows, highlight.key, highlight.direction);
  }, [rows, highlight]);

  const selectRow = (row: Record<string, unknown>, absoluteIndex: number) => {
    if (!canvas || !leadKey) return;
    const lead = formatCell(row[leadKey], resolveKind(primary!, rows));
    if (!lead || lead === "—") return;
    const facts = columns
      .filter((col) => col.key !== leadKey)
      .map((col) => ({
        label: col.label || col.key,
        value: formatCell(row[col.key], resolveKind(col, rows)),
      }))
      .filter((f) => f.value && f.value !== "—");
    canvas.selectLocal({
      tipo: inferCanvasTipo({
        valor: lead,
        row,
        categoryKey: leadKey,
      }),
      valor: lead,
      widget: "ComparisonTable",
      contexto: node?.title,
      facts,
    });
  };

  if (!columns || columns.length < 2) return null;

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
  const selectable = Boolean(canvas);

  return (
    <div className="border-t border-rule pt-4">
      <div className="-mx-1 overflow-x-auto overscroll-x-contain px-1">
        <table className="w-max min-w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-rule">
              {columns.map((col) => {
                const kind = resolveKind(col, rows);
                const isPrimary = col.key === leadKey;
                return (
                  <th
                    key={col.key}
                    scope="col"
                    className={cn(
                      "whitespace-nowrap pb-2 pr-4 font-display text-xs font-semibold uppercase tracking-wide text-muted-foreground",
                      !isPrimary &&
                        (kind === "number" ||
                          kind === "percent" ||
                          kind === "money") &&
                        "text-right",
                    )}
                  >
                    {col.label}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {slice.map((row, i) => {
              const absoluteIndex = safePage * PAGE_SIZE + i;
              const isWinner = winners.has(absoluteIndex);
              return (
                <tr
                  key={absoluteIndex}
                  role={selectable ? "button" : undefined}
                  tabIndex={selectable ? 0 : undefined}
                  onClick={
                    selectable ? () => selectRow(row, absoluteIndex) : undefined
                  }
                  onKeyDown={
                    selectable
                      ? (event: KeyboardEvent) => {
                          if (event.key !== "Enter" && event.key !== " ") return;
                          event.preventDefault();
                          selectRow(row, absoluteIndex);
                        }
                      : undefined
                  }
                  className={cn(
                    "border-b border-rule/60 last:border-0",
                    selectable &&
                      "cursor-pointer outline-none transition-colors hover:bg-secondary/60 focus-visible:bg-secondary/60",
                    isWinner && "bg-accent-soft/70",
                  )}
                >
                  {columns.map((col) => {
                    const kind = resolveKind(col, rows);
                    const isPrimary = col.key === leadKey;
                    const numeric =
                      kind === "number" ||
                      kind === "percent" ||
                      kind === "money";
                    const winCell =
                      isWinner && highlight?.key === col.key;
                    const value = row[col.key];
                    const display = formatCell(value, kind);

                    if (kind === "url" && typeof value === "string") {
                      return (
                        <td
                          key={col.key}
                          className="whitespace-nowrap py-2.5 pr-4 align-middle"
                        >
                          <a
                            href={value}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-foreground underline-offset-2 hover:underline"
                            onClick={(event) => event.stopPropagation()}
                          >
                            {display}
                          </a>
                        </td>
                      );
                    }

                    return (
                      <td
                        key={col.key}
                        className={cn(
                          "whitespace-nowrap py-2.5 pr-4 align-middle tabular-nums",
                          isPrimary
                            ? "font-display font-medium text-foreground"
                            : "text-foreground",
                          !isPrimary && numeric && "text-right",
                          winCell && "font-semibold text-accent",
                        )}
                        title={display}
                      >
                        {display}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showPager ? (
        <nav
          aria-label="Paginación de la comparación"
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
