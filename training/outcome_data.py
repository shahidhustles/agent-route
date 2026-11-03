"""Build router training data from measured model outcomes.

Reads scored runs under benchmarking/results/, keeps tasks every pool
model answered, and labels each task with the passing model that best
serves --objective: lowest measured latency, lowest measured cost, or
`fast-passes` (the first --models entry is the strong model, the last the
fast one; the label is the fast model exactly when it passed), or `ordered`
(models ranked by mean cost x median latency on the training split, cheapest
and fastest first; the label is the first model in that order that passed,
and the strongest model, by training pass rate, when none did).
Splits are family-isolated and stratified by source. Profiles shown to the
router are measured on the training split only, so validation and test
outcomes never leak into the input.

    .venv/bin/python training/outcome_data.py \
        --runs benchmarking/results/pilot-v1-20261028T040319Z benchmarking/results/full-v1-20261028T050713Z \
        --models deepseek/deepseek-v4.1-flash nvidia/nemotron-3.5-super-vl
"""
import argparse
import collections
import hashlib
import json
import pathlib
import random
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUITES = ROOT / 'benchmarking' / 'suites'
OUT = ROOT / 'data' / 'outcome'
TASK_HEAD, TASK_TAIL = 1600, 400


def short(model):
    return model.split('/')[-1]


def task_text(case):
    """What the router sees: the last user message, clipped for long documents."""
    text = case['messages'][-1]['content']
    if len(text) > TASK_HEAD + TASK_TAIL:
        omitted = len(text) - TASK_HEAD - TASK_TAIL
        text = f'{text[:TASK_HEAD]}\n[... {omitted} characters omitted ...]\n{text[-TASK_TAIL:]}'
    return text


def load_outcomes(runs, models):
    cases, outcomes = {}, collections.defaultdict(dict)
    for run in runs:
        run = pathlib.Path(run)
        meta = json.loads((run / 'meta.json').read_text())
        for line in (SUITES / f'{meta["suite"]}.jsonl').read_text().splitlines():
            if line.strip():
                c = json.loads(line)
                cases[c['id']] = c
        for path in run.glob('*__*/*.json'):
            r = json.loads(path.read_text())
            if r['model'] in models and (r.get('score') or {}).get('passed') is not None:
                outcomes[r['case_id']][r['model']] = r
    complete = {cid: recs for cid, recs in outcomes.items() if len(recs) == len(models)}
    return cases, complete


OBJECTIVE_KEYS = {'latency': 'latency_ms', 'cost': 'cost_usd'}


def model_order(train_ids, outcomes, models):
    """Cheapest-and-fastest first, measured on training tasks only; also returns the strongest model."""
    def stats(m):
        recs = [outcomes[c][m] for c in train_ids]
        return (statistics.mean(r['result']['cost_usd'] for r in recs) *
                statistics.median(r['result']['latency_ms'] for r in recs) / 1000,
                sum(r['score']['passed'] for r in recs) / len(recs))
    order = sorted(models, key=lambda m: (stats(m)[0], models.index(m)))
    return order, max(models, key=lambda m: (stats(m)[1], -models.index(m)))


def label(recs, models, objective, strongest=None):
    if objective == 'ordered':
        # `models` is the cost-latency order here.
        return next((m for m in models if recs[m]['score']['passed']), strongest)
    if objective == 'fast-passes':
        return models[-1] if recs[models[-1]]['score']['passed'] else models[0]
    passing = [m for m in models if recs[m]['score']['passed']]
    if not passing:
        return None
    key = OBJECTIVE_KEYS[objective]
    return min(passing, key=lambda m: (recs[m]['result'][key], models.index(m)))


def split_ids(cases, ids, seed, test_frac, val_frac):
    by_source = collections.defaultdict(list)
    for cid in ids:
        by_source[cases[cid]['source']].append(cid)
    split = {}
    for source, members in sorted(by_source.items()):
        # Hash order is stable across runs and independent of file order.
        members.sort(key=lambda cid: hashlib.sha256(f'{seed}:{cases[cid]["family_id"]}'.encode()).hexdigest())
        n_test = round(len(members) * test_frac)
        n_val = round(len(members) * val_frac)
        for i, cid in enumerate(members):
            split[cid] = 'test' if i < n_test else 'validation' if i < n_test + n_val else 'train'
    return split


def profiles(train_ids, cases, outcomes, models):
    out = []
    for m in models:
        recs = [outcomes[c][m] for c in train_ids]
        by_cat = collections.defaultdict(list)
        for c, r in zip(train_ids, recs):
            by_cat[cases[c]['category']].append(r['score']['passed'])
        out.append({
            'model_slug': short(m),
            'pass_rate': {cat: round(sum(v) / len(v), 2) for cat, v in sorted(by_cat.items())},
            'mean_cost_usd': round(statistics.mean(r['result']['cost_usd'] for r in recs), 6),
            'median_latency_s': round(statistics.median(r['result']['latency_ms'] for r in recs) / 1000, 1),
            'mean_output_tokens': round(statistics.mean(r['result']['completion_tokens'] for r in recs)),
        })
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--runs', nargs='+', required=True)
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--seed', type=int, default=20261028)
    parser.add_argument('--objective', choices=sorted(OBJECTIVE_KEYS) + ['fast-passes', 'ordered'], default='latency')
    parser.add_argument('--out-dir', help='default data/outcome')
    parser.add_argument('--test-frac', type=float, default=0.2)
    parser.add_argument('--val-frac', type=float, default=0.1)
    args = parser.parse_args(argv)

    cases, outcomes = load_outcomes(args.runs, args.models)
    split = split_ids(cases, list(outcomes), args.seed, args.test_frac, args.val_frac)
    train_ids = sorted(c for c, s in split.items() if s == 'train')
    profile_block = profiles(train_ids, cases, outcomes, args.models)
    order, strongest = model_order(train_ids, outcomes, args.models)
    label_models = order if args.objective == 'ordered' else args.models
    out = pathlib.Path(args.out_dir) if args.out_dir else OUT
    out.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    files = {}
    for name in ('train', 'validation', 'test'):
        rows = []
        for cid in sorted(c for c, s in split.items() if s == name):
            case, recs = cases[cid], outcomes[cid]
            target = label(recs, label_models, args.objective, strongest)
            counts[(name, short(target) if target else 'none')] += 1
            # Tasks no model passes carry no routing signal; keep them only for evaluation.
            if target is None and name == 'train':
                continue
            rows.append({
                'case_id': cid, 'family_id': case['family_id'], 'source': case['source'], 'category': case['category'],
                'input': {
                    'user_task': task_text(case),
                    'requires_tools': bool(case.get('tools')),
                    'approx_input_tokens': len(case['messages'][-1]['content']) // 4,
                    'candidates': profile_block,
                },
                'output': short(target) if target else None,
                'outcomes': {short(m): {'passed': recs[m]['score']['passed'], 'cost_usd': recs[m]['result']['cost_usd'],
                                        'latency_ms': recs[m]['result']['latency_ms'],
                                        'output_tokens': recs[m]['result']['completion_tokens'],
                                        'truncated': recs[m]['result'].get('finish_reason') == 'length'}
                             for m in args.models},
            })
        body = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
        (out / f'{name}.jsonl').write_text(body)
        files[name] = {'rows': len(rows), 'sha256': hashlib.sha256(body.encode()).hexdigest()}

    manifest = {'runs': [pathlib.Path(r).name for r in args.runs], 'models': args.models, 'seed': args.seed,
                'objective': args.objective,
                'label_rule': ('fast model if it passed, else strong model' if args.objective == 'fast-passes' else
                               f'first passing model in the train-measured cost x latency order {[short(m) for m in order]}; '
                               f'none-pass tasks labelled {short(strongest)}' if args.objective == 'ordered' else
                               f'passing model with lowest measured {OBJECTIVE_KEYS[args.objective]}; none-pass tasks dropped from train'),
                'files': files, 'label_counts': {f'{k[0]}:{k[1]}': v for k, v in sorted(counts.items())},
                'model_order': [short(m) for m in order], 'strongest': short(strongest), 'profiles': profile_block}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'profiles'}, indent=2))


if __name__ == '__main__':
    main()
