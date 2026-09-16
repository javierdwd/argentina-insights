"use client";

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import type { ListProps } from "./List.schema";
import {
  useCanvasActionOptional,
  useCanvasBrush,
  useCanvasNode,
} from "@/components/shell/useCanvasAction";
import { inferCanvasTipo } from "@/components/shell/infer-canvas-tipo";
import { rowMatchesBrush } from "@/components/shell/canvas-brush";
import {
  foldImageColumns,
  inferColumnKind,
  isGenericImageLabel,
  looksLikeHttpUrl,
  looksLikeImageUrl,
  pickListSelectionLead,
} from "./list-cell";

/**
 * List widget — compact table for structured records that don't fit Chart,
 * Metric, PersonCard, or Acta. Columns + scalar cells + client pagination.
 *
 * Image URL columns (imagen/foto/photoUrl, or values that look like pictures)
 * render as thumbnails. When a name column is also present, the photo folds
 * into that cell so the table is not a wall of truncated URLs.
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
  // Nested arrays/objects must never dump JSON into a cell — the proxy
  // should have flattened them. Show a count for arrays; dash otherwise.
  if (Array.isArray(value)) {
    return value.length === 0 ? "—" : String(value.length);
  }
  if (typeof value === "object") return "—";
  return String(value);
}

function Thumb({
  src,
  alt,
  round,
}: {
  src: string;
  alt: string;
  round: boolean;
}) {
  const [errored, setErrored] = useState(false);
  if (!src || errored) {
    return (
      <span
        aria-hidden
        className={[
          "inline-block h-9 w-9 shrink-0 bg-secondary",
          round ? "rounded-full" : "rounded-md",
        ].join(" ")}
      />
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- external, unpredictable domains
    <img
      src={src}
      alt={alt}
      width={36}
      height={36}
      onError={() => setErrored(true)}
      className={[
        "h-9 w-9 shrink-0 border border-rule object-cover",
        round ? "rounded-full" : "rounded-md",
      ].join(" ")}
    />
  );
}

function CellValue({
  kind,
  value,
  imageSrc,
  imageAlt,
}: {
  kind: ReturnType<typeof inferColumnKind>;
  value: unknown;
  imageSrc?: string | null;
  imageAlt?: string;
}) {
  if (imageSrc) {
    const src = looksLikeHttpUrl(imageSrc) ? String(imageSrc).trim() : "";
    return (
      <span className="inline-flex items-center gap-2.5">
        <Thumb src={src} alt={imageAlt || ""} round />
        <span>{formatCell(value)}</span>
      </span>
    );
  }
  if (kind === "image") {
    const src = looksLikeImageUrl(value) || looksLikeHttpUrl(value)
      ? String(value).trim()
      : "";
    return <Thumb src={src} alt="" round={false} />;
  }
  if (kind === "url" && looksLikeHttpUrl(value)) {
    const href = String(value).trim();
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="truncate text-foreground underline-offset-2 hover:underline"
        onClick={(event) => event.stopPropagation()}
      >
        {(() => {
          try {
            return new URL(href).hostname.replace(/^www\./, "");
          } catch {
            return href;
          }
        })()}
      </a>
    );
  }
  return formatCell(value);
}

export function List({ columns, data }: ListProps) {
  const rows = data ?? [];
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const folded = useMemo(
    () => foldImageColumns(columns ?? [], rows),
    [columns, rows],
  );
  const visible = folded.columns;
  const leadKey = visible[0]?.key;
  const dataKey = `${rows.length}:${leadKey ? String(rows[0]?.[leadKey] ?? "") : ""}`;
  const canvas = useCanvasActionOptional();
  const brush = useCanvasBrush();
  const node = useCanvasNode();

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) =>
      Object.values(row).some((value) => {
        if (value === null || value === undefined || value === "") return false;
        if (typeof value === "object") return false;
        return String(value).toLowerCase().includes(q);
      }),
    );
  }, [rows, query]);

  const pageCount = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE));

  useEffect(() => {
    setPage(0);
  }, [dataKey]);

  useEffect(() => {
    setPage(0);
  }, [query]);

  const safePage = Math.min(page, pageCount - 1);

  const slice = useMemo(() => {
    const start = safePage * PAGE_SIZE;
    return filteredRows.slice(start, start + PAGE_SIZE);
  }, [filteredRows, safePage]);

  const selectRow = (row: Record<string, unknown>) => {
    if (!canvas) return;
    const lead = pickListSelectionLead(row, columns ?? [], rows, formatCell);
    if (!lead) return;
    const facts = (columns ?? [])
      .filter((col) => inferColumnKind(col, rows) !== "image")
      .map((col) => ({
        label: col.label || col.key,
        value: formatCell(row[col.key]),
      }))
      .filter((f) => f.value && f.value !== "—");
    canvas.selectLocal({
      tipo: inferCanvasTipo({
        valor: lead.valor,
        row,
        categoryKey: lead.key,
      }),
      valor: lead.valor,
      imageUrl: lead.imageUrl,
      widget: "List",
      contexto: node?.title,
      facts,
    });
  };

  if (!columns || columns.length === 0) return null;

  if (rows.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center border-t border-rule">
        <p className="text-xs text-muted-foreground/50 select-none">Sin datos</p>
      </div>
    );
  }

  const from = filteredRows.length === 0 ? 0 : safePage * PAGE_SIZE + 1;
  const to = Math.min(filteredRows.length, (safePage + 1) * PAGE_SIZE);
  const showPager = filteredRows.length > PAGE_SIZE;
  const selectable = Boolean(canvas);

  return (
    <div className="border-t border-rule pt-4">
      <div className="mb-3">
        <label className="sr-only" htmlFor="list-filter">
          Filtrar filas
        </label>
        <input
          id="list-filter"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Filtrar…"
          className="w-full max-w-xs rounded-md border border-rule bg-card px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        />
      </div>
      <div className="-mx-1 overflow-x-auto overscroll-x-contain px-1">
        <table className="w-max min-w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-rule">
              {visible.map((col) => {
                const kind = inferColumnKind(col, rows);
                const hideLabel =
                  kind === "image" && isGenericImageLabel(col.label, col.key);
                return (
                  <th
                    key={col.key}
                    scope="col"
                    className="whitespace-nowrap pb-2 pr-4 font-display text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                  >
                    {hideLabel ? (
                      <span className="sr-only">{col.label || "Foto"}</span>
                    ) : (
                      col.label
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {slice.length === 0 ? (
              <tr>
                <td
                  colSpan={visible.length}
                  className="py-6 text-center text-sm text-muted-foreground"
                >
                  Sin coincidencias
                </td>
              </tr>
            ) : (
              slice.map((row, i) => {
                const brushed = rowMatchesBrush(row, brush, {
                  categoryKey: leadKey,
                });
                return (
                  <tr
                    key={safePage * PAGE_SIZE + i}
                    role={selectable ? "button" : undefined}
                    tabIndex={selectable ? 0 : undefined}
                    onClick={selectable ? () => selectRow(row) : undefined}
                    onKeyDown={
                      selectable
                        ? (event: KeyboardEvent) => {
                            if (event.key !== "Enter" && event.key !== " ") {
                              return;
                            }
                            event.preventDefault();
                            selectRow(row);
                          }
                        : undefined
                    }
                    className={[
                      "border-b border-rule/60 last:border-0",
                      selectable
                        ? "cursor-pointer outline-none transition-colors hover:bg-secondary/60 focus-visible:bg-secondary/60"
                        : "",
                      brushed ? "bg-accent-soft/70" : "",
                    ].join(" ")}
                  >
                    {visible.map((col) => {
                      const kind = inferColumnKind(col, rows);
                      const foldHere =
                        Boolean(folded.imageKey) && col.key === folded.nameKey;
                      const imageSrc = foldHere
                        ? row[folded.imageKey as string]
                        : undefined;
                      return (
                        <td
                          key={col.key}
                          className="whitespace-nowrap py-2 pr-4 align-middle text-foreground tabular-nums"
                          title={
                            kind === "image" || foldHere
                              ? undefined
                              : formatCell(row[col.key])
                          }
                        >
                          <CellValue
                            kind={kind}
                            value={row[col.key]}
                            imageSrc={
                              typeof imageSrc === "string" ? imageSrc : null
                            }
                            imageAlt={
                              foldHere ? formatCell(row[col.key]) : undefined
                            }
                          />
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {showPager ? (
        <nav
          aria-label="Paginación de la tabla"
          className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground"
        >
          <p>
            {from}–{to} de {filteredRows.length}
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
