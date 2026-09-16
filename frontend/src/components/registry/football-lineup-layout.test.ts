import assert from "node:assert/strict";
import test from "node:test";
import {
  fallbackFormation,
  formationPositions,
  parseFormation,
} from "./football-lineup-layout";

test("parseFormation accepts compact and dashed formations", () => {
  assert.deepEqual(parseFormation("433"), [4, 3, 3]);
  assert.deepEqual(parseFormation("4-2-3-1"), [4, 2, 3, 1]);
  assert.equal(parseFormation("4-4"), null);
  assert.equal(parseFormation("unknown"), null);
});

test("formation positions distribute rows and mirror both sides", () => {
  const home = formationPositions(11, "4-3-3", "home");
  const away = formationPositions(11, "433", "away");

  assert.equal(home.length, 11);
  assert.equal(home.filter((position) => position.line === 1).length, 4);
  assert.equal(home.filter((position) => position.line === 2).length, 3);
  assert.equal(home.filter((position) => position.line === 3).length, 3);
  home.forEach((position, index) => {
    assert.equal(away[index]?.x, position.x);
    assert.equal(away[index]?.y, 100 - position.y);
  });
});

test("invalid formations use broad deterministic rows", () => {
  assert.deepEqual(fallbackFormation(10), [4, 4, 2]);
  assert.deepEqual(
    formationPositions(11, "invalid", "home").map((position) => position.line),
    [0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3],
  );
});
