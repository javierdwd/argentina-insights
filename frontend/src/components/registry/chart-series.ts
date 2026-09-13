/** Pure helpers for matching Chart series keys to row columns. */

function measureFilled(row: Record<string, unknown>, keys: string[]): boolean {
  return keys.some((key) => {
    const value = row[key];
    return value !== null && value !== undefined && value !== "";
  });
}

/** Drop leading/trailing rows where every plotted series is empty. */
export function trimEmptyMeasureEdges<T extends Record<string, unknown>>(
  rows: T[],
  measureKeys: string[],
): T[] {
  if (rows.length === 0 || measureKeys.length === 0) return rows;
  let start = 0;
  while (start < rows.length && !measureFilled(rows[start]!, measureKeys)) start += 1;
  let end = rows.length - 1;
  while (end >= start && !measureFilled(rows[end]!, measureKeys)) end -= 1;
  return rows.slice(start, end + 1);
}

function foldKey(key: string): string {
  return key
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function lettersOnly(key: string): string {
  return foldKey(key).replace(/_/g, "");
}

function editDistance(left: string, right: string): number {
  if (left === right) return 0;
  if (!left.length) return right.length;
  if (!right.length) return left.length;
  const prev = Array.from({ length: right.length + 1 }, (_, i) => i);
  for (let i = 1; i <= left.length; i++) {
    let diag = prev[0]!;
    prev[0] = i;
    for (let j = 1; j <= right.length; j++) {
      const tmp = prev[j]!;
      const cost = left[i - 1] === right[j - 1] ? 0 : 1;
      prev[j] = Math.min(tmp + 1, prev[j - 1]! + 1, diag + cost);
      diag = tmp;
    }
  }
  return prev[right.length]!;
}

export function collectRowKeys(data: Record<string, unknown>[]): string[] {
  const keys = new Set<string>();
  for (const row of data) {
    for (const key of Object.keys(row)) keys.add(key);
  }
  return [...keys];
}

export function resolveSeriesKey(
  wanted: string,
  columns: string[],
  used: Set<string>,
): string {
  const available = columns.filter((col) => !used.has(col));
  if (available.includes(wanted)) return wanted;
  const wantFold = foldKey(wanted);
  const foldHit = available.find((col) => foldKey(col) === wantFold);
  if (foldHit) return foldHit;
  const wantLetters = lettersOnly(wanted);
  const letterHits = available.filter((col) => {
    const have = lettersOnly(col);
    return (
      have === wantLetters ||
      (wantLetters.length >= 6 &&
        (have.startsWith(wantLetters) || wantLetters.startsWith(have)))
    );
  });
  if (letterHits.length === 1) return letterHits[0]!;
  const tokens = wantFold.split("_").filter(Boolean);
  if (tokens.length >= 2) {
    const prefix = tokens.slice(0, 2).join("_");
    const prefixHits = available.filter((col) => foldKey(col).startsWith(prefix));
    if (prefixHits.length === 1) return prefixHits[0]!;
  }
  if (wantLetters.length >= 6) {
    const close = available
      .map((col) => ({ col, dist: editDistance(wantLetters, lettersOnly(col)) }))
      .filter((hit) => hit.dist <= 2)
      .sort((a, b) => a.dist - b.dist);
    if (close.length === 1) return close[0]!.col;
    if (close.length > 1 && close[0]!.dist < close[1]!.dist) return close[0]!.col;
  }
  return wanted;
}

export function resolveChartSeries<T extends { key: string }>(
  series: T[] | null | undefined,
  data: Record<string, unknown>[] | null | undefined,
): T[] {
  if (!series?.length) return series ?? [];
  if (!data?.length) return series;
  const columns = collectRowKeys(data);
  const used = new Set<string>();
  return series.map((entry) => {
    const key = resolveSeriesKey(entry.key, columns, used);
    used.add(key);
    return key === entry.key ? entry : { ...entry, key };
  });
}
