/**
 * Map Open-Meteo WMO weather_code onto a coarse icon kind.
 * https://open-meteo.com/en/docs — WMO Weather interpretation codes.
 */

export type WeatherKind =
  | "clear"
  | "partly"
  | "overcast"
  | "fog"
  | "rain"
  | "snow"
  | "storm";

function asCode(raw: unknown): number | null {
  if (typeof raw === "number" && Number.isFinite(raw)) return Math.trunc(raw);
  if (typeof raw === "string" && raw.trim()) {
    const n = Number(raw);
    if (Number.isFinite(n)) return Math.trunc(n);
  }
  return null;
}

export function weatherKind(input: {
  weatherCode?: unknown;
  precipitation?: unknown;
}): WeatherKind {
  const code = asCode(input.weatherCode);
  if (code === 0 || code === 1) return "clear";
  if (code === 2) return "partly";
  if (code === 3) return "overcast";
  if (code === 45 || code === 48) return "fog";
  if (
    code != null &&
    ((code >= 51 && code <= 67) || (code >= 80 && code <= 82))
  ) {
    return "rain";
  }
  if (code != null && ((code >= 71 && code <= 77) || code === 85 || code === 86)) {
    return "snow";
  }
  if (code != null && code >= 95 && code <= 99) return "storm";
  const precip =
    typeof input.precipitation === "number"
      ? input.precipitation
      : Number(input.precipitation);
  if (Number.isFinite(precip) && precip > 0.2) return "rain";
  return "clear";
}
