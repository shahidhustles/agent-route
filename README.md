# EDI Model Router

This repository contains the EDI model router, its training and evaluation pipeline, profile and registry contracts, and tests.

The current learned router fine-tunes Qwen3-0.6B to choose one candidate model from a task and a set of model profiles. The runtime enforces tool-use and context-window constraints before inference, validates the returned slug, falls back deterministically when the local router is unavailable, and keeps the selected model fixed for a session.

Start with [PROJECT_STATUS.md](PROJECT_STATUS.md) for the project scope and [MID_SEM_CHECKLIST.md](MID_SEM_CHECKLIST.md) for the ordered implementation plan. The missing primary-model benchmark is specified in [benchmarking/README.md](benchmarking/README.md).

## Project map

```text
edi-model-router/
  runtime.ts                 learned-router client and session selection
  router.ts                  heuristic baseline
  profiles.ts                provisional built-in profiles
  registry.ts                endpoint and profile registry schema
  registry.example.json      sample candidate registry
  training-profiles.json     training-time profile snapshot
  training/                  data, LoRA training, serving, and evaluation
  benchmarking/              contract for the missing benchmark engine
  evaluation.md              accepted checkpoint results and limits
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

`registry.example.json` shows how to associate profiles with OpenAI-compatible endpoints. Its ports, served-model IDs, capability scores, and hardware values are samples, not measurements.

## Current evidence

The accepted checkpoint reached 82.875% exact route accuracy on the synthetic validation split. It produced valid JSON for every validation case, but the original wrapper rejected six hard-constraint violations. The held-out test split remains untouched.

That result measures agreement with the synthetic teacher. It does not measure downstream task success or prove that the placeholder model profiles are accurate. Read [evaluation.md](evaluation.md) before using the number in a review.

## Dataset warning

The generator creates 8,000 examples from 42 templates. Most prompts vary industrial equipment names, so the data is heavily shaped by MRPL-style workflows. Keep those prompts as one domain, but add independently written, domain-neutral examples before retraining or making general routing claims.
