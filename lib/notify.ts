import { toast } from "sonner";

import { BackendDownError } from "@/lib/api";

/** Errors stay until dismissed. Everything else clears itself. */
const STICKY = { duration: Infinity } as const;

export type Failure = "backend" | "weekly" | "cap" | "other";

export function classify(error: unknown): Failure {
  if (error instanceof BackendDownError) return "backend";
  const text = error instanceof Error ? error.message : String(error);
  if (/weekly usage limit/i.test(text)) return "weekly";
  if (/spend cap/i.test(text)) return "cap";
  return "other";
}

export const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

/** Toasts for the states in the spec. The same text also stays inline wherever it blocks the next step. */
export const notify = {
  copied: (what: string) => toast.success(`Copied ${what}`, { id: "copied" }),
  copyFailed: () => toast.error("Could not copy. The browser blocked clipboard access.", { ...STICKY, id: "copy-failed" }),
  saved: (verdict: "good" | "bad") => toast.success(`Verdict saved: ${verdict}`, { description: "The next route sees it.", id: "verdict" }),
  capSet: (usd: string) => toast.success(`Spend cap set to ${usd}`, { id: "cap-set" }),
  rerun: (model: string) => toast.info(`Rerun started on ${model}`, { id: "rerun" }),
  runFailed: (detail: string) => toast.error("The run failed", { ...STICKY, description: detail, id: "run-failed" }),
  capHit: (detail: string) =>
    toast.error("Spend cap reached", { ...STICKY, description: `${detail}. Raise the cap in the header to continue.`, id: "cap-hit" }),
  weeklyLimit: (detail: string) =>
    toast.error("Weekly usage limit reached", { ...STICKY, description: `${detail}. Live runs resume after the reset.`, id: "weekly" }),
  backendDown: () =>
    toast.error("Backend unreachable", { ...STICKY, description: "Start it with bun run web:backend, then try again.", id: "backend" }),
  /** Routes any thrown error to the toast that fits it. */
  error(error: unknown, fallback = "Something went wrong") {
    const kind = classify(error);
    if (kind === "backend") return notify.backendDown();
    if (kind === "weekly") return notify.weeklyLimit(message(error));
    if (kind === "cap") return notify.capHit(message(error));
    return toast.error(fallback, { ...STICKY, description: message(error) });
  },
};

export async function copyText(text: string, what: string) {
  try {
    await navigator.clipboard.writeText(text);
    notify.copied(what);
  } catch {
    notify.copyFailed();
  }
}
