"""Run phase 2 agents on a task suite inside the Docker sandbox.

    .venv/bin/python agents/run.py --suite benchmarking/suites/agents-v1.jsonl --run-dir benchmarking/results/agents-v1-smoke \
        --models opencode/deepseek-v4.1-flash-free --tasks code-001,sheet-001

Each (task, agent, model) runs once: `opencode run --agent <agent> -m <model> --format json` in a fresh
agent-route-opencode container whose only mount is the run's workspace (plus the agent configs, read-only).
Records go to <run-dir>/runs.jsonl, one line per run. A rerun skips every key already recorded, so runs are
resumable. Rate-limited runs are retried with backoff and never recorded as finished; if a model stays
rate-limited, the runner stops that model and says how far it got.

Order: --order task (default) finishes every model on a task before the next task starts, rotating through the
agents, so a run cut short by a cap leaves complete rows. --order model runs model by model (in --models order),
so a run cut short by limits still has complete data for the earlier models.

Command Code models (`cc/<model id>`, e.g. cc/deepseek/deepseek-v4.1-flash) are paid. They use the custom `cc` provider
in agents/opencode/opencode.json (OpenAI-compatible). The @gururea plugin does not load in OpenCode 2.1.4, and the
built-in commandcode catalog lacks MiMo V2.6 Flash and Nemotron 3.5 Super VL. The container reaches them
through agents/cmdproxy.py, which runs in this process, holds the API key (read from --env-file, never passed to a
container), and enforces --max-usd and the provider's weekly limit. Runs that hit a cap are discarded, not recorded.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import threading
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import cmdproxy  # noqa: E402
from validators import JUDGED, validate  # noqa: E402

IMAGE = 'agent-route-opencode'
FREE_MODELS = [
    'opencode/deepseek-v4.1-flash-free',
    'opencode/nemotron-3.5-super-vl-free',
    'opencode/glm-5.3-flash-free',
    'opencode/mimo-v2.6-flash-free',
]
CC_MODELS = [
    'cc/deepseek/deepseek-v4.1-flash',
    'cc/z-ai/glm-5.3-flash',
    'cc/xiaomi/mimo-v2.6-flash',
    'cc/nvidia/nemotron-3.5-super-vl',
]
STOP_MARKERS = (cmdproxy.CAP_MARKER, cmdproxy.WEEKLY_MARKER)
RATE_LIMIT_MARKERS = ('FreeUsageLimitError', 'rate limit', 'rate_limit', 'Rate limit', 'Too Many Requests', '429',
                      'quota', 'usage limit')


def load_suite(path):
    tasks = [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    return tasks


def run_key(task_id, agent, model):
    return f'{task_id}|{agent}|{model}'


def plan(tasks, models, agents=None, order='model'):
    """Runs to do. `model` order: model, task, agent. `task` order: tasks rotate through the agents (first task of
    every agent, then the second of every agent, ...) and each (task, agent) runs on every model back to back."""
    pairs = [(t, a) for t in tasks for a in t['agents'] if not agents or a in agents]
    if order == 'task':
        rank, seen = {}, {}
        for t, a in pairs:
            rank[(t['id'], a)] = seen[a] = seen.get(a, -1) + 1
        pairs.sort(key=lambda ta: (rank[(ta[0]['id'], ta[1])], ta[1]))
        for t, a in pairs:
            for model in models:
                yield t, a, model
    else:
        for model in models:
            for t, a in pairs:
                yield t, a, model


def parse_events(stdout):
    stats = {'model_calls': 0, 'input_tokens': 0, 'cache_read_tokens': 0, 'cache_write_tokens': 0,
             'output_tokens': 0, 'reasoning_tokens': 0, 'tool_calls': 0, 'errors': [], 'final_text': ''}
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = ev.get('type')
        part = ev.get('part') or {}
        if kind == 'step_finish':
            tok = part.get('tokens') or {}
            stats['model_calls'] += 1
            stats['input_tokens'] += tok.get('input', 0)
            stats['output_tokens'] += tok.get('output', 0)
            stats['reasoning_tokens'] += tok.get('reasoning', 0)
            stats['cache_read_tokens'] += (tok.get('cache') or {}).get('read', 0)
            stats['cache_write_tokens'] += (tok.get('cache') or {}).get('write', 0)
        elif kind == 'tool_use':
            stats['tool_calls'] += 1
        elif kind == 'text':
            stats['final_text'] = part.get('text', '')[-500:]
        elif kind == 'error':
            err = ev.get('error') or {}
            stats['errors'].append(f"{err.get('type', '?')}: {str(err.get('message') or err.get('data') or err)[:300]}")
    return stats


def is_rate_limited(text):
    return any(m in text for m in RATE_LIMIT_MARKERS)


def prepare_workspace(ws, task):
    if ws.exists():
        shutil.rmtree(ws)
    (ws / 'out').mkdir(parents=True)
    if task.get('inputs'):
        (ws / 'inputs').mkdir()
        for name, body in task['inputs'].items():
            (ws / 'inputs' / name).write_text(body)


def docker_argv(name, ws, agent, model, prompt, env=None, contract='json'):
    """The `docker run` command for one agent run.

    `json` is the contract of the recorded suite `agents-cc-20261031`: the agent prompts in `opencode/agent-json` and
    our own skills. `files` is the live contract: prompts in `opencode/agent` and Anthropic's skills (fetched by
    `sandbox/fetch_skills.sh` into `opencode/skills-files`). LibreOffice and Node need more memory and processes.
    """
    cfg = '/home/runner/.config/opencode'
    env_args = [a for k, v in (env or {}).items() for a in ('-e', f'{k}={v}')]
    files = contract == 'files'
    agents_dir, skills_dir = (('agent', 'skills-files') if files else ('agent-json', 'skills'))
    limits = ['--memory', '3g', '--cpus', '2', '--pids-limit', '512'] if files else ['--memory', '2g', '--cpus', '2', '--pids-limit', '256']
    return ['docker', 'run', '--rm', '--name', name, *limits, *env_args,
            '-v', f'{ws}:/work',
            '-v', f'{HERE / "opencode" / agents_dir}:{cfg}/agent:ro',
            '-v', f'{HERE / "opencode" / skills_dir}:{cfg}/skills:ro',
            '-v', f'{HERE / "opencode" / "opencode.json"}:{cfg}/opencode.json:ro',
            IMAGE, 'opencode', 'run', '--standalone', '--agent', agent, '-m', model, '--format', 'json', '--auto', '--thinking',
            prompt]


def run_once(task, agent, model, ws, timeout_s, env=None):
    prepare_workspace(ws, task)
    name = f'ar-{uuid.uuid4().hex[:12]}'
    start = time.time()
    timed_out = False
    try:
        proc = subprocess.run(docker_argv(name, ws, agent, model, task['prompt'], env), capture_output=True, text=True,
                              timeout=timeout_s)
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        subprocess.run(['docker', 'kill', name], capture_output=True)
        stdout = (e.stdout or b'').decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
        stderr = (e.stderr or b'').decode() if isinstance(e.stderr, bytes) else (e.stderr or '')
        code, timed_out = None, True
    wall = time.time() - start
    (ws.parent / f'{ws.name}.events.jsonl').write_text(stdout)
    if stderr.strip():
        (ws.parent / f'{ws.name}.stderr.txt').write_text(stderr[-20000:])
    return stdout, stderr, code, timed_out, wall


class Runner:
    def __init__(self, args, proxy=None):
        self.args = args
        self.proxy = proxy
        self.run_dir = pathlib.Path(args.run_dir).resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.memory = self.run_dir / 'runs.jsonl'
        self.lock = threading.Lock()
        self.done = set()
        if self.memory.exists():
            records = [json.loads(l) for l in self.memory.read_text().splitlines() if l.strip()]
            if args.retry_not_run:
                # Drop rows written when limits stopped a model, so those runs go again.
                kept = [r for r in records if not r.get('not_run')]
                print(f'retrying {len(records) - len(kept)} not-run records', flush=True)
                self.memory.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in kept))
                records = kept
            for r in records:
                self.done.add(run_key(r['task_id'], r['agent'], r['model']))
        self.blocked = {}  # model -> reason, once a model stays rate-limited

    def record(self, rec):
        with self.lock:
            with self.memory.open('a') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            self.done.add(run_key(rec['task_id'], rec['agent'], rec['model']))

    def execute(self, task, agent, model):
        key = run_key(task['id'], agent, model)
        if key in self.done or model in self.blocked:
            return None
        ws = self.run_dir / 'work' / model.split('/')[-1] / agent / task['id']
        paid = model.startswith('cc/')
        delay = self.args.backoff_s
        for attempt in range(1, self.args.max_attempts + 1):
            if model in self.blocked or (paid and self.proxy.stopped):
                return None
            env, token = None, None
            if paid:
                token = self.proxy.new_token()
                env = {'CC_BASE_URL': self.proxy.url, 'CC_RUN_TOKEN': token}
            stdout, stderr, code, timed_out, wall = run_once(task, agent, model, ws, self.args.timeout_s, env)
            usage = self.proxy.take(token) if paid else None
            stats = parse_events(stdout)
            err_text = ' '.join(stats['errors']) + ' ' + stderr[-2000:]
            if paid and (self.proxy.stopped or any(m in err_text for m in STOP_MARKERS)):
                # A cap or weekly limit ended this run: its data is partial, so discard it. The ledger keeps the spend.
                self.proxy.stopped = self.proxy.stopped or cmdproxy.WEEKLY_MARKER
                print(f'  discarded {key}: {self.proxy.stopped}', flush=True)
                return None
            if stats['errors'] and is_rate_limited(err_text) and not timed_out:
                print(f'  rate-limited {key} (attempt {attempt}), sleeping {delay}s', flush=True)
                time.sleep(delay)
                delay = min(delay * 2, 900)
                continue
            break
        else:
            self.blocked[model] = f'rate-limited after {self.args.max_attempts} attempts: {err_text.strip()[:200]}'
            print(f'  stopping {model}: {self.blocked[model]}', flush=True)
            return None
        check = task['checks'][agent]
        result = validate(agent, check, ws)
        rec = {
            'task_id': task['id'], 'agent': agent, 'model': model, 'gold_agents': task['agents'],
            'overlap': len(task['agents']) > 1, 'attempts': attempt,
            'artifact_dir': str(ws.relative_to(ROOT)),
            'validator': result, 'needs_judge': agent in JUDGED,
            'passed': bool(result['passed']) if agent not in JUDGED else None,
            'wall_s': round(wall, 2), 'exit_code': code, 'timed_out': timed_out,
            **{k: v for k, v in stats.items() if k != 'errors'},
            'errors': stats['errors'][:5],
            **({'cost_usd': round(usage['usd'], 6), 'proxy_requests': usage['requests'],
                'proxy_prompt_tokens': usage['prompt_tokens'], 'proxy_cached_tokens': usage['cached_tokens'],
                'proxy_completion_tokens': usage['completion_tokens'], 'usage_missing': usage['usage_missing']}
               if usage else {}),
            'finished_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        if agent in JUDGED and not result['passed']:
            rec['passed'] = False  # failed the automatic part; the judge cannot rescue it
        self.record(rec)
        mark = {True: 'pass', False: 'FAIL', None: 'judge'}[rec['passed']]
        cost = f' ${rec["cost_usd"]:.4f} (total ${self.proxy.spent:.3f})' if usage else ''
        print(f'{mark:5} {key} {wall:6.1f}s{cost} calls={stats["model_calls"]} in={stats["input_tokens"]}+{stats["cache_read_tokens"]}c '
              f'out={stats["output_tokens"]} {result["detail"][:90]}', flush=True)
        return rec


def finalize(runner, items):
    """Write an error record for every planned run that has none, so the run accounts for every key."""
    n = 0
    for task, agent, model in items:
        if run_key(task['id'], agent, model) in runner.done:
            continue
        reason = runner.blocked.get(model) or runner.args.finalize_reason
        runner.record({'task_id': task['id'], 'agent': agent, 'model': model, 'gold_agents': task['agents'],
                       'overlap': len(task['agents']) > 1, 'passed': None, 'not_run': True, 'error': reason,
                       'finished_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        n += 1
    print(f'wrote {n} not-run records')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--suite', required=True)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--models', default=','.join(FREE_MODELS), help='"cc" expands to the four Command Code models')
    parser.add_argument('--order', choices=['task', 'model'], default='task')
    parser.add_argument('--max-usd', type=float, help='cap on Command Code spend, summed over the ledger file')
    parser.add_argument('--ledger', default=str(ROOT / 'benchmarking' / 'results' / 'agents-cc-ledger.jsonl'))
    parser.add_argument('--cached-rate', type=float, default=0.25,
                        help='cached input tokens are counted at this fraction of the input price')
    parser.add_argument('--env-file', default=str(ROOT / '.env.modal'))
    parser.add_argument('--agents', help='comma-separated agent filter')
    parser.add_argument('--tasks', help='comma-separated task ID filter')
    parser.add_argument('--concurrency', type=int, default=3)
    parser.add_argument('--timeout-s', type=int, default=900)
    parser.add_argument('--max-attempts', type=int, default=5)
    parser.add_argument('--backoff-s', type=int, default=60)
    parser.add_argument('--finalize', action='store_true', help='record every missing planned run as not run')
    parser.add_argument('--retry-not-run', action='store_true', help='drop not-run records and run those keys again')
    parser.add_argument('--finalize-reason', default='not run: free-model limits stopped the run')
    args = parser.parse_args(argv)

    suite_path = pathlib.Path(args.suite).resolve()
    tasks = load_suite(suite_path)
    if args.tasks:
        keep = set(args.tasks.split(','))
        order = args.tasks.split(',')
        tasks = sorted((t for t in tasks if t['id'] in keep), key=lambda t: order.index(t['id']))
    models = CC_MODELS if args.models == 'cc' else args.models.split(',')
    agents = set(args.agents.split(',')) if args.agents else None
    proxy = None
    if any(m.startswith('cc/') for m in models):
        if args.max_usd is None:
            parser.error('Command Code models need --max-usd')
        key = cmdproxy.read_env(args.env_file, 'CMD_API_KEY')
        if not key:
            parser.error(f'CMD_API_KEY missing from {args.env_file}')
        proxy = cmdproxy.Proxy(key, args.max_usd, args.ledger, base_url=cmdproxy.read_env(args.env_file, 'CMD_BASE_URL') or cmdproxy.DEFAULT_BASE,
                               cached_rate=args.cached_rate)
        print(f'proxy {proxy.url}; ledger spend so far USD {proxy.spent:.4f} of {args.max_usd}; cached input at '
              f'{args.cached_rate:g} x input price', flush=True)
    runner = Runner(args, proxy)
    meta = runner.run_dir / 'meta.json'
    if not meta.exists():
        meta.write_text(json.dumps({'suite': str(suite_path.relative_to(ROOT)),
                                    'suite_sha256': hashlib.sha256(suite_path.read_bytes()).hexdigest(),
                                    'models': models, 'order': args.order, 'max_usd': args.max_usd, 'cached_rate': args.cached_rate,
                                    'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
                                   indent=1) + '\n')
    items = list(plan(tasks, models, agents, args.order))
    if args.finalize:
        finalize(runner, items)
        return
    todo = [i for i in items if run_key(i[0]['id'], i[1], i[2]) not in runner.done]
    print(f'{len(items)} planned, {len(items) - len(todo)} already recorded, {len(todo)} to run', flush=True)
    if args.order == 'task':
        print(f'== {len(todo)} runs, task order', flush=True)
        with cf.ThreadPoolExecutor(args.concurrency) as pool:
            list(pool.map(lambda i: runner.execute(*i), todo))
        for model in runner.blocked:
            finalize(runner, [i for i in items if i[2] == model])
    else:
        # One model at a time keeps the model-by-model order even with concurrency.
        for model in models:
            batch = [i for i in todo if i[2] == model]
            if not batch:
                continue
            print(f'== {model}: {len(batch)} runs', flush=True)
            with cf.ThreadPoolExecutor(args.concurrency) as pool:
                list(pool.map(lambda i: runner.execute(*i), batch))
            if model in runner.blocked:
                # Limits held for the whole backoff (~30 min): account for the rest and move on.
                finalize(runner, [i for i in items if i[2] == model])
    left = [i for i in items if run_key(i[0]['id'], i[1], i[2]) not in runner.done]
    print(f'done: {len(items) - len(left)} of {len(items)} recorded; blocked models: {runner.blocked or "none"}')
    if proxy:
        print(f'spend: USD {proxy.spent:.4f} of {args.max_usd} (this session USD {proxy.spent - proxy.spent_at_start:.4f}); '
              f'stopped: {proxy.stopped or "no"}')


if __name__ == '__main__':
    main()
