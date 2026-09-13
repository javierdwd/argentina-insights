"use client";

import type { ComponentProps, HTMLAttributes } from "react";
import {
  ArrowsClockwise,
  CloudArrowDown,
  Layout,
  MagnifyingGlass,
} from "@phosphor-icons/react";
import {
  CopilotChatReasoningMessage,
  useDefaultRenderTool,
} from "@copilotkit/react-core/v2";

type ToolStatus = "inProgress" | "executing" | "complete";

type ToolRenderProps = {
  name: string;
  status: ToolStatus;
  parameters: unknown;
};

function paramRecord(parameters: unknown): Record<string, unknown> {
  if (typeof parameters === "string") {
    try {
      const parsed: unknown = JSON.parse(parameters);
      if (typeof parsed === "object" && parsed !== null) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return {};
    }
  }
  if (typeof parameters !== "object" || parameters === null) return {};
  return parameters as Record<string, unknown>;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

const FX_CASA: Record<string, string> = {
  blue: "el dólar blue",
  oficial: "el dólar oficial",
  mep: "el dólar MEP",
  bolsa: "el dólar MEP",
  ccl: "el dólar CCL",
  contadoconliqui: "el dólar CCL",
  mayorista: "el dólar mayorista",
  tarjeta: "el dólar tarjeta",
  cripto: "el dólar cripto",
};

/** Human topic from a proxy path — never the /v1/ string. */
function fetchTopic(path: string, inner: Record<string, unknown>): string {
  const hay = path.toLowerCase();
  const casa =
    asText(inner.casa).toLowerCase() ||
    (hay.match(/dolares\/([a-z]+)/)?.[1] ?? "");
  const fx = FX_CASA[casa];
  const province = asText(inner.province);
  const title = asText(inner.title);
  const entidad = asText(inner.entidad);
  const names = asText(inner.names);

  if (hay.includes("dolares") || hay.includes("cotizaciones")) {
    return fx ?? "el dólar";
  }
  if (hay.includes("inflacioninteranual")) return "la inflación interanual";
  if (hay.includes("inflacion")) return "la inflación";
  if (hay.includes("riesgo")) return "el riesgo país";
  if (hay.includes("confianza")) return "la confianza en el gobierno";
  if (hay.includes("uva")) return "el UVA";
  if (hay.includes("depositos") || hay.includes("tasas")) {
    return "las tasas de plazo fijo";
  }
  if (hay.includes("rendimientos")) {
    return entidad ? `tasas de ${entidad}` : "tasas por entidad";
  }
  if (hay.includes("votos")) {
    return hay.includes("senado")
      ? "la votación en el Senado"
      : hay.includes("diputados")
        ? "la votación en Diputados"
        : "el detalle de la votación";
  }
  if (hay.includes("actas")) {
    if (title) {
      const short = title.length > 42 ? `${title.slice(0, 40)}…` : title;
      return `el acta «${short}»`;
    }
    return hay.includes("senado")
      ? "actas del Senado"
      : hay.includes("diputados")
        ? "actas de Diputados"
        : "las actas";
  }
  if (hay.includes("senadores")) {
    return province ? `senadores de ${province}` : "los senadores";
  }
  if (hay.includes("diputados")) {
    if (names) return `a ${names.split("|")[0] ?? names}`;
    return province ? `diputados de ${province}` : "los diputados";
  }
  if (hay.includes("eventos")) return "eventos presidenciales";
  if (hay.includes("presidentes")) return "los mandatos presidenciales";
  return "datos";
}

function toolLine(name: string, status: ToolStatus, parameters: unknown): string | null {
  if (status === "complete") return null;

  const params = paramRecord(parameters);
  const query = asText(params.query);
  const path = asText(params.path);
  const inner = paramRecord(params.params);

  if (name === "search_actas") {
    return query ? `Buscando «${query}» en las actas…` : "Buscando en las actas…";
  }
  if (name === "fetch_argentinadatos") {
    return `Consultando ${fetchTopic(path, inner)}…`;
  }
  if (name === "transform_dataset") {
    return "Reordenando la tabla…";
  }
  if (name === "DirectoryMatch") {
    return "Buscando coincidencias…";
  }
  if (name === "ComposeOutput") {
    return "Armando la vista…";
  }
  return "Trabajando…";
}

function toolGlyph(name: string) {
  if (name === "search_actas" || name === "DirectoryMatch") return MagnifyingGlass;
  if (name === "transform_dataset") return ArrowsClockwise;
  if (name === "ComposeOutput") return Layout;
  return CloudArrowDown;
}

function ToolActivity({ name, status, parameters }: ToolRenderProps) {
  const line = toolLine(name, status, parameters);
  if (!line) return null;
  const Glyph = toolGlyph(name);
  return (
    <p
      className="my-1 flex items-center gap-1.5 text-[0.8rem] leading-snug text-muted-foreground"
      aria-live={status === "complete" ? undefined : "polite"}
    >
      <Glyph size={13} weight="regular" className="shrink-0 text-accent" aria-hidden />
      {line}
    </p>
  );
}

function renderToolActivity({
  name,
  status,
  parameters,
}: ToolRenderProps) {
  return <ToolActivity name={name} status={status} parameters={parameters} />;
}

/** Register a wildcard tool renderer so fetches aren't a blank wait. */
export function ChatToolActivity() {
  useDefaultRenderTool({ render: renderToolActivity }, []);
  return null;
}

function thinkingLabel(isStreaming?: boolean, label?: string): string {
  if (isStreaming) return "Pensando…";
  if (!label) return "Pensó un momento";
  if (/a few seconds/i.test(label)) return "Pensó unos segundos";
  const seconds = label.match(/Thought for (\d+) seconds?/i);
  if (seconds) return `Pensó ${seconds[1]} s`;
  const minutes = label.match(/Thought for (\d+) minutes?/i);
  if (minutes) return `Pensó ${minutes[1]} min`;
  const compact = label.match(/Thought for (\d+)m(?:\s+(\d+)s)?/i);
  if (compact) {
    const secs = compact[2] ? ` ${compact[2]} s` : "";
    return `Pensó ${compact[1]} min${secs}`;
  }
  return "Pensó un momento";
}

/** One short prose line from a reasoning blob (shared with floating status). */
export function clipReasoning(text: string): string {
  const cleaned = text
    .replace(/\/v1\/\S+/g, "")
    .replace(/[*_`#>]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) return "";
  const first = cleaned.split(/(?<=[.!?])\s+/)[0] ?? cleaned;
  if (first.length <= 72) return first;
  return `${first.slice(0, 70).trimEnd()}…`;
}

/** Latest non-empty reasoning in the current turn (after the last user msg). */
export function latestTurnReasoning(
  messages: { role?: string; content?: unknown }[] | undefined,
): string {
  if (!messages?.length) return "";
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "user") break;
    if (message.role !== "reasoning") continue;
    const raw = typeof message.content === "string" ? message.content : "";
    const line = clipReasoning(raw);
    if (line) return line;
  }
  return "";
}

export function ReasoningContent({
  children,
  isStreaming,
  hasContent: _hasContent,
  className,
  ...props
}: ComponentProps<typeof CopilotChatReasoningMessage.Content>) {
  const raw = typeof children === "string" ? children : "";
  const line = clipReasoning(raw);
  if (!line) return null;
  return (
    <p
      className={[
        "line-clamp-1 pb-1 text-[0.8rem] leading-snug text-muted-foreground",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      title={isStreaming ? undefined : line}
      {...props}
    >
      {line}
    </p>
  );
}

export function ReasoningHeader({
  isStreaming,
  label,
  ...props
}: ComponentProps<typeof CopilotChatReasoningMessage.Header>) {
  return (
    <CopilotChatReasoningMessage.Header
      {...props}
      isStreaming={isStreaming}
      label={thinkingLabel(isStreaming, label)}
    />
  );
}

export function ThinkingCursor({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-testid="copilot-loading-cursor"
      className={["mt-1 text-[0.8rem] text-muted-foreground", className]
        .filter(Boolean)
        .join(" ")}
      aria-live="polite"
      {...props}
    >
      Pensando…
    </div>
  );
}
