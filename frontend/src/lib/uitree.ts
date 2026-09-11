/**
 * UITree — generic node contract.
 *
 * Widget-specific Zod schemas live next to their components
 * (e.g. registry/Chart.schema.ts). This file defines the shared
 * transport shape used by DynamicRenderer.
 *
 * Node-level fields:
 *   id      — stable key used by React and for mutation tracking
 *   type    — registry key (Chart, Metric, Text, Stack, …)
 *   title   — heading rendered by DynamicRenderer ABOVE the component.
 *             Universal across all widget types; no widget implements its own.
 *   props   — widget-specific props (validated per-type by NODE_SCHEMAS)
 *   children — for container widgets (Stack, Grid, …)
 */

export type UINode = {
  id: string;
  type: string;
  title?: string;
  props?: Record<string, unknown>;
  children?: UINode[];
};
