"use client";

import { useState } from "react";
import type {
  FootballLineupProps,
  FootballLineupSide,
  FootballPlayer,
} from "./FootballLineup.schema";
import {
  formationPositions,
  type PitchSide,
} from "./football-lineup-layout";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return `${parts[0]![0]}${parts.at(-1)![0]}`.toUpperCase();
}

function shortName(player: FootballPlayer): string {
  if (player.shortName?.trim()) return player.shortName.trim();
  const parts = player.name.trim().split(/\s+/);
  return parts.length > 1 ? parts.at(-1)! : player.name;
}

function shirtNumber(player: FootballPlayer): string | null {
  const value = player.number ?? player.shirtNumber;
  return value == null || String(value).trim() === "" ? null : String(value);
}

function playerPhoto(player: FootballPlayer): string | undefined {
  return player.photoUrl || player.photo || player.face || undefined;
}

function isGoalkeeper(player: FootballPlayer): boolean {
  return /^(gk|g|por|goalkeeper|arquero)$/i.test(player.position?.trim() ?? "");
}

function orderedStarters(players: FootballPlayer[]): FootballPlayer[] {
  const goalkeeper = players.findIndex(isGoalkeeper);
  if (goalkeeper <= 0) return players;
  return [
    players[goalkeeper]!,
    ...players.filter((_, index) => index !== goalkeeper),
  ];
}

function PlayerFace({
  player,
  size = "normal",
}: {
  player: FootballPlayer;
  size?: "normal" | "small";
}) {
  const [failed, setFailed] = useState(false);
  const photo = playerPhoto(player);
  const dimensions = size === "small" ? "h-7 w-7" : "h-8 w-8 sm:h-10 sm:w-10";

  if (photo && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- third-party football portraits
      <img
        src={photo}
        alt=""
        onError={() => setFailed(true)}
        className={`${dimensions} rounded-full border border-card/80 bg-card object-cover shadow-sm`}
      />
    );
  }

  return (
    <span
      aria-hidden
      className={`${dimensions} flex items-center justify-center rounded-full border border-card/80 bg-secondary font-display text-[0.62rem] font-semibold text-secondary-foreground shadow-sm`}
    >
      {initials(player.name)}
    </span>
  );
}

function PlayerMarker({
  player,
  x,
  y,
}: {
  player: FootballPlayer;
  x: number;
  y: number;
}) {
  const number = shirtNumber(player);
  const label = [number ? `Número ${number}` : null, player.name]
    .filter(Boolean)
    .join(", ");
  return (
    <li
      aria-label={label}
      className="absolute z-10 flex w-[4.5rem] -translate-x-1/2 -translate-y-1/2 flex-col items-center text-center sm:w-24"
      style={{ left: `${x}%`, top: `${y}%` }}
    >
      <span className="relative">
        <PlayerFace player={player} />
        {number ? (
          <span className="absolute -right-1 -bottom-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-foreground px-1 text-[0.55rem] font-bold leading-none text-background ring-1 ring-card">
            {number}
          </span>
        ) : null}
      </span>
      <span className="mt-0.5 max-w-full truncate rounded bg-card/90 px-1.5 py-0.5 text-[0.58rem] font-semibold leading-none text-foreground shadow-sm sm:text-[0.66rem]">
        {shortName(player)}
      </span>
    </li>
  );
}

function teamStatus(side: FootballLineupSide): string {
  return side.isProjected ? "Probable" : "Confirmada";
}

function CoachAndBench({ side }: { side: FootballLineupSide }) {
  const coach =
    typeof side.coach === "string" ? side.coach : side.coach?.name;
  return (
    <section
      aria-label={`Cuerpo técnico y suplentes de ${side.team}`}
      className="min-w-0 rounded-xl border border-border/80 bg-card/55 p-3"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-display text-sm font-semibold text-foreground">
          {side.team}
        </p>
        {coach ? (
          <p className="text-xs text-muted-foreground">DT · {coach}</p>
        ) : null}
      </div>
      {(side.substitutes ?? []).length ? (
        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Suplentes">
          {(side.substitutes ?? []).map((player, index) => (
            <span
              key={`${player.name}-${index}`}
              className="inline-flex max-w-full items-center gap-1 rounded-full bg-secondary px-2 py-1 text-[0.68rem] text-secondary-foreground"
            >
              {shirtNumber(player) ? (
                <span className="font-semibold tabular-nums">
                  {shirtNumber(player)}
                </span>
              ) : null}
              <span className="truncate">{shortName(player)}</span>
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">Sin suplentes informados</p>
      )}
    </section>
  );
}

function sideHeader(side: FootballLineupSide | undefined, align: "top" | "bottom") {
  if (!side) return null;
  const formation = side.formation != null ? String(side.formation) : "s/d";
  return (
    <div
      className={[
        "absolute inset-x-3 z-20 flex items-center justify-between gap-3 rounded-lg bg-card/90 px-3 py-2 shadow-sm ring-1 ring-border/80 backdrop-blur-sm",
        align === "top" ? "top-3" : "bottom-3",
      ].join(" ")}
    >
      <div className="flex min-w-0 items-center gap-2">
        {side.logo ? (
          // eslint-disable-next-line @next/next/no-img-element -- third-party team crests
          <img src={side.logo} alt="" className="h-6 w-6 object-contain" />
        ) : null}
        <span className="truncate text-xs font-semibold text-foreground sm:text-sm">
          {side.team}
        </span>
      </div>
      <span className="shrink-0 text-[0.65rem] text-muted-foreground sm:text-xs">
        {formation} · {teamStatus(side)}
      </span>
    </div>
  );
}

function PitchMarkings() {
  return (
    <svg
      viewBox="0 0 68 105"
      preserveAspectRatio="none"
      aria-hidden
      className="absolute inset-0 h-full w-full text-accent/35"
    >
      <rect x="1" y="1" width="66" height="103" fill="none" stroke="currentColor" strokeWidth="0.45" />
      <line x1="1" y1="52.5" x2="67" y2="52.5" stroke="currentColor" strokeWidth="0.45" />
      <circle cx="34" cy="52.5" r="9.15" fill="none" stroke="currentColor" strokeWidth="0.45" />
      <circle cx="34" cy="52.5" r="0.65" fill="currentColor" />
      <rect x="13.85" y="1" width="40.3" height="16.5" fill="none" stroke="currentColor" strokeWidth="0.45" />
      <rect x="24.84" y="1" width="18.32" height="5.5" fill="none" stroke="currentColor" strokeWidth="0.45" />
      <circle cx="34" cy="11" r="0.65" fill="currentColor" />
      <path d="M 26.7 17.5 A 9.15 9.15 0 0 0 41.3 17.5" fill="none" stroke="currentColor" strokeWidth="0.45" />
      <rect x="13.85" y="87.5" width="40.3" height="16.5" fill="none" stroke="currentColor" strokeWidth="0.45" />
      <rect x="24.84" y="98.5" width="18.32" height="5.5" fill="none" stroke="currentColor" strokeWidth="0.45" />
      <circle cx="34" cy="94" r="0.65" fill="currentColor" />
      <path d="M 26.7 87.5 A 9.15 9.15 0 0 1 41.3 87.5" fill="none" stroke="currentColor" strokeWidth="0.45" />
    </svg>
  );
}

export function FootballLineup({ data }: FootballLineupProps) {
  const home = data.find((row) => row.side === "home");
  const away = data.find((row) => row.side === "away");
  const sides = [away, home].filter(
    (side): side is FootballLineupSide => Boolean(side),
  );

  if (!sides.length) {
    return <p className="border-t border-rule py-6 text-center text-xs text-muted-foreground">Sin formación disponible</p>;
  }

  return (
    <div className="border-t border-rule pt-4">
      <figure
        aria-label={`Formaciones de ${sides.map((side) => side.team).join(" y ")}. Las posiciones representan líneas tácticas aproximadas.`}
        className="relative mx-auto aspect-[68/105] w-full max-w-[38rem] overflow-hidden rounded-2xl bg-accent-soft/55 ring-1 ring-accent/20"
      >
        <PitchMarkings />
        {sideHeader(away, "top")}
        {sideHeader(home, "bottom")}
        {sides.map((side) => {
          const players = orderedStarters(side.starting ?? []);
          const positions = formationPositions(
            players.length,
            side.formation != null ? String(side.formation) : null,
            side.side as PitchSide,
          );
          return (
            <ol key={side.side} aria-label={`Titulares de ${side.team}`}>
              {players.map((player, index) => (
                <PlayerMarker
                  key={`${side.side}-${player.name}-${index}`}
                  player={player}
                  x={positions[index]?.x ?? 50}
                  y={positions[index]?.y ?? 50}
                />
              ))}
            </ol>
          );
        })}
      </figure>
      <p className="mt-2 text-center text-[0.65rem] text-muted-foreground">
        Ubicación aproximada por líneas de formación; no representa coordenadas de juego.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {sides.map((side) => (
          <CoachAndBench key={side.side} side={side} />
        ))}
      </div>
    </div>
  );
}
