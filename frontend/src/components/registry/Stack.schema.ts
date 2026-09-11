import { z } from "zod";

export const StackPropsSchema = z.object({
  /** Vertical spacing between children */
  gap: z.enum(["sm", "md", "lg"]).optional(),
});

export type StackProps = z.infer<typeof StackPropsSchema>;

export const StackNodeSchema = z.object({
  id: z.string(),
  type: z.literal("Stack"),
  title: z.string().optional(),
  props: StackPropsSchema.optional(),
  children: z.array(z.unknown()).optional(),
});

export type StackNode = z.infer<typeof StackNodeSchema>;
