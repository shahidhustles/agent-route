import http.client
import json
import pathlib
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import server  # noqa: E402


class RoutingText(unittest.TestCase):
    def test_short_task_is_read_whole(self):
        self.assertEqual(server.routing_text('Write add(a, b).'), ('Write add(a, b).', False))

    def test_long_task_keeps_the_end(self):
        text = 'A ' * 15000 + 'Write a Python function add(a,b) returning their sum.'
        read, truncated = server.routing_text(text)
        self.assertTrue(truncated)
        self.assertTrue(read.endswith('returning their sum.'))
        self.assertLessEqual(len(read), server.ROUTE_HEAD + server.ROUTE_TAIL + 5)
        self.assertEqual(server.routing_text('x' * server.ROUTE_FULL), ('x' * server.ROUTE_FULL, False))


class RunInputs(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.runs = pathlib.Path(tmp.name)

    def put(self, run_id, rel, body='a,b\n1,2\n'):
        path = self.runs / run_id / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def test_run_without_a_csv_has_nothing_to_reuse(self):
        self.assertIsNone(server.stored_csv(self.runs, {'id': 'r1', 'csv_name': None}))

    def test_rerun_finds_the_uploaded_copy(self):
        self.put('r1', 'upload/data.csv', 'x,y\n3,4\n')
        self.assertEqual(server.stored_csv(self.runs, {'id': 'r1', 'csv_name': 'data.csv'}), ('data.csv', 'x,y\n3,4\n'))

    def test_rerun_falls_back_to_the_workspace_input(self):
        self.put('r1', 'work/inputs/data.csv')
        self.assertEqual(server.stored_csv(self.runs, {'id': 'r1', 'csv_name': 'data.csv'})[0], 'data.csv')

    def test_missing_file_refuses_with_a_message(self):
        with self.assertRaisesRegex(ValueError, 'data.csv.*gone'):
            server.stored_csv(self.runs, {'id': 'r1', 'csv_name': 'data.csv'})

    def test_csv_name_cannot_leave_the_inputs_folder(self):
        self.assertEqual(server.safe_csv_name('../../x.csv'), '.._.._x.csv')
        self.assertEqual(server.safe_csv_name('..'), 'input.csv')
        self.assertEqual(server.safe_csv_name(''), 'input.csv')


class RerunMetadata(unittest.TestCase):
    route = {'agent': 'code', 'model': 'z-ai/glm-5.3-flash', 'confidence': {'agent': 1.0, 'model': 0.9}}

    def test_route_is_kept_only_for_the_model_it_chose(self):
        self.assertEqual(server.route_for_run(self.route, 'code', 'z-ai/glm-5.3-flash'), self.route)

    def test_manual_rerun_carries_no_route(self):
        self.assertIsNone(server.route_for_run(self.route, 'code', server.DEFAULT_MODEL))
        self.assertIsNone(server.route_for_run(self.route, 'docx', 'z-ai/glm-5.3-flash'))
        self.assertIsNone(server.route_for_run(None, 'code', server.DEFAULT_MODEL))


class StaleDecision(unittest.TestCase):
    def test_same_text_passes_ignoring_outer_space(self):
        server.check_fresh('Write add(a,b).', ' Write add(a,b).\n')
        server.check_fresh('anything', None)

    def test_edited_text_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'changed after it was routed'):
            server.check_fresh('Create a Word document.', 'Write a Python function.')


class SizeLimit(unittest.TestCase):
    """A real server on a free port, with a stub State: only the body-size path is under test."""

    def test_oversized_body_gets_a_readable_413(self):
        class Stub:
            runs = {}

        httpd = server.Server(('127.0.0.1', 0), server.make_handler(Stub()))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        conn = http.client.HTTPConnection('127.0.0.1', httpd.server_address[1], timeout=20)
        body = b'x' * (server.MAX_BODY + 1000)
        conn.request('POST', '/runs', body=body, headers={'Content-Type': 'application/json'})
        response = conn.getresponse()
        self.assertEqual(response.status, 413)
        self.assertIn('limit is 2 MB', json.loads(response.read())['error'])


if __name__ == '__main__':
    unittest.main()

class StreamingAnswer(unittest.TestCase):
    def test_real_stream_keeps_history_and_settles_usage(self):
        import http.server
        import cmdproxy
        seen = []
        class Provider(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                for chunk in [{'choices': [{'delta': {'content': 'hello '}}]},
                              {'choices': [{'delta': {'content': 'again'}}]},
                              {'choices': [], 'usage': {'prompt_tokens': 1000, 'completion_tokens': 10}}]:
                    self.wfile.write(f'data: {json.dumps(chunk)}\n\n'.encode())
                    self.wfile.flush()
                self.wfile.write(b'data: [DONE]\n\n')
        provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider)
        threading.Thread(target=provider.serve_forever, daemon=True).start()
        self.addCleanup(provider.shutdown)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = server.State.__new__(server.State)
        state.proxy = cmdproxy.Proxy('test', .25, pathlib.Path(tmp.name) / 'ledger',
            prices={server.DEFAULT_MODEL: (.15, .6)}, bind='127.0.0.1',
            base_url=f'http://127.0.0.1:{provider.server_port}')
        self.addCleanup(state.proxy.close)
        history = [{'role': 'user', 'content': 'Remember 7'}, {'role': 'assistant', 'content': 'OK'},
                   {'role': 'user', 'content': 'What number?'}]
        events = list(state.answer_stream('What number?', server.DEFAULT_MODEL, history))
        self.assertEqual(''.join(e.get('text', '') for e in events), 'hello again')
        self.assertEqual(seen[0]['messages'][1:], history)
        self.assertTrue(seen[0]['stream'])
        self.assertAlmostEqual(events[-1]['cost_usd'], .000156)
        self.assertAlmostEqual(state.proxy.spent, .000156)
        self.assertEqual(state.proxy.reserved, 0)
        self.assertEqual(len((pathlib.Path(tmp.name) / 'ledger').read_text().splitlines()), 1)

class Cancellation(unittest.TestCase):
    def test_cancel_kills_only_the_run_workspace_container(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        state = server.State.__new__(server.State)
        run = {'id': 'cancel-test', 'status': 'running', 'events': [], 'cond': threading.Condition()}
        with patch.object(server.subprocess, 'run', return_value=SimpleNamespace(stdout='container-id\n')) as command:
            state.cancel_run(run)
        self.assertTrue(run['cancelled'])
        self.assertEqual(command.call_args_list[0].args[0], ['docker', 'ps', '-q', '--filter',
            f'volume={(server.RUNS_DIR / "cancel-test" / "work").resolve()}'])
        self.assertEqual(command.call_args_list[1].args[0], ['docker', 'kill', 'container-id'])
        self.assertEqual(run['events'][-1]['text'], 'Stopped by you.')
