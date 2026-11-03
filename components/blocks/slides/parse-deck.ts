import { deckSchema } from "./deck-schema";
import type { Slide } from "./types";

function ensureSlideIds(slides: Slide[]): Slide[] {
  return slides.map((slide) => ({
    ...slide,
    id: slide.id && slide.id.length > 0 ? slide.id : crypto.randomUUID(),
  }));
}

export function parseDeckContent(content: string): Slide[] {
  const trimmed = content.trim();
  if (trimmed.length === 0) {
    return [];
  }

  try {
    const parsed: unknown = JSON.parse(trimmed);
    const result = deckSchema.safeParse(parsed);
    if (!result.success) {
      return [];
    }
    return ensureSlideIds(
      result.data.map((s) => ({
        body: s.body ?? "",
        bullets: s.bullets,
        id: s.id ?? "",
        imageUrl: s.imageUrl,
        title: s.title,
      }))
    );
  } catch {
    return [];
  }
}

export function serializeDeck(slides: Slide[]): string {
  return JSON.stringify(slides);
}
