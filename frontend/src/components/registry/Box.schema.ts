import { z } from "zod";

export const BoxPropsSchema = z.object({
  /** Allowlisted Tailwind classes only — sanitized on the client. */
  className: z.string().optional(),
  /**
   * Optional PascalCase name of a widget this layout is approximating
   * (e.g. SpreadExplainer). Frontend ignores it; used to promote patterns later.
   */
  suggests: z.string().optional(),
});

export type BoxProps = z.infer<typeof BoxPropsSchema>;

export const BoxNodeSchema = z.object({
  id: z.string(),
  type: z.literal("Box"),
  title: z.string().optional(),
  props: BoxPropsSchema.optional(),
  children: z.array(z.unknown()).optional(),
});

export type BoxNode = z.infer<typeof BoxNodeSchema>;
