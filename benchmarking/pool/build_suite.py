"""Sample a versioned task suite from public datasets.

Writes benchmarking/suites/<version>.jsonl. Every case carries a family ID
(the source dataset's own item ID), so later splits can keep a family in
exactly one of train, validation, or test.

    .venv/bin/python benchmarking/pool/build_suite.py --version pilot-v1 --scale 1
"""
import argparse
import base64
import hashlib
import io
import json
import pathlib
import pickle
import random
import zlib

from datasets import load_dataset
from huggingface_hub import hf_hub_download

HERE = pathlib.Path(__file__).resolve().parent
SUITES = HERE.parent / 'suites'

# Tasks per source at --scale 1 (the 200-task pilot).
PILOT_COUNTS = {
    'livecodebench': 25,
    'mbppplus': 10,
    'math500': 20,
    'gsm8k': 5,
    'mmlu_pro': 25,
    'ifeval': 20,
    'bfcl_simple': 15,
    'bfcl_multiple': 10,
    'squad_v2': 20,
    'longbench_v2': 15,
    'wildchat': 35,
}

# The training suite: harder items, more open-ended prompts (where the
# pilot found the largest model gaps), and no family shared with the pilot.
FULL_COUNTS = {
    'livecodebench': 120,
    'mbppplus': 20,
    'math500': 90,
    'gsm8k': 10,
    'mmlu_pro': 100,
    'ifeval': 80,
    'bfcl_simple': 10,
    'bfcl_multiple': 20,
    'bfcl_live_simple': 10,
    'bfcl_live_multiple': 20,
    'squad_v2': 40,
    'longbench_v2': 60,
    'wildchat': 220,
}
MIXES = {'pilot': PILOT_COUNTS, 'full': FULL_COUNTS}

# Set by main(): HARD skews sampling toward difficult items; EXCLUDE holds
# family IDs from earlier suites so no family appears in two suites.
HARD = False
EXCLUDE = set()


def fresh(source, rows, native_id):
    return [r for r in rows if f'{source}:{native_id(r)}' not in EXCLUDE]

MCQ_SUFFIX = 'Think it through, then end your reply with a final line of the form "Answer: X", where X is the option letter.'
MATH_SUFFIX = 'Solve the problem. Put the final answer alone inside \\boxed{}.'
CODE_SUFFIX = 'Write a complete Python 3 program that reads from standard input and writes to standard output. Reply with exactly one ```python code block.'


def user(content):
    return [{'role': 'user', 'content': content}]


def case(source, native_id, category, messages, scoring, max_tokens, **extra):
    return {
        'id': f'{source}-{native_id}',
        'family_id': f'{source}:{native_id}',
        'source': source,
        'category': category,
        'messages': messages,
        'max_tokens': max_tokens,
        'scoring': scoring,
        **extra,
    }


class _PlainUnpickler(pickle.Unpickler):
    """LiveCodeBench pickles plain strings; refuse anything that names a class."""

    def find_class(self, module, name):
        raise pickle.UnpicklingError(f'blocked global {module}.{name}')


def _lcb_private_tests(blob):
    raw = zlib.decompress(base64.b64decode(blob))
    return json.loads(_PlainUnpickler(io.BytesIO(raw)).load())


def livecodebench(rng, n):
    files = ['test5.jsonl', 'test6.jsonl'] if HARD else ['test6.jsonl']
    rows = [json.loads(line) for f in files
            for line in open(hf_hub_download('livecodebench/code_generation_lite', f, repo_type='dataset'))]
    # stdin problems only; LeetCode items need a functional harness.
    rows = fresh('livecodebench', [r for r in rows if r['platform'] == 'atcoder'], lambda r: r['question_id'])
    by_level = {level: [r for r in rows if r['difficulty'] == level] for level in ('easy', 'medium', 'hard')}
    want = {'easy': n // 6, 'medium': (3 * n) // 10} if HARD else {'easy': n // 4, 'medium': n // 2}
    want['hard'] = n - want['easy'] - want['medium']
    picked = [r for level, k in want.items() for r in rng.sample(by_level[level], min(k, len(by_level[level])))]
    out = []
    for r in picked:
        tests = json.loads(r['public_test_cases']) + _lcb_private_tests(r['private_test_cases'])
        tests = [{'input': t['input'], 'output': t['output']} for t in tests if t.get('testtype', 'stdin') == 'stdin']
        out.append(case('livecodebench', r['question_id'], 'coding',
                        user(f"{r['question_content']}\n\n{CODE_SUFFIX}"),
                        {'type': 'code_stdio', 'tests': tests, 'timeout_s': 6},
                        16384, difficulty=r['difficulty'], contest_date=r['contest_date']))
    return out


def mbppplus(rng, n):
    rows = fresh('mbppplus', list(load_dataset('evalplus/mbppplus', split='test')), lambda r: r['task_id'])
    out = []
    for r in rng.sample(rows, n):
        prompt = (f"{r['prompt']}\n\nYour function must pass this test:\n{r['test_list'][0]}\n\n"
                  'Reply with exactly one ```python code block containing the function and any imports it needs.')
        out.append(case('mbppplus', r['task_id'], 'coding', user(prompt),
                        {'type': 'code_func', 'test': r['test'], 'timeout_s': 20}, 8192))
    return out


def math500(rng, n):
    rows = [r for r in load_dataset('HuggingFaceH4/MATH-500', split='test') if r['level'] >= 3]
    rows = fresh('math500', rows, lambda r: r['unique_id'].replace('/', '_').removesuffix('.json'))
    if HARD:
        picked = rng.sample([r for r in rows if r['level'] == 5], (4 * n) // 5)
        picked += rng.sample([r for r in rows if r['level'] == 4], n - len(picked))
    else:
        hard = [r for r in rows if r['level'] >= 4]
        picked = rng.sample(hard, (3 * n) // 4)
        picked += rng.sample([r for r in rows if r['level'] == 3], n - len(picked))
    return [case('math500', r['unique_id'].replace('/', '_').removesuffix('.json'), 'math',
                 user(f"{r['problem']}\n\n{MATH_SUFFIX}"),
                 {'type': 'math', 'answer': r['answer']}, 16384, level=r['level'])
            for r in picked]


def gsm8k(rng, n):
    rows = fresh('gsm8k', list(enumerate(load_dataset('openai/gsm8k', 'main', split='test'))), lambda r: r[0])
    return [case('gsm8k', i, 'math', user(f"{r['question']}\n\n{MATH_SUFFIX}"),
                 {'type': 'math', 'answer': r['answer'].split('####')[-1].strip()}, 8192)
            for i, r in rng.sample(rows, n)]


def _mcq_text(question, options):
    letters = 'ABCDEFGHIJ'
    lines = '\n'.join(f'{letters[i]}) {opt}' for i, opt in enumerate(options))
    return f'{question}\n\n{lines}\n\n{MCQ_SUFFIX}'


def mmlu_pro(rng, n):
    rows = fresh('mmlu_pro', list(load_dataset('TIGER-Lab/MMLU-Pro', split='test')), lambda r: r['question_id'])
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r['category'], []).append(r)
    cats = sorted(by_cat)
    if HARD:
        # Round-robin over subjects without replacement.
        for cat in cats:
            rng.shuffle(by_cat[cat])
        picked = [by_cat[cats[i % len(cats)]][i // len(cats)] for i in range(n)]
    else:
        picked = [rng.choice(by_cat[cats[i % len(cats)]]) for i in range(n)]
    return [case('mmlu_pro', r['question_id'], 'reasoning', user(_mcq_text(r['question'], r['options'])),
                 {'type': 'mcq', 'answer': r['answer']}, 16384, subject=r['category'])
            for r in picked]


def ifeval(rng, n):
    rows = fresh('ifeval', list(load_dataset('google/IFEval', split='train')), lambda r: r['key'])
    return [case('ifeval', r['key'], 'instruction_following', user(r['prompt']),
                 {'type': 'ifeval', 'instruction_ids': r['instruction_id_list'], 'kwargs': r['kwargs']}, 8192)
            for r in rng.sample(rows, n)]


_BFCL_TYPES = {'dict': 'object', 'float': 'number', 'tuple': 'array', 'any': 'string'}


def _openai_schema(node):
    if isinstance(node, dict):
        fixed = {k: _openai_schema(v) for k, v in node.items()}
        if isinstance(fixed.get('type'), str):
            fixed['type'] = _BFCL_TYPES.get(fixed['type'], fixed['type'])
        return fixed
    if isinstance(node, list):
        return [_openai_schema(v) for v in node]
    return node


def _bfcl(rng, n, split):
    repo = 'gorilla-llm/Berkeley-Function-Calling-Leaderboard'
    questions = [json.loads(l) for l in open(hf_hub_download(repo, f'BFCL_v3_{split}.json', repo_type='dataset'))]
    questions = fresh(f'bfcl_{split}', questions, lambda q: q['id'])
    answers = {a['id']: a['ground_truth'] for a in
               (json.loads(l) for l in open(hf_hub_download(repo, f'possible_answer/BFCL_v3_{split}.json', repo_type='dataset')))}
    out = []
    for q in rng.sample(questions, n):
        tools = [{'type': 'function', 'function': {
            # OpenAI-style APIs reject dots in function names.
            'name': f['name'].replace('.', '_'),
            'description': f['description'],
            'parameters': _openai_schema(f['parameters']),
        }} for f in q['function']]
        truth = [{name.replace('.', '_'): args for name, args in call.items()} for call in answers[q['id']]]
        out.append(case(f'bfcl_{split}', q['id'], 'tool_use', q['question'][0],
                        {'type': 'bfcl', 'ground_truth': truth}, 4096, tools=tools))
    return out


def squad_v2(rng, n):
    rows = fresh('squad_v2', list(load_dataset('rajpurkar/squad_v2', split='validation')), lambda r: r['id'])
    answerable = [r for r in rows if r['answers']['text']]
    unanswerable = [r for r in rows if not r['answers']['text']]
    picked = rng.sample(answerable, n - n // 4) + rng.sample(unanswerable, n // 4)
    out = []
    for r in picked:
        prompt = (f"Passage:\n{r['context']}\n\nQuestion: {r['question']}\n\n"
                  'Answer with a short span copied from the passage. If the passage does not contain the answer, reply exactly: unanswerable')
        out.append(case('squad_v2', r['id'], 'document_qa', user(prompt),
                        {'type': 'squad', 'answers': r['answers']['text']}, 4096))
    return out


def longbench_v2(rng, n):
    # About 50k tokens at most, inside every pool model's context window.
    rows = [r for r in load_dataset('THUDM/LongBench-v2', split='train')
            if (HARD or r['length'] == 'short') and len(r['context']) <= 200_000]
    rows = fresh('longbench_v2', rows, lambda r: r['_id'])
    out = []
    for r in rng.sample(rows, n):
        options = [r['choice_A'], r['choice_B'], r['choice_C'], r['choice_D']]
        prompt = f"Read the document and answer the question.\n\n<document>\n{r['context']}\n</document>\n\n" + _mcq_text(r['question'], options)
        out.append(case('longbench_v2', r['_id'], 'long_context', user(prompt),
                        {'type': 'mcq', 'answer': r['answer']}, 16384, domain=r['domain'], difficulty=r['difficulty']))
    return out


def wildchat(rng, n):
    stream = load_dataset('allenai/WildChat-1M', split='train', streaming=True)
    pool, seen = [], set()
    for r in stream:
        if r['language'] != 'English' or r['toxic'] or r['redacted'] or r['turn'] != 1:
            continue
        text = r['conversation'][0]['content'].strip()
        key = hashlib.sha1(text.lower().encode()).hexdigest()
        if not 40 <= len(text) <= 2500 or key in seen or f"wildchat:{r['conversation_hash']}" in EXCLUDE:
            continue
        seen.add(key)
        pool.append((r['conversation_hash'], text))
        if len(pool) >= n * 40:
            break
    return [case('wildchat', h, 'open_ended', user(text), {'type': 'judge'}, 8192)
            for h, text in rng.sample(pool, n)]


BUILDERS = {
    'livecodebench': livecodebench, 'mbppplus': mbppplus, 'math500': math500, 'gsm8k': gsm8k,
    'mmlu_pro': mmlu_pro, 'ifeval': ifeval,
    'bfcl_simple': lambda rng, n: _bfcl(rng, n, 'simple'),
    'bfcl_multiple': lambda rng, n: _bfcl(rng, n, 'multiple'),
    'bfcl_live_simple': lambda rng, n: _bfcl(rng, n, 'live_simple'),
    'bfcl_live_multiple': lambda rng, n: _bfcl(rng, n, 'live_multiple'),
    'squad_v2': squad_v2, 'longbench_v2': longbench_v2, 'wildchat': wildchat,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--scale', type=float, default=1.0)
    parser.add_argument('--seed', type=int, default=20261028)
    parser.add_argument('--mix', choices=sorted(MIXES), default='pilot')
    parser.add_argument('--hard', action='store_true', help='skew sampling toward difficult items')
    parser.add_argument('--exclude', nargs='*', default=[], help='earlier suite versions whose families to skip')
    args = parser.parse_args(argv)
    global HARD
    HARD = args.hard
    for version in args.exclude:
        for line in (SUITES / f'{version}.jsonl').read_text().splitlines():
            if line.strip():
                EXCLUDE.add(json.loads(line)['family_id'])
    counts = MIXES[args.mix]

    path = SUITES / f'{args.version}.jsonl'
    if path.exists():
        raise SystemExit(f'{path} exists; suites are immutable, pick a new version')
    cases = []
    for source, count in counts.items():
        rng = random.Random(f'{args.seed}:{source}')
        got = BUILDERS[source](rng, max(1, round(count * args.scale)))
        print(f'{source}: {len(got)}')
        cases.extend(got)
    ids = [c['id'] for c in cases]
    assert len(ids) == len(set(ids)), 'duplicate case IDs'
    body = ''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases)
    path.write_text(body)
    manifest = {'version': args.version, 'seed': args.seed, 'scale': args.scale, 'mix': args.mix, 'hard': args.hard,
                'excluded_suites': args.exclude, 'counts': counts,
                'cases': len(cases), 'sha256': hashlib.sha256(body.encode()).hexdigest()}
    path.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{len(cases)} cases -> {path}')


if __name__ == '__main__':
    main()
