import assert from "node:assert/strict";
import test from "node:test";
import {
  factsFromCategoryRow,
  inferCanvasTipo,
  looksLikePersonName,
} from "./infer-canvas-tipo.ts";

test("looksLikePersonName matches Spanish compound names", () => {
  assert.equal(looksLikePersonName("Javier Milei"), true);
  assert.equal(looksLikePersonName("Cristina Fernández de Kirchner"), true);
  assert.equal(looksLikePersonName("Alberto Fernández"), true);
  assert.equal(looksLikePersonName("Mauricio Macri"), true);
});

test("looksLikePersonName rejects series and codes", () => {
  assert.equal(looksLikePersonName("Dólar blue"), false);
  assert.equal(looksLikePersonName("AFIRMATIVO"), false);
  assert.equal(looksLikePersonName("Milei"), false);
  assert.equal(looksLikePersonName("2023-12-10"), false);
});

test("inferCanvasTipo prefers selectAs then row.entity", () => {
  assert.equal(
    inferCanvasTipo({
      valor: "Santa Fe",
      selectAs: "persona",
    }),
    "persona",
  );
  assert.equal(
    inferCanvasTipo({
      valor: "Milei",
      row: { entity: "persona", label: "Milei" },
    }),
    "persona",
  );
});

test("inferCanvasTipo uses column keys, not president-specific logic", () => {
  assert.equal(
    inferCanvasTipo({ valor: "Juan Pérez", categoryKey: "diputado" }),
    "persona",
  );
  assert.equal(
    inferCanvasTipo({ valor: "Córdoba", categoryKey: "provincia" }),
    "provincia",
  );
  assert.equal(
    inferCanvasTipo({ valor: "2024-05-01", categoryKey: "fecha" }),
    "fecha",
  );
});

test("inferCanvasTipo treats province labels as provinces, people as people", () => {
  assert.equal(inferCanvasTipo({ valor: "Santa Fe" }), "provincia");
  assert.equal(inferCanvasTipo({ valor: "Javier Milei" }), "persona");
  assert.equal(
    inferCanvasTipo({
      valor: "Milei",
      row: { label: "Milei", partido: "LLA", value: 1555 },
    }),
    "persona",
  );
  assert.equal(inferCanvasTipo({ valor: "UCR" }), "fila");
});

test("inferCanvasTipo does not treat photo-only rows or poster URLs as personas", () => {
  assert.equal(
    inferCanvasTipo({
      valor: "https://image.tmdb.org/t/p/w500/a.jpg",
      row: { foto: "https://image.tmdb.org/t/p/w500/a.jpg", titulo: "X" },
      categoryKey: "foto",
    }),
    "fila",
  );
  assert.equal(
    inferCanvasTipo({
      valor: "La ciénaga",
      row: {
        foto: "https://image.tmdb.org/t/p/w500/a.jpg",
        titulo: "La ciénaga",
        valor: 7.1,
      },
      categoryKey: "titulo",
    }),
    "fila",
  );
  assert.equal(
    inferCanvasTipo({
      valor: "Milei",
      row: { label: "Milei", partido: "LLA", foto: "https://x.test/m.jpg" },
    }),
    "persona",
  );
});

test("factsFromCategoryRow skips entity and photo keys", () => {
  const facts = factsFromCategoryRow(
    {
      label: "Javier Milei",
      value: 1555,
      sublabel: "2023-12-10 → hoy",
      partido: "LLA",
      entity: "persona",
      imagen: "https://example.com/m.jpg",
    },
    { skip: ["label"] },
  );
  const byLabel = Object.fromEntries(facts.map((f) => [f.label, f.value]));
  assert.equal(byLabel.Valor, "1.555");
  assert.equal(byLabel.Período, "2023-12-10 → hoy");
  assert.equal(byLabel.Partido, "LLA");
  assert.equal(byLabel.entity, undefined);
  assert.equal(byLabel.imagen, undefined);
});
