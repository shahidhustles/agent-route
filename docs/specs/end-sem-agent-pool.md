# End-sem agent router

## Goal

For each user task, pick an agent and the model it runs on. Agents differ in what they produce (code, spreadsheets, documents, slides, diagrams, maps, 3D scenes). Models differ in speed, accuracy, and token use. The router learns both choices by watching runs: every finished run becomes a memory entry, and new tasks are routed from how agents and models did on similar past tasks.

The model router (`training/outcome_*`) handles single calls. This router sits in front of it.

## Agents

The eight agents and their output contracts are listed in `docs/plan.md`, phase 2. Each is an OpenCode custom agent (prompt, tools, output contract) run headless with `opencode run --agent <agent> -m <model>` in a sandboxed scratch workspace. One harness for every agent keeps the comparison about agent and model choice. Output contracts match the `ai-components` UI blocks, so the phase 5 UI renders agent output unchanged.

## Tasks

About 20 tasks per agent, plus overlap tasks that two or more agents could complete ("chart last quarter's sales": spreadsheet, data-analysis, or code). Every task carries a gold agent label and an automatic check from `docs/plan.md`. Open-ended outputs (docx, slides, maps) add a judge rubric scored by Codex.

## Memory

One record per run: `task_id`, `embedding` (BAAI/bge-small-en-v1.5 over the task text), `agent`, `model`, `passed`, `wall_s`, `input_tokens`, `output_tokens`, `cost_usd`.

## Routing

1. Embed the task; retrieve the k most similar past tasks (k = 10, cosine).
2. Agent: similarity-weighted vote over the neighbours' successful agents. A fine-tuned Qwen classifier is the comparison.
3. Model: for the chosen agent, estimate each model's success probability from that agent's nearest past tasks, smoothed by a Beta prior from the agent-model pair's own pass rate (a pair with no runs borrows the model's pooled rate); estimate wall time and cost the same way.
4. Choose by preference with a tolerance rule instead of a weighted score: `accurate` takes the highest pass probability (ties to DeepSeek); `balanced` and `cheap` take the cheapest model whose pass probability is within a tolerance of DeepSeek's; `fast` takes the fastest of those. The tolerance is fitted by leave-one-task-out on the recorded runs (`routing/pair_eval.py fit`). A model with fewer than 3 runs on the agent never replaces DeepSeek. The weighted score of the first design suited single calls, where every model had hundreds of outcomes; with 10 runs per cell a tolerance is easier to fit and to explain.
5. Explore by Thompson sampling from the Beta posteriors while collecting data; act greedily at evaluation.
6. Append each finished, validated run to `data/memory/online.jsonl`, so routing improves online. `--dry-run` appends nothing.

`routing/route.py` returns the agent, model, confidence, runner-up, per-model estimates, and a reasoning string for all four preferences; its docstring is the contract for the Next.js route.

## Evaluation

Agent choice is scored against the gold agent labels of the `agents-v1` tasks; an overlap task counts as correct for any acceptable agent. Model choice is scored on recorded single-call outcomes (`pilot-v1`: 200 tasks x 6 models; phase 1: 501 tasks x 2 models). Strategies see the tasks once in a fixed order, and outcomes are looked up from the records, so every strategy is compared on the same outcomes. Strategies: best single model, random, kNN greedy, kNN with Thompson sampling, oracle. Report success rate, latency, cost, agent-selection accuracy, and cumulative regret against the oracle, per preference. Agent x model outcomes come from `agents-cc-20261031` (80 tasks x 4 models). Model choice there is scored by leave-one-task-out replay with the tolerance chosen inside each fold, against always-DeepSeek, each single model, random, a per-agent table, and the oracle, with paired bootstrap CIs; an online stream from empty memory (20 seeds) measures learning.

## Models

DeepSeek V4.1 Flash (the default and reference), GLM-5.3 Flash, MiMo V2.6 Flash, and Nemotron 3.5 Super VL, called through the Command Code provider API. Agents reach them as the `cc` provider in `agents/opencode/opencode.json`, through the host proxy `agents/cmdproxy.py`, which holds the key and enforces a spend cap and the weekly limit.

## Out of scope

Browser control, agent-to-agent hand-offs, multi-agent collaboration, learned embedding models.
