import { formatDelta, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { TrendDown, TrendUp } from "@phosphor-icons/react";
import type { MetricProps } from "./Metric.schema";

const TREND_CLASS: Record<string, string> = {
  up: "text-trend-up",
  down: "text-trend-down",
  flat: "text-muted-foreground",
};

/**
 * Metric widget — typographic quote block (no card chrome).
 *
 * Used by the agent UITree for spot values: FX, inflation, yields.
 */
export function Metric({
  label,
  value,
  unit,
  delta,
  trend = "flat",
}: MetricProps) {
  const trendClass = TREND_CLASS[trend] ?? TREND_CLASS.flat;
  const displayValue =
    typeof value === "number" ? formatNumber(value) : value;
  const valueSize =
    displayValue.length > 10
      ? "text-3xl md:text-4xl"
      : "text-4xl md:text-5xl";

  return (
    <div className="min-w-0 border-t border-rule pt-4">
      <p className="text-sm text-muted-foreground">{label}</p>

      <p className="mt-1 flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span
          className={cn(
            "min-w-0 font-display font-semibold tracking-tight tabular-nums text-foreground [overflow-wrap:anywhere]",
            valueSize,
          )}
        >
          {displayValue}
        </span>
        {unit ? (
          <span className="font-sans text-sm font-normal text-muted-foreground md:text-base">
            {unit}
          </span>
        ) : null}
      </p>

      {typeof delta === "number" ? (
        <p
          className={cn(
            "mt-1.5 inline-flex items-center gap-1 text-sm font-medium tabular-nums",
            trendClass,
          )}
        >
          {trend === "up" ? (
            <TrendUp size={14} weight="regular" aria-hidden />
          ) : trend === "down" ? (
            <TrendDown size={14} weight="regular" aria-hidden />
          ) : null}
          {formatDelta(delta)}%
        </p>
      ) : null}
    </div>
  );
}
