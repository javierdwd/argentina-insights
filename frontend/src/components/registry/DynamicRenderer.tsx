import type { UINode } from "@/lib/uitree";
import { REGISTRY } from "./widgets";

interface DynamicRendererProps {
  node: UINode;
}

/**
 * Looks up a UITree node in the registry and renders it.
 *
 * Pipeline: Agent → UITree JSON → widget schema (*.schema.ts) → DynamicRenderer
 *
 * DynamicRenderer is intentionally thin:
 *   1. Look up the component by `node.type`
 *   2. Spread `node.props` as component props
 *   3. Recurse into `node.children`
 */
export function DynamicRenderer({ node }: DynamicRendererProps) {
  const Component = REGISTRY[node.type];

  if (!Component) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[DynamicRenderer] Unknown node type: "${node.type}"`);
    }
    return null;
  }

  return (
    <Component {...node.props}>
      {node.children?.map((child, i) => (
        <DynamicRenderer key={i} node={child as UINode} />
      ))}
    </Component>
  );
}
