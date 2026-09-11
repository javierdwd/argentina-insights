import type { UINode } from "@/lib/uitree";
import { NODE_SCHEMAS, REGISTRY } from "./widgets";

interface DynamicRendererProps {
  node: UINode;
}

/**
 * Looks up a UITree node in the registry and renders it.
 *
 * Pipeline: Agent → UITree JSON (state) → DynamicRenderer → widget component
 *
 * Responsibilities:
 *   1. Render node.title as a heading above the component (universal chrome).
 *   2. Validate node.props against NODE_SCHEMAS[type] (warn in dev, skip on fail).
 *   3. Look up the component by node.type and spread node.props.
 *   4. Recurse into node.children.
 *
 * Neither title nor children are passed as props to the component itself;
 * the component only receives its own typed props.
 */
export function DynamicRenderer({ node }: DynamicRendererProps) {
  const Component = REGISTRY[node.type];

  if (!Component) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[DynamicRenderer] Unknown node type: "${node.type}"`);
    }
    return null;
  }

  // Validate props against the per-type schema in dev.
  if (process.env.NODE_ENV !== "production") {
    const schema = NODE_SCHEMAS[node.type as keyof typeof NODE_SCHEMAS];
    if (schema) {
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

  return (
    <div>
      {/* Universal widget heading — rendered here so every widget type gets it
          without implementing its own title. */}
      {node.title ? (
        <p className="mb-2 text-sm text-muted-foreground">{node.title}</p>
      ) : null}

      <Component {...(node.props ?? {})}>
        {node.children?.map((child, i) => (
          <DynamicRenderer key={(child as UINode).id ?? i} node={child as UINode} />
        ))}
      </Component>
    </div>
  );
}
