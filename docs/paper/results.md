# Paper results

Facts and numbers for the IEEE paper. Keep each entry short: a table, a number with its source run, or a one-line decision with its reason. Replace a stale row rather than appending a new one.

## Candidate pool

Six open-weight models served through the Command Code provider API (`https://api.commandcode.ai/provider/v1`), chosen for low price and lab diversity. Prices are USD per 1M tokens, input / output, from the Command Code GOAT plan page on 2026-10-28.

| Model ID | Lab | Price in / out | Role in pool | Public evidence (mostly vendor-reported) |
|---|---|---|---|---|
| `deepseek/deepseek-v4.1-flash` | DeepSeek | 0.15 / 0.60 | Strong generalist | DeepSWE v1.1 74.2, GPQA Diamond 90.9 |
| `z-ai/glm-5.3-flash` | Z.ai | 0.15 / 0.50 | Agentic, terminal, multimodal | Terminal-Bench 2.1 84.3 (NVIDIA BF16 check 82.6) |
| `ornith/ornith-1.5-122b` | Ornith | 0.16 / 0.64 | Coding specialist | SWE-bench Verified 84.5 (unverified) |
| `xiaomi/mimo-v2.6-flash` | Xiaomi | 0.14 / 0.28 | Cheapest output, long context | AA Intelligence Index 38, AA-LCR 74.3 |
| `tencent/hy3-paid` | Tencent | 0.14 / 0.58 | Search and research | BrowseComp 84.2 |
| `nvidia/nemotron-3.5-super-vl` | NVIDIA | 0.20 / 0.50 | Small, fast, low-cost tier (12B active) | AA Intelligence Index 26.5 |

Excluded: Step 3.5 Flash (provider returns model_not_found), Laguna S 2.1 (free tier rate-limited), MiniMax M3.1 Flash (license unclear, 93% AA hallucination rate), Qwen3.8-27B (0.40 / 3.00, verbose), Muse Spark Open (1.25 / 4.25).

## Method decisions

- Hy3 and Ornith are dropped from the `full-v1` run and the multi-model router (2026-10-31). Hy3 was the priciest to finish (about USD 1.87). Ornith's upstream host returned HTTP 402 with a zero balance on every call. Their pilot results stay in this file.
- Router labels come from measured outcomes: each pool model answers every task. The phase 1 two-model router labels a task with Nemotron when Nemotron passed, else DeepSeek. These replace the earlier policy-generated labels, whose confidence was a formula (`0.55 + margin`) and stayed in 0.6-0.7.
- Router confidence is the softmax over each candidate slug's sequence log-probability under the router. The deployed router serves it raw; the two-model router section says why.
- Tasks come from public datasets with automatic scoring. Open-ended real-user prompts (WildChat) are scored by an LLM judge outside the pool: GPT-6.1 Sol, medium reasoning, blind to model identity.
- Known risk: contamination. LiveCodeBench's newest public release (test6) covers contests from 2025-01 to 2025-04, before these models' training cutoffs.

## Task mix

Pilot suite `pilot-v1`: 200 tasks, seed 20261028, manifest `benchmarking/suites/pilot-v1.manifest.json`.

| Category | Source datasets | Scoring | Tasks |
|---|---|---|---:|
| Coding | LiveCodeBench test6 (AtCoder, stdin), MBPP+ | Unit tests in a network-less Docker sandbox | 35 |
| Math | MATH-500 (levels 3-5), GSM8K | Boxed-answer match; judge checks mismatches | 25 |
| Reasoning | MMLU-Pro (all 14 subjects) | Option letter | 25 |
| Instruction following | IFEval | Google's IFEval checkers, strict | 20 |
| Tool use | BFCL v3 simple, multiple | Function name and argument match | 25 |
| Document QA | SQuAD v2 (25% unanswerable) | F1 >= 0.5 or span match | 20 |
| Long context | LongBench v2 (short, <= 200k chars) | Option letter | 15 |
| Open-ended | WildChat-1M (English, first turn, non-toxic) | LLM judge, pass at >= 7/10 | 35 |

Decoding: temperature 0, streamed, output cap 4k-16k tokens by category. A response cut off at the cap counts as a failure.

## Pilot results (run `pilot-v1-20261028T040319Z`)

1,200 calls (6 models x 200 tasks). Total pool cost USD 1.80. The judge ran on a separate subscription at no API cost.

Pass rate by category:

| Model | Coding | Doc QA | Instr. | Long ctx | Math | Open-ended | Reasoning | Tool use | All (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| DeepSeek V4.1 Flash | 0.77 | 0.90 | 0.85 | 0.60 | 1.00 | 0.83 | 0.88 | 0.96 | 0.855 [0.80, 0.90] |
| GLM-5.3 Flash | 0.66 | 0.90 | 0.80 | 0.67 | 1.00 | 0.63 | 0.80 | 0.96 | 0.790 [0.73, 0.84] |
| Ornith 1.5 122B | 0.74 | 0.90 | 0.80 | 0.60 | 1.00 | 0.46 | 0.80 | 0.96 | 0.770 [0.71, 0.82] |
| MiMo V2.6 Flash | 0.69 | 0.90 | 0.80 | 0.60 | 1.00 | 0.54 | 0.76 | 0.88 | 0.760 [0.70, 0.81] |
| Hy3 | 0.63 | 0.85 | 0.95 | 0.53 | 0.88 | 0.57 | 0.72 | 0.96 | 0.750 [0.69, 0.81] |
| Nemotron 3.5 Super VL | 0.60 | 0.90 | 0.85 | 0.53 | 0.96 | 0.54 | 0.80 | 0.96 | 0.755 [0.69, 0.81] |

Efficiency per task:

| Model | Mean cost (USD) | Median latency (s) | Mean output tokens | Reasoning share | Truncated at cap |
|---|---:|---:|---:|---:|---:|
| DeepSeek V4.1 Flash | 0.00139 | 5.9 | 1922 | 0.86 | 7 |
| GLM-5.3 Flash | 0.00176 | 4.4 | 2967 | 0.90 | 17 |
| Ornith 1.5 122B | 0.00160 | 15.0 | 2009 | 0.80 | 9 |
| MiMo V2.6 Flash | 0.00087 | 13.0 | 2155 | 0.75 | 11 |
| Hy3 | 0.00253 | 20.3 | 3901 | 0.94 | 20 |
| Nemotron 3.5 Super VL | 0.00086 | 1.7 | 913 | 0.27 | 1 |

Routing headroom:

| Strategy | Pass rate | Mean cost (USD) |
|---|---:|---:|
| Best single model (DeepSeek V4.1 Flash) | 0.855 | 0.00139 |
| Oracle, cheapest passing model | 0.905 | 0.00108 |

Findings:

- Models passing per task: 0 models 19, 1-5 models 69, all 6 models 112. Only 69 of 200 tasks (35%) separate the pool.
- Cheapest-passing labels: MiMo 86, Nemotron 48, DeepSeek 36, GLM 8, Hy3 3, none 19. Fastest-passing labels: Nemotron 123. The label depends on the objective.
- DeepSeek's lead comes mostly from open-ended (0.83 vs <= 0.63) and coding. Per-category n is 15-35, so most other gaps sit inside noise.
- GLM-5.3 Flash spent the full 16k-token cap reasoning on 12 of 25 LiveCodeBench problems without emitting code.
- LLM judge (GPT-6.1 Sol, medium) scored 125 of 210 open-ended answers >= 7; mean rating DeepSeek 7.51, others 5.89-6.37. It confirmed 3 of 4 flagged math mismatches as equivalent.
- Next suite: oversample hard items and cap all-pass tasks, so labels carry signal.

## Full run (run `full-v1-20261028T050713Z`, finished 2026-10-31)

Four models on all 800 tasks (seed 20261028, manifest `benchmarking/suites/full-v1.manifest.json`); all 800 tasks have results from all four. Hy3 (68 tasks) and Ornith (74 tasks) records stay out of the tables. Judge: GPT-6.1 Sol, medium, blind; 603 of 880 open-ended answers scored >= 7, and 28 of 40 flagged math mismatches were equivalent.

| Model | Coding | Doc QA | Instr. | Long ctx | Math | Open-ended | Reasoning | Tool use | All |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DeepSeek V4.1 Flash | 0.66 | 0.88 | 0.96 | 0.77 | 0.99 | 0.89 | 0.89 | 0.80 | 0.851 |
| GLM-5.3 Flash | 0.59 | 0.82 | 0.81 | 0.72 | 0.89 | 0.72 | 0.88 | 0.85 | 0.76 |
| Nemotron 3.5 Super VL | 0.59 | 0.90 | 0.86 | 0.72 | 0.92 | 0.66 | 0.87 | 0.82 | 0.76 |
| MiMo V2.6 Flash | 0.50 | 0.88 | 0.80 | 0.67 | 0.92 | 0.47 | 0.83 | 0.85 | 0.67 |

| Model | Mean cost (USD) | Median latency (s) | Mean output tokens | Truncated at cap |
|---|---:|---:|---:|---:|
| DeepSeek V4.1 Flash | 0.00193 | 9.2 | 2631 | 33 |
| GLM-5.3 Flash | 0.00125 | 9.0 | 1794 | 47 |
| Nemotron 3.5 Super VL | 0.00221 | 4.6 | 3385 | 71 |
| MiMo V2.6 Flash | 0.00121 | 24.6 | 3072 | 73 |

- Models passing per task: 0 models 82, 1 model 56, 2 models 67, 3 models 136, 4 models 459. 341 of 800 tasks separate the pool.
- Best single model DeepSeek, pass 0.851 at USD 0.00193 per task. Oracle (cheapest passing): pass 0.897 at USD 0.00136.
- Cheapest-passing labels: GLM 286, MiMo 263, DeepSeek 125, Nemotron 44, none 82. Fastest-passing: Nemotron 489, DeepSeek 118, GLM 102, MiMo 9, none 82.
- Weekly limit: the resumed window made 1,955 successful calls for USD 2.38 at list price and never hit the limit. The 2026-10-28 stop came at about USD 5.43 by the same accounting, so this window gives no new evidence on the limit's size. Ornith's 726 failed calls were not billed.

## Two-model router (phase 1, 2026-10-28)

Qwen3-0.6B LoRA router choosing DeepSeek V4.1 Flash (strong) or Nemotron 3.5 Super VL (fast). Data: 501 tasks both models answered in `pilot-v1-20261028T040319Z` and `full-v1-20261028T050713Z`, family-isolated splits (train 350, validation 52, test 100). Nemotron passes 70 of 100 test tasks. AUC is for "Nemotron passes"; thresholds come from validation (fastest setting within 0.02 of always-DeepSeek pass rate).

| Strategy (test, n=100) | Pass rate | Mean latency (s) | AUC | Share to Nemotron |
|---|---:|---:|---:|---:|
| Always DeepSeek | 0.78 | 26.8 | | 0 |
| Always Nemotron | 0.70 | 12.6 | | 1 |
| Random | 0.74 | 19.7 | 0.50 | 0.5 |
| Oracle | 0.81 | 14.2 | | |
| Embedding kNN (bge-small, k=10) | 0.77 | 25.9 | 0.756 | |
| Zero-shot Qwen3-0.6B | 0.74 | 18.9 | 0.291 | 0.39 |
| Router v1, "fastest passing model" labels | 0.77 | 26.6 | 0.733 | 0.05 |
| Router v2, "Nemotron passes" labels (rollback) | 0.77 | 26.5 | 0.785 | 0.09 |

At a matched 50% share to Nemotron, every ranker lands at 0.74-0.75 pass rate (random 0.74, kNN 0.75, v1 0.74, v2 0.74).

Calibration on test, P(Nemotron passes):

| Router | ECE raw | ECE Platt | Brier raw | Confidence range of pick |
|---|---:|---:|---:|---|
| v1 | 0.128 | 0.122 | 0.205 | 0.50-0.73 |
| v2 | 0.064 | 0.110 | 0.162 | 0.50-0.89 |

Findings:

- v2 beats v1 on test AUC by 0.05, but the paired bootstrap 95% CI of the difference is [-0.01, 0.12] (2,000 resamples). On validation v1 scored higher (0.60 vs 0.56). Treat the label change as a small, unconfirmed gain.
- Neither learned router beats random at matched share. With 100 test tasks, a 1-2 point pass-rate gap is inside noise.
- The validation threshold (0.86) sends only 9% of tasks to Nemotron, so this router behaves almost like always-DeepSeek. The latency saving the oracle shows (14.2 s vs 26.8 s) is not captured yet.
- Platt scaling fit on 52 validation tasks (slope 0.67) made v2 worse on test, so the service returns raw probabilities. `artifacts/outcome-router-fp-v1/serving.json` records this.
- Deployed as Modal app `agent-route-outcome-router` (T4). Median routing time 136 ms in offline GPU scoring; 110-150 ms per live request after the first (1.0 s).

## Four-model router (phase 4, 2026-10-31)

Qwen3-0.6B LoRA router over DeepSeek, GLM, MiMo, and Nemotron (`artifacts/outcome-router-4m-v1`, 4 epochs, Colab T4, 1,638 s, best validation loss 0.078). Data: the 1,000 tasks all four models answered in `pilot-v1` and `full-v1`, family-isolated and source-stratified (train 700, validation 100, test 200; `data/outcome-4m`). Deployed 2026-10-31 on Modal app `agent-route-outcome-router`; `artifacts/outcome-router-fp-v1` is the rollback.

Label rule: rank models by mean cost x median latency on train (Nemotron, GLM, DeepSeek, MiMo); the label is the first model in that order that passed, and DeepSeek when none passed. Train labels: Nemotron 527, DeepSeek 109, GLM 61, MiMo 3. On validation, a bge-small kNN vote predicted this set at 0.79 label agreement (majority 0.77, pass 0.78). The cost-ranked labels (GLM/MiMo-heavy) agreed at 0.47 and dropped kNN pass to 0.68-0.75; fastest-passing labels agreed at 0.61-0.66. The ordered rule is mostly "Nemotron passes", as in the two-model router, with DeepSeek as the none-pass default.

Truncation shapes the labels: 80 of Nemotron's 245 failures were output-cap hits (GLM 76 of 232, MiMo 102 of 309, DeepSeek 53 of 148), and 56 of the 102 none-pass tasks include a truncation.

| Strategy (test, n=200) | Pass | Mean cost (USD) | Median latency (s) | Mean latency (s) |
|---|---:|---:|---:|---:|
| Always DeepSeek | 0.855 | 0.00205 | 9.9 | 22.2 |
| Always GLM | 0.780 | 0.00153 | 8.9 | 30.1 |
| Always MiMo | 0.685 | 0.00116 | 22.3 | 61.7 |
| Always Nemotron | 0.755 | 0.00210 | 4.0 | 9.5 |
| Random | 0.769 | 0.00170 | 9.5 | 31.2 |
| Oracle (label rule) | 0.895 | 0.00200 | 5.3 | 16.0 |
| Embedding kNN (k=20), threshold 0.76 | 0.810 | 0.00223 | 6.5 | 19.4 |
| Zero-shot Qwen3-0.6B | 0.855 | 0.00205 | 9.9 | 22.2 |
| Router, threshold 0.76 | 0.840 | 0.00212 | 7.7 | 19.7 |
| Router, `cheap` preference | 0.820 | 0.00191 | 9.2 | 23.6 |

- Serving rule: top candidate, or DeepSeek below a confidence threshold. The threshold is the lowest-latency one on validation with pass rate within 0.02 of always-DeepSeek, the same rule as the two-model router. It gives 0.76, which sends 48% of test tasks to Nemotron and 52% to DeepSeek. GLM and MiMo never clear it. A first evaluation used a cost-plus-latency score instead and landed on 0.92 (100% DeepSeek), decided by a single validation task. That score was dropped after the test curve had been seen, so treat 0.76 as chosen by a validation-only rule, restored after one look at test.
- Router minus always-DeepSeek (paired bootstrap): pass -0.015 (CI [-0.045, 0.010]), median latency -2.2 s (CI [-3.8, -0.9]), mean latency -2.5 s (CI [-3.7, -1.3]), cost +USD 0.00007 (CI [-0.00005, 0.00022]). The router saves latency, not money.
- `cheap` preference: the router's Nemotron probability acts as an easy-task score, and easy tasks go to GLM instead. GLM and the threshold (0.74, lowest-cost within 0.02 of always-DeepSeek) were chosen on validation; 56% of test tasks go to GLM. Against always-DeepSeek: pass -0.035 (CI [-0.065, -0.005]), cost -USD 0.00014 or 6.7% (CI [-0.00030, 0.00005]), median latency -0.7 s (CI [-2.0, 0.7]). The cost saving is not significant at n=200.
- A fixed per-category table is worse. With true categories, cheapest-within-0.02 on train (GLM for tool use, reasoning, long context; MiMo for document Q&A) gives 0.83 pass at USD 0.00205 on test, the same cost as always-DeepSeek. GLM and MiMo pass nothing a learnable rule can target; only 13 of 1,000 tasks pass on GLM or MiMo alone.
- Limits on cheap routing (all 1,000 tasks, 5-fold family-grouped CV, 2026-10-31). A per-model pass predictor (logistic regression on bge-small plus prompt length) reaches AUC 0.64-0.72. Sending tasks to GLM by that score gives 0.832 pass at USD 0.00166 against DeepSeek's 0.852 at USD 0.00183 (-9.2% cost); on the 200-task test split it loses to the `cheap` preference (0.810 at USD 0.00196 vs 0.820 at USD 0.00191). The cheapest-passing oracle is 0.898 at USD 0.00148 (-19%), so the gap is prediction, not capability.
- Try-cheap-then-escalate does not pay here. Escalating GLM to DeepSeek on truncation costs USD 0.00188 at 0.795 pass. Even a perfect, free checker costs USD 0.00222 at 0.881 pass, 21% above always-DeepSeek, because failures concentrate on the expensive tasks.
- The pool's price gap is narrow: input USD 0.15 (DeepSeek, GLM) and 0.14 (MiMo) per 1M tokens, output 0.60, 0.50, and 0.28. Moving every task off DeepSeek saves 26% (GLM) or 38% (MiMo) at most, so DeepSeek is the strongest model here, not a frontier-priced one.
- Matched share at the same 48% Nemotron mix: random assignment passes 0.806, kNN 0.810, the router 0.840. kNN at its own 0.76 threshold loses 0.045 pass (CI [-0.075, -0.020]).
- Where the Nemotron traffic goes: all of math500, mbppplus, squad_v2, gsm8k, most of mmlu_pro and bfcl. LiveCodeBench, LongBench, and most ifeval and WildChat stay on DeepSeek. The pass-rate loss sits in mmlu_pro (0.80 vs 0.92, n=25) and math500 (0.95 vs 1.00, n=22).
- Calibration of the top pick (did it pass?): ECE 0.081, Brier 0.156, mean confidence 0.745 against 0.755 pass rate. Zero-shot ECE 0.259, Brier 0.254. Zero-shot falls back to DeepSeek on everything.
- Oracle headroom is 0.895 pass at 16.0 s mean latency. 459 of the 800 full-run tasks pass on all four models, so the pool leaves little pass rate to win and the router's gain is latency.
- Live check (2026-10-31, `transformers` 4.51.3 on Modal, adapter trained on 5.x): probabilities match the Colab scores within 0.007 on 12 test tasks, with 12 of 12 picks the same. Routing takes 250-560 ms warm; the cold start took 70 s.

## Agent runs (phase 2, 2026-10-28)

Eight OpenCode agents (code, spreadsheet, data-analysis, docx, slides, diagram, map, scene-3d), each run headless in a fresh Docker container. Suite `agents-v1`: 200 tasks (20 per agent plus 40 overlap tasks with every acceptable agent listed), 260 runs per model, seed 20261028. Smoke run `agents-v1-smoke1`: all 8 agents pass on DeepSeek V4.1 Flash.

Full run `agents-v1-full-20261028` on the free OpenCode models stopped at 31 of 1,040 runs, all DeepSeek: code 17/20, spreadsheet 11/11. Mean 6.2 model calls and 94k input tokens per run (88% cached). The free quota is shared across the four free models and ran out after about 200 calls and 3M tokens. Two hard LiveCodeBench tasks hit the 900 s cap and used 550-750k input tokens each.

## Agent x model runs (phase 4, 2026-10-31)

Run `agents-cc-20261031`: the eight OpenCode agents on the four pool models, paid from the Command Code plan. 10 tasks per agent (80 tasks, seed 20261031, `benchmarking/suites/agents-cc-v1.manifest.json`; code skips the two hard LiveCodeBench tasks and two MBPP+ tasks that took over 100k tokens on the free tier, so all 10 code tasks are MBPP+), every task on every model: 320 runs, 80 per model, all scored. No run was discarded or stopped by a limit; one MiMo run (map-02) hit the 600 s timeout. Judged agents (docx, slides, map; 116 runs with a passing automatic check): Codex GPT-6.1 Sol, medium, blind to model, pass at score >= 7.

Cost: runs go through a host proxy that holds the API key and counts list-price cost (USD per 1M tokens in / out: DeepSeek 0.15 / 0.60, GLM 0.15 / 0.50, MiMo 0.14 / 0.28, Nemotron 0.20 / 0.50). The API reports cached tokens but no cached price, and no published cached price was found, so cached input is counted at 0.25 x input price (assumed). Ledger total USD 1.79 of the USD 2.50 cap (run records USD 1.77; the rest is the smoke run and one request cut off by a timeout, charged at its worst case). At full input price for cached tokens, the same run would have counted about USD 3.6 and hit the cap.

Pass rate (passed / 10) with the 95% Wilson interval, mean cost per run, median wall time:

| Agent | DeepSeek | GLM | MiMo | Nemotron |
|---|---|---|---|---|
| code | 0.90 [0.60, 0.98]; $0.0019; 17 s | 0.90 [0.60, 0.98]; $0.0014; 12 s | 0.80 [0.49, 0.94]; $0.0021; 50 s | 0.90 [0.60, 0.98]; $0.0027; 7 s |
| spreadsheet | 1.00 [0.72, 1.00]; $0.0043; 28 s | 1.00 [0.72, 1.00]; $0.0032; 19 s | 1.00 [0.72, 1.00]; $0.0065; 119 s | 0.80 [0.49, 0.94]; $0.0118; 19 s |
| data-analysis | 1.00 [0.72, 1.00]; $0.0037; 28 s | 1.00 [0.72, 1.00]; $0.0025; 22 s | 1.00 [0.72, 1.00]; $0.0051; 90 s | 1.00 [0.72, 1.00]; $0.0153; 20 s |
| docx | 0.30 [0.11, 0.60]; $0.0138; 89 s | 0.50 [0.24, 0.76]; $0.0058; 62 s | 0.40 [0.17, 0.69]; $0.0098; 186 s | 0.40 [0.17, 0.69]; $0.0143; 24 s |
| slides | 0.50 [0.24, 0.76]; $0.0034; 32 s | 0.40 [0.17, 0.69]; $0.0024; 25 s | 0.30 [0.11, 0.60]; $0.0020; 74 s | 0.40 [0.17, 0.69]; $0.0040; 10 s |
| diagram | 0.90 [0.60, 0.98]; $0.0022; 17 s | 0.90 [0.60, 0.98]; $0.0017; 16 s | 0.90 [0.60, 0.98]; $0.0011; 35 s | 0.70 [0.40, 0.89]; $0.0024; 7 s |
| map | 1.00 [0.72, 1.00]; $0.0041; 29 s | 0.80 [0.49, 0.94]; $0.0024; 22 s | 0.70 [0.40, 0.89]; $0.0059; 178 s | 0.50 [0.24, 0.76]; $0.0051; 11 s |
| scene-3d | 0.90 [0.60, 0.98]; $0.0062; 33 s | 0.50 [0.24, 0.76]; $0.0113; 69 s | 0.70 [0.40, 0.89]; $0.0083; 142 s | 0.50 [0.24, 0.76]; $0.0100; 10 s |
| All 80 | 0.81 [0.71, 0.88]; $0.0050; 28 s | 0.75 [0.65, 0.83]; $0.0038; 23 s | 0.72 [0.62, 0.81]; $0.0051; 94 s | 0.65 [0.54, 0.75]; $0.0082; 12 s |

Mean cost per run by agent, over all four models: code $0.0020, diagram $0.0018, slides $0.0030, map $0.0044, spreadsheet $0.0064, data-analysis $0.0066, scene-3d $0.0090, docx $0.0109. Per model, the 80 runs cost DeepSeek $0.40, GLM $0.31, MiMo $0.41, Nemotron $0.66. Nemotron is the dearest per run: it loops (up to 20 calls, 123k fresh tokens on one data-analysis task) and caches least (64% of input, DeepSeek 86%).

Picks for the router (cheapest within 0.05 pass rate of DeepSeek; fastest by median wall time):

| Agent | Cheapest within 0.05 | Saving vs DeepSeek | Fastest |
|---|---|---:|---|
| code | GLM | 23% | Nemotron |
| spreadsheet | GLM | 26% | GLM (tie with Nemotron, 19 s) |
| data-analysis | GLM | 32% | Nemotron |
| docx | GLM | 58% | Nemotron |
| slides | DeepSeek | 0% | Nemotron |
| diagram | MiMo | 49% | Nemotron |
| map | DeepSeek | 0% | Nemotron |
| scene-3d | DeepSeek | 0% | Nemotron |

- No pick is separated by the intervals. With n = 10 per cell, every Wilson interval overlaps DeepSeek's (the closest: Nemotron on map, 0.50 [0.24, 0.76] against 1.00 [0.72, 1.00]; Nemotron pooled, [0.54, 0.75] against [0.71, 0.88]). Treat the picks as leads to test, not findings.
- DeepSeek has the highest or a tied-highest point pass rate on seven of eight agents and the highest pooled (0.81). The exception is docx, where it is lowest (0.30 against 0.40-0.50). Docx and slides sit at 0.3-0.5 for every model, so those two agents are weak for all four rather than a model choice. Judge scores on docx and slides runs that passed the automatic check average 5.8-6.7.
- GLM is the cheap alternative: 0.75 pooled at $0.0038 per run (24% below DeepSeek), the cheapest model on five agents (code, spreadsheet, data-analysis, docx, map). MiMo is cheapest on slides and diagram, DeepSeek on scene-3d. GLM's scene-3d result (0.50 against 0.90) is the largest gap the picks rule excludes.
- Nemotron has the lowest median wall time on seven agents and ties GLM on spreadsheet (median 12 s pooled against 28 s for DeepSeek) but passes least (0.65) and costs most per run. MiMo is slowest (94 s median).
- Limits: 10 tasks per cell, hand-written or templated tasks, one run per cell at temperature 0, cached-token rate assumed, list-price cost only. The proxy count is authoritative for cost; OpenCode's own cost field reads 0 for these models.

## End-sem router (phase 3, 2026-10-28)

Evaluated by replay of recorded outcomes; no new model calls. Code in `routing/`, outputs in `artifacts/phase3/`.

Memory (`routing/memory.py`, rebuilt 2026-11-01): 4,904 outcome records over 1,200 tasks, each task embedded with BAAI/bge-small-en-v1.5. Sources: `pilot-v1` 1,200 calls, `full-v1` 3,342 scored calls, 362 finished OpenCode agent runs (`agents-v1-smoke1`, `agents-v1-full-20261028`, and the 320 paid runs of `agents-cc-20261031`; 3 smoke runs still wait for the judge). The tables below were rerun on this memory on 2026-11-01: the pilot-6 and agent-selection numbers did not move; the phase 1 (two-model) rows did, because `full-v1` scoring had finished since the first run.

### Agent selection

`agents-v1`, one split stratified by group (train 100, validation 20, test 80, of which 16 overlap tasks). A pick is correct if it is any acceptable agent. CIs are 2,000-resample bootstraps over test tasks.

| Method | Accuracy (95% CI) | Single-label (n=64) | Overlap (n=16) |
|---|---|---:|---:|
| Majority agent (spreadsheet) | 0.20 [0.11, 0.29] | 0.13 | 0.50 |
| Zero-shot Qwen3-0.6B | 0.61 [0.50, 0.72] | 0.59 | 0.69 |
| kNN vote, k=5 (k from validation) | 0.89 [0.81, 0.95] | 0.86 | 1.00 |
| Fine-tuned Qwen3-0.6B (LoRA r=8) | 0.98 [0.94, 1.00] | 0.97 | 1.00 |

- The fine-tuned classifier beats kNN by 0.09 (paired 95% CI [0.03, 0.16]). Trained on Colab T4 in 72 s: 132 examples (each overlap task once per acceptable agent), best validation loss at epoch 1 of 3 (`artifacts/agent-router-v1`). Scoring 8 candidates takes about 0.2 s per task on the T4.
- 6 of kNN's 9 errors are mix-ups between docx, slides, and diagram. 28 of zero-shot Qwen's 31 errors pick data-analysis.
- Agents-v1 tasks come from templates, so near-duplicate prompts sit in train and test. Both kNN and the classifier benefit; treat these as in-distribution numbers.
- The CLI uses the kNN vote because it needs no GPU. Switching to the classifier is a phase 5 choice.

### Model selection by replay

Per task and model: Beta posterior on success from the k nearest past outcomes of that model, prior strength s centred on the model's global pass rate; latency and cost are neighbour means shrunk the same way. Score = P(success) - w_time·latency/L - w_cost·cost/C, with L and C the train medians. Thompson sampling draws P(success) from the posterior.

Protocol, per seed (20 seeds): a collection stream over the train tasks from empty memory, where a strategy sees only its chosen model's outcome and appends it; then an evaluation stream over the test tasks, greedy, still appending. kNN greedy and kNN + Thompson differ only in collection. "Full train memory" starts evaluation with every model's train outcomes. Best single is the model with the highest mean train utility per preference. Regret = oracle utility minus chosen utility.

Tuning on validation only: k and s minimise the Brier score of P(success); each preference weight is the grid value that minimises its target while greedy validation pass rate stays within 0.02 (balanced) or 0.05 (fast, cheap) of accurate.

| Dataset (phase 1 splits) | Test tasks | k | s | Balanced w | Fast w_time | Cheap w_cost |
|---|---:|---:|---:|---:|---:|---:|
| pilot-v1, 6 models | 40 | 20 | 10 | 0.05 | 0.1 | 0.02 |
| Phase 1, DeepSeek + Nemotron | 100 | 3 | 2 | 0.01 | 0.1 | 0 |

Pilot, 6 models (pass rate / regret per task, test, mean over 20 seeds):

| Strategy | Accurate | Balanced | Fast | Cheap | Fast: mean latency (s) |
|---|---|---|---|---|---:|
| Best single | 0.85 / 0.025 | 0.75 / 0.116 | 0.75 / 0.107 | 0.85 / 0.078 | 3.4 |
| Random | 0.75 / 0.125 | 0.75 / 0.378 | 0.75 / 0.393 | 0.75 / 0.176 | 26.5 |
| kNN greedy | 0.83 / 0.048 | 0.77 / 0.185 | 0.79 / 0.146 | 0.80 / 0.118 | 9.7 |
| kNN + Thompson | 0.80 / 0.080 | 0.79 / 0.170 | 0.76 / 0.130 | 0.79 / 0.129 | 6.4 |
| kNN, full train memory | 0.84 / 0.035 | 0.80 / 0.081 | 0.80 / 0.072 | 0.79 / 0.127 | 4.4 |
| Oracle | 0.88 / 0 | 0.88 / 0 | 0.88 / 0 | 0.88 / 0 | 4.8 |

Best single is DeepSeek for accurate and cheap, Nemotron for balanced and fast. Pass-rate CIs span about ±0.12 on 40 tasks.

Phase 1 data, 2 models (accurate, pass / regret per task): best single (DeepSeek) 0.79 / 0.020; kNN greedy 0.777 / 0.033; kNN + Thompson 0.769 / 0.041; full train memory 0.784 / 0.025; random 0.750 / 0.059; oracle 0.81. Validation found no cheap weight that kept pass rate within tolerance, so cheap equals accurate here. For fast the best single is Nemotron (0.70 pass, 12.6 s); kNN greedy gets 0.728 at 16.6 s, the oracle 0.79 at 12.7 s.

Findings:

- No bandit-feedback strategy beats the best single model. kNN greedy has more regret than best single in every pilot preference, with CIs above zero for accurate (+0.022, CI [0.004, 0.044]), balanced, and cheap. On the phase 1 data it is also worse for accurate (+0.013, CI [-0.001, 0.025]) and fast (+0.058, CI [0.018, 0.105]), and the interval touches zero for accurate.
- Thompson sampling does not pay for its exploration. On pilot accurate it collects more regret than greedy (15.5 vs 10.6 over 137 tasks) and ends with lower test pass (0.80 vs 0.83). With 6 models and 137 collection tasks, each model gets about 20 tries.
- With full train memory, kNN beats best single on pilot balanced and fast (regret -0.035, CI [-0.090, 0.002]) at 0.80 vs 0.75 pass and 4.4 s vs 3.4 s mean latency. The CI touches zero. On the phase 1 data it ties best single (accurate +0.005, CI [0.000, 0.017]; balanced -0.018, CI [-0.051, 0.011]; fast +0.006, CI [-0.020, 0.031]), matching the phase 1 finding that learned routers land inside noise.
- Oracle headroom stays large (pilot 0.88 vs 0.85 pass; phase 1 0.81 vs 0.79 pass for accurate). kNN over bge-small embeddings does not find it on these task counts.
- Regret curves for phase 6: `artifacts/phase3/regret-pilot6.csv`, `regret-two-model.csv` (mean and 2.5/97.5 percentiles over seeds, per strategy, preference, and phase).

### End-to-end path (superseded)

The phase 3 path ran on the free OpenCode models and appended recorded outcomes on `--dry-run`. The agent x model router below replaces it: `routing/route.py` now routes over the four paid pool models, `--dry-run` appends nothing, and `--run` goes through the `cc` provider and the host proxy.

## Agent x model router (phase 4, 2026-11-01)

Router for a chosen agent: pass probability per model (Beta prior from the agent-model pair, shrunk towards the k=10 nearest tasks of that agent), wall time, and cost, from the 320 paid runs of `agents-cc-20261031`. Rule (`routing/policy.py`): `accurate` takes the highest pass probability (ties to DeepSeek); `balanced` and `cheap` take the cheapest model whose pass probability is within a tolerance of DeepSeek's; `fast` takes the fastest of those. A model with fewer than 3 past runs on the agent never replaces DeepSeek. Code: `routing/agent_model.py`, `routing/pair_eval.py`, `routing/route.py`; outputs in `artifacts/router/`.

### Honest replay (leave-one-task-out)

Each of the 80 tasks is held out once. Its pick comes from a memory without its own outcome and a tolerance chosen inside the fold: an inner leave-one-task-out over the other 79 tasks picks the tolerance (grid 0 to 1.0) that minimises cost (balanced, cheap) or wall time (fast) while inner pass stays within 0.02 (balanced) or 0.05 (cheap, fast) of always-DeepSeek. The model is chosen given the agent that ran the task. Stochastic strategies (random, Thompson) average 20 seeds per task. Intervals are paired bootstrap CIs over tasks (2,000 resamples) against always-DeepSeek; the wall-time interval is for the difference of medians.

Single models (the same for every preference):

| Strategy | Pass /80 | Pass vs DeepSeek, points [95% CI] | Mean cost (USD x 1e-3) | Cost vs DeepSeek (x 1e-3) [95% CI] | Median wall (s) | Wall vs DeepSeek (s) [95% CI] |
|---|---:|---|---:|---|---:|---|
| Always DeepSeek | 65 | | 4.95 | | 28 | |
| Always GLM | 60 | -6.2 [-16.2, +2.5] | 3.83 | -1.12 [-2.22, -0.04] | 23 | -5.1 [-9.0, -1.2] |
| Always MiMo | 58 | -8.8 [-17.5, +0.0] | 5.10 | +0.15 [-0.99, +1.18] | 94 | +66.1 [+51.8, +89.9] |
| Always Nemotron | 52 | -16.2 [-26.3, -6.2] | 8.21 | +3.26 [+1.68, +5.02] | 12 | -16.6 [-20.8, -13.3] |
| Random | 58.4 | -8.2 [-14.5, -2.6] | 5.52 | +0.57 [-0.18, +1.25] | 39 | +10.2 [+4.4, +19.4] |

Routers, per preference:

| Preference | Strategy | Pass /80 | Pass vs DeepSeek, points [95% CI] | Mean cost (USD x 1e-3) | Cost vs DeepSeek (x 1e-3) [95% CI] | Median wall (s) | Wall vs DeepSeek (s) [95% CI] |
|---|---|---:|---|---:|---|---:|---|
| accurate | per-agent table | 66 | +1.2 [-3.8, +7.5] | 3.94 | -1.01 [-1.94, -0.27] | 28 | +0.0 [+0.0, +0.0] |
| accurate | kNN greedy | 64 | -1.2 [-6.2, +2.5] | 4.19 | -0.76 [-1.47, -0.18] | 28 | -0.5 [-2.9, +0.0] |
| accurate | kNN + Thompson | 61.7 | -4.1 [-9.7, +1.1] | 4.81 | -0.14 [-0.84, +0.44] | 37 | +9.1 [+3.0, +14.7] |
| accurate | oracle | 73 | +10.0 [+3.7, +17.5] | 3.47 | -1.48 [-2.35, -0.89] | 24 | -4.4 [-8.0, +1.3] |
| balanced | per-agent table | 61 | -5.0 [-12.5, +2.5] | 3.35 | -1.60 [-2.52, -0.84] | 27 | -1.5 [-6.2, +1.5] |
| balanced | kNN greedy | 61 | -5.0 [-12.5, +2.5] | 3.35 | -1.60 [-2.52, -0.84] | 27 | -1.5 [-6.2, +1.5] |
| balanced | kNN + Thompson | 61.9 | -3.9 [-10.7, +2.6] | 3.50 | -1.45 [-2.25, -0.81] | 28 | -0.4 [-4.7, +3.0] |
| cheap | per-agent table | 63 | -2.5 [-10.0, +5.0] | 3.09 | -1.86 [-2.80, -1.12] | 29 | +0.8 [-4.9, +5.5] |
| cheap | kNN greedy | 63 | -2.5 [-10.0, +5.0] | 3.09 | -1.86 [-2.80, -1.12] | 29 | +0.8 [-4.9, +5.5] |
| cheap | kNN + Thompson | 63.4 | -2.0 [-9.4, +5.6] | 3.19 | -1.76 [-2.71, -1.03] | 29 | +0.8 [-4.9, +4.7] |
| fast | per-agent table | 59 | -7.5 [-15.0, +0.0] | 5.99 | +1.04 [-0.13, +2.42] | 22 | -6.0 [-10.1, -3.6] |
| fast | kNN greedy | 60 | -6.2 [-13.7, +0.0] | 5.76 | +0.81 [-0.31, +2.20] | 23 | -5.3 [-9.6, -2.4] |
| fast | kNN + Thompson | 63 | -2.5 [-8.3, +2.5] | 5.57 | +0.62 [-0.31, +1.73] | 22 | -6.1 [-9.6, -3.0] |
| balanced, cheap | oracle (cheapest passing) | 73 | +10.0 [+3.7, +17.5] | 3.47 | -1.48 [-2.35, -0.89] | 24 | -4.4 [-8.0, +1.3] |
| fast | oracle (fastest passing) | 73 | +10.0 [+3.7, +17.5] | 5.96 | +1.01 [-0.26, +2.34] | 17 | -10.9 [-15.2, -6.9] |

- Nothing beats always-DeepSeek on pass rate. The best router result is the per-agent table under `accurate` at +1.2 points, and every pass interval contains zero. The router buys cost: `cheap` saves 37% (USD 3.09e-3 against 4.95e-3 per run, CI of the difference excludes zero) for 2.5 points of pass (CI [-10.0, +5.0]); `balanced` saves 32% for 5.0 points. `fast` cuts median wall time by 5 to 6 s (CI excludes zero) for 2.5 to 7.5 points of pass and about USD 0.0006 to 0.001 more per run.
- The per-agent table that scored 67 of 80 at USD 3.5e-3 per run (cheapest within 0.05 of DeepSeek, picked on the same 80 tasks) reproduces in-sample at 67 and USD 3.47e-3. With picks that never saw the scored task it is 61 (balanced) to 63 (cheap) at USD 3.35e-3 to 3.09e-3, against always-DeepSeek's 65 at 4.95e-3. The in-sample number was a selection effect. The pass gain it showed is gone; part of the cost saving stays.
- kNN adds nothing over the per-agent table. With 9 neighbours per agent and similar tasks inside an agent, the kNN estimate is close to the agent's own pass rate, and balanced and cheap picks are identical.
- Thompson sampling at evaluation (a 20-seed average) loses pass on accurate (61.7 against 64 greedy) and wall time for the same reason: random draws from wide Betas. It is a collection policy only.
- Selected tolerances across folds: cheap 0.3 in 80 of 80 folds; balanced 0.1 in 64 of 80; fast 0.02 in 58 and 0.1 in 16; accurate needs none. Tolerances this wide mean the search allows almost any model whose pass rate is not far lower, then lets cost decide.
- Agent choice, leave-one-task-out kNN vote (k=5, 199 labelled tasks): 0.938 on the 80 tasks (75 correct). Errors: diagram-12 to data-analysis, docx-10 to slides, scene-13 to diagram, sheet-12 and sheet-17 to data-analysis. If a wrong agent counts as a failed run, kNN greedy pass falls to 0.71 (balanced), 0.74 (cheap), 0.75 (accurate), 0.70 (fast). The fine-tuned Qwen classifier (0.98 on the phase 3 test split) is not used by the CLI.
- Limits: 80 tasks, 10 per agent, one run per cell; model choice is scored given the agent that ran the task; wall time and cost are single-run values with an assumed cached-token rate; docx, slides, and scene-3d failure rates (0.3-0.5 for every model) cap what any router can win there.

### Online learning (20 seeds)

Per seed the 80 tasks arrive in random order from an empty agent-model memory (priors: single-call rates). The first 60 are the collection stream (Thompson sampling, the memory gets only the chosen model's outcome), the last 20 the evaluation stream (greedy, memory still updated). Regret is against the oracle for the preference: passes lost per task, and excess cost (USD) or wall time (s) over the oracle's pick. Tolerances are the ones fitted on all 80 tasks (balanced 0.1, cheap 0.3, fast 0.1, accurate 0), so the learning curve is slightly optimistic.

| Preference | Lost passes per task, first / last 20 of collection | Slope per task [95% CI over seeds] | Cost per run (USD x 1e-3), first / last 20 | Collection regret, passes / excess | Always-DeepSeek, same stream | Eval pass (20 tasks) |
|---|---|---|---|---|---|---:|
| accurate | 0.200 / 0.183 | -0.0004 [-0.0019, +0.0010] | 5.37 / 5.21 | 10.95 / 0 | 5.7 / 0 | 0.760 |
| balanced | 0.158 / 0.130 | -0.0010 [-0.0021, +0.0001] | 4.88 / 4.13 | 8.35 / USD 0.059 | 5.7 / USD 0.083 | 0.813 |
| cheap | 0.165 / 0.138 | -0.0010 [-0.0021, +0.0003] | 4.77 / 4.25 | 8.80 / USD 0.054 | 5.7 / USD 0.083 | 0.795 |
| fast | 0.198 / 0.170 | -0.0010 [-0.0022, +0.0006] | 6.58 / 6.34 | 11.35 / 137 s | 5.7 / 764 s | 0.733 |

- It learns a little, and not reliably. Later tasks do better than early ones in every preference (balanced and cheap cost per run fall 15% and 11%), but each slope interval includes zero. With 80 tasks over 8 agents and 4 models, the first 20 tasks of a stream give each of the 32 agent-model pairs under one run on average.
- Learning costs passes. During collection the bandit loses 8 to 11 passes against the oracle, where always-DeepSeek loses 5.7, because exploring the cheaper models fails more often. It saves cost against DeepSeek (excess cost USD 0.054 to 0.059 against 0.083) and wall time under `fast` (137 s against 764 s). On 80 tasks the stream does not pay back its lost passes in pass rate.

### Live check (2026-11-01)

Four paid runs through `routing/route.py --run` (cc provider, `agents/cmdproxy.py`, cap USD 0.05 on a ledger of its own): `code-05-mbppplus-18` (cheap, GLM, pass, 11.1 s, USD 0.0014), `code-06-mbppplus-237` (cheap, GLM, pass, 30.0 s, USD 0.0031), `diagram-05-microservices` (cheap, MiMo, pass, 42.0 s, USD 0.0015), `diagram-11-school-er` (fast, GLM, pass, 12.4 s, USD 0.0017). Ledger total USD 0.0077; no weekly-limit error. Each validated result went to `data/memory/online.jsonl`. After the first run, routing `code-06` showed GLM at 11 code runs (was 10) and its pass estimate moved from 0.8813 to 0.8840. A fifth task, `diagram-08-project-gantt`, was routed to data-analysis (vote share 0.26 against docx 0.21); the CLI refused to run a non-gold agent and spent nothing.

## Agent skills smoke check (2026-11-01)

Run `agents-skills-smoke-20261101`: GLM 5.3 Flash, 11 runs with one on-demand skill per agent (`docs/specs/agent-skills.md`), against the same tasks in `agents-cc-20261031`. Spend USD 0.061 of a 0.10 cap. Judge Codex `gpt-6.1-sol`, medium, blind. All 8 agents loaded their skill.

| Task | Check | Judge | Cost | Total tokens |
|---|---|---|---:|---:|
| code-12 | pass, pass | | $0.0014 to $0.0017 | 8.8k to 13.8k |
| sheet-18 | pass, pass | | $0.0021 to $0.0032 | 15.8k to 36.0k |
| analysis-20 | pass, pass | | $0.0020 to $0.0057 | 15.7k to 78.4k |
| diagram-07 | pass, pass | | $0.0016 to $0.0018 | 9.5k to 15.5k |
| map-14 | pass, pass | 7 to 7 | $0.0037 to $0.0034 | 31.2k to 23.7k |
| scene-09 | pass, pass | | $0.0141 to $0.0089 | 173k to 98k |
| scene-04 | fail, pass | | $0.0111 to $0.0058 | 107k to 57k |
| slides-08 | pass, pass | 8 to 7 | $0.0029 to $0.0036 | 17.1k to 28.9k |
| slides-18 | pass, pass | 4 to 2 | $0.0025 to $0.0025 | 15.0k to 16.0k |
| docx-16 | pass, pass | 6 to 5 | $0.0071 to $0.0142 | 59k to 164k |
| docx-10 | pass, pass | 3 to 3 | $0.0085 to $0.0106 | 97k to 102k |

Totals: $0.057 to $0.061 (+7%), 549k to 633k tokens (+15%). The docx and slides judge scores did not improve (three lower, one equal, none higher); the one clear gain is scene-04, whose `ReflectorPlane` blur error passed the validator. Eleven runs at one sample each cannot show a quality gain or loss.


## Live agents use real files (2026-11-02)

Live app runs now follow a real-file contract with Anthropic's `pptx`, `docx`, `xlsx` and `frontend-design` skills (`docs/specs/agent-skills.md`): `out/deck.pptx`, `document.docx`, `workbook.xlsx`, `analysis.xlsx`, and self-contained HTML for diagram, map and 3D. The recorded numbers in this file, including `agents-cc-20261031`, come from the older JSON contracts (`agents/opencode/agent-json`), which still run unchanged. Paid checks on GLM 5.3 Flash, one run per agent through the app (2026-11-02, second round after prompt and sandbox fixes): slides USD 0.020 (274 s, 12 model calls), docx 0.027 (306 s), spreadsheet 0.008 (118 s), data-analysis 0.010 (143 s), diagram 0.018 (307 s), map 0.021 (365 s), 3D scene 0.008 (164 s). Every run passed its file validator and rendered in the panel. The first slides run, before the one-image `ar-look` review tool and the pptxgenjs helper, cost USD 0.043 over 28 calls; the JSON-contract slides agent averaged USD 0.0024 over 25 s. One run each, not measured rates.

## One model per chat from the single-call router (2026-11-02)

Replay on the 80 tasks and 320 runs of `agents-cc-20261031` (`routing/session_eval.py`, `scripts/modal-picks.ts`, `artifacts/router/session.json`). The deployed Modal model router (`outcome-router-4m-v1`, trained on single calls) saw each task text as the first message of its own chat and picked a model per preference; the recorded outcome of that model on that task was looked up. The per-agent table uses the leave-one-task-out numbers above. Pass /80, mean cost USD x 1e-3, median wall seconds; paired 95% CI against always-DeepSeek.

| Preference | Modal router, one model | Pass vs DeepSeek, points [CI] | Cost vs DeepSeek [CI] | Per-agent table |
|---|---|---|---|---|
| accurate | 65 / 4.95 / 28 (always DeepSeek) | 0 | 0 | 66 / 3.94 / 28 |
| balanced | 59 / 6.02 / 25 (DeepSeek 62%, Nemotron 38%) | -13.7 to -2.5 | +0.28 to +2.15 | 61 / 3.35 / 27 |
| fast | 52 / 8.21 / 12 (always Nemotron) | -26.3 to -6.2 | +1.68 to +5.02 | 59 / 5.99 / 22 |
| cheap | 59 / 4.45 / 27 (GLM 65%, DeepSeek 35%) | -15.0 to 0.0 | -1.52 to +0.44 | 63 / 3.09 / 29 |

The single-call router treats Nemotron as the cheap fast model, but in agent runs Nemotron loops and costs the most per run, so `balanced` and `fast` pay more and pass less than always-DeepSeek. The per-agent table, built from agent runs, is better on pass and cost for every preference; only the raw `fast` wall time is lower for the Modal pick. One model per chat from the single-call router does not fit agent runs; the agent x model table is the router for agent calls. 80 tasks, one run per cell.

## More agent-vote tasks (2026-11-02)

The web app sent a deck request ("5 slides on how volcanoes erupt") to the diagram agent: the kNN vote matched the topic, not the output format. I added label-only tasks (5 per agent first, same topics across agents with the format named: deck, Word document, flowchart, workbook, map, 3D model; `benchmarking/suites/agents-routing-v2.jsonl`) to the memory and kept 16 others out as a held-out set (`agents-routing-v2-heldout.jsonl`, 2 per agent, different topics). Memory format and the 4,904 records are unchanged; tasks went from 1,200 to 1,240. The first web test of a docx request (immune system, Word document) still went to slides because my training tasks paired slides with that topic but docx with others, so I added 10 more docx tasks on the same class topics (50 label-only tasks in all; tasks 1,250). Held-out vote: 13 of 16 before, 15 after the first 40, 16 after the 50; the volcano deck prompts went from diagram (0.39) to slides (0.70 and 0.72). 16 tasks, one split, written by the same author as the training tasks, so read it as a check that the failure is fixed, not as a new accuracy figure.
