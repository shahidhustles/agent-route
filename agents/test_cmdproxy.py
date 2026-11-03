import http.server
import json
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import cmdproxy  # noqa: E402
import run  # noqa: E402

MODEL = 'deepseek/deepseek-v4.1-flash'
SEEN = []


class Upstream(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        SEEN.append(self.headers.get('Authorization'))
        self.rfile.read(int(self.headers['Content-Length']))
        usage = {'prompt_tokens': 1000, 'completion_tokens': 100, 'prompt_tokens_details': {'cached_tokens': 400}}
        body = ('data: ' + json.dumps({'choices': [{'delta': {'content': 'hi'}}]}) + '\n\n'
                'data: ' + json.dumps({'choices': [], 'usage': usage}) + '\n\ndata: [DONE]\n\n').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def post(proxy, token, max_tokens=100):
    body = json.dumps({'model': MODEL, 'stream': True, 'max_tokens': max_tokens, 'messages': []}).encode()
    request = urllib.request.Request(proxy.url + '/chat/completions', data=body,
                                     headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    return urllib.request.urlopen(request).read()


class ProxyTest(unittest.TestCase):
    def setUp(self):
        self.upstream = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.upstream.shutdown()
        self.dir.cleanup()

    def proxy(self, cap):
        return cmdproxy.Proxy('REAL-KEY', cap, pathlib.Path(self.dir.name) / 'ledger.jsonl',
                              prices={MODEL: (0.15, 0.60)}, bind='127.0.0.1',
                              base_url=f'http://127.0.0.1:{self.upstream.server_address[1]}', cached_rate=0.25)

    def test_counts_cost_with_cached_rate_and_swaps_the_key(self):
        proxy = self.proxy(1.0)
        token = proxy.new_token()
        post(proxy, token)
        self.assertEqual(SEEN[-1], 'Bearer REAL-KEY')
        usage = proxy.take(token)
        # 600 fresh x 0.15 + 400 cached x 0.15 x 0.25 + 100 out x 0.60, per million
        self.assertAlmostEqual(usage['usd'], (600 * 0.15 + 400 * 0.15 * 0.25 + 100 * 0.60) / 1e6)
        self.assertEqual(usage['cached_tokens'], 400)
        proxy.close()

    def test_take_waits_for_inflight_stream_usage_after_cancellation(self):
        proxy = self.proxy(1.0)
        self.addCleanup(proxy.close)
        token = proxy.new_token()
        self.assertIsNone(proxy.admit(token, .01))
        finished = threading.Event()
        result = []
        def collect():
            result.append(proxy.take(token))
            finished.set()
        thread = threading.Thread(target=collect)
        thread.start()
        self.assertFalse(finished.wait(.05))
        proxy.settle(token, MODEL, .01, {'prompt_tokens': 100, 'completion_tokens': 20}, 'test')
        self.assertTrue(finished.wait(1))
        thread.join()
        self.assertAlmostEqual(result[0]['usd'], .000027)
        self.assertEqual(result[0]['pending'], 0)

    def test_refuses_after_the_cap_and_unknown_tokens(self):
        proxy = self.proxy(0.0001)
        token = proxy.new_token()
        with self.assertRaises(urllib.error.HTTPError) as err:
            post(proxy, token, max_tokens=32000)
        self.assertEqual(err.exception.code, 402)
        self.assertIn(cmdproxy.CAP_MARKER, err.exception.read().decode())
        self.assertTrue(proxy.stopped)
        with self.assertRaises(urllib.error.HTTPError) as err:
            post(proxy, 'run-unknown')
        self.assertEqual(err.exception.code, 403)
        proxy.close()

    def test_ledger_carries_spend_into_the_next_session(self):
        proxy = self.proxy(1.0)
        post(proxy, proxy.new_token())
        spent = proxy.spent
        proxy.close()
        self.assertAlmostEqual(self.proxy(1.0).spent, spent)


class PlanTest(unittest.TestCase):
    def test_task_order_finishes_every_model_before_the_next_task(self):
        tasks = [{'id': 'a1', 'agents': ['a']}, {'id': 'a2', 'agents': ['a']}, {'id': 'b1', 'agents': ['b']}]
        order = [(t['id'], m) for t, _, m in run.plan(tasks, ['m1', 'm2'], order='task')]
        self.assertEqual(order, [('a1', 'm1'), ('a1', 'm2'), ('b1', 'm1'), ('b1', 'm2'), ('a2', 'm1'), ('a2', 'm2')])


if __name__ == '__main__':
    unittest.main()
