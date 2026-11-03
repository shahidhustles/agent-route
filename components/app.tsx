"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { OctagonXIcon, ServerCrashIcon } from "lucide-react";

import {
  AGENTS,
  DEEPSEEK,
  MODEL_NAME,
  PREFERENCES,
  api,
  money,
  type Agent,
  type Answer,
  type Preference,
  type RouteResponse,
  type Run,
  type RunEvent,
  type Status,
} from "@/lib/api";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { BackendDownError } from "@/lib/api";
import { classify, copyText, message, notify } from "@/lib/notify";
import { csvSizeError, isStale, isTooLong } from "@/lib/route-state";
import { HINT, Term } from "./term";

import { AgentChoice, ChangeAgent, DecisionPanel, DecisionSkeleton, PreferencePicker } from "./decision-panel";
import { RecordedView } from "./recorded-view";
import { ResultSkeleton, ResultView } from "./result-view";
import { RunProgress } from "./run-progress";
import { TabList } from "./tab-list";

type Mode = "agent" | "answer";
type View = "task" | "recorded";

export function App() {
  const [view, setView] = useState<View>("task");
  const [mode, setMode] = useState<Mode>("agent");
  const [text, setText] = useState("");
  const [preference, setPreference] = useState<Preference>("cheap");
  const [csv, setCsv] = useState<{ name: string; body: string } | null>(null);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [pickedAgent, setPickedAgent] = useState<Agent | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [answer, setAnswer] = useState<(Answer & { waited_s: number; preference: Preference }) | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [backendDown, setBackendDown] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [loadingRun, setLoadingRun] = useState(false);
  const source = useRef<EventSource | null>(null);

  const refreshStatus = useCallback(
    () =>
      api<Status>("status").then(
        (s) => {
          setBackendDown(false);
          setStatus(s);
        },
        (e) => {
          // The poll runs every 8 s; the toast has a fixed id, so it never stacks.
          if (e instanceof BackendDownError) {
            setBackendDown(true);
            notify.backendDown();
          }
        }
      ),
    []
  );
  // A stopped ledger is announced once per reason, not on every poll.
  const announced = useRef<string | null>(null);
  useEffect(() => {
    if (!status?.stopped) {
      announced.current = null;
      return;
    }
    if (announced.current === status.stopped) return;
    announced.current = status.stopped;
    if (/weekly usage limit/i.test(status.stopped)) notify.weeklyLimit(status.stopped);
    else notify.capHit(status.stopped);
  }, [status?.stopped]);
  useEffect(() => {
    refreshStatus();
    const t = setInterval(refreshStatus, 8000);
    return () => clearInterval(t);
  }, [refreshStatus]);
  useEffect(() => () => source.current?.close(), []);

  /** Stream a run's progress and load the result when it ends. The server replays events from the start, so a reload sees them all. */
  const follow = (id: string) => {
    source.current?.close();
    const es = new EventSource(`/api/py/runs/${id}/events`);
    source.current = es;
    es.onmessage = async (m) => {
      const ev = JSON.parse(m.data) as RunEvent;
      setEvents((prev) => [...prev, ev]);
      if (ev.kind === "done") {
        es.close();
        setFinishing(true);
        try {
          const done = await api<Run>(`runs/${id}`);
          setRun(done);
          reportRun(done);
        } catch (e) {
          fail(e, "Could not load the finished run");
        } finally {
          setFinishing(false);
        }
        refreshStatus();
      }
    };
    es.onerror = () => {
      // The stream also closes after `done`; only report a drop while the run is still going.
      es.close();
      api<Run>(`runs/${id}`).then((r) => {
        setRun(r);
        if (r.status === "running") fail(new Error("The progress stream dropped. Reload the run from the server."), "Progress stream dropped");
        else reportRun(r);
        refreshStatus();
      }, (e) => fail(e));
    };
  };

  // A run link (?run=<id>) reopens a run after a reload. A run still going reconnects to its progress.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("run");
    if (!id) return;
    setLoadingRun(true);
    api<Run>(`runs/${id}`)
      .then(
        (r) => {
          setText(r.text);
          setRun(r);
          if (r.status === "running") follow(id);
        },
        (e) => notify.error(e, "Could not reopen that run")
      )
      .finally(() => setLoadingRun(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reset = () => {
    source.current?.close();
    window.history.replaceState(null, "", window.location.pathname);
    setRoute(null);
    setPickedAgent(null);
    setRun(null);
    setEvents([]);
    setAnswer(null);
    setError(null);
  };

  /** A failure shows inline where it blocks the next step, and as a toast that stays until dismissed. */
  const fail = (e: unknown, fallback?: string) => {
    setError(message(e));
    notify.error(e, fallback);
  };

  const submit = async (agent?: Agent) => {
    if (!text.trim()) return;
    setError(null);
    setRun(null);
    setEvents([]);
    setAnswer(null);
    try {
      if (mode === "answer") {
        setBusy("Routing, then asking one model");
        setRoute(null);
        const t0 = performance.now();
        const a = await postAnswer(text, preference);
        setAnswer({ ...a, waited_s: (performance.now() - t0) / 1000, preference });
        refreshStatus();
      } else {
        setBusy("Routing");
        const r = await api<RouteResponse>("route", { text, agent });
        setRoute(r);
        setPickedAgent(agent ?? null);
      }
    } catch (e) {
      fail(e, "Routing failed");
    } finally {
      setBusy(null);
    }
  };

  const stale = isStale(route, text);
  // An edit after routing voids the decision: nothing below runs on it until the task is routed again.
  const decision = route && !stale ? route.decisions[preference] : undefined;
  const running = run?.status === "running";
  /** A rerun repeats the original run: its own text, and its CSV, which the backend reads from the original run. */
  const start = async (agent: Agent, model: string, rerun?: Run) => {
    setError(null);
    setEvents([]);
    setFinishing(false);
    setBusy("Starting");
    try {
      const { id } = await api<{ id: string }>("runs", {
        text: rerun ? rerun.text : text,
        agent,
        model,
        preference,
        csv: rerun ? undefined : csv ?? undefined,
        rerun_of: rerun?.id,
        route: rerun ? null : decision ?? null,
        routed_text: rerun ? undefined : route?.task.text,
      });
      setRun({ id, text: rerun ? rerun.text : text, agent, model, status: "running" } as Run);
      if (rerun) notify.rerun(MODEL_NAME[model] ?? model);
      window.history.replaceState(null, "", `?run=${id}`);
      follow(id);
    } catch (e) {
      fail(e, "Could not start the run");
    } finally {
      setBusy(null);
    }
  };

  const mark = async (passed: boolean) => {
    if (!run) return;
    setBusy("Saving");
    try {
      await api(`runs/${run.id}/mark`, { passed });
      setRun(await api<Run>(`runs/${run.id}`));
      refreshStatus();
      notify.saved(passed ? "good" : "bad");
    } catch (e) {
      fail(e, "Could not save the verdict");
    } finally {
      setBusy(null);
    }
  };

  /** Surface a finished run that did not pass cleanly. */
  const reportRun = (r: Run) => {
    const result = r.result;
    if (!result || result.status === "passed") return;
    const kind = classify(new Error(result.detail));
    if (kind === "weekly") notify.weeklyLimit(result.detail);
    else if (kind === "cap" || result.status === "stopped") notify.capHit(result.detail);
    else if (result.status === "error" || result.contract?.passed === false) notify.runFailed(result.detail);
  };

  const needsAgent = route?.low_vote && !pickedAgent;
  const longTask = mode === "agent" && isTooLong(text);
  const needsCsv = decision && (decision.agent === "spreadsheet" || decision.agent === "data-analysis");

  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-8">
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
          <span className="text-[16px] font-medium tracking-[0.01em]">agent router</span>
          <TabList
            className="flex gap-1"
            items={[["task", "Task"], ["recorded", "Recorded examples"]] as const}
            label="View"
            onChange={setView}
            value={view}
          />
        </div>
        <SpendChip onChange={() => refreshStatus()} status={status} />
      </header>

      <main className="mx-auto flex max-w-[1200px] flex-col gap-12 px-4 pt-8 pb-24 sm:px-8">
        {backendDown ? (
          <Alert variant="destructive">
            <ServerCrashIcon aria-hidden className="mt-0.5 size-4 shrink-0" />
            <div className="min-w-0 space-y-3">
              <div>
                <AlertTitle>Backend unreachable</AlertTitle>
                <AlertDescription>
                  The page cannot reach the router backend on port 8765, so routing, runs and recorded examples are off. Start it with{" "}
                  <code className="font-mono text-[13px] text-ink">bun run web:backend</code>, then retry.
                </AlertDescription>
              </div>
              <Button onClick={() => refreshStatus()} size="sm" type="button" variant="outline">
                Retry
              </Button>
            </div>
          </Alert>
        ) : null}
        {status?.stopped ? (
          <Alert className="border-concrete" variant="default">
            <OctagonXIcon aria-hidden className="mt-0.5 size-4 shrink-0" />
            <div className="min-w-0">
              <AlertTitle>Live calls are stopped</AlertTitle>
              <AlertDescription>
                {status.stopped}. {/weekly usage limit/i.test(status.stopped) ? "Live runs resume after the reset." : "Raise the cap in the header to continue."} Recorded examples still work.
              </AlertDescription>
            </div>
          </Alert>
        ) : null}
        {view === "task" ? (
        <section className="max-w-3xl">
          <h1 className="text-[28px] leading-[1.15] tracking-[0.012em] font-medium text-balance sm:text-[36px] sm:leading-[1.11]">
            Describe a task. The router picks the agent and <span className="text-signal">the model</span>.
          </h1>
          <p className="mt-3 text-[18px] leading-[1.35] text-graphite text-pretty">
            Every choice comes from how agents and models did on similar tasks before. You see the numbers, then the run, then the result.
          </p>
        </section>
        ) : null}

        {view === "recorded" ? (
          <RecordedView />
        ) : (
          <>
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                reset();
                submit();
              }}
            >
              <TabList
                className="flex gap-1"
                items={[["agent", "Run an agent"], ["answer", "Just answer"]] as const}
                label="Mode"
                onChange={(m) => {
                  setMode(m);
                  reset();
                }}
                value={mode}
              />
              <textarea
                aria-label="Task"
                className="field min-h-32 resize-y"
                onChange={(e) => setText(e.target.value)}
                placeholder={mode === "agent" ? "Draw a sequence diagram of a login flow with a password reset branch" : "Ask a plain question"}
                value={text}
              />
              {longTask ? (
                <p className="text-[14px] text-graphite" role="status">
                  This task is {text.trim().length.toLocaleString()} characters. The router reads the first 300 and the last 300, so keep the
                  instruction near the start or the end. The agent still gets the whole text.
                </p>
              ) : null}
              {mode === "answer" ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="chrome mr-2 text-ash">Model router preference</span>
                  {PREFERENCES.map((p) => (
                    <button aria-pressed={preference === p} className="tab" key={p} onClick={() => setPreference(p)} type="button">
                      {p}
                    </button>
                  ))}
                </div>
              ) : (
                <label className="chrome flex flex-wrap items-center gap-3 text-ash">
                  Optional CSV for spreadsheet and data tasks
                  <input
                    accept=".csv,text/csv"
                    className="text-[12px] normal-case"
                    onChange={async (e) => {
                      const f = e.target.files?.[0];
                      const tooBig = f ? csvSizeError(f) : null;
                      setCsvError(tooBig);
                      if (!f || tooBig) {
                        setCsv(null);
                        if (tooBig) e.target.value = "";
                        return;
                      }
                      setCsv({ name: f.name.replace(/[^\w.-]/g, "_"), body: await f.text() });
                    }}
                    type="file"
                  />
                  {csv ? <span className="text-ink">attached {csv.name}</span> : null}
                  {csvError ? (
                    <span className="normal-case text-fail" role="alert">
                      {csvError} Attach a smaller file, or{" "}
                      <button
                        className="underline"
                        onClick={(e) => {
                          e.preventDefault();
                          setCsvError(null);
                        }}
                        type="button"
                      >
                        run without one
                      </button>
                      .
                    </span>
                  ) : null}
                </label>
              )}
              <div className="flex items-center gap-4">
                <Button disabled={!text.trim() || running || backendDown} loading={!!busy && busy !== "Saving" && busy !== "Starting"} type="submit">
                  {mode === "agent" ? "Route task" : "Route and answer"}
                </Button>
                {busy ? <span className="chrome text-ash">{busy}…</span> : null}
              </div>
            </form>

            {error ? (
              <Alert variant="destructive">
                <OctagonXIcon aria-hidden className="mt-0.5 size-4 shrink-0" />
                <div className="min-w-0">
                  <AlertTitle>Something stopped</AlertTitle>
                  <AlertDescription className="break-words">{error}</AlertDescription>
                </div>
              </Alert>
            ) : null}

            {mode === "answer" && busy ? <AnswerSkeleton /> : null}
            {mode === "answer" && answer && !busy ? <AnswerView answer={answer} /> : null}
            {!busy && !error && !run && !loadingRun && (mode === "answer" ? !answer : !decision && !needsAgent) ? (
              <EmptyState mode={mode} stale={stale} />
            ) : null}
            {mode === "agent" && busy === "Routing" ? <DecisionSkeleton /> : null}

            {mode === "agent" && route && !stale && busy !== "Routing" ? (
              needsAgent ? (
                <AgentChoice agents={route.agents} onPick={(a) => submit(a)} />
              ) : (
                <>
                  <PreferencePicker onChange={setPreference} route={route} value={preference} />
                  {decision ? <DecisionPanel agents={route.agents} decision={decision} /> : null}
                  <ChangeAgent current={decision?.agent} disabled={!!busy} onPick={(a) => submit(a)} votes={route.agents} />
                  {needsCsv && !csv ? (
                    <p className="text-[14px] text-ash">This agent works on a data file. Attach a CSV above, or it will have nothing to open.</p>
                  ) : null}
                  {!run && decision ? (
                    <div>
                      <Button
                        disabled={!!busy || !!status?.stopped || backendDown || !!csvError}
                        loading={busy === "Starting"}
                        onClick={() => start(decision.agent, decision.model)}
                        type="button"
                      >
                        Run {MODEL_NAME[decision.model]} on the {decision.agent} agent
                      </Button>
                    </div>
                  ) : null}
                </>
              )
            ) : null}

            {run && (running || events.length) ? <RunProgress events={events} running={!!running} /> : null}
            {(finishing || loadingRun) && !run?.result ? <ResultSkeleton /> : null}
            {run?.result ? (
              <ResultView
                busy={busy}
                onMark={mark}
                onRerun={() => start(run.agent, DEEPSEEK, run)}
                run={run}
              />
            ) : null}
          </>
        )}
      </main>
    </div>
  );
}

async function postAnswer(text: string, preference: Preference): Promise<Answer> {
  let response: Response;
  try {
    response = await fetch("/api/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, preference }),
    });
  } catch {
    throw new BackendDownError();
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (data?.error) throw new Error(data.error);
    throw response.status >= 500 ? new BackendDownError() : new Error(`HTTP ${response.status}`);
  }
  return data as Answer;
}

function EmptyState({ mode, stale }: { mode: Mode; stale: boolean }) {
  return (
    <section aria-label="Nothing routed yet" className="max-w-2xl border-t pt-4">
      <p className="chrome text-ash">{mode === "agent" ? (stale ? "Route again" : "No route yet") : "No answer yet"}</p>
      <p className="mt-1 text-[14px] text-ash">
        {mode === "agent"
          ? stale
            ? "The task changed after it was routed, so the old decision is gone. Press Route task to route the new text."
            : "Describe a task above and press Route task. The decision, its numbers and the run appear here. Recorded examples open without any model call."
          : "Ask a plain question above. The model router picks one model and its answer appears here."}
      </p>
    </section>
  );
}

/** Same frame as AnswerView. The Modal model router sleeps when idle, so the first call can be slow. */
function AnswerSkeleton() {
  return (
    <section aria-busy aria-label="Waiting for the answer" className="panel space-y-3 p-6" role="status">
      <Skeleton className="h-[21px] w-full max-w-xl" />
      <Skeleton className="h-[16px] w-28" />
      <div className="max-w-3xl space-y-2">
        <Skeleton className="h-[24px] w-full" />
        <Skeleton className="h-[24px] w-11/12" />
        <Skeleton className="h-[24px] w-2/3" />
      </div>
      <p className="text-[14px] text-ash">The first call can take about a minute while the model router starts. Later calls take seconds.</p>
    </section>
  );
}

function AnswerView({ answer }: { answer: Answer & { waited_s: number; preference: Preference } }) {
  const r = answer.router;
  return (
    <section aria-label="Answer" className="panel space-y-3 p-6">
      <div className="space-y-1 text-[14px] text-ash">
        {r ? (
          <>
            <p>
              Model router picked <b className="font-medium text-ink">{MODEL_NAME[answer.model] ?? answer.model}</b> for the{" "}
              <b className="font-medium text-ink">{answer.preference}</b> preference.{" "}
              {r.easy_score !== undefined ? (
                <>
                  Its <Term hint={HINT.easyScore}>easy score</Term> was {Math.round(r.easy_score * 100)}%. The{" "}
                  <Term hint={HINT.threshold}>threshold</Term> for {answer.preference} is {Math.round(r.threshold * 100)}%, so the task counted as{" "}
                  {r.easy_score >= r.threshold ? "easy and went to the cheap pick for that preference" : "not easy and went to the fallback model"}.{" "}
                </>
              ) : null}
              The <Term hint={HINT.answerConfidence}>confidence</Term> of {Math.round(r.confidence * 100)}% is the router&apos;s own pass
              probability for the model it picked.
            </p>
            <p>
              All scores:{" "}
              {Object.entries(r.probabilities)
                .sort((a, b) => b[1] - a[1])
                .map(([k, v]) => `${k} ${Math.round(v * 100)}%`)
                .join(", ")}
              .
            </p>
          </>
        ) : (
          <p>Model router unavailable: {answer.router_error}</p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p className="chrome flex gap-x-3 text-ash tabular-nums">
          <span>{answer.waited_s.toFixed(1)} s total wait</span>
          <span>
            {answer.wall_s.toFixed(1)} s model call{r ? `, ${Math.round(r.routing_ms)} ms routing` : ""}
          </span>
          <span>{money(answer.cost_usd)}</span>
        </p>
        <Button onClick={() => copyText(answer.text, "answer")} size="sm" type="button" variant="outline">
          Copy answer
        </Button>
      </div>
      <article className="max-w-3xl text-[16px] leading-[1.5] whitespace-pre-wrap">{answer.text}</article>
    </section>
  );
}

function SpendChip({ status, onChange }: { status: Status | null; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [saving, setSaving] = useState(false);
  if (!status) return <Skeleton className="h-[16px] w-48" />;
  const next = Number(value);
  const valid = value.trim() !== "" && Number.isFinite(next) && next > 0 && next !== status.cap_usd;
  const apply = async () => {
    setSaving(true);
    try {
      await api("settings", { max_usd: next });
      setConfirm(false);
      setEditing(false);
      notify.capSet(money(next));
      onChange();
    } catch (e) {
      setConfirm(false);
      notify.error(e, "Could not change the cap");
    } finally {
      setSaving(false);
    }
  };
  return (
    <div aria-label="Spend" className="chrome flex flex-wrap items-center gap-3 text-ash">
      <span className="tabular-nums">
        Spent {money(status.spent_usd)} of{" "}
        {editing ? (
          <span className="inline-flex items-center gap-2">
            <input
              aria-label="Spend cap in USD"
              autoFocus
              className="w-16 rounded-sm border border-concrete bg-paper px-1 text-ink"
              inputMode="decimal"
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  // Keep the keypress from reaching the dialog that opens and takes focus.
                  e.preventDefault();
                  if (valid) setConfirm(true);
                }
                if (e.key === "Escape") setEditing(false);
              }}
              value={value}
            />
            <Button disabled={!valid} onClick={() => setConfirm(true)} size="sm" type="button">
              Set
            </Button>
            <Button onClick={() => setEditing(false)} size="sm" type="button" variant="outline">
              Cancel
            </Button>
          </span>
        ) : (
          <button
            className="text-ink underline"
            onClick={() => {
              setValue(String(status.cap_usd));
              setEditing(true);
            }}
            type="button"
          >
            {money(status.cap_usd)}
          </button>
        )}
      </span>
      <AlertDialog onOpenChange={setConfirm} open={confirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Change the spend cap?</AlertDialogTitle>
            <AlertDialogDescription>
              The cap limits live Command Code calls from this app. It goes from {money(status.cap_usd)} to {money(next || 0)}. Spent so far:{" "}
              {money(status.spent_usd)}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep {money(status.cap_usd)}</AlertDialogCancel>
            <AlertDialogAction
              disabled={saving}
              onClick={(e) => {
                e.preventDefault();
                apply();
              }}
            >
              {saving ? "Saving…" : `Set to ${money(next || 0)}`}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
