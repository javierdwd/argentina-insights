import assert from "node:assert/strict";
import test from "node:test";
import {
  filterRowsByRelativeRange,
  parseIsoDay,
  xKeyLooksDated,
} from "./chart-local-controls";
import {
  rowMatchesBrush,
  textMatchesBrush,
} from "../shell/canvas-brush";

test("parseIsoDay parses valid days", () => {
  assert.ok(parseIsoDay("2024-06-15")?.toISOString().startsWith("2024-06-15"));
  assert.equal(parseIsoDay("nope"), null);
});

test("xKeyLooksDated detects ISO x columns", () => {
  const rows = [
    { fecha: "2024-01-01", v: 1 },
    { fecha: "2024-01-02", v: 2 },
    { fecha: "2024-01-03", v: 3 },
  ];
  assert.equal(xKeyLooksDated(rows, "fecha"), true);
  assert.equal(xKeyLooksDated([{ fecha: "enero" }], "fecha"), false);
});

test("filterRowsByRelativeRange is relative to last dated point", () => {
  const rows = [
    { fecha: "2020-01-01", v: 1 },
    { fecha: "2023-06-01", v: 2 },
    { fecha: "2024-01-01", v: 3 },
    { fecha: "2024-06-01", v: 4 },
    { fecha: "2024-12-01", v: 5 },
  ];
  const oneYear = filterRowsByRelativeRange(rows, "fecha", "1Y");
  assert.deepEqual(
    oneYear.map((r) => r.fecha),
    ["2024-01-01", "2024-06-01", "2024-12-01"],
  );
  assert.equal(filterRowsByRelativeRange(rows, "fecha", "all").length, 5);
});

test("rowMatchesBrush matches fecha by day prefix", () => {
  const brush = { tipo: "fecha" as const, valor: "2024-06-15" };
  assert.equal(
    rowMatchesBrush({ fecha: "2024-06-15T12:00:00", blue: 1200 }, brush, {
      categoryKey: "fecha",
    }),
    true,
  );
  assert.equal(
    rowMatchesBrush({ fecha: "2024-06-16", blue: 1200 }, brush, {
      categoryKey: "fecha",
    }),
    false,
  );
});

test("textMatchesBrush ignores accents", () => {
  assert.equal(
    textMatchesBrush("Córdoba", { tipo: "provincia", valor: "Cordoba" }),
    true,
  );
  assert.equal(
    textMatchesBrush("José Pérez", { tipo: "persona", valor: "Jose Perez" }),
    true,
  );
});
