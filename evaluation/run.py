"""Run all routing strategies over the frozen evaluation workload."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'benchmarking'))

from adapters.cmd import CommandCodeClient, provider_model_id
from baselines import MODELS, STRATEGIES, route
from scorers import score_case

BENCHMARK_VERSION = 'v1'
DECODING = {'temperature': 0}
SEED = 20260919
PRICES_PER_MILLION = {
    'glm-5.3-flash': {'input': .15, 'output': .50, 'cached_input': .03},
    'deepseek-v4.1-flash': {'input': .30, 'output': 1.20, 'cached_input': .006},
}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def hash_path(path):
    path = Path(path)
    digest = hashlib.sha256()
    files = [path] if path.is_file() else sorted(item for item in path.rglob('*') if item.is_file())
    for item in files:
        digest.update(str(item.relative_to(path.parent if path.is_file() else path)).encode())
        with item.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
    return digest.hexdigest()


def write_freeze_manifest(path, checkpoint, workload):
    sources = {
        'workload': workload,
        'profiles': ROOT / 'training-profiles.json',
        'checkpoint': checkpoint,
        'strategies_python': HERE / 'baselines.py',
        'strategies_typescript': ROOT / 'router.ts',
        'scorers': ROOT / 'benchmarking/scorers/__init__.py',
        'held_out_data': ROOT / 'data/test.jsonl',
    }
    manifest = {
        'status': 'frozen-before-held-out',
        'benchmark_version': BENCHMARK_VERSION,
        'seed': SEED,
        'strategies': list(STRATEGIES),
        'artifacts': {name: {
            'path': str(Path(source).resolve().relative_to(ROOT.resolve())),
            'sha256': hash_path(source),
        } for name, source in sources.items()},
    }
    path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def load_profiles():
    wanted = set(MODELS)
    return [item for item in json.loads((ROOT / 'training-profiles.json').read_text())
            if item['model_slug'] in wanted]


def cache_key(task, model):
    value = {'benchmark_version': BENCHMARK_VERSION, 'task_id': task['task_id'],
             'model_id': model, 'decoding': {**DECODING, 'max_tokens': task['max_tokens']}}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def calculate_cost(model, usage):
    price = PRICES_PER_MILLION[model]
    input_tokens = usage.get('prompt_tokens', 0) or 0
    output_tokens = usage.get('completion_tokens', 0) or 0
    cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0) or 0
    uncached = max(0, input_tokens - cached)
    return round((uncached * price['input'] + cached * price['cached_input']
                  + output_tokens * price['output']) / 1_000_000, 9)


class ExecutionCache:
    def __init__(self, directory, client=None, max_cost_usd=0):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.max_cost_usd = max_cost_usd
        self.spent_usd = 0
        self.hits = 0
        self.misses = 0

    def execute(self, task, model):
        path = self.directory / f'{cache_key(task, model)}.json'
        if path.exists():
            self.hits += 1
            return json.loads(path.read_text())
        if self.client is None:
            raise RuntimeError(f'Offline cache miss for {task["task_id"]} on {model}')
        projected = ((len(json.dumps(task['messages'])) / 4) * PRICES_PER_MILLION[model]['input']
                     + task['max_tokens'] * PRICES_PER_MILLION[model]['output']) / 1_000_000
        if self.spent_usd + projected > self.max_cost_usd:
            raise RuntimeError(f'Paid-call cap would be exceeded by {task["task_id"]} on {model}')
        case = {'messages': task['messages'], 'max_tokens': task['max_tokens']}
        if task.get('tools'):
            case['tools'] = task['tools']
        result = self.client.chat(provider_model_id(model), case)
        score = score_case(task, result)
        usage = result.get('usage') or {}
        output_tokens = usage.get('completion_tokens', 0) or 0
        latency = result.get('latency_ms', 0) or 0
        evidence = {
            'cache_key': path.stem, 'task_id': task['task_id'], 'model_slug': model,
            'success': score['passed'], 'score_detail': score['detail'],
            'execution_latency_ms': latency,
            'output_tokens': output_tokens,
            'token_rate': round(output_tokens / (latency / 1000), 3) if latency else None,
            'request_cost_usd': calculate_cost(model, usage),
            'usage': usage, 'result': result,
        }
        self.spent_usd += evidence['request_cost_usd']
        path.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
        self.misses += 1
        return evidence

    def import_benchmark_run(self, run_dir, workload):
        """Seed this cache from ticket 01 evidence without making a network call."""
        tasks = {task['task_id']: task for task in workload}
        imported = 0
        for model in MODELS:
            for task_id, task in tasks.items():
                source = run_dir / model / f'{task_id}.json'
                if not source.exists():
                    continue
                saved = json.loads(source.read_text())
                result = saved['result']
                usage = result.get('usage') or {}
                latency = result.get('latency_ms', 0) or 0
                output_tokens = usage.get('completion_tokens', 0) or 0
                evidence = {
                    'cache_key': cache_key(task, model), 'task_id': task_id, 'model_slug': model,
                    'success': saved['score']['passed'], 'score_detail': saved['score']['detail'],
                    'execution_latency_ms': latency, 'output_tokens': output_tokens,
                    'token_rate': round(output_tokens / (latency / 1000), 3) if latency else None,
                    'request_cost_usd': calculate_cost(model, usage), 'usage': usage, 'result': result,
                    'source_evidence': str(source),
                }
                destination = self.directory / f'{evidence["cache_key"]}.json'
                if not destination.exists():
                    destination.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
                    imported += 1
        return imported


def learned_callback(checkpoint):
    if checkpoint is None:
        return None
    sys.path.insert(0, str(ROOT / 'training'))
    from infer import Router
    from common import validate_output
    router = Router(checkpoint)

    def select(task, profiles):
        request = {'user_task': task['messages'][-1]['content'],
                   'candidate_models': [p['model_slug'] for p in profiles], 'profiles': profiles,
                   'requires_tools': task.get('requires_tools', False),
                   'input_tokens': task.get('input_tokens', 0)}
        return validate_output(router.generate(request), request)
    return select


def evaluate(workload, profiles, cache, checkpoint=None, strategies=STRATEGIES):
    learned = learned_callback(checkpoint)
    rows = []
    for index, task in enumerate(workload):
        outcomes = {model: cache.execute(task, model) for model in MODELS}
        for strategy in strategies:
            decision = route(strategy, task, profiles, index, SEED, learned, outcomes)
            evidence = outcomes[decision['model_slug']]
            rows.append({**decision,
                         'policy_agreement': decision['model_slug'] == task['policy_label'],
                         'success': evidence['success'],
                         'execution_latency_ms': evidence['execution_latency_ms'],
                         'token_rate': evidence['token_rate'],
                         'request_cost_usd': evidence['request_cost_usd'],
                         'execution_error': evidence['result'].get('error'),
                         'evidence': f'cache/{evidence["cache_key"]}.json'})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workload', type=Path, default=HERE / 'workload.jsonl')
    parser.add_argument('--cache', type=Path, default=HERE / 'cache')
    parser.add_argument('--output', type=Path, default=HERE / 'results.json')
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--benchmark-run', type=Path)
    parser.add_argument('--allow-paid-calls', action='store_true')
    parser.add_argument('--max-cost-usd', type=float, default=0)
    parser.add_argument('--freeze-manifest', type=Path, default=HERE / 'frozen-manifest.json')
    parser.add_argument('--freeze-only', action='store_true')
    parser.add_argument('--strategies', nargs='+', choices=STRATEGIES, default=list(STRATEGIES))
    args = parser.parse_args(argv)
    if ('learned' in args.strategies or args.freeze_only) and args.checkpoint is None:
        parser.error('--checkpoint is required when evaluating the learned strategy')
    if args.checkpoint is not None:
        write_freeze_manifest(args.freeze_manifest, args.checkpoint, args.workload)
    if args.freeze_only:
        print(f'Frozen artifact hashes written to {args.freeze_manifest}')
        return
    workload = read_jsonl(args.workload)
    if not 50 <= len(workload) <= 100:
        parser.error('The frozen workload must contain 50 to 100 tasks')
    if args.allow_paid_calls and args.max_cost_usd <= 0:
        parser.error('--allow-paid-calls requires a positive --max-cost-usd')
    if args.allow_paid_calls and not os.environ.get('CMD_API_KEY'):
        parser.error('--allow-paid-calls requires CMD_API_KEY')
    client = CommandCodeClient(os.environ['CMD_API_KEY']) if args.allow_paid_calls else None
    cache = ExecutionCache(args.cache, client, args.max_cost_usd)
    imported = cache.import_benchmark_run(args.benchmark_run, workload) if args.benchmark_run else 0
    rows = evaluate(workload, load_profiles(), cache, args.checkpoint, args.strategies)
    result = {'kind': 'validation', 'benchmark_version': BENCHMARK_VERSION, 'seed': SEED,
              'workload_sha256': hashlib.sha256(args.workload.read_bytes()).hexdigest(),
              'decoding': DECODING, 'prices_per_million_usd': PRICES_PER_MILLION,
              'cache': {'hits': cache.hits, 'misses': cache.misses, 'imported': imported},
              'paid_calls_enabled': args.allow_paid_calls, 'paid_call_cap_usd': args.max_cost_usd,
              'paid_call_cost_usd': round(cache.spent_usd, 9), 'rows': rows}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'{len(rows)} routes written to {args.output}; cache {cache.hits} hits, {cache.misses} misses')


if __name__ == '__main__':
    main()
