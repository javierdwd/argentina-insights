/** Unit tests for Política / Cine destination helpers (no network). */

import assert from "node:assert/strict";
import test from "node:test";
import { latestActas, polishDiscover } from "./shared.ts";

test("latestActas sorts newest first and caps", () => {
  const rows = latestActas(
    [
      { actaId: 1, titulo: "Vieja", fecha: "2025-01-01", resultado: "AFIRMATIVA" },
      { actaId: 2, titulo: "Nueva", fecha: "2025-06-01", resultado: "NEGATIVA" },
      { actaId: 3, titulo: "Media", fecha: "2025-03-01", resultado: "AFIRMATIVA" },
    ],
    2,
  );
  assert.equal(rows.length, 2);
  assert.equal(rows[0]?.titulo, "Nueva");
  assert.equal(rows[1]?.titulo, "Media");
});

test("polishDiscover drops future releases and prefers vote mass", () => {
  const rows = polishDiscover(
    [
      { id: 1, titulo: "Futura", fecha: "2099-01-01", valor: 9, votos: 9999, foto: "https://x/a.jpg" },
      { id: 2, titulo: "Clásico", fecha: "2014-08-21", valor: 7.8, votos: 500, foto: "https://x/b.jpg" },
      { id: 3, titulo: "Nicho", fecha: "2020-01-01", valor: 8.5, votos: 10 },
    ],
    "2026-09-13",
    10,
  );
  assert.equal(rows.length, 2);
  assert.equal(rows[0]?.titulo, "Clásico");
  assert.equal(rows[1]?.titulo, "Nicho");
});
