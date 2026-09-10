/**
 * Home page — scaffold proof-of-concept.
 *
 * Renders a hard-coded UITree with a single Metric node to confirm the
 * pipeline: UINode → DynamicRenderer → Metric.
 *
 * The agent will replace this with a dynamically generated tree once
 * the CopilotKit ↔ LangGraph integration is wired up.
 */

import { DynamicRenderer } from "@/components/registry/DynamicRenderer";
import type { UINode } from "@/lib/uitree";

// Sample tree: a single Metric for the Blue Dollar spot rate.
const SAMPLE_TREE: UINode = {
  type: "Metric",
  props: {
    label: "Blue Dollar",
    value: 1250.5,
    unit: "ARS/USD",
    delta: 1.8,
    trend: "up",
  },
};

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8 bg-background">
      <div className="text-center space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Argentina Insights</h1>
        <p className="text-sm text-muted-foreground">
          Scaffold — DynamicRenderer + Metric widget proof of concept
        </p>
      </div>

      <DynamicRenderer node={SAMPLE_TREE} />
    </main>
  );
}
