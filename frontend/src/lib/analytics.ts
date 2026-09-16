"use client";

import { sendGAEvent } from "@next/third-parties/google";

type QueryStage = "initial" | "follow_up";

function queryLengthBucket(length: number): "short" | "medium" | "long" {
  if (length <= 40) return "short";
  if (length <= 120) return "medium";
  return "long";
}

export function trackQuerySubmitted(query: string, stage: QueryStage): void {
  sendGAEvent("event", "query_submitted", {
    query_stage: stage,
    query_length_bucket: queryLengthBucket(query.length),
  });
}

export function trackConversationReset(previousQueryCount: number): void {
  sendGAEvent("event", "conversation_reset", {
    previous_query_count: previousQueryCount,
  });
}
