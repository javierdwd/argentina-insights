import assert from "node:assert/strict";
import test from "node:test";
import {
  foldImageColumns,
  inferColumnKind,
  looksLikeImageUrl,
  pickListSelectionLead,
} from "./list-cell.ts";

test("looksLikeImageUrl matches common image paths", () => {
  assert.equal(
    looksLikeImageUrl(
      "https://api.argentinadatos.com/static/presidentes/justo-jose-de-urquiza.jpg",
    ),
    true,
  );
  assert.equal(
    looksLikeImageUrl("https://upload.wikimedia.org/foo/bar.png?w=200"),
    true,
  );
  assert.equal(looksLikeImageUrl("https://senado.gob.ar/senadores/1"), false);
  assert.equal(looksLikeImageUrl("Partido Unitario"), false);
});

test("inferColumnKind uses imagen/foto keys without president-specific logic", () => {
  assert.equal(inferColumnKind({ key: "imagen" }), "image");
  assert.equal(inferColumnKind({ key: "foto" }), "image");
  assert.equal(inferColumnKind({ key: "photoUrl" }), "image");
  assert.equal(inferColumnKind({ key: "partido" }), "text");
});

test("inferColumnKind uses values when the key is generic", () => {
  const data = [
    { media: "https://cdn.example.com/a.webp" },
    { media: "https://cdn.example.com/b.webp" },
  ];
  assert.equal(inferColumnKind({ key: "media" }, data), "image");
  assert.equal(
    inferColumnKind({ key: "media", kind: "url" }, data),
    "url",
  );
});

test("foldImageColumns drops the photo URL column next to a name", () => {
  const out = foldImageColumns(
    [
      { key: "nombre", label: "Nombre" },
      { key: "imagen", label: "Imagen" },
      { key: "partido", label: "Partido" },
    ],
    [{ nombre: "Urquiza", imagen: "https://x.test/u.jpg", partido: "Federal" }],
  );
  assert.deepEqual(
    out.columns.map((c) => c.key),
    ["nombre", "partido"],
  );
  assert.equal(out.imageKey, "imagen");
  assert.equal(out.nameKey, "nombre");
});

test("foldImageColumns folds poster into titulo for film lists", () => {
  const out = foldImageColumns(
    [
      { key: "foto", label: "Foto" },
      { key: "titulo", label: "Título" },
      { key: "valor", label: "Rating" },
    ],
    [
      {
        foto: "https://image.tmdb.org/t/p/w500/a.jpg",
        titulo: "Nueve reinas",
        valor: 7.8,
      },
    ],
  );
  assert.deepEqual(
    out.columns.map((c) => c.key),
    ["titulo", "valor"],
  );
  assert.equal(out.imageKey, "foto");
  assert.equal(out.nameKey, "titulo");
});

test("pickListSelectionLead prefers titulo over poster URL", () => {
  const lead = pickListSelectionLead(
    {
      foto: "https://image.tmdb.org/t/p/w500/hxt.jpg",
      titulo: "La ciénaga",
      valor: 7.1,
    },
    [
      { key: "foto", label: "Foto" },
      { key: "titulo", label: "Título" },
      { key: "valor", label: "Rating" },
    ],
    undefined,
    (v) => (v == null || v === "" ? "" : String(v)),
  );
  assert.ok(lead);
  assert.equal(lead!.valor, "La ciénaga");
  assert.equal(lead!.key, "titulo");
  assert.equal(lead!.imageUrl, "https://image.tmdb.org/t/p/w500/hxt.jpg");
});
