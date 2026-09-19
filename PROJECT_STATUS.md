# EDI project status

## Current contents

- `runtime.ts` contains the learned-router client, schema validation, hard tool and context filters, deterministic fallback, load probing, and session locking.
- `router.ts` contains the earlier heuristic router. Keep it as a baseline for comparison, not as the final learned method.
- `profiles.ts`, `training-profiles.json`, `registry.ts`, and `registry.example.json` define the current model profile and endpoint contracts. Their capability and hardware values are placeholders.
- `training/` contains synthetic data generation, Qwen3-0.6B LoRA training, inference, serving, evaluation, tests, and the Colab notebook.
- `evaluation.md` and `evaluation-summary.json` preserve the accepted 82.875% validation result and its limitations.

## Deliberately excluded

- The main agent implementation and model-picker UI. They consume this package but are not needed to develop or evaluate the router.
- Monorepo configuration, root lockfile, unrelated packages, and deployment settings.
- Trained checkpoints, generated datasets, virtual environments, and local demo output. The scripts reproduce these or install a separately transferred artifact.

## Mid-sem work still required

1. Build the benchmarking engine described in `benchmarking/README.md`.
2. Replace the placeholder values in `training-profiles.json` and the runtime registry with measured profile values.
3. Generalize the task corpus. Keep MRPL workflows as one domain, then add independently written coding, document, reasoning, tool-use, long-context, spreadsheet, and simple tasks from neutral domains.
4. Regenerate the splits and retrain. Keep template variants or source groups isolated by split to prevent leakage.
5. Evaluate the learned router against random, round-robin, static-rule, heuristic, and oracle policies using the same tasks and candidate set.
6. Report routing agreement, downstream task success, cost, latency, throughput, VRAM, invalid outputs, and hard-constraint violations separately.

Do not present the current capability scores as benchmark results. The existing 82.875% figure measures agreement with a synthetic teacher on the validation split, not whether the selected primary model completes real tasks successfully.
