import {
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  streamText,
  toUIMessageStream,
  tool,
} from "ai";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { z } from "zod";

import { latestUserText, routeTask } from "@/lib/routing";
import {
  COMMAND_CODE_BASE_URL,
  providerModelId,
  type ModelSlug,
} from "@/profiles";
import type { AgentUIMessage } from "@/lib/agent/types";

export const maxDuration = 180;

const SYSTEM_PROMPT = `You are a Python code generator that creates self-contained, executable code snippets. When writing code:

1. Each snippet should be complete and runnable on its own
2. Prefer using print() statements to display outputs
3. Include helpful comments explaining the code
4. Keep snippets concise (generally under 15 lines)
5. Avoid external dependencies - use Python standard library
6. Handle potential errors gracefully
7. Return meaningful output that demonstrates the code's functionality
8. Don't use input() or other interactive functions
9. Don't access files or network resources
10. Don't use infinite loops

When the user asks for code or changes, call updateCodeDocument with the full Python source as a string. Keep chat replies concise; the artifact panel shows the full code.`;

const RATE_LIMIT = 20;
const RATE_WINDOW_MS = 5 * 60 * 1000;
const rateHits = new Map<string, { count: number; resetAt: number }>();

function enforceRateLimit(identifier: string):
  | { ok: true }
  | { ok: false; headers: Headers } {
  const now = Date.now();
  const entry = rateHits.get(identifier);
  if (!entry || entry.resetAt <= now) {
    rateHits.set(identifier, { count: 1, resetAt: now + RATE_WINDOW_MS });
    return { ok: true };
  }
  entry.count += 1;
  if (entry.count > RATE_LIMIT) {
    const headers = new Headers({
      "Retry-After": Math.ceil((entry.resetAt - now) / 1000).toString(),
    });
    return { ok: false, headers };
  }
  return { ok: true };
}

export async function POST(request: Request) {
  const apiKey = process.env.CMD_API_KEY;
  if (!apiKey) {
    return Response.json(
      { error: "CMD_API_KEY is not configured on this server." },
      { status: 500 },
    );
  }

  const identifier =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "local";
  const limit = enforceRateLimit(identifier);
  if (!limit.ok) {
    return Response.json(
      { error: "Rate limit hit for the code artifact agent. Try again later." },
      { headers: limit.headers, status: 429 },
    );
  }

  const { messages }: { messages: AgentUIMessage[] } = await request.json();
  const task = latestUserText(messages);
  const provider = createOpenAICompatible({
    apiKey,
    baseURL: COMMAND_CODE_BASE_URL,
    name: "commandcode",
  });

  const stream = createUIMessageStream<AgentUIMessage>({
    originalMessages: messages,
    execute: async ({ writer }) => {
      writer.write({ type: "start" });
      writer.write({
        type: "data-routing",
        id: "routing-status",
        data: { status: "routing" },
      });

      const selection = await routeTask(task);

      writer.write({
        type: "data-routing",
        id: "routing-status",
        data: {
          status: "selected",
          model: selection.model_slug,
          confidence: selection.confidence,
        },
      });
      writer.write({
        type: "data-id",
        id: "artifact-id",
        data: "code-artifact",
      });
      writer.write({
        type: "data-title",
        id: "artifact-title",
        data: "Code artifact",
      });
      writer.write({
        type: "data-kind",
        id: "artifact-kind",
        data: "code",
      });

      const updateCodeDocument = tool({
        description:
          "Replace the artifact content with a complete Python source string.",
        execute: async ({ code }) => {
          writer.write({
            type: "data-codeDelta",
            id: `delta-${Date.now()}`,
            data: code,
          });
          return { ok: true as const };
        },
        inputSchema: z.object({
          code: z.string().describe("Full Python source"),
        }),
      });

      const result = streamText({
        model: provider.chatModel(
          providerModelId(selection.model_slug as ModelSlug),
        ),
        system: SYSTEM_PROMPT,
        messages: await convertToModelMessages(messages),
        toolChoice: "auto",
        tools: { updateCodeDocument },
      });

      writer.merge(
        toUIMessageStream({
          stream: result.stream,
          sendStart: false,
          onError: () =>
            "The response could not be generated. Please try again.",
        }),
      );
    },
    onError: (error) =>
      error instanceof Error ? error.message : "The request failed.",
  });

  return createUIMessageStreamResponse({ stream });
}
