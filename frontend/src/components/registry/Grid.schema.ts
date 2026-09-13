import { z } from "zod";

export const GridPropsSchema = z.object({
  columns: z.union([z.literal(2), z.literal(3)]).optional(),
  gap: z.enum(["sm", "md", "lg"]).optional(),
});

export type GridProps = z.infer<typeof GridPropsSchema>;

export const GridNodeSchema = z.object({
  id: z.string(),
  type: z.literal("Grid"),
  title: z.string().optional(),
  props: GridPropsSchema.optional(),
  children: z.array(z.unknown()).optional(),
});
