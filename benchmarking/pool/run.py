"""Run every pool model on a suite, then score the saved responses.

    .venv/bin/python benchmarking/pool/run.py call --suite pilot-v1
    .venv/bin/python benchmarking/pool/run.py call --resume benchmarking/results/<run>
    .venv/bin/python benchmarking/pool/run.py score benchmarking/results/<run>

`call` writes one JSON file per (model, case) and skips files that exist,
so a resumed run never repeats a paid call. `score` rewrites only the
`score` field and can be rerun after a scorer fix.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import pathlib
import random
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score import score  # noqa: E402

BASE_URL = os.environ.get('CMD_BASE_URL', 'https://api.commandcode.ai/provider/v1')
SUITES = HERE.parent / 'suites'
RESULTS = HERE.parent / 'results'

# USD per 1M tokens (input, output), Command Code GOAT plan page, 2026-10-28.
POOL = {
    'deepseek/deepseek-v4.1-flash': (0.15, 0.60),
    'z-ai/glm-5.3-flash': (0.15, 0.50),
    'ornith/ornith-1.5-122b': (0.16, 0.64),
    'xiaomi/mimo-v2.6-flash': (0.14, 0.28),
    'tencent/hy3-paid': (0.14, 0.58),
    'nvidia/nemotron-3.5-super-vl': (0.20, 0.50),
}
RETRY_WAITS = (5, 15, 45, 90)
_print_lock = threading.Lock()
_spend_lock = threading.Lock()
_spend = {'usd': 0.0, 'limit': None, 'stopped': None}


def log(*parts):
    with _print_lock:
        print(*parts, flush=True)


def load_suite(version):
    path = SUITES / f'{version}.jsonl'
    body = path.read_text()
    return [json.loads(line) for line in body.splitlines() if line.strip()], hashlib.sha256(body.encode()).hexdigest()


def model_dir(run_dir, model):
    return run_dir / model.replace('/', '__')


def _read_stream(response):
    """Assemble an OpenAI-style SSE stream into one message plus usage."""
    content, tool_calls, finish, usage, served, first_token = [], {}, None, {}, None, None
    for raw_line in response:
        line = raw_line.decode(errors='replace').strip()
        if not line.startswith('data:'):
            continue
        data = line[5:].strip()
        if data == '[DONE]':
            break
        chunk = json.loads(data)
        if chunk.get('error'):
            raise ValueError(f'stream error: {str(chunk["error"])[:200]}')
        served = chunk.get('model') or served
        usage = chunk.get('usage') or usage
        for choice in chunk.get('choices') or []:
            delta = choice.get('delta') or {}
            if first_token is None and (delta.get('content') or delta.get('reasoning') or delta.get('reasoning_content') or delta.get('tool_calls')):
                first_token = time.monotonic()
            if delta.get('content'):
                content.append(delta['content'])
            for call in delta.get('tool_calls') or []:
                slot = tool_calls.setdefault(call.get('index', 0), {'type': 'function', 'function': {'name': '', 'arguments': ''}})
                slot['id'] = call.get('id') or slot.get('id')
                fn = call.get('function') or {}
                slot['function']['name'] += fn.get('name') or ''
                slot['function']['arguments'] += fn.get('arguments') or ''
            finish = choice.get('finish_reason') or finish
    return {'content': ''.join(content) or None, 'tool_calls': [tool_calls[i] for i in sorted(tool_calls)],
            'finish_reason': finish, 'usage': usage, 'model': served, 'first_token': first_token}


def chat(api_key, model, case, timeout=900):
    # Streaming keeps the connection busy; a buffered request that thinks
    # longer than ~100 s is cut off by the gateway with HTTP 524.
    payload = {'model': model, 'messages': case['messages'], 'temperature': 0, 'max_tokens': case['max_tokens'],
               'stream': True, 'stream_options': {'include_usage': True}}
    if case.get('tools'):
        payload['tools'] = case['tools']
    request = urllib.request.Request(
        f'{BASE_URL}/chat/completions', data=json.dumps(payload).encode(), method='POST',
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}',
                 'User-Agent': 'agent-route-pool/1.0', 'Accept': 'text/event-stream'})
    last = None
    for wait in (*RETRY_WAITS, None):
        start = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                out = _read_stream(response)
            if out['finish_reason'] is None and not out['content'] and not out['tool_calls']:
                raise ValueError('empty stream')
            break
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors='replace')[:300]
            last = f'HTTP {error.code}: {body}'
            if error.code not in (408, 409, 429, 500, 502, 503, 504, 520, 522, 524) or wait is None:
                return {'error': last}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            last = f'{type(error).__name__}: {error}'
            if wait is None:
                return {'error': last}
        time.sleep(wait + random.random() * 3)
    end = time.monotonic()
    usage = out['usage']
    price_in, price_out = POOL[model]
    prompt_tokens = usage.get('prompt_tokens') or 0
    completion_tokens = usage.get('completion_tokens') or 0
    reasoning = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
    return {
        'content': out['content'],
        'tool_calls': out['tool_calls'],
        'finish_reason': out['finish_reason'],
        'latency_ms': round((end - start) * 1000),
        'ttft_ms': round((out['first_token'] - start) * 1000) if out['first_token'] else None,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'reasoning_tokens': reasoning,
        'cost_usd': round((prompt_tokens * price_in + completion_tokens * price_out) / 1e6, 7),
        'served_model': out['model'],
        'streamed': True,
    }


def call_one(api_key, run_dir, model, case):
    path = model_dir(run_dir, model) / f'{case["id"]}.json'
    if path.exists():
        return 'skip'
    if _spend['stopped']:
        return 'stopped'
    result = chat(api_key, model, case)
    record = {'case_id': case['id'], 'model': model, 'category': case['category'], 'source': case['source'],
              'called_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'result': result}
    # Errors are not cached: a later --resume retries them.
    if 'error' in result:
        log('ERROR', model, case['id'], result['error'][:160])
        if 'weekly usage limit' in result['error']:
            _spend['stopped'] = 'weekly limit'
        return 'error'
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    with _spend_lock:
        _spend['usd'] += result['cost_usd']
        if _spend['limit'] is not None and _spend['usd'] >= _spend['limit']:
            _spend['stopped'] = f'spend cap ${_spend["limit"]}'
    log(model, case['id'], f'{result["latency_ms"]}ms', f'{result["completion_tokens"]}tok', f'${result["cost_usd"]}')
    return 'ok'


def cmd_call(args):
    api_key = os.environ.get('CMD_API_KEY')
    if not api_key:
        raise SystemExit('Set CMD_API_KEY')
    if args.resume:
        run_dir = pathlib.Path(args.resume).resolve()
        meta = json.loads((run_dir / 'meta.json').read_text())
    else:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        run_dir = RESULTS / f'{args.suite}-{stamp}'
        run_dir.mkdir(parents=True)
        _, digest = load_suite(args.suite)
        meta = {'suite': args.suite, 'suite_sha256': digest, 'models': list(POOL), 'prices_per_mtok': POOL,
                'decoding': {'temperature': 0}, 'base_url': BASE_URL, 'started_at': stamp}
        (run_dir / 'meta.json').write_text(json.dumps(meta, indent=2) + '\n')
    cases, digest = load_suite(meta['suite'])
    if digest != meta['suite_sha256']:
        raise SystemExit('suite file changed since this run started')
    models = args.models.split(',') if args.models else meta['models']
    _spend['limit'] = args.max_usd
    for model in models:
        model_dir(run_dir, model).mkdir(exist_ok=True)
    jobs = [(m, c) for c in cases for m in models]
    counts = {}
    # One worker pool per model keeps a slow model from starving the others.
    pools = {m: concurrent.futures.ThreadPoolExecutor(args.per_model) for m in models}
    futures = [pools[m].submit(call_one, api_key, run_dir, m, c) for m, c in jobs]
    for future in concurrent.futures.as_completed(futures):
        status = future.result()
        counts[status] = counts.get(status, 0) + 1
    for pool in pools.values():
        pool.shutdown()
    log(json.dumps(counts), f'spent ${_spend["usd"]:.2f}', f'stopped: {_spend["stopped"]}', run_dir)


def cmd_score(args):
    run_dir = pathlib.Path(args.run).resolve()
    meta = json.loads((run_dir / 'meta.json').read_text())
    cases = {c['id']: c for c in load_suite(meta['suite'])[0]}
    paths = sorted(run_dir.glob('*__*/*.json'))

    def work(path):
        record = json.loads(path.read_text())
        if 'score' in record and not args.rescore:
            return
        record['score'] = score(cases[record['case_id']], record['result'])
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')

    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(work, paths))
    log(f'scored {len(paths)} records in {run_dir}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    call = sub.add_parser('call')
    call.add_argument('--suite')
    call.add_argument('--resume')
    call.add_argument('--models', help='comma-separated subset of the pool')
    call.add_argument('--per-model', type=int, default=4)
    call.add_argument('--max-usd', type=float, help='stop starting calls once this run has spent this much at list price')
    sc = sub.add_parser('score')
    sc.add_argument('run')
    sc.add_argument('--rescore', action='store_true')
    sc.add_argument('--workers', type=int, default=4)
    args = parser.parse_args(argv)
    if args.command == 'call':
        if not (args.suite or args.resume):
            parser.error('call needs --suite or --resume')
        cmd_call(args)
    else:
        cmd_score(args)


if __name__ == '__main__':
    main()
