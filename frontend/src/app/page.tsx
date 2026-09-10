/**
 * Home — Cold bulletin shell + sample Metric via DynamicRenderer.
 */

import { DynamicRenderer } from "@/components/registry/DynamicRenderer";
import { HomeStage } from "@/components/shell/HomeStage";
import type { UINode } from "@/lib/uitree";

const SAMPLE_TREE: UINode = {
  type: "Metric",
  props: {
    label: "Blue dollar",
    value: 1250.5,
    unit: "ARS/USD",
    delta: 1.8,
    trend: "up",
  },
};

export default function Home() {
  return (
    <HomeStage>
      <DynamicRenderer node={SAMPLE_TREE} />
    </HomeStage>
  );
}
