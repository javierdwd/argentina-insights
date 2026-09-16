import assert from "node:assert/strict";
import test from "node:test";
import {
  buildEvolutionData,
  leadingTeams,
  polishStandings,
  polishTeamStats,
  recentSeasons,
} from "./football";

test("recentSeasons sorts descending and caps at five", () => {
  assert.deepEqual(
    recentSeasons([
      { season: "2021" },
      { season: "2024" },
      { season: "2023" },
      { season: 2022 },
      { season: "2025" },
      { season: "2020" },
      { season: "2024" },
    ]),
    ["2025", "2024", "2023", "2022", "2021"],
  );
});

test("standings and leaders are rank ordered and de-duplicated", () => {
  const standings = polishStandings([
    { team: "Segundo", rank: "2", points: "20" },
    { team: "Primero", rank: 1, points: 24 },
    { team: "", rank: 3 },
  ]);
  assert.deepEqual(
    standings.map((row) => [row.team, row.rank, row.points]),
    [
      ["Primero", 1, 24],
      ["Segundo", 2, 20],
    ],
  );
  assert.deepEqual(
    leadingTeams([...standings, { ...standings[0]!, rank: 3 }], 2).map(
      (row) => row.team,
    ),
    ["Primero", "Segundo"],
  );
});

test("evolution pivots normalized team metrics by season", () => {
  const stats = polishTeamStats([
    {
      team: "A",
      season: "2024",
      winRate: "55.5",
      goalDifferencePerGame: 0.7,
    },
    {
      team: "B",
      season: "2024",
      winRate: 48,
      goalDifferencePerGame: "0.2",
    },
    { team: "A", season: "2025", winRate: 60 },
  ]);
  const pivot = buildEvolutionData(
    stats,
    ["2025", "2024"],
    ["A", "B"],
    "winRate",
  );

  assert.deepEqual(pivot.series, [
    { key: "team1", label: "A" },
    { key: "team2", label: "B" },
  ]);
  assert.deepEqual(pivot.data, [
    { season: "2024", team1: 55.5, team2: 48 },
    { season: "2025", team1: 60 },
  ]);
});
