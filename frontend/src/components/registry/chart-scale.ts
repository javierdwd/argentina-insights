/** Pure numeric helpers for chart axes (no React). */

export function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** Max |value| across rows for one series key; 0 if all null/empty. */
export function seriesMagnitude(
  data: Record<string, unknown>[],
  key: string,
): number {
  let max = 0;
  for (const row of data) {
    const n = asNumber(row[key]);
    if (n === null) continue;
    max = Math.max(max, Math.abs(n));
  }
  return max;
}

/**
 * Share of rows where 2+ series are filled. Period overlays (one line per
 * mandate) sit near 0; overlays of distinct measures (blue vs inflación)
 * sit near 1 after the join.
 */
export function seriesOverlapRatio(
  data: Record<string, unknown>[],
  keys: string[],
): number {
  if (data.length === 0 || keys.length < 2) return 1;
  let overlap = 0;
  let any = 0;
  for (const row of data) {
    let filled = 0;
    for (const key of keys) {
      if (asNumber(row[key]) !== null) filled += 1;
    }
    if (filled > 0) any += 1;
    if (filled >= 2) overlap += 1;
  }
  return any === 0 ? 0 : overlap / any;
}

/**
 * When two+ series share one Y axis but differ by ~8×+ in magnitude
 * (e.g. blue ARS vs inflación %), put the smaller ones on the right axis.
 * Respects an explicit yAxisIndex:1 from compose.
 * Skip when series barely overlap in X — same measure split by period
 * (Macri ~60 vs Milei ~1400) must stay on one axis.
 */
export function withAutoDualAxis<
  T extends { key: string; yAxisIndex?: 0 | 1 },
>(series: T[], data: Record<string, unknown>[]): T[] {
  if (series.length < 2 || data.length === 0) return series;
  if (series.some((s) => s.yAxisIndex === 1)) return series;
  if (seriesOverlapRatio(data, series.map((s) => s.key)) < 0.1) return series;

  const mags = series.map((s) => seriesMagnitude(data, s.key));
  const positives = mags.filter((m) => m > 0);
  if (positives.length < 2) return series;

  const maxMag = Math.max(...positives);
  const minMag = Math.min(...positives);
  if (maxMag / minMag < 8) return series;

  return series.map((s, i) => {
    const m = mags[i] ?? 0;
    if (m <= 0) return s;
    if (maxMag / m >= 8) return { ...s, yAxisIndex: 1 as const };
    return s;
  });
}
