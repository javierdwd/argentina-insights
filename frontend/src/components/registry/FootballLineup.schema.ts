import { z } from "zod";

const ShirtNumberSchema = z.union([z.string(), z.number()]);

export const FootballPlayerSchema = z
  .object({
    name: z.string(),
    shortName: z.string().optional(),
    number: ShirtNumberSchema.optional(),
    shirtNumber: ShirtNumberSchema.optional(),
    position: z.string().optional(),
    photoUrl: z.string().optional(),
    photo: z.string().optional(),
    face: z.string().optional(),
  })
  .passthrough();

export const FootballCoachSchema = z.union([
  z.string(),
  z
    .object({
      name: z.string(),
      photoUrl: z.string().optional(),
    })
    .passthrough(),
]);

export const FootballLineupSideSchema = z
  .object({
    side: z.enum(["home", "away"]),
    team: z.string(),
    teamId: z.union([z.string(), z.number()]).optional(),
    logo: z.string().optional(),
    formation: z.union([z.string(), z.number()]).optional(),
    isProjected: z.boolean().optional().default(false),
    starting: z.array(FootballPlayerSchema).default([]),
    substitutes: z.array(FootballPlayerSchema).default([]),
    coach: FootballCoachSchema.optional(),
  })
  .passthrough();

export const FootballLineupPropsSchema = z.object({
  data: z.array(FootballLineupSideSchema).min(1).max(2),
});

export type FootballPlayer = z.infer<typeof FootballPlayerSchema>;
export type FootballLineupSide = z.infer<typeof FootballLineupSideSchema>;
export type FootballLineupProps = z.infer<typeof FootballLineupPropsSchema>;

export const FootballLineupNodeSchema = z.object({
  id: z.string(),
  type: z.literal("FootballLineup"),
  title: z.string().optional(),
  props: FootballLineupPropsSchema,
  children: z.array(z.unknown()).optional(),
});

export type FootballLineupNode = z.infer<typeof FootballLineupNodeSchema>;
