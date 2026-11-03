"use client";

import { useMemo, useState } from "react";

import { cn } from "@/lib/utils";

import { parseDeckContent } from "./parse-deck";

// Read-only deck viewer in the layout of ai-components agent-slides-artifact: a thumbnail rail and a 16:9 slide.
export function DeckView({ content }: { content: string }) {
  const slides = useMemo(() => parseDeckContent(content), [content]);
  const [index, setIndex] = useState(0);
  if (!slides.length) return <p className="text-sm text-muted-foreground">The deck has no readable slides.</p>;
  const slide = slides[Math.min(index, slides.length - 1)];
  return (
    <div className="flex flex-col gap-3 md:flex-row">
      <ol className="flex gap-2 overflow-x-auto md:max-h-[420px] md:w-44 md:shrink-0 md:flex-col md:overflow-y-auto">
        {slides.map((s, i) => (
          <li className="shrink-0" key={s.id}>
            <button
              className={cn(
                "w-40 rounded-sm border p-2 text-left text-xs md:w-full",
                i === index ? "border-foreground bg-muted" : "hover:bg-muted/60"
              )}
              onClick={() => setIndex(i)}
              type="button"
            >
              <span className="text-muted-foreground tabular-nums">{i + 1}</span>
              <span className="mt-0.5 line-clamp-2 block font-medium">{s.title}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex min-h-[260px] flex-col md:aspect-video rounded-sm border bg-card p-6 md:p-10">
          <h3 className="text-xl font-semibold text-balance md:text-3xl">{slide.title}</h3>
          {slide.body ? <p className="mt-3 text-sm whitespace-pre-line text-muted-foreground md:text-base">{slide.body}</p> : null}
          <ul className="mt-4 list-disc space-y-1.5 pl-5 text-sm md:text-lg">
            {slide.bullets.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <button className="btn-ghost" disabled={index === 0} onClick={() => setIndex(index - 1)} type="button">
            Previous
          </button>
          <span className="tabular-nums">
            {index + 1} / {slides.length}
          </span>
          <button
            className="btn-ghost"
            disabled={index >= slides.length - 1}
            onClick={() => setIndex(index + 1)}
            type="button"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
