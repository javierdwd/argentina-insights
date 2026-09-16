"use client";

import {
  ArrowRight,
  ChartLineUp,
  FilmSlate,
  Scales,
  SoccerBall,
} from "@phosphor-icons/react";
import type { Icon } from "@phosphor-icons/react";
import {
  DESTINATIONS,
  type DestinationId,
} from "@/lib/destinations";

const DESTINATION_ICON: Record<DestinationId, Icon> = {
  economia: ChartLineUp,
  politica: Scales,
  cine: FilmSlate,
  football: SoccerBall,
};

interface DestinationStripProps {
  busy: boolean;
  activeId: DestinationId | null;
  error?: string | null;
  onOpen: (id: DestinationId) => void;
}

export function DestinationStrip({
  busy,
  activeId,
  error,
  onOpen,
}: DestinationStripProps) {
  return (
    <section aria-labelledby="destination-heading" className="mt-12">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2
            id="destination-heading"
            className="font-display text-xl font-semibold tracking-tight text-foreground"
          >
            Entrá por tema
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Panoramas listos para explorar sin esperar una respuesta.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 pb-3 sm:grid-cols-2 xl:grid-cols-4">
        {DESTINATIONS.map((destination) => {
          const Glyph = DESTINATION_ICON[destination.id];
          const loading = activeId === destination.id;
          return (
            <button
              key={destination.id}
              type="button"
              disabled={busy}
              onClick={() => onOpen(destination.id)}
              className="group flex min-h-40 min-w-0 w-full flex-col rounded-2xl border border-border bg-card/70 p-4 text-left transition-[transform,background-color,border-color,box-shadow] hover:-translate-y-0.5 hover:border-accent/35 hover:bg-card hover:shadow-[0_18px_45px_-34px_color-mix(in_oklab,var(--accent)_55%,transparent)] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-45"
            >
              <span className="flex w-full items-start justify-between gap-4">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-soft text-accent">
                  <Glyph size={18} weight="regular" aria-hidden />
                </span>
                <ArrowRight
                  size={16}
                  className="text-accent transition-transform group-hover:translate-x-1"
                  aria-hidden
                />
              </span>
              <span className="mt-4 font-display text-base font-semibold text-foreground">
                {loading ? `Cargando ${destination.title}…` : destination.title}
              </span>
              <span className="mt-1 text-sm leading-snug text-muted-foreground">
                {destination.blurb}
              </span>
              <span className="mt-auto pt-4 text-xs font-medium text-accent">
                {destination.highlights.slice(0, 2).join(" / ")}
              </span>
            </button>
          );
        })}
      </div>
      {error ? (
        <p className="mt-2 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
