# End-sem plan

Tick a task when it is done and verified. Each phase starts only after the one before it works, except phase 4, which waits for the Command Code reset on 2026-10-31 09:56 UTC.

## Phase 1: Temporary model router (DeepSeek V4.1 Flash vs Nemotron 3.5 Super VL)

- [x] Pilot run: 200 tasks x 6 models, judged (`pilot-v1-20261028T040319Z`)
- [x] Partial full run, stopped by the weekly limit (`full-v1-20261028T050713Z`, 1,387 of 4,800 calls)
- [x] Outcome training data, 501 tasks, family-isolated splits (`training/outcome_data.py`)
- [x] Router v1 trained on "fastest passing model" labels; test AUC 0.73, gains within noise
- [x] Evaluate router v2 ("does Nemotron pass?" labels, `artifacts/outcome-router-fp-v1`); keep the better one. Kept v2: AUC 0.785 vs 0.733, difference within noise
- [x] Platt-calibrate on validation; write `serving.json` (threshold, profiles). Platt made test calibration worse, so the service serves raw probabilities; threshold 0.86
- [x] Deploy `training/modal_outcome_app.py`; stop the old policy router app
- [x] Point `runtime.ts`, `router.ts`, `profiles.ts`, and `demo:cli` at the new endpoint
- [x] Record results in `docs/paper/results.md`

## Phase 2: OpenCode agents

Eight agents, each an OpenCode custom agent with its own prompt, tools, and output contract. The output contracts match the UI blocks used in phase 5.

| Agent | Output contract | Automatic check |
|---|---|---|
| code | Python file | Hidden unit tests in the Docker sandbox |
| spreadsheet | Transformed CSV plus change log | Expected cells |
| data-analysis | Answers plus chart spec from a CSV | Numeric answers |
| docx | `.docx` | Opens; judge rubric |
| slides | Slide JSON (`title`, `bullets`) | Schema; judge rubric |
| diagram | Mermaid source | Parses and renders |
| map | GeoJSON FeatureCollection | Valid GeoJSON; judge rubric |
| scene-3d | json-render three.js spec | Validates and renders |

- [x] `agents/` with one OpenCode agent config and one validator per agent (validator unit tests in `agents/test_validators.py`)
- [x] Runner: `opencode run --agent <a> -m <model>` in a sandboxed scratch workspace; record artifact, pass/fail, wall time, tokens (smoke `agents-v1-smoke1`: 8 of 8 agents pass on DeepSeek)
- [x] Task set: about 20 tasks per agent, plus overlap tasks that more than one agent could do, each with a gold agent label (`agents-v1`: 200 tasks, 260 runs per model)
- [x] Full run on the free OpenCode models, stopped by the free quota, which the four free models share: 31 of 1,040 runs finished, all on DeepSeek (`agents-v1-full-20261028`). At that quota the full run would take weeks, so per-agent model choice moves to phase 4

## Phase 3: End-sem routing

Agent choice is evaluated on the gold agent labels of the 200 `agents-v1` tasks, so it needs no runs. Model choice is evaluated on the single-call outcomes already recorded: `pilot-v1` (200 tasks x 6 models, every outcome known) and the 501 two-model tasks from phase 1.

- [x] Task embeddings (BAAI/bge-small-en-v1.5) and an outcome memory: task, agent, model, outcome, time, tokens, cost (`routing/memory.py`: 4,904 records, 1,200 tasks after the 2026-10-31 runs)
- [x] Agent selection: kNN over task embeddings on `agents-v1` gold labels (an overlap task counts as correct for any listed agent); compare with a fine-tuned Qwen classifier. Test n=80: kNN 0.89, fine-tuned Qwen3-0.6B 0.98, zero-shot 0.61, majority 0.20
- [x] Model selection from similar past outcomes, weighted by preference: accurate, balanced, fast, cheap (`routing/policy.py`; k, prior, and weights tuned on validation)
- [x] Contextual bandit: Thompson sampling during collection, online memory updates, greedy at evaluation
- [x] Evaluation on the recorded outcomes: best single model, random, kNN greedy, kNN + Thompson, oracle; success, latency, cost, cumulative regret per preference (`routing/replay.py`, 20 seeds). No bandit strategy beats the best single model
- [x] End-to-end path: task, then agent, then model, then the OpenCode agent run, then a memory append (shown with the recorded DeepSeek agent runs; `routing/route.py --dry-run`)
- [x] Record results in `docs/paper/results.md`

## Phase 4: After the reset (from 2026-10-31)

- [x] Resume `full-v1` on four models (DeepSeek, GLM, MiMo, Nemotron). Hy3 dropped on cost; Ornith dropped because its upstream host returned HTTP 402 with a zero balance. Spend capped at USD 4.90; score, judge with Codex in shards, summarize
- [x] Retrain and evaluate the four-model router; redeploy
- [x] Agent x model runs: 80 tasks (10 per agent) x 4 models = 320 paid Command Code runs through OpenCode, all scored, USD 1.79 of the USD 2.50 cap (`agents-cc-20261031`; host proxy `agents/cmdproxy.py`, cached input counted at 0.25 x input price, assumed). No pick is separated by the 95% intervals; DeepSeek is top or tied on 7 of 8 agents. Results in `docs/paper/results.md`; runs added to `routing/memory.py` (320 of 4,904 records)
- [x] Agent x model router: the four pool models routed per agent from the 320 runs, with a tolerance rule (cheapest or fastest model within a tolerance of DeepSeek's pass probability; `accurate` takes the highest pass). Leave-one-task-out replay with in-fold tolerance, online-learning stream (20 seeds), phase 3 replay rerun on the 4,904-record memory, and four live runs through the `cc` provider and proxy (4 of 4 passed, USD 0.0077 of the USD 0.05 cap). Nothing beats always-DeepSeek on pass; `cheap` saves 37% of cost for 2.5 points of pass (CI [-10.0, +5.0]); the per-agent table's 67 of 80 falls to 61-63 honestly; the bandit learns weakly on 80 tasks. Contract for the UI in the `routing/route.py` docstring; results in `docs/paper/results.md`

## Phase 5: Unified UI

- [x] One Next.js app that renders each agent's output with its block from `ai-components` (code, spreadsheet, data analysis, docx, slides, Mermaid, map, three.js). All eight render recorded artifacts from `agents-cc-20261031` at 1280 and 390 px; code, slides and diagram also rendered from live runs (`docs/screenshots/`)
- [x] Every agent run goes through the agent router, which picks the agent and the model from real agent outcomes; that choice is final. A "Just answer" mode sends the prompt through the Modal model router to one Command Code call. The UI shows the chosen agent and model, confidence, and the runner-up
- [x] Runs from the UI feed the outcome memory. A run is appended with no verdict, the user marks it good or bad, and the next route counts it (MiMo on diagram went from 12 to 13 past runs)

## Phase 6: Paper

- [ ] Figures: per-category pass rates, routing headroom, cost-latency curves, regret curves
- [ ] Draft from `docs/paper/results.md`
