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
 * Unordered ``- `` offer lists are lifted into inline buttons so they sit
 * in the paragraph instead of looking like another markdown list.
 */

const ACTIONS_RE = /\[\[\s*actions\s*\]\]([\s\S]*?)\[\[\s*\/\s*actions\s*\]\]/gi;

const ACTIONS_TAG_RE = /\[\[\s*\/?\s*actions\s*\]\]/gi;

const BOTON_RE =
  /\[\[\s*bot[oó]n\s*\]\]([\s\S]*?)\[\[\s*\/\s*bot[oó]n\s*\]\]|\[bot[oó]n\]([\s\S]*?)\[\/bot[oó]n\]/gi;

const BOTON_MARKUP_RE =
  /\[\[\s*\/?\s*bot[oó]n\s*\]\]|\[\/?bot[oó]n\]/gi;

const BOTON_WRAP_RE =
  /^\[\[\s*bot[oó]n\s*\]\]([\s\S]*)\[\[\s*\/\s*bot[oó]n\s*\]\]$|^\[bot[oó]n\]([\s\S]*)\[\/bot[oó]n\]$/i;

const BULLET_LINE = /^\s*[-*•]\s+(.+?)\s*$/;

const MAX_OFFERS = 4;

const OFFER_RE =
  /^(mostr[áa]|mostrame|mostrar|compar[áa]|comparar|superpon[ée]|superponer|tra[ée]|traer|busc[áa]|buscar|calcul[áa]|calcular|agreg[áa]|agregar|cruz[áa]|cruzar|filtr[áa]|filtrar|list[áa]|listar|arm[áa]|armar|profundiz[áa]|profundizar|analiz[áa]|analizar|sum[áa]|sumar|dame|quiero|ver)(?=\s|$|[¿?¡!.,;:])/i;

const FACT_LABEL_RE =
  /^(d[ií]a|fecha|ventana|d[oó]lar|riesgo|fuente|extracto|serie|a la izquierda|a la derecha|en (el|la) canvas)(?=\s|$|[¿?¡!.,;:])/i;

const ISO_DAY_RE = /^\d{4}-\d{2}-\d{2}\b/;

export type ChatSegment =
  | { type: "text"; text: string }
  | { type: "button"; text: string };

/** Executable next ask (imperative / infinitive), not a dated fact. */
export function looksLikeOffer(text: string): boolean {
  const label = stripBotonWrappers(text);
  if (!label || label.length > 140) return false;
  if (ISO_DAY_RE.test(label) || FACT_LABEL_RE.test(label)) return false;
  const kv = /^([^:]{2,40}):\s+\S/.exec(label);
  if (kv && !OFFER_RE.test(label)) return false;
  if (OFFER_RE.test(label)) return true;
  return /\?\s*$/.test(label) && label.length <= 100;
}

/** Analyst kv/date dump that must stay as prose, never a clickable chip. */
export function looksLikeFact(text: string): boolean {
  const label = stripBotonWrappers(text);
  if (!label) return false;
  if (ISO_DAY_RE.test(label) || FACT_LABEL_RE.test(label)) return true;
  const kv = /^([^:]{2,40}):\s+\S/.exec(label);
  return Boolean(kv && !OFFER_RE.test(label));
}

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
  if (!text || looksLikeFact(text)) return;
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
  const actions: string[] = [];
  let prose = content.replace(ACTIONS_RE, (_full, body: string) => {
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
    if (label && looksLikeFact(label) && !looksLikeOffer(label)) {
      segments.push({ type: "text", text: label });
    } else if (label) {
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

/** Turn ``- offer`` lists into inline ``[boton]`` tags on the previous sentence. */
export function liftBulletOffers(prose: string): string {
  const lines = prose.split("\n");
  const out: string[] = [];
  let index = 0;
  while (index < lines.length) {
    const bullet = lines[index].match(BULLET_LINE);
    if (!bullet) {
      out.push(lines[index]);
      index += 1;
      continue;
    }
    const offers: string[] = [];
    const factLines: string[] = [];
    while (index < lines.length) {
      const item = lines[index].match(BULLET_LINE);
      if (!item) break;
      const raw = item[1];
      const label = stripBotonWrappers(raw.replace(/\s+/g, " ").trim());
      const tagged = /\[\/?bot[oó]n\]/i.test(raw);
      if (label && (tagged || looksLikeOffer(label))) {
        if (offers.length < MAX_OFFERS) offers.push(label);
      } else if (lines[index].trim()) {
        factLines.push(lines[index]);
      }
      index += 1;
    }
    if (offers.length > 0) {
      const tags = offers.map(buttonTag).join(" ");
      while (out.length > 0 && !out[out.length - 1].trim()) out.pop();
      if (out.length > 0) {
        out[out.length - 1] = `${out[out.length - 1].trimEnd()} ${tags}`;
      } else {
        out.push(tags);
      }
    }
    if (factLines.length > 0) {
      out.push(...factLines);
    }
  }
  return out.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

/**
 * Fold block ``[[actions]]`` and dash-list offers into the prose as inline
 * buttons so they read as part of the sentence, not a second UI.
 */
export function embedOffersInProse(prose: string, actions: string[]): string {
  const text = liftBulletOffers(prose);
  const existing = parseInlineButtons(text)
    .filter((segment) => segment.type === "button")
    .map((segment) => segment.text);
  const extra = actions
    .map(stripBotonWrappers)
    .filter(
      (action) =>
        action && !looksLikeFact(action) && !alreadyCovered(action, existing),
    );
  const room = Math.max(0, MAX_OFFERS - existing.length);
  const clipped = extra.slice(0, room);
  if (clipped.length === 0) return text;
  const tags = clipped.map(buttonTag).join(" ");
  if (!text) return tags;
  return `${text.trimEnd()} ${tags}`;
}
