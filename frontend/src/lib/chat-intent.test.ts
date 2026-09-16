import assert from "node:assert/strict";
import test from "node:test";
import { parseChatIntent } from "./chat-intent";

test("parses and trims a pending query", () => {
  assert.deepEqual(
    parseChatIntent(JSON.stringify({ type: "query", query: "  inflación  " })),
    { type: "query", query: "inflación" },
  );
});

test("parses a known destination", () => {
  assert.deepEqual(
    parseChatIntent(
      JSON.stringify({ type: "destination", destinationId: "economia" }),
    ),
    { type: "destination", destinationId: "economia" },
  );
});

test("rejects malformed and unknown intents", () => {
  assert.equal(parseChatIntent("{"), null);
  assert.equal(
    parseChatIntent(
      JSON.stringify({ type: "destination", destinationId: "unknown" }),
    ),
    null,
  );
  assert.equal(
    parseChatIntent(JSON.stringify({ type: "query", query: "  " })),
    null,
  );
});
