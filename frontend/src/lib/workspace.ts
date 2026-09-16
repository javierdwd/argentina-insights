/** Browser-only persistence for the last canvas. */

import type { UINode } from "./uitree";

export const WORKSPACE_KEY = "argentina-insights.workspace.v1";
export const WORKSPACE_EVENT = "argentina-insights:workspace";

export type WorkspaceLastCanvas = {
  uiTree: UINode;
  query?: string;
  savedAt: string;
};

export type Workspace = {
  version: 1;
  lastCanvas: WorkspaceLastCanvas | null;
};

export const EMPTY_WORKSPACE: Workspace = {
  version: 1,
  lastCanvas: null,
};

function nowIso(): string {
  return new Date().toISOString();
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function isUiNode(value: unknown): value is UINode {
  return isRecord(value) && typeof value.type === "string" && value.type.length > 0;
}

function parseLastCanvas(value: unknown): WorkspaceLastCanvas | null {
  if (!isRecord(value) || !isUiNode(value.uiTree)) return null;
  const savedAt = asString(value.savedAt);
  if (!savedAt) return null;
  return {
    uiTree: value.uiTree,
    query: asString(value.query),
    savedAt,
  };
}

export function parseWorkspace(raw: string | null): Workspace {
  if (!raw) return EMPTY_WORKSPACE;
  try {
    const data: unknown = JSON.parse(raw);
    if (!isRecord(data)) return EMPTY_WORKSPACE;
    return {
      version: 1,
      lastCanvas: parseLastCanvas(data.lastCanvas),
    };
  } catch {
    return EMPTY_WORKSPACE;
  }
}

let cachedRaw: string | null | undefined;
let cachedValue: Workspace = EMPTY_WORKSPACE;

function readRaw(): string | null {
  try {
    return localStorage.getItem(WORKSPACE_KEY);
  } catch {
    return null;
  }
}

export function getWorkspace(): Workspace {
  if (typeof window === "undefined") return EMPTY_WORKSPACE;
  const raw = readRaw();
  if (raw === cachedRaw) return cachedValue;
  cachedRaw = raw;
  cachedValue = parseWorkspace(raw);
  return cachedValue;
}

function notify(): void {
  cachedRaw = undefined;
  window.dispatchEvent(new Event(WORKSPACE_EVENT));
}

function write(next: Workspace): boolean {
  const normalized: Workspace = {
    version: 1,
    lastCanvas: next.lastCanvas,
  };
  const attempts: Workspace[] = [normalized];
  if (normalized.lastCanvas) {
    attempts.push({ ...normalized, lastCanvas: null });
  }
  for (const candidate of attempts) {
    try {
      localStorage.setItem(WORKSPACE_KEY, JSON.stringify(candidate));
      notify();
      return candidate === normalized;
    } catch {
      // Quota or private-mode write failure — try a smaller payload.
    }
  }
  return false;
}

function update(mutator: (current: Workspace) => Workspace): boolean {
  return write(mutator(getWorkspace()));
}

export function saveLastCanvas(uiTree: UINode, query?: string): boolean {
  if (!isUiNode(uiTree)) return false;
  return update((current) => ({
    ...current,
    lastCanvas: {
      uiTree: cloneJson(uiTree),
      query: query?.trim() || undefined,
      savedAt: nowIso(),
    },
  }));
}

export function clearLastCanvas(): void {
  try {
    localStorage.removeItem(WORKSPACE_KEY);
    notify();
  } catch {
    write(EMPTY_WORKSPACE);
  }
}

export function subscribeWorkspace(onStoreChange: () => void): () => void {
  const onChange = () => {
    cachedRaw = undefined;
    onStoreChange();
  };
  window.addEventListener(WORKSPACE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(WORKSPACE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}
