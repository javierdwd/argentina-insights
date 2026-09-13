import { z } from "zod";

export const PersonSchema = z.object({
  /** Full display name */
  name: z.string(),
  /** Portrait URL (senado.gob.ar / datos.hcdn.gob.ar); falls back to initials */
  photoUrl: z.string().optional(),
  /** e.g. "Senador", "Diputada", or a vote label when mapped from voto */
  role: z.string().optional(),
  /** partido or bloque parlamentario */
  party: z.string().optional(),
  /** provincia that the person represents */
  province: z.string().optional(),
  /** Official email when the roster has one */
  email: z.string().optional(),
  /** Phone / mesa de entradas */
  phone: z.string().optional(),
  /** Short Wikipedia extract when the proxy enriched a single profile */
  bio: z.string().optional(),
  /** Social / contact URLs (and sometimes duplicate emails) from ``redes`` */
  links: z.array(z.string()).optional(),
});

export const PersonCardPropsSchema = z.object({
  /**
   * One entry → detailed profile. Multiple → roster.
   * ``layout`` only applies when there are 2+ people.
   */
  people: z.array(PersonSchema).min(1),
  /**
   * Roster presentation: ``grid`` (default) or ``list`` (vertical rows —
   * better for long voter / affirmation lists).
   */
  layout: z.enum(["grid", "list"]).optional(),
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
