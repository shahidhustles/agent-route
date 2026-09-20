# 04 - Package the mid-sem review demo

## Goal

Provide one clean terminal flow that explains the profiles, routes a task, runs the selected model, and displays the strategy comparison.

## Files

Create:
- `demo/README.md`
- `demo/saved-run.json`

Modify:
- `demo.ts`
- `README.md`
- `PROJECT_STATUS.md`
- `MID_SEM_CHECKLIST.md`
- `package.json`

## Implementation notes

- Print both profiles, eligible candidates after hard filtering, selected model, confidence, profile evidence, routing time, model response, task score, token use, calculated request cost, and execution metrics.
- Choose two prepared examples that favor different models according to the final measured profiles. Base each explanation on visible profile differences and constraints.
- Add a saved-run mode that completes the same presentation without a live Zen call.
- Document a clean-start command for Colab and local playback.
- Record a short fallback video after the final flow passes.
- Keep mid-sem model routing separate from the end-sem self-hosted agent router in all wording.

## Blocked by

- 03 - Compare routing strategies end to end

## Done when

- A reviewer can enter a task and see filtering, selection, execution, and metrics in one terminal flow.
- The demo uses `glm-5.3-flash` and `deepseek-v4.1-flash` and shows at least one justified selection of each.
- Live and saved-run modes present the same fields and comparison summary.
- The documented clean-start flow works within the review time limit.
- Repository status, checklist, report, and demo use the same model names, profile version, checkpoint, and result values.
