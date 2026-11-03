"use client";

import { CircleCheckIcon, OctagonXIcon, TriangleAlertIcon } from "lucide-react";
import { useState } from "react";

import { HINT, Term } from "@/components/term";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AGENT_LABEL, DEEPSEEK, MODEL_NAME, money, pct, type Run } from "@/lib/api";
import { copyText } from "@/lib/notify";

import { ArtifactView, ArtifactSkeleton } from "./artifact-view";

/** `agents/run.py` keeps the last 500 characters of the agent's final message. */
const NOTE_LIMIT = 500;

export function ResultView({
  run,
  onMark,
  onRerun,
  busy,
}: {
  run: Run;
  onMark: (passed: boolean) => Promise<void>;
  onRerun: () => void;
  busy: string | null;
}) {
  const [pending, setPending] = useState<boolean | null>(null);
  const r = run.result;
  if (!r) return null;
  const contractOk = r.contract?.passed === true;
  const stopped = r.status === "stopped";
  // A decision belongs to the model it chose. A run on another model (a manual rerun) has none of its own.
  const route = run.route && run.route.model === run.model && run.route.agent === run.agent ? run.route : null;
  const runner = route?.runner_up;
  const manual = run.rerun_of
    ? `manual rerun, ${MODEL_NAME[run.model] ?? run.model} estimate ${pct(run.before.p_pass)} pass`
    : "chosen by hand";
  const runnerUp =
    [runner?.agent ? AGENT_LABEL[runner.agent.agent] : null, runner?.model ? MODEL_NAME[runner.model.model] : null]
      .filter(Boolean)
      .join(" / ") || "none";
  const mark = async (passed: boolean) => {
    setPending(passed);
    await onMark(passed);
    setPending(null);
  };
  const Icon = stopped ? TriangleAlertIcon : contractOk ? CircleCheckIcon : OctagonXIcon;
  return (
    <section aria-label="Result" className="space-y-6">
      <dl className="grid grid-cols-2 gap-x-12 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Agent" value={AGENT_LABEL[run.agent]} />
        <Stat label="Model" value={MODEL_NAME[run.model] ?? run.model} />
        <Stat
          hint={HINT.confidence}
          label="Confidence"
          value={
            route
              ? `${route.manual_agent ? "agent chosen by hand" : `${pct(route.confidence.agent)} agent`}, ${pct(route.confidence.model)} model`
              : manual
          }
        />
        <Stat hint={HINT.runnerUp} label="Runner-up" value={route ? runnerUp : "none"} />
        <Stat label="Cost" value={money(r.cost_usd)} />
        <Stat label="Wall time" value={`${r.wall_s.toFixed(1)} s`} />
      </dl>

      <Alert className={stopped ? "border-concrete" : undefined} role="status" variant={stopped || contractOk ? "default" : "destructive"}>
        <Icon aria-hidden className={`mt-0.5 size-4 shrink-0 ${stopped ? "text-ink" : contractOk ? "text-ok" : "text-fail"}`} />
        <div className="min-w-0">
          <AlertTitle>{stopped ? "Stopped" : contractOk ? "Contract passed" : "Contract failed"}</AlertTitle>
          <AlertDescription className="break-words">{stopped ? `${r.detail}. Nothing was recorded.` : r.detail}</AlertDescription>
        </div>
      </Alert>

      <div className="flex flex-wrap gap-2">
        {!contractOk && !stopped && run.model !== DEEPSEEK ? (
          <Button disabled={!!busy} loading={busy === "Starting"} onClick={onRerun} type="button">
            Rerun on DeepSeek
          </Button>
        ) : null}
        <Button onClick={() => copyText(window.location.href, "run link")} type="button" variant="outline">
          Copy run link
        </Button>
      </div>

      {run.artifact ? (
        <div className="panel p-6">
          <ArtifactView artifact={run.artifact} docxHref={`/api/py/runs/${run.id}/docx`} forceRaw={!contractOk} runId={run.id} />
        </div>
      ) : null}

      {r.final_text ? (
        <p className="text-[14px] text-ash">
          Agent note: {r.final_text.length >= NOTE_LIMIT ? `\u2026${r.final_text}` : r.final_text}
          {r.final_text.length >= NOTE_LIMIT ? <span> (cut: only the last {NOTE_LIMIT} characters are kept)</span> : null}
        </p>
      ) : null}

      {r.appended ? (
        <div className="space-y-2 border-t pt-4 text-[14px]">
          {run.marked === null ? (
            <div className="flex flex-wrap items-center gap-3">
              <span>
                {r.record_passed === false
                  ? "Recorded as failed because the contract failed. Mark it good if you disagree."
                  : "Was this result good? The run sits in the memory without a verdict until you answer."}
              </span>
              <Button disabled={!!busy} loading={pending === true} onClick={() => mark(true)} type="button" variant="outline">
                Good
              </Button>
              <Button disabled={!!busy} loading={pending === false} onClick={() => mark(false)} type="button" variant="outline">
                Bad
              </Button>
            </div>
          ) : (
            <p>
              Marked {run.marked ? "good" : "bad"}.
              {run.mark_effect ? (
                <>
                  {" "}
                  The next route sees it: {MODEL_NAME[run.model]} on {AGENT_LABEL[run.agent]} went from{" "}
                  {run.mark_effect.before.runs_seen} to {run.mark_effect.after.runs_seen} past runs, and its estimated pass from{" "}
                  {pct(run.mark_effect.before.p_pass)} to {pct(run.mark_effect.after.p_pass)}.
                </>
              ) : null}
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="border-t pt-3">
      <dt className="chrome text-ash">{hint ? <Term hint={hint}>{label}</Term> : label}</dt>
      <dd className="text-[16px] tabular-nums">{value}</dd>
    </div>
  );
}

/** Stat row, verdict line and artifact frame at the sizes ResultView settles on. */
export function ResultSkeleton() {
  return (
    <section aria-busy aria-label="Loading result" className="space-y-6" role="status">
      <div className="grid grid-cols-2 gap-x-12 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
        {["Agent", "Model", "Confidence", "Runner-up", "Cost", "Wall time"].map((k) => (
          <div className="border-t pt-3" key={k}>
            <p className="chrome text-ash">{k}</p>
            <Skeleton className="mt-1 h-6 w-24" />
          </div>
        ))}
      </div>
      <Skeleton className="h-[74px] w-full" />
      <div className="panel p-6">
        <ArtifactSkeleton />
      </div>
      <p className="sr-only">Loading the result.</p>
    </section>
  );
}
