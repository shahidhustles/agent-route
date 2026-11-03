"""Honest evaluation of agent x model routing on `agents-cc-20261031` (80 tasks x 4 models, each task run by its agent).

    .venv/bin/python routing/pair_eval.py loto      # leave-one-task-out replay, writes artifacts/router/loto.json
    .venv/bin/python routing/pair_eval.py online    # bandit stream from empty memory, writes artifacts/router/online.json
    .venv/bin/python routing/pair_eval.py fit       # tolerance per preference on all recorded runs, writes params.json

loto: every task is held out once. Its pick comes from a memory and a tolerance that never saw its outcome: the
tolerance is chosen inside the fold by an inner leave-one-task-out over the other 79 tasks. The model is chosen
given the agent that ran the task, so agent mistakes are scored separately (agent_eval below). Stochastic
strategies (random, Thompson) average 20 seeds per task. CIs are paired bootstraps over tasks against
always-DeepSeek (2,000 resamples).

online: per seed the 80 tasks arrive in random order from an empty agent-model memory. The first 60 are the
collection stream (Thompson sampling, memory updated with the chosen model's outcome only), the last 20 the
evaluation stream (greedy, memory still updated). Regret is measured against the oracle for the preference.
"""
import argparse
import json
import pathlib
import random
import statistics
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from agent_model import (MODELS, PREFERENCES, SHORT, ESTIMATORS, PairTable, chat_priors, load_grid,  # noqa: E402
                         select_tolerance)
from memory import Memory  # noqa: E402
from policy import REFERENCE, agent_vote, choose_by_tolerance, loto_splits  # noqa: E402

OUT = ROOT / 'artifacts' / 'router'
SEEDS = 20
COLLECT = 60


def oracle_pick(grid, task, preference):
    """Best model in hindsight: accurate takes any passing model (cheapest), cheap and balanced the cheapest
    passing model, fast the fastest passing model. With no passing model the reference model."""
    o = grid.outcomes[task]
    passing = [m for m in MODELS if o[m][0] > 0]
    if not passing:
        return REFERENCE
    key = 1 if preference == 'fast' else 2
    return min(passing, key=lambda m: (o[m][key], MODELS.index(m)))


def bootstrap(values, stat=np.mean, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    v = np.asarray(values, float)
    idx = rng.integers(0, len(v), (n, len(v)))
    s = np.sort([stat(v[i]) for i in idx])
    return [float(s[int(0.025 * n)]), float(s[int(0.975 * n) - 1])]


def paired_ci(a, b, stat=np.mean, n=2000, seed=0):
    """Bootstrap CI of stat(a) - stat(b) over resampled tasks."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    idx = rng.integers(0, len(a), (n, len(a)))
    d = np.sort([stat(a[i]) - stat(b[i]) for i in idx])
    return [float(d[int(0.025 * n)]), float(d[int(0.975 * n) - 1])]


def loto_picks(grid, priors=None, seeds=SEEDS):
    """Per strategy and preference: task -> list of picks (one per seed; deterministic strategies have one)."""
    ids = grid.ids
    picks = {}
    folds = {}
    for held, train in loto_splits(ids):
        folds[held] = {'train': train,
                       'knn': select_tolerance(grid, train, 'knn', priors)[0],
                       'table': select_tolerance(grid, train, 'table', priors)[0]}
    for held in ids:
        f = folds[held]
        est = {name: ESTIMATORS[name](grid, f['train'], held, priors) for name in ESTIMATORS}
        for pref in PREFERENCES:
            for strategy, name, mode in (('per_agent_table', 'table', 'greedy'), ('knn_greedy', 'knn', 'greedy'),
                                         ('knn_thompson', 'knn', 'thompson')):
                if mode == 'greedy':
                    chosen = [choose_by_tolerance(est[name], pref, f[name][pref], MODELS)[0]]
                else:
                    chosen = [choose_by_tolerance(est[name], pref, f[name][pref], MODELS, 'thompson',
                                                  np.random.default_rng(1000 * s + ids.index(held)))[0]
                              for s in range(seeds)]
                picks.setdefault((strategy, pref), {})[held] = chosen
            picks.setdefault(('oracle', pref), {})[held] = [oracle_pick(grid, held, pref)]
            rng = random.Random(ids.index(held))
            picks.setdefault(('random', pref), {})[held] = [rng.choice(MODELS) for _ in range(seeds)]
    return picks, folds


def per_task_values(grid, pick_lists, ids):
    """Mean over seeds of (passed, wall, cost) for each task."""
    out = []
    for t in ids:
        rows = [grid.outcomes[t][m] for m in pick_lists[t]]
        out.append([statistics.mean(r[i] for r in rows) for i in range(3)])
    return np.array(out)


def agent_eval(mem, grid):
    """Leave-one-task-out agent accuracy of the kNN vote over all other agents-v1 tasks with gold labels."""
    labelled = [t for t in mem.tasks.values() if t.get('agents')]
    vecs = np.stack([mem.vectors[t['task_id']] for t in labelled])
    ids = [t['task_id'] for t in labelled]
    ok, wrong = {}, []
    for t in grid.ids:
        i = ids.index(t)
        keep = [j for j in range(len(ids)) if j != i]
        ranked = agent_vote(mem.vectors[t], vecs[keep], [labelled[j]['agents'] for j in keep], 5)
        ok[t] = ranked[0][0] in labelled[i]['agents']
        if not ok[t]:
            wrong.append((t, ranked[0][0]))
    return ok, wrong


def loto(mem=None, seeds=SEEDS):
    mem = mem or Memory.load()
    grid = load_grid(mem)
    priors = chat_priors(mem)
    ids = grid.ids
    picks, folds = loto_picks(grid, priors, seeds)
    ds_vals = per_task_values(grid, {t: [REFERENCE] for t in ids}, ids)
    result = {'tasks': len(ids), 'seeds': seeds, 'preferences': {}}
    for pref in PREFERENCES:
        strategies = {'always_deepseek': {t: [REFERENCE] for t in ids}}
        for m in MODELS[1:]:
            strategies[f'always_{SHORT[m].lower()}'] = {t: [m] for t in ids}
        for s in ('random', 'per_agent_table', 'knn_greedy', 'knn_thompson', 'oracle'):
            strategies[s] = picks[(s, pref)]
        rows = {}
        for name, pl in strategies.items():
            v = per_task_values(grid, pl, ids)
            row = {'pass': float(v[:, 0].mean()), 'passed_of_80': float(v[:, 0].sum()),
                   'mean_cost_usd': float(v[:, 2].mean()), 'median_wall_s': float(np.median(v[:, 1])),
                   'mean_wall_s': float(v[:, 1].mean())}
            if name != 'always_deepseek':
                row['pass_vs_deepseek_ci95'] = paired_ci(v[:, 0], ds_vals[:, 0])
                row['cost_vs_deepseek_ci95'] = paired_ci(v[:, 2], ds_vals[:, 2])
                row['median_wall_vs_deepseek_ci95'] = paired_ci(v[:, 1], ds_vals[:, 1], np.median)
                row['pass_vs_deepseek'] = row['pass'] - float(ds_vals[:, 0].mean())
                row['cost_vs_deepseek'] = row['mean_cost_usd'] - float(ds_vals[:, 2].mean())
                row['median_wall_vs_deepseek'] = row['median_wall_s'] - float(np.median(ds_vals[:, 1]))
            if name in ('per_agent_table', 'knn_greedy', 'knn_thompson'):
                share = {}
                for t in ids:
                    for m in pl[t]:
                        share[SHORT[m]] = share.get(SHORT[m], 0) + 1 / len(pl[t])
                row['model_share'] = {k: round(v_ / len(ids), 3) for k, v_ in sorted(share.items(), key=lambda x: -x[1])}
            rows[name] = row
        result['preferences'][pref] = rows
    tol = {name: {pref: [folds[t][name][pref] for t in ids] for pref in PREFERENCES} for name in ('knn', 'table')}
    result['tolerance_per_fold'] = {name: {pref: {str(x): v.count(x) for x in sorted(set(v))}
                                           for pref, v in d.items()} for name, d in tol.items()}
    ok, wrong = agent_eval(mem, grid)
    result['agent_vote_accuracy'] = sum(ok.values()) / len(ids)
    result['agent_vote_errors'] = wrong
    # In-sample per-agent table (the flattering number): picks from all 80 tasks, scored on the same 80.
    insample = {}
    for pref in PREFERENCES:
        # The table is built from all 80 tasks, the scored task included.
        picks_in = {t: [choose_by_tolerance(ESTIMATORS['table'](grid, ids, t, priors), pref, 0.05, MODELS)[0]]
                    for t in ids}
        v = per_task_values(grid, picks_in, ids)
        insample[pref] = {'passed_of_80': float(v[:, 0].sum()), 'mean_cost_usd': float(v[:, 2].mean()),
                          'median_wall_s': float(np.median(v[:, 1]))}
    result['in_sample_table_tol_0.05'] = insample
    # Agent errors: a wrong agent cannot produce the task's artifact, so count it as a failed run (lower bound).
    for pref in PREFERENCES:
        for name in ('knn_greedy',):
            v = per_task_values(grid, picks[(name, pref)], ids)
            joint = [v[i, 0] if ok[t] else 0.0 for i, t in enumerate(ids)]
            result['preferences'][pref][name]['pass_with_agent_errors_lower_bound'] = float(np.mean(joint))
    return result


# --- online learning ---------------------------------------------------------------------------------------

def regret_parts(grid, task, pref, model):
    """Lost pass and excess target (USD or seconds) against the oracle's pick."""
    o = grid.outcomes
    best = oracle_pick(grid, task, pref)
    lost = o[task][best][0] - o[task][model][0]
    key = 1 if pref == 'fast' else 2
    excess = o[task][model][key] - o[task][best][key] if pref != 'accurate' else 0.0
    return lost, excess


def online_stream(grid, priors, pref, tolerance, seed, mode='thompson'):
    rng = np.random.default_rng(seed)
    order = grid.ids[:]
    random.Random(seed).shuffle(order)
    table = PairTable(priors)
    logs = []
    for step, t in enumerate(order):
        phase = 'collect' if step < COLLECT else 'eval'
        est = table.estimates(grid.vectors[t], grid.agent[t])
        use = 'thompson' if (mode == 'thompson' and phase == 'collect') else 'greedy'
        m = choose_by_tolerance(est, pref, tolerance, MODELS, use, rng)[0]
        passed, wall, cost = grid.outcomes[t][m]
        table.add(grid.vectors[t], grid.agent[t], m, passed, wall, cost)
        lost, excess = regret_parts(grid, t, pref, m)
        logs.append({'step': step, 'phase': phase, 'task': t, 'model': m, 'passed': passed, 'cost': cost,
                     'wall': wall, 'lost_pass': lost, 'excess': excess})
    return logs


def online(mem=None, seeds=SEEDS):
    mem = mem or Memory.load()
    grid = load_grid(mem)
    priors = chat_priors(mem)
    tolerances, _ = select_tolerance(grid, grid.ids, 'knn', priors)
    ids = grid.ids
    oracle_pass = np.mean([max(o[0] for o in grid.outcomes[t].values()) for t in ids])
    result = {'tolerance': tolerances, 'seeds': seeds, 'collect_tasks': COLLECT, 'eval_tasks': len(ids) - COLLECT,
              'oracle_pass': float(oracle_pass), 'preferences': {}}
    curves = {}
    for pref in PREFERENCES:
        runs = {mode: [online_stream(grid, priors, pref, tolerances[pref], s, mode) for s in range(seeds)]
                for mode in ('thompson', 'greedy')}
        res = {}
        for mode, streams in runs.items():
            lost = np.array([[l['lost_pass'] for l in s] for s in streams])
            excess = np.array([[l['excess'] for l in s] for s in streams])
            passed = np.array([[l['passed'] for l in s] for s in streams])
            cost = np.array([[l['cost'] for l in s] for s in streams])
            wall = np.array([[l['wall'] for l in s] for s in streams])
            third = COLLECT // 3
            slope = [float(np.polyfit(np.arange(COLLECT), lost[i, :COLLECT], 1)[0]) for i in range(seeds)]
            res[mode] = {
                'collect_cum_lost_pass': float(lost[:, :COLLECT].sum(axis=1).mean()),
                'collect_cum_excess': float(excess[:, :COLLECT].sum(axis=1).mean()),
                'lost_pass_per_task_first_third': float(lost[:, :third].mean()),
                'lost_pass_per_task_last_third': float(lost[:, COLLECT - third:COLLECT].mean()),
                'excess_per_task_first_third': float(excess[:, :third].mean()),
                'excess_per_task_last_third': float(excess[:, COLLECT - third:COLLECT].mean()),
                'pass_first_third': float(passed[:, :third].mean()), 'pass_last_third': float(passed[:, COLLECT - third:COLLECT].mean()),
                'cost_first_third': float(cost[:, :third].mean()), 'cost_last_third': float(cost[:, COLLECT - third:COLLECT].mean()),
                'lost_pass_slope_per_task': float(np.mean(slope)),
                'lost_pass_slope_ci95': bootstrap(slope),
                'eval_pass': float(passed[:, COLLECT:].mean()), 'eval_cost_usd': float(cost[:, COLLECT:].mean()),
                'eval_median_wall_s': float(np.median(wall[:, COLLECT:])),
                'eval_lost_pass_per_task': float(lost[:, COLLECT:].mean()),
                'eval_excess_per_task': float(excess[:, COLLECT:].mean()),
            }
            if mode == 'thompson':
                curves[pref] = {'cum_lost_pass': np.cumsum(lost, axis=1).mean(axis=0).round(3).tolist(),
                                'cum_excess': np.cumsum(excess, axis=1).mean(axis=0).round(6).tolist()}
        # Fixed policy reference: the same rule with the final deployed memory is the LOTO number; here compare
        # with always-DeepSeek and random on the same eval-position tasks.
        ds_lost = []
        for s in range(seeds):
            order = grid.ids[:]
            random.Random(s).shuffle(order)
            ds_lost.append([regret_parts(grid, t, pref, REFERENCE) + (grid.outcomes[t][REFERENCE][0],
                                                                       grid.outcomes[t][REFERENCE][2]) for t in order])
        ds = np.array(ds_lost)
        res['always_deepseek'] = {'collect_cum_lost_pass': float(ds[:, :COLLECT, 0].sum(axis=1).mean()),
                                  'collect_cum_excess': float(ds[:, :COLLECT, 1].sum(axis=1).mean()),
                                  'eval_pass': float(ds[:, COLLECT:, 2].mean()),
                                  'eval_cost_usd': float(ds[:, COLLECT:, 3].mean())}
        result['preferences'][pref] = res
    result['curves'] = curves
    return result


def fit(mem=None):
    mem = mem or Memory.load()
    grid = load_grid(mem)
    tol, detail = select_tolerance(grid, grid.ids, 'knn', chat_priors(mem))
    return {'tolerance': tol, 'tasks': len(grid.ids), 'always_deepseek_pass': detail['always_deepseek_pass'],
            'search': detail['search'], 'slack': {'balanced': 0.02, 'cheap': 0.05, 'fast': 0.05}}


def print_loto(res):
    print(f'agent vote accuracy (LOTO kNN, k=5): {res["agent_vote_accuracy"]:.3f}; errors {res["agent_vote_errors"]}')
    for pref, rows in res['preferences'].items():
        print(f'\n{pref}\n')
        print('| Strategy | Pass /80 | Pass vs DeepSeek [95% CI] | Cost USD | Cost vs DeepSeek [CI] | Median wall s | Wall vs DeepSeek [CI] |')
        print('|---|---:|---|---:|---|---:|---|')
        for name, r in rows.items():
            if 'pass_vs_deepseek' not in r:
                print(f'| {name} | {r["passed_of_80"]:.1f} | | {r["mean_cost_usd"]:.5f} | | {r["median_wall_s"]:.1f} | |')
                continue
            c = lambda k, d: f'{r[k]:+.{d}f} [{r[k + "_ci95"][0]:+.{d}f}, {r[k + "_ci95"][1]:+.{d}f}]'
            print(f'| {name} | {r["passed_of_80"]:.1f} | {c("pass_vs_deepseek", 3)} | {r["mean_cost_usd"]:.5f} | '
                  f'{c("cost_vs_deepseek", 5)} | {r["median_wall_s"]:.1f} | {c("median_wall_vs_deepseek", 1)} |')
    print('\nin-sample per-agent table (tol 0.05):', json.dumps(res['in_sample_table_tol_0.05']))
    print('tolerance per fold:', json.dumps(res['tolerance_per_fold']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['loto', 'online', 'fit'])
    parser.add_argument('--seeds', type=int, default=SEEDS)
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if args.command == 'loto':
        res = loto(seeds=args.seeds)
        (OUT / 'loto.json').write_text(json.dumps(res, indent=2) + '\n')
        print_loto(res)
    elif args.command == 'online':
        res = online(seeds=args.seeds)
        (OUT / 'online.json').write_text(json.dumps(res, indent=2) + '\n')
        print(json.dumps({k: v for k, v in res.items() if k != 'curves'}, indent=1))
    else:
        res = fit()
        (OUT / 'params.json').write_text(json.dumps(res, indent=2) + '\n')
        print(json.dumps({k: res[k] for k in ('tolerance', 'tasks', 'always_deepseek_pass')}, indent=1))


if __name__ == '__main__':
    main()
