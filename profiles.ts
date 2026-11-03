export const MODEL_SLUGS = {
  qwenGeneral: "qwen3.8-27b",
  qwenCoder: "qwen2.5-coder-14b-instruct",
  deepSeekReasoning: "deepseek-r1-distill-qwen-14b",
  mistralGeneral: "mistral-small-3.1-24b-instruct",
  gemmaDocument: "gemma-3-27b-it",
  glmFlash: "glm-5.3-flash",
  deepSeekFlash: "deepseek-v4.1-flash",
  nemotronSuperVl: "nemotron-3.5-super-vl",
  mimoFlash: "mimo-v2.6-flash",
} as const;

export type ModelSlug = (typeof MODEL_SLUGS)[keyof typeof MODEL_SLUGS];

export const COMMAND_CODE_BASE_URL = "https://api.commandcode.ai/provider/v1";

export const PROVIDER_MODEL_IDS: Readonly<Partial<Record<ModelSlug, string>>> = {
  [MODEL_SLUGS.glmFlash]: "z-ai/glm-5.3-flash",
  [MODEL_SLUGS.deepSeekFlash]: "deepseek/deepseek-v4.1-flash",
  [MODEL_SLUGS.nemotronSuperVl]: "nvidia/nemotron-3.5-super-vl",
  [MODEL_SLUGS.mimoFlash]: "xiaomi/mimo-v2.6-flash",
};

/** USD per 1M tokens on the Command Code GOAT plan page, 2026-10-28. */
export const PROVIDER_PRICES: Readonly<
  Partial<Record<ModelSlug, Readonly<{ input: number; output: number }>>>
> = {
  [MODEL_SLUGS.glmFlash]: { input: 0.15, output: 0.5 },
  [MODEL_SLUGS.deepSeekFlash]: { input: 0.15, output: 0.6 },
  [MODEL_SLUGS.nemotronSuperVl]: { input: 0.2, output: 0.5 },
  [MODEL_SLUGS.mimoFlash]: { input: 0.14, output: 0.28 },
};

export function providerModelId(modelSlug: ModelSlug): string {
  const providerId = PROVIDER_MODEL_IDS[modelSlug];
  if (providerId === undefined) {
    throw new Error(`No Command Code provider ID for model: ${modelSlug}`);
  }
  return providerId;
}

export type CapabilityScores = Readonly<{
  reasoning: number;
  coding: number;
  tool_use: number;
  document_qa: number;
  structured_output: number;
  instruction_following: number;
  long_context: number;
}>;

export type ModelProfile = Readonly<{
  model_slug: ModelSlug;
  capabilities: CapabilityScores;
  runtime: Readonly<{
    tokens_per_second: number;
    peak_vram_gb: number;
    usable_context: number;
  }>;
  features: Readonly<{
    tool_calling: boolean;
    multimodal: boolean;
  }>;
  target_deployment?: Readonly<{
    total_vram_gb: number;
    hardware: string;
    precision: string;
  }>;
}>;

/**
 * Candidates of the outcome-trained Modal router (`training/modal_outcome_app.py`).
 * The service holds their measured profiles itself; clients send only the task.
 * The service sends a task to the preference's easy model when its easy-task
 * score reaches the returned threshold, and to `fallback` otherwise.
 */
export const OUTCOME_ROUTER = {
  router: "outcome-router-4m-v1",
  fallback: MODEL_SLUGS.deepSeekFlash,
} as const;

export const OUTCOME_CANDIDATES: readonly ModelSlug[] = [
  MODEL_SLUGS.deepSeekFlash,
  MODEL_SLUGS.glmFlash,
  MODEL_SLUGS.mimoFlash,
  MODEL_SLUGS.nemotronSuperVl,
];

export const PROFILE_VERSION = "benchmark-v1-20260919T110437Z-272c";

export const MVP_MODEL_PROFILES = [
  {
    model_slug: MODEL_SLUGS.qwenGeneral,
    capabilities: {
      reasoning: 0.91,
      coding: 0.88,
      tool_use: 0.94,
      document_qa: 0.93,
      structured_output: 0.94,
      instruction_following: 0.94,
      long_context: 0.96,
    },
    runtime: { tokens_per_second: 18, peak_vram_gb: 54, usable_context: 262_144 },
    features: { tool_calling: true, multimodal: true },
  },
  {
    model_slug: MODEL_SLUGS.qwenCoder,
    capabilities: {
      reasoning: 0.82,
      coding: 0.97,
      tool_use: 0.87,
      document_qa: 0.68,
      structured_output: 0.88,
      instruction_following: 0.85,
      long_context: 0.86,
    },
    runtime: { tokens_per_second: 36, peak_vram_gb: 28, usable_context: 131_072 },
    features: { tool_calling: true, multimodal: false },
  },
  {
    model_slug: MODEL_SLUGS.deepSeekReasoning,
    capabilities: {
      reasoning: 0.97,
      coding: 0.86,
      tool_use: 0.62,
      document_qa: 0.7,
      structured_output: 0.78,
      instruction_following: 0.79,
      long_context: 0.82,
    },
    runtime: { tokens_per_second: 28, peak_vram_gb: 28, usable_context: 65_536 },
    features: { tool_calling: false, multimodal: false },
  },
  {
    model_slug: MODEL_SLUGS.mistralGeneral,
    capabilities: {
      reasoning: 0.86,
      coding: 0.83,
      tool_use: 0.87,
      document_qa: 0.89,
      structured_output: 0.88,
      instruction_following: 0.88,
      long_context: 0.88,
    },
    runtime: { tokens_per_second: 34, peak_vram_gb: 48, usable_context: 131_072 },
    features: { tool_calling: true, multimodal: true },
  },
  {
    model_slug: MODEL_SLUGS.gemmaDocument,
    capabilities: {
      reasoning: 0.85,
      coding: 0.78,
      tool_use: 0.65,
      document_qa: 0.94,
      structured_output: 0.83,
      instruction_following: 0.86,
      long_context: 0.89,
    },
    runtime: { tokens_per_second: 22, peak_vram_gb: 52, usable_context: 131_072 },
    features: { tool_calling: false, multimodal: true },
  },
  {
    model_slug: MODEL_SLUGS.glmFlash,
    capabilities: {
      reasoning: 0.8,
      coding: 1,
      tool_use: 1,
      document_qa: 1,
      structured_output: 1,
      instruction_following: 0.8,
      long_context: 1,
    },
    runtime: { tokens_per_second: 6.72, peak_vram_gb: 160, usable_context: 202_752 },
    features: { tool_calling: true, multimodal: false },
    target_deployment: {
      total_vram_gb: 160,
      hardware: "2 x NVIDIA H100 80 GB",
      precision: "FP8",
    },
  },
  {
    model_slug: MODEL_SLUGS.deepSeekFlash,
    capabilities: {
      reasoning: 0.6,
      coding: 0.6,
      tool_use: 1,
      document_qa: 0.2,
      structured_output: 1,
      instruction_following: 0.8,
      long_context: 0.8,
    },
    runtime: { tokens_per_second: 35.74, peak_vram_gb: 640, usable_context: 163_840 },
    features: { tool_calling: true, multimodal: false },
    target_deployment: {
      total_vram_gb: 640,
      hardware: "8 x NVIDIA H100 80 GB",
      precision: "FP8",
    },
  },
] as const satisfies readonly ModelProfile[];

export const DEFAULT_MODEL_CANDIDATES: readonly ModelSlug[] = MVP_MODEL_PROFILES.map(
  (profile) => profile.model_slug,
);

export function isModelSlug(value: string): value is ModelSlug {
  return MVP_MODEL_PROFILES.some((profile) => profile.model_slug === value);
}

export function getModelProfile(modelSlug: ModelSlug): ModelProfile {
  const profile = MVP_MODEL_PROFILES.find((candidate) => candidate.model_slug === modelSlug);
  if (profile === undefined) {
    throw new Error(`Missing profile for model: ${modelSlug}`);
  }
  return profile;
}
