"""Benchmark Command Code candidate models on a versioned suite.

Each run writes into an immutable directory under benchmarking/results/.
A rerun never overwrites an earlier run; --resume <dir> fills only the
missing case results and preserves all earlier evidence.
"""
import argparse
import datetime
import json
import os
import pathlib
import sys
import urllib.error

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from adapters.cmd import CommandCodeClient, provider_model_id
from scorers import score_case

SUITE_VERSION = 'v1'
MODELS = {
    'flash': 'glm-5.3-flash',
    'deepseek': 'deepseek-v4.1-flash',
}
ATTEMPTS = 2


def load_suite(version):
    path = HERE / 'suites' / f'{version}.jsonl'
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def create_run_dir(version):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_dir = HERE / 'results' / f'{version}-{stamp}-{os.urandom(2).hex()}'
    run_dir.mkdir(parents=True)
    return run_dir


def request_for(model, case, session_id):
    """The exact request minus authorization data, for saved evidence."""
    payload = {
        'model': model,
        'messages': case['messages'],
        'temperature': 0,
        'max_tokens': case['max_tokens'],
    }
    if case.get('tools'):
        payload['tools'] = case['tools']
    return {'payload': payload, 'session_id': session_id}


def call_case(client, model, case):
    last_error = None
    for _ in range(ATTEMPTS):
        try:
            return client.chat(model, case)
        except (urllib.error.URLError, OSError, KeyError, ValueError) as error:
            last_error = f'{type(error).__name__}: {error}'
    return {'error': last_error, 'content': None, 'tool_calls': [], 'usage': {}}


def run_model(client, model, cases, run_dir, log=lambda *_: None):
    model_dir = run_dir / model
    model_dir.mkdir(exist_ok=True)
    ran = skipped = 0
    for case in cases:
        session_id = f'{run_dir.name}-{model}-{case["id"]}'
        case_path = model_dir / f'{case["id"]}.json'
        if case_path.exists():
            skipped += 1
            continue
        request = request_for(provider_model_id(model), case, session_id)
        result = call_case(client, provider_model_id(model), case)
        scored = {'passed': False, 'detail': 'request failed'}
        if 'error' not in result:
            scored = score_case(case, result)
        case_path.write_text(json.dumps({
            'case_id': case['id'],
            'category': case['category'],
            'request': request,
            'result': result,
            'score': scored,
        }, indent=2) + '\n')
        ran += 1
        log(model, case['id'], scored)
    return ran, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', default='both',
                        help="flash, deepseek, or both")
    parser.add_argument('--suite', default=SUITE_VERSION)
    parser.add_argument('--resume', help='existing run directory to complete')
    parser.add_argument('--api-key-env', default='CMD_API_KEY')
    args = parser.parse_args(argv)

    models = [MODELS['flash'], MODELS['deepseek']] if args.models == 'both' else [MODELS[args.models]]
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f'Set {args.api_key_env} to the Command Code API key')

    run_dir = pathlib.Path(args.resume).resolve() if args.resume else create_run_dir(args.suite)
    if args.resume and not (run_dir / 'meta.json').exists():
        raise SystemExit(f'Not a benchmark run directory: {run_dir}')
    if not args.resume:
        cases = load_suite(args.suite)
        (run_dir / 'meta.json').write_text(json.dumps({
            'suite_version': args.suite,
            'suite_path': f'benchmarking/suites/{args.suite}.jsonl',
            'models': models,
            'decoding': {'temperature': 0, 'attempts': ATTEMPTS},
            'api_key_env': args.api_key_env,
            'headers_saved_redacted': True,
            'started_at': run_dir.name.split('-')[1],
        }, indent=2) + '\n')

    cases = load_suite(args.suite)
    client = CommandCodeClient(api_key)
    for model in models:
        def log(name, case_id, scored, _model=model):
            print(f'{_model} {case_id}: {"pass" if scored["passed"] else "FAIL"} {scored["detail"]}')
        ran, skipped = run_model(client, model, cases, run_dir, log)
        print(f'{model}: {ran} new, {skipped} reused')
    print(run_dir)
    return run_dir


if __name__ == '__main__':
    main()
