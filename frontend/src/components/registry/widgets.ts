import type { ComponentType } from "react";
import type { z } from "zod";
import { Chart } from "./Chart";
import { ChartNodeSchema } from "./Chart.schema";
import { List } from "./List";
import { ListNodeSchema } from "./List.schema";
import { Metric } from "./Metric";
import { MetricNodeSchema } from "./Metric.schema";
import { PersonCard } from "./PersonCard";
import { PersonCardNodeSchema } from "./PersonCard.schema";
import { Stack } from "./Stack";
import { StackNodeSchema } from "./Stack.schema";
import { Text } from "./Text";
import { TextNodeSchema } from "./Text.schema";

/**
 * Component registry — map UITree `type` → React component.
 *
 * To add a new widget:
 *   1. Create <Name>.tsx and <Name>.schema.ts next to this file.
 *   2. Add one line to REGISTRY and one line to NODE_SCHEMAS.
 *   3. Add a WidgetDef to agent/src/agent/ui/catalog.py.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const REGISTRY: Record<string, ComponentType<any>> = {
  Chart,
  List,
  Metric,
  PersonCard,
  Stack,
  Text,
};

/**
 * Per-type Zod node schemas — used by DynamicRenderer for props validation.
 */
export const NODE_SCHEMAS = {
  Chart: ChartNodeSchema,
  List: ListNodeSchema,
  Metric: MetricNodeSchema,
  PersonCard: PersonCardNodeSchema,
  Stack: StackNodeSchema,
  Text: TextNodeSchema,
} as const satisfies Record<string, z.ZodType>;
