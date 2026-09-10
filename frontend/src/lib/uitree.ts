/**
 * UITree — generic node contract.
 *
 * Widget-specific Zod schemas live next to their components
 * (e.g. registry/Metric.schema.ts). This file only defines the
 * loose transport shape used by DynamicRenderer.
 */

import { z } from "zod";

export type UINode = {
  type: string;
  props?: Record<string, unknown>;
  children?: UINode[];
};

/** Loose schema for initial parse / transport validation. */
export const UINodeSchema = z.object({
  type: z.string(),
  props: z.record(z.string(), z.unknown()).optional(),
  // Children are unknown[] here; DynamicRenderer recurses at runtime.
  children: z.array(z.unknown()).optional(),
});
