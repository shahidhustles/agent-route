"""Judge packets for the rubric-scored agents (docx, slides, map).

    .venv/bin/python agents/judge.py export <run-dir> --model opencode/deepseek-v4.1-flash-free
    (the judge reads <run-dir>/judge/<model>/packets.jsonl and writes verdicts.jsonl next to it; see agents/JUDGE.md)
    .venv/bin/python agents/judge.py import <run-dir> --model opencode/deepseek-v4.1-flash-free
    .venv/bin/python agents/judge.py merge <run-dir>     # after the runner has exited

Only runs that passed the automatic check get a packet; a failed check already fails the run.
Packets carry an opaque ID and no agent or model name; key.json maps IDs back and the judge never reads it.
`import` writes judge/judged.jsonl (one line per run). `merge` folds those verdicts into runs.jsonl, setting
passed = automatic check passed and judge score >= --pass-at. The runner appends to runs.jsonl while it runs,
so merge only once it has exited.
"""
import argparse
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
MAX_CHARS = 12000


def load_runs(run_dir):
    return [json.loads(l) for l in (run_dir / 'runs.jsonl').read_text().splitlines() if l.strip()]


def run_key(r):
    return f'{r["task_id"]}|{r["agent"]}|{r["model"]}'


def clip(text):
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + '\n[truncated]'


def round_coords(node):
    if isinstance(node, list):
        return [round_coords(n) for n in node]
    return round(node, 5) if isinstance(node, float) else node


def render_artifact(agent, ws):
    out = ws / 'out'
    if agent == 'docx':
        doc = json.loads((out / 'document.json').read_text())
        return clip(f'Title: {doc["title"]}\n\n{doc["markdown"]}')
    if agent == 'slides':
        deck = json.loads((out / 'slides.json').read_text())
        parts = []
        for i, s in enumerate(deck, 1):
            lines = [f'Slide {i}: {s["title"]}']
            if s.get('body'):
                lines.append(s['body'])
            lines += [f'- {b}' for b in s['bullets']]
            parts.append('\n'.join(lines))
        return clip('\n\n'.join(parts))
    if agent == 'map':
        col = json.loads((out / 'map.json').read_text())['collection']
        feats = []
        for f in col['features']:
            g = f['geometry']
            coords = round_coords(g['coordinates'])
            text = json.dumps(coords)
            if len(text) > 600:
                text = text[:600] + ' ...'
            feats.append(f'{g["type"]} {json.dumps(f.get("properties") or {}, ensure_ascii=False)} coordinates {text}')
        return clip('GeoJSON features, coordinates as [longitude, latitude]:\n' + '\n'.join(feats))
    raise ValueError(agent)


def model_dir(run_dir, model):
    return run_dir / 'judge' / model.split('/')[-1]


def cmd_export(args):
    run_dir = pathlib.Path(args.run).resolve()
    tasks = {}
    meta = json.loads((run_dir / 'meta.json').read_text())
    for line in (ROOT / meta['suite']).read_text().splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t['id']] = t
    packets, key = [], {}
    for r in load_runs(run_dir):
        if r['model'] != args.model or not r.get('needs_judge') or not (r.get('validator') or {}).get('passed'):
            continue
        pid = hashlib.sha256(f'{run_dir.name}:{run_key(r)}'.encode()).hexdigest()[:12]
        packets.append({'packet_id': pid, 'kind': r['agent'], 'request': tasks[r['task_id']]['prompt'],
                        'artifact': render_artifact(r['agent'], ROOT / r['artifact_dir'])})
        key[pid] = run_key(r)
    packets.sort(key=lambda p: p['packet_id'])
    d = model_dir(run_dir, args.model)
    d.mkdir(parents=True, exist_ok=True)
    (d / 'packets.jsonl').write_text(''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in packets))
    (d / 'key.json').write_text(json.dumps(key, indent=1) + '\n')
    kinds = {}
    for p in packets:
        kinds[p['kind']] = kinds.get(p['kind'], 0) + 1
    print(json.dumps(kinds), d / 'packets.jsonl')


def cmd_import(args):
    run_dir = pathlib.Path(args.run).resolve()
    d = model_dir(run_dir, args.model)
    key = json.loads((d / 'key.json').read_text())
    verdicts = {}
    for line in (d / 'verdicts.jsonl').read_text().splitlines():
        if line.strip():
            v = json.loads(line)
            verdicts[v['packet_id']] = v
    missing = sorted(set(key) - set(verdicts))
    if missing:
        raise SystemExit(f'{len(missing)} packets have no verdict, e.g. {missing[:3]}')
    judged_path = run_dir / 'judge' / 'judged.jsonl'
    judged = {}
    if judged_path.exists():
        for line in judged_path.read_text().splitlines():
            if line.strip():
                j = json.loads(line)
                judged[j['key']] = j
    for pid, k in key.items():
        v = verdicts[pid]
        score = int(v['score'])
        assert 1 <= score <= 10, v
        judged[k] = {'key': k, 'packet_id': pid, 'score': score, 'note': v.get('note', '')}
    judged_path.write_text(''.join(json.dumps(j, ensure_ascii=False) + '\n' for j in judged.values()))
    print(f'imported {len(key)} verdicts for {args.model}; {len(judged)} judged runs in total')


def cmd_merge(args):
    run_dir = pathlib.Path(args.run).resolve()
    judged = {}
    path = run_dir / 'judge' / 'judged.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                j = json.loads(line)
                judged[j['key']] = j
    runs = load_runs(run_dir)
    waiting = 0
    for r in runs:
        if not r.get('needs_judge') or r.get('not_run'):
            continue
        if not (r.get('validator') or {}).get('passed'):
            r['passed'] = False
            continue
        j = judged.get(run_key(r))
        if j is None:
            r['passed'] = None
            waiting += 1
            continue
        r['judge'] = {'score': j['score'], 'note': j['note'], 'judge_model': 'codex/gpt-6.1-sol (medium)'}
        r['passed'] = j['score'] >= args.pass_at
    (run_dir / 'runs.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in runs))
    print(f'merged {len(judged)} verdicts into {len(runs)} records; {waiting} judged runs still waiting')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('export', 'import'):
        p = sub.add_parser(name)
        p.add_argument('run')
        p.add_argument('--model', required=True)
    m = sub.add_parser('merge')
    m.add_argument('run')
    m.add_argument('--pass-at', type=int, default=7)
    args = parser.parse_args(argv)
    {'export': cmd_export, 'import': cmd_import, 'merge': cmd_merge}[args.command](args)


if __name__ == '__main__':
    main()
