import assert from "node:assert/strict";
import test from "node:test";
import { EMPTY_WORKSPACE, parseWorkspace } from "./workspace";

const tree = {
  type: "Callout",
  props: { title: "Inflación" },
};

test("migrates the previous canvas-only workspace", () => {
  const workspace = parseWorkspace(
    JSON.stringify({
      version: 1,
      lastCanvas: {
        uiTree: tree,
        query: "Inflación",
        savedAt: "2026-09-16T20:00:00.000Z",
      },
    }),
  );

  assert.equal(workspace.version, 2);
  assert.equal(workspace.threadId, null);
  assert.deepEqual(workspace.messages, []);
  assert.deepEqual(workspace.agentState, {});
  assert.deepEqual(workspace.lastCanvas?.uiTree, tree);
});

test("restores a complete active session", () => {
  const messages = [{ id: "m1", role: "user", content: "Inflación" }];
  const agentState = { ui_tree: tree, datasets: { inflation: [1, 2] } };
  const workspace = parseWorkspace(
    JSON.stringify({
      version: 2,
      threadId: "thread-1",
      messages,
      agentState,
      lastCanvas: {
        uiTree: tree,
        savedAt: "2026-09-16T20:00:00.000Z",
      },
    }),
  );

  assert.equal(workspace.threadId, "thread-1");
  assert.deepEqual(workspace.messages, messages);
  assert.deepEqual(workspace.agentState, agentState);
  assert.deepEqual(workspace.lastCanvas?.uiTree, tree);
});

test("rejects invalid persisted data", () => {
  assert.deepEqual(parseWorkspace("{"), EMPTY_WORKSPACE);
  assert.deepEqual(parseWorkspace(null), EMPTY_WORKSPACE);
});
