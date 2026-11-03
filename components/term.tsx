"use client";

import { useState, type ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Plain-language hints for the router's own terms. */
export const HINT = {
  confidence: "How strongly the nearest past tasks back this choice: the agent's vote share and the model's estimated pass rate.",
  runnerUp: "The next best option the router weighed and passed over.",
  easyScore: "The Modal router's probability that the fastest model passes this prompt. A high score marks the task as easy.",
  threshold: "The score a preference needs before it uses its cheaper pick. Lower scores go to the fallback model. Each preference has its own, set on validation data.",
  answerConfidence: "The Modal router's own probability that the model it picked passes. It is not the agent router's vote share, and a cheap pick can score low here while the easy score is high.",
  voteShare: "Share of the most similar past tasks that were handled by this agent.",
  estimatedPass: "Chance the run meets its output contract, estimated from this model's past runs on similar tasks.",
  pastRuns: "How many recorded runs the estimate rests on. Fewer runs, weaker estimate.",
  considered: "A model counts when its estimated pass rate is within the tolerance of the reference model. Others are never picked.",
} as const;

/** A dotted-underline term with a hint. A tap toggles it, since touch screens have no hover. */
export function Term({ children, hint }: { children: ReactNode; hint: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip onOpenChange={setOpen} open={open}>
      <TooltipTrigger asChild>
        <button
          className="cursor-help font-[inherit] tracking-[inherit] [text-transform:inherit] underline decoration-concrete decoration-dotted underline-offset-4 hover:decoration-ink"
          onClick={() => setOpen((o) => !o)}
          type="button"
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent>{hint}</TooltipContent>
    </Tooltip>
  );
}
