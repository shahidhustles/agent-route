"""Summarize a scored pool run into the tables the paper needs.

    .venv/bin/python benchmarking/pool/summarize.py benchmarking/results/<run>

Writes <run>/summary.json and prints markdown tables:
pass rate per model and category, cost/latency/token use per model,
how often each model is the cheapest passing choice, and how many
tasks separate the models at all.
"""
import argparse
import collections
import json
import pathlib
import statistics


def short(model):
    return model.split('/')[-1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run')
    parser.add_argument('--models', help='comma-separated models to summarize (default: all models in meta.json)')
    args = parser.parse_args(argv)
    run_dir = pathlib.Path(args.run).resolve()
    meta = json.loads((run_dir / 'meta.json').read_text())
    models = args.models.split(',') if args.models else meta['models']

    by_case = collections.defaultdict(dict)
    category = {}
    for path in run_dir.glob('*__*/*.json'):
        r = json.loads(path.read_text())
        if r['model'] not in models:
            continue
        by_case[r['case_id']][r['model']] = r
        category[r['case_id']] = r['category']
    complete = {c: recs for c, recs in by_case.items()
                if len(recs) == len(models) and all((x.get('score') or {}).get('passed') is not None for x in recs.values())}
    cats = sorted({category[c] for c in complete})

    pass_rate = {m: {} for m in models}
    for m in models:
        for cat in cats + ['all']:
            ids = [c for c in complete if cat == 'all' or category[c] == cat]
            pass_rate[m][cat] = sum(complete[c][m]['score']['passed'] for c in ids) / len(ids)

    usage = {}
    for m in models:
        recs = [complete[c][m]['result'] for c in complete]
        usage[m] = {
            'mean_cost_usd': statistics.mean(r['cost_usd'] for r in recs),
            'median_latency_s': statistics.median(r['latency_ms'] for r in recs) / 1000,
            'mean_output_tokens': statistics.mean(r['completion_tokens'] for r in recs),
            'reasoning_share': sum(r['reasoning_tokens'] for r in recs) / max(1, sum(r['completion_tokens'] for r in recs)),
            'truncated': sum(bool(complete[c][m]['score'].get('truncated')) for c in complete),
        }

    def winner(recs, key):
        passing = [m for m in models if recs[m]['score']['passed']]
        return min(passing, key=lambda m: key(recs[m]['result'])) if passing else None

    label_cost = collections.Counter(winner(complete[c], lambda r: r['cost_usd']) for c in complete)
    label_latency = collections.Counter(winner(complete[c], lambda r: r['latency_ms']) for c in complete)
    label_cost_by_cat = {cat: collections.Counter(winner(complete[c], lambda r: r['cost_usd'])
                                                  for c in complete if category[c] == cat) for cat in cats}
    n_pass = collections.Counter(sum(complete[c][m]['score']['passed'] for m in models) for c in complete)

    best_single = max(models, key=lambda m: pass_rate[m]['all'])
    oracle = sum(1 for c in complete if any(complete[c][m]['score']['passed'] for m in models)) / len(complete)
    oracle_cost = statistics.mean(
        complete[c][label][ 'result']['cost_usd'] if (label := winner(complete[c], lambda r: r['cost_usd']))
        else complete[c][best_single]['result']['cost_usd'] for c in complete)

    summary = {'run': run_dir.name, 'tasks_scored': len(complete), 'tasks_total': len(by_case),
               'pass_rate': pass_rate, 'usage': usage,
               'cheapest_passing_label': {str(k): v for k, v in label_cost.items()},
               'fastest_passing_label': {str(k): v for k, v in label_latency.items()},
               'cheapest_passing_label_by_category': {cat: {str(k): v for k, v in cnt.items()} for cat, cnt in label_cost_by_cat.items()},
               'models_passing_histogram': dict(sorted(n_pass.items())),
               'best_single_model': best_single, 'best_single_pass_rate': pass_rate[best_single]['all'],
               'best_single_mean_cost_usd': usage[best_single]['mean_cost_usd'],
               'oracle_pass_rate': oracle, 'oracle_mean_cost_usd': oracle_cost}
    (run_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')

    print(f'Run {run_dir.name}: {len(complete)} of {len(by_case)} tasks fully scored\n')
    print('| Model | ' + ' | '.join(cats) + ' | all |')
    print('|---|' + '---:|' * (len(cats) + 1))
    for m in models:
        print(f'| {short(m)} | ' + ' | '.join(f'{pass_rate[m][c]:.2f}' for c in cats + ['all']) + ' |')
    print('\n| Model | Mean cost / task (USD) | Median latency (s) | Mean output tokens | Reasoning share | Truncated |')
    print('|---|---:|---:|---:|---:|---:|')
    for m in models:
        u = usage[m]
        print(f'| {short(m)} | {u["mean_cost_usd"]:.5f} | {u["median_latency_s"]:.1f} | {u["mean_output_tokens"]:.0f} | {u["reasoning_share"]:.2f} | {u["truncated"]} |')
    print('\n| Label (cheapest passing model) | Tasks | Label (fastest passing) | Tasks |')
    print('|---|---:|---|---:|')
    lc, ll = label_cost.most_common(), label_latency.most_common()
    for i in range(max(len(lc), len(ll))):
        a = lc[i] if i < len(lc) else ('', '')
        b = ll[i] if i < len(ll) else ('', '')
        print(f'| {short(a[0]) if a[0] else ("none pass" if a[0] is None else "")} | {a[1]} | '
              f'{short(b[0]) if b[0] else ("none pass" if b[0] is None else "")} | {b[1]} |')
    print('\nModels passing per task:', dict(sorted(n_pass.items())))
    print(f'Best single model: {short(best_single)} pass {pass_rate[best_single]["all"]:.3f}, '
          f'mean cost ${usage[best_single]["mean_cost_usd"]:.5f}')
    print(f'Oracle (cheapest passing): pass {oracle:.3f}, mean cost ${oracle_cost:.5f}')


if __name__ == '__main__':
    main()
