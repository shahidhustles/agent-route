import { z } from "zod";
import { AGENTS, PREFERENCES } from "./api";
const estimate = z.object({
  model: z.string(),
  p_pass: z.number(),
  wall_s: z.number(),
  cost_usd: z.number(),
  runs_seen: z.number(),
});
const decision = z.object({
  agent: z.enum(AGENTS),
  model: z.string(),
  reasoning: z.string(),
  confidence: z.object({ agent: z.number(), model: z.number() }),
  runner_up: z.object({
    agent: z.object({ agent: z.enum(AGENTS), share: z.number() }).nullable(),
    model: z.object({ model: z.string() }).passthrough().nullable(),
  }),
  estimates: z.array(estimate),
});
const artifact = z.object({
  agent: z.enum(AGENTS),
  files: z.record(z.string(), z.string()),
  binary: z.record(z.string(), z.number()),
  contract: z.literal("files").optional(),
});
export const chatMeta = z.object({
  preference: z.enum(PREFERENCES).optional(),
  agentMode: z.boolean().optional(),
  failed: z.boolean().optional(),
  runId: z.string().optional(),
  run: z
    .object({
      id: z.string(),
      text: z.string(),
      agent: z.enum(AGENTS),
      model: z.string(),
      marked: z.boolean().nullable(),
      status: z.string(),
      artifact: artifact.nullable(),
      result: z
        .object({ cost_usd: z.number(), wall_s: z.number(), appended: z.boolean().optional() })
        .passthrough()
        .nullable(),
    })
    .optional(),
  route: z
    .object({
      agents: z.array(z.object({ agent: z.enum(AGENTS), share: z.number() })),
      decisions: z.object({
        cheap: decision,
        balanced: decision,
        fast: decision,
        accurate: decision,
      }),
    })
    .optional(),
  routing: z
    .object({
      model: z.string(),
      router: z
        .object({
          probabilities: z.record(z.string(), z.number()),
          confidence: z.number(),
          routing_ms: z.number(),
        })
        .passthrough()
        .nullable(),
      routerError: z.string().optional(),
    })
    .optional(),
  answer: z.object({ model: z.string(), cost_usd: z.number(), wall_s: z.number() }).optional(),
});
export type ChatMeta = z.infer<typeof chatMeta>;
export type ArtifactSelection = {
  artifact: z.infer<typeof artifact>;
  title: string;
  docxHref: string;
  runId?: string;
};
