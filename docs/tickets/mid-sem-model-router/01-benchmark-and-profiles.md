# 01 - Benchmark Zen models and build profiles

## Goal

Run one versioned benchmark against both paid Zen models and turn the saved results into profiles that the router can consume.

## Files

Create:
- `benchmarking/run.py`
- `benchmarking/build_profile.py`
- `benchmarking/adapters/zen.py`
- `benchmarking/suites/v1.jsonl`
- `benchmarking/scorers/__init__.py`
- `benchmarking/test_benchmarking.py`

Modify:
- `benchmarking/README.md`
- `runtime.ts`
- `profiles.ts`
- `registry.ts`
- `registry.example.json`
- `training/common.py`
- `training-profiles.json`
- `runtime.test.ts`

## Implementation notes

- Benchmark `glm-5.3-flash` and `deepseek-v4.1-flash` through the configured OpenCode Zen endpoint with identical cases and scorers.
- Read the Zen API key from an environment variable. Send a deterministic `x-opencode-session` value per benchmark conversation and redact authorization data from saved evidence.
- Save each run in a new immutable directory with raw requests, responses, timings, token counts, calculated request costs, errors, scores, model IDs, suite version, and timestamp. A rerun must not overwrite an earlier run.
- Cover the capability fields already used by the router. Capability values are category pass rates.
- Add `target_deployment` to the profile contract. Declared planning assumptions (provider hardware is not public): 160 GB on 2 x NVIDIA H100 80 GB with FP8 for `glm-5.3-flash`, and 640 GB on 8 x NVIDIA H100 80 GB with FP8 for `deepseek-v4.1-flash`.
- Add optional `available_vram_gb` to routing requests. Filter models that exceed it, alongside the existing tool and context filters.
- Run the benchmark from Colab. Use the Colab MCP to execute the notebook cells or commands, inspect progress, and download the completed run and generated profiles into the workspace.

## Blocked by

None.

## Done when

- One Colab command benchmarks either model or both.
- A completed run can resume after interruption and preserves its earlier evidence.
- The profile builder emits two schema-valid profiles without hand-editing capability scores.
- The router rejects a `deepseek-v4.1-flash` request with a 160 GB limit and keeps `glm-5.3-flash` eligible.
- Python tests, Bun tests, type checking, and linting pass.
