import assert from "node:assert/strict";
import test from "node:test";
import { withAutoDualAxis } from "./chart-scale.ts";
import {
  resolveChartSeries,
  trimEmptyMeasureEdges,
} from "./chart-series.ts";
import {
  pivotCategoryVoteCounts,
  seriesLookLikeVotes,
  sortVoteCategoryRows,
} from "./vote-pivot.ts";

test("withAutoDualAxis puts % scale on the right when vs ARS", () => {
  const data = [
    { fecha: "2026-01", blue: 1400, inflacion: 80 },
    { fecha: "2026-02", blue: 1500, inflacion: 70 },
    { fecha: "2026-03", blue: 1450, inflacion: 60 },
  ];
  const out = withAutoDualAxis(
    [
      { key: "blue", label: "Blue" },
      { key: "inflacion", label: "Inflación" },
    ],
    data,
  );
  assert.equal(out[0]?.yAxisIndex, undefined);
  assert.equal(out[1]?.yAxisIndex, 1);
});

test("withAutoDualAxis leaves similar magnitudes on one axis", () => {
  const data = [
    { fecha: "a", blue: 1400, mep: 1380 },
    { fecha: "b", blue: 1500, mep: 1490 },
  ];
  const out = withAutoDualAxis(
    [
      { key: "blue", label: "Blue" },
      { key: "mep", label: "MEP" },
    ],
    data,
  );
  assert.equal(out[0]?.yAxisIndex, undefined);
  assert.equal(out[1]?.yAxisIndex, undefined);
});

test("withAutoDualAxis respects explicit dual axis", () => {
  const data = [
    { a: 100, b: 1 },
    { a: 200, b: 2 },
  ];
  const out = withAutoDualAxis(
    [
      { key: "a", label: "A", yAxisIndex: 0 as const },
      { key: "b", label: "B", yAxisIndex: 1 as const },
    ],
    data,
  );
  assert.equal(out[1]?.yAxisIndex, 1);
});

test("withAutoDualAxis keeps period overlays on one axis", () => {
  const data = [
    { fecha: "2016-01-01", mauricio_macri: 15, alberto_fernandez: null, javier_milei: null },
    { fecha: "2018-01-01", mauricio_macri: 40, alberto_fernandez: null, javier_milei: null },
    { fecha: "2021-01-01", mauricio_macri: null, alberto_fernandez: 150, javier_milei: null },
    { fecha: "2023-06-01", mauricio_macri: null, alberto_fernandez: 800, javier_milei: null },
    { fecha: "2024-06-01", mauricio_macri: null, alberto_fernandez: null, javier_milei: 1200 },
    { fecha: "2025-09-01", mauricio_macri: null, alberto_fernandez: null, javier_milei: 1400 },
  ];
  const out = withAutoDualAxis(
    [
      { key: "mauricio_macri", label: "Mauricio Macri" },
      { key: "alberto_fernandez", label: "Alberto Fernández" },
      { key: "javier_milei", label: "Javier Milei" },
    ],
    data,
  );
  assert.equal(out[0]?.yAxisIndex, undefined);
  assert.equal(out[1]?.yAxisIndex, undefined);
  assert.equal(out[2]?.yAxisIndex, undefined);
});

test("resolveChartSeries maps fernandez onto accent-stripped slug", () => {
  const series = resolveChartSeries(
    [
      { key: "mauricio_macri", label: "Mauricio Macri" },
      { key: "alberto_fernandez", label: "Alberto Fernández" },
      { key: "javier_milei", label: "Javier Milei" },
    ],
    [
      {
        fecha: "2020-01-01",
        mauricio_macri: null,
        alberto_fern_ndez: 80,
        javier_milei: null,
      },
    ],
  );
  assert.equal(series[1]?.key, "alberto_fern_ndez");
});

test("trimEmptyMeasureEdges drops leading empty years", () => {
  const trimmed = trimEmptyMeasureEdges(
    [
      { fecha: "2011-01-01", mauricio_macri: null, javier_milei: null },
      { fecha: "2012-01-01", mauricio_macri: null, javier_milei: null },
      { fecha: "2016-01-01", mauricio_macri: 15, javier_milei: null },
      { fecha: "2024-01-01", mauricio_macri: null, javier_milei: 1200 },
    ],
    ["mauricio_macri", "javier_milei"],
  );
  assert.equal(trimmed[0]?.fecha, "2016-01-01");
});

test("pivotCategoryVoteCounts counts votos per bloque", () => {
  const rows = pivotCategoryVoteCounts(
    [
      { nombre: "A", voto: "afirmativo", bloque: "UCR" },
      { nombre: "B", voto: "AFIRMATIVO", bloque: "UCR" },
      { nombre: "C", voto: "negativo", bloque: "UCR" },
      { nombre: "D", voto: "negativo", bloque: "LLA" },
      { nombre: "E", voto: "ausente", bloque: "LLA" },
    ],
    "bloque",
    [
      { key: "afirmativo" },
      { key: "negativo" },
      { key: "abstencion" },
      { key: "ausente" },
    ],
  );
  assert.ok(rows);
  const byBlock = Object.fromEntries(rows.map((r) => [r.bloque, r]));
  assert.equal(byBlock.UCR?.afirmativo, 2);
  assert.equal(byBlock.UCR?.negativo, 1);
  assert.equal(byBlock.LLA?.negativo, 1);
  assert.equal(byBlock.LLA?.ausente, 1);
  assert.equal(byBlock.LLA?.afirmativo, 0);
});

test("pivotCategoryVoteCounts leaves numeric series alone", () => {
  const out = pivotCategoryVoteCounts(
    [
      { fecha: "2026-01-01", venta: 1400 },
      { fecha: "2026-01-02", venta: 1410 },
    ],
    "fecha",
    [{ key: "venta" }],
  );
  assert.equal(out, null);
});

test("sortVoteCategoryRows ranks by negativos", () => {
  const sorted = sortVoteCategoryRows(
    [
      { bloque: "UCR", negativo: 1, afirmativo: 4 },
      { bloque: "LLA", negativo: 3, afirmativo: 0 },
    ],
    [{ key: "afirmativo" }, { key: "negativo" }],
  );
  assert.equal(sorted[0]?.bloque, "LLA");
  assert.ok(seriesLookLikeVotes([{ key: "afirmativo" }, { key: "negativo" }]));
});
