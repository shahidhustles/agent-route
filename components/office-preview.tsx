"use client";

import { ChevronLeftIcon, ChevronRightIcon, DownloadIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type Manifest = {
  kind: "pptx" | "docx" | "xlsx";
  pages: { page: string; thumb: string }[];
  pdf: string;
  sheets: string | null;
};
type Cell = { v: string; b: boolean; i: boolean; fg: string | null; bg: string | null; al: string | null; num: boolean };
type Sheet = { name: string; rows: number; cols: number; cells: Cell[][]; widths: number[]; merges: string[]; charts: number };

const label = { pptx: "slide", docx: "page", xlsx: "page" } as const;

/** Page images of a real .pptx, .docx or .xlsx. The backend converts it in a no-network container; this fetches the result. */
export function OfficePreview({ runId, name }: { runId: string; name: string }) {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const href = `/api/py/runs/${runId}/file/${name}`;

  useEffect(() => {
    const controller = new AbortController();
    setManifest(null);
    setError(null);
    fetch(`/api/py/runs/${runId}/preview/${name}`, { signal: controller.signal })
      .then(async (r) => {
        const data = await r.json().catch(() => null);
        if (!r.ok) throw new Error(data?.error ?? `The preview failed (HTTP ${r.status}).`);
        setManifest(data as Manifest);
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [runId, name, attempt]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 truncate text-sm text-ash">
          {name}
          {manifest ? ` · ${manifest.pages.length} ${label[manifest.kind]}${manifest.pages.length === 1 ? "" : "s"}` : ""}
        </p>
        <a className={buttonVariants({ size: "sm", variant: "outline" })} download href={href}>
            <DownloadIcon aria-hidden className="size-3.5" />
            Download {name}
          </a>
      </div>
      {error ? (
        <div className="space-y-2 rounded-sm border border-fail p-3 text-sm text-fail" role="alert">
          <p>{error}</p>
          <p className="text-ash">The file itself is fine to download. Only the preview failed.</p>
          <Button onClick={() => setAttempt(attempt + 1)} size="sm" type="button" variant="outline">
            Try the preview again
          </Button>
        </div>
      ) : !manifest ? (
        <PreviewSkeleton />
      ) : manifest.kind === "pptx" ? (
        <Deck pages={manifest.pages} />
      ) : manifest.kind === "docx" ? (
        <Pages pages={manifest.pages} />
      ) : (
        <Workbook manifest={manifest} />
      )}
    </div>
  );
}

export function PreviewSkeleton() {
  return (
    <div aria-busy aria-label="Converting the file for preview" className="space-y-3" role="status">
      <Skeleton className="aspect-video w-full" />
      <div className="flex gap-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton className="aspect-video w-24" key={i} />
        ))}
      </div>
      <p className="text-xs text-ash">Converting with LibreOffice in an isolated container. This takes 5 to 20 seconds.</p>
    </div>
  );
}

function Deck({ pages }: { pages: Manifest["pages"] }) {
  const [i, setI] = useState(0);
  const go = useCallback((d: number) => setI((n) => Math.min(pages.length - 1, Math.max(0, n + d))), [pages.length]);
  return (
    <div
      className="space-y-3 outline-none"
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") go(1);
        if (e.key === "ArrowLeft") go(-1);
      }}
      role="group"
      tabIndex={0}
      aria-label="Slide viewer, use the arrow keys to change slide"
    >
      <div className="overflow-hidden border bg-muted">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img alt={`Slide ${i + 1} of ${pages.length}`} className="block w-full" src={pages[i].page} />
      </div>
      <div className="flex items-center justify-center gap-3 text-sm">
        <Button aria-label="Previous slide" disabled={i === 0} onClick={() => go(-1)} size="sm" type="button" variant="outline">
          <ChevronLeftIcon className="size-4" />
        </Button>
        <span className="tabular-nums">
          Slide {i + 1} of {pages.length}
        </span>
        <Button aria-label="Next slide" disabled={i === pages.length - 1} onClick={() => go(1)} size="sm" type="button" variant="outline">
          <ChevronRightIcon className="size-4" />
        </Button>
      </div>
      <Thumbs current={i} onPick={setI} pages={pages} />
    </div>
  );
}

function Thumbs({ pages, current, onPick }: { pages: Manifest["pages"]; current: number; onPick: (n: number) => void }) {
  return (
    <ol aria-label="Thumbnails" className="flex gap-2 overflow-x-auto pb-1">
      {pages.map((p, n) => (
        <li className="shrink-0" key={p.thumb}>
          <button
            aria-current={n === current}
            aria-label={`Go to ${n + 1}`}
            className={`block overflow-hidden border-2 ${n === current ? "border-ink" : "border-transparent hover:border-concrete"}`}
            onClick={() => onPick(n)}
            type="button"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img alt="" className="h-16 w-auto" loading="lazy" src={p.thumb} />
          </button>
        </li>
      ))}
    </ol>
  );
}

function Pages({ pages }: { pages: Manifest["pages"] }) {
  const [i, setI] = useState(0);
  return (
    <div className="space-y-3">
      {pages.length > 1 ? <Thumbs current={i} onPick={(n) => { setI(n); document.getElementById(`doc-page-${n}`)?.scrollIntoView({ block: "nearest" }); }} pages={pages} /> : null}
      <div className="max-h-[640px] space-y-4 overflow-auto bg-muted p-3">
        {pages.map((p, n) => (
          <div className="shadow-sm" id={`doc-page-${n}`} key={p.page}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img alt={`Page ${n + 1} of ${pages.length}`} className="block w-full bg-white" loading={n < 2 ? "eager" : "lazy"} src={p.page} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Workbook({ manifest }: { manifest: Manifest }) {
  const [view, setView] = useState<"sheets" | "pages">("sheets");
  const [sheets, setSheets] = useState<Sheet[] | null>(null);
  const [active, setActive] = useState(0);
  useEffect(() => {
    if (!manifest.sheets) return;
    fetch(manifest.sheets)
      .then((r) => r.json())
      .then((d: { sheets: Sheet[] }) => setSheets(d.sheets))
      .catch(() => setSheets([]));
  }, [manifest.sheets]);
  return (
    <div className="space-y-3">
      <div className="flex gap-1" role="tablist">
        {(
          [
            ["sheets", "Sheets"],
            ["pages", "Printed pages and charts"],
          ] as const
        ).map(([id, text]) => (
          <button aria-selected={view === id} className={`tab ${view === id ? "" : "text-ash"}`} key={id} onClick={() => setView(id)} role="tab" type="button">
            {text}
          </button>
        ))}
      </div>
      {view === "pages" ? (
        <Pages pages={manifest.pages} />
      ) : !sheets ? (
        <Skeleton className="h-[320px] w-full" />
      ) : !sheets.length ? (
        <p className="text-sm text-ash">The sheets could not be read. The printed pages tab still shows the workbook.</p>
      ) : (
        <div className="space-y-2">
          <div className="flex gap-1 overflow-x-auto" role="tablist">
            {sheets.map((s, n) => (
              <button
                aria-selected={n === active}
                className={`shrink-0 border px-3 py-1 text-sm ${n === active ? "border-ink bg-fog" : "border-transparent text-ash"}`}
                key={s.name}
                onClick={() => setActive(n)}
                role="tab"
                type="button"
              >
                {s.name}
                {s.charts ? ` (${s.charts} chart${s.charts > 1 ? "s" : ""})` : ""}
              </button>
            ))}
          </div>
          <SheetGrid sheet={sheets[active]} />
          {sheets[active].charts ? <p className="text-xs text-ash">Charts show on the printed pages tab.</p> : null}
        </div>
      )}
    </div>
  );
}

function colName(n: number) {
  let s = "";
  for (n += 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  return s;
}

function SheetGrid({ sheet }: { sheet: Sheet }) {
  const cut = sheet.rows > sheet.cells.length || sheet.cols > (sheet.cells[0]?.length ?? 0);
  return (
    <div>
      <div className="max-h-[520px] overflow-auto border">
        <table className="border-collapse text-[13px]">
          <thead>
            <tr>
              <th className="sticky top-0 left-0 z-20 w-10 border bg-muted" />
              {sheet.widths.map((w, c) => (
                <th className="sticky top-0 z-10 border bg-muted px-2 py-0.5 font-normal text-ash" key={c} style={{ minWidth: Math.max(48, w * 7) }}>
                  {colName(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sheet.cells.map((row, r) => (
              <tr key={r}>
                <th className="sticky left-0 z-10 border bg-muted px-2 font-normal text-ash">{r + 1}</th>
                {row.map((cell, c) => (
                  <td
                    className="max-w-[320px] truncate border px-2 py-0.5 whitespace-nowrap"
                    key={c}
                    style={{
                      background: cell.bg ?? undefined,
                      color: cell.fg ?? undefined,
                      fontWeight: cell.b ? 600 : undefined,
                      fontStyle: cell.i ? "italic" : undefined,
                      textAlign: (cell.al as "left" | "center" | "right" | null) ?? (cell.num ? "right" : "left"),
                    }}
                  >
                    {cell.v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {cut ? <p className="mt-1 text-xs text-ash">Showing the first {sheet.cells.length} rows and {sheet.cells[0]?.length ?? 0} columns. Download the file for the rest.</p> : null}
    </div>
  );
}
