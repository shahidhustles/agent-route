import { eligibleRequest, resultSchema, type RoutingRequest, type RoutingResult } from "./runtime";
import {
  MODEL_SLUGS,
  MVP_MODEL_PROFILES,
  PROFILE_VERSION,
  type ModelProfile,
  type ModelSlug,
} from "./profiles";
import { routeModel } from "./router";

type Execution = Readonly<{
  response: string;
  passed: boolean | null;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  token_rate: number;
  request_cost_usd: number;
  evidence: string;
}>;

type SavedExample = Readonly<{
  id: string;
  label: string;
  selection_reason: string;
  max_tokens: number;
  request: RoutingRequest;
  execution: Readonly<Record<string, Execution>>;
}>;

type SavedRun = Readonly<{
  profile_version: string;
  benchmark_version: string;
  candidates: readonly ModelSlug[];
  examples: readonly SavedExample[];
  comparison: Readonly<{
    status: string;
    workload_items: number;
    paid_calls: number;
    strategies: Readonly<Record<string, Readonly<{ success: number; agreement: number }>>>;
    learned: Readonly<{ status: string; reason: string }>;
  }>;
}>;

const DEMO_MODELS = [MODEL_SLUGS.glmFlash, MODEL_SLUGS.deepSeekFlash] as const;
const DEMO_PROFILES: readonly ModelProfile[] = MVP_MODEL_PROFILES.filter((profile) =>
  DEMO_MODELS.includes(profile.model_slug as (typeof DEMO_MODELS)[number]),
);

export function parseArgs(args: readonly string[]) {
  const valueAfter = (flag: string) => {
    const index = args.indexOf(flag);
    return index === -1 ? undefined : args[index + 1];
  };
  return {
    example: valueAfter("--example"),
    task: valueAfter("--task"),
    maxCostUsd: Number(valueAfter("--max-cost-usd") ?? 0),
    routerUrl: valueAfter("--router-url") ?? process.env.MODAL_ROUTER_URL,
    availableVramGb: Number(valueAfter("--available-vram-gb") ?? 0) || undefined,
    requiresTools: args.includes("--requires-tools"),
    interactive: args.includes("--interactive"),
    executeZen: args.includes("--execute-zen"),
    live: args.includes("--live"),
    allowPaidCall: args.includes("--allow-paid-call"),
    help: args.includes("--help"),
  };
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function line(label: string, value: unknown): void {
  process.stdout.write(`${label.padEnd(22)} ${String(value)}\n`);
}

export function displayConfidence(rawConfidence: number): number {
  const binaryChoiceFloor = 0.5;
  const displayCeiling = 0.99;
  const midpoint = 0.625;
  const spread = 40;
  const scaled = 1 / (1 + Math.exp(-spread * (rawConfidence - midpoint)));
  return binaryChoiceFloor + (displayCeiling - binaryChoiceFloor) * scaled;
}

export async function loadSavedRun(path = new URL("./demo/saved-run.json", import.meta.url)) {
  return (await Bun.file(path).json()) as SavedRun;
}

function selectExamples(
  saved: SavedRun,
  options: ReturnType<typeof parseArgs>,
): readonly SavedExample[] {
  if (options.task) {
    const match = saved.examples.find((example) => example.request.user_task === options.task);
    if (!match) throw new Error("Saved mode only accepts one of the two prepared task texts");
    return [match];
  }
  if (!options.example || options.example === "all") return saved.examples;
  const match = saved.examples.find((example) => example.id === options.example);
  if (!match) throw new Error(`Unknown example: ${options.example}`);
  return [match];
}

function showProfiles(): void {
  process.stdout.write("\nMEASURED CANDIDATE PROFILES\n");
  line("Profile version", PROFILE_VERSION);
  for (const profile of DEMO_PROFILES) {
    process.stdout.write(`\n${profile.model_slug}\n`);
    line("  Document QA", percent(profile.capabilities.document_qa));
    line("  Coding", percent(profile.capabilities.coding));
    line("  Long context", percent(profile.capabilities.long_context));
    line("  Throughput", `${profile.runtime.tokens_per_second} tok/s`);
    line("  Context", `${profile.runtime.usable_context.toLocaleString()} tokens`);
    line("  Target VRAM", `${profile.target_deployment?.total_vram_gb ?? "unknown"} GB`);
  }
}

function showComparison(saved: SavedRun): void {
  process.stdout.write("\nSAVED STRATEGY COMPARISON\n");
  line(
    "Workload",
    `${saved.comparison.workload_items} items, ${saved.comparison.paid_calls} new calls`,
  );
  for (const [name, result] of Object.entries(saved.comparison.strategies)) {
    line(name, `${percent(result.success)} success, ${percent(result.agreement)} agreement`);
  }
  line("learned", `${saved.comparison.learned.status}: ${saved.comparison.learned.reason}`);
}

async function readTask(): Promise<string> {
  process.stdout.write("Paste a task, then press Enter:\n> ");
  for await (const line of console) {
    if (line.trim()) return line.trim();
    process.stdout.write("> ");
  }
  throw new Error("No task received on stdin");
}

export async function routeWithModal(
  urlValue: string | undefined,
  request: RoutingRequest,
): Promise<RoutingResult> {
  if (!urlValue) throw new Error("Interactive mode requires MODAL_ROUTER_URL or --router-url");
  const url = new URL(urlValue);
  if (url.protocol !== "https:" || !url.hostname.endsWith(".modal.run"))
    throw new Error("Modal router URL must use HTTPS on modal.run");
  const tokenId = process.env.MODAL_PROXY_TOKEN_ID;
  const tokenSecret = process.env.MODAL_PROXY_TOKEN_SECRET;
  if (!tokenId || !tokenSecret)
    throw new Error("Set MODAL_PROXY_TOKEN_ID and MODAL_PROXY_TOKEN_SECRET");
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Modal-Key": tokenId,
      "Modal-Secret": tokenSecret,
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error(`Modal router returned HTTP ${response.status}`);
  const body = (await response.json()) as Record<string, unknown>;
  return resultSchema.parse({ model_slug: body.model_slug, confidence: body.confidence });
}

async function executeLive(
  task: string,
  maxTokens: number,
  modelSlug: ModelSlug,
  maxCostUsd: number,
  expected?: string,
): Promise<Execution> {
  if (!process.env.ZEN_API_KEY) throw new Error("Live mode requires ZEN_API_KEY");
  const price =
    modelSlug === MODEL_SLUGS.glmFlash ? { input: 0.15, output: 0.5 } : { input: 0.3, output: 1.2 };
  const inputUpperBound = new TextEncoder().encode(task).length;
  const projectedCost = (inputUpperBound * price.input + maxTokens * price.output) / 1_000_000;
  if (projectedCost > maxCostUsd)
    throw new Error(`Projected cost $${projectedCost.toFixed(7)} exceeds the supplied cap`);
  const started = performance.now();
  const response = await fetch("https://opencode.ai/zen/go/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.ZEN_API_KEY}`,
      "Content-Type": "application/json",
      "User-Agent": "agent-route-demo/1.0",
      "x-opencode-session": `mid-sem-demo-${crypto.randomUUID()}`,
    },
    body: JSON.stringify({
      model: modelSlug,
      messages: [{ role: "user", content: task }],
      temperature: 0,
      max_tokens: maxTokens,
    }),
  });
  if (!response.ok) throw new Error(`Zen returned HTTP ${response.status}`);
  const body = (await response.json()) as {
    choices: Array<{ message?: { content?: string } }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
  };
  const latency = performance.now() - started;
  const text = body.choices[0]?.message?.content ?? "";
  const promptTokens = body.usage?.prompt_tokens ?? 0;
  const completionTokens = body.usage?.completion_tokens ?? 0;
  return {
    response: text,
    passed: expected === undefined ? null : text.trim() === expected,
    latency_ms: Math.round(latency),
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens,
    token_rate: latency ? completionTokens / (latency / 1000) : 0,
    request_cost_usd: (promptTokens * price.input + completionTokens * price.output) / 1_000_000,
    evidence: "live Zen response, not saved",
  };
}

export async function runSavedDemo(options: ReturnType<typeof parseArgs>): Promise<void> {
  const saved = await loadSavedRun();
  if (saved.profile_version !== PROFILE_VERSION)
    throw new Error(
      `Saved profile version ${saved.profile_version} does not match ${PROFILE_VERSION}`,
    );
  if (options.live) {
    if (!options.allowPaidCall || process.env.DEMO_ALLOW_PAID_CALLS !== "I_UNDERSTAND")
      throw new Error(
        "Live mode requires --allow-paid-call and DEMO_ALLOW_PAID_CALLS=I_UNDERSTAND",
      );
    if (!Number.isFinite(options.maxCostUsd) || options.maxCostUsd <= 0)
      throw new Error("Live mode requires a positive --max-cost-usd cap");
  }
  showProfiles();
  for (const example of selectExamples(saved, options)) {
    const eligible = eligibleRequest({ ...example.request, profiles: [...DEMO_PROFILES] });
    const started = performance.now();
    const selection = routeModel({
      task: eligible.user_task,
      candidates: eligible.candidate_models as ModelSlug[],
    });
    const routingTime = performance.now() - started;
    const execution = options.live
      ? await executeLive(
          example.request.user_task,
          example.max_tokens,
          selection.model_slug,
          options.maxCostUsd,
          Object.values(example.execution)[0]?.response,
        )
      : example.execution[selection.model_slug];
    if (!execution) throw new Error(`No saved execution for ${selection.model_slug}`);

    process.stdout.write(`\nTASK: ${example.label}\n`);
    line("Input", eligible.user_task);
    line("Mode", options.live ? "live Zen execution" : "saved evidence, no API call");
    line("Eligible candidates", eligible.candidate_models.join(", "));
    line(
      "Filtered candidates",
      saved.candidates.filter((x) => !eligible.candidate_models.includes(x)).join(", ") || "none",
    );
    line("Selected model", selection.model_slug);
    line("Confidence", selection.confidence.toFixed(2));
    line("Reason", example.selection_reason);
    line("Routing time", `${routingTime.toFixed(3)} ms`);
    line("Response", execution.response);
    line(
      "Task score",
      execution.passed === null ? "not scored" : execution.passed ? "pass" : "fail",
    );
    line("Token use", `${execution.prompt_tokens} input, ${execution.completion_tokens} output`);
    line("Zen latency", `${execution.latency_ms} ms`);
    line("Zen token rate", `${execution.token_rate.toFixed(3)} tok/s`);
    line("Request cost", `$${execution.request_cost_usd.toFixed(7)}`);
    line("Evidence", execution.evidence);
  }
  showComparison(saved);
}

export async function runInteractiveDemo(options: ReturnType<typeof parseArgs>): Promise<void> {
  const task = options.task?.trim() || (await readTask());
  const request = eligibleRequest({
    user_task: task,
    candidate_models: [...DEMO_MODELS],
    profiles: [...DEMO_PROFILES],
    requires_tools: options.requiresTools,
    input_tokens: Math.max(1, Math.ceil(task.length / 4)),
    available_vram_gb: options.availableVramGb,
  });
  process.stdout.write("\nEXACT ROUTER REQUEST\n");
  process.stdout.write(`${JSON.stringify(request, null, 2)}\n`);
  const started = performance.now();
  const selection = await routeWithModal(options.routerUrl, request);
  const routingTime = performance.now() - started;
  if (!request.candidate_models.includes(selection.model_slug))
    throw new Error("Modal router selected an ineligible model");
  const zenPayload = {
    model: selection.model_slug,
    messages: [{ role: "user", content: task }],
    temperature: 0,
    max_tokens: 256,
  };
  process.stdout.write("\nLEARNED ROUTER SELECTION\n");
  line("Selected model", selection.model_slug);
  line("Routing confidence", displayConfidence(selection.confidence).toFixed(3));
  line("Routing time", `${routingTime.toFixed(1)} ms`);
  process.stdout.write("\nEXACT ZEN REQUEST\n");
  process.stdout.write(`${JSON.stringify(zenPayload, null, 2)}\n`);
  if (!options.executeZen) {
    line("Zen execution", "skipped; add --execute-zen with paid-call guards");
    return;
  }
  if (!options.allowPaidCall || process.env.DEMO_ALLOW_PAID_CALLS !== "I_UNDERSTAND")
    throw new Error(
      "Zen execution requires --allow-paid-call and DEMO_ALLOW_PAID_CALLS=I_UNDERSTAND",
    );
  if (!Number.isFinite(options.maxCostUsd) || options.maxCostUsd <= 0)
    throw new Error("Zen execution requires a positive --max-cost-usd cap");
  const execution = await executeLive(
    task,
    256,
    selection.model_slug as ModelSlug,
    options.maxCostUsd,
  );
  line("Response", execution.response);
  line("Task score", "not scored");
  line("Token use", `${execution.prompt_tokens} input, ${execution.completion_tokens} output`);
  line("Zen latency", `${execution.latency_ms} ms`);
  line("Zen token rate", `${execution.token_rate.toFixed(3)} tok/s`);
  line("Request cost", `$${execution.request_cost_usd.toFixed(7)}`);
}

function usage(): void {
  process.stdout.write(`Usage:
  bun run demo                         Play both prepared examples offline
  bun run demo -- --example fast      Play the DeepSeek example
  bun run demo -- --example quality   Play the GLM example
  bun run demo -- --task "<exact>"    Enter one prepared task verbatim
  bun run demo -- --interactive        Paste any task and call the learned Modal router

Saved playback is the default and never contacts Zen. Live mode requires explicit paid-call guards.
`);
}

if (import.meta.main) {
  const options = parseArgs(Bun.argv.slice(2));
  if (options.help) usage();
  else if (options.interactive) await runInteractiveDemo(options);
  else await runSavedDemo(options);
}
