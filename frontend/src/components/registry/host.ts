/**
 * Allowlisted host tags + Tailwind class vocabulary for Box fallback trees.
 *
 * compose_ui may emit these when no catalog widget fits. DynamicRenderer
 * maps them with createElement — never eval / JSX from the model.
 */

export const HOST_TAGS = new Set([
  // HTML
  "div",
  "p",
  "span",
  "h2",
  "h3",
  "ul",
  "ol",
  "li",
  "dl",
  "dt",
  "dd",
  "strong",
  "em",
  // SVG (succession arrows, simple diagrams)
  "svg",
  "g",
  "path",
  "line",
  "polyline",
  "polygon",
  "circle",
  "rect",
  "text",
  "defs",
  "marker",
  "title",
] as const);

export type HostTag = typeof HOST_TAGS extends Set<infer T> ? T : never;

export const SVG_HOST_TAGS = new Set([
  "svg",
  "g",
  "path",
  "line",
  "polyline",
  "polygon",
  "circle",
  "rect",
  "text",
  "defs",
  "marker",
  "title",
]);

/** Layout + bulletin tokens already used in the shell / widgets. */
export const HOST_CLASS_VOCAB = new Set([
  // layout
  "flex",
  "flex-col",
  "flex-row",
  "flex-wrap",
  "items-start",
  "items-center",
  "items-end",
  "items-baseline",
  "justify-start",
  "justify-center",
  "justify-between",
  "justify-end",
  "self-center",
  "grid",
  "grid-cols-1",
  "grid-cols-2",
  "grid-cols-3",
  "md:grid-cols-2",
  "md:grid-cols-3",
  "gap-1",
  "gap-1.5",
  "gap-2",
  "gap-3",
  "gap-4",
  "gap-6",
  "gap-8",
  "gap-10",
  "min-w-0",
  "min-w-[12rem]",
  "max-w-xl",
  "max-w-2xl",
  "max-w-3xl",
  "shrink-0",
  "grow",
  "w-full",
  "w-4",
  "w-6",
  "w-8",
  "w-10",
  "w-12",
  "h-4",
  "h-6",
  "h-8",
  "h-10",
  "h-12",
  "h-auto",
  "relative",
  "absolute",
  "overflow-hidden",
  "overflow-x-auto",
  // spacing
  "mt-1",
  "mt-1.5",
  "mt-2",
  "mt-3",
  "mt-4",
  "mb-1",
  "mb-2",
  "mb-3",
  "mb-4",
  "ml-2",
  "mr-2",
  "mx-auto",
  "pl-4",
  "pr-4",
  "pt-2",
  "pt-3",
  "pt-4",
  "pb-2",
  "pb-3",
  "pb-4",
  "py-1",
  "py-2",
  "py-3",
  "py-4",
  "px-2",
  "px-3",
  "px-4",
  // typography
  "font-display",
  "font-sans",
  "font-medium",
  "font-normal",
  "font-semibold",
  "text-xs",
  "text-sm",
  "text-base",
  "text-lg",
  "text-xl",
  "text-2xl",
  "text-4xl",
  "text-5xl",
  "md:text-5xl",
  "text-center",
  "text-left",
  "leading-relaxed",
  "leading-snug",
  "leading-tight",
  "tracking-tight",
  "tracking-wide",
  "uppercase",
  "tabular-nums",
  "whitespace-pre-wrap",
  // color / borders (theme tokens)
  "text-foreground",
  "text-muted-foreground",
  "text-accent",
  "text-sky",
  "text-trend-up",
  "text-trend-down",
  "text-destructive",
  "bg-muted",
  "bg-card",
  "bg-secondary",
  "bg-accent-soft",
  "border",
  "border-t",
  "border-b",
  "border-l-2",
  "border-l-4",
  "border-rule",
  "border-border",
  "border-accent",
  "border-destructive",
  "rounded-md",
  "rounded-lg",
  "rounded-xl",
  // lists
  "list-disc",
  "list-decimal",
  "list-inside",
  "list-none",
] as const);

export type HostClass = typeof HOST_CLASS_VOCAB extends Set<infer T> ? T : never;

/**
 * Safe attribute keys for host nodes (mostly SVG geometry).
 * React camelCase only — kebab-case from the model is mapped below.
 */
const HOST_ATTR_KEYS = new Set([
  "viewBox",
  "width",
  "height",
  "d",
  "fill",
  "stroke",
  "strokeWidth",
  "strokeLinecap",
  "strokeLinejoin",
  "strokeDasharray",
  "x",
  "y",
  "x1",
  "y1",
  "x2",
  "y2",
  "cx",
  "cy",
  "r",
  "rx",
  "ry",
  "points",
  "transform",
  "opacity",
  "markerEnd",
  "markerStart",
  "markerMid",
  "orient",
  "refX",
  "refY",
  "markerWidth",
  "markerHeight",
  "markerUnits",
  "xmlns",
  "role",
  "aria-hidden",
  "aria-label",
  "preserveAspectRatio",
]);

const ATTR_ALIASES: Record<string, string> = {
  "stroke-width": "strokeWidth",
  "stroke-linecap": "strokeLinecap",
  "stroke-linejoin": "strokeLinejoin",
  "stroke-dasharray": "strokeDasharray",
  "marker-end": "markerEnd",
  "marker-start": "markerStart",
  "marker-mid": "markerMid",
  "marker-width": "markerWidth",
  "marker-height": "markerHeight",
  "marker-units": "markerUnits",
  "ref-x": "refX",
  "ref-y": "refY",
  "aria-hidden": "aria-hidden",
  "aria-label": "aria-label",
  viewbox: "viewBox",
};

const SAFE_PAINT = /^(none|currentColor|#[0-9a-fA-F]{3,8}|rgb\([^)]+\)|rgba\([^)]+\))$/;
const SAFE_NUMBERISH = /^-?[\d.]+(%|[a-z]*)?$/i;
const SAFE_PATH = /^[MmLlHhVvCcSsQqTtAaZz0-9 pant.,\-+eE]+$/;
const SAFE_POINTS = /^[\d pant.,\-+eE]+$/;
const SAFE_TRANSFORM = /^[a-zA-Z0-9 pant.,\-+eE()]+$/;
const SAFE_VIEWBOX = /^[\d pant.\-+eE]+$/;
const SAFE_MARKER_REF = /^url\(#[A-Za-z][\w-]*\)$/;

function aliasAttrKey(key: string): string | null {
  if (HOST_ATTR_KEYS.has(key)) return key;
  const mapped = ATTR_ALIASES[key] ?? ATTR_ALIASES[key.toLowerCase()];
  if (mapped && HOST_ATTR_KEYS.has(mapped)) return mapped;
  return null;
}

function isSafeAttrValue(key: string, value: string): boolean {
  const v = value.trim();
  if (!v || v.length > 2000) return false;
  if (/javascript:|data:|<|>/i.test(v)) return false;
  switch (key) {
    case "fill":
    case "stroke":
      return SAFE_PAINT.test(v) || v === "transparent";
    case "d":
      return SAFE_PATH.test(v);
    case "points":
      return SAFE_POINTS.test(v);
    case "transform":
      return SAFE_TRANSFORM.test(v);
    case "viewBox":
    case "preserveAspectRatio":
      return SAFE_VIEWBOX.test(v) || /^[a-zA-Z0-9 ]+$/.test(v);
    case "markerEnd":
    case "markerStart":
    case "markerMid":
      return SAFE_MARKER_REF.test(v) || v === "none";
    case "xmlns":
      return v === "http://www.w3.org/2000/svg";
    case "role":
      return /^[a-z]+$/.test(v);
    case "aria-hidden":
      return v === "true" || v === "false";
    case "aria-label":
      return v.length <= 200 && !/[<>]/.test(v);
    case "orient":
      return v === "auto" || v === "auto-start-reverse" || SAFE_NUMBERISH.test(v);
    default:
      return SAFE_NUMBERISH.test(v) || SAFE_PAINT.test(v);
  }
}

/** Space-joined class string with only vocabulary tokens kept (order preserved). */
export function sanitizeHostClass(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) return undefined;
  const kept = value
    .split(/\s+/)
    .filter((token) => HOST_CLASS_VOCAB.has(token as HostClass));
  return kept.length > 0 ? kept.join(" ") : undefined;
}

/**
 * Build a safe props object for createElement (className + SVG geometry).
 * Drops text/content/suggests/dataRef/event handlers.
 */
export function sanitizeHostProps(
  props: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (!props) return out;
  const className = sanitizeHostClass(props.className);
  if (className) out.className = className;

  for (const [rawKey, rawVal] of Object.entries(props)) {
    if (
      rawKey === "className" ||
      rawKey === "text" ||
      rawKey === "content" ||
      rawKey === "suggests" ||
      rawKey === "dataRef" ||
      rawKey === "children" ||
      rawKey.startsWith("on")
    ) {
      continue;
    }
    const key = aliasAttrKey(rawKey);
    if (!key) continue;
    if (typeof rawVal === "number" && Number.isFinite(rawVal)) {
      out[key] = rawVal;
      continue;
    }
    if (typeof rawVal === "boolean" && key === "aria-hidden") {
      out[key] = rawVal;
      continue;
    }
    if (typeof rawVal === "string" && isSafeAttrValue(key, rawVal)) {
      out[key] = rawVal.trim();
    }
  }
  return out;
}

export function isHostType(type: string): boolean {
  return HOST_TAGS.has(type as HostTag);
}

export function isSvgHostType(type: string): boolean {
  return SVG_HOST_TAGS.has(type);
}

/** Single-line class list for Tailwind `@source inline(...)`. */
export function hostClassVocabInline(): string {
  return [...HOST_CLASS_VOCAB].join(" ");
}
