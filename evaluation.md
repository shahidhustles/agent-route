# Routing strategy evaluation

Ticket 03 adds the frozen 70-item workload and the six-policy evaluation runner. The workload contains two evaluation passes over 35 existing benchmark tasks, with ten items in each of seven categories, and records seed `20260919`. Both passes reference the same task IDs and decoding settings, so they reuse the 70 model outcomes saved by ticket 01. `evaluation/frozen-manifest.json` records the workload, profiles, checkpoint, strategies, scorer, and sealed test-data hashes before held-out evaluation.

Run the validation comparison from the repository root:

```bash
python evaluation/run.py \
  --checkpoint /path/to/merged-checkpoint \
  --benchmark-run benchmarking/results/v1-20260919T110437Z-272c
python evaluation/report.py
```

The default is offline-only. The first command imports the already-saved ticket 01 outcomes and stores them by benchmark version, task ID, model ID, and decoding settings under `evaluation/cache/`. Later strategies and reruns reuse those responses. A cache miss stops the run without contacting Command Code. Paid calls require `--allow-paid-calls` and an explicit `--max-cost-usd` cap.

The report separates policy agreement, downstream success, invalid output, hard-constraint violations, routing latency, provider latency, token rate, calculated request cost, routing errors, and execution errors. It also writes per-category results and evidence paths.

The repository does not contain a complete merged checkpoint, so `evaluation-summary.json` marks the learned-policy comparison as pending instead of presenting partial results as a finished experiment.

Run the held-out router test once, after validation is accepted:

```bash
python training/evaluate.py \
  --model /path/to/merged-checkpoint \
  --split test \
  --allow-held-out-test \
  --artifact-manifest evaluation/frozen-manifest.json \
  --report evaluation/held-out.json
```

The command checks the checkpoint and sealed test-data hashes first. It refuses to overwrite an existing held-out report.

## Prior MVP evaluation

The accepted checkpoint is Qwen3-0.6B with LoRA, merged with base revision `c1899de289a04d12100db370d81485cdf75e47ca`. Colab Tesla T4 training used 6400 examples for two epochs. The validation split contains 800 examples, with another 800 in the separate test split.

| Measure                        | Recorded validation result                           |
| ------------------------------ | ---------------------------------------------------- |
| Exact route accuracy           | 82.875%                                              |
| Valid JSON format              | 100%                                                 |
| Invalid candidate slug rate    | 0%                                                   |
| Raw hard-constraint violations | 0.75%, six requests rejected by the original wrapper |
| Original wrapper acceptance    | 99.25%                                               |
| Anonymous model accuracy       | 83.251%                                              |
| Reversed candidate accuracy    | 81.875%                                              |
| Candidate-order agreement      | 83.25%                                               |
| Winner-removed accuracy        | 83.554%                                              |
| T4 median / p95 latency        | 0.820 / 1.257 seconds                                |

These numbers measure agreement with a synthetic profile-based teacher, not actual primary-model quality. The test split remains untouched because training stopped at the original 90% validation gate. Sahil accepted 82.875% for the MVP on September 6, 2026. This scope decision is not a new test-accuracy claim.

[evaluation-summary.json](evaluation-summary.json) preserves per-family metrics and correct/incorrect examples from the downloaded report. The full report remains in the model archive.

The new runtime prefilters incompatible candidates and uses compatible deterministic fallback for rejected output. Automated tests cover its contract. The historical score describes the original evaluation path, not this updated wrapper. No new full-dataset accuracy is claimed.

## Local smoke run

The downloaded merged checkpoint returned valid routes for six tasks on this Windows workstation without runtime fallback. Requests took 4.99 to 8.53 seconds, including the cold first request.

| Task                                  | Selected model               |
| ------------------------------------- | ---------------------------- |
| Word inspection approval note         | Qwen3.8-27B                  |
| Python debugging and sandbox tests    | Qwen2.5-Coder-14B-Instruct   |
| Pipe pressure calculation             | DeepSeek-R1-Distill-Qwen-14B |
| Short polite rewrite                  | Qwen3.8-27B                  |
| Multi-file search and JSON extraction | Qwen3.8-27B                  |
| 150K-token manual comparison          | Qwen3.8-27B                  |

The short rewrite picked the larger general model, so simple-task efficiency is not reliable. All six confidence values were 0.95. Confidence is uncalibrated and must not be shown as a probability of correctness. Reasoning and long-context validation results are weaker than document/tool results.

This verifies routing only. It does not prove that six primary models are installed, that downstream tasks complete on those models, or that the whole workbench is air-gapped.
