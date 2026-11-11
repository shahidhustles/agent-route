"use client";

import { DownloadIcon } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";

/**
 * A self-contained HTML artifact in a sandboxed frame. `allow-scripts` without `allow-same-origin` gives the page an
 * opaque origin, so its script cannot read the app's cookies, storage or DOM. The backend also serves it under a CSP
 * that blocks every request off the page, so the "no network" rule holds even if an agent breaks it. The page loads
 * by URL, not srcDoc, because a three.js scene is over 600 KB.
 */
export function HtmlPreview({ runId, name, height = "h-[560px]" }: { runId: string; name: string; height?: string }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="min-w-0 truncate text-sm text-ash">{name}</p>
        <a className={buttonVariants({ size: "sm", variant: "outline" })} download href={`/api/runs/${runId}/file/${name}`}>
          <DownloadIcon aria-hidden className="size-3.5" />
          Download {name}
        </a>
      </div>
      <iframe className={`${height} w-full border bg-white`} referrerPolicy="no-referrer" sandbox="allow-scripts" src={`/api/runs/${runId}/view/${name}`} title={name} />
    </div>
  );
}
