import { z } from "zod";

export const ActaVoteSchema = z.object({
  voter: z.string().optional(),
  vote: z.string().optional(),
  title: z.string().optional(),
  date: z.string().optional(),
  result: z.string().optional(),
}).passthrough();

export const ActaPropsSchema = z.object({
  /** Flattened vote rows (or one acta with votos[]) — injected by bind_data */
  data: z.array(z.record(z.string(), z.unknown())).default([]),
});

export type ActaVote = z.infer<typeof ActaVoteSchema>;
export type ActaProps = z.infer<typeof ActaPropsSchema>;

export const ActaNodeSchema = z.object({
  id: z.string(),
  type: z.literal("Acta"),
  title: z.string().optional(),
  props: ActaPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type ActaNode = z.infer<typeof ActaNodeSchema>;
