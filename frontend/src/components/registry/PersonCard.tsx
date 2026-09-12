"use client";

import { useState } from "react";
import type { Person, PersonCardProps } from "./PersonCard.schema";

/**
 * PersonCard widget — public-official directory entry.
 *
 * One person → detailed profile (large photo, role/party/province).
 * Multiple people → compact roster grid (small photo, name + subtitle).
 *
 * Used for senators/deputies: profile lookups and committee/province rosters.
 */

function getInitials(name: string): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function subtitle(person: Person): string {
  return [person.role, person.party, person.province].filter(Boolean).join(" · ");
}

function Avatar({ person, size }: { person: Person; size: number }) {
  const [errored, setErrored] = useState(false);
  const showImage = Boolean(person.photoUrl) && !errored;

  if (showImage) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- external, unpredictable domains (scraped)
      <img
        src={person.photoUrl}
        alt={person.name}
        width={size}
        height={size}
        onError={() => setErrored(true)}
        className="shrink-0 rounded-full border border-rule object-cover"
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground"
      style={{ width: size, height: size }}
    >
      <span
        className="font-display font-semibold"
        style={{ fontSize: size * 0.34 }}
      >
        {getInitials(person.name)}
      </span>
    </div>
  );
}

function ProfileCard({ person }: { person: Person }) {
  const sub = subtitle(person);
  return (
    <div className="flex items-start gap-4">
      <Avatar person={person} size={72} />
      <div className="min-w-0">
        <p className="font-display text-xl font-semibold tracking-tight text-foreground">
          {person.name}
        </p>
        {sub ? <p className="mt-1 text-sm text-muted-foreground">{sub}</p> : null}
      </div>
    </div>
  );
}

function RosterTile({ person }: { person: Person }) {
  const sub = subtitle(person);
  return (
    <div className="flex items-center gap-3">
      <Avatar person={person} size={40} />
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">{person.name}</p>
        {sub ? (
          <p className="truncate text-xs text-muted-foreground">{sub}</p>
        ) : null}
      </div>
    </div>
  );
}

export function PersonCard({ people }: PersonCardProps) {
  // A row that carries no name has nothing to render, and would take the
  // whole canvas down with it.
  const entries = (people ?? []).filter((person) => Boolean(person?.name));
  if (entries.length === 0) return null;

  return (
    <div className="border-t border-rule pt-4">
      {entries.length === 1 ? (
        <ProfileCard person={entries[0]} />
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {entries.map((person, i) => (
            <RosterTile key={`${person.name}-${i}`} person={person} />
          ))}
        </div>
      )}
    </div>
  );
}
