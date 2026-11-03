"use client";

import { useEffect, useMemo, useState } from "react";

import { AGENTS, AGENT_LABEL, DEEPSEEK, MODEL_NAME, api, type Agent, type Artifact, type Recorded } from "@/lib/api";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { notify } from "@/lib/notify";

import { ArtifactSkeleton, ArtifactView } from "./artifact-view";
import { TabList } from "./tab-list";

/** Free previews: every block renders a real artifact recorded in agents-cc-20261031, with no model call. */
export function RecordedView() {
  const [index, setIndex] = useState<Recorded[]>([]);
  const [agent, setAgent] = useState<Agent>("code");
  const [model, setModel] = useState(DEEPSEEK);
  const short = model.split("/").pop();
  const [task, setTask] = useState<string>("");
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingIndex, setLoadingIndex] = useState(true);

  useEffect(() => {
    api<Recorded[]>("recorded")
      .then(setIndex, (e) => {
        setError(e instanceof Error ? e.message : String(e));
        notify.error(e, "Could not load the recorded examples");
      })
      .finally(() => setLoadingIndex(false));
  }, []);

  const tasks = useMemo(() => index.filter((r) => r.agent === agent && r.model === model), [index, agent, model]);
  useEffect(() => {
    const first = tasks.find((t) => t.passed) ?? tasks[0];
    setTask(first?.task_id ?? "");
  }, [tasks]);

  useEffect(() => {
    setError(null);
    setArtifact(null);
    if (!task || !tasks.some((t) => t.task_id === task)) return;
    api<Artifact>(`recorded/${short}/${agent}/${task}`).then(setArtifact, (e) => {
      setError(e instanceof Error ? e.message : String(e));
      notify.error(e, "Could not load this artifact");
    });
  }, [task, short, agent, tasks]);

  const current = tasks.find((t) => t.task_id === task);
  return (
    <div className="space-y-4">
      <p className="max-w-2xl text-[15px] text-ash">
        Finished runs from the 320-run agent x model study. Each opens in the block that renders its output contract.
      </p>
      <TabList
        className="flex flex-wrap gap-1.5"
        items={AGENTS.map((a) => [a, AGENT_LABEL[a]] as const)}
        label="Agent"
        onChange={setAgent}
        value={agent}
      />
      {loadingIndex ? (
        <div aria-busy aria-label="Loading recorded examples" className="flex flex-wrap items-center gap-4" role="status">
          <Skeleton className="h-[34px] w-44" />
          <Skeleton className="h-[34px] w-72 max-w-full" />
          <Skeleton className="h-[16px] w-24" />
        </div>
      ) : !tasks.length && !error ? (
        <p className="border-t pt-4 text-[14px] text-ash">No recorded runs for {AGENT_LABEL[agent]} on {MODEL_NAME[model]}. Pick another agent or model.</p>
      ) : null}
      <div className={`flex flex-wrap items-center gap-4 text-[13px] ${loadingIndex ? "hidden" : ""}`}>
        <label className="chrome flex items-center gap-2 text-ash">
          Model
          <select className="field !w-auto !px-2 !py-1 !text-[13px]" onChange={(e) => setModel(e.target.value)} value={model}>
            {Object.entries(MODEL_NAME).map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
        </label>
        <label className="chrome flex min-w-0 items-center gap-2 text-ash">
          Task
          <select className="field !w-auto min-w-0 max-w-[60vw] !px-2 !py-1 !text-[13px]" onChange={(e) => setTask(e.target.value)} value={task}>
            {tasks.map((t) => (
              <option key={t.task_id} value={t.task_id}>
                {t.task_id} {t.passed === false ? "(failed)" : t.passed === null ? "(judge pending)" : ""}
              </option>
            ))}
          </select>
        </label>
        {current ? (
          <span className="chrome text-ash tabular-nums">
            {current.wall_s?.toFixed(0)} s, ${current.cost_usd?.toFixed(4)}
          </span>
        ) : null}
      </div>
      {error ? (
        <Alert variant="destructive">
          <div>
            <AlertTitle>Could not load</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </div>
        </Alert>
      ) : null}
      {artifact ? (
        <div className="panel p-6">
          <ArtifactView artifact={artifact} docxHref={`/api/py/recorded/${short}/${agent}/${task}/docx`} key={`${model}${agent}${task}`} />
        </div>
      ) : !error && (loadingIndex || tasks.length) ? (
        <div className="panel p-6">
          <ArtifactSkeleton />
        </div>
      ) : null}
    </div>
  );
}
