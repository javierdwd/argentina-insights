import { z } from "zod";

export const WeatherUnitPropsSchema = z.object({
  /** Clima rows — injected by bind_data; never authored by the LLM */
  data: z.array(z.record(z.string(), z.unknown())).default([]),
});

export type WeatherUnitProps = z.infer<typeof WeatherUnitPropsSchema>;

export const WeatherUnitNodeSchema = z.object({
  id: z.string(),
  type: z.literal("WeatherUnit"),
  title: z.string().optional(),
  props: WeatherUnitPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type WeatherUnitNode = z.infer<typeof WeatherUnitNodeSchema>;
