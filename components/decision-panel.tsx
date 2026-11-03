"use client";

import {
  AGENTS,
  AGENT_LABEL,
  MODEL_NAME,
  PREFERENCES,
  money,
  pct,
  type Agent,
  type Decision,
  type Preference,
  type RouteResponse,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { HINT, Term } from "@/components/term";
import { cn } from "@/lib/utils";

const label = (m: string) => MODEL_NAME[m] ?? m;

export function PreferencePicker({
  route,
  value,
  onChange,
}: {
  route: RouteResponse;
  value: Preference;
  onChange: (p: Preference) => void;
}) {
  return (
    <div aria-label="Preference" className="grid gap-x-12 gap-y-4 sm:grid-cols-2 lg:grid-cols-4" role="radiogroup">
      {PREFERENCES.map((p) => {
        const d = route.decisions[p];
        const top = d.estimates.find((e) => e.chosen)!;
        const on = value === p;
        return (
          <button
            aria-checked={on}
            className={cn(
              "group border-t pt-4 text-left transition-colors",
              on ? "border-ink" : "border-hairline hover:border-concrete"
            )}
            key={p}
            onClick={() => onChange(p)}
            role="radio"
            type="button"
          >
            <span className="chrome flex items-center justify-between">
              {p}
              {on ? <span className="text-ink">selected</span> : null}
            </span>
            <span className="mt-2 block text-[26px] leading-[1.23] tracking-[0.012em]">{label(d.model)}</span>
            <span className="mt-1 block text-[13px] text-ash">{AGENT_LABEL[d.agent]} agent</span>
            <span className="chrome mt-3 flex flex-wrap gap-x-3 tabular-nums text-ash">
              <span>pass {pct(top.p_pass)}</span>
              <span>{money(top.cost_usd)}</span>
              <span>{top.wall_s.toFixed(0)} s</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function DecisionPanel({ decision, agents }: { decision: Decision; agents: RouteResponse["agents"] }) {
  const ru = decision.runner_up;
  return (
    <section aria-label="Router decision" className="panel grid gap-8 p-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="min-w-0 space-y-6">
        <div>
          <p className="chrome text-ash">Agent</p>
          <p className="text-[36px] leading-[1.11] tracking-[0.012em]">{AGENT_LABEL[decision.agent]}</p>
          <p className="text-[13px] text-ash tabular-nums">
            {decision.manual_agent ? (
              <>
                Chosen by you. The nearest-task <Term hint={HINT.voteShare}>vote share</Term> for it was {pct(decision.confidence.agent)}.{" "}
              </>
            ) : (
              <>
                <Term hint={HINT.voteShare}>vote share</Term> {pct(decision.confidence.agent)}.{" "}
              </>
            )}
            {ru.agent ? (
              <>
                <Term hint={HINT.runnerUp}>Runner-up</Term> {AGENT_LABEL[ru.agent.agent]} {pct(ru.agent.share)}.
              </>
            ) : (
              "No other agent among the nearest tasks."
            )}
          </p>
        </div>
        <div>
          <p className="chrome text-ash">Model</p>
          <p className="text-[36px] leading-[1.11] tracking-[0.012em]">{label(decision.model)}</p>
          <p className="text-[13px] text-ash tabular-nums">
            <Term hint={HINT.estimatedPass}>estimated pass</Term> {pct(decision.confidence.model)}.
            {ru.model ? (
              <>
                {" "}
                <Term hint={HINT.runnerUp}>Runner-up</Term> {label(ru.model.model)} {pct(ru.model.p_pass)}, {money(ru.model.cost_usd)}.
              </>
            ) : null}
          </p>
        </div>
      </div>
      <div className="min-w-0 space-y-4">
        <p className="text-[15px] text-pretty text-graphite">{decision.reasoning}</p>
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="chrome border-b text-left text-ash">
                <th className="py-2 pr-4 font-medium">Model</th>
                <th className="py-2 pr-4 text-right font-medium">Pass</th>
                <th className="py-2 pr-4 text-right font-medium">Cost</th>
                <th className="py-2 pr-4 text-right font-medium">Wall</th>
                <th className="py-2 pr-4 text-right font-medium whitespace-nowrap">
                  <Term hint={HINT.pastRuns}>Past runs</Term>
                </th>
                <th className="py-2 font-medium">
                  <Term hint={HINT.considered}>Considered</Term>
                </th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {decision.estimates.map((e) => (
                <tr className={cn("border-b last:border-0", e.chosen && "font-medium")} key={e.model}>
                  <td className="py-2 pr-4">{label(e.model)}{e.chosen ? " (chosen)" : ""}</td>
                  <td className="py-2 pr-4 text-right">{pct(e.p_pass)}</td>
                  <td className="py-2 pr-4 text-right">{money(e.cost_usd)}</td>
                  <td className="py-2 pr-4 text-right whitespace-nowrap">{e.wall_s.toFixed(0)} s</td>
                  <td className="py-2 pr-4 text-right">{e.runs_seen}</td>
                  <td className="py-2 text-ash">{e.eligible ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[13px] text-ash">
          Nearest-task vote: {agents.map((a) => `${AGENT_LABEL[a.agent]} ${pct(a.share)}`).join(", ")}.
        </p>
      </div>
    </section>
  );
}

/** All eight agents with their vote share, for the first pick and for changing it later. */
function AgentButtons({
  votes,
  current,
  disabled,
  onPick,
}: {
  votes: RouteResponse["agents"];
  current?: Agent;
  disabled?: boolean;
  onPick: (a: Agent) => void;
}) {
  const share = new Map(votes.map((v) => [v.agent, v.share]));
  const order = [...AGENTS].sort((a, b) => (share.get(b) ?? 0) - (share.get(a) ?? 0));
  return (
    <div className="flex flex-wrap gap-2">
      {order.map((a) => (
        <Button aria-pressed={current === a} disabled={disabled || current === a} key={a} onClick={() => onPick(a)} type="button" variant="outline">
          {AGENT_LABEL[a]} <span className="text-ash tabular-nums">{pct(share.get(a) ?? 0)}</span>
        </Button>
      ))}
    </div>
  );
}

/** Shown on every route. Picking an agent routes the same task again for that agent, so its models are re-estimated. */
export function ChangeAgent({
  votes,
  current,
  disabled,
  onPick,
}: {
  votes: RouteResponse["agents"];
  current?: Agent;
  disabled?: boolean;
  onPick: (a: Agent) => void;
}) {
  return (
    <section aria-label="Change agent" className="space-y-2">
      <p className="chrome text-ash">Change agent</p>
      <p className="text-[13px] text-ash">The router chose from the nearest-task vote. Pick another agent and its models are estimated again.</p>
      <AgentButtons current={current} disabled={disabled} onPick={onPick} votes={votes} />
    </section>
  );
}

export function AgentChoice({ agents, onPick }: { agents: RouteResponse["agents"]; onPick: (a: Agent) => void }) {
  return (
    <section aria-label="Choose an agent" className="panel space-y-4 border-concrete p-6">
      <p className="text-[15px]">
        The router is not sure which agent fits: the top vote share is {pct(agents[0].share)}. Pick one before anything runs.
      </p>
      <AgentButtons onPick={onPick} votes={agents} />
    </section>
  );
}

/** Same grid and heights as PreferencePicker and DecisionPanel, so the page does not move when the route arrives. */
export function DecisionSkeleton() {
  return (
    <div aria-busy aria-label="Routing" className="space-y-12" role="status">
      <div className="grid gap-x-12 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
        {PREFERENCES.map((p) => (
          <div className="border-t border-hairline pt-4" key={p}>
            <Skeleton className="h-[16px] w-16" />
            <Skeleton className="mt-2 h-[32px] w-32" />
            <Skeleton className="mt-2 h-[20px] w-28" />
            <Skeleton className="mt-3 h-[16px] w-40" />
          </div>
        ))}
      </div>
      <section className="panel grid gap-8 p-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="min-w-0 space-y-6">
          {["Agent", "Model"].map((k) => (
            <div key={k}>
              <p className="chrome text-ash">{k}</p>
              <Skeleton className="mt-1 h-[40px] w-48" />
              <Skeleton className="mt-2 h-[20px] w-64 max-w-full" />
            </div>
          ))}
        </div>
        <div className="min-w-0 space-y-4">
          <Skeleton className="h-[44px] w-full" />
          <Skeleton className="h-[172px] w-full" />
          <Skeleton className="h-[20px] w-3/4" />
        </div>
      </section>
      <p className="sr-only">Routing the task.</p>
    </div>
  );
}
