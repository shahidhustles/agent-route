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

After deploying `training/modal_app.py`, `bun run demo:interactive` starts the browser chat at `http://localhost:3000`. Each prompt goes to the fine-tuned Qwen router first. The selected model and confidence appear before the answer streams. The original terminal flow remains available through `bun run demo:cli`.

## Code artifact agent

`/agent` hosts the single-purpose code artifact agent. Each prompt goes to the Modal router, and the selected model streams Python through Command Code into a browser editor. Run executes the snippet with Pyodide without leaving the page.

It needs the Modal router variables plus `CMD_API_KEY` in `.env.modal`:

```sh
CMD_API_KEY=your-key
bun run demo:interactive
```

Open `http://localhost:3000/agent`, submit a prompt, and the routing chip resolves into a model and confidence before code streams. Versions stay in the tab; nothing is persisted.

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

## Current evidence

The refined checkpoint reached 82.875% policy agreement on the validation split. The frozen downstream comparison reuses 70 saved model outcomes and makes no paid calls. Random, round-robin, static-rule, heuristic, and oracle results are available. The learned downstream comparison and held-out test remain pending because the repository does not contain a complete merged checkpoint.

The 82.875% figure measures agreement with the deterministic profile policy, not downstream task success. Read [evaluation.md](evaluation.md) before using it in a review.

## Dataset scope

The generator uses 120 independently written task families across 12 domain-neutral categories. Families stay within one split. The held-out split remains sealed.
