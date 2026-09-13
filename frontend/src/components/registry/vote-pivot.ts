function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

const VOTE_TOKENS = ["afirmativo", "negativo", "abstencion", "ausente"] as const;
type VoteToken = (typeof VOTE_TOKENS)[number];

const VOTE_ALIASES: Record<string, VoteToken> = {
  si: "afirmativo",
  yes: "afirmativo",
  positivo: "afirmativo",
  no: "negativo",
  ausentes: "ausente",
  abstenciones: "abstencion",
};

const VOTE_FIELDS = ["voto", "vote", "tipoVoto", "tipo_voto"] as const;

export function canonVoteToken(raw: string): string {
  return raw
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .trim();
}

export function matchVoteToken(raw: string): VoteToken | null {
  const folded = canonVoteToken(raw);
  const stripped = folded.endsWith("s") ? folded.slice(0, -1) : folded;
  if (stripped in VOTE_ALIASES) return VOTE_ALIASES[stripped];
  if (folded in VOTE_ALIASES) return VOTE_ALIASES[folded];
  for (const token of VOTE_TOKENS) {
    if (stripped === token || folded === token) return token;
  }
  for (const token of VOTE_TOKENS) {
    if (stripped.length >= 4 && (stripped.startsWith(token) || token.startsWith(stripped))) {
      return token;
    }
    if (folded.includes(token)) return token;
  }
  return null;
}

export function seriesLookLikeVotes(series: { key: string }[]): boolean {
  return series.length > 0 && series.every((s) => matchVoteToken(s.key) !== null);
}

function voteLabelFromRow(row: Record<string, unknown>): string | null {
  for (const key of VOTE_FIELDS) {
    const value = row[key];
    if (value !== null && value !== undefined && String(value).trim()) {
      return String(value);
    }
  }
  return null;
}

function seriesKeysAreNumeric(
  data: Record<string, unknown>[],
  keys: string[],
): boolean {
  return keys.some((key) => data.some((row) => asNumber(row[key]) !== null));
}

/**
 * Roll-call rows are one legislator per row (`voto` = "afirmativo"). Compose
 * often asks for a stacked bar with series keys afirmativo/negativo/… which
 * are not columns. Count votes per xKey category (typically `bloque`).
 */
export function pivotCategoryVoteCounts(
  data: Record<string, unknown>[] | undefined,
  xKey: string,
  series: { key: string }[],
): Record<string, unknown>[] | null {
  if (!data?.length || !xKey || series.length === 0) return null;
  const keys = series.map((s) => s.key);
  if (seriesKeysAreNumeric(data, keys)) return null;
  const keyTokens = keys.map((key) => ({ key, token: matchVoteToken(key) }));
  if (!keyTokens.some((entry) => entry.token)) return null;
  if (!data.some((row) => voteLabelFromRow(row))) return null;

  const grouped = new Map<string, Record<string, unknown>>();
  const order: string[] = [];
  for (const row of data) {
    const cat = String(row[xKey] ?? "").trim();
    if (!cat) continue;
    if (!grouped.has(cat)) {
      const init: Record<string, unknown> = { [xKey]: cat };
      for (const key of keys) init[key] = 0;
      grouped.set(cat, init);
      order.push(cat);
    }
    const label = voteLabelFromRow(row);
    if (!label) continue;
    const token = matchVoteToken(label);
    if (!token) continue;
    const bucket = grouped.get(cat)!;
    for (const entry of keyTokens) {
      if (entry.token === token) {
        bucket[entry.key] = Number(bucket[entry.key] ?? 0) + 1;
        break;
      }
    }
  }

  const rows = order.map((cat) => grouped.get(cat)!);
  const anyCount = rows.some((row) => keys.some((key) => Number(row[key]) > 0));
  return anyCount ? rows : null;
}

/** Prefer negativos desc (the usual "quién se partió" ranking), else first series. */
export function sortVoteCategoryRows(
  rows: Record<string, unknown>[],
  series: { key: string }[],
): Record<string, unknown>[] {
  const negKey = series.find((s) => matchVoteToken(s.key) === "negativo")?.key;
  const sortKey = negKey ?? series[0]?.key;
  if (!sortKey) return rows;
  return [...rows].sort(
    (a, b) => Number(b[sortKey] ?? 0) - Number(a[sortKey] ?? 0),
  );
}
