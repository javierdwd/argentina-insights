import { Metric } from "./Metric";
import type { MetricRowProps } from "./MetricRow.schema";

/**
 * Horizontal strip of spot metrics (spread / multi-casa FX / KPI row).
 * No card chrome — hairline rules only, matching Metric.
 */
export function MetricRow({ items }: MetricRowProps) {
  return (
    <div className="border-t border-rule pt-4">
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))]">
        {items.map((item, i) => (
          <div key={`${item.label}-${i}`} className="min-w-0 [&_>div]:border-t-0 [&_>div]:pt-0">
            <Metric {...item} />
          </div>
        ))}
      </div>
    </div>
  );
}
