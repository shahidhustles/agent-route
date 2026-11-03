# EDI Model Router

This repository contains the mid-sem model router, its Command Code benchmark, Qwen3-0.6B training pipeline, routing-strategy comparison, and offline review demo.

The measured candidates are `glm-5.3-flash` and `deepseek-v4.1-flash`, served through Command Code. The runtime filters tool, context, and VRAM constraints before selection. The mid-sem work routes between models. Heterogeneous agent routing remains end-sem work.

Start with [PROJECT_STATUS.md](PROJECT_STATUS.md) for the honest completion state. The review flow is in [demo/README.md](demo/README.md).

## Project map

```text
edi-model-router/
  runtime.ts                 learned-router client and session selection
  router.ts                  heuristic baseline
  profiles.ts                measured Command Code profiles
  registry.ts                endpoint and profile registry schema
  registry.example.json      sample candidate registry
  training-profiles.json     training-time profile snapshot
  training/                  data, LoRA training, serving, and evaluation
  benchmarking/              versioned Command Code benchmark and saved evidence
  evaluation/                frozen workload, policies, cache, and reports
  demo/                      saved review playback and instructions
  evaluation.md              current and prior evaluation limits
```

## Install and verify

Install Bun dependencies from this directory:

```sh
bun install
bun run test
bun run typecheck
bun run lint
```

Run the Python contract tests without installing the GPU training stack:

```sh
python -m unittest discover -s training -p 'test_*.py'
```

See [training/README.md](training/README.md) for environment setup, dataset generation, LoRA training, evaluation, and local serving.

## Review demo

The default demo is offline and cannot spend Command Code credits:

```sh
bun run demo
```

It presents both measured profiles, two opposite model selections, saved model responses and execution metrics, and the offline strategy comparison. See [demo/README.md](demo/README.md) for the prepared cases and Colab command.

After deploying `training/modal_outcome_app.py`, `bun run demo:cli` sends pasted tasks to the outcome-trained Qwen router, which picks DeepSeek V4.1 Flash or Nemotron 3.5 Super VL and returns both probabilities.

## Router service

After installing the Python dependencies and obtaining a merged checkpoint:

```sh
.venv/bin/python training/serve.py --model artifacts/qwen3-router/merged
```

On Windows, use `.venv/Scripts/python.exe`. The service binds to `127.0.0.1:8787` and exposes `POST /route` plus `GET /health`.

```ts
import { createLocalRouter } from "edi-model-router";
import { MVP_MODEL_PROFILES } from "./profiles";

const route = createLocalRouter();
const result = await route({
  user_task: "Create and verify a Word approval note",
  candidate_models: MVP_MODEL_PROFILES.map((profile) => profile.model_slug),
  profiles: [...MVP_MODEL_PROFILES],
  requires_tools: true,
  input_tokens: 8000,
});
```

`registry.example.json` shows how to associate profiles with OpenAI-compatible endpoints. Its local ports and served-model IDs are examples.

## Web app

One screen: type a task, see which agent and model the router chose and why, watch the agent run in its Docker sandbox, and read the output in the block that fits it (code, spreadsheet, data analysis, document, slides, diagram, map, 3D scene). Design tokens are in `docs/specs/ui-design.md`.

Two processes, both bound to localhost. Run each in its own terminal from the repo root.

```bash
# 1. Backend: router, outcome memory, agent runs, spend cap (loads the embedding model, about 10 s)
.venv/bin/python routing/server.py --port 8765 --max-usd 0.25

# 2. Web app on http://127.0.0.1:3001 (reads the Modal router settings from .env.modal)
bun install
bun run web
```

Needs Docker with the `agent-route-opencode` image (`agents/sandbox/build.sh`) and `CMD_API_KEY` in `.env.modal`. The key stays in the backend process and the host proxy; the browser and the containers never see it.

- **Run an agent.** The agent router picks the agent and model from past outcomes. Pick a preference (cheap by default), press the run button. Below a 50% vote share the app shows the top two agents and waits for your pick.
- **Just answer.** The Modal model router picks the model, then one Command Code call answers.
- **Result.** Agent, model, confidence, runner-up, cost, wall time, and whether the output passed its contract. A failed contract shows the error and the raw files, with a one-click rerun on DeepSeek.
- **Memory.** A finished run is appended to `data/memory/online.jsonl` with no verdict. Press Good or Bad and the next route counts it.
- **Recorded examples.** The second tab opens finished runs from `agents-cc-20261031` in each block, with no model call.
- **Spend cap.** The backend keeps its own ledger (`benchmarking/results/agents-ui-ledger.jsonl`). Click the cap in the top right to change it. A `weekly usage limit` reply stops live calls; routing and recorded examples keep working.
- **From curl.** `POST /api/py/route`, `POST /api/py/runs`, then `GET /api/py/runs/<id>/events` for the progress stream. The endpoints are listed in the `routing/server.py` docstring.

Generated output is untrusted. Markdown renders without raw HTML, Mermaid runs at `securityLevel: "strict"`, scenes are declarative json-render specs, and code is shown, never run.

## Current evidence

The refined checkpoint reached 82.875% policy agreement on the validation split. The frozen downstream comparison reuses 70 saved model outcomes and makes no paid calls. Random, round-robin, static-rule, heuristic, and oracle results are available. The learned downstream comparison and held-out test remain pending because the repository does not contain a complete merged checkpoint.

The 82.875% figure measures agreement with the deterministic profile policy, not downstream task success. Read [evaluation.md](evaluation.md) before using it in a review.

## Dataset scope

The generator uses 120 independently written task families across 12 domain-neutral categories. Families stay within one split. The held-out split remains sealed.
