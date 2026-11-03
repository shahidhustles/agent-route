"""Agent selection on the agents-v1 gold labels. No agent runs needed.

    .venv/bin/python routing/agents_eval.py split     # writes data/agents/{train,validation,test}.jsonl
    .venv/bin/python routing/agents_eval.py report \
        --zero-shot artifacts/agent-router-zero-shot/predictions.jsonl \
        --fine-tuned artifacts/agent-router-v1/predictions.jsonl

One fixed split of the 200 tasks, stratified by group (each agent's 20 tasks, and the 40 overlap tasks as
their own group): 8 test, 2 validation, 10 train per 20 tasks. Every method is scored on the same test tasks.
A pick is correct when it is one of the task's acceptable agents. Methods: majority agent (most frequent
acceptable agent in train), similarity-weighted kNN vote over train embeddings (k chosen on validation), and
Qwen3-0.6B zero-shot and fine-tuned scores from training/predict_outcome.py --format agent.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import random
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'training'))
from memory import AGENT_SUITE, Embedder, read_jsonl  # noqa: E402
from policy import agent_vote  # noqa: E402
import agent_router  # noqa: E402

OUT = ROOT / 'data' / 'agents'
SEED = 20261028
K_GRID = [1, 3, 5, 10, 20]


def split_tasks(tasks, seed=SEED, per20=(8, 2)):
    """Stratified split: per group, hash-ordered, the first 40% test, next 10% validation, rest train."""
    groups = collections.defaultdict(list)
    for t in tasks:
        groups[t['group']].append(t)
    split = {}
    for group, members in sorted(groups.items()):
        members.sort(key=lambda t: hashlib.sha256(f'{seed}:{t["id"]}'.encode()).hexdigest())
        n_test = round(len(members) * per20[0] / 20)
        n_val = round(len(members) * per20[1] / 20)
        for i, t in enumerate(members):
            split[t['id']] = 'test' if i < n_test else 'validation' if i < n_test + n_val else 'train'
    return split


def write_split():
    tasks = read_jsonl(AGENT_SUITE)
    split = split_tasks(tasks)
    OUT.mkdir(parents=True, exist_ok=True)
    files = {}
    for part in ('train', 'validation', 'test'):
        rows = [{'case_id': t['id'], 'group': t['group'], 'agents': t['agents'],
                 'input': agent_router.request(t['prompt']), 'output': t['agents'][0]}
                for t in tasks if split[t['id']] == part]
        body = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
        (OUT / f'{part}.jsonl').write_text(body)
        files[part] = {'rows': len(rows), 'sha256': hashlib.sha256(body.encode()).hexdigest(),
                       'groups': dict(collections.Counter(r['group'] for r in rows))}
    (OUT / 'manifest.json').write_text(json.dumps({'suite': AGENT_SUITE.name, 'seed': SEED, 'files': files,
                                                   'label_rule': 'overlap tasks list every acceptable agent'},
                                                  indent=2) + '\n')
    return files


def load_split():
    return {part: read_jsonl(OUT / f'{part}.jsonl') for part in ('train', 'validation', 'test')}


def embed(rows, embedder):
    return embedder.encode([r['input']['user_task'] for r in rows])


def knn_picks(train, rows, train_vecs, row_vecs, k):
    labels = [r['agents'] for r in train]
    return [agent_vote(v, train_vecs, labels, k)[0][0] for v in row_vecs]


def accuracy(rows, picks):
    return sum(p in r['agents'] for r, p in zip(rows, picks)) / len(rows)


def bootstrap_ci(hits, n=2000, seed=0):
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(hits) for _ in hits) / len(hits) for _ in range(n))
    return [round(means[int(0.025 * n)], 3), round(means[int(0.975 * n) - 1], 3)]


def choose_k(train, val, train_vecs, val_vecs):
    """Best validation accuracy; ties go to the k closest to the spec default of 10."""
    scores = {k: accuracy(val, knn_picks(train, val, train_vecs, val_vecs, k)) for k in K_GRID}
    best = max(scores.values())
    return min((k for k, s in scores.items() if s == best), key=lambda k: abs(k - 10)), scores


def prediction_picks(path, rows):
    preds = {}
    for p in read_jsonl(path):
        preds[p['case_id']] = p
    picks = [max(preds[r['case_id']]['probabilities'].items(), key=lambda x: x[1])[0] for r in rows]
    ms = [preds[r['case_id']]['routing_ms'] for r in rows]
    return picks, float(np.median(ms))


def report(zero_shot=None, fine_tuned=None, out=None):
    data = load_split()
    train, val, test = data['train'], data['validation'], data['test']
    embedder = Embedder()
    tv, vv, sv = embed(train, embedder), embed(val, embedder), embed(test, embedder)
    k, k_scores = choose_k(train, val, tv, vv)
    counts = collections.Counter(a for r in train for a in r['agents'])
    majority = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
    methods = {'majority': [majority] * len(test), f'knn (k={k})': knn_picks(train, test, tv, sv, k)}
    routing_ms = {}
    for name, path in (('zero-shot Qwen3-0.6B', zero_shot), ('fine-tuned Qwen3-0.6B', fine_tuned)):
        if path:
            methods[name], routing_ms[name] = prediction_picks(path, test)
    overlap = [i for i, r in enumerate(test) if len(r['agents']) > 1]
    single = [i for i, r in enumerate(test) if len(r['agents']) == 1]
    results = {}
    hits_by = {}
    for name, picks in methods.items():
        hits = [int(p in r['agents']) for r, p in zip(test, picks)]
        hits_by[name] = hits
        results[name] = {'accuracy': round(sum(hits) / len(hits), 3), 'ci95': bootstrap_ci(hits),
                         'single_label': round(sum(hits[i] for i in single) / len(single), 3),
                         'overlap': round(sum(hits[i] for i in overlap) / len(overlap), 3),
                         'routing_ms_median': routing_ms.get(name),
                         'confusions': dict(collections.Counter(f'{r["agents"]}->{p}' for r, p in zip(test, picks)
                                                                if p not in r['agents']))}
    knn_name = f'knn (k={k})'
    if 'fine-tuned Qwen3-0.6B' in hits_by:
        diff = [a - b for a, b in zip(hits_by[knn_name], hits_by['fine-tuned Qwen3-0.6B'])]
        rng = random.Random(1)
        means = sorted(sum(rng.choice(diff) for _ in diff) / len(diff) for _ in range(2000))
        results['knn minus fine-tuned'] = {'accuracy': round(sum(diff) / len(diff), 3),
                                           'ci95': [round(means[50], 3), round(means[1949], 3)]}
    summary = {'test_tasks': len(test), 'overlap_test_tasks': len(overlap), 'k': k, 'k_validation_accuracy': k_scores,
               'majority_agent': majority, 'results': results}
    out = pathlib.Path(out or ROOT / 'artifacts' / 'phase3' / 'agent-selection.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(f'Test tasks: {len(test)} ({len(overlap)} overlap). kNN k={k} from validation {k_scores}\n')
    print('| Method | Accuracy (95% CI) | Single-label | Overlap |')
    print('|---|---|---:|---:|')
    for name, r in results.items():
        if 'single_label' in r:
            print(f'| {name} | {r["accuracy"]:.3f} [{r["ci95"][0]:.2f}, {r["ci95"][1]:.2f}] | {r["single_label"]:.3f} | {r["overlap"]:.3f} |')
        else:
            print(f'| {name} | {r["accuracy"]:+.3f} [{r["ci95"][0]:+.2f}, {r["ci95"][1]:+.2f}] | | |')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['split', 'report'])
    parser.add_argument('--zero-shot', type=pathlib.Path)
    parser.add_argument('--fine-tuned', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.command == 'split':
        print(json.dumps(write_split(), indent=2))
    else:
        report(args.zero_shot, args.fine_tuned, args.out)


if __name__ == '__main__':
    main()
