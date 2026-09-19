import json
import tempfile
import unittest
from pathlib import Path

from baselines import MODELS, STRATEGIES, route
from report import build_report
from run import ExecutionCache, cache_key, calculate_cost


PROFILES = [
    {'model_slug': MODELS[0], 'capabilities': {key: .9 for key in
     ('reasoning','coding','tool_use','document_qa','structured_output','instruction_following','long_context')},
     'runtime': {'tokens_per_second': 10, 'usable_context': 1000},
     'features': {'tool_calling': True}, 'target_deployment': {'total_vram_gb': 160}},
    {'model_slug': MODELS[1], 'capabilities': {key: .7 for key in
     ('reasoning','coding','tool_use','document_qa','structured_output','instruction_following','long_context')},
     'runtime': {'tokens_per_second': 30, 'usable_context': 1000},
     'features': {'tool_calling': True}, 'target_deployment': {'total_vram_gb': 640}},
]
TASK = {'task_id': 'task-1', 'category': 'coding', 'messages': [{'role':'user','content':'x'}],
        'max_tokens': 10, 'scoring': {'type':'exact','value':'ok'}, 'requirements':
        {key: .8 for key in ('reasoning','coding','tool_use','document_qa','structured_output','instruction_following','long_context')},
        'policy_label': MODELS[0]}


class FakeClient:
    def __init__(self): self.calls = 0
    def chat(self, model, case, session):
        self.calls += 1
        return {'content':'ok','tool_calls':[],'latency_ms':100,
                'usage':{'prompt_tokens':100,'completion_tokens':10}}


class EvaluationTests(unittest.TestCase):
    def test_all_strategies_share_one_result_contract(self):
        outcomes = {model: {'model_slug':model, 'success': model == MODELS[0],
                            'execution_latency_ms':100, 'request_cost_usd':.01} for model in MODELS}
        keys = None
        for strategy in STRATEGIES:
            learned = lambda *_: {'model_slug':MODELS[0], 'confidence':.8}
            result = route(strategy, TASK, PROFILES, 0, 7, learned, outcomes)
            keys = keys or set(result)
            self.assertEqual(set(result), keys)
            self.assertIn(result['model_slug'], MODELS)

    def test_execution_cache_reuses_identical_call(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as directory:
            cache = ExecutionCache(Path(directory), client, max_cost_usd=1)
            first = cache.execute(TASK, MODELS[0])
            second = cache.execute(TASK, MODELS[0])
        self.assertEqual(first, second)
        self.assertEqual(client.calls, 1)
        self.assertEqual((cache.hits, cache.misses), (1, 1))

    def test_offline_cache_miss_never_calls_zen(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = ExecutionCache(Path(directory))
            with self.assertRaisesRegex(RuntimeError, 'Offline cache miss'):
                cache.execute(TASK, MODELS[0])

    def test_cache_key_includes_decoding_and_cost_uses_cached_rate(self):
        self.assertEqual(len(cache_key(TASK, MODELS[0])), 64)
        cost = calculate_cost(MODELS[0], {'prompt_tokens':1000, 'completion_tokens':100,
            'prompt_tokens_details': {'cached_tokens':400}})
        self.assertEqual(cost, .000152)

    def test_report_separates_metrics_and_categories(self):
        row = {'strategy':'random','category':'coding','policy_agreement':True,'success':True,
               'invalid_output':False,'constraint_violation':False,'routing_time_ms':1,
               'execution_latency_ms':100,'token_rate':20,'request_cost_usd':.001,
               'routing_error':None,'execution_error':None}
        report = build_report({'kind':'validation','benchmark_version':'v1','seed':1,
                               'workload_sha256':'abc','rows':[row]})
        self.assertEqual(report['aggregate']['random']['downstream_success'], 1)
        self.assertIn('coding', report['categories'])


if __name__ == '__main__':
    unittest.main()
