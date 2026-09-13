import { z } from "zod";

export const CalloutPropsSchema = z.object({
  /** Short kicker above the body */
  eyebrow: z.string().optional(),
  content: z.string(),
  tone: z.enum(["insight", "info", "warning"]).optional(),
});

export type CalloutProps = z.infer<typeof CalloutPropsSchema>;

export const CalloutNodeSchema = z.object({
  id: z.string(),
  type: z.literal("Callout"),
  title: z.string().optional(),
  props: CalloutPropsSchema,
  children: z.array(z.unknown()).optional(),
});
