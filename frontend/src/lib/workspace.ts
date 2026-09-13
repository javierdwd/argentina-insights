/**
 * Browser-only workspace: saved views + last canvas.
 * No login / no backend — localStorage on this origin.
 */

import type { UINode } from "./uitree";

export const WORKSPACE_KEY = "argentina-insights.workspace.v1";
export const WORKSPACE_EVENT = "argentina-insights:workspace";

const MAX_VIEWS = 8;

export type WorkspaceView = {
  id: string;
  title: string;
  query?: string;
  uiTree: UINode;
  createdAt: string;
};

export type WorkspaceLastCanvas = {
  uiTree: UINode;
  query?: string;
  savedAt: string;
};

export type Workspace = {
  version: 1;
  views: WorkspaceView[];
  lastCanvas: WorkspaceLastCanvas | null;
};

export const EMPTY_WORKSPACE: Workspace = {
  version: 1,
  views: [],
  lastCanvas: null,
};

export function compactTitle(text: string, max = 88): string {
  const trimmed = text.replace(/\s+/g, " ").trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1).trimEnd()}…`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function newId(): string {
  return crypto.randomUUID();
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

function parseView(value: unknown): WorkspaceView | null {
  if (!isRecord(value)) return null;
  const id = asString(value.id);
  const title = asString(value.title);
  const createdAt = asString(value.createdAt);
  if (!id || !title || !createdAt || !isUiNode(value.uiTree)) return null;
  return {
    id,
    title,
    query: asString(value.query),
    uiTree: value.uiTree,
    createdAt,
  };
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
    const views = Array.isArray(data.views)
      ? data.views.map(parseView).filter((v): v is WorkspaceView => v !== null)
      : [];
    // Legacy `pins` in older localStorage payloads are ignored.
    return {
      version: 1,
      views: views.slice(0, MAX_VIEWS),
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
    views: next.views.slice(0, MAX_VIEWS),
    lastCanvas: next.lastCanvas,
  };
  const payload = JSON.stringify(normalized);
  const attempts: Workspace[] = [normalized];
  if (normalized.lastCanvas) {
    attempts.push({ ...normalized, lastCanvas: null });
  }
  if (normalized.views.length > 0) {
    attempts.push({
      ...normalized,
      lastCanvas: null,
      views: normalized.views.slice(0, -1),
    });
  }
  for (const candidate of attempts) {
    try {
      localStorage.setItem(WORKSPACE_KEY, JSON.stringify(candidate));
      notify();
      return candidate === normalized || JSON.stringify(candidate) === payload;
    } catch {
      // Quota or private-mode write failure — try a smaller payload.
    }
  }
  return false;
}

function update(mutator: (current: Workspace) => Workspace): boolean {
  return write(mutator(getWorkspace()));
}

export function saveView(input: {
  title: string;
  uiTree: UINode;
  query?: string;
}): WorkspaceView | null {
  const title = compactTitle(input.title);
  if (!title || !isUiNode(input.uiTree)) return null;
  const query = input.query?.trim() || undefined;
  let saved: WorkspaceView | null = null;
  update((current) => {
    const existing = query
      ? current.views.find((view) => view.query === query)
      : undefined;
    const view: WorkspaceView = {
      id: existing?.id ?? newId(),
      title,
      query,
      uiTree: cloneJson(input.uiTree),
      createdAt: nowIso(),
    };
    saved = view;
    const rest = current.views.filter((item) => item.id !== view.id);
    return { ...current, views: [view, ...rest] };
  });
  return saved;
}

export function removeView(id: string): void {
  update((current) => ({
    ...current,
    views: current.views.filter((view) => view.id !== id),
  }));
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
  update((current) => ({ ...current, lastCanvas: null }));
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
