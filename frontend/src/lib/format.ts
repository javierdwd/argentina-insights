/**
 * Number formatting via Intl.NumberFormat.
 *
 * Product default is es-AR (Argentine public-data product).
 * Swap DEFAULT_LOCALE (or pass `locale`) when i18n lands.
 */

export const DEFAULT_LOCALE = "es-AR";

const numberFormatterCache = new Map<string, Intl.NumberFormat>();

function getNumberFormatter(
  locale: string,
  options: Intl.NumberFormatOptions,
): Intl.NumberFormat {
  const key = `${locale}:${JSON.stringify(options)}`;
  let formatter = numberFormatterCache.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat(locale, options);
    numberFormatterCache.set(key, formatter);
  }
  return formatter;
}

/** Format a metric / quote value (up to 2 fraction digits). */
export function formatNumber(
  value: number,
  locale: string = DEFAULT_LOCALE,
): string {
  return getNumberFormatter(locale, {
    maximumFractionDigits: 2,
  }).format(value);
}

/** Format a percentage delta (1 fraction digit, no style:% — caller adds "%"). */
export function formatDelta(
  value: number,
  locale: string = DEFAULT_LOCALE,
): string {
  return getNumberFormatter(locale, {
    maximumFractionDigits: 1,
    signDisplay: "exceptZero",
  }).format(value);
}
