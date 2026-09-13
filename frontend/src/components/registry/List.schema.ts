import { z } from "zod";

export const ListColumnSchema = z.object({
  /** Key to read from each data row (e.g. "titulo", "fecha", "resultado") */
  key: z.string(),
  /** Column header shown to the user */
  label: z.string(),
  /**
   * How to render the cell. Omit to infer: `imagen`/`foto`/`photoUrl` keys
   * and `https://…/*.jpg` values become thumbnails, not truncated URLs.
   */
  kind: z.enum(["text", "image", "date", "url", "number"]).optional(),
});

export const ListPropsSchema = z.object({
  /** Which fields to show, in order, and how to label them */
  columns: z.array(ListColumnSchema).min(1),
  /** Data rows — injected by bind_data; never authored by the LLM directly */
  data: z.array(z.record(z.string(), z.unknown())).default([]),
});

export type ListColumn = z.infer<typeof ListColumnSchema>;
export type ListProps = z.infer<typeof ListPropsSchema>;

export const ListNodeSchema = z.object({
  id: z.string(),
  type: z.literal("List"),
  title: z.string().optional(),
  props: ListPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type ListNode = z.infer<typeof ListNodeSchema>;
