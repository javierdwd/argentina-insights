/**
 * Client-side date-range filter for chart rows already bound in props.
 * Window is relative to the latest dated point (not "today"), so historical
 * series still get a sensible last-N window.
 */

export type ChartRangeId = "1M" | "3M" | "1Y" | "5Y" | "all";

export const CHART_RANGE_OPTIONS: { id: ChartRangeId; label: string }[] = [
  { id: "1M", label: "1M" },
  { id: "3M", label: "3M" },
  { id: "1Y", label: "1A" },
  { id: "5Y", label: "5A" },
  { id: "all", label: "Todo" },
];

const RANGE_DAYS: Record<Exclude<ChartRangeId, "all">, number> = {
  "1M": 31,
  "3M": 93,
  "1Y": 366,
  "5Y": 366 * 5,
};

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})/;

export function parseIsoDay(value: unknown): Date | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  const match = ISO_DAY.exec(text);
  if (!match) return null;
  const y = Number(match[1]);
  const m = Number(match[2]);
  const d = Number(match[3]);
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) {
    return null;
  }
  const date = new Date(Date.UTC(y, m - 1, d));
  if (
    date.getUTCFullYear() !== y ||
    date.getUTCMonth() !== m - 1 ||
    date.getUTCDate() !== d
  ) {
    return null;
  }
  return date;
}

export function xKeyLooksDated(
  rows: Record<string, unknown>[] | undefined,
  xKey: string,
): boolean {
  if (!rows?.length || !xKey) return false;
  let hits = 0;
  const sample = Math.min(rows.length, 12);
  for (let i = 0; i < sample; i += 1) {
    if (parseIsoDay(rows[i]?.[xKey])) hits += 1;
  }
  return hits >= Math.min(3, sample);
}

function addUtcDays(date: Date, days: number): Date {
  const next = new Date(date.getTime());
  next.setUTCDate(next.getUTCDate() + days);
  return next;
}

/** Keep rows whose xKey fecha falls in [end - window, end]. */
export function filterRowsByRelativeRange<T extends Record<string, unknown>>(
  rows: T[],
  xKey: string,
  range: ChartRangeId,
): T[] {
  if (!rows.length || range === "all") return rows;
  let end: Date | null = null;
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const d = parseIsoDay(rows[i]?.[xKey]);
    if (d) {
      end = d;
      break;
    }
  }
  if (!end) return rows;
  const start = addUtcDays(end, -RANGE_DAYS[range]);
  return rows.filter((row) => {
    const d = parseIsoDay(row[xKey]);
    if (!d) return true;
    return d.getTime() >= start.getTime() && d.getTime() <= end!.getTime();
  });
}
