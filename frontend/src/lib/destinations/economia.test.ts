/** Unit tests for Economía destination helpers (no network). */

import assert from "node:assert/strict";
import test from "node:test";
import {
  alignBlueOficial,
  isEconomiaDestination,
} from "./economia-shared";
import type { UINode } from "../uitree";

test("alignBlueOficial joins by fecha and drops non-overlap", () => {
  const rows = alignBlueOficial(
    [
      { fecha: "2026-01-01", venta: 1400 },
      { fecha: "2026-01-02", venta: 1410 },
      { fecha: "2026-01-03", venta: 1420 },
    ],
    [
      { fecha: "2026-01-02", venta: 1000 },
      { fecha: "2026-01-03", venta: 1010 },
    ],
  );
  assert.deepEqual(rows, [
    { fecha: "2026-01-02", blue: 1410, oficial: 1000 },
    { fecha: "2026-01-03", blue: 1420, oficial: 1010 },
  ]);
});

test("isEconomiaDestination matches title or destinationId", () => {
  assert.equal(
    isEconomiaDestination({
      id: "a",
      type: "Stack",
      title: "Economía",
    }),
    true,
  );
  assert.equal(
    isEconomiaDestination({
      id: "b",
      type: "Stack",
      props: { destinationId: "economia" },
    } as UINode),
    true,
  );
  assert.equal(
    isEconomiaDestination({ id: "c", type: "Stack", title: "Otro" }),
    false,
  );
});
