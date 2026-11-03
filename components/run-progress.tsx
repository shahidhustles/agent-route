"use client";

import { useEffect, useRef } from "react";

import { Progress } from "@/components/ui/progress";
import type { RunEvent } from "@/lib/api";
import { cn } from "@/lib/utils";

const STEPS = ["Queued", "Agent started", "Working", "Checking contract", "Finished"] as const;

/** The run has no known length, so progress is the stage it has reached, read from the event stream. */
function stage(events: RunEvent[], running: boolean) {
  if (!running) return 4;
  if (events.some((e) => e.kind === "done")) return 3;
  if (events.some((e) => e.kind === "tool" || e.kind === "thinking" || e.kind === "text")) return 2;
  if (events.some((e) => e.kind === "start")) return 1;
  return 0;
}

// The one blue block of the system: the run's event stream as monospaced columns of text, as on Parallel's hero.
export function RunProgress({ events, running }: { events: RunEvent[]; running: boolean }) {
  const end = useRef<HTMLLIElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [events.length]);
  const tokens = events.reduce((n, e) => (e.kind === "tokens" ? n + e.output : n), 0);
  const tools = events.filter((e) => e.kind === "tool").length;
  const last = [...events].reverse().find((e) => "t" in e) as { t: number } | undefined;
  const at = stage(events, running);
  return (
    <section aria-label="Run progress" aria-live="polite" className="rounded-sm bg-blueprint p-6 text-white">
      <div className="chrome mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-white/80">
        <span>{STEPS[at]}</span>
        <span className="flex gap-x-3 tabular-nums">
          {last ? <span>{last.t.toFixed(0)} s</span> : null}
          {tools ? <span>{tools} tool calls</span> : null}
          {tokens ? <span>{tokens} output tokens</span> : null}
        </span>
      </div>
      <Progress
        aria-label="Run stage"
        className="bg-white/25"
        indicatorClassName="bg-white"
        max={100}
        value={(at / (STEPS.length - 1)) * 100}
      />
      <ol aria-label="Stages" className="chrome mt-2 mb-4 grid grid-cols-5 gap-2 text-white/60">
        {STEPS.map((s, i) => (
          <li aria-current={i === at ? "step" : undefined} className={cn("truncate", i <= at && "text-white")} key={s} title={s}>
            <span className="hidden sm:inline">{s}</span>
            <span className="sm:hidden">{i + 1}</span>
          </li>
        ))}
      </ol>
      {!events.length ? <p className="chrome mb-2 text-white/75">Waiting for the sandbox to start</p> : null}
      <ol className="max-h-60 min-h-24 space-y-1 overflow-auto font-mono text-[12px] leading-[1.5]">
        {events
          .filter((e) => ["tool", "thinking", "error", "text", "start"].includes(e.kind))
          .map((e) => (
            <li className="flex gap-3" key={e.i}>
              <span className="w-10 shrink-0 text-right text-white/50 tabular-nums">{"t" in e ? e.t.toFixed(0) + "s" : ""}</span>
              {e.kind === "tool" ? (
                <span className="min-w-0 break-words"><b className="font-medium">{e.tool}</b> <span className="text-white/75">{e.text}</span></span>
              ) : e.kind === "error" ? (
                <span className="font-medium text-blush">{e.text}</span>
              ) : e.kind === "text" ? (
                <span className="min-w-0 break-words text-white/75">agent: {e.text}</span>
              ) : e.kind === "start" ? (
                <span className="text-white/75">started {e.agent} on {e.model}</span>
              ) : e.kind === "thinking" ? (
                <span className="text-white/60">{e.text}</span>
              ) : null}
            </li>
          ))}
        <li ref={end} />
      </ol>
    </section>
  );
}
