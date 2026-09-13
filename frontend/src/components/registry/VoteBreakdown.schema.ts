import { z } from "zod";

export const VoteBreakdownPropsSchema = z.object({
  /** Row key for the vote label (AFIRMATIVO / NEGATIVO / …) */
  voteKey: z.string().default("voto"),
  /** donut = hollow; pie = filled */
  kind: z.enum(["donut", "pie"]).optional(),
  data: z.array(z.record(z.string(), z.unknown())).default([]),
});

export type VoteBreakdownProps = z.infer<typeof VoteBreakdownPropsSchema>;

export const VoteBreakdownNodeSchema = z.object({
  id: z.string(),
  type: z.literal("VoteBreakdown"),
  title: z.string().optional(),
  props: VoteBreakdownPropsSchema,
  children: z.array(z.unknown()).optional(),
});
