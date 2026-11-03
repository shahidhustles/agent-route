import { z } from "zod";

export const slideSchema = z.object({
  body: z.string().optional(),
  bullets: z.array(z.string()),
  id: z.string().optional(),
  imageUrl: z.string().optional(),
  title: z.string(),
});

export const deckSchema = z.array(slideSchema);

export type SlideInput = z.infer<typeof slideSchema>;
