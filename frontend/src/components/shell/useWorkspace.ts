"use client";

import { useSyncExternalStore } from "react";
import {
  EMPTY_WORKSPACE,
  getWorkspace,
  subscribeWorkspace,
  type Workspace,
} from "@/lib/workspace";

function getServerSnapshot(): Workspace {
  return EMPTY_WORKSPACE;
}

/** Reactive localStorage workspace (views + last canvas). */
export function useWorkspace(): Workspace {
  return useSyncExternalStore(
    subscribeWorkspace,
    getWorkspace,
    getServerSnapshot,
  );
}

/** Skip canvas-selection turns when naming a saved view. */
export function lastUserQuery(
  messages: { role?: string; content?: unknown }[] | undefined,
): string | undefined {
  if (!messages?.length) return undefined;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "user") continue;
    const text = messageText(message.content);
    if (!text) continue;
    if (isFollowUpQuery(text)) continue;
    return text;
  }
  return undefined;
}

function isFollowUpQuery(text: string): boolean {
  return (
    text.startsWith("Seleccioné en el canvas:") ||
    text.startsWith("Profundizá ") ||
    text.startsWith("Quiero el detalle de ") ||
    text.startsWith("Quiero profundizar en ")
  );
}

export function messageText(content: unknown): string {
  if (typeof content === "string") return content.trim();
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part) {
          return String((part as { text?: unknown }).text ?? "");
        }
        return "";
      })
      .join("")
      .trim();
  }
  return "";
}
