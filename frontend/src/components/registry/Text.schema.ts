import { z } from "zod";

export const TextPropsSchema = z.object({
  /** The prose content to display. */
  content: z.string(),
  /** Optional short title rendered above the body. */
  title: z.string().optional(),
});

export type TextProps = z.infer<typeof TextPropsSchema>;

export const TextNodeSchema = z.object({
  type: z.literal("Text"),
  props: TextPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type TextNode = z.infer<typeof TextNodeSchema>;
