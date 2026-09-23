import type { UIMessage } from "ai";

import { MVP_MODEL_PROFILES } from "@/profiles";
import { resultSchema } from "@/runtime";

const ROUTER_MODELS = new Set(["glm-5.3-flash", "deepseek-v4.1-flash"]);
const ROUTER_PROFILES = MVP_MODEL_PROFILES.filter((profile) =>
  ROUTER_MODELS.has(profile.model_slug),
);

export type RoutingSelection = Readonly<{
  model_slug: string;
  confidence: number;
}>;

export function latestUserText(messages: readonly UIMessage[]): string {
  const message = messages.findLast((entry) => entry.role === "user");
  const text = message?.parts
    .filter(
      (part): part is Extract<(typeof message.parts)[number], { type: "text" }> =>
        part.type === "text",
    )
    .map((part) => part.text)
    .join("\n")
    .trim();

  if (!text) throw new Error("Send a text prompt before routing.");
  return text;
}

export async function routeTask(task: string): Promise<RoutingSelection> {
  const urlValue = process.env.MODAL_ROUTER_URL;
  const tokenId = process.env.MODAL_PROXY_TOKEN_ID;
  const tokenSecret = process.env.MODAL_PROXY_TOKEN_SECRET;

  if (!urlValue || !tokenId || !tokenSecret) {
    throw new Error("The Modal router is not configured on this server.");
  }

  const url = new URL(urlValue);
  if (url.protocol !== "https:" || !url.hostname.endsWith(".modal.run")) {
    throw new Error("The Modal router URL must use HTTPS on modal.run.");
  }

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Modal-Key": tokenId,
      "Modal-Secret": tokenSecret,
    },
    body: JSON.stringify({
      user_task: task,
      candidate_models: ROUTER_PROFILES.map((profile) => profile.model_slug),
      profiles: ROUTER_PROFILES,
      requires_tools: false,
      input_tokens: Math.ceil(new TextEncoder().encode(task).length / 4),
    }),
    redirect: "error",
    signal: AbortSignal.timeout(120_000),
  });

  if (!response.ok) throw new Error(`The Modal router returned HTTP ${response.status}.`);
  const body = (await response.json()) as Record<string, unknown>;
  return resultSchema.parse({ model_slug: body.model_slug, confidence: body.confidence });
}
