# Mid-sem model router

## Goal

Build a review-ready model routing system in two days. It benchmarks two free OpenCode Zen models, turns the results into model profiles, trains the existing Qwen3-0.6B router, and compares learned routing with fixed baselines.

The review must prove a narrow claim: measured capability profiles can help a learned router choose between a faster model and a stronger model for a given task. The end-sem project will replace Zen execution with self-hosted models and extend model selection into heterogeneous agent routing.

## User flow

1. The reviewer starts the benchmark or opens a saved benchmark run.
2. The system shows profiles for `nemotron-3-ultra-free` and `nemotron-3.5-lightning-free`.
3. The reviewer enters a task and optional tool, context, and VRAM requirements.
4. Hard constraints remove incompatible candidates.
5. The learned router selects a model and reports its confidence, short reason, and routing time.
6. The selected Zen model executes the task.
7. The terminal shows the response, task score, latency, token rate, and selected profile.
8. A saved report compares the learned router with the baseline strategies on the frozen evaluation workload.

## Requirements

- Use only the free Zen candidates `nemotron-3-ultra-free` and `nemotron-3.5-lightning-free`.
- Run benchmark, training, evaluation, and demo commands from Google Colab.
- Read the Zen API key from a Colab secret or environment variable. Never write it to a notebook output, result file, or repository file.
- Send a stable `x-opencode-session` value for each benchmark conversation. Retries of one case reuse its session value. Separate cases use separate values.
- Save raw requests, responses, scores, timings, token counts, errors, model IDs, benchmark version, and run timestamp. Redact authentication headers.
- Benchmark both models with the same prompts and scorers.
- Cover reasoning, coding, tool use, document QA, structured output, instruction following, long context, and simple requests.
- Use deterministic scoring where possible. Capability scores equal the pass rate for each category and remain within `0..1`.
- Use domain-neutral tasks. Do not include MRPL prompts or confidential material.
- Give every source task a family ID. Keep one family in only one of training, validation, or held-out test.
- Generate router labels with the existing deterministic policy after replacing placeholder capabilities with benchmark results.
- Keep the held-out test sealed until profiles, data, router checkpoint, baselines, and scoring rules are frozen.
- Compare random, round-robin, static-rule, existing heuristic, learned, and oracle strategies on the same 50 to 100 task workload.
- Cache execution by benchmark version, task ID, model ID, and decoding settings so repeated strategy selections do not repeat the same model call.
- Report routing agreement separately from downstream task success. Report routing time separately from Zen execution time.
- The target thresholds are at least 80% validation policy agreement, less than 1% invalid router output, and zero tool, context, or VRAM constraint violations.
- The learned router must match or beat the best non-oracle baseline on downstream success, or preserve success while improving latency.
- Preserve the existing 82.875% result as prior evidence only. Do not mix it with the new experiment.

## Implementation decisions

### Benchmark engine

Add the engine under `benchmarking/` using the layout already proposed in `benchmarking/README.md`:

- `run.py` runs a selected model or the full suite and can resume without overwriting an earlier run.
- `adapters/zen.py` calls `https://opencode.ai/zen/v1/chat/completions` with the API key, user agent, and session header.
- `suites/` stores versioned JSONL cases and fixtures.
- `scorers/` contains category scorers.
- `build_profile.py` aggregates one run into the profile contract.
- `results/` stores run directories with immutable raw evidence, summaries, and manifests.

The benchmark uses public, license-compatible samples for reasoning and coding. Custom cases cover structured output, instruction following, tool calls, document QA, long context, and simple requests. The first complete suite should stay small enough to rerun within the two-day build window.

### Model profiles

Update `profileSchema`, `ModelProfile`, the registry, and the Python validation contract. A profile contains:

- measured capability pass rates;
- measured API latency and output token rate;
- usable context established by the suite;
- tool-calling and multimodal feature flags;
- provider and model provenance;
- a target deployment configuration used by hardware-aware routing.

Use these target deployment configurations for the mid-sem build:

| Model | Planned role | Target accelerator | Quantization | VRAM budget |
| --- | --- | --- | --- | ---: |
| `nemotron-3-ultra-free` | Higher-quality reasoning and difficult tasks | 2 x NVIDIA H100 80 GB | FP8 | 160 GB |
| `nemotron-3.5-lightning-free` | Fast, simple, structured, and latency-sensitive tasks | NVIDIA RTX 5090 32 GB | 4-bit | 32 GB |

Name this block `target_deployment` in stored profiles. Zen remains the execution provider for the mid-sem demo. End-sem work will update the block from the self-hosted serving configuration.

Add optional `available_vram_gb` to routing requests. Hard filtering rejects a candidate when its target VRAM budget exceeds the supplied limit. Existing tool and context filters remain unchanged.

### Dataset and training

Replace the current industrial template corpus with independently phrased, domain-neutral tasks. Include coding, education, safe finance, documents, research, office work, everyday requests, reasoning, tool use, long context, spreadsheets, and simple editing.

Reuse the existing training pipeline in `training/`. Update `generate_data.py` to load the generated profile version, preserve family-isolated splits, record its seed and settings, and hash every output split. Fine-tune Qwen3-0.6B with the current LoRA flow. Select the checkpoint from validation results only.

### Evaluation and demo

Expose every strategy through one routing interface and one output schema. The oracle selects the model with the better saved outcome for each evaluation task. Random routing records its seed.

Extend `demo.ts` or replace it with a Colab-friendly terminal entry point. It must print the candidate profiles, filtered candidates, selection, confidence, reason, routing time, selected-model output, and execution metrics. It must also load a saved run when Zen is unavailable.

Prepare a short screen recording from the same clean-start flow used in the live demo.

## Demo / acceptance

- [ ] One Colab command benchmarks either candidate or both candidates.
- [ ] Both candidates receive the same cases and scoring rules.
- [ ] A completed run retains raw responses, timings, scores, errors, metadata, and a run manifest.
- [ ] The profile builder produces schema-valid profiles without manual score editing.
- [ ] The displayed profiles include benchmark provenance and the agreed target deployment configuration.
- [ ] The generalized dataset contains no MRPL tasks and keeps task families isolated across splits.
- [ ] The training manifest records the profile version, seed, settings, split hashes, and selected checkpoint.
- [ ] The router rejects candidates that violate tool, context, or available-VRAM constraints.
- [ ] The learned router meets the agreed validation thresholds.
- [ ] All six strategies run against the same frozen workload and emit the same result shape.
- [ ] The report separates routing agreement, task success, routing latency, execution latency, throughput, and errors.
- [ ] A user can enter a simple task and see Lightning selected when its profile is sufficient.
- [ ] A user can enter a difficult task and see Ultra selected when its measured profile supports that choice.
- [ ] The terminal demo works from a clean start and has a saved-run fallback.
- [ ] The held-out result is produced once after artifact hashes are recorded.
- [ ] Tests, type checking, and linting pass.

## Out of scope

- Self-hosting the two primary models during mid-sem.
- Measuring physical GPU memory from Zen.
- More than two candidate models.
- MRPL-specific data or claims.
- A graphical dashboard. The terminal report is sufficient.
- Heterogeneous agent routing, historical-outcome matching, contextual-bandit exploration, and online learning.
- Production deployment, authentication UI, multi-user state, and distributed execution.
- Changing the held-out experiment after its first frozen run. Later changes start a new experiment version.
