export type PitchSide = "home" | "away";

export type FormationPosition = {
  x: number;
  y: number;
  line: number;
  indexInLine: number;
};

/**
 * Accept compact API formations (433) and display forms (4-3-3).
 * A valid outfield formation must account for ten players.
 */
export function parseFormation(value: string | null | undefined): number[] | null {
  const raw = value?.trim();
  if (!raw) return null;
  const parts = raw.includes("-")
    ? raw.split("-").map((part) => Number(part.trim()))
    : /^\d{2,5}$/.test(raw)
      ? [...raw].map(Number)
      : raw.split(/\s+/).map(Number);
  if (
    parts.length < 2 ||
    parts.length > 5 ||
    parts.some((part) => !Number.isInteger(part) || part < 1 || part > 5) ||
    parts.reduce((sum, part) => sum + part, 0) !== 10
  ) {
    return null;
  }
  return parts;
}

/** Broad, explicitly approximate rows when formation data is absent/invalid. */
export function fallbackFormation(outfieldCount: number): number[] {
  const count = Math.max(0, Math.floor(outfieldCount));
  if (count === 0) return [];
  if (count <= 4) return [count];
  if (count <= 7) {
    const back = Math.ceil(count / 2);
    return [back, count - back];
  }
  const back = Math.ceil(count * 0.4);
  const remaining = count - back;
  const midfield = Math.ceil(remaining * 0.55);
  return [back, midfield, remaining - midfield].filter((n) => n > 0);
}

/**
 * Place an ordered XI in broad tactical bands. Coordinates communicate the
 * formation only; they are not source tracking coordinates.
 */
export function formationPositions(
  playerCount: number,
  formation: string | null | undefined,
  side: PitchSide,
): FormationPosition[] {
  const count = Math.max(0, Math.floor(playerCount));
  if (count === 0) return [];
  const outfieldCount = Math.max(0, count - 1);
  const parsed = parseFormation(formation);
  const lines =
    parsed && parsed.reduce((sum, line) => sum + line, 0) === outfieldCount
      ? parsed
      : fallbackFormation(outfieldCount);
  const mirror = (y: number) => (side === "away" ? 100 - y : y);
  const positions: FormationPosition[] = [
    { x: 50, y: mirror(90), line: 0, indexInLine: 0 },
  ];

  lines.forEach((lineSize, lineIndex) => {
    // Fill one half only: defenders near goal, forwards near halfway.
    const progress = (lineIndex + 1) / Math.max(1, lines.length);
    const y = 91 - progress * 36;
    for (let index = 0; index < lineSize; index += 1) {
      positions.push({
        x: ((index + 1) * 100) / (lineSize + 1),
        y: mirror(y),
        line: lineIndex + 1,
        indexInLine: index,
      });
    }
  });

  return positions.slice(0, count);
}
