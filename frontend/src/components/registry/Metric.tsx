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

  return (
    <div className="min-w-[12rem] border-t border-rule pt-4">
      <p className="text-sm text-muted-foreground">{label}</p>

      <p className="mt-1 font-display text-4xl font-semibold tracking-tight tabular-nums text-foreground md:text-5xl">
        {displayValue}
        {unit ? (
          <span className="ml-2 font-sans text-base font-normal text-muted-foreground">
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
