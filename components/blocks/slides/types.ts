export interface Slide {
  id: string;
  title: string;
  /** Optional paragraph-style copy (multiple lines preserved). */
  body?: string;
  bullets: string[];
  imageUrl?: string;
}
