"use client";

import { useEffect, useMemo, useState, type KeyboardEvent, type MouseEvent } from "react";
import type { Person, PersonCardProps } from "./PersonCard.schema";
import {
  useCanvasActionOptional,
  useCanvasNode,
} from "@/components/shell/useCanvasAction";

/**
 * PersonCard widget — public-official directory entry.
 *
 * One person → detailed profile (large photo, role/party/province,
 * email / phone / social links when present).
 * Multiple people → compact roster (grid or vertical list) with pagination.
 *
 * Also used for filtered voter lists (map voto → role, imagen/foto → photoUrl)
 * instead of a plain List table.
 */

const PAGE_SIZE = 12;

function getInitials(name: string): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function asLabel(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string" || typeof value === "number") {
    return String(value).trim();
  }
  // Nested API objects (periodoLegal, meta, …) must never render as
  // "[object Object]" in the subtitle line.
  return "";
}

function subtitle(person: Person): string {
  return [asLabel(person.role), asLabel(person.party), asLabel(person.province)]
    .filter(Boolean)
    .join(" · ");
}

function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function linkLabel(href: string): string {
  try {
    const host = new URL(href).hostname.replace(/^www\./, "");
    if (host.includes("facebook")) return "Facebook";
    if (host.includes("instagram")) return "Instagram";
    if (host.includes("twitter") || host.includes("x.com")) return "X";
    if (host.includes("youtube")) return "YouTube";
    if (host.includes("linkedin")) return "LinkedIn";
    if (host.includes("tiktok")) return "TikTok";
    if (host.includes("wikipedia")) return "Wikipedia";
    return host;
  } catch {
    return href;
  }
}

function contactLinks(person: Person): { href: string; label: string }[] {
  const email = asLabel(person.email).toLowerCase();
  const seen = new Set<string>();
  const out: { href: string; label: string }[] = [];

  const push = (href: string, label: string) => {
    const key = href.toLowerCase();
    if (!href || seen.has(key)) return;
    seen.add(key);
    out.push({ href, label });
  };

  if (email) push(`mailto:${email}`, email);

  for (const raw of person.links ?? []) {
    const value = asLabel(raw);
    if (!value) continue;
    if (looksLikeEmail(value)) {
      if (value.toLowerCase() === email) continue;
      push(`mailto:${value}`, value);
      continue;
    }
    const href = /^https?:\/\//i.test(value) ? value : `https://${value}`;
    push(href, linkLabel(href));
  }

  return out;
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

function ProfileCard({
  person,
  onSelect,
}: {
  person: Person;
  onSelect?: (person: Person) => void;
}) {
  const sub = subtitle(person);
  const phone = asLabel(person.phone);
  const bio = asLabel(person.bio);
  const links = contactLinks(person);
  const selectable = Boolean(onSelect);

  return (
    <div
      role={selectable ? "button" : undefined}
      tabIndex={selectable ? 0 : undefined}
      onClick={
        selectable
          ? (event: MouseEvent) => {
              if ((event.target as HTMLElement).closest("a")) return;
              onSelect?.(person);
            }
          : undefined
      }
      onKeyDown={
        selectable
          ? (event: KeyboardEvent) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              if ((event.target as HTMLElement).closest("a")) return;
              event.preventDefault();
              onSelect?.(person);
            }
          : undefined
      }
      className={
        selectable
          ? "flex cursor-pointer items-start gap-4 rounded-md outline-none transition-colors hover:bg-secondary/60 focus-visible:ring-2 focus-visible:ring-accent/40"
          : "flex items-start gap-4"
      }
    >
      <Avatar person={person} size={72} />
      <div className="min-w-0">
        <p className="font-display text-xl font-semibold tracking-tight text-foreground">
          {person.name}
        </p>
        {sub ? <p className="mt-1 text-sm text-muted-foreground">{sub}</p> : null}
        {bio ? (
          <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-muted-foreground">
            {bio}
          </p>
        ) : null}
        {phone || links.length > 0 ? (
          <div className="mt-3 space-y-1 text-sm">
            {phone ? (
              <p className="text-muted-foreground">
                <span className="text-foreground/70">Tel. </span>
                <a
                  href={`tel:${phone.replace(/[^\d+]/g, "")}`}
                  className="text-foreground underline-offset-2 hover:underline"
                  onClick={(event) => event.stopPropagation()}
                >
                  {phone}
                </a>
              </p>
            ) : null}
            {links.length > 0 ? (
              <ul className="flex flex-wrap gap-x-3 gap-y-1">
                {links.map((link) => (
                  <li key={link.href}>
                    <a
                      href={link.href}
                      target={link.href.startsWith("mailto:") ? undefined : "_blank"}
                      rel={
                        link.href.startsWith("mailto:")
                          ? undefined
                          : "noopener noreferrer"
                      }
                      className="text-foreground underline-offset-2 hover:underline"
                      onClick={(event) => event.stopPropagation()}
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function RosterTile({
  person,
  onSelect,
}: {
  person: Person;
  onSelect?: (person: Person) => void;
}) {
  const sub = subtitle(person);
  const selectable = Boolean(onSelect);
  return (
    <div
      role={selectable ? "button" : undefined}
      tabIndex={selectable ? 0 : undefined}
      onClick={selectable ? () => onSelect?.(person) : undefined}
      onKeyDown={
        selectable
          ? (event: KeyboardEvent) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              event.preventDefault();
              onSelect?.(person);
            }
          : undefined
      }
      className={
        selectable
          ? "flex cursor-pointer items-center gap-3 rounded-md p-1 outline-none transition-colors hover:bg-secondary/60 focus-visible:ring-2 focus-visible:ring-accent/40"
          : "flex items-center gap-3"
      }
    >
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

function RosterListRow({
  person,
  onSelect,
}: {
  person: Person;
  onSelect?: (person: Person) => void;
}) {
  const sub = subtitle(person);
  const selectable = Boolean(onSelect);
  return (
    <div
      role={selectable ? "button" : undefined}
      tabIndex={selectable ? 0 : undefined}
      onClick={selectable ? () => onSelect?.(person) : undefined}
      onKeyDown={
        selectable
          ? (event: KeyboardEvent) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              event.preventDefault();
              onSelect?.(person);
            }
          : undefined
      }
      className={
        selectable
          ? "flex cursor-pointer items-center gap-3 border-b border-rule/60 py-2.5 outline-none transition-colors last:border-0 hover:bg-secondary/60 focus-visible:ring-2 focus-visible:ring-accent/40"
          : "flex items-center gap-3 border-b border-rule/60 py-2.5 last:border-0"
      }
    >
      <Avatar person={person} size={40} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{person.name}</p>
        {sub ? (
          <p className="truncate text-xs text-muted-foreground">{sub}</p>
        ) : null}
      </div>
    </div>
  );
}

export function PersonCard({ people, layout = "grid" }: PersonCardProps) {
  const entries = (people ?? []).filter((person) => Boolean(person?.name));
  const [page, setPage] = useState(0);
  const dataKey = `${entries.length}:${entries[0]?.name ?? ""}:${layout}`;
  const canvas = useCanvasActionOptional();
  const node = useCanvasNode();

  const onSelectPerson = (person: Person) => {
    if (!canvas || !person.name?.trim()) return;
    const facts = [
      person.role ? { label: "Rol", value: String(person.role) } : null,
      person.party ? { label: "Partido", value: String(person.party) } : null,
      person.province
        ? { label: "Provincia", value: String(person.province) }
        : null,
    ].filter((f): f is { label: string; value: string } => Boolean(f));
    canvas.selectLocal({
      tipo: "persona",
      valor: person.name.trim(),
      widget: "PersonCard",
      contexto: node?.title,
      facts,
    });
  };

  useEffect(() => {
    setPage(0);
  }, [dataKey]);

  const pageCount = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const slice = useMemo(() => {
    const start = safePage * PAGE_SIZE;
    return entries.slice(start, start + PAGE_SIZE);
  }, [entries, safePage]);

  if (entries.length === 0) {
    return (
      <div className="flex min-h-24 items-center justify-center border-t border-rule px-4 py-6">
        <p className="text-xs text-muted-foreground/70 select-none">
          Sin personas para mostrar en esta vista
        </p>
      </div>
    );
  }

  const select = canvas ? onSelectPerson : undefined;

  if (entries.length === 1) {
    return (
      <div className="border-t border-rule pt-4">
        <ProfileCard person={entries[0]} onSelect={select} />
      </div>
    );
  }

  const from = safePage * PAGE_SIZE + 1;
  const to = Math.min(entries.length, (safePage + 1) * PAGE_SIZE);
  const showPager = entries.length > PAGE_SIZE;
  const useList = layout === "list";

  return (
    <div className="border-t border-rule pt-4">
      {useList ? (
        <div>
          {slice.map((person, i) => (
            <RosterListRow
              key={`${person.name}-${safePage}-${i}`}
              person={person}
              onSelect={select}
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {slice.map((person, i) => (
            <RosterTile
              key={`${person.name}-${safePage}-${i}`}
              person={person}
              onSelect={select}
            />
          ))}
        </div>
      )}

      {showPager ? (
        <nav
          aria-label="Paginación del listado"
          className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground"
        >
          <p>
            {from}–{to} de {entries.length}
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
