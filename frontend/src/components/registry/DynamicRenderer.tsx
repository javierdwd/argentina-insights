import { createElement, memo, type ReactNode } from "react";
import {
  ChartBar,
  ChartDonut,
  ChartLine,
  CloudSun,
  Hash,
  IdentificationCard,
  Lightbulb,
  MapTrifold,
  Newspaper,
  Package,
  Scroll,
  Table,
  TextAlignLeft,
  type Icon,
} from "@phosphor-icons/react";
import type { UINode } from "@/lib/uitree";
import { CanvasNodeProvider } from "@/components/shell/useCanvasAction";
import { isHostType, sanitizeHostProps } from "./host";
import { WIDGET_PANEL } from "./panel";
import { NODE_SCHEMAS, REGISTRY } from "./widgets";

const WIDGET_ICON: Partial<Record<string, Icon>> = {
  Acta: Scroll,
  AnnotatedTimeline: ChartLine,
  Box: Package,
  Callout: Lightbulb,
  Chart: ChartLine,
  ComparisonTable: Table,
  List: Table,
  Metric: Hash,
  MetricRow: Hash,
  News: Newspaper,
  PeriodBars: ChartBar,
  PersonCard: IdentificationCard,
  ProvinceMap: MapTrifold,
  Text: TextAlignLeft,
  VoteBreakdown: ChartDonut,
  WeatherUnit: CloudSun,
};

/** Layout shells — no panel; leaf children get their own surface. */
const LAYOUT_TYPES = new Set(["Stack", "Grid", "Box"]);

interface DynamicRendererProps {
  node: UINode;
}

function renderChildren(node: UINode): ReactNode[] | undefined {
  if (!node.children?.length) return undefined;
  return node.children.map((child, i) => (
    <DynamicRenderer
      key={(child as UINode).id ?? i}
      node={child as UINode}
    />
  ));
}

/**
 * Host tag from a Box tree — allowlisted HTML/SVG only, no title chrome.
 */
function HostNode({ node }: { node: UINode }) {
  const props = node.props ?? {};
  const safeProps = sanitizeHostProps(props);
  const rawText = props.text ?? props.content;
  const text =
    typeof rawText === "string" && rawText.length > 0 ? rawText : null;
  const kids = renderChildren(node);
  const childNodes =
    text != null && kids
      ? [text, ...kids]
      : text != null
        ? text
        : kids;

  return createElement(node.type, safeProps, childNodes);
}

/**
 * Looks up a UITree node in the registry and renders it.
 *
 * Pipeline: Agent → UITree JSON (state) → DynamicRenderer → widget / host
 *
 * Responsibilities:
 *   1. Wrap leaf widgets in a panel (bg-card) so they lift off stage paper.
 *   2. Render node.title as a heading above registry widgets (universal chrome).
 *   3. Validate node.props against NODE_SCHEMAS[type] (warn in dev, skip on fail).
 *   4. Look up the component by node.type, or render an allowlisted host tag.
 *   5. Recurse into node.children.
 *
 * Host tags (div/p/…) and layout shells (Stack/Grid/Box) skip panel + title
 * chrome — title lives on each leaf (or on Box content). Neither title nor
 * children are passed as props to registry components; the component only
 * receives its own typed props.
 */
export const DynamicRenderer = memo(function DynamicRenderer({
  node,
}: DynamicRendererProps) {
  const Component = REGISTRY[node.type];

  if (!Component) {
    if (isHostType(node.type)) {
      return <HostNode node={node} />;
    }
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[DynamicRenderer] Unknown node type: "${node.type}"`);
    }
    return null;
  }

  // Validate props against the per-type schema in dev.
  if (process.env.NODE_ENV !== "production") {
    const schema = NODE_SCHEMAS[node.type as keyof typeof NODE_SCHEMAS];
    const isPendingData = node.props?.dataRef != null;
    if (schema && !isPendingData) {
      const result = schema.safeParse({
        id: node.id,
        type: node.type,
        title: node.title,
        props: node.props,
        children: node.children,
      });
      if (!result.success) {
        console.warn(
          `[DynamicRenderer] Props validation failed for "${node.type}":`,
          result.error.issues,
        );
      }
    }
  }

  const Glyph = WIDGET_ICON[node.type];
  // Drop suggest-only / host-only keys before spreading onto widgets.
  // dataRef is agent-side only — if it leaks mid-stream (pre-bind), strip it
  // and default the rows prop so Chart/List don't see `data: undefined`.
  const {
    text: _text,
    suggests: _suggests,
    dataRef: _dataRef,
    ...rest
  } = (node.props ?? {}) as Record<string, unknown>;
  void _text;
  void _suggests;
  const widgetProps =
    _dataRef != null && rest.data === undefined && rest.people === undefined
      ? node.type === "PersonCard"
        ? { ...rest, people: [] }
        : { ...rest, data: [] }
      : rest;

  const body = (
    <CanvasNodeProvider type={node.type} title={node.title}>
      <Component {...widgetProps}>{renderChildren(node)}</Component>
    </CanvasNodeProvider>
  );

  const titleRow = node.title ? (
    <p className="mb-1 flex items-center gap-1.5 font-display text-sm font-medium tracking-tight text-foreground">
      {Glyph ? (
        <Glyph
          size={14}
          weight="regular"
          className="shrink-0 text-accent"
          aria-hidden
        />
      ) : null}
      {node.title}
    </p>
  ) : null;

  if (LAYOUT_TYPES.has(node.type)) {
    if (!titleRow) return body;
    return (
      <div>
        {titleRow}
        {body}
      </div>
    );
  }

  return (
    <section className={WIDGET_PANEL}>
      {titleRow}
      {body}
    </section>
  );
});
