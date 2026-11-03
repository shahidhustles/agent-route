"""Replay evaluation of model choice on recorded single-call outcomes. No model calls.

    .venv/bin/python routing/replay.py --dataset pilot6      # pilot-v1, 200 tasks x 6 models
    .venv/bin/python routing/replay.py --dataset two-model   # phase 1 data, 501 tasks x 2 models

Both datasets use the phase 1 splits (data/outcome): pilot6 has 137 train, 23 validation, 40 test tasks;
two-model has 350 / 52 / 100.

Tuning uses validation only, with full-information train memory (every model's outcome on every train task):
k and prior strength minimise the Brier score of P(success) over validation (task, model) pairs; then each
preference's weight is the grid value that minimises its target (latency for fast, cost for cheap, both for
balanced) while the greedy validation pass rate stays within a tolerance of `accurate`.

Each seed then replays two streams per strategy and preference:
1. collection: the train tasks in a seeded order, starting from empty memory. The strategy picks a model,
   sees only that model's recorded outcome (bandit feedback), and appends it to memory;
2. evaluation: the test tasks in a seeded order, greedy picks, still appending the chosen outcome.

Strategies: random; best single model (highest mean train utility for the preference); kNN greedy and
kNN + Thompson (differ only in collection); kNN with full-information train memory (what memory could give
if every model had run on every train task); oracle (highest realized utility per task).

Regret per task = oracle utility - chosen utility, with utility = passed - w_time*latency/L - w_cost*cost/C.
Test metrics are averaged over seeds per task, then given 95% bootstrap CIs over test tasks. Regret curves
(mean and 2.5/97.5 percentiles over seeds) go to artifacts/phase3/regret-<dataset>.csv.
"""
import argparse
import csv
import json
import pathlib
import random
import statistics
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from memory import Memory  # noqa: E402
from policy import PREFERENCES, OutcomeTable, Params, choose_model  # noqa: E402

OUT = ROOT / 'artifacts' / 'phase3'
PILOT_RUN = 'pilot-v1-20261028T040319Z'
PILOT_MODELS = ['deepseek/deepseek-v4.1-flash', 'z-ai/glm-5.3-flash', 'ornith/ornith-1.5-122b',
                'xiaomi/mimo-v2.6-flash', 'tencent/hy3-paid', 'nvidia/nemotron-3.5-super-vl']
TWO_MODELS = ['deepseek/deepseek-v4.1-flash', 'nvidia/nemotron-3.5-super-vl']
K_GRID = [3, 5, 10, 20, 40]
PRIOR_GRID = [0.5, 1, 2, 5, 10]
WEIGHT_GRID = [0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0]
TOLERANCE = {'balanced': 0.02, 'fast': 0.05, 'cheap': 0.05}
STRATEGIES = ['random', 'best_single', 'knn_greedy', 'knn_thompson', 'knn_full_memory', 'oracle']


class Dataset:
    """Complete outcome grid: outcomes[task][model] = (passed, latency_s, cost_usd)."""

    def __init__(self, name, models, outcomes, vectors, split):
        self.name, self.models, self.outcomes, self.vectors = name, models, outcomes, vectors
        self.ids = {part: sorted(t for t in outcomes if split.get(t) == part) for part in ('train', 'validation', 'test')}

    def utility(self, task, model, preference, params):
        passed, lat, cost = self.outcomes[task][model]
        w_time, w_cost = params.weights[preference]
        return passed - w_time * lat / params.latency_scale - w_cost * cost / params.cost_scale


def load_dataset(name, mem=None):
    mem = mem or Memory.load()
    if name == 'pilot6':
        models, runs = PILOT_MODELS, {PILOT_RUN}
    else:
        models, runs = TWO_MODELS, {PILOT_RUN, 'full-v1-20261028T050713Z'}
    grid = {}
    for r in mem.records:
        if r['run'] in runs and r['model'] in models and r['passed'] is not None:
            grid.setdefault(r['task_id'], {})[r['model']] = (float(r['passed']), r['latency_s'], r['cost_usd'])
    split = {t: info['split'] for t, info in mem.tasks.items() if info['dataset'] in ('pilot-v1', 'full-v1')}
    outcomes = {t: o for t, o in grid.items() if len(o) == len(models) and split.get(t)}
    return Dataset(name, models, outcomes, {t: mem.vectors[t] for t in outcomes}, split)


def full_table(ds, ids):
    table = OutcomeTable()
    for t in ids:
        for m in ds.models:
            table.add(ds.vectors[t], m, *ds.outcomes[t][m])
    return table


def greedy_picks(ds, table, ids, preference, params):
    return [choose_model(table, ds.vectors[t], ds.models, preference, params)[0] for t in ids]


def tune(ds):
    train, val = ds.ids['train'], ds.ids['validation']
    lat = [ds.outcomes[t][m][1] for t in train for m in ds.models]
    cost = [ds.outcomes[t][m][2] for t in train for m in ds.models]
    params = Params(latency_scale=statistics.median(lat), cost_scale=statistics.median(cost))
    table = full_table(ds, train)
    brier = {}
    for k in K_GRID:
        for prior in PRIOR_GRID:
            p = Params(k=k, prior=prior)
            errs = [(table.estimate(ds.vectors[t], m, p).p_success - ds.outcomes[t][m][0]) ** 2
                    for t in val for m in ds.models]
            brier[(k, prior)] = statistics.mean(errs)
    params.k, params.prior = min(brier, key=lambda kp: (brier[kp], abs(kp[0] - 10), kp[1]))

    def val_metrics(pref):
        picks = greedy_picks(ds, table, val, pref, params)
        o = [ds.outcomes[t][m] for t, m in zip(val, picks)]
        return {'pass': statistics.mean(x[0] for x in o), 'lat': statistics.mean(x[1] for x in o),
                'cost': statistics.mean(x[2] for x in o),
                'both': statistics.mean(x[1] / params.latency_scale + x[2] / params.cost_scale for x in o)}

    weight_search = {}
    base = val_metrics('accurate')
    for pref, target in (('fast', 'lat'), ('cheap', 'cost'), ('balanced', 'both')):
        rows = []
        for w in WEIGHT_GRID:
            params.weights[pref] = {'fast': (w, 0.0), 'cheap': (0.0, w), 'balanced': (w, w)}[pref]
            rows.append((w, val_metrics(pref)))
        ok = [(w, m) for w, m in rows if m['pass'] >= base['pass'] - TOLERANCE[pref] - 1e-9]
        w = min(ok, key=lambda x: (x[1][target], x[0]))[0]
        params.weights[pref] = {'fast': (w, 0.0), 'cheap': (0.0, w), 'balanced': (w, w)}[pref]
        weight_search[pref] = [{'w': w_, **{k: round(v, 5) for k, v in m.items()}} for w_, m in rows]
    return params, {'brier': {f'k={k},prior={s}': round(v, 4) for (k, s), v in brier.items()},
                    'validation_accurate': {k: round(v, 5) for k, v in base.items()},
                    'weight_search': weight_search}


def run_stream(ds, strategy, preference, params, collect_ids, test_ids, seed, best_single):
    """Replay one strategy. Returns per-step logs: (phase, task, model, regret)."""
    rng = np.random.default_rng(seed)
    pick_rng = random.Random(seed)
    table = full_table(ds, ds.ids['train']) if strategy == 'knn_full_memory' else OutcomeTable()
    phases = [('test', test_ids)] if strategy == 'knn_full_memory' else [('collect', collect_ids), ('test', test_ids)]
    logs = []
    for phase, ids in phases:
        for t in ids:
            u = {m: ds.utility(t, m, preference, params) for m in ds.models}
            if strategy == 'random':
                m = pick_rng.choice(ds.models)
            elif strategy == 'best_single':
                m = best_single
            elif strategy == 'oracle':
                m = max(ds.models, key=lambda x: u[x])
            else:
                mode = 'thompson' if strategy == 'knn_thompson' and phase == 'collect' else 'greedy'
                m = choose_model(table, ds.vectors[t], ds.models, preference, params, mode=mode, rng=rng)[0]
                table.add(ds.vectors[t], m, *ds.outcomes[t][m])
            logs.append((phase, t, m, max(u.values()) - u[m]))
    return logs


def bootstrap(values, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    v = np.asarray(values, float)
    means = np.sort(v[rng.integers(0, len(v), (n, len(v)))].mean(axis=1))
    return [round(float(means[int(0.025 * n)]), 4), round(float(means[int(0.975 * n) - 1]), 4)]


def evaluate(ds, params, seeds):
    train, test = ds.ids['train'], ds.ids['test']
    best = {p: max(ds.models, key=lambda m: statistics.mean(ds.utility(t, m, p, params) for t in train))
            for p in PREFERENCES}
    results, curves = {}, []
    for pref in PREFERENCES:
        results[pref] = {}
        per_task = {}
        for strategy in STRATEGIES:
            cum = {'collect': [], 'test': []}
            task_vals = {t: [] for t in test}
            collect_regret = []
            for seed in seeds:
                order = random.Random(seed)
                collect_ids, test_ids = train[:], test[:]
                order.shuffle(collect_ids)
                order.shuffle(test_ids)
                logs = run_stream(ds, strategy, pref, params, collect_ids, test_ids, seed, best[pref])
                for phase in ('collect', 'test'):
                    regrets = [r for ph, _, _, r in logs if ph == phase]
                    if regrets:
                        cum[phase].append(np.cumsum(regrets))
                collect_regret.append(sum(r for ph, _, _, r in logs if ph == 'collect'))
                for ph, t, m, r in logs:
                    if ph == 'test':
                        passed, lat, cost = ds.outcomes[t][m]
                        task_vals[t].append((passed, lat, cost, r, m))
            for phase, arrs in cum.items():
                if not arrs:
                    continue
                a = np.stack(arrs)
                for step in range(a.shape[1]):
                    curves.append({'dataset': ds.name, 'preference': pref, 'strategy': strategy, 'phase': phase,
                                   'step': step + 1, 'mean_cum_regret': round(float(a[:, step].mean()), 4),
                                   'p2_5': round(float(np.percentile(a[:, step], 2.5)), 4),
                                   'p97_5': round(float(np.percentile(a[:, step], 97.5)), 4)})
            avg = {t: [statistics.mean(v[i] for v in vals) for i in range(4)] for t, vals in task_vals.items()}
            per_task[strategy] = avg
            share = {}
            for vals in task_vals.values():
                for v in vals:
                    share[v[4]] = share.get(v[4], 0) + 1
            total = sum(share.values())
            col = lambda i: [avg[t][i] for t in test]
            results[pref][strategy] = {
                'pass_rate': round(statistics.mean(col(0)), 4), 'pass_ci95': bootstrap(col(0)),
                'mean_latency_s': round(statistics.mean(col(1)), 2), 'mean_cost_usd': round(statistics.mean(col(2)), 6),
                'test_regret_per_task': round(statistics.mean(col(3)), 4), 'regret_ci95': bootstrap(col(3)),
                'test_cum_regret': round(sum(col(3)), 3),
                'collect_cum_regret': round(statistics.mean(collect_regret), 2) if strategy != 'knn_full_memory' else None,
                'model_share': {m.split('/')[-1]: round(n / total, 3) for m, n in sorted(share.items(), key=lambda x: -x[1])},
            }
        for strategy in ('knn_greedy', 'knn_thompson', 'knn_full_memory', 'random'):
            diff = [per_task[strategy][t][3] - per_task['best_single'][t][3] for t in test]
            results[pref][strategy]['regret_minus_best_single'] = round(statistics.mean(diff), 4)
            results[pref][strategy]['regret_minus_best_single_ci95'] = bootstrap(diff, seed=1)
    return results, curves, best


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dataset', choices=['pilot6', 'two-model'], required=True)
    parser.add_argument('--seeds', type=int, default=20)
    args = parser.parse_args(argv)
    ds = load_dataset(args.dataset)
    params, tuning = tune(ds)
    results, curves, best = evaluate(ds, params, list(range(args.seeds)))
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'dataset': ds.name, 'models': ds.models, 'tasks': {k: len(v) for k, v in ds.ids.items()},
              'seeds': args.seeds,
              'params': {'k': params.k, 'prior': params.prior, 'latency_scale_s': params.latency_scale,
                         'cost_scale_usd': params.cost_scale,
                         'weights': {p: {'w_time': w[0], 'w_cost': w[1]} for p, w in params.weights.items()}},
              'best_single': best, 'tuning': tuning, 'results': results}
    (OUT / f'replay-{ds.name}.json').write_text(json.dumps(report, indent=2) + '\n')
    with (OUT / f'regret-{ds.name}.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(curves[0]))
        w.writeheader()
        w.writerows(curves)
    print(f'{ds.name}: tasks {report["tasks"]}, k={params.k}, prior={params.prior}, '
          f'L={params.latency_scale:.2f}s, C=${params.cost_scale:.6f}, weights {report["params"]["weights"]}')
    for pref in PREFERENCES:
        print(f'\n{pref} (best single: {best[pref].split("/")[-1]})\n')
        print('| Strategy | Pass (95% CI) | Mean latency (s) | Mean cost (USD) | Regret/task (95% CI) | vs best single | Collect regret |')
        print('|---|---|---:|---:|---|---|---:|')
        for s, r in results[pref].items():
            vs = (f'{r["regret_minus_best_single"]:+.3f} [{r["regret_minus_best_single_ci95"][0]:+.3f}, '
                  f'{r["regret_minus_best_single_ci95"][1]:+.3f}]') if 'regret_minus_best_single' in r else ''
            print(f'| {s} | {r["pass_rate"]:.3f} [{r["pass_ci95"][0]:.2f}, {r["pass_ci95"][1]:.2f}] | {r["mean_latency_s"]:.1f} | '
                  f'{r["mean_cost_usd"]:.5f} | {r["test_regret_per_task"]:.3f} [{r["regret_ci95"][0]:.3f}, {r["regret_ci95"][1]:.3f}] | '
                  f'{vs} | {r["collect_cum_regret"] if r["collect_cum_regret"] is not None else ""} |')


if __name__ == '__main__':
    main()
