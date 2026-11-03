"""Long-lived backend for the web app: routing, free-text agent runs, progress streaming, artifacts, memory.

    .venv/bin/python routing/server.py --port 8765 --max-usd 0.25

Binds 127.0.0.1. The Next.js app proxies /api/py/* to it. The embedding model, outcome memory, and the
Command Code proxy (`agents/cmdproxy.py`, which holds the key and the spend cap) live in this process, so routing
takes tens of milliseconds instead of the 3 s a fresh CLI call spends loading them.

Endpoints (JSON unless noted):
    GET  /status                      spend, cap, provider-limit state, memory size
    POST /settings    {max_usd}       change the spend cap for this and later runs
    POST /route       {text, agent?}  the `route.py` contract, plus `agents` (full vote); `agent` overrides the vote.
                                      A task over 1,500 characters is read as its first and last 300 (`truncated`)
    POST /answer      {text, model}   one chat call through the proxy ("Just answer")
    POST /runs        {text, agent, model, preference, csv?, rerun_of?, route?, routed_text?}   start an agent run; returns {id}.
                                      A rerun without `csv` reuses the original run's file or is refused;
                                      `routed_text` differing from `text` is refused; a body over 2 MB gets a 413
    GET  /runs/<id>                   run state, result, artifact
    GET  /runs/<id>/events            text/event-stream of progress events, then a final `done`
    GET  /runs/<id>/docx              the .docx of a run made under the old JSON contract
    GET  /runs/<id>/file/<name>       a real output file (.pptx, .docx, .xlsx, .html, ...) as a download
    GET  /runs/<id>/view/<name>       an .html output inline, under a CSP that allows its own script and nothing off the page
    GET  /runs/<id>/preview/<name>    page images of an Office output, made in a no-network container; returns the
                                      manifest {kind, pages, sheets, urls}. 502 with a readable message if conversion fails
    GET  /runs/<id>/preview/<name>/<asset>   page-N.jpg, thumb-N.jpg, file.pdf or sheets.json
    POST /runs/<id>/cancel           stop the container; settle in-flight spend
    POST /runs/<id>/mark {passed}     user verdict; updates the memory record and re-routes
    POST /answer {text, model, stream:true, messages:[{role,content}]}  SSE deltas then usage
    GET  /recorded                    runs recorded in agents-cc-20261031 (free, for the previews)
    GET  /recorded/<model>/<agent>/<task>   the recorded artifact
"""
import argparse
import http.server
import json
import pathlib
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'agents'))
import cmdproxy  # noqa: E402
from adhoc import free_text_detail, read_artifact, read_artifact_files, run_adhoc  # noqa: E402
from preview import PreviewError, build_preview  # noqa: E402
from agent_model import MODELS, SHORT  # noqa: E402
from memory import Embedder, Memory, read_jsonl  # noqa: E402
from policy import PREFERENCES  # noqa: E402
from route import ONLINE, build_table, decide, load_tolerance, vote_agents  # noqa: E402

RUNS_DIR = ROOT / 'data' / 'ui-runs'
LEDGER = ROOT / 'benchmarking' / 'results' / 'agents-ui-ledger.jsonl'
RECORDED = ROOT / 'benchmarking' / 'results' / 'agents-cc-20261031'
ENV_FILE = ROOT / '.env.modal'
LOW_VOTE = 0.5
MAX_BODY = 2_000_000
DRAIN_LIMIT = 32_000_000  # an oversized body is read and dropped up to this size so the client can read the 413
ROUTE_FULL = 1500  # a task up to this long is embedded whole
ROUTE_HEAD, ROUTE_TAIL = 300, 300  # a longer one is read as its start and its end; more of the middle drowns the instruction
AGENTS = ('code', 'spreadsheet', 'data-analysis', 'docx', 'slides', 'diagram', 'map', 'scene-3d')
DEFAULT_MODEL = 'deepseek/deepseek-v4.1-flash'


class BodyTooLarge(Exception):
    pass


def routing_text(text):
    """The text the encoder reads. A long task keeps its start and its end, where the instruction usually is.

    Returns (text, truncated).
    """
    if len(text) <= ROUTE_FULL:
        return text, False
    return text[:ROUTE_HEAD] + ' ... ' + text[-ROUTE_TAIL:], True


def safe_csv_name(name):
    name = re.sub(r'[^\w.-]', '_', str(name or ''))
    return 'input.csv' if name.strip('.') == '' else name


def stored_csv(runs_dir, run):
    """The (name, body) CSV a run was started with, or None if it had none. Raises ValueError if the file is gone."""
    name = run.get('csv_name')
    if not name:
        return None
    for rel in ('upload', 'work/inputs'):
        path = pathlib.Path(runs_dir) / run['id'] / rel / name
        if path.is_file():
            return name, path.read_text()
    raise ValueError(f'The input file {name} from run {run["id"]} is gone, so the run cannot be repeated. '
                     'Attach the CSV again and start a new run.')


def check_fresh(text, routed_text):
    """A decision belongs to the text it was made for. Refuse a run whose text changed after routing."""
    if routed_text is not None and routed_text.strip() != text.strip():
        raise ValueError('The task changed after it was routed. Route it again before running.')


def route_for_run(route, agent, model):
    """Keep the routing decision only if this run is the one it chose. A manual rerun carries none."""
    if isinstance(route, dict) and route.get('agent') == agent and route.get('model') == model:
        return route
    return None


class State:
    def __init__(self, max_usd, online=ONLINE, env_file=ENV_FILE):
        self.lock = threading.RLock()
        self.online = pathlib.Path(online)
        self.embedder = Embedder()
        self.mem = Memory.load(online=self.online)
        key = cmdproxy.read_env(env_file, 'CMD_API_KEY')
        if not key:
            raise SystemExit(f'CMD_API_KEY missing from {env_file}')
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        self.proxy = cmdproxy.Proxy(key, max_usd, LEDGER,
                                    base_url=cmdproxy.read_env(env_file, 'CMD_BASE_URL') or cmdproxy.DEFAULT_BASE)
        self.runs = {}
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        self.tolerance = load_tolerance()
        self.embedder.encode(['warm up'])
        self.load_runs()

    # --- routing -----------------------------------------------------------
    def route(self, text, agent=None):
        if agent is not None and agent not in AGENTS:
            raise ValueError(f'unknown agent {agent}')
        read, truncated = routing_text(text)
        vector = self.embedder.encode([read])[0]
        with self.lock:
            votes = vote_agents(self.mem, vector)
            if agent:
                share = dict(votes).get(agent, 0.0)
                votes = [(agent, share)] + [v for v in votes if v[0] != agent]
            table = build_table(self.mem)
            decisions = {p: decide(table, vector, votes, p, self.tolerance[p]) for p in PREFERENCES}
        if agent:
            for d in decisions.values():
                d['manual_agent'] = True
        return {'task': {'id': None, 'text': text}, 'agents': [{'agent': a, 'share': round(s, 4)} for a, s in votes],
                'low_vote': votes[0][1] < LOW_VOTE and not agent, 'agent_override': bool(agent),
                'truncated': {'chars': len(text), 'read_head': ROUTE_HEAD, 'read_tail': ROUTE_TAIL} if truncated else None,
                'decisions': decisions}, vector

    # --- status ------------------------------------------------------------
    def status(self):
        p = self.proxy
        return {'spent_usd': round(p.spent, 5), 'cap_usd': p.cap_usd, 'stopped': p.stopped,
                'session_usd': round(p.spent - p.spent_at_start, 5), 'records': len(self.mem.records),
                'ui_records': sum(1 for r in self.mem.records if r.get('run') == 'ui'),
                'models': [{'id': m, 'name': SHORT[m]} for m in MODELS]}

    def set_cap(self, max_usd):
        with self.proxy.lock:
            self.proxy.cap_usd = max_usd
            if self.proxy.stopped and self.proxy.stopped.startswith('spend cap') and self.proxy.spent < max_usd:
                self.proxy.stopped = None

    # --- runs --------------------------------------------------------------
    def load_runs(self):
        for path in sorted(RUNS_DIR.glob('*/run.json')):
            try:
                run = json.loads(path.read_text())
            except ValueError:
                continue
            if run['status'] == 'running':
                run['status'] = 'error'
                run['result'] = {'status': 'error', 'detail': 'the server restarted during this run'}
            # Runs saved before free_text_detail existed still carry the suite wording.
            result = run.get('result') or {}
            if (result.get('contract') or {}).get('passed'):
                result['contract']['detail'] = free_text_detail(run['agent'], result['contract']['detail'])
                result['detail'] = free_text_detail(run['agent'], result.get('detail', ''))
            run['events'] = run.get('events', [])
            run['cond'] = threading.Condition()
            self.runs[run['id']] = run

    def save_run(self, run):
        path = RUNS_DIR / run['id'] / 'run.json'
        with self.lock:
            path.write_text(json.dumps({k: v for k, v in run.items() if k != 'cond'}, ensure_ascii=False))

    def start_run(self, body):
        text = (body.get('text') or '').strip()
        agent, model = body.get('agent'), body.get('model')
        if not text or agent not in AGENTS:
            raise ValueError('text and a known agent are required')
        if model not in MODELS:
            raise ValueError(f'unknown model {model}')
        check_fresh(text, body.get('routed_text'))
        rerun_of = body.get('rerun_of')
        csv = body.get('csv')
        csv = (safe_csv_name(csv['name']), csv['body']) if csv and csv.get('body') else None
        if csv is None and rerun_of:
            original = self.runs.get(rerun_of)
            if original is None:
                raise ValueError(f'no run {rerun_of} to repeat')
            csv = stored_csv(RUNS_DIR, original)
        if self.proxy.stopped:
            raise PermissionError(f'live calls are stopped: {self.proxy.stopped}')
        vector = self.embedder.encode([routing_text(text)[0]])[0]
        with self.lock:
            table = build_table(self.mem)
            est = table.estimates(vector, agent)[model]
        run_id = time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:4]
        run = {'id': run_id, 'text': text, 'agent': agent, 'model': model, 'preference': body.get('preference'),
               'rerun_of': rerun_of, 'route': route_for_run(body.get('route'), agent, model), 'status': 'running', 'events': [],
               'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'result': None, 'artifact': None,
               'csv_name': csv[0] if csv else None, 'marked': None, 'mark_effect': None,
               'before': {'p_pass': round(est.p_success, 4), 'runs_seen': table.count(agent, model)},
               'cond': threading.Condition()}
        (RUNS_DIR / run_id).mkdir(parents=True)
        if csv:  # a copy outside the workspace, which each execution wipes, so a rerun can reuse it
            (RUNS_DIR / run_id / 'upload').mkdir()
            (RUNS_DIR / run_id / 'upload' / csv[0]).write_text(csv[1])
        self.runs[run_id] = run
        self.save_run(run)
        threading.Thread(target=self.execute, args=(run, csv, vector), daemon=True).start()
        return run_id

    def emit(self, run, event):
        with run['cond']:
            event['i'] = len(run['events'])
            run['events'].append(event)
            run['cond'].notify_all()

    def execute(self, run, csv, vector):
        run_dir = RUNS_DIR / run['id']
        try:
            if run.get('cancelled'):
                raise RuntimeError('Stopped by you.')
            result = run_adhoc(run_dir, run['text'], run['agent'], run['model'], self.proxy,
                               lambda e: self.emit(run, e), csv=csv)
        except Exception as e:  # keep the app alive; the run reports the error
            result = {'status': 'error', 'detail': f'{type(e).__name__}: {e}', 'contract': None, 'wall_s': 0.0,
                      'cost_usd': 0.0, 'input_tokens': 0, 'output_tokens': 0}
        if run.get('cancelled'):
            result = {**result, 'status': 'stopped', 'detail': 'Stopped by you.'}
        run['artifact'] = read_artifact_files(run['agent'], run_dir / 'work') if result['status'] in ('passed', 'failed') else None
        if result['status'] in ('passed', 'failed'):
            # A failed contract is a definite failure; a pass waits for the user's verdict.
            passed = False if result['status'] == 'failed' else None
            record = {'task_id': f'ui-{run["id"]}', 'dataset': 'ui', 'run': 'ui', 'agent': run['agent'],
                      'model': run['model'], 'passed': passed, 'latency_s': result['wall_s'],
                      'input_tokens': result['input_tokens'], 'output_tokens': result['output_tokens'],
                      'cost_usd': result['cost_usd']}
            task = {'task_id': record['task_id'], 'dataset': 'ui', 'split': None, 'agents': None, 'text': run['text']}
            with self.lock:
                self.mem.append_online(self.online, record, task, vector)
            result['appended'] = True
            result['record_passed'] = passed
        else:
            result['appended'] = False
        run['result'] = result
        run['status'] = result['status']
        self.save_run(run)
        self.emit(run, {'kind': 'done', 'status': run['status']})

    def mark(self, run, passed):
        task_id = f'ui-{run["id"]}'
        with self.lock:
            rec = next((r for r in self.mem.records if r['task_id'] == task_id), None)
            if rec is None:
                raise ValueError('this run left no memory record to mark')
            rec['passed'] = bool(passed)
            rows = read_jsonl(self.online)
            for row in rows:
                if row['record']['task_id'] == task_id:
                    row['record']['passed'] = bool(passed)
            self.online.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            vector = self.mem.vectors[task_id]
            table = build_table(self.mem)
            est = table.estimates(vector, run['agent'])[run['model']]
        run['marked'] = bool(passed)
        run['mark_effect'] = {'before': run['before'],
                              'after': {'p_pass': round(est.p_success, 4), 'runs_seen': table.count(run['agent'], run['model'])}}
        self.save_run(run)
        return run['mark_effect']

    def public_run(self, run):
        return {k: v for k, v in run.items() if k not in ('cond', 'events')} | {'n_events': len(run['events'])}

    def cancel_run(self, run):
        """Stop this run's container. Its in-flight provider usage still settles in the proxy."""
        if run['status'] != 'running':
            return self.public_run(run)
        run['cancelled'] = True
        workspace = str((RUNS_DIR / run['id'] / 'work').resolve())
        ids = subprocess.run(['docker', 'ps', '-q', '--filter', f'volume={workspace}'],
                             capture_output=True, text=True, timeout=10).stdout.split()
        if ids:
            subprocess.run(['docker', 'kill', *ids], capture_output=True, timeout=15)
        if not ids and run['status'] == 'running':
            def stop_when_started():
                while run['status'] == 'running':
                    time.sleep(0.3)
                    containers = subprocess.run(['docker', 'ps', '-q', '--filter', f'volume={workspace}'],
                        capture_output=True, text=True, timeout=10).stdout.split()
                    if containers:
                        subprocess.run(['docker', 'kill', *containers], capture_output=True, timeout=15)
                        return
            threading.Thread(target=stop_when_started, daemon=True).start()
        self.emit(run, {'kind': 'error', 'text': 'Stopped by you.'})
        return self.public_run(run)

    def answer_stream(self, text, model, messages=None):
        """Yield provider deltas, then settled usage. Prior user and assistant turns stay in order."""
        if model not in MODELS:
            raise ValueError(f'unknown model {model}')
        if self.proxy.stopped:
            raise PermissionError(f'live calls are stopped: {self.proxy.stopped}')
        history = messages or [{'role': 'user', 'content': text}]
        if not isinstance(history, list) or any(not isinstance(m, dict) or
                m.get('role') not in ('user', 'assistant') or not isinstance(m.get('content'), str) for m in history):
            raise ValueError('messages must contain user or assistant text turns')
        token = self.proxy.new_token()
        body = json.dumps({'model': model, 'max_tokens': 1024, 'stream': True,
                           'messages': [{'role': 'system', 'content': 'Answer directly and concisely. Use Markdown when useful.'},
                                        *history]}).encode()
        request = urllib.request.Request(self.proxy.url + '/chat/completions', data=body,
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
        start = time.time()
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                for line in response:
                    raw = line.decode(errors='replace').strip()
                    if not raw.startswith('data:') or raw[5:].strip() == '[DONE]':
                        continue
                    chunk = json.loads(raw[5:])
                    for choice in chunk.get('choices', []):
                        delta = choice.get('delta', {}).get('content')
                        if delta:
                            yield {'type': 'delta', 'text': delta}
        finally:
            usage = self.proxy.take(token) or {'usd': 0.0}
        yield {'type': 'done', 'model': model, 'wall_s': round(time.time() - start, 2),
               'cost_usd': round(usage['usd'], 6)}

    # --- just answer -------------------------------------------------------
    def answer(self, text, model):
        if model not in MODELS:
            raise ValueError(f'unknown model {model}')
        if self.proxy.stopped:
            raise PermissionError(f'live calls are stopped: {self.proxy.stopped}')
        token = self.proxy.new_token()
        body = json.dumps({'model': model, 'max_tokens': 1024, 'stream': False,
                           'messages': [{'role': 'system', 'content': 'Answer the user directly and concisely. Use Markdown when it helps.'},
                                        {'role': 'user', 'content': text}]}).encode()
        request = urllib.request.Request(self.proxy.url + '/chat/completions', data=body, method='POST',
                                         headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
        start = time.time()
        try:
            with urllib.request.urlopen(request, timeout=300) as r:
                payload = json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors='replace')[:300]
            self.proxy.take(token)
            raise RuntimeError(f'provider returned HTTP {e.code}: {detail}')
        usage = self.proxy.take(token) or {'usd': 0.0}
        return {'text': payload['choices'][0]['message']['content'] or '', 'model': model,
                'wall_s': round(time.time() - start, 2), 'cost_usd': round(usage['usd'], 6),
                'usage': payload.get('usage') or {}}


MIME = {'.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.html': 'text/html; charset=utf-8', '.geojson': 'application/geo+json', '.py': 'text/x-python',
        '.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.json': 'application/json'}
SAFE_NAME = re.compile(r'[\w.-]+')


def run_output(run_id, name):
    """The path of an output file of a run, or None if the name is not a plain file inside its out/ folder."""
    if not SAFE_NAME.fullmatch(name):
        return None
    path = RUNS_DIR / run_id / 'work' / 'out' / name
    return path if path.is_file() else None


def recorded_index():
    runs = read_jsonl(RECORDED / 'runs.jsonl')
    return [{'task_id': r['task_id'], 'agent': r['agent'], 'model': r['model'].removeprefix('cc/'),
             'passed': r.get('passed'), 'wall_s': r.get('wall_s'), 'cost_usd': r.get('cost_usd'),
             'artifact_dir': r.get('artifact_dir')} for r in runs if not r.get('not_run')]


def make_handler(state):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            pass

        def send_json(self, obj, status=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def fail(self, status, message):
            self.send_json({'error': message}, status)

        def body(self):
            n = int(self.headers.get('Content-Length') or 0)
            if n > MAX_BODY:
                # Read the body off the socket before answering. Replying with the body unread resets the
                # connection and the dev proxy reports a 500 instead of this message.
                left = min(n, DRAIN_LIMIT)
                while left > 0:
                    chunk = self.rfile.read(min(65536, left))
                    if not chunk:
                        break
                    left -= len(chunk)
                if n > DRAIN_LIMIT:
                    self.close_connection = True
                raise BodyTooLarge(f'The request is {n / 1_000_000:.1f} MB; the limit is {MAX_BODY / 1_000_000:.0f} MB. '
                                   'Attach a smaller CSV.')
            return json.loads(self.rfile.read(n) or b'{}')

        def dispatch(self, method):
            parts = [p for p in self.path.split('?')[0].split('/') if p]
            try:
                if method == 'GET':
                    return self.get(parts)
                return self.post(parts)
            except BodyTooLarge as e:
                self.fail(413, str(e))
            except PermissionError as e:
                self.fail(429, str(e))
            except (ValueError, KeyError) as e:
                self.fail(400, str(e))
            except Exception as e:
                self.fail(500, f'{type(e).__name__}: {e}')

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')

        def get(self, parts):
            if parts == ['status']:
                return self.send_json(state.status())
            if parts == ['recorded']:
                return self.send_json(recorded_index())
            if len(parts) == 4 and parts[0] == 'recorded':
                _, model, agent, task = parts
                ws = RECORDED / 'work' / model / agent / task
                if not ws.resolve().is_relative_to((RECORDED / 'work').resolve()) or not ws.is_dir():
                    return self.fail(404, 'no such recorded run')
                return self.send_json(read_artifact(agent, ws))
            if len(parts) == 5 and parts[0] == 'recorded' and parts[4] == 'docx':
                _, model, agent, task, _ = parts
                return self.send_file(RECORDED / 'work' / model / agent / task / 'out' / 'document.docx', RECORDED / 'work')
            if parts[:1] == ['runs'] and len(parts) >= 2:
                run = state.runs.get(parts[1])
                if run is None:
                    return self.fail(404, 'no such run')
                if len(parts) == 2:
                    return self.send_json(state.public_run(run))
                if parts[2] == 'events':
                    return self.stream(run)
                if parts[2] == 'docx':
                    return self.send_file(RUNS_DIR / run['id'] / 'work' / 'out' / 'document.docx', RUNS_DIR)
                if parts[2] == 'file' and len(parts) == 4:
                    path = run_output(run['id'], parts[3])
                    return self.send_file(path, RUNS_DIR) if path else self.fail(404, 'no such file')
                if parts[2] == 'view' and len(parts) == 4:
                    return self.view_html(run, parts[3])
                if parts[2] == 'preview' and len(parts) in (4, 5):
                    return self.preview(run, parts[3], parts[4] if len(parts) == 5 else None)
            if parts == ['runs']:
                return self.send_json([state.public_run(r) for r in sorted(state.runs.values(), key=lambda r: r['id'])])
            self.fail(404, 'not found')

        def post(self, parts):
            data = self.body()
            if parts == ['route']:
                text = (data.get('text') or '').strip()
                if not text:
                    raise ValueError('text is required')
                out, _ = state.route(text, data.get('agent'))
                return self.send_json(out)
            if parts == ['settings']:
                cap = float(data['max_usd'])
                if cap < 0:
                    raise ValueError('max_usd must be positive')
                state.set_cap(cap)
                return self.send_json(state.status())
            if parts == ['runs']:
                return self.send_json({'id': state.start_run(data)})
            if parts == ['answer'] and data.get('stream'):
                return self.stream_answer(data)
            if len(parts) == 3 and parts[0] == 'runs' and parts[2] == 'cancel':
                run = state.runs.get(parts[1])
                if run is None:
                    return self.fail(404, 'no such run')
                return self.send_json(state.cancel_run(run))
            if parts == ['answer']:
                return self.send_json(state.answer((data.get('text') or '').strip(), data.get('model') or DEFAULT_MODEL))
            if len(parts) == 3 and parts[0] == 'runs' and parts[2] == 'mark':
                run = state.runs.get(parts[1])
                if run is None:
                    return self.fail(404, 'no such run')
                return self.send_json(state.mark(run, bool(data['passed'])))
            self.fail(404, 'not found')

        def stream_answer(self, data):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache, no-transform')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            connected = True
            try:
                for event in state.answer_stream(data.get('text', ''), data.get('model') or DEFAULT_MODEL,
                                                data.get('messages')):
                    if connected:
                        try:
                            self.wfile.write(f'data: {json.dumps(event)}\n\n'.encode())
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            connected = False  # drain so paid usage is still accounted for
            except Exception as error:
                if connected:
                    self.wfile.write(f'data: {json.dumps({"type": "error", "error": str(error)})}\n\n'.encode())
                    self.wfile.flush()

        def send_file(self, path, base):
            path = pathlib.Path(path)
            if not path.resolve().is_relative_to(pathlib.Path(base).resolve()) or not path.is_file():
                return self.fail(404, 'no such file')
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', MIME.get(path.suffix, 'application/octet-stream'))
            self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def view_html(self, run, name):
            """A self-contained HTML output, for the artifact panel's sandboxed iframe. The CSP is the enforcement: the page
            runs its own inline script and styles but cannot fetch, load or submit anything off the page."""
            path = run_output(run['id'], name)
            if path is None or path.suffix != '.html':
                return self.fail(404, 'no such page')
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Security-Policy', "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; "
                             "style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def preview(self, run, name, asset):
            src = run_output(run['id'], name)
            if src is None:
                return self.fail(404, 'no such file')
            out = RUNS_DIR / run['id'] / 'preview' / name
            if asset:
                path = out / asset
                if not SAFE_NAME.fullmatch(asset) or not path.is_file():
                    return self.fail(404, 'no such preview file')
                body = path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', MIME.get(path.suffix, 'application/octet-stream'))
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'private, max-age=3600')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(body)
                return
            try:
                manifest = build_preview(src, out)
            except PreviewError as e:
                return self.fail(502, str(e))
            base = f'/api/py/runs/{run["id"]}/preview/{name}'
            n = manifest['pages']
            self.send_json({**manifest, 'pages': [{'page': f'{base}/page-{i}.jpg', 'thumb': f'{base}/thumb-{i}.jpg'}
                                                   for i in range(1, n + 1)],
                            'pdf': f'{base}/file.pdf', 'sheets': f'{base}/sheets.json' if manifest.get('sheets') else None})

        def stream(self, run):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache, no-transform')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            i = 0
            try:
                while True:
                    with run['cond']:
                        while i >= len(run['events']) and run['status'] == 'running':
                            run['cond'].wait(timeout=15)
                            if i >= len(run['events']) and run['status'] == 'running':
                                self.wfile.write(b': keep-alive\n\n')
                                self.wfile.flush()
                        batch = run['events'][i:]
                    for ev in batch:
                        self.wfile.write(f'data: {json.dumps(ev, ensure_ascii=False)}\n\n'.encode())
                    self.wfile.flush()
                    i += len(batch)
                    if not batch and run['status'] != 'running':
                        break
                    if batch and batch[-1].get('kind') == 'done':
                        break
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--max-usd', type=float, default=0.25, help='Command Code spend cap for app use (ledger of its own)')
    args = parser.parse_args(argv)
    state = State(args.max_usd)
    server = Server(('127.0.0.1', args.port), make_handler(state))
    print(f'router backend on http://127.0.0.1:{args.port}; ledger USD {state.proxy.spent:.4f} of {args.max_usd}; '
          f'{len(state.mem.records)} memory records', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
