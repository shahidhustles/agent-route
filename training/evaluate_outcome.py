"""Offline evaluation of an N-model outcome router on saved outcomes. No model API calls.

    .venv/bin/python training/evaluate_outcome.py --data-dir data/outcome-4m-ordered \
        --predictions artifacts/outcome-router-4m-v1/predictions.jsonl \
        --base-predictions artifacts/outcome-router-4m-v1/predictions-base.jsonl

Every strategy picks one model per test task; pass, latency, and cost come
from that model's recorded outcome. Everything tunable (kNN k, the serving
threshold) is chosen on validation only.

Serving rule: take the router's top candidate; when its probability is below
a threshold, use the fallback model (the strongest). The threshold is the one
with the lowest mean latency on validation whose pass rate stays within
--tolerance of always-fallback.

Reported on test: single models, random, oracle, embedding kNN, zero-shot
base model, and the router; a matched-share comparison (the router's own
routing mix assigned at random); paired bootstrap CIs of router minus
always-fallback; a per-source breakdown; calibration of the top pick (did
the picked model pass?).
"""
import argparse
import collections
import json
import pathlib
import random
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
EMBED_MODEL = 'BAAI/bge-small-en-v1.5'
THRESHOLDS = [i / 100 for i in range(0, 101, 2)]
KS = [3, 5, 10, 20, 40]


def load(data_dir, split):
    return [json.loads(l) for l in (data_dir / f'{split}.jsonl').read_text().splitlines() if l.strip()]


def metrics(rows, picks):
    chosen = [r['outcomes'][p] for r, p in zip(rows, picks)]
    return {
        'pass_rate': round(sum(c['passed'] for c in chosen) / len(chosen), 4),
        'mean_cost_usd': round(statistics.mean(c['cost_usd'] for c in chosen), 6),
        'mean_latency_s': round(statistics.mean(c['latency_ms'] for c in chosen) / 1000, 2),
        'median_latency_s': round(statistics.median(c['latency_ms'] for c in chosen) / 1000, 2),
        'mean_output_tokens': round(statistics.mean(c['output_tokens'] for c in chosen)),
    }


def apply_rule(top, conf, t, fallback):
    return [m if c >= t else fallback for m, c in zip(top, conf)]


def choose_threshold(rows, top, conf, fallback, tolerance):
    base = metrics(rows, [fallback] * len(rows))
    best = None
    for t in THRESHOLDS + [1.01]:
        m = metrics(rows, apply_rule(top, conf, t, fallback))
        if m['pass_rate'] < base['pass_rate'] - tolerance - 1e-9:
            continue
        if best is None or m['mean_latency_s'] < best[0] - 1e-9:
            best = (m['mean_latency_s'], t)
    return best[1]


def top_and_conf(probs_rows):
    top = [max(p, key=p.get) for p in probs_rows]
    return top, [p[t] for p, t in zip(probs_rows, top)]


def calibration(conf, hit, bins=10):
    n = len(conf)
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        group = [(c, h) for c, h in zip(conf, hit) if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if group:
            ece += len(group) / n * abs(statistics.mean(c for c, _ in group) - statistics.mean(h for _, h in group))
    return {'ece': round(ece, 4), 'brier': round(statistics.mean((c - h) ** 2 for c, h in zip(conf, hit)), 4),
            'pick_pass_rate': round(statistics.mean(hit), 4), 'mean_confidence': round(statistics.mean(conf), 4),
            'confidence_range': [round(min(conf), 3), round(max(conf), 3)]}


def knn_probs(train, rows, emb_train, emb, slugs, k):
    out = []
    for sims in emb @ emb_train.T:
        vote = collections.Counter({s: 0.0 for s in slugs})
        for i in sims.argsort()[::-1][:k]:
            vote[train[i]['output']] += max(float(sims[i]), 1e-6)
        total = sum(vote.values())
        out.append({s: v / total for s, v in vote.items()})
    return out


def bootstrap(rows, picks, fallback, resamples=2000, seed=0):
    """Paired bootstrap of router minus always-fallback over test tasks."""
    a = [r['outcomes'][p] for r, p in zip(rows, picks)]
    b = [r['outcomes'][fallback] for r in rows]
    rng = random.Random(seed)
    n = len(rows)
    stats = collections.defaultdict(list)
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        stats['pass_rate'].append(statistics.mean(a[i]['passed'] - b[i]['passed'] for i in idx))
        stats['mean_cost_usd'].append(statistics.mean(a[i]['cost_usd'] - b[i]['cost_usd'] for i in idx))
        stats['mean_latency_s'].append(statistics.mean(a[i]['latency_ms'] - b[i]['latency_ms'] for i in idx) / 1000)
        stats['median_latency_s'].append((statistics.median(a[i]['latency_ms'] for i in idx) -
                                          statistics.median(b[i]['latency_ms'] for i in idx)) / 1000)
    ci = lambda v: [round(x, 6) for x in (sorted(v)[int(0.025 * resamples)], sorted(v)[int(0.975 * resamples) - 1])]
    point = {'pass_rate': statistics.mean(x['passed'] for x in a) - statistics.mean(x['passed'] for x in b),
             'mean_cost_usd': statistics.mean(x['cost_usd'] for x in a) - statistics.mean(x['cost_usd'] for x in b),
             'mean_latency_s': (statistics.mean(x['latency_ms'] for x in a) - statistics.mean(x['latency_ms'] for x in b)) / 1000,
             'median_latency_s': (statistics.median(x['latency_ms'] for x in a) - statistics.median(x['latency_ms'] for x in b)) / 1000}
    return {k: {'diff': round(point[k], 6), 'ci95': ci(v)} for k, v in stats.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data-dir', type=pathlib.Path, required=True)
    parser.add_argument('--predictions', type=pathlib.Path, required=True)
    parser.add_argument('--base-predictions', type=pathlib.Path)
    parser.add_argument('--fallback', default='deepseek-v4.1-flash')
    parser.add_argument('--tolerance', type=float, default=0.02)
    parser.add_argument('--out', type=pathlib.Path)
    args = parser.parse_args()
    fb = args.fallback

    train, val, test = (load(args.data_dir, s) for s in ('train', 'validation', 'test'))
    slugs = [c['model_slug'] for c in train[0]['input']['candidates']]
    results, picks_by = {}, {}
    for m in slugs:
        results[f'always_{m}'] = metrics(test, [m] * len(test))
    rng = random.Random(0)
    runs = [metrics(test, [rng.choice(slugs) for _ in test]) for _ in range(200)]
    results['random'] = {k: round(statistics.mean(r[k] for r in runs), 4) for k in runs[0]}
    # Oracle: the label rule itself (cheapest-and-fastest passing model, strongest when none passed).
    oracle = [r['output'] for r in test]
    results['oracle'] = metrics(test, oracle)

    def learned(name, probs_val, probs_test, extra=None):
        top_v, conf_v = top_and_conf(probs_val)
        top_t, conf_t = top_and_conf(probs_test)
        t = choose_threshold(val, top_v, conf_v, fb, args.tolerance)
        picks = apply_rule(top_t, conf_t, t, fb)
        picks_by[name] = picks
        hit = [float(r['outcomes'][p]['passed']) for r, p in zip(test, top_t)]
        results[name] = {**metrics(test, picks), 'threshold': t, 'top1_only': metrics(test, top_t),
                         'routing_mix': {m: round(picks.count(m) / len(picks), 3) for m in slugs},
                         'label_agreement_top1': round(sum(p == r['output'] for p, r in zip(top_t, test)) / len(test), 4),
                         'calibration_top_pick': calibration(conf_t, hit), **(extra or {})}

    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer(EMBED_MODEL)
    enc = lambda rows: embedder.encode([r['input']['user_task'] for r in rows], normalize_embeddings=True)
    e_train, e_val, e_test = enc(train), enc(val), enc(test)
    best_k = max(KS, key=lambda k: (sum(max(p, key=p.get) == r['output'] for p, r in zip(knn_probs(train, val, e_train, e_val, slugs, k), val)), -k))
    learned('embedding_knn', knn_probs(train, val, e_train, e_val, slugs, best_k),
            knn_probs(train, test, e_train, e_test, slugs, best_k), {'k': best_k})

    def router_probs(path):
        preds = {(p['split'], p['case_id']): p for p in map(json.loads, path.read_text().splitlines())}
        return ([preds[('validation', r['case_id'])]['probabilities'] for r in val],
                [preds[('test', r['case_id'])]['probabilities'] for r in test],
                statistics.median(p['routing_ms'] for p in preds.values()))

    for name, path in [('zero_shot_base', args.base_predictions), ('router', args.predictions)]:
        if path:
            pv, pt, ms = router_probs(path)
            learned(name, pv, pt, {'median_routing_ms': ms})

    # Matched share: the router's own routing mix, assigned to test tasks at random.
    mix_picks = picks_by['router']
    shuffles = []
    rng = random.Random(1)
    for _ in range(200):
        p = mix_picks[:]
        rng.shuffle(p)
        shuffles.append(metrics(test, p))
    matched = {k: round(statistics.mean(r[k] for r in shuffles), 4) for k in shuffles[0]}
    matched_knn = None
    # kNN at the router's mix: rank by kNN confidence in each model, give each model its quota.
    quota = collections.Counter(mix_picks)
    knn_pt = knn_probs(train, test, e_train, e_test, slugs, best_k)
    assigned, free = {}, set(range(len(test)))
    for m in sorted(quota, key=lambda s: quota[s]):
        if m == fb:
            continue
        for i in sorted(free, key=lambda i: -knn_pt[i][m])[:quota[m]]:
            assigned[i] = m
            free.discard(i)
    matched_knn = metrics(test, [assigned.get(i, fb) for i in range(len(test))])

    # Cheap preference: easy tasks (high router score for the fastest model) go to a cheaper model.
    pv, pt, _ = router_probs(args.predictions)
    easy_slug = 'nemotron-3.5-super-vl'
    ev, et = [p[easy_slug] for p in pv], [p[easy_slug] for p in pt]
    base_pass = metrics(val, [fb] * len(val))['pass_rate']
    cheap = None
    for m in ('glm-5.3-flash', 'mimo-v2.6-flash'):
        for t in THRESHOLDS:
            s = metrics(val, [m if e >= t else fb for e in ev])
            if s['pass_rate'] >= base_pass - args.tolerance - 1e-9 and (cheap is None or s['mean_cost_usd'] < cheap[0]):
                cheap = (s['mean_cost_usd'], m, t)
    picks_by['cheap'] = [cheap[1] if e >= cheap[2] else fb for e in et]
    results['cheap'] = {**metrics(test, picks_by['cheap']), 'easy_model': cheap[1], 'threshold': cheap[2],
                        'routing_mix': {m: round(picks_by['cheap'].count(m) / len(test), 3) for m in slugs}}

    boot = {n: bootstrap(test, picks_by[n], fb) for n in picks_by if n in ('router', 'embedding_knn', 'cheap')}

    by_source = {}
    for src in sorted({r['source'] for r in test}):
        idx = [i for i, r in enumerate(test) if r['source'] == src]
        rows = [test[i] for i in idx]
        by_source[src] = {'n': len(idx), 'router': metrics(rows, [picks_by['router'][i] for i in idx]),
                          fb: metrics(rows, [fb] * len(idx)),
                          'router_mix': dict(collections.Counter(picks_by['router'][i] for i in idx))}

    report = {'data_dir': str(args.data_dir), 'test_tasks': len(test), 'models': slugs, 'fallback': fb,
              'tolerance': args.tolerance, 'embedding_model': EMBED_MODEL, 'results': results,
              'matched_share': {'router_mix': matched, 'knn_at_router_mix': matched_knn},
              'bootstrap_vs_fallback': boot, 'by_source': by_source}
    out = args.out or args.predictions.parent / 'evaluation.json'
    out.write_text(json.dumps(report, indent=2) + '\n')

    print(f'Test tasks: {len(test)}\n')
    print('| Strategy | Pass | Mean cost (USD) | Median latency (s) | Mean latency (s) |')
    print('|---|---:|---:|---:|---:|')
    for name, m in results.items():
        print(f'| {name} | {m["pass_rate"]:.3f} | {m["mean_cost_usd"]:.6f} | {m["median_latency_s"]:.2f} | {m["mean_latency_s"]:.2f} |')
    print(f'\nmatched share (router mix at random): {matched}\nkNN at router mix: {matched_knn}')
    for n in ('router', 'embedding_knn', 'zero_shot_base'):
        if n in results:
            r = results[n]
            print(f'\n{n}: threshold {r["threshold"]}, mix {r["routing_mix"]}, top1 label agreement {r["label_agreement_top1"]}')
            print(f'  top1 only {r["top1_only"]}\n  calibration {r["calibration_top_pick"]}')
    for n, b in boot.items():
        print(f'\nbootstrap {n} minus always-{fb}: {b}')
    print(f'\nwrote {out}')


if __name__ == '__main__':
    main()
