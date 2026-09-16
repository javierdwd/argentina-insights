import { z } from "zod";

export const NewsItemSchema = z.object({
  title: z.string(),
  source: z.string(),
  publishedAt: z.string(),
  url: z.string().url(),
});

export const NewsPropsSchema = z.object({
  /** News rows are injected by bind_data; never authored by the LLM. */
  data: z.array(NewsItemSchema).default([]),
});

export type NewsItem = z.infer<typeof NewsItemSchema>;
export type NewsProps = z.infer<typeof NewsPropsSchema>;

export const NewsNodeSchema = z.object({
  id: z.string(),
  type: z.literal("News"),
  title: z.string().optional(),
  props: NewsPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type NewsNode = z.infer<typeof NewsNodeSchema>;
