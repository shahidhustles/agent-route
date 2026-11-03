export const PREFERENCES = ["cheap", "balanced", "fast", "accurate"] as const;
export type Preference = (typeof PREFERENCES)[number];

export const AGENTS = [
  "code",
  "spreadsheet",
  "data-analysis",
  "docx",
  "slides",
  "diagram",
  "map",
  "scene-3d",
] as const;
export type Agent = (typeof AGENTS)[number];

export const AGENT_LABEL: Record<Agent, string> = {
  code: "Code",
  spreadsheet: "Spreadsheet",
  "data-analysis": "Data analysis",
  docx: "Document",
  slides: "Slides",
  diagram: "Diagram",
  map: "Map",
  "scene-3d": "3D scene",
};

export const MODEL_NAME: Record<string, string> = {
  "deepseek/deepseek-v4.1-flash": "DeepSeek",
  "z-ai/glm-5.3-flash": "GLM",
  "xiaomi/mimo-v2.6-flash": "MiMo",
  "nvidia/nemotron-3.5-super-vl": "Nemotron",
};
export const DEEPSEEK = "deepseek/deepseek-v4.1-flash";

export type Estimate = {
  model: string;
  p_pass: number;
  wall_s: number;
  cost_usd: number;
  runs_seen: number;
  eligible: boolean;
  chosen: boolean;
};

export type Decision = {
  preference: Preference;
  agent: Agent;
  model: string;
  confidence: { agent: number; model: number };
  runner_up: {
    agent: { agent: Agent; share: number } | null;
    model: { model: string; p_pass: number; wall_s: number; cost_usd: number } | null;
  };
  tolerance: number;
  /** Set when the user picked the agent, so the agent confidence is a vote share the router did not act on. */
  manual_agent?: boolean;
  estimates: Estimate[];
  reasoning: string;
};

export type RouteResponse = {
  task: { id: string | null; text: string };
  agents: { agent: Agent; share: number }[];
  low_vote: boolean;
  agent_override?: boolean;
  /** Set when the task was longer than the router reads: the router saw the start and the end. */
  truncated?: { chars: number; read_head: number; read_tail: number } | null;
  decisions: Record<Preference, Decision>;
};

export type Artifact = {
  agent: Agent;
  files: Record<string, string>;
  binary: Record<string, number>;
  /** `files`: a run made under the real-file contract (.pptx, .docx, .xlsx, .html). Absent for recorded JSON runs. */
  contract?: "files";
};

export type RunResult = {
  status: "passed" | "failed" | "stopped" | "error";
  detail: string;
  wall_s: number;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  tool_calls?: number;
  final_text?: string;
  appended?: boolean;
  record_passed?: boolean | null;
  contract: { passed: boolean; detail: string } | null;
};

export type Run = {
  id: string;
  text: string;
  agent: Agent;
  model: string;
  preference: Preference | null;
  rerun_of: string | null;
  csv_name?: string | null;
  status: "running" | "passed" | "failed" | "stopped" | "error";
  result: RunResult | null;
  artifact: Artifact | null;
  route: Decision | null;
  marked: boolean | null;
  mark_effect: {
    before: { p_pass: number; runs_seen: number };
    after: { p_pass: number; runs_seen: number };
  } | null;
  before: { p_pass: number; runs_seen: number };
};

export type RunEvent =
  | { kind: "start"; agent: string; model: string; i: number }
  | { kind: "thinking"; text: string; t: number; i: number }
  | { kind: "tool"; tool: string; text: string; t: number; i: number }
  | { kind: "text"; text: string; t: number; i: number }
  | { kind: "tokens"; input: number; output: number; t: number; i: number }
  | { kind: "error"; text: string; t: number; i: number }
  | { kind: "done"; status: string; i: number };

export type Status = {
  spent_usd: number;
  cap_usd: number;
  stopped: string | null;
  session_usd: number;
  records: number;
  ui_records: number;
};

export type Recorded = {
  task_id: string;
  agent: Agent;
  model: string;
  passed: boolean | null;
  wall_s: number;
  cost_usd: number;
};

export type Answer = {
  text: string;
  model: string;
  wall_s: number;
  cost_usd: number;
  router: {
    model_slug: string;
    confidence: number;
    probabilities: Record<string, number>;
    threshold: number;
    easy_score?: number;
    routing_ms: number;
  } | null;
  router_error?: string;
};

/** The backend did not answer at all (process down, port closed, or the dev proxy gave up). */
export class BackendDownError extends Error {
  constructor() {
    super("The router backend is not answering.");
  }
}

/** A failed request. `detail` is the backend's own message when it sent one. */
async function failure(response: Response): Promise<Error> {
  const data = (await response.json().catch(() => null)) as { error?: string } | null;
  if (data?.error) return new Error(data.error);
  if (response.status === 413) return new Error("The upload is too large. Attach a smaller CSV.");
  return response.status >= 500 ? new BackendDownError() : new Error(`HTTP ${response.status}`);
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/py/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new BackendDownError();
  }
  if (!response.ok) throw await failure(response);
  return (await response.json()) as T;
}

export const money = (usd: number) =>
  usd > 0 && usd < 0.0001 ? "<$0.0001" : usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(3)}`;
export const pct = (x: number) => `${Math.round(x * 100)}%`;
