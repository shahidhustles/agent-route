import { createUIMessageStream, createUIMessageStreamResponse } from "ai";
import { z } from "zod";
import { rejectAnonymous } from "@/lib/require-user";
import { routeAnswer } from "@/lib/answer";
import { AGENTS, PREFERENCES, type RouteResponse, type Run } from "@/lib/api";
import { sse } from "@/lib/chat-stream";

export const maxDuration = 600;
const BACKEND = process.env.ROUTER_BACKEND_URL ?? "http://127.0.0.1:8765";
const input = z.object({
  messages: z.array(
    z.object({
      role: z.enum(["user", "assistant", "system"]),
      parts: z.array(z.object({ type: z.string(), text: z.string().optional() }).passthrough()),
    }),
  ),
  preference: z.enum(PREFERENCES).default("balanced"),
  agentMode: z.boolean().default(false),
  csv: z
    .object({ name: z.string(), body: z.string().max(1_000_000) })
    .nullable()
    .optional(),
  override: z
    .object({
      agent: z.enum(AGENTS).optional(),
      model: z.string().optional(),
      rerun_of: z.string().optional(),
    })
    .nullable()
    .optional(),
});
const runEvent = z.object({
  kind: z.enum(["start", "thinking", "tool", "text", "tokens", "error", "done"]),
  i: z.number(),
  text: z.string().optional(),
  tool: z.string().optional(),
  t: z.number().optional(),
});
const answerEvent = z.discriminatedUnion("type", [
  z.object({ type: z.literal("delta"), text: z.string() }),
  z.object({ type: z.literal("error"), error: z.string() }),
  z.object({
    type: z.literal("done"),
    model: z.string(),
    wall_s: z.number(),
    cost_usd: z.number(),
  }),
]);
async function backend<T>(path: string, body?: unknown): Promise<T> {
  let response;
  try {
    response = await fetch(`${BACKEND}/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new Error("The backend is unavailable. Start the router backend and try again.");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error ?? "The request failed.");
  return data;
}
export async function POST(request: Request) {
  const rejected = await rejectAnonymous();
  if (rejected) return rejected;
  const parsed = input.safeParse(await request.json());
  if (!parsed.success)
    return Response.json({ error: "Invalid chat request or CSV too large." }, { status: 400 });
  const { messages, preference, agentMode, csv, override } = parsed.data;
  const history = messages
    .filter((m) => m.role !== "system")
    .map((m) => ({
      role: m.role,
      content: m.parts
        .filter((p) => p.type === "text")
        .map((p) => p.text ?? "")
        .join("\n"),
    }))
    .filter((m) => m.content);
  const text = history.findLast((m) => m.role === "user")?.content ?? "";
  if (!text.trim()) return Response.json({ error: "Write a message first." }, { status: 400 });
  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      writer.write({ type: "start", messageId: crypto.randomUUID() });
      let runId: string | undefined;
      let active: string | undefined;
      const cancel = () => {
        if (runId) void backend(`runs/${runId}/cancel`, {}).catch(() => {});
      };
      request.signal.addEventListener("abort", cancel, { once: true });
      const finishStep = () => {
        if (active)
          writer.write({
            type: "tool-output-available",
            toolCallId: active,
            output: { done: true },
          });
        active = undefined;
      };
      try {
        // Fail fast when offline, before waiting on Modal's cold start.
        const status = await backend<{ stopped: string | null }>("status");
        if (status.stopped) throw new Error(`Live calls are stopped: ${status.stopped}`);
        if (agentMode) {
          const route = await backend<RouteResponse>("route", { text, agent: override?.agent });
          const decision = route.decisions[preference];
          writer.write({
            type: "message-metadata",
            messageMetadata: { route, preference, agentMode: true },
          });
          const started = await backend<{ id: string }>("runs", {
            text,
            agent: override?.agent ?? decision.agent,
            model: override?.model ?? decision.model,
            preference,
            route: decision,
            routed_text: text,
            csv,
            rerun_of: override?.rerun_of,
          });
          runId = started.id;
          writer.write({ type: "message-metadata", messageMetadata: { runId } });
          if (request.signal.aborted) {
            cancel();
            return;
          }
          const response = await fetch(`${BACKEND}/runs/${runId}/events`, {
            signal: request.signal,
            cache: "no-store",
          });
          // The last agent message is also the final reply, so each one waits for a later step before it is shown.
          let heldText: z.infer<typeof runEvent> | undefined;
          const writeStep = (event: z.infer<typeof runEvent>) => {
            finishStep();
            active = `${runId}-${event.i}`;
            writer.write({
              type: "tool-input-available",
              toolCallId: active,
              toolName:
                event.kind === "tool"
                  ? (event.tool ?? "tool")
                  : event.kind === "start"
                    ? "thinking"
                    : event.kind,
              input: { text: event.text ?? "Starting agent", time: event.t },
            });
          };
          for await (const value of sse(response)) {
            const event = runEvent.parse(value);
            if (["start", "thinking", "tool", "text", "error"].includes(event.kind)) {
              if (heldText) writeStep(heldText);
              heldText = undefined;
              if (event.kind === "text") heldText = event;
              else writeStep(event);
            }
          }
          const run = await backend<Run>(`runs/${runId}`);
          if (heldText?.text && !run.result?.final_text?.startsWith(heldText.text))
            writeStep(heldText);
          finishStep();
          writer.write({ type: "message-metadata", messageMetadata: { run, runId } });
          if (run.status === "running")
            throw new Error(
              "The agent connection was interrupted before it finished. Check the backend before rerunning.",
            );
          const finalText = run.result?.final_text;
          const detail = run.result?.detail || "The run finished.";
          const reply =
            finalText && (run.status === "stopped" || run.status === "error")
              ? `${finalText}\n\n${detail}`
              : finalText || detail;
          writer.write({ type: "text-start", id: "answer" });
          writer.write({ type: "text-delta", id: "answer", delta: reply });
          writer.write({ type: "text-end", id: "answer" });
        } else {
          const routing = await routeAnswer(text, preference);
          writer.write({
            type: "message-metadata",
            messageMetadata: { routing, preference, agentMode: false },
          });
          const response = await fetch(`${BACKEND}/answer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              text,
              model: override?.model ?? routing.model,
              stream: true,
              messages: history,
            }),
            signal: request.signal,
          });
          writer.write({ type: "text-start", id: "answer" });
          for await (const value of sse(response)) {
            const event = answerEvent.parse(value);
            if (event.type === "delta")
              writer.write({ type: "text-delta", id: "answer", delta: event.text });
            if (event.type === "error") throw new Error(event.error);
            if (event.type === "done")
              writer.write({ type: "message-metadata", messageMetadata: { answer: event } });
          }
          writer.write({ type: "text-end", id: "answer" });
        }
        writer.write({ type: "finish" });
      } catch (error) {
        finishStep();
        if (request.signal.aborted) {
          cancel();
          return;
        }
        writer.write({ type: "text-start", id: "error" });
        writer.write({
          type: "text-delta",
          id: "error",
          delta: error instanceof Error ? error.message : "The request failed. Try again.",
        });
        writer.write({ type: "text-end", id: "error" });
        writer.write({ type: "message-metadata", messageMetadata: { failed: true } });
        writer.write({ type: "finish" });
      } finally {
        request.signal.removeEventListener("abort", cancel);
      }
    },
    onError: () => "The connection was interrupted. Try again.",
  });
  return createUIMessageStreamResponse({ stream });
}
