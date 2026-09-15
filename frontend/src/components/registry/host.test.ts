import assert from "node:assert/strict";
import test from "node:test";
import {
  HOST_CLASS_VOCAB,
  HOST_TAGS,
  isHostType,
  isSvgHostType,
  sanitizeHostClass,
  sanitizeHostProps,
} from "./host";

test("sanitizeHostClass keeps vocab tokens and drops unknowns", () => {
  const out = sanitizeHostClass(
    "flex flex-col gap-4 bg-red-500 onClick text-muted-foreground",
  );
  assert.equal(out, "flex flex-col gap-4 text-muted-foreground");
});

test("sanitizeHostClass returns undefined for empty or all-illegal", () => {
  assert.equal(sanitizeHostClass(""), undefined);
  assert.equal(sanitizeHostClass("   "), undefined);
  assert.equal(sanitizeHostClass("bg-red-500 hover:underline"), undefined);
  assert.equal(sanitizeHostClass(null), undefined);
  assert.equal(sanitizeHostClass(42), undefined);
});

test("sanitizeHostClass preserves order of allowed tokens", () => {
  assert.equal(
    sanitizeHostClass("text-accent gap-6 flex"),
    "text-accent gap-6 flex",
  );
});

test("isHostType accepts allowlisted tags only", () => {
  for (const tag of HOST_TAGS) {
    assert.equal(isHostType(tag), true);
  }
  assert.equal(isHostType("button"), false);
  assert.equal(isHostType("img"), false);
  assert.equal(isHostType("a"), false);
  assert.equal(isHostType("Box"), false);
  assert.equal(isHostType("Chart"), false);
  assert.equal(isSvgHostType("svg"), true);
  assert.equal(isSvgHostType("path"), true);
  assert.equal(isSvgHostType("div"), false);
});

test("HOST_CLASS_VOCAB includes core bulletin layout tokens", () => {
  for (const token of [
    "flex",
    "flex-col",
    "grid",
    "grid-cols-2",
    "gap-4",
    "text-muted-foreground",
    "border-rule",
    "font-display",
    "tabular-nums",
  ] as const) {
    assert.ok(HOST_CLASS_VOCAB.has(token), `missing ${token}`);
  }
});

test("sanitizeHostProps keeps SVG geometry and drops handlers", () => {
  const out = sanitizeHostProps({
    className: "w-full h-8 text-accent",
    viewBox: "0 0 24 24",
    d: "M12 2 L12 20",
    stroke: "currentColor",
    fill: "none",
    "stroke-width": "2",
    markerEnd: "url(#arrow)",
    onClick: "alert(1)",
    dataRef: "ds_x",
    text: "ignored-here",
    href: "javascript:alert(1)",
  });
  assert.equal(out.className, "w-full h-8 text-accent");
  assert.equal(out.viewBox, "0 0 24 24");
  assert.equal(out.d, "M12 2 L12 20");
  assert.equal(out.stroke, "currentColor");
  assert.equal(out.fill, "none");
  assert.equal(out.strokeWidth, "2");
  assert.equal(out.markerEnd, "url(#arrow)");
  assert.equal("onClick" in out, false);
  assert.equal("dataRef" in out, false);
  assert.equal("text" in out, false);
  assert.equal("href" in out, false);
});

test("sanitizeHostProps rejects unsafe paint and paths", () => {
  const out = sanitizeHostProps({
    fill: "url(javascript:alert(1))",
    d: "<script>alert(1)</script>",
    stroke: "red",
  });
  assert.equal(out.fill, undefined);
  assert.equal(out.d, undefined);
  assert.equal(out.stroke, undefined);
});
