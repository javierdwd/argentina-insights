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
  buildFootballTree,
  FOOTBALL_DESTINATION_ID,
  FOOTBALL_FOLLOW_UPS,
  FOOTBALL_QUERY,
  isFootballDestination,
} from "./football";
import {
  buildPoliticaTree,
  POLITICA_DESTINATION_ID,
  POLITICA_FOLLOW_UPS,
  POLITICA_QUERY,
  isPoliticaDestination,
} from "./politica";
import { destinationIdOf } from "./shared";

export type DestinationId = "economia" | "politica" | "cine" | "football";

export type DestinationDef = {
  id: DestinationId;
  title: string;
  blurb: string;
  highlights: readonly string[];
  followUps: readonly string[];
  build: () => Promise<UINode>;
};

export const DESTINATIONS: DestinationDef[] = [
  {
    id: "economia",
    title: ECONOMIA_QUERY,
    blurb: "Compará alternativas y entendé qué rendimiento o riesgo asumís.",
    highlights: ["Plazos fijos", "Fondos comunes", "Hipotecarios UVA"],
    followUps: [
      "¿El mejor plazo fijo le gana a la inflación interanual?",
      "Histórico del FCI Delta Pesos Clase A este año",
      "Compará hipotecarios UVA y cómo viene el índice UVA",
      "Superponé EMAE al blue",
      "Marcá en el blue los eventos presidenciales de 2024",
      "Cruzá riesgo país con confianza en el gobierno",
    ],
    build: buildEconomiaTree,
  },
  {
    id: "politica",
    title: POLITICA_QUERY,
    blurb: "Confianza, Senado y la modernización laboral.",
    highlights: ["Votaciones", "Legisladores", "Confianza"],
    followUps: POLITICA_FOLLOW_UPS,
    build: buildPoliticaTree,
  },
  {
    id: "cine",
    title: CINE_QUERY,
    blurb: "Películas argentinas, ratings y elenco.",
    highlights: ["Películas", "Elencos", "Filmografías"],
    followUps: CINE_FOLLOW_UPS,
    build: buildCineTree,
  },
  {
    id: "football",
    title: FOOTBALL_QUERY,
    blurb: "Tabla actual y evolución reciente de los equipos que lideran.",
    highlights: ["Liga Profesional", "Historial", "Selección"],
    followUps: FOOTBALL_FOLLOW_UPS,
    build: buildFootballTree,
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
  if (
    raw === "economia" ||
    raw === "politica" ||
    raw === "cine" ||
    raw === "football"
  ) {
    return raw;
  }
  if (isEconomiaDestination(tree)) return "economia";
  if (isPoliticaDestination(tree)) return "politica";
  if (isCineDestination(tree)) return "cine";
  if (isFootballDestination(tree)) return "football";
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
  FOOTBALL_DESTINATION_ID,
  FOOTBALL_QUERY,
};
