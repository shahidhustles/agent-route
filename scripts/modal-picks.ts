// Ask the deployed Modal model router which model it would pick for each agents-cc-20261031 task, per preference.
//   bun --env-file=.env.modal scripts/modal-picks.ts
// Writes artifacts/router/modal-picks.json. The router sees the task text only; the key never leaves the process.
import { readFileSync, writeFileSync } from "node:fs";
import { createOutcomeRouter } from "../runtime";

const { MODAL_ROUTER_URL, MODAL_PROXY_TOKEN_ID, MODAL_PROXY_TOKEN_SECRET } = process.env;
if (!MODAL_ROUTER_URL || !MODAL_PROXY_TOKEN_ID || !MODAL_PROXY_TOKEN_SECRET) throw new Error("MODAL_* missing");
const route = createOutcomeRouter({ url: MODAL_ROUTER_URL, tokenId: MODAL_PROXY_TOKEN_ID, tokenSecret: MODAL_PROXY_TOKEN_SECRET });

const manifest = JSON.parse(readFileSync("benchmarking/suites/agents-cc-v1.manifest.json", "utf8"));
const prompts = new Map<string, string>();
for (const line of readFileSync("benchmarking/suites/agents-v1.jsonl", "utf8").split("\n").filter(Boolean)) {
  const t = JSON.parse(line);
  prompts.set(t.id, t.prompt);
}
const ids: string[] = Object.values(manifest.tasks as Record<string, string[]>).flat();
const preferences = ["accurate", "balanced", "fast", "cheap"] as const;
const out: Array<{ task_id: string; preference: string; model_slug: string; confidence: number }> = [];
for (const id of ids) {
  for (const preference of preferences) {
    const r = await route({ user_task: prompts.get(id) as string, preference });
    out.push({ task_id: id, preference, model_slug: r.model_slug, confidence: r.confidence });
  }
  console.log(id, out.slice(-4).map((x) => x.model_slug.split("-")[0]).join(" "));
}
writeFileSync("artifacts/router/modal-picks.json", JSON.stringify(out, null, 1));
