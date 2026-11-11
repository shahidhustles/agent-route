import { ARTIFACT_BUCKET } from "@/lib/supabase/config";
import { artifactPath } from "@/lib/persistence/runs";
import { serverSupabase } from "@/lib/supabase/server";

const BACKEND = process.env.ROUTER_BACKEND_URL ?? "http://127.0.0.1:8765";
// No leading dot, so "." and ".." never reach the backend URL or a Storage path.
const SAFE = /^(?!\.)[\w.-]+$/;
const TYPES: Record<string, string> = {
  jpg: "image/jpeg",
  pdf: "application/pdf",
  json: "application/json",
  html: "text/html; charset=utf-8",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};
const HTML_CSP =
  "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:";

/**
 * Serves a run's files and page images. A run saved to Supabase Storage is read from there, so its preview opens in
 * any browser and after the backend's own run folder is gone. A run still being saved falls through to the backend.
 * Paths match the backend's own: file/<name>, view/<name>, preview/<name> and preview/<name>/<asset>.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ runId: string; rest: string[] }> },
) {
  const { runId, rest } = await params;
  const [kind, name, asset, ...extra] = rest;
  if (
    !SAFE.test(runId) ||
    ![kind, name, asset].every((p) => p === undefined || SAFE.test(p)) ||
    extra.length
  )
    return Response.json({ error: "Not found." }, { status: 404 });

  const stored = await serverSupabase();
  if (stored) {
    const path =
      kind === "preview"
        ? artifactPath(stored.userId, runId, "preview", name ?? "", asset ?? "manifest.json")
        : kind === "file" || kind === "view"
          ? artifactPath(stored.userId, runId, name ?? "")
          : null;
    if (path) {
      const { data } = await stored.db.storage.from(ARTIFACT_BUCKET).download(path);
      if (data) {
        const file = (asset ?? name ?? "").split(".").pop() ?? "";
        const headers = new Headers({
          "Content-Type":
            TYPES[kind === "preview" && !asset ? "json" : file] ?? "application/octet-stream",
          "Cache-Control": "private, max-age=3600",
          "X-Content-Type-Options": "nosniff",
        });
        if (kind === "view") headers.set("Content-Security-Policy", HTML_CSP);
        if (kind === "file") headers.set("Content-Disposition", `attachment; filename="${name}"`);
        return new Response(data, { headers });
      }
    }
  }

  const response = await fetch(`${BACKEND}/runs/${runId}/${rest.join("/")}`, {
    cache: "no-store",
  }).catch(() => null);
  if (!response)
    return Response.json({ error: "The router backend is not answering." }, { status: 502 });
  const headers = new Headers();
  for (const key of [
    "content-type",
    "content-disposition",
    "content-security-policy",
    "cache-control",
  ]) {
    const value = response.headers.get(key);
    if (value) headers.set(key, value);
  }
  headers.set("X-Content-Type-Options", "nosniff");
  return new Response(response.body, { status: response.status, headers });
}
