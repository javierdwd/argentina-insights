import type { DestinationId } from "./destinations";

const CHAT_INTENT_KEY = "argentina-insights.chat-intent.v1";

export type ChatIntent =
  | { type: "query"; query: string }
  | { type: "destination"; destinationId: DestinationId };

function isDestinationId(value: unknown): value is DestinationId {
  return (
    value === "economia" ||
    value === "politica" ||
    value === "cine" ||
    value === "football"
  );
}

export function parseChatIntent(raw: string | null): ChatIntent | null {
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    const record = value as Record<string, unknown>;
    if (
      record.type === "query" &&
      typeof record.query === "string" &&
      record.query.trim()
    ) {
      return { type: "query", query: record.query.trim() };
    }
    if (
      record.type === "destination" &&
      isDestinationId(record.destinationId)
    ) {
      return {
        type: "destination",
        destinationId: record.destinationId,
      };
    }
  } catch {
    // Ignore malformed or unavailable browser storage.
  }
  return null;
}

export function saveChatIntent(intent: ChatIntent): void {
  try {
    sessionStorage.setItem(CHAT_INTENT_KEY, JSON.stringify(intent));
  } catch {
    // Navigation still works; /chat will open without an automatic action.
  }
}

export function takeChatIntent(): ChatIntent | null {
  try {
    const intent = parseChatIntent(sessionStorage.getItem(CHAT_INTENT_KEY));
    sessionStorage.removeItem(CHAT_INTENT_KEY);
    return intent;
  } catch {
    return null;
  }
}

export function clearChatIntent(): void {
  try {
    sessionStorage.removeItem(CHAT_INTENT_KEY);
  } catch {
    // Ignore unavailable browser storage.
  }
}
