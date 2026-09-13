import type { ReactNode } from "react";

/**
 * Shared empty state for data-bound chart widgets.
 */
export function ChartEmpty(): ReactNode {
  return (
    <div className="flex h-52 items-center justify-center border-t border-rule">
      <p className="text-xs text-muted-foreground/50 select-none">Sin datos</p>
    </div>
  );
}

/** Brand celeste — ECharts cannot read CSS variables on canvas. */
export const ACCENT_HEX = "#1868a0";
export const SKY_HEX = "#74acdf";

/**
 * Hex palette for ECharts — CSS variables (var(--chart-N)) do NOT paint on
 * canvas, so every series collapsed to the same default stroke.
 * Celeste first, then rust / ink / red for extra series.
 */
export const CHART_COLORS = [
  ACCENT_HEX,
  "#c45c2a",
  "#2c4a6e",
  "#9b3b3b",
  "#5c6b7a",
  SKY_HEX,
  "#6b5b3a",
  "#121820",
];

/** Soft cap for cartesian line/bar/area — keeps axis labels readable. */
export const MAX_CHART_POINTS = 64;

export function seriesColor(index: number, explicit?: string): string {
  if (explicit && !explicit.includes("var(")) return explicit;
  return CHART_COLORS[index % CHART_COLORS.length];
}

export { asNumber, seriesMagnitude, seriesOverlapRatio, withAutoDualAxis } from "./chart-scale";
export {
  resolveChartSeries,
  resolveSeriesKey,
  trimEmptyMeasureEdges,
} from "./chart-series";

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})/;

/** Short axis label: same-year → DD/MM; multi-year → MM/YY. */
export function formatAxisLabel(
  raw: string,
  opts?: { multiYear?: boolean },
): string {
  const m = ISO_DAY.exec(raw);
  if (!m) return raw.length > 14 ? raw.slice(0, 10) : raw;
  const [, y, mo, d] = m;
  if (opts?.multiYear) return `${mo}/${y.slice(2)}`;
  return `${d}/${mo}`;
}

/** Full-ish label for tooltips (ISO day when present). */
export function formatTooltipLabel(raw: string): string {
  const m = ISO_DAY.exec(raw);
  if (!m) return raw;
  return `${m[1]}-${m[2]}-${m[3]}`;
}

export function axisLabelsAreMultiYear(labels: string[]): boolean {
  const years = new Set<string>();
  for (const raw of labels) {
    const m = ISO_DAY.exec(raw);
    if (m) years.add(m[1]);
    if (years.size > 1) return true;
  }
  return false;
}

/**
 * Evenly sample rows for display. Keeps first/last; enough for shape without
 * crowding the category axis.
 */
export function downsampleRows<T>(rows: T[], maxPoints: number = MAX_CHART_POINTS): T[] {
  if (rows.length <= maxPoints || maxPoints < 2) return rows;
  const out: T[] = [];
  const last = rows.length - 1;
  for (let i = 0; i < maxPoints; i++) {
    const idx = Math.round((i * last) / (maxPoints - 1));
    const row = rows[idx];
    if (out[out.length - 1] !== row) out.push(row);
  }
  return out;
}

/**
 * Even buckets; prefer the row with most non-null measure values.
 * Keeps sparse monthly series (inflación) when overlaid on daily FX.
 */
export function downsampleRowsPreferFilled<T extends Record<string, unknown>>(
  rows: T[],
  measureKeys: string[],
  maxPoints: number = MAX_CHART_POINTS,
): T[] {
  if (rows.length <= maxPoints || maxPoints < 2) return rows;
  if (measureKeys.length === 0) return downsampleRows(rows, maxPoints);

  const out: T[] = [];
  const n = rows.length;
  for (let i = 0; i < maxPoints; i++) {
    const start = Math.floor((i * n) / maxPoints);
    const end = Math.max(start + 1, Math.floor(((i + 1) * n) / maxPoints));
    const chunk = rows.slice(start, end);
    let best = chunk[0]!;
    let bestScore = -1;
    for (const row of chunk) {
      const score = measureKeys.reduce((sum, key) => {
        const v = row[key];
        return sum + (v !== null && v !== undefined && v !== "" ? 1 : 0);
      }, 0);
      if (score > bestScore) {
        best = row;
        bestScore = score;
      }
    }
    if (out[out.length - 1] !== best) out.push(best);
  }
  return out;
}

/** ECharts axisLabel config: ~6–8 ticks, no rotate when labels are short. */
export function categoryAxisLabel(n: number, opts?: { rotate?: number }) {
  const tickTarget = 7;
  const interval =
    n <= tickTarget ? 0 : Math.max(0, Math.ceil(n / tickTarget) - 1);
  return {
    fontSize: 11,
    hideOverlap: true,
    rotate: opts?.rotate ?? 0,
    interval,
  };
}
