"use client";

import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { ActaProps } from "./Acta.schema";

/**
 * Acta widget — one legislative vote: header once (date, result, title),
 * then the roll call. Vote rows from /actas/id/{id}/votos stamp the parent
 * acta onto every legislator; this widget lifts that shared text out of
 * the list so it is not repeated 160 times.
 */

const PAGE_SIZE = 10;

const VOTE_ORDER = ["afirmativo", "negativo", "abstencion", "ausente"] as const;

const VOTE_LABEL: Record<string, string> = {
  afirmativo: "A favor",
  negativo: "En contra",
  abstencion: "Abstención",
  abstención: "Abstención",
  ausente: "Ausente",
  presidente: "Presidió",
};

const VOTE_CLASS: Record<string, string> = {
  afirmativo: "text-trend-up",
  negativo: "text-trend-down",
  abstencion: "text-muted-foreground",
  abstención: "text-muted-foreground",
  ausente: "text-muted-foreground",
  presidente: "text-muted-foreground",
};

function asText(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

function canonVote(value: unknown): string {
  return asText(value)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function formatDate(value: string): string {
  const iso = value.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return value;
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.toLocaleDateString("es-AR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function voteLabel(vote: string): string {
  const key = canonVote(vote);
  return VOTE_LABEL[key] ?? (vote ? vote : "—");
}

type RollRow = {
  voter: string;
  vote: string;
  title: string;
  date: string;
  result: string;
};

function flatten(data: Record<string, unknown>[]): RollRow[] {
  // Flat vote rows are remapped by bind_data to schema keys (title/date/…).
  // A single nested acta still has Spanish keys inside votos[] — aliases
  // only run on the outer row.
  if (data.length === 1 && Array.isArray(data[0]?.votos)) {
    const acta = data[0];
    const title = asText(acta.title ?? acta.titulo);
    const date = asText(acta.date ?? acta.fecha);
    const result = asText(acta.result ?? acta.resultado);
    return (acta.votos as unknown[]).flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const row = item as Record<string, unknown>;
      const voter = asText(row.voter ?? row.nombre);
      if (!voter) return [];
      return [
        {
          voter,
          vote: asText(row.vote ?? row.voto),
          title,
          date,
          result,
        },
      ];
    });
  }

  return data.flatMap((row) => {
    const voter = asText(row.voter);
    if (!voter) return [];
    return [
      {
        voter,
        vote: asText(row.vote),
        title: asText(row.title),
        date: asText(row.date),
        result: asText(row.result),
      },
    ];
  });
}

export function Acta({ data }: ActaProps) {
  const rows = useMemo(() => flatten(data ?? []), [data]);
  const header = rows[0];
  const tallies = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of rows) {
      const key = canonVote(row.vote) || "otro";
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const known = VOTE_ORDER.filter((key) => counts.has(key)).map((key) => ({
      key,
      count: counts.get(key) ?? 0,
    }));
    const extra = [...counts.entries()]
      .filter(
        ([key]) => !VOTE_ORDER.includes(key as (typeof VOTE_ORDER)[number]),
      )
      .map(([key, count]) => ({ key, count }));
    return [...known, ...extra];
  }, [rows]);

  const [filter, setFilter] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const filtered = useMemo(
    () =>
      filter ? rows.filter((row) => canonVote(row.vote) === filter) : rows,
    [rows, filter],
  );

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const dataKey = `${rows.length}:${header?.date ?? ""}:${header?.title ?? ""}`;

  useEffect(() => {
    setPage(0);
    setFilter(null);
  }, [dataKey]);

  useEffect(() => {
    setPage(0);
  }, [filter]);

  const safePage = Math.min(page, pageCount - 1);
  const slice = filtered.slice(
    safePage * PAGE_SIZE,
    (safePage + 1) * PAGE_SIZE,
  );

  if (!header) {
    return (
      <div className="flex h-24 items-center justify-center border-t border-rule">
        <p className="text-xs text-muted-foreground/50 select-none">
          Sin votos
        </p>
      </div>
    );
  }

  const from = safePage * PAGE_SIZE + 1;
  const to = Math.min(filtered.length, (safePage + 1) * PAGE_SIZE);
  const showPager = filtered.length > PAGE_SIZE;

  return (
    <div className="border-t border-rule pt-4">
      <header className="max-w-xl">
        {header.date ? (
          <p className="font-display text-2xl font-semibold tracking-tight text-foreground">
            {formatDate(header.date)}
          </p>
        ) : null}
        {header.result ? (
          <p className="mt-1 text-sm text-muted-foreground">{header.result}</p>
        ) : null}
        {header.title ? (
          <p className="mt-3 text-[0.95rem] leading-relaxed text-foreground">
            {header.title}
          </p>
        ) : null}
      </header>

      {tallies.length > 0 ? (
        <ul className="mt-5 flex flex-wrap gap-x-5 gap-y-1 border-t border-rule pt-3">
          {tallies.map(({ key, count }) => {
            const active = filter === key;
            return (
              <li key={key}>
                <button
                  type="button"
                  aria-pressed={active}
                  onClick={() => setFilter(active ? null : key)}
                  className={cn(
                    "text-sm tabular-nums",
                    active
                      ? "text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <span className={cn("font-medium", VOTE_CLASS[key])}>
                    {voteLabel(key)}
                  </span>
                  <span className="ml-1.5">{count}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}

      <ol className="mt-3 divide-y divide-rule/60 border-t border-rule">
        {slice.map((row, i) => (
          <li
            key={`${row.voter}-${safePage * PAGE_SIZE + i}`}
            className="flex items-baseline justify-between gap-4 py-2 text-sm"
          >
            <span className="min-w-0 text-foreground">{row.voter}</span>
            <span
              className={cn(
                "shrink-0 tabular-nums",
                VOTE_CLASS[canonVote(row.vote)] ?? "text-muted-foreground",
              )}
            >
              {voteLabel(row.vote)}
            </span>
          </li>
        ))}
      </ol>

      {showPager ? (
        <nav
          aria-label="Paginación de la votación"
          className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground"
        >
          <p>
            {from}–{to} de {filtered.length}
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
