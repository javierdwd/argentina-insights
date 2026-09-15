import assert from "node:assert/strict";
import test from "node:test";
import {
  embedOffersInProse,
  parseChatActions,
  parseInlineButtons,
} from "./parse-chat-actions";

test("double-wrapped [boton] yields a clean label", () => {
  const raw =
    "[boton][boton]Mostrá la diferencia porcentual[/boton][/boton]\n" +
    "[boton][boton]Calculá rendimiento real[/boton][/boton]";
  const segments = parseInlineButtons(raw);
  const buttons = segments.filter((s) => s.type === "button");
  assert.deepEqual(
    buttons.map((s) => s.text),
    ["Mostrá la diferencia porcentual", "Calculá rendimiento real"],
  );
  assert.equal(
    segments.some((s) => s.type === "text" && /\[\/?boton\]/i.test(s.text)),
    false,
  );
});

test("bullet list of already-tagged offers is not wrapped again", () => {
  const prose =
    "Elegí una acción:\n" +
    "- [boton]Mostrá la diferencia porcentual[/boton]\n" +
    "- [boton]Calculá rendimiento real[/boton]";
  const out = embedOffersInProse(prose, []);
  assert.equal((out.match(/\[boton\]/g) ?? []).length, 2);
  assert.equal(out.includes("[boton][boton]"), false);
});

test("[[actions]] lines that already have [boton] are not double-tagged", () => {
  const raw =
    "En la pantalla verás la serie.\n\n" +
    "[[actions]]\n" +
    "[boton]Mostrá la diferencia porcentual[/boton]\n" +
    "[boton]Calculá rendimiento real[/boton]\n" +
    "[[/actions]]";
  const { prose, actions } = parseChatActions(raw);
  assert.deepEqual(actions, [
    "Mostrá la diferencia porcentual",
    "Calculá rendimiento real",
  ]);
  const out = embedOffersInProse(prose, actions);
  assert.equal(out.includes("[boton][boton]"), false);
  const buttons = parseInlineButtons(out).filter((s) => s.type === "button");
  assert.deepEqual(
    buttons.map((s) => s.text),
    ["Mostrá la diferencia porcentual", "Calculá rendimiento real"],
  );
});

test("fact bullets are not lifted into buttons", () => {
  const prose =
    "Analista — datos concretos obtenidos\n" +
    "- Día: 2020-05-22 — Oferta de canje de deuda\n" +
    "- Ventana usada: 2020-05-15 → 2020-05-29\n" +
    "- 2020-05-15: 138 ARS (venta)\n" +
    "- A la izquierda: el extracto de Wikipedia\n" +
    "- Mostrá la tabla con valores diarios\n" +
    "- Compará el blue con MEP y CCL";
  const out = embedOffersInProse(prose, []);
  const buttons = parseInlineButtons(out).filter((s) => s.type === "button");
  assert.deepEqual(
    buttons.map((s) => s.text),
    [
      "Mostrá la tabla con valores diarios",
      "Compará el blue con MEP y CCL",
    ],
  );
  assert.equal(out.includes("Día: 2020-05-22"), true);
  assert.equal(out.includes("A la izquierda:"), true);
});

test("[[actions]] fact lines are dropped", () => {
  const raw =
    "En pantalla: la semana del canje.\n\n" +
    "[[actions]]\n" +
    "Día: 2020-05-22 — Oferta de canje\n" +
    "Compará el blue con MEP y CCL\n" +
    "[[/actions]]";
  const { actions } = parseChatActions(raw);
  assert.deepEqual(actions, ["Compará el blue con MEP y CCL"]);
});

test("inline [[actions]] separators without a close tag become buttons", () => {
  const raw =
    "En pantalla queda la ficha de Javier Milei, con su partido.\n\n" +
    "Analizar reservas y dólar blue durante su mandato [[actions]] " +
    "Ver la confianza en el Gobierno durante su mandato [[actions]] " +
    "Comparar su mandato con los presidentes anteriores";
  const { prose, actions } = parseChatActions(raw);
  assert.equal(prose.includes("[[actions]]"), false);
  assert.equal(prose.includes("ficha de Javier Milei"), true);
  assert.deepEqual(actions, [
    "Analizar reservas y dólar blue durante su mandato",
    "Ver la confianza en el Gobierno durante su mandato",
    "Comparar su mandato con los presidentes anteriores",
  ]);
  const out = embedOffersInProse(prose, actions);
  assert.equal(out.includes("[[actions]]"), false);
  const buttons = parseInlineButtons(out).filter((s) => s.type === "button");
  assert.deepEqual(
    buttons.map((s) => s.text),
    [
      "Analizar reservas y dólar blue durante su mandato",
      "Ver la confianza en el Gobierno durante su mandato",
      "Comparar su mandato con los presidentes anteriores",
    ],
  );
});

test("unclosed [[actions]] block still yields buttons", () => {
  const raw =
    "En pantalla queda la ficha.\n\n" +
    "[[actions]]\n" +
    "Analizar reservas y dólar blue durante su mandato\n" +
    "Ver la confianza en el Gobierno durante su mandato\n" +
    "Comparar su mandato con los presidentes anteriores";
  const { prose, actions } = parseChatActions(raw);
  assert.equal(prose, "En pantalla queda la ficha.");
  assert.equal(prose.includes("[["), false);
  assert.deepEqual(actions, [
    "Analizar reservas y dólar blue durante su mandato",
    "Ver la confianza en el Gobierno durante su mandato",
    "Comparar su mandato con los presidentes anteriores",
  ]);
});
