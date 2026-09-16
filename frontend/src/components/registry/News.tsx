"use client";

import { useMemo, useState } from "react";
import { ArrowSquareOut } from "@phosphor-icons/react";
import type { NewsItem, NewsProps } from "./News.schema";

const PAGE_SIZE = 8;

function formatPublishedAt(value: string): string {
  const isoDay = value.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDay)) return value;
  const [year, month, day] = isoDay.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("es-AR", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function Story({ item }: { item: NewsItem }) {
  return (
    <article className="group border-b border-rule/70 py-4 first:pt-2 last:border-0 last:pb-1">
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="grid grid-cols-[1fr_auto] items-start gap-4 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
      >
        <div className="min-w-0">
          <h3 className="font-display text-base font-semibold leading-snug tracking-tight text-foreground decoration-1 underline-offset-4 group-hover:underline sm:text-lg">
            {item.title}
          </h3>
          <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
            <span className="font-medium text-foreground/75">{item.source}</span>
            <time dateTime={item.publishedAt}>
              {formatPublishedAt(item.publishedAt)}
            </time>
          </p>
        </div>
        <ArrowSquareOut
          size={17}
          weight="regular"
          aria-hidden
          className="mt-1 shrink-0 text-muted-foreground transition-colors group-hover:text-accent"
        />
        <span className="sr-only">Abrir noticia en una pestaña nueva</span>
      </a>
    </article>
  );
}

/** Editorial headline list backed by Google News RSS. */
export function News({ data }: NewsProps) {
  const rows = data;
  const dataKey = `${rows.length}:${rows[0]?.url ?? ""}`;
  const [pagination, setPagination] = useState({ key: dataKey, page: 0 });
  const page = pagination.key === dataKey ? pagination.page : 0;

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const visible = useMemo(() => {
    const start = safePage * PAGE_SIZE;
    return rows.slice(start, start + PAGE_SIZE);
  }, [rows, safePage]);

  if (rows.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center border-t border-rule">
        <p className="text-xs text-muted-foreground/50 select-none">
          No se encontraron noticias
        </p>
      </div>
    );
  }

  const from = safePage * PAGE_SIZE + 1;
  const to = Math.min(rows.length, (safePage + 1) * PAGE_SIZE);

  return (
    <div className="border-t border-rule pt-2">
      <div>
        {visible.map((item) => (
          <Story key={`${item.url}-${item.publishedAt}`} item={item} />
        ))}
      </div>

      {pageCount > 1 ? (
        <nav
          aria-label="Paginación de noticias"
          className="mt-4 flex items-center justify-between gap-3 border-t border-rule pt-3 text-xs text-muted-foreground"
        >
          <p>
            {from}–{to} de {rows.length}
          </p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={safePage === 0}
              onClick={() =>
                setPagination({ key: dataKey, page: safePage - 1 })
              }
              className="rounded px-2 py-1 font-medium text-foreground enabled:hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              type="button"
              disabled={safePage >= pageCount - 1}
              onClick={() =>
                setPagination({ key: dataKey, page: safePage + 1 })
              }
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
