import { ARTIFACT_BUCKET } from "@/lib/supabase/config";
import type { Run } from "@/lib/api";
import type { Db } from "./conversations";

const OFFICE = /\.(pptx|docx|xlsx)$/;
const MIME: Record<string, string> = {
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  html: "text/html",
  jpg: "image/jpeg",
  pdf: "application/pdf",
  json: "application/json",
};
const mime = (name: string) => MIME[name.split(".").pop() ?? ""] ?? "application/octet-stream";

type Manifest = {
  pages: { page: string; thumb: string }[];
  pdf?: string;
  sheets?: string | null;
  [key: string]: unknown;
};

export type SaveRunInput = {
  run: Run;
  userId: string;
  conversationId: string | null;
  messageId: string | null;
  /** GET against the Python backend, path relative to its root (`runs/<id>/file/<name>`). */
  backend: (path: string) => Promise<Response>;
};

/** Where a run's files live: the private bucket, under the owner's id. */
export const artifactPath = (userId: string, runId: string, ...rest: string[]) =>
  [userId, runId, ...rest].join("/");

const upload = async (db: Db, path: string, body: Blob | string, name: string) => {
  const { error } = await db.storage
    .from(ARTIFACT_BUCKET)
    .upload(path, body, { upsert: true, contentType: mime(name) });
  if (error) throw new Error(error.message);
};

async function fetched(input: SaveRunInput, path: string) {
  const response = await input.backend(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response;
}

/** Page images, the PDF and the sheet data of one Office file, plus a manifest whose URLs point at /api/runs. */
async function savePreview(db: Db, input: SaveRunInput, name: string): Promise<string[]> {
  const { run, userId } = input;
  const base = `/api/py/runs/${run.id}/preview/${name}`;
  const manifest = (await (
    await fetched(input, `runs/${run.id}/preview/${name}`)
  ).json()) as Manifest;
  const urls = [
    ...manifest.pages.flatMap((p) => [p.page, p.thumb]),
    ...(manifest.pdf ? [manifest.pdf] : []),
    ...(manifest.sheets ? [manifest.sheets] : []),
  ];
  const saved: string[] = [];
  for (let i = 0; i < urls.length; i += 4) {
    await Promise.all(
      urls.slice(i, i + 4).map(async (url) => {
        const asset = url.slice(base.length + 1);
        const response = await fetched(input, url.replace("/api/py/", ""));
        const path = artifactPath(userId, run.id, "preview", name, asset);
        await upload(db, path, await response.blob(), asset);
        saved.push(path);
      }),
    );
  }
  const local = JSON.stringify(manifest).replaceAll("/api/py/runs/", "/api/runs/");
  const manifestPath = artifactPath(userId, run.id, "preview", name, "manifest.json");
  await upload(db, manifestPath, local, "manifest.json");
  return [...saved, manifestPath];
}

/**
 * Writes a finished run: its output files and page images to the artifacts bucket, then the run row.
 * A file that fails to upload is reported, not fatal; the row still records everything that did save.
 */
export async function saveRun(db: Db, input: SaveRunInput) {
  const { run, userId } = input;
  const saved: string[] = [];
  const failed: string[] = [];
  const artifact = run.artifact;
  const names =
    artifact?.contract === "files"
      ? [
          ...Object.keys(artifact.binary),
          ...Object.keys(artifact.files).filter((name) => name.endsWith(".html")),
        ]
      : [];
  for (const name of names) {
    try {
      const response = await fetched(input, `runs/${run.id}/file/${name}`);
      const path = artifactPath(userId, run.id, name);
      await upload(db, path, await response.blob(), name);
      saved.push(path);
    } catch (error) {
      failed.push(`${name}: ${error instanceof Error ? error.message : "upload failed"}`);
      continue;
    }
    if (!OFFICE.test(name)) continue;
    try {
      saved.push(...(await savePreview(db, input, name)));
    } catch (error) {
      failed.push(`${name} preview: ${error instanceof Error ? error.message : "preview failed"}`);
    }
  }
  const { error } = await db.from("runs").upsert({
    id: run.id,
    conversation_id: input.conversationId,
    message_id: input.messageId,
    prompt: run.text,
    agent: run.agent,
    model: run.model,
    preference: run.preference,
    status: run.status,
    cost_usd: run.result?.cost_usd ?? null,
    wall_s: run.result?.wall_s ?? null,
    routing: run.route,
    verdict: run.marked,
    rerun_of: run.rerun_of,
    artifact,
    files: saved,
  });
  if (error) throw new Error(`Saving the run failed: ${error.message}`);
  return { saved, failed };
}

export async function saveVerdict(db: Db, runId: string, passed: boolean) {
  const { error } = await db.from("runs").update({ verdict: passed }).eq("id", runId);
  if (error) throw new Error(`Saving the verdict failed: ${error.message}`);
}
