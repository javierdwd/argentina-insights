import { z } from "zod";

export const ProvinceMapPropsSchema = z.object({
  /** Province name field */
  nameKey: z.string().default("provincia"),
  /** Numeric field to encode (size + color) */
  valueKey: z.string(),
  data: z.array(z.record(z.string(), z.unknown())).default([]),
});

export type ProvinceMapProps = z.infer<typeof ProvinceMapPropsSchema>;

export const ProvinceMapNodeSchema = z.object({
  id: z.string(),
  type: z.literal("ProvinceMap"),
  title: z.string().optional(),
  props: ProvinceMapPropsSchema,
  children: z.array(z.unknown()).optional(),
});
