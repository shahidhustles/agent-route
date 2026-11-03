"""Compare label sets on validation with a cheap proxy: bge-small kNN vote predicts each label set,
then the vote's picks are scored on the recorded validation outcomes. No test data is read.

    .venv/bin/python training/compare_labels.py data/outcome-4m-ordered data/outcome-4m-cost data/outcome-4m-latency
"""
import collections
import json
import pathlib
import statistics
import sys

from sentence_transformers import SentenceTransformer


def load(d, split):
    return [json.loads(l) for l in (pathlib.Path(d) / f'{split}.jsonl').read_text().splitlines() if l.strip()]


def main(dirs, ks=(5, 10, 20)):
    emb_model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    for d in dirs:
        train, val = load(d, 'train'), load(d, 'validation')
        enc = lambda rows: emb_model.encode([r['input']['user_task'] for r in rows], normalize_embeddings=True)
        sims = enc(val) @ enc(train).T
        counts = collections.Counter(r['output'] for r in val)
        print(f'\n{d}  validation labels {dict(counts)}')
        for k in ks:
            picks = []
            for row_sims in sims:
                vote = collections.Counter()
                for i in row_sims.argsort()[::-1][:k]:
                    vote[train[i]['output']] += float(row_sims[i])
                picks.append(vote.most_common(1)[0][0])
            chosen = [r['outcomes'][p] for r, p in zip(val, picks)]
            agree = sum(p == r['output'] for p, r in zip(picks, val) if r['output']) / sum(1 for r in val if r['output'])
            print(f'  k={k:2d} label agreement {agree:.3f}  pass {statistics.mean(c["passed"] for c in chosen):.3f}  '
                  f'cost {statistics.mean(c["cost_usd"] for c in chosen):.5f}  median latency {statistics.median(c["latency_ms"] for c in chosen)/1000:.1f}s')
        majority = counts.most_common(1)[0][0]
        c = [r['outcomes'][majority] for r in val]
        print(f'  majority label ({majority}): agreement {counts[majority]/sum(counts.values()):.3f}  pass {statistics.mean(x["passed"] for x in c):.3f}')


if __name__ == '__main__':
    main(sys.argv[1:])
