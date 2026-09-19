# 03 - Compare routing strategies end to end

## Goal

Run every routing strategy against one frozen workload and produce an auditable comparison of routing quality, task success, and execution performance.

## Files

Create:
- `evaluation/baselines.py`
- `evaluation/run.py`
- `evaluation/report.py`
- `evaluation/workload.jsonl`
- `evaluation/test_evaluation.py`

Modify:
- `router.ts`
- `training/evaluate.py`
- `evaluation.md`
- `evaluation-summary.json`
- `package.json`

## Implementation notes

- Implement random, round-robin, static-rule, existing heuristic, learned, and oracle routing behind one input and result contract.
- Freeze a balanced 50 to 100 task workload. Record the random seed.
- Cache each execution by benchmark version, task ID, model ID, and decoding settings so strategies can reuse identical Zen results.
- Define oracle selection from the saved per-model outcome for each task.
- Report policy agreement, downstream task success, invalid output, constraint violations, routing latency, Zen execution latency, token rate, and errors separately.
- Run the untouched held-out test once only after the workload, profiles, checkpoint, strategies, and scorers are frozen. Record their hashes first.

## Blocked by

- 02 - Generalize data and train the router

## Done when

- All six strategies accept the same candidate set and workload and emit the same result shape.
- Repeating the evaluation reuses cached model executions.
- The report contains aggregate and per-category results with links to the saved evidence.
- The held-out result is clearly separate from validation and has a frozen artifact manifest.
- The learned router matches or beats the best non-oracle downstream success, or preserves success while improving latency.
