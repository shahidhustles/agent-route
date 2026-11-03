"""Route one task to an agent and a model, optionally run it, and append the outcome to memory.

    .venv/bin/python routing/route.py --text "Draw the login flow as a sequence diagram" --dry-run --json
    .venv/bin/python routing/route.py --task-id diagram-03-ci-pipeline --preference cheap --dry-run
    .venv/bin/python routing/route.py --task-id code-05-mbppplus-18 --preference cheap --run --max-usd 0.05

Flow: embed the task, retrieve the k nearest agents-v1 tasks, vote for the agent (kNN, k from
artifacts/phase3/agent-selection.json), then for that agent estimate each of the four pool models from its past
runs: pass probability (Beta prior from the agent-model pair's pass rate, shrunk towards similarity-weighted
neighbours), wall time and cost. The preference decides (routing/policy.py choose_by_tolerance):

- accurate: the highest pass probability (ties go to DeepSeek);
- balanced, cheap: among models whose pass probability is within the tolerance of DeepSeek's, the cheapest;
- fast: among the same models, the fastest.

Tolerances come from artifacts/router/params.json (`pair_eval.py fit`, leave-one-task-out on every recorded run).
A model with fewer than MIN_RUNS past runs for the agent is never picked over DeepSeek, so thin evidence keeps
the default. DeepSeek V4.1 Flash is the reference. The default preference is `accurate`, which picked DeepSeek
for 80% of tasks in the leave-one-task-out replay; balanced and cheap are opt-in (docs/paper/results.md).

--dry-run routes and prints the command that would run; it appends nothing. --run launches the OpenCode agent
through agents/run.py with the `cc` provider and the host proxy agents/cmdproxy.py, which holds the API key and
stops at --max-usd (a ledger of its own, so the cap covers these live runs only) or at a weekly usage limit.
Suite tasks only: the validators need the task's checks. The validated result is appended to --online-memory.

UI contract (Next.js server route): call the CLI with --json, or import and call `route_task`. Both return

    {
      "task": {"id": str | null, "text": str},
      "preference": "accurate" | "balanced" | "fast" | "cheap",
      "agent": str,                      # chosen agent
      "model": str,                      # chosen model ID, e.g. "z-ai/glm-5.3-flash"
      "confidence": {"agent": float,     # kNN vote share of the chosen agent, 0-1
                     "model": float},    # estimated pass probability of the chosen model on this agent, 0-1
      "runner_up": {"agent": {"agent": str, "share": float} | null,
                    "model": {"model": str, "p_pass": float, "wall_s": float, "cost_usd": float} | null},
      "estimates": [{"model", "p_pass", "wall_s", "cost_usd", "runs_seen", "eligible", "chosen"}],  # best first
      "reasoning": str,                  # one paragraph the UI can show
      "decisions": {preference: <the same fields without task/decisions>},   # all four preferences
      "command": [str] | null,           # agents/run.py argv for a suite task
      "run": null | {"status": "passed" | "failed" | "stopped" | "no_record", "passed": bool | null,
                     "wall_s": float, "cost_usd": float, "detail": str, "appended": bool}
    }

Costs are USD at list price, wall time in seconds. A server route should treat `run.status == "stopped"` as a
provider limit (no record is written) and keep the routing decision. Routing takes about 3 s per call, almost all
of it loading the embedding model and memory; keep a process warm if latency matters.
"""
import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'agents'))
from agent_model import MODELS, PARAMS, SHORT, PairTable, chat_priors  # noqa: E402
from memory import AGENT_SUITE, Embedder, Memory, agent_records, read_jsonl  # noqa: E402
from policy import PREFERENCES, REFERENCE, agent_vote, choose_by_tolerance  # noqa: E402

AGENT_EVAL = ROOT / 'artifacts' / 'phase3' / 'agent-selection.json'
ROUTER_PARAMS = ROOT / 'artifacts' / 'router' / 'params.json'
ONLINE = ROOT / 'data' / 'memory' / 'online.jsonl'
LIVE_RUN_DIR = ROOT / 'benchmarking' / 'results' / 'agents-live-cc'
LIVE_LEDGER = ROOT / 'benchmarking' / 'results' / 'agents-live-cc-ledger.jsonl'
DEFAULT_TOLERANCE = {'accurate': 0.0, 'balanced': 0.1, 'fast': 0.1, 'cheap': 0.3}
MIN_RUNS = 3
STOP_MARKERS = ('weekly usage limit', 'SPEND_CAP_REACHED')


def load_tolerance():
    if ROUTER_PARAMS.exists():
        return {**DEFAULT_TOLERANCE, **json.loads(ROUTER_PARAMS.read_text())['tolerance']}
    return dict(DEFAULT_TOLERANCE)


def vote_agents(mem, vector, task_id=None):
    labelled = [t for t in mem.tasks.values() if t.get('agents') and t['task_id'] != task_id]
    vecs = np.stack([mem.vectors[t['task_id']] for t in labelled])
    k = json.loads(AGENT_EVAL.read_text())['k'] if AGENT_EVAL.exists() else 10
    return agent_vote(vector, vecs, [t['agents'] for t in labelled], k)


def build_table(mem, task_id=None):
    """Agent x model memory from every finished agent run of the four models (the routed task's own runs excluded)."""
    table = PairTable(chat_priors(mem))
    for r in mem.records:
        if r['agent'] != 'chat' and r['model'] in MODELS and r['passed'] is not None and r['task_id'] != task_id \
                and r['task_id'] in mem.vectors:
            table.add(mem.vectors[r['task_id']], r['agent'], r['model'], r['passed'], r['latency_s'], r['cost_usd'])
    return table


def explain(preference, agent, agents, ranked, tolerance, ref_p):
    a = f'{agent} (vote share {agents[0][1]:.2f}' + (f', runner-up {agents[1][0]} {agents[1][1]:.2f})' if len(agents) > 1 else ')')
    top = ranked[0]
    name = lambda m: SHORT[m['model']]
    if preference == 'accurate':
        return (f'Agent {a}. Accurate takes the highest estimated pass probability: {name(top)} at {top["p_pass"]:.2f} '
                f'(DeepSeek {ref_p:.2f}).')
    ok = [m for m in ranked if m['eligible']]
    rest = ', '.join(f'{name(m)} {m["p_pass"]:.2f}' for m in ok) or 'none'
    target = 'fastest' if preference == 'fast' else 'cheapest'
    unit = f'{top["wall_s"]:.0f} s' if preference == 'fast' else f'USD {top["cost_usd"]:.4f} per run'
    thin = [name(m) for m in ranked if not m['eligible'] and m['p_pass'] >= ref_p - tolerance and m['runs_seen'] < MIN_RUNS]
    note = f' {", ".join(thin)} lack {MIN_RUNS}+ runs on this agent, so they were not considered.' if thin else ''
    return (f'Agent {a}. {preference.capitalize()} accepts models within {tolerance:.2f} of DeepSeek\'s estimated pass '
            f'probability ({ref_p:.2f}): {rest}. Picked {name(top)}, the {target} of them at {unit}.{note}')


def decide(table, vector, agents, preference, tolerance):
    agent = agents[0][0]
    est = table.estimates(vector, agent)
    seen = {m: table.count(agent, m) for m in MODELS}
    considered = [m for m in MODELS if m == REFERENCE or seen[m] >= MIN_RUNS]
    _, ranked = choose_by_tolerance({m: est[m] for m in considered}, preference, tolerance, considered)
    for m in MODELS:
        if m not in considered:
            ranked.append({'model': m, 'p_pass': est[m].p_success, 'eligible': False, 'wall_s': est[m].latency_s,
                           'cost_usd': est[m].cost_usd, 'neighbours': est[m].neighbours})
    rows = [{'model': r['model'], 'p_pass': round(r['p_pass'], 4), 'wall_s': round(r['wall_s'], 2),
             'cost_usd': round(r['cost_usd'], 6), 'runs_seen': seen[r['model']], 'eligible': r['eligible'],
             'chosen': i == 0} for i, r in enumerate(ranked)]
    top, second = rows[0], rows[1] if len(rows) > 1 else None
    ru = agents[1] if len(agents) > 1 else None
    return {'preference': preference, 'agent': agent, 'model': top['model'],
            'confidence': {'agent': round(agents[0][1], 4), 'model': top['p_pass']},
            'runner_up': {'agent': {'agent': ru[0], 'share': round(ru[1], 4)} if ru else None,
                          'model': {k: second[k] for k in ('model', 'p_pass', 'wall_s', 'cost_usd')} if second else None},
            'tolerance': tolerance, 'estimates': rows,
            'reasoning': explain(preference, agent, agents, rows, tolerance, est[REFERENCE].p_success)}


def run_command(task_id, agent, model, max_usd):
    return [sys.executable, str(ROOT / 'agents' / 'run.py'), '--suite', str(AGENT_SUITE), '--run-dir', str(LIVE_RUN_DIR),
            '--models', f'cc/{model}', '--tasks', task_id, '--agents', agent, '--concurrency', '1',
            '--max-usd', str(max_usd), '--ledger', str(LIVE_LEDGER)]


def live_run(mem, task, d, max_usd, online, vector):
    """Run the chosen agent on the chosen model, validate, append. Returns the `run` block."""
    cmd = run_command(task['id'], d['agent'], d['model'], max_usd)
    key = (task['id'], d['agent'], f'cc/{d["model"]}')
    runs_path = LIVE_RUN_DIR / 'runs.jsonl'
    if runs_path.exists() and any((r['task_id'], r['agent'], r['model']) == key for r in read_jsonl(runs_path)):
        return {'status': 'no_record', 'passed': None, 'wall_s': 0.0, 'cost_usd': 0.0, 'appended': False,
                'detail': 'this task, agent, and model already ran in the live run directory; nothing run'}
    stopped = None
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        print('  | ' + line.rstrip(), file=sys.stderr, flush=True)
        stopped = stopped or next((m for m in STOP_MARKERS if m in line), None)
    proc.wait()
    fresh = [r for r in (read_jsonl(runs_path) if runs_path.exists() else [])
             if (r['task_id'], r['agent'], r['model']) == key and not r.get('not_run')]
    if not fresh:
        return {'status': 'stopped' if stopped else 'no_record', 'passed': None, 'wall_s': 0.0, 'cost_usd': 0.0,
                'appended': False, 'detail': f'no record written ({stopped or "run failed"})'}
    raw = fresh[-1]
    rec = agent_records(LIVE_RUN_DIR, {task['id']: task})
    rec = [r for r in rec if r['agent'] == d['agent'] and r['model'] == d['model']][-1]
    rec['run'] = 'live-cc'
    mem.append_online(online, rec, mem.tasks.get(task['id']), vector)
    return {'status': 'passed' if rec['passed'] else 'failed', 'passed': bool(rec['passed']), 'wall_s': rec['latency_s'],
            'cost_usd': rec['cost_usd'], 'detail': raw['validator']['detail'], 'appended': True}


def route_task(text=None, task_id=None, preference='accurate', run=False, max_usd=0.05, online=ONLINE, mem=None,
               embedder=None):
    """Route one task. `task_id` names an agents-v1 task; otherwise `text` is embedded. Returns the contract dict."""
    mem = mem or Memory.load(online=online)
    task = None
    if task_id:
        task = {t['id']: t for t in read_jsonl(AGENT_SUITE)}[task_id]
        text, vector = task['prompt'], mem.vectors[task_id]
    else:
        vector = (embedder or Embedder()).encode([text])[0]
    agents = vote_agents(mem, vector, task_id)
    table = build_table(mem, task_id)
    tol = load_tolerance()
    decisions = {p: decide(table, vector, agents, p, tol[p]) for p in PREFERENCES}
    out = {'task': {'id': task_id, 'text': text}, **decisions[preference],
           'decisions': {p: d for p, d in decisions.items()}, 'command': None, 'run': None}
    d = decisions[preference]
    if task is not None and d['agent'] in task['agents']:
        out['command'] = [str(pathlib.Path(c).relative_to(ROOT)) if c.startswith(str(ROOT)) else c
                          for c in run_command(task_id, d['agent'], d['model'], max_usd)]
    if run:
        if task is None:
            out['run'] = {'status': 'no_record', 'passed': None, 'wall_s': 0.0, 'cost_usd': 0.0, 'appended': False,
                          'detail': 'running needs a suite task (--task-id): the validators read its checks'}
        elif d['agent'] not in task['agents']:
            out['run'] = {'status': 'no_record', 'passed': None, 'wall_s': 0.0, 'cost_usd': 0.0, 'appended': False,
                          'detail': f'{d["agent"]} is not an acceptable agent for {task_id} (gold {task["agents"]})'}
        else:
            out['run'] = live_run(mem, task, d, max_usd, online, vector)
    return out


def print_decision(out):
    print(f'Task: {out["task"]["text"][:120]!r}{"..." if len(out["task"]["text"]) > 120 else ""}')
    for p, d in out['decisions'].items():
        ru = d['runner_up']
        print(f'\n[{p}] agent {d["agent"]} (share {d["confidence"]["agent"]:.2f}, runner-up '
              f'{ru["agent"]["agent"] + " " + format(ru["agent"]["share"], ".2f") if ru["agent"] else "none"}); '
              f'model {SHORT[d["model"]]} (P(pass) {d["confidence"]["model"]:.2f}, runner-up '
              f'{SHORT[ru["model"]["model"]] + " " + format(ru["model"]["p_pass"], ".2f") if ru["model"] else "none"})')
        print('  ' + d['reasoning'])
    d = out['decisions'][out['preference']]
    print(f'\nSelected preference: {out["preference"]}')
    print('\n| Model | P(pass) | Est. wall (s) | Est. cost (USD) | Past runs | Eligible |')
    print('|---|---:|---:|---:|---:|---|')
    for m in d['estimates']:
        print(f'| {SHORT[m["model"]]}{" *" if m["chosen"] else ""} | {m["p_pass"]:.2f} | {m["wall_s"]:.0f} | '
              f'{m["cost_usd"]:.5f} | {m["runs_seen"]} | {"yes" if m["eligible"] else "no"} |')
    if out['command']:
        print('\nCommand:', ' '.join(['.venv/bin/python'] + out['command'][1:]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--task-id', help='an agents-v1 task')
    src.add_argument('--text', help='free-text task (routing only)')
    parser.add_argument('--preference', choices=PREFERENCES, default='accurate')
    act = parser.add_mutually_exclusive_group()
    act.add_argument('--dry-run', action='store_true', help='route and print the command; run and append nothing')
    act.add_argument('--run', action='store_true')
    parser.add_argument('--max-usd', type=float, default=0.05, help='proxy spend cap for --run')
    parser.add_argument('--online-memory', type=pathlib.Path, default=ONLINE)
    parser.add_argument('--json', action='store_true', help='print the decision as JSON')
    args = parser.parse_args(argv)
    out = route_task(args.text, args.task_id, args.preference, args.run, args.max_usd, args.online_memory)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print_decision(out)
        if out['run']:
            r = out['run']
            print(f'\nRun: {r["status"]} ({r["detail"]}); wall {r["wall_s"]:.1f} s, cost USD {r["cost_usd"]:.4f}'
                  + (f'; appended to {args.online_memory}' if r['appended'] else ''))
    return out


if __name__ == '__main__':
    main()
