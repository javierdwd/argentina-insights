import { z } from "zod";

export const PersonSchema = z.object({
  /** Full display name */
  name: z.string(),
  /** Portrait URL (senado.gob.ar / datos.hcdn.gob.ar); falls back to initials */
  photoUrl: z.string().url().optional(),
  /** e.g. "Senador", "Diputada" */
  role: z.string().optional(),
  /** partido or bloque parlamentario */
  party: z.string().optional(),
  /** provincia that the person represents */
  province: z.string().optional(),
});

export const PersonCardPropsSchema = z.object({
  /** One entry → detailed profile card. Multiple → compact roster grid. */
  people: z.array(PersonSchema).min(1),
});

export type Person = z.infer<typeof PersonSchema>;
export type PersonCardProps = z.infer<typeof PersonCardPropsSchema>;

export const PersonCardNodeSchema = z.object({
  id: z.string(),
  type: z.literal("PersonCard"),
  title: z.string().optional(),
  props: PersonCardPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type PersonCardNode = z.infer<typeof PersonCardNodeSchema>;
