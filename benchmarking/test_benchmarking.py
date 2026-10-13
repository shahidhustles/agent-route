import json
import pathlib
import tempfile
import unittest

from adapters.cmd import redact_headers
from build_profile import build_profile
from run import create_run_dir, run_model
from scorers import score_case


def write_case(run_dir, model, case_id, category, passed, result=None):
    model_dir = run_dir / model
    model_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        'case_id': case_id,
        'category': category,
        'request': {'session_id': 's'},
        'result': result or {'content': 'x', 'tool_calls': [], 'usage': {'completion_tokens': 10}, 'latency_ms': 1000},
        'score': {'passed': passed, 'detail': ''},
    }
    (model_dir / f'{case_id}.json').write_text(json.dumps(entry))


class ScorerTests(unittest.TestCase):
    def assertPassed(self, expected, case, result):
        self.assertEqual(score_case(case, result)['passed'], expected)

    def result(self, content=None, tool_calls=None):
        return {'content': content, 'tool_calls': tool_calls or []}

    def test_exact_normalizes_whitespace_and_case(self):
        self.assertPassed(True, {'scoring': {'type': 'exact', 'value': 'Yes'}},
                          self.result('  yes\n'))
        self.assertPassed(False, {'scoring': {'type': 'exact', 'value': 'yes'}},
                          self.result('maybe yes'))

    def test_contains_case_rules(self):
        case = {'scoring': {'type': 'contains', 'values': ['April 3']}}
        self.assertPassed(True, case, self.result('It arrives April 3.'))
        self.assertPassed(False, case, self.result('arrives on april 3'))
        ci = {'scoring': {'type': 'contains', 'values': ['April 3'], 'case_insensitive': True}}
        self.assertPassed(True, ci, self.result('april 3'))

    def test_json_extracts_fenced_output(self):
        case = {'scoring': {'type': 'json', 'expected': {'count': 4}}}
        self.assertPassed(True, case, self.result('```json\n{"count": 4}\n```'))
        self.assertPassed(False, case, self.result('{"count": 3}'))
        self.assertPassed(False, case, self.result('no json here'))

    def test_tool_call_name_and_args(self):
        case = {'scoring': {'type': 'tool_call', 'name': 'get_weather', 'args': {'city': 'Tokyo'}}}
        call = {'function': {'name': 'get_weather', 'arguments': '{"city": "Tokyo", "unit": "c"}'}}
        self.assertPassed(True, case, self.result(None, [call]))
        wrong = {'function': {'name': 'get_weather', 'arguments': '{"city": "Osaka"}'}}
        self.assertPassed(False, case, self.result(None, [wrong]))
        none = {'scoring': {'type': 'tool_call', 'name': None}}
        self.assertPassed(True, none, self.result('12'))
        self.assertPassed(False, none, self.result(None, [call]))

    def test_constraints(self):
        def case(*constraints):
            return {'scoring': {'type': 'constraints', 'constraints': constraints}}
        self.assertPassed(True, case({'kind': 'word_count', 'value': 3}),
                          self.result('sky is blue'))
        self.assertPassed(False, case({'kind': 'word_count', 'value': 3}),
                          self.result('the sky is blue'))
        self.assertPassed(True, case({'kind': 'line_count', 'value': 2}),
                          self.result('red\nblue\n'))
        self.assertPassed(True, case({'kind': 'forbidden', 'value': 'water'}),
                          self.result('it rained hard'))
        self.assertPassed(False, case({'kind': 'forbidden', 'value': 'water'}),
                          self.result('rain is water'))
        self.assertPassed(True, case({'kind': 'min_words', 'value': 4}),
                          self.result('one two three four five'))
        self.assertPassed(False, case({'kind': 'min_words', 'value': 4}),
                          self.result('one two three'))
        with self.assertRaises(ValueError):
            score_case(case({'kind': 'bogus', 'value': 1}), self.result('x'))

    def test_malformed_output_scores_zero_without_raising(self):
        case = {'scoring': {'type': 'tool_call', 'name': 'x', 'args': {}}}
        scored = score_case(case, {'content': None, 'tool_calls': [
            {'function': {'name': 'x', 'arguments': 'not-json'}}]})
        self.assertFalse(scored['passed'])


class RunTests(unittest.TestCase):
    def test_redact_headers(self):
        redacted = redact_headers({'Authorization': 'Bearer k', 'x-api-key': 'k', 'Accept': 'json'})
        self.assertEqual(redacted['Authorization'], '[REDACTED]')
        self.assertEqual(redacted['x-api-key'], '[REDACTED]')
        self.assertEqual(redacted['Accept'], 'json')

    def test_resume_reuses_saved_evidence_and_fills_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = pathlib.Path(tmp) / 'run'
            run_dir.mkdir()
            (run_dir / 'meta.json').write_text(json.dumps({'suite_version': 'v1'}))
            write_case(run_dir, 'm1', 'r1-clock-arrival', 'reasoning', True,
                       {'content': 'saved-evidence', 'tool_calls': [], 'usage': {}, 'latency_ms': 1})

            calls = []

            class FakeClient:
                def chat(self, model, case):
                    calls.append((model, case['id']))
                    return {'content': 'fresh', 'tool_calls': [], 'usage': {}, 'latency_ms': 5}

            ran, skipped = run_model(FakeClient(), 'm1', [
                {'id': 'r1-clock-arrival', 'category': 'reasoning', 'max_tokens': 8,
                 'messages': [], 'scoring': {'type': 'exact', 'value': 'x'}},
                {'id': 'r2-mixed-arith', 'category': 'reasoning', 'max_tokens': 8,
                 'messages': [], 'scoring': {'type': 'exact', 'value': 'x'}},
            ], run_dir, log=lambda *_: None)
            self.assertEqual((ran, skipped), (1, 1))
            self.assertEqual(calls, [('m1', 'r2-mixed-arith')])
            saved = json.loads((run_dir / 'm1' / 'r1-clock-arrival.json').read_text())
            self.assertEqual(saved['result']['content'], 'saved-evidence')

    def test_rerun_never_overwrites_earlier_run(self):
        first = create_run_dir('v1')
        second = create_run_dir('v1')
        try:
            self.assertNotEqual(first, second)
        finally:
            for run in (first, second):
                for path in sorted([run] + list(run.rglob('*')), reverse=True):
                    path.rmdir()


class ProfileBuilderTests(unittest.TestCase):
    def test_profiles_are_complete_and_schema_shaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = pathlib.Path(tmp) / 'run'
            run_dir.mkdir()
            model = 'glm-5.3-flash'
            categories = ['reasoning', 'coding', 'tool_use', 'document_qa',
                          'structured_output', 'instruction_following', 'long_context']
            for i, category in enumerate(categories):
                write_case(run_dir, model, f'case-{i}', category, i % 2 == 0,
                           {'content': 'x', 'tool_calls': [], 'usage': {'completion_tokens': 50},
                            'latency_ms': 500})
            profile = build_profile(model, [json.loads(p.read_text())
                                            for p in sorted((run_dir / model).glob('*.json'))])
            self.assertEqual(set(profile['capabilities']), set(categories))
            self.assertTrue(all(0 <= v <= 1 for v in profile['capabilities'].values()))
            self.assertEqual(profile['capabilities']['reasoning'], 1.0)
            self.assertEqual(profile['capabilities']['coding'], 0.0)
            self.assertEqual(profile['runtime']['tokens_per_second'], 100.0)
            self.assertEqual(profile['runtime']['peak_vram_gb'], 160)
            self.assertEqual(profile['target_deployment']['precision'], 'FP8')
            self.assertTrue(profile['features']['tool_calling'])


if __name__ == '__main__':
    unittest.main()
