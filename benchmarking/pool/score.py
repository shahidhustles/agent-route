"""Deterministic scorers for pool suites.

score(case, result) returns {'passed': bool | None, 'detail': str, ...}.
passed is None when the case needs the LLM judge (open-ended tasks).
Math mismatches that still produced an answer carry review=True so the
judge can catch equivalent forms the string check misses.

Model-written code runs in the agent-route-sandbox Docker image with no
network, capped memory, CPU, and process count.
"""
import json
import pathlib
import re
import string
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from scorers.ifeval import follows_all  # noqa: E402

SANDBOX_IMAGE = 'agent-route-sandbox'

STDIO_HARNESS = r'''
import json, subprocess, sys
tests = json.load(open('tests.json'))
timeout = float(sys.argv[1])
for i, t in enumerate(tests):
    try:
        p = subprocess.run([sys.executable, 'solution.py'], input=t['input'], capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(json.dumps({'passed': False, 'detail': f'test {i}: timeout'})); sys.exit()
    got = [l.rstrip() for l in p.stdout.strip().splitlines()]
    want = [l.rstrip() for l in t['output'].strip().splitlines()]
    if p.returncode != 0 or got != want:
        reason = 'runtime error' if p.returncode else 'wrong answer'
        print(json.dumps({'passed': False, 'detail': f'test {i}: {reason}'})); sys.exit()
print(json.dumps({'passed': True, 'detail': f'{len(tests)} tests passed'}))
'''


def response_text(result):
    return result.get('content') or ''


def extract_code(text):
    blocks = re.findall(r'```(?:python|py)?\s*\n(.*?)```', text, re.S)
    return blocks[-1] if blocks else text


def _sandbox(files, command, timeout_s):
    with tempfile.TemporaryDirectory() as tmp:
        for name, body in files.items():
            pathlib.Path(tmp, name).write_text(body)
        argv = ['docker', 'run', '--rm', '--network', 'none', '--memory', '1g', '--cpus', '1',
                '--pids-limit', '64', '-v', f'{tmp}:/work:ro', '-w', '/work', SANDBOX_IMAGE, *command]
        try:
            return subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return None


def score_code_stdio(scoring, result):
    code = extract_code(response_text(result))
    if not code.strip():
        return {'passed': False, 'detail': 'no code'}
    per_test = scoring['timeout_s']
    budget = 60 + per_test * len(scoring['tests'])
    proc = _sandbox({'solution.py': code, 'tests.json': json.dumps(scoring['tests']), 'harness.py': STDIO_HARNESS},
                    ['python', 'harness.py', str(per_test)], budget)
    if proc is None:
        return {'passed': False, 'detail': 'sandbox timeout'}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {'passed': False, 'detail': f'harness error: {proc.stderr[-200:]}'}


def score_code_func(scoring, result):
    code = extract_code(response_text(result))
    if not code.strip():
        return {'passed': False, 'detail': 'no code'}
    proc = _sandbox({'main.py': f"{code}\n\n{scoring['test']}\n"}, ['python', 'main.py'], scoring['timeout_s'] + 30)
    if proc is None:
        return {'passed': False, 'detail': 'sandbox timeout'}
    if proc.returncode == 0:
        return {'passed': True, 'detail': 'tests passed'}
    return {'passed': False, 'detail': (proc.stderr.strip().splitlines() or ['failed'])[-1][:200]}


def last_boxed(text):
    start = text.rfind('\\boxed')
    if start < 0:
        return None
    i = text.find('{', start)
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(text)):
        depth += {'{': 1, '}': -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1:j]
    return None


def normalize_math(answer):
    s = answer.strip()
    s = re.sub(r'\\text\{(.*?)\}', r'\1', s)
    for token in ('\\$', '\\left', '\\right', '\\!', '\\,', '\\;', '$', '^\\circ', '^{\\circ}', '\\%', '%', ' '):
        s = s.replace(token, '')
    s = s.replace('\\dfrac', '\\frac').replace('\\tfrac', '\\frac')
    s = re.sub(r'\\frac(\d)(\d)', r'\\frac{\1}{\2}', s)
    s = s.rstrip('.')
    if re.fullmatch(r'-?[\d,]+(\.\d+)?', s):
        s = s.replace(',', '')
        s = str(float(s)).removesuffix('.0')
    return s


def score_math(scoring, result):
    text = response_text(result)
    got = last_boxed(text)
    if got is None:
        return {'passed': False, 'detail': 'no boxed answer'}
    ok = normalize_math(got) == normalize_math(scoring['answer'])
    return {'passed': ok, 'detail': f'got {got!r}, want {scoring["answer"]!r}', 'review': not ok}


def score_mcq(scoring, result):
    text = response_text(result)
    found = re.findall(r'Answer\s*[:：]\s*\**\(?([A-J])\b', text)
    if not found:
        return {'passed': False, 'detail': 'no answer letter'}
    got = found[-1]
    return {'passed': got == scoring['answer'], 'detail': f'got {got}, want {scoring["answer"]}'}


def score_ifeval(scoring, result, prompt):
    ok, each = follows_all(response_text(result), scoring['instruction_ids'], scoring['kwargs'], prompt)
    return {'passed': ok, 'detail': f'{sum(each)}/{len(each)} instructions followed'}


def _squad_norm(text):
    text = text.lower()
    text = ''.join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r'\b(a|an|the)\b', ' ', text)
    return ' '.join(text.split())


def _f1(pred, gold):
    p, g = pred.split(), gold.split()
    common = sum(min(p.count(w), g.count(w)) for w in set(p))
    if not common:
        return 0.0
    precision, recall = common / len(p), common / len(g)
    return 2 * precision * recall / (precision + recall)


def score_squad(scoring, result):
    pred = _squad_norm(response_text(result))
    if not scoring['answers']:
        ok = pred == 'unanswerable' or pred.startswith('unanswerable')
        return {'passed': ok, 'detail': 'unanswerable item'}
    if 'unanswerable' in pred.split()[:2]:
        return {'passed': False, 'detail': 'said unanswerable'}
    golds = [_squad_norm(a) for a in scoring['answers']]
    best = max(_f1(pred, g) for g in golds)
    contained = any(g and g in pred and len(pred.split()) <= 3 * len(g.split()) + 3 for g in golds)
    return {'passed': best >= 0.5 or contained, 'detail': f'f1 {best:.2f}'}


def _same_value(got, allowed):
    for want in allowed:
        if isinstance(want, str) and isinstance(got, str) and got.strip().lower() == want.strip().lower():
            return True
        if isinstance(want, bool) or isinstance(got, bool):
            if got is want:
                return True
            continue
        if isinstance(want, (int, float)) and isinstance(got, (int, float)) and float(got) == float(want):
            return True
        if isinstance(want, list) and isinstance(got, list) and len(want) == len(got) and all(
                _same_value(g, [w]) for g, w in zip(got, want)):
            return True
        if isinstance(want, dict) and isinstance(got, dict) and set(got) <= set(want) and all(
                _same_value(got[k], v if isinstance(v, list) else [v]) for k, v in got.items()):
            return True
        if got == want:
            return True
    return False


def score_bfcl(scoring, result):
    calls = result.get('tool_calls') or []
    truth = scoring['ground_truth']
    if len(calls) != len(truth):
        return {'passed': False, 'detail': f'{len(calls)} calls, want {len(truth)}'}
    call = calls[0].get('function', {})
    (want_name, want_args), = truth[0].items()
    if call.get('name') != want_name:
        return {'passed': False, 'detail': f'called {call.get("name")}, want {want_name}'}
    try:
        args = json.loads(call.get('arguments') or '{}')
    except json.JSONDecodeError:
        return {'passed': False, 'detail': 'arguments not JSON'}
    extra = set(args) - set(want_args)
    if extra:
        return {'passed': False, 'detail': f'unexpected args {sorted(extra)}'}
    for name, allowed in want_args.items():
        if name not in args:
            if '' not in allowed:
                return {'passed': False, 'detail': f'missing {name}'}
            continue
        if not _same_value(args[name], allowed):
            return {'passed': False, 'detail': f'{name}={args[name]!r} not in {allowed!r}'}
    return {'passed': True, 'detail': 'call matches'}


def score(case, result):
    if result.get('error'):
        return {'passed': False, 'detail': f'request failed: {result["error"][:120]}'}
    if result.get('finish_reason') == 'length' and case['scoring']['type'] != 'bfcl':
        truncated = True
    else:
        truncated = False
    scoring = case['scoring']
    kind = scoring['type']
    if kind == 'judge':
        out = {'passed': None, 'detail': 'awaiting judge'}
    elif kind == 'code_stdio':
        out = score_code_stdio(scoring, result)
    elif kind == 'code_func':
        out = score_code_func(scoring, result)
    elif kind == 'math':
        out = score_math(scoring, result)
    elif kind == 'mcq':
        out = score_mcq(scoring, result)
    elif kind == 'ifeval':
        out = score_ifeval(scoring, result, case['messages'][-1]['content'])
    elif kind == 'squad':
        out = score_squad(scoring, result)
    elif kind == 'bfcl':
        out = score_bfcl(scoring, result)
    else:
        raise ValueError(f'unknown scoring type {kind}')
    if truncated:
        out['truncated'] = True
    return out
