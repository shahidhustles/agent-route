"use client";

import dynamic from "next/dynamic";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { parse } from "papaparse";
import { useMemo, useState } from "react";

import type { ChartSpec } from "@/components/blocks/chart/chart";
import { MicrosoftWord } from "@/components/blocks/docx/microsoft-word";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Artifact } from "@/lib/api";
import { copyText } from "@/lib/notify";

import { HtmlPreview } from "./html-preview";
import { OfficePreview } from "./office-preview";
import { TabList } from "./tab-list";

// Each block shows a skeleton the size of the settled block while its chunk loads, so the panel does not jump.
const lazy = <T,>(loader: () => Promise<T>, height: string) =>
  dynamic(loader as never, { ssr: false, loading: () => <BlockSkeleton height={height} /> });
function BlockSkeleton({ height }: { height: string }) {
  return <Skeleton aria-busy aria-label="Loading block" className={height} role="status" />;
}
export const ArtifactSkeleton = () => (
  <div aria-busy aria-label="Loading artifact" role="status">
    <div className="mb-4 flex gap-1">
      {["Rendered", "Raw output"].map((t) => (
        <span className="tab text-ash" key={t}>
          {t}
        </span>
      ))}
    </div>
    <Skeleton className="h-[360px] w-full" />
  </div>
);

const CodeView = lazy(() => import("@/components/blocks/code/code-view").then((m) => m.CodeView), "h-[360px]") as React.ComponentType<{ content: string }>;
const DeckView = lazy(() => import("@/components/blocks/slides/deck-view").then((m) => m.DeckView), "h-[420px]") as React.ComponentType<{ content: string }>;
const SceneView = lazy(() => import("@/components/blocks/three/scene-view").then((m) => m.SceneView), "h-[320px]") as React.ComponentType<{ content: string }>;
const MapView = lazy(() => import("@/components/blocks/map/map-artifact-preview").then((m) => m.MapArtifactPreview), "h-[480px]") as React.ComponentType<{ content: string }>;
const Mermaid = lazy(() => import("@/components/blocks/mermaid/mermaid-diagram").then((m) => m.MermaidDiagram), "h-[240px]") as React.ComponentType<{ source: string }>;
const Sheet = lazy(() => import("@/components/blocks/sheet/spreadsheet-editor").then((m) => m.SpreadsheetEditor), "h-[360px]") as React.ComponentType<{
  content: string;
  saveContent: (c: string, v: boolean) => void;
  currentVersionIndex: number;
  isCurrentVersion: boolean;
  status: string;
}>;
const Chart = lazy(() => import("@/components/blocks/chart/chart").then((m) => m.ChartView), "h-[300px]") as React.ComponentType<{ spec: ChartSpec }>;

function json<T>(text: string | undefined): T | null {
  try {
    return text ? (JSON.parse(text) as T) : null;
  } catch {
    return null;
  }
}

function Bad({ children }: { children: React.ReactNode }) {
  return <p className="rounded-sm border border-fail p-3 text-sm text-fail">{children}</p>;
}

type SheetChanges = {
  ops?: Record<string, unknown>[];
  chart?: { type: string; title: string; xKey: string; yKeys: string[]; aggregate?: string; groupBy?: string };
  findings?: { label: string; value: unknown; note?: string }[];
};

function sheetChart(csv: string, chart: NonNullable<SheetChanges["chart"]>): ChartSpec {
  const rows = parse<Record<string, string>>(csv, { header: true, skipEmptyLines: true }).data;
  const groups = new Map<string, Record<string, number[]>>();
  for (const row of rows) {
    const key = row[chart.xKey] ?? "";
    const g = groups.get(key) ?? {};
    for (const y of chart.yKeys) (g[y] ??= []).push(Number(row[y]));
    groups.set(key, g);
  }
  const agg = chart.aggregate ?? "sum";
  const data = [...groups].slice(0, 50).map(([x, g]) => ({
    [chart.xKey]: x,
    ...Object.fromEntries(
      chart.yKeys.map((y) => {
        const v = (g[y] ?? []).filter((n) => Number.isFinite(n));
        const sum = v.reduce((a, b) => a + b, 0);
        return [y, agg === "count" ? (g[y] ?? []).length : agg === "avg" ? sum / (v.length || 1) : sum];
      })
    ),
  }));
  const pie = chart.type === "pie";
  return {
    chartType: chart.type,
    title: chart.title,
    description: `${groups.size} groups, ${agg}`,
    xAxisKey: pie ? "name" : chart.xKey,
    yAxisKeys: chart.yKeys,
    data: pie ? data.map((d) => ({ name: d[chart.xKey], value: d[chart.yKeys[0]] })) : data,
  };
}

function SpreadsheetPanel({ files }: { files: Record<string, string> }) {
  const csv = files["result.csv"] ?? "";
  const changes = json<SheetChanges>(files["changes.json"]);
  const chart = useMemo(() => (changes?.chart ? sheetChart(csv, changes.chart) : null), [csv, changes]);
  return (
    <div className="space-y-4">
      <div className="h-[360px] overflow-hidden border-y">
        <Sheet content={csv} currentVersionIndex={0} isCurrentVersion={false} saveContent={() => {}} status="idle" />
      </div>
      {changes?.findings?.length ? (
        <dl className="grid gap-2 sm:grid-cols-3">
          {changes.findings.map((f, i) => (
            <div className="border-t pt-3" key={i}>
              <dt className="text-xs text-ash">{f.label}</dt>
              <dd className="text-lg font-medium tabular-nums">{String(f.value)}</dd>
              {f.note ? <dd className="text-xs text-ash">{f.note}</dd> : null}
            </div>
          ))}
        </dl>
      ) : null}
      {chart ? <Chart spec={chart} /> : null}
      {changes?.ops?.length ? (
        <details className="border-t pt-3 text-sm">
          <summary className="cursor-pointer font-medium">Change log ({changes.ops.length} operations)</summary>
          <ol className="mt-2 list-decimal space-y-1 pl-5 font-mono text-xs">
            {changes.ops.map((op, i) => (
              <li key={i}>{JSON.stringify(op)}</li>
            ))}
          </ol>
        </details>
      ) : null}
    </div>
  );
}

type Analysis = { answers?: Record<string, unknown>; chart?: ChartSpec; insights?: string[] };

function AnalysisPanel({ files }: { files: Record<string, string> }) {
  const doc = json<Analysis>(files["analysis.json"]);
  if (!doc) return <Bad>analysis.json could not be read.</Bad>;
  return (
    <div className="space-y-4">
      {doc.answers ? (
        <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(doc.answers).map(([k, v]) => (
            <div className="border-t pt-3" key={k}>
              <dt className="text-xs text-ash">{k}</dt>
              <dd className="text-lg font-medium tabular-nums">{typeof v === "number" ? v.toLocaleString() : String(v)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {doc.chart ? <Chart spec={doc.chart} /> : null}
      {doc.insights?.length ? (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {doc.insights.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function DocxPanel({ files, docxHref }: { files: Record<string, string>; docxHref?: string }) {
  const doc = json<{ title?: string; markdown?: string }>(files["document.json"]);
  if (!doc?.markdown) return <Bad>document.json has no markdown.</Bad>;
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <MicrosoftWord className="size-6 shrink-0" />
          <h3 className="truncate text-sm font-semibold">{doc.title}</h3>
        </div>
        {docxHref ? (
          <a className="chrome shrink-0 rounded-sm border px-2.5 py-1 text-ash transition-colors hover:border-concrete hover:bg-fog active:bg-mortar" download href={docxHref}>
            Download .docx
          </a>
        ) : null}
      </div>
      {/* Markdown is rendered without raw HTML, so generated text cannot inject markup or script. */}
      <article className="prose-doc max-h-[560px] overflow-auto border-y p-6 text-sm leading-relaxed [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_h1]:mb-3 [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:mt-5 [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mt-4 [&_h3]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_ol>li]:list-decimal [&_p]:my-2 [&_table]:my-3 [&_table]:w-full [&_td]:border [&_td]:p-1.5 [&_th]:border [&_th]:bg-muted [&_th]:p-1.5">
        <Markdown remarkPlugins={[remarkGfm]}>{doc.markdown}</Markdown>
      </article>
    </div>
  );
}

function DiagramPanel({ files }: { files: Record<string, string> }) {
  const doc = json<{ source?: string }>(files["diagram.json"]);
  const [showSource, setShowSource] = useState(false);
  if (!doc?.source) return <Bad>diagram.json has no source.</Bad>;
  return (
    <div className="space-y-2">
      <div className="max-h-[560px] overflow-auto border-y p-2">
        <Mermaid source={doc.source} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => setShowSource(!showSource)} size="sm" type="button" variant="outline">
          {showSource ? "Hide" : "Show"} Mermaid source
        </Button>
        <Button onClick={() => copyText(doc.source ?? "", "Mermaid source")} size="sm" type="button" variant="outline">
          Copy source
        </Button>
      </div>
      {showSource ? <pre className="overflow-auto rounded-sm bg-muted p-3 font-mono text-xs">{doc.source}</pre> : null}
    </div>
  );
}

function Raw({ files, binary }: { files: Record<string, string>; binary?: Record<string, number> }) {
  const names = Object.keys(files);
  const sizes = Object.entries(binary ?? {});
  if (!names.length && !sizes.length) return <p className="text-sm text-ash">The agent wrote no output files.</p>;
  return (
    <div className="space-y-3">
      {sizes.map(([n, bytes]) => (
        <p className="text-xs text-ash" key={n}>
          File out/{n}, {(bytes / 1024).toFixed(0)} KB. A binary file; the rendered view shows it.
        </p>
      ))}
      {names.map((n) => (
        <div key={n}>
          <div className="mb-1 flex items-center justify-between gap-3">
            <p className="text-xs text-ash">File out/{n}</p>
            <Button onClick={() => copyText(files[n], n)} size="sm" type="button" variant="outline">
              Copy
            </Button>
          </div>
          <pre className="max-h-80 overflow-auto rounded-sm bg-muted p-3 font-mono text-xs whitespace-pre-wrap">{files[n].slice(0, 30000)}</pre>
        </div>
      ))}
    </div>
  );
}

const OFFICE_FILE: Partial<Record<Artifact["agent"], string>> = {
  slides: "deck.pptx",
  docx: "document.docx",
  spreadsheet: "workbook.xlsx",
  "data-analysis": "analysis.xlsx",
};
const HTML_FILE: Partial<Record<Artifact["agent"], string>> = { diagram: "diagram.html", map: "map.html", "scene-3d": "scene.html" };

/** The real file a run produced: converted to page images in the backend (Office) or shown in a sandboxed frame (HTML). */
function RealFile({ artifact, runId }: { artifact: Artifact; runId: string }) {
  const expected = { office: OFFICE_FILE[artifact.agent], html: HTML_FILE[artifact.agent] };
  // The router can send a request to an agent whose file differs from what the request needed; show any real file written.
  const office = expected.office && artifact.binary[expected.office] ? expected.office : Object.keys(artifact.binary).find((n) => /\.(pptx|docx|xlsx)$/.test(n)) ?? expected.office;
  const html = expected.html && artifact.files[expected.html] ? expected.html : Object.keys(artifact.files).find((n) => n.endsWith(".html")) ?? expected.html;
  if (office && artifact.binary[office]) return <OfficePreview key={`${runId}${office}`} name={office} runId={runId} />;
  if (html && artifact.files[html])
    return <HtmlPreview height={artifact.agent === "map" ? "h-[520px]" : "h-[560px]"} key={runId} name={html} runId={runId} />;
  if (artifact.agent === "code") return <CodeView content={artifact.files["solution.py"] ?? ""} />;
  return <Bad>The agent did not write its output file, so there is nothing to preview. Raw output lists what it did write.</Bad>;
}

export function ArtifactView({ artifact, docxHref, forceRaw, runId }: { artifact: Artifact; docxHref?: string; forceRaw?: boolean; runId?: string }) {
  const [tab, setTab] = useState<"rendered" | "raw">(forceRaw ? "raw" : "rendered");
  const f = artifact.files;
  let body: React.ReactNode;
  if (artifact.contract === "files" && runId) body = <RealFile artifact={artifact} runId={runId} />;
  else
  switch (artifact.agent) {
    case "code":
      body = <CodeView content={f["solution.py"] ?? ""} />;
      break;
    case "spreadsheet":
      body = <SpreadsheetPanel files={f} />;
      break;
    case "data-analysis":
      body = <AnalysisPanel files={f} />;
      break;
    case "docx":
      body = <DocxPanel docxHref={docxHref} files={f} />;
      break;
    case "slides":
      body = <DeckView content={f["slides.json"] ?? ""} />;
      break;
    case "diagram":
      body = <DiagramPanel files={f} />;
      break;
    case "map":
      body = (
        <div className="h-[480px] [&>div]:h-full">
          <MapView content={f["map.json"] ?? ""} />
        </div>
      );
      break;
    case "scene-3d":
      body = <SceneView content={f["scene.jsonl"] ?? ""} />;
      break;
  }
  return (
    <div>
      <TabList
        className="mb-4 flex gap-1"
        items={[["rendered", "Rendered"], ["raw", "Raw output"]] as const}
        label="Output view"
        onChange={setTab}
        value={tab}
      />
      {tab === "rendered" ? body : <Raw files={f} binary={artifact.binary} />}
    </div>
  );
}
