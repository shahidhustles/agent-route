"""Outcome memory for the end-sem router: one record per recorded outcome, plus one embedding per task.

    .venv/bin/python routing/memory.py build

Sources:
- single-call runs `pilot-v1-20261028T040319Z` and `full-v1-20261028T050713Z` (agent `chat`), every scored call;
- agent runs `agents-v1-smoke1`, `agents-v1-full-20261028`, and the paid Command Code run `agents-cc-20261031`
  (model stored as the base ID, e.g. deepseek/deepseek-v4.1-flash, cost_usd from the host proxy; finished runs only; not-run rows are skipped,
  judge-pending runs keep passed=None).

Writes data/memory/records.jsonl (one outcome per line), data/memory/tasks.jsonl (task_id, dataset, split,
text) and data/memory/embeddings.npy (rows aligned with tasks.jsonl, BAAI/bge-small-en-v1.5, L2-normalised).
Single-call tasks carry their phase 1 split (data/outcome); agent tasks carry the agent split (data/agents) once
`routing/agents_eval.py split` has written it.
"""
import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'training'))
from outcome_data import task_text  # noqa: E402

RESULTS = ROOT / 'benchmarking' / 'results'
SUITES = ROOT / 'benchmarking' / 'suites'
OUT = ROOT / 'data' / 'memory'
EMBED_MODEL = 'BAAI/bge-small-en-v1.5'
SINGLE_CALL_RUNS = ['pilot-v1-20261028T040319Z', 'full-v1-20261028T050713Z']
AGENT_RUNS = ['agents-v1-smoke1', 'agents-v1-full-20261028', 'agents-cc-20261031']
AGENT_SUITE = SUITES / 'agents-v1.jsonl'
ROUTING_SUITE = SUITES / 'agents-routing-v2.jsonl'  # label-only tasks for the agent vote; no runs, held-out set kept out
CHAT = 'chat'
FIELDS = ['task_id', 'dataset', 'run', 'agent', 'model', 'passed', 'latency_s', 'input_tokens', 'output_tokens',
          'cost_usd']


def read_jsonl(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


def single_call_records(run_dir):
    """Every scored call in a pool run, as memory records, plus the task text per case."""
    meta = json.loads((run_dir / 'meta.json').read_text())
    cases = {c['id']: c for c in read_jsonl(SUITES / f'{meta["suite"]}.jsonl')}
    records, texts = [], {}
    for path in sorted(run_dir.glob('*__*/*.json')):
        r = json.loads(path.read_text())
        passed = (r.get('score') or {}).get('passed')
        if passed is None:
            continue
        res = r['result']
        records.append({'task_id': r['case_id'], 'dataset': meta['suite'], 'run': run_dir.name, 'agent': CHAT,
                        'model': r['model'], 'passed': bool(passed), 'latency_s': res['latency_ms'] / 1000,
                        'input_tokens': res.get('prompt_tokens', 0), 'output_tokens': res.get('completion_tokens', 0),
                        'cost_usd': res.get('cost_usd', 0.0)})
        texts[r['case_id']] = task_text(cases[r['case_id']])
    return records, texts


def agent_records(run_dir, suite):
    """Finished agent runs. Context tokens count fresh input plus cache reads; free models cost nothing, paid runs carry the proxy's cost."""
    records = []
    for r in read_jsonl(run_dir / 'runs.jsonl'):
        if r.get('not_run') or r['task_id'] not in suite:
            continue
        records.append({'task_id': r['task_id'], 'dataset': 'agents-v1', 'run': run_dir.name, 'agent': r['agent'],
                        'model': r['model'].removeprefix('cc/'), 'passed': r.get('passed'), 'latency_s': r['wall_s'],
                        'input_tokens': r.get('input_tokens', 0) + r.get('cache_read_tokens', 0),
                        'output_tokens': r.get('output_tokens', 0), 'cost_usd': r.get('cost_usd', 0.0)})
    return records


def load_splits():
    split = {}
    for name, rows in (('outcome', ROOT / 'data' / 'outcome'), ('agents', ROOT / 'data' / 'agents')):
        for part in ('train', 'validation', 'test'):
            path = rows / f'{part}.jsonl'
            if path.exists():
                for row in read_jsonl(path):
                    split[row['case_id']] = part
    return split


class Embedder:
    """bge-small sentence embeddings, cached by text hash so rebuilding memory does not re-encode."""

    def __init__(self, cache=OUT / 'embedding-cache.npz'):
        self.cache_path = pathlib.Path(cache)
        self.cache = {}
        if self.cache_path.exists():
            data = np.load(self.cache_path)
            self.cache = dict(zip(data['keys'].tolist(), data['vectors']))
        self.model = None

    @staticmethod
    def key(text):
        return hashlib.sha256(text.encode()).hexdigest()

    def encode(self, texts):
        missing = [t for t in dict.fromkeys(texts) if self.key(t) not in self.cache]
        if missing:
            if self.model is None:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(EMBED_MODEL)
            vecs = self.model.encode(missing, normalize_embeddings=True, batch_size=32)
            for t, v in zip(missing, vecs):
                self.cache[self.key(t)] = np.asarray(v, dtype=np.float32)
            self.save()
        return np.stack([self.cache[self.key(t)] for t in texts]) if texts else np.zeros((0, 384), np.float32)

    def save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        keys = list(self.cache)
        np.savez(self.cache_path, keys=np.array(keys), vectors=np.stack([self.cache[k] for k in keys]))


class Memory:
    """Outcome records plus a task_id -> embedding map. Appends go to an optional online JSONL file."""

    def __init__(self, records, tasks, vectors):
        self.records = list(records)
        self.tasks = {t['task_id']: t for t in tasks}
        self.vectors = {t['task_id']: v for t, v in zip(tasks, vectors)}

    @classmethod
    def load(cls, path=OUT, online=None):
        path = pathlib.Path(path)
        tasks = read_jsonl(path / 'tasks.jsonl')
        mem = cls(read_jsonl(path / 'records.jsonl'), tasks, np.load(path / 'embeddings.npy'))
        if online and pathlib.Path(online).exists():
            for row in read_jsonl(online):
                mem.add(row['record'], row.get('task'), np.asarray(row['embedding'], np.float32) if row.get('embedding') else None)
        return mem

    def add(self, record, task=None, vector=None):
        self.records.append(record)
        if task and record['task_id'] not in self.tasks:
            self.tasks[record['task_id']] = task
        if vector is not None and record['task_id'] not in self.vectors:
            self.vectors[record['task_id']] = vector

    def append_online(self, path, record, task, vector):
        """Add a finished run and persist it, so the next routing call sees it."""
        self.add(record, task, vector)
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as f:
            f.write(json.dumps({'record': record, 'task': task, 'embedding': [round(float(x), 6) for x in vector]}) + '\n')

    def select(self, **where):
        return [r for r in self.records if all(r.get(k) == v for k, v in where.items())]


def build(out=OUT):
    split = load_splits()
    records, texts = [], {}
    for run in SINGLE_CALL_RUNS:
        recs, t = single_call_records(RESULTS / run)
        records += recs
        texts.update(t)
    suite = {t['id']: t for t in read_jsonl(AGENT_SUITE)}
    for run in AGENT_RUNS:
        records += agent_records(RESULTS / run, suite)
    # agents-v1 prompts become tasks even without runs: agent selection votes over their gold labels.
    for tid, t in suite.items():
        texts[tid] = t['prompt']
    routing = {t['id']: t for t in read_jsonl(ROUTING_SUITE)} if ROUTING_SUITE.exists() else {}
    for tid, t in routing.items():
        texts[tid] = t['prompt']
    dataset = {r['task_id']: r['dataset'] for r in records}
    tasks = [{'task_id': tid, 'dataset': dataset.get(tid, 'agents-routing-v2' if tid in routing else 'agents-v1'), 'split': split.get(tid),
              'agents': (suite.get(tid) or routing.get(tid) or {}).get('agents'), 'text': text}
             for tid, text in sorted(texts.items())]
    vectors = Embedder(out / 'embedding-cache.npz').encode([t['text'] for t in tasks])
    out.mkdir(parents=True, exist_ok=True)
    (out / 'records.jsonl').write_text(''.join(json.dumps({k: r[k] for k in FIELDS}) + '\n' for r in records))
    (out / 'tasks.jsonl').write_text(''.join(json.dumps(t, ensure_ascii=False) + '\n' for t in tasks))
    np.save(out / 'embeddings.npy', vectors.astype(np.float32))
    by = {}
    for r in records:
        by.setdefault((r['run'], r['passed'] is not None), 0)
        by[(r['run'], r['passed'] is not None)] += 1
    summary = {'records': len(records), 'tasks': len(tasks),
               'by_run': {f'{run} ({"scored" if s else "awaiting judge"})': n for (run, s), n in sorted(by.items())}}
    (out / 'manifest.json').write_text(json.dumps({**summary, 'embed_model': EMBED_MODEL,
                                                   'sources': SINGLE_CALL_RUNS + AGENT_RUNS}, indent=2) + '\n')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['build', 'show'])
    args = parser.parse_args(argv)
    if args.command == 'build':
        print(json.dumps(build(), indent=2))
    else:
        mem = Memory.load()
        print(f'{len(mem.records)} records, {len(mem.tasks)} tasks, {len(mem.vectors)} embeddings')


if __name__ == '__main__':
    main()
