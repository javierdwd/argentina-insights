/**
 * Parse clickable follow-ups from an assistant message.
 *
 * Block (after the prose):
 *   [[actions]]
 *   first executable ask
 *   [[/actions]]
 *
 * Inline (inside a sentence):
 *   [boton]Mostrá las tasas por entidad[/boton]
 *
 * Only explicit protocol markup creates buttons. Prose is never interpreted
 * to guess whether a sentence is an action.
 */

const ACTIONS_RE = /\[\[\s*actions\s*\]\]([\s\S]*?)\[\[\s*\/\s*actions\s*\]\]/gi;

const ACTIONS_TAG_RE = /\[\[\s*\/?\s*actions\s*\]\]/gi;

const NEXT_OPEN_RE = /\[\[\s*next\s*\]\]/gi;
const NEXT_CLOSE_RE = /\[\[\s*\/\s*next\s*\]\]/gi;

const BOTON_RE =
  /\[\[\s*bot[oó]n\s*\]\]([\s\S]*?)\[\[\s*\/\s*bot[oó]n\s*\]\]|\[bot[oó]n\]([\s\S]*?)\[\/bot[oó]n\]/gi;

const BOTON_MARKUP_RE =
  /\[\[\s*\/?\s*bot[oó]n\s*\]\]|\[\/?bot[oó]n\]/gi;

const BOTON_WRAP_RE =
  /^\[\[\s*bot[oó]n\s*\]\]([\s\S]*)\[\[\s*\/\s*bot[oó]n\s*\]\]$|^\[bot[oó]n\]([\s\S]*)\[\/bot[oó]n\]$/i;

const MAX_OFFERS = 4;

export type ChatSegment =
  | { type: "text"; text: string }
  | { type: "button"; text: string };

/** Collapse ``[boton][boton]X[/boton][/boton]`` so the parser sees one pair. */
export function collapseNestedBoton(content: string): string {
  let out = content;
  let prev = "";
  while (out !== prev) {
    prev = out;
    out = out.replace(/\[bot[oó]n\]\s*\[bot[oó]n\]/gi, "[boton]");
    out = out.replace(/\[\/bot[oó]n\]\s*\[\/bot[oó]n\]/gi, "[/boton]");
    out = out.replace(
      /\[\[\s*bot[oó]n\s*\]\]\s*\[\[\s*bot[oó]n\s*\]\]/gi,
      "[[boton]]",
    );
    out = out.replace(
      /\[\[\s*\/\s*bot[oó]n\s*\]\]\s*\[\[\s*\/\s*bot[oó]n\s*\]\]/gi,
      "[[/boton]]",
    );
  }
  return out;
}

export function stripBotonWrappers(label: string): string {
  let out = label.trim();
  let prev = "";
  while (out !== prev) {
    prev = out;
    const match = out.match(BOTON_WRAP_RE);
    if (!match) break;
    out = (match[1] ?? match[2] ?? "").trim();
  }
  return out.replace(BOTON_MARKUP_RE, "").replace(/\s+/g, " ").trim();
}

function pushAction(raw: string, actions: string[]): void {
  const text = stripBotonWrappers(raw.replace(/^[-*•\d.)\s]+/, "").trim());
  if (!text) return;
  if (actions.some((item) => isSimilarAsk(item, text))) return;
  if (actions.length < MAX_OFFERS) actions.push(text);
}

/** Models sometimes emit ``[[actions]]`` as a separator, with no close tag. */
function salvageLooseActions(content: string): {
  prose: string;
  actions: string[];
} {
  const tagRe = new RegExp(ACTIONS_TAG_RE.source, "gi");
  const matches = [...content.matchAll(tagRe)];
  if (matches.length === 0) {
    return { prose: content, actions: [] };
  }

  const actions: string[] = [];
  const first = matches[0];
  const firstIndex = first.index ?? 0;
  const lineStart = content.lastIndexOf("\n", firstIndex - 1) + 1;
  const atLineStart = content.slice(lineStart, firstIndex).trim() === "";

  let prose = content.slice(0, firstIndex);
  if (!atLineStart) {
    pushAction(content.slice(lineStart, firstIndex), actions);
    prose = content.slice(0, lineStart);
  }

  let cursor = firstIndex + first[0].length;
  for (const match of matches.slice(1)) {
    const index = match.index ?? cursor;
    for (const line of content.slice(cursor, index).split("\n")) {
      pushAction(line, actions);
    }
    cursor = index + match[0].length;
  }
  for (const line of content.slice(cursor).split("\n")) {
    pushAction(line, actions);
  }

  return { prose, actions };
}

export function parseChatActions(content: string): {
  prose: string;
  actions: string[];
} {
  // Defense in depth for persisted or streamed analyst markup. The backend
  // normally converts [[next]], but models can omit its closing tag.
  const normalized = content
    .replace(NEXT_OPEN_RE, "[[actions]]")
    .replace(NEXT_CLOSE_RE, "[[/actions]]");
  const actions: string[] = [];
  let prose = normalized.replace(ACTIONS_RE, (_full, body: string) => {
    for (const line of body.split("\n")) {
      pushAction(line, actions);
    }
    return "";
  });

  ACTIONS_TAG_RE.lastIndex = 0;
  if (ACTIONS_TAG_RE.test(prose)) {
    const loose = salvageLooseActions(prose);
    prose = loose.prose;
    for (const action of loose.actions) pushAction(action, actions);
  }

  prose = prose
    .replace(ACTIONS_TAG_RE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return { prose, actions };
}

export function hasInlineButtons(content: string): boolean {
  BOTON_RE.lastIndex = 0;
  return BOTON_RE.test(collapseNestedBoton(content));
}

/** Keep button labels as plain text (for copy / markdown fallback). */
export function stripInlineButtons(content: string): string {
  BOTON_RE.lastIndex = 0;
  return collapseNestedBoton(content)
    .replace(BOTON_RE, (_full, double?: string, single?: string) =>
      stripBotonWrappers(double ?? single ?? ""),
    )
    .replace(BOTON_MARKUP_RE, "")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

export function parseInlineButtons(content: string): ChatSegment[] {
  const source = collapseNestedBoton(content);
  const segments: ChatSegment[] = [];
  const re = new RegExp(BOTON_RE.source, "gi");
  let last = 0;
  let match: RegExpExecArray | null = re.exec(source);
  while (match) {
    if (match.index > last) {
      const text = source.slice(last, match.index).replace(BOTON_MARKUP_RE, "");
      if (text) segments.push({ type: "text", text });
    }
    const label = stripBotonWrappers(match[1] ?? match[2] ?? "");
    if (label) {
      segments.push({ type: "button", text: label });
    }
    last = match.index + match[0].length;
    match = re.exec(source);
  }
  if (last < source.length) {
    const text = source.slice(last).replace(BOTON_MARKUP_RE, "");
    if (text) segments.push({ type: "text", text });
  }
  return segments.length > 0 ? segments : [{ type: "text", text: source }];
}

function normalizeAsk(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

function isSimilarAsk(a: string, b: string): boolean {
  const left = normalizeAsk(a);
  const right = normalizeAsk(b);
  if (!left || !right) return false;
  if (left === right) return true;
  if (left.includes(right) || right.includes(left)) return true;
  const leftTokens = new Set(left.split(" ").filter((w) => w.length > 3));
  const rightTokens = new Set(right.split(" ").filter((w) => w.length > 3));
  if (leftTokens.size === 0 || rightTokens.size === 0) return false;
  let hit = 0;
  for (const token of leftTokens) {
    if (rightTokens.has(token)) hit += 1;
  }
  const smaller = Math.min(leftTokens.size, rightTokens.size);
  return hit >= 3 && hit / smaller >= 0.6;
}

function buttonTag(label: string): string {
  return `[boton]${stripBotonWrappers(label)}[/boton]`;
}

function alreadyCovered(label: string, existing: string[]): boolean {
  return existing.some((item) => isSimilarAsk(item, label));
}

/**
 * Fold explicitly parsed actions into prose as inline buttons.
 */
export function embedOffersInProse(prose: string, actions: string[]): string {
  const text = prose;
  const existing = parseInlineButtons(text)
    .filter((segment) => segment.type === "button")
    .map((segment) => segment.text);
  const extra = actions
    .map(stripBotonWrappers)
    .filter((action) => action && !alreadyCovered(action, existing));
  const room = Math.max(0, MAX_OFFERS - existing.length);
  const clipped = extra.slice(0, room);
  if (clipped.length === 0) return text;
  const tags = clipped.map(buttonTag).join(" ");
  if (!text) return tags;
  return `${text.trimEnd()} ${tags}`;
}
