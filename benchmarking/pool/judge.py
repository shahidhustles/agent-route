"""Hand open-ended answers and math mismatches to an external judge, then import its verdicts.

    .venv/bin/python benchmarking/pool/judge.py export benchmarking/results/<run>
    (the judge reads judge/packets.jsonl and writes judge/verdicts.jsonl)
    .venv/bin/python benchmarking/pool/judge.py import benchmarking/results/<run>

Packets hide model identity: answers carry shuffled letters, and the
letter-to-model key stays in judge/key.json, which the judge never reads.
"""
import argparse
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import load_suite  # noqa: E402
from score import last_boxed  # noqa: E402

MAX_ANSWER_CHARS = 8000
LETTERS = 'ABCDEFGH'


def records(run_dir, models=None):
    for path in sorted(run_dir.glob('*__*/*.json')):
        record = json.loads(path.read_text())
        if models is None or record['model'] in models:
            yield path, record


def cmd_export(args):
    run_dir = pathlib.Path(args.run).resolve()
    meta = json.loads((run_dir / 'meta.json').read_text())
    cases = {c['id']: c for c in load_suite(meta['suite'])[0]}
    by_case = {}
    models = set(args.models.split(',')) if args.models else None
    for _, record in records(run_dir, models):
        by_case.setdefault(record['case_id'], []).append(record)
    rng = random.Random(f'judge:{run_dir.name}')
    packets, key = [], {}
    for case_id, recs in sorted(by_case.items()):
        case = cases[case_id]
        if case['scoring']['type'] == 'judge':
            rng.shuffle(recs)
            answers = {}
            for letter, rec in zip(LETTERS, recs):
                text = rec['result'].get('content') or ''
                answers[letter] = text[:MAX_ANSWER_CHARS] + ('\n[truncated]' if len(text) > MAX_ANSWER_CHARS else '')
                key[f'{case_id}:{letter}'] = rec['model']
            packets.append({'packet_id': case_id, 'kind': 'open_ended',
                            'prompt': case['messages'][-1]['content'], 'answers': answers})
        elif case['scoring']['type'] == 'math':
            for rec in recs:
                if not (rec.get('score') or {}).get('review'):
                    continue
                packet_id = f'{case_id}:{rec["model"]}'
                packets.append({'packet_id': packet_id, 'kind': 'math_equivalence',
                                'problem': case['messages'][-1]['content'],
                                'reference_answer': case['scoring']['answer'],
                                'model_answer': last_boxed(rec['result'].get('content') or '')})
    judge_dir = run_dir / 'judge'
    judge_dir.mkdir(exist_ok=True)
    (judge_dir / 'packets.jsonl').write_text(''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in packets))
    (judge_dir / 'key.json').write_text(json.dumps(key, indent=1) + '\n')
    kinds = {}
    for p in packets:
        kinds[p['kind']] = kinds.get(p['kind'], 0) + 1
    print(json.dumps(kinds), judge_dir / 'packets.jsonl')


def cmd_import(args):
    run_dir = pathlib.Path(args.run).resolve()
    judge_dir = run_dir / 'judge'
    key = json.loads((judge_dir / 'key.json').read_text())
    verdicts = {}
    for line in (judge_dir / 'verdicts.jsonl').read_text().splitlines():
        if line.strip():
            v = json.loads(line)
            verdicts[v['packet_id']] = v
    updated = missing = 0
    models = set(args.models.split(',')) if args.models else None
    for path, record in records(run_dir, models):
        score = record.get('score') or {}
        case_id, model = record['case_id'], record['model']
        new = None
        if score.get('detail') == 'awaiting judge' or score.get('judge'):
            letter = next((k.split(':')[-1] for k, m in key.items() if k.startswith(case_id + ':') and m == model), None)
            verdict = verdicts.get(case_id)
            if verdict and letter in verdict.get('scores', {}):
                rating = verdict['scores'][letter]
                new = {'passed': rating >= args.pass_at, 'detail': f'judge {rating}/10', 'judge': True,
                       'rating': rating, 'judge_note': verdict.get('notes', {}).get(letter)}
        elif score.get('review'):
            verdict = verdicts.get(f'{case_id}:{model}')
            if verdict:
                new = {**score, 'passed': bool(verdict['equivalent']), 'review': False,
                       'detail': score['detail'] + f' | judge: {"equivalent" if verdict["equivalent"] else "different"}'}
        if new is None:
            if score.get('detail') == 'awaiting judge' or score.get('review'):
                missing += 1
            continue
        record['score'] = new
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
        updated += 1
    print(f'updated {updated}, still waiting {missing}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    ex = sub.add_parser('export')
    ex.add_argument('run')
    ex.add_argument('--models', help='comma-separated models to include; others are left out of the packets')
    im = sub.add_parser('import')
    im.add_argument('run')
    im.add_argument('--models', help='comma-separated models to import verdicts for')
    im.add_argument('--pass-at', type=int, default=7)
    args = parser.parse_args(argv)
    {'export': cmd_export, 'import': cmd_import}[args.command](args)


if __name__ == '__main__':
    main()
