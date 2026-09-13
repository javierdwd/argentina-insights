/**
 * Fixed destinations — load via /api/data, no LLM turn.
 */

import type { UINode } from "@/lib/uitree";
import {
  buildCineTree,
  CINE_DESTINATION_ID,
  CINE_FOLLOW_UPS,
  CINE_QUERY,
  isCineDestination,
} from "./cine";
import {
  buildEconomiaTree,
  ECONOMIA_DESTINATION_ID,
  ECONOMIA_QUERY,
  isEconomiaDestination,
} from "./economia";
import {
  buildPoliticaTree,
  POLITICA_DESTINATION_ID,
  POLITICA_FOLLOW_UPS,
  POLITICA_QUERY,
  isPoliticaDestination,
} from "./politica";
import { destinationIdOf } from "./shared";

export type DestinationId = "economia" | "politica" | "cine";

export type DestinationDef = {
  id: DestinationId;
  title: string;
  blurb: string;
  followUps: readonly string[];
  build: () => Promise<UINode>;
};

export const DESTINATIONS: DestinationDef[] = [
  {
    id: "economia",
    title: ECONOMIA_QUERY,
    blurb: "Blue vs oficial, inflación y riesgo — listo para explorar.",
    followUps: [
      "Superponé EMAE al blue",
      "Compará el blue por mandato presidencial",
      "Semana con el pico de brecha: ¿qué votó el Congreso?",
      "Cruzá riesgo país con confianza en el gobierno",
    ],
    build: buildEconomiaTree,
  },
  {
    id: "politica",
    title: POLITICA_QUERY,
    blurb: "Confianza, Senado y la modernización laboral.",
    followUps: POLITICA_FOLLOW_UPS,
    build: buildPoliticaTree,
  },
  {
    id: "cine",
    title: CINE_QUERY,
    blurb: "Películas argentinas, ratings y elenco.",
    followUps: CINE_FOLLOW_UPS,
    build: buildCineTree,
  },
];

export function getDestination(id: DestinationId): DestinationDef {
  const found = DESTINATIONS.find((d) => d.id === id);
  if (!found) throw new Error(`Unknown destination: ${id}`);
  return found;
}

export function getDestinationId(
  tree: UINode | null | undefined,
): DestinationId | null {
  const raw = destinationIdOf(tree);
  if (raw === "economia" || raw === "politica" || raw === "cine") return raw;
  if (isEconomiaDestination(tree)) return "economia";
  if (isPoliticaDestination(tree)) return "politica";
  if (isCineDestination(tree)) return "cine";
  return null;
}

export function followUpsFor(tree: UINode | null | undefined): readonly string[] {
  const id = getDestinationId(tree);
  if (!id) return [];
  return getDestination(id).followUps;
}

export function queryForDestination(
  tree: UINode | null | undefined,
): string | undefined {
  const id = getDestinationId(tree);
  if (!id) return undefined;
  return getDestination(id).title;
}

export {
  ECONOMIA_DESTINATION_ID,
  ECONOMIA_QUERY,
  POLITICA_DESTINATION_ID,
  POLITICA_QUERY,
  CINE_DESTINATION_ID,
  CINE_QUERY,
};
