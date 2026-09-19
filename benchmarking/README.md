# Benchmarking engine handoff

The missing engine must run each candidate model on a fixed suite and write measured profiles in the schema already accepted by `runtime.ts` and `registry.ts`.

## Required output

Produce one record per model:

```json
{
  "model_slug": "example-model",
  "capabilities": {
    "reasoning": 0.0,
    "coding": 0.0,
    "tool_use": 0.0,
    "document_qa": 0.0,
    "structured_output": 0.0,
    "instruction_following": 0.0,
    "long_context": 0.0
  },
  "runtime": {
    "tokens_per_second": 0.0,
    "peak_vram_gb": 0.0,
    "usable_context": 1
  },
  "features": {
    "tool_calling": false,
    "multimodal": false
  }
}
```

Capability scores must come from versioned task suites and deterministic scorers where possible. Store raw model responses and per-case results so every aggregate score can be audited. Record warm and cold latency separately, along with hardware, quantization, serving configuration, model revision, seed, and benchmark version.

## Suggested layout

```text
benchmarking/
  adapters/       model-server clients
  suites/         versioned prompts, fixtures, and expected outputs
  scorers/        category-specific scoring code
  results/        ignored raw runs and summaries
  run.py          benchmark entry point
  build_profile.py
```

## Mid-sem acceptance

- At least two real candidate models run through the same suite.
- Every generated profile passes `profileSchema` in `runtime.ts`.
- A repeated run records enough metadata to explain score or latency changes.
- The router consumes generated profiles without hand-editing values.
- The report compares learned routing with random, round-robin, static-rule, heuristic, and oracle baselines.

The engine should remain separate from router training. Benchmarking measures primary models. Router training learns to choose among the resulting profiles.

## Running

The engine is implemented under `benchmarking/`:

```text
benchmarking/
  adapters/zen.py     OpenAI-compatible client for https://opencode.ai/zen/v1
  suites/v1.jsonl     35 versioned cases (5 per capability category)
  scorers/            deterministic scorers; category pass rates come only from these
  run.py              benchmark entry point
  build_profile.py    turn a saved run into router profiles
  results/            immutable run directories (never overwritten)
```

Run one model or both (set `ZEN_API_KEY`; retries of one case reuse its `x-opencode-session` value, separate cases get separate values):

```bash
export ZEN_API_KEY=...          # Colab: read from a Colab secret instead
python benchmarking/run.py --models both --suite v1
python benchmarking/run.py --models ultra --suite v1 --resume benchmarking/results/<run>
python benchmarking/build_profile.py benchmarking/results/<run>
```

Every run writes an immutable `results/<suite>-<timestamp>-<id>/` directory with
`meta.json` and one JSON file per case (raw request without authorization data,
raw response, timings, token counts, errors, score). Interrupted runs resume
with `--resume <dir>`: only missing case results are computed, earlier evidence
is preserved. `build_profile.py` writes `profiles.json` into the run directory;
capability values are category pass rates and `peak_vram_gb` is declared from
the agreed target deployment (`glm-5.3-flash`: 160 GB on 2 x NVIDIA H100 80 GB,
FP8; `deepseek-v4.1-flash`: 640 GB on 8 x NVIDIA H100 80 GB, FP8 — declared
planning assumptions; provider hardware is not public), not measured through
the API.

The first two runs (`v1-20260919T105523Z-d7e7`, pre-fix scorer; and
`v1-20260919T110437Z-272c`) used the same suite after fixing the expected value
for `c2-reverse-string` and relaxing exact scoring to ignore markdown emphasis
and trailing punctuation. Both runs are kept as evidence.

Tests: `python -m unittest discover -s benchmarking -p 'test_*.py'`.
