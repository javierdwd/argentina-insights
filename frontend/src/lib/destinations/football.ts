/**
 * Destino Fútbol — current Liga Profesional table and recent, normalized
 * performance history. Loaded directly through /api/data (no LLM turn).
 */

import { fetchData } from "@/lib/data-api";
import type { UINode } from "@/lib/uitree";
import { asRows, num, str, type SeriesRow } from "./shared";

export const FOOTBALL_QUERY = "Fútbol";
export const FOOTBALL_DESTINATION_ID = "football";

export const FOOTBALL_FOLLOW_UPS = [
  "Mostrame la evolución de River Plate en las últimas cinco temporadas",
  "Compará a River Plate y Boca Juniors en las últimas cinco temporadas",
  "Historial reciente de enfrentamientos entre River Plate y Boca Juniors",
  "Últimos partidos y evolución de la Selección Argentina",
] as const;

export type StandingRow = {
  team: string;
  teamId?: string;
  logo?: string;
  rank: number;
  played?: number;
  won?: number;
  drawn?: number;
  lost?: number;
  goalsFor?: number;
  goalsAgainst?: number;
  goalDifference?: number;
  points?: number;
  form?: string;
  zone?: string;
};

export type TeamSeasonMetric = {
  team: string;
  season: string;
  winRate?: number;
  pointsPerGame?: number;
  goalDifferencePerGame?: number;
};

function optionalNumber(value: unknown): number | undefined {
  return num(value) ?? undefined;
}

/** Seasons are API strings (including split-year labels), sorted newest first. */
export function recentSeasons(rows: SeriesRow[], limit = 5): string[] {
  const values = rows
    .map((row) => str(row.season))
    .filter((season): season is string => season != null);
  return [...new Set(values)]
    .sort((a, b) =>
      b.localeCompare(a, "es", { numeric: true, sensitivity: "base" }),
    )
    .slice(0, Math.max(0, limit));
}

/** Keep valid table rows, sort by rank, and normalize numeric fields. */
export function polishStandings(rows: SeriesRow[]): StandingRow[] {
  const polished: StandingRow[] = [];
  for (const row of rows) {
    const team = str(row.team);
    const rank = num(row.rank);
    if (!team || rank == null) continue;
    polished.push({
      team,
      teamId: str(row.teamId) ?? undefined,
      logo: str(row.logo) ?? undefined,
      rank,
      played: optionalNumber(row.played),
      won: optionalNumber(row.won),
      drawn: optionalNumber(row.drawn),
      lost: optionalNumber(row.lost),
      goalsFor: optionalNumber(row.goalsFor),
      goalsAgainst: optionalNumber(row.goalsAgainst),
      goalDifference: optionalNumber(row.goalDifference),
      points: optionalNumber(row.points),
      form: str(row.form) ?? undefined,
      zone: str(row.zone) ?? undefined,
    });
  }
  return polished.sort((a, b) => a.rank - b.rank);
}

/** Choose a small, stable set from the top of the latest standings. */
export function leadingTeams(
  standings: StandingRow[],
  limit = 4,
): StandingRow[] {
  const seen = new Set<string>();
  return standings.filter((row) => {
    const key = row.team.toLocaleLowerCase("es-AR");
    if (seen.has(key) || seen.size >= limit) return false;
    seen.add(key);
    return true;
  });
}

export function polishTeamStats(rows: SeriesRow[]): TeamSeasonMetric[] {
  const out: TeamSeasonMetric[] = [];
  for (const row of rows) {
    const team = str(row.team);
    const season = str(row.season);
    if (!team || !season) continue;
    out.push({
      team,
      season,
      winRate: optionalNumber(row.winRate),
      pointsPerGame: optionalNumber(row.pointsPerGame),
      goalDifferencePerGame: optionalNumber(row.goalDifferencePerGame),
    });
  }
  return out;
}

type EvolutionRow = Record<string, string | number>;

/**
 * Pivot flat team-season metrics for Chart. Series keys are deterministic and
 * independent from club names, while values stay comparable across formats.
 */
export function buildEvolutionData(
  stats: TeamSeasonMetric[],
  seasons: string[],
  teams: string[],
  metric: "winRate" | "goalDifferencePerGame",
): { data: EvolutionRow[]; series: Array<{ key: string; label: string }> } {
  const series = teams.map((team, index) => ({
    key: `team${index + 1}`,
    label: team,
  }));
  const byKey = new Map(
    stats.map((row) => [`${row.season}\u0000${row.team}`, row] as const),
  );
  const data = [...seasons].reverse().map((season) => {
    const point: EvolutionRow = { season };
    teams.forEach((team, index) => {
      const value = byKey.get(`${season}\u0000${team}`)?.[metric];
      if (value != null && Number.isFinite(value)) {
        point[`team${index + 1}`] = value;
      }
    });
    return point;
  });
  return { data, series };
}

export async function buildFootballTree(): Promise<UINode> {
  const seasonsRaw = await fetchData("/v1/football/league/seasons", {});
  const seasons = recentSeasons(asRows(seasonsRaw), 5);
  const latestSeason = seasons[0];

  if (!latestSeason) {
    return {
      id: "destino-football",
      type: "Stack",
      title: FOOTBALL_QUERY,
      props: { gap: "md", destinationId: FOOTBALL_DESTINATION_ID },
      children: [],
    };
  }

  const standingsRaw = await fetchData("/v1/football/league/standings", {
    season: latestSeason,
  });
  const standings = polishStandings(asRows(standingsRaw));
  // The analytical endpoint intentionally caps comparisons at two teams.
  const leaders = leadingTeams(standings, 2);
  const teamNames = leaders.map((row) => row.team);

  const statsRaw =
    teamNames.length && seasons.length
      ? await fetchData("/v1/football/league/team-stats", {
          teams: teamNames.join("|"),
          seasons: seasons.join("|"),
        })
      : [];
  const stats = polishTeamStats(asRows(statsRaw));
  const winEvolution = buildEvolutionData(
    stats,
    seasons,
    teamNames,
    "winRate",
  );
  const goalEvolution = buildEvolutionData(
    stats,
    seasons,
    teamNames,
    "goalDifferencePerGame",
  );

  const leader = standings[0];
  const children: UINode[] = [];

  if (leader) {
    children.push({
      id: "football-leader-metrics",
      type: "MetricRow",
      title: `Líder — temporada ${latestSeason}`,
      props: {
        items: [
          { label: "Equipo", value: leader.team },
          { label: "Puntos", value: leader.points ?? "—" },
          { label: "Jugados", value: leader.played ?? "—" },
          { label: "Diferencia de gol", value: leader.goalDifference ?? "—" },
        ],
      },
    });
  }

  children.push({
    id: "football-standings",
    type: "ComparisonTable",
    title: `Liga Profesional — tabla ${latestSeason}`,
    props: {
      columns: [
        { key: "rank", label: "#", kind: "number" },
        { key: "team", label: "Equipo", primary: true },
        { key: "played", label: "PJ", kind: "number" },
        { key: "won", label: "G", kind: "number" },
        { key: "drawn", label: "E", kind: "number" },
        { key: "lost", label: "P", kind: "number" },
        { key: "goalDifference", label: "DG", kind: "number" },
        { key: "points", label: "Pts", kind: "number" },
      ],
      highlight: { key: "points", direction: "max" },
      data: standings,
    },
  });

  if (winEvolution.data.some((row) => Object.keys(row).length > 1)) {
    children.push({
      id: "football-win-rate-history",
      type: "Chart",
      title: "Evolución de los dos primeros — porcentaje de triunfos",
      props: {
        kind: "line",
        xKey: "season",
        series: winEvolution.series,
        data: winEvolution.data,
      },
    });
  }

  if (goalEvolution.data.some((row) => Object.keys(row).length > 1)) {
    children.push({
      id: "football-goal-difference-history",
      type: "Chart",
      title: "Evolución de los dos primeros — diferencia de gol por partido",
      props: {
        kind: "line",
        xKey: "season",
        series: goalEvolution.series,
        data: goalEvolution.data,
      },
    });
  }

  return {
    id: "destino-football",
    type: "Stack",
    title: FOOTBALL_QUERY,
    props: { gap: "md", destinationId: FOOTBALL_DESTINATION_ID },
    children,
  };
}

export function isFootballDestination(
  tree: UINode | null | undefined,
): boolean {
  if (!tree) return false;
  if (tree.title === FOOTBALL_QUERY) return true;
  return tree.props?.destinationId === FOOTBALL_DESTINATION_ID;
}
