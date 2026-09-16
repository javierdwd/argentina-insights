import assert from "node:assert/strict";
import test from "node:test";
import { pivotLongSeries } from "./chart-series";

test("pivotLongSeries turns team-season metrics into chart columns", () => {
  const rows = pivotLongSeries(
    [
      { season: "2023", team: "River Plate", pointsPerGame: 2.1 },
      { season: "2023", team: "Boca Juniors", pointsPerGame: 1.6 },
      { season: "2024", team: "River Plate", pointsPerGame: 1.9 },
      { season: "2024", team: "Boca Juniors", pointsPerGame: 2.0 },
    ],
    "season",
    "team",
    "pointsPerGame",
    [{ key: "River Plate" }, { key: "Boca Juniors" }],
  );

  assert.deepEqual(rows, [
    { season: "2023", "River Plate": 2.1, "Boca Juniors": 1.6 },
    { season: "2024", "River Plate": 1.9, "Boca Juniors": 2.0 },
  ]);
});

test("pivotLongSeries leaves wide data unchanged without long-format props", () => {
  const rows = [{ season: "2024", River: 2.1 }];
  assert.equal(
    pivotLongSeries(rows, "season", undefined, undefined, [{ key: "River" }]),
    rows,
  );
});
