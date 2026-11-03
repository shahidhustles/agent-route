"""Host-side proxy that lets sandboxed OpenCode runs reach the Command Code provider API.

The API key stays in this process. A container gets a one-run token instead, so the agent's own shell cannot
read the key. The proxy forwards /v1/chat/completions, counts spend per run and in total at list price, and
refuses new requests once the cap is reached or the provider reports a weekly usage limit.

Spend is the ledger total across proxy sessions (`ledger` file, one line per request), so a rerun continues
from what earlier runs spent. Each request reserves its worst case (input at the full rate for every byte of
the body, output at max_tokens) until its real usage arrives, so concurrent requests cannot overshoot the cap.
"""
import http.server
import importlib.util
import json
import pathlib
import socketserver
import threading
import time
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAP_MARKER = 'SPEND_CAP_REACHED'
WEEKLY_MARKER = 'weekly usage limit'
DEFAULT_BASE = 'https://api.commandcode.ai/provider/v1'
DEFAULT_MAX_TOKENS = 32000
BYTES_PER_TOKEN = 2.5  # conservative: real text runs 3-4 bytes per token, so reservations err high


def load_prices():
    """USD per 1M tokens (input, output) from the pool runner, the single source of list prices."""
    path = ROOT / 'benchmarking' / 'pool' / 'run.py'
    spec = importlib.util.spec_from_file_location('pool_run', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.POOL)


def read_env(path, name):
    for line in pathlib.Path(path).read_text().splitlines():
        if line.startswith(name + '='):
            return line.split('=', 1)[1].strip().strip('"\'')
    return None


class Proxy:
    def __init__(self, api_key, cap_usd, ledger, prices=None, base_url=DEFAULT_BASE, bind='172.17.0.1',
                 cached_rate=0.25):
        self.api_key, self.cap_usd, self.base_url = api_key, cap_usd, base_url.rstrip('/')
        self.prices = prices or load_prices()
        self.cached_rate = cached_rate  # cached input counted at this fraction of the input price
        self.ledger = pathlib.Path(ledger)
        self.lock = threading.Lock()
        self.settled = threading.Condition(self.lock)
        self.stopped = None
        self.tokens = {}  # run token -> usage totals
        self.reserved = 0.0
        self.spent = 0.0
        if self.ledger.exists():
            for line in self.ledger.read_text().splitlines():
                if line.strip():
                    self.spent += json.loads(line)['usd']
        self.spent_at_start = self.spent
        proxy = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def do_POST(self):
                proxy.handle(self)

        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        self.server = Server((bind, 0), Handler)
        self.url = f'http://{bind}:{self.server.server_address[1]}/v1'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    # --- per-run tokens -------------------------------------------------
    def new_token(self):
        token = 'run-' + uuid.uuid4().hex[:16]
        with self.lock:
            self.tokens[token] = {'requests': 0, 'usd': 0.0, 'prompt_tokens': 0, 'cached_tokens': 0,
                                  'completion_tokens': 0, 'usage_missing': 0, 'cap_refused': False, 'pending': 0}
        return token

    def take(self, token):
        with self.settled:
            while self.tokens.get(token, {}).get('pending', 0):
                self.settled.wait(timeout=1)
            return self.tokens.pop(token, None)

    # --- accounting -----------------------------------------------------
    def cost(self, model, prompt, cached, completion):
        price_in, price_out = self.prices[model]
        fresh = max(prompt - cached, 0)
        return (fresh * price_in + cached * price_in * self.cached_rate + completion * price_out) / 1e6

    def reserve(self, model, body_len, max_tokens):
        price_in, price_out = self.prices[model]
        return (body_len / BYTES_PER_TOKEN * price_in + max_tokens * price_out) / 1e6

    def settle(self, token, model, reserved, usage, label):
        prompt = usage.get('prompt_tokens') or 0
        cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens') or usage.get('cached_tokens') or 0
        completion = usage.get('completion_tokens') or 0
        missing = not usage
        usd = reserved if missing else self.cost(model, prompt, cached, completion)
        with self.lock:
            self.reserved -= reserved
            self.spent += usd
            entry = self.tokens.get(token)
            if entry is not None:
                entry['pending'] -= 1
                entry['requests'] += 1
                entry['usd'] += usd
                entry['prompt_tokens'] += prompt
                entry['cached_tokens'] += cached
                entry['completion_tokens'] += completion
                entry['usage_missing'] += int(missing)
            with self.ledger.open('a') as f:
                f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'label': label,
                                    'model': model, 'prompt': prompt, 'cached': cached, 'completion': completion,
                                    'usd': round(usd, 7), 'usage_missing': missing}) + '\n')
            self.settled.notify_all()
            if self.cap_usd is not None and self.spent >= self.cap_usd and not self.stopped:
                self.stopped = f'spend cap USD {self.cap_usd}'

    # --- request handling -----------------------------------------------
    def reply(self, h, status, message):
        body = json.dumps({'error': {'message': message, 'type': 'proxy_error'}}).encode()
        h.send_response(status)
        h.send_header('Content-Type', 'application/json')
        h.send_header('Content-Length', str(len(body)))
        h.send_header('Connection', 'close')
        h.end_headers()
        h.wfile.write(body)

    def admit(self, token, need):
        """Reserve `need` or return why not. In-flight reservations make a request wait; only real spend refuses."""
        while True:
            with self.lock:
                if not self.stopped and self.cap_usd is not None and self.spent + need > self.cap_usd:
                    self.stopped = f'spend cap USD {self.cap_usd}'
                if self.stopped:
                    self.tokens[token]['cap_refused'] = True
                    return self.stopped
                if self.cap_usd is None or self.spent + self.reserved + need <= self.cap_usd:
                    self.reserved += need
                    self.tokens[token]['pending'] += 1
                    return None
            time.sleep(0.5)

    def handle(self, h):
        h.close_connection = True
        token = (h.headers.get('Authorization') or '').removeprefix('Bearer ').strip()
        raw = h.rfile.read(int(h.headers.get('Content-Length') or 0))
        if token not in self.tokens or not h.path.endswith('/chat/completions'):
            return self.reply(h, 403, 'unknown run token or path')
        try:
            payload = json.loads(raw)
            model = payload['model']
            if model not in self.prices:
                return self.reply(h, 400, f'model not allowed: {model}')
        except (ValueError, KeyError):
            return self.reply(h, 400, 'bad request body')
        stream = bool(payload.get('stream'))
        if stream:
            payload.setdefault('stream_options', {})['include_usage'] = True
        max_tokens = int(payload.get('max_tokens') or payload.get('max_completion_tokens') or DEFAULT_MAX_TOKENS)
        payload = json.dumps(payload).encode()
        need = self.reserve(model, len(payload), max_tokens)
        refusal = self.admit(token, need)
        if refusal:
            return self.reply(h, 402, f'{CAP_MARKER}: {refusal}')
        request = urllib.request.Request(
            f'{self.base_url}/chat/completions', data=payload, method='POST',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}',
                     'User-Agent': 'agent-route-pool/1.0', 'Accept': 'text/event-stream' if stream else 'application/json'})
        usage = {}
        connected = True
        try:
            with urllib.request.urlopen(request, timeout=900) as upstream:
                h.send_response(upstream.status)
                h.send_header('Content-Type', upstream.headers.get('Content-Type', 'application/json'))
                h.send_header('Connection', 'close')
                h.end_headers()
                if stream:
                    for line in upstream:
                        text = line.decode(errors='replace').strip()
                        if text.startswith('data:') and text[5:].strip() not in ('', '[DONE]'):
                            try:
                                chunk = json.loads(text[5:])
                            except ValueError:
                                continue
                            usage = chunk.get('usage') or usage
                        if connected:
                            try:
                                h.wfile.write(line)
                                h.wfile.flush()
                            except (BrokenPipeError, ConnectionResetError):
                                connected = False  # keep reading the provider's final usage
                else:
                    body = upstream.read()
                    h.wfile.write(body)
                    try:
                        usage = json.loads(body).get('usage') or {}
                    except ValueError:
                        pass
        except urllib.error.HTTPError as error:
            body = error.read()
            if WEEKLY_MARKER in body.decode(errors='replace'):
                self.stopped = WEEKLY_MARKER
            self.settle(token, model, need, {'prompt_tokens': 0}, 'http-error')
            h.send_response(error.code)
            h.send_header('Content-Type', 'application/json')
            h.send_header('Content-Length', str(len(body)))
            h.send_header('Connection', 'close')
            h.end_headers()
            h.wfile.write(body)
            return
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            # Upstream may have billed a request the client never saw finish: keep the reservation as spend.
            self.settle(token, model, need, {}, f'aborted: {type(error).__name__}')
            return
        self.settle(token, model, need, usage, 'ok')

    def close(self):
        self.server.shutdown()
