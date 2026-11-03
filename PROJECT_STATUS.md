# EDI project status

## Current contents

- `runtime.ts` contains the learned-router client, schema validation, hard tool and context filters, deterministic fallback, load probing, and session locking.
- `router.ts` exposes random, round-robin, static-rule, heuristic, learned, and oracle strategies through one result contract.
- `profiles.ts` and `training-profiles.json` contain benchmark version `benchmark-v1-20260919T110437Z-272c` for `glm-5.3-flash` and `deepseek-v4.1-flash`, served through Command Code.
- `training/` contains family-isolated data generation, Qwen3-0.6B LoRA training, inference, serving, evaluation, tests, and the Colab notebook.
- `evaluation/` contains the 70-item workload, offline cache importer, reports, tests, and frozen artifact manifest.
- `demo/` contains the no-cost saved playback and review instructions.
- `training/modal_app.py` deploys the fine-tuned Qwen3-0.6B LoRA router on a protected Modal T4 endpoint. `bun run demo:cli` sends pasted tasks to it.

## Deliberately excluded

- The end-sem heterogeneous-agent system and any web UI. They consume this package but are not needed to develop or evaluate the router.
- Monorepo configuration, root lockfile, unrelated packages, and deployment settings.
- Trained checkpoints, generated datasets, virtual environments, and local demo output. The scripts reproduce these or install a separately transferred artifact.

## Evidence and limits

- The saved benchmark has 35 tasks per model across seven categories. It ran against OpenCode Zen; profiles need re-measuring against Command Code before the next benchmark or evaluation run.
- The refined router recorded 82.875% validation policy agreement. This is not downstream success.
- The offline comparison reuses 70 model outcomes. It reports five strategies without spending new credits.
- The learned router is deployed from the pinned base revision plus the trained adapter. The full learned downstream comparison remains pending.
- The held-out test has not run.
- A person still needs to record the fallback video.

The mid-sem deliverable routes between two models. Do not describe it as the end-sem heterogeneous-agent router.
