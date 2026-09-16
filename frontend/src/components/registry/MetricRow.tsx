import { Metric } from "./Metric";
import type { MetricRowProps } from "./MetricRow.schema";

/**
 * Responsive group of spot metrics (spread / multi-casa FX / KPI row).
 * Each metric keeps a readable minimum width, so dense rows become a grid
 * instead of squeezing values into overlapping columns.
 */
export function MetricRow({ items }: MetricRowProps) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,16rem),1fr))] gap-x-6 gap-y-5">
      {items.map((item, i) => (
        <Metric key={`${item.label}-${i}`} {...item} />
      ))}
    </div>
  );
}
