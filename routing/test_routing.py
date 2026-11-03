import json
import pathlib
import sys
import tempfile
import unittest

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import memory  # noqa: E402
from agents_eval import accuracy, split_tasks  # noqa: E402
from policy import OutcomeTable, Params, agent_vote, choose_model, utility  # noqa: E402
from replay import Dataset, run_stream  # noqa: E402


def unit(*xs):
    v = np.array(xs, np.float32)
    return v / np.linalg.norm(v)


class AgentVoteTest(unittest.TestCase):
    def test_nearest_labels_win_and_overlap_splits_its_vote(self):
        vecs = np.stack([unit(1, 0), unit(0.9, 0.1), unit(0, 1)])
        labels = [['code'], ['code', 'spreadsheet'], ['map']]
        ranked = agent_vote(unit(1, 0), vecs, labels, k=2)
        self.assertEqual(ranked[0][0], 'code')
        self.assertAlmostEqual(sum(s for _, s in ranked), 1.0)
        shares = dict(ranked)
        self.assertGreater(shares['code'], shares['spreadsheet'])
        self.assertNotIn('map', shares)

    def test_exclude_drops_the_task_itself(self):
        vecs = np.stack([unit(1, 0), unit(0, 1)])
        ranked = agent_vote(unit(1, 0), vecs, [['code'], ['map']], k=1, exclude={0})
        self.assertEqual(ranked[0][0], 'map')


class EstimateTest(unittest.TestCase):
    def test_empty_model_uses_given_priors(self):
        est = OutcomeTable().estimate(unit(1, 0), 'm', Params(prior=4), prior_rate=0.75, prior_latency=9.0)
        self.assertAlmostEqual(est.p_success, 0.75)
        self.assertAlmostEqual(est.latency_s, 9.0)
        self.assertEqual(est.neighbours, 0)

    def test_posterior_mixes_global_rate_and_weighted_neighbours(self):
        t = OutcomeTable()
        t.add(unit(1, 0), 'm', 1, 2.0, 0.1)
        t.add(unit(0, 1), 'm', 0, 10.0, 0.3)
        p = Params(k=1, prior=2)
        est = t.estimate(unit(1, 0), 'm', p)
        # global rate (1+1)/(2+2) = 0.5; nearest neighbour passed with similarity 1
        self.assertAlmostEqual(est.alpha, 2 * 0.5 + 1)
        self.assertAlmostEqual(est.beta, 2 * 0.5)
        self.assertAlmostEqual(est.latency_s, (2 * 6.0 + 2.0) / 3)
        self.assertEqual(est.neighbours, 1)

    def test_utility_uses_scaled_weights(self):
        p = Params(latency_scale=10, cost_scale=0.01, weights={'fast': (0.5, 0.0), 'cheap': (0.0, 1.0)})
        self.assertAlmostEqual(utility(0.9, 20, 0.02, 'fast', p), 0.9 - 1.0)
        self.assertAlmostEqual(utility(0.9, 20, 0.02, 'cheap', p), 0.9 - 2.0)


class ChooseModelTest(unittest.TestCase):
    def setUp(self):
        self.t = OutcomeTable()
        for _ in range(5):
            self.t.add(unit(1, 0), 'strong', 1, 30.0, 0.002)
            self.t.add(unit(1, 0), 'fast', 1, 2.0, 0.001)
        self.t.add(unit(1, 0), 'fast', 0, 2.0, 0.001)
        self.params = Params(k=10, prior=1, latency_scale=10, cost_scale=0.001,
                             weights={'accurate': (0, 0), 'fast': (0.1, 0), 'cheap': (0, 0.1), 'balanced': (0.05, 0.05)})

    def test_accurate_prefers_higher_pass_rate(self):
        m, ranked = choose_model(self.t, unit(1, 0), ['fast', 'strong'], 'accurate', self.params)
        self.assertEqual(m, 'strong')
        self.assertEqual([r[0] for r in ranked], ['strong', 'fast'])

    def test_fast_trades_a_little_success_for_latency(self):
        m, _ = choose_model(self.t, unit(1, 0), ['fast', 'strong'], 'fast', self.params)
        self.assertEqual(m, 'fast')

    def test_thompson_is_reproducible_with_a_seed(self):
        picks = [choose_model(self.t, unit(1, 0), ['fast', 'strong'], 'accurate', self.params, mode='thompson',
                              rng=np.random.default_rng(3))[0] for _ in range(2)]
        self.assertEqual(picks[0], picks[1])


class ReplayTest(unittest.TestCase):
    def dataset(self):
        rng = np.random.default_rng(0)
        outcomes, vectors, split = {}, {}, {}
        for i in range(30):
            easy = i % 2 == 0
            outcomes[f't{i}'] = {'strong': (1.0, 20.0, 0.002), 'fast': (1.0 if easy else 0.0, 2.0, 0.001)}
            vectors[f't{i}'] = unit(1, 0.05 * rng.random()) if easy else unit(0.05 * rng.random(), 1)
            split[f't{i}'] = 'test' if i >= 20 else 'train'
        return Dataset('toy', ['strong', 'fast'], outcomes, vectors, split)

    def test_oracle_has_no_regret_and_knn_uses_bandit_feedback(self):
        ds = self.dataset()
        params = Params(k=5, prior=1, latency_scale=10, cost_scale=0.001)
        params.weights['fast'] = (0.1, 0.0)
        logs = run_stream(ds, 'oracle', 'fast', params, ds.ids['train'], ds.ids['test'], 0, 'strong')
        self.assertEqual(sum(r for *_, r in logs), 0)
        logs = run_stream(ds, 'knn_greedy', 'fast', params, ds.ids['train'], ds.ids['test'], 0, 'strong')
        self.assertEqual(len(logs), 30)
        self.assertTrue(all(r >= 0 for *_, r in logs))

    def test_full_memory_routes_by_similarity(self):
        ds = self.dataset()
        params = Params(k=5, prior=1, latency_scale=10, cost_scale=0.001)
        params.weights['fast'] = (0.1, 0.0)
        logs = run_stream(ds, 'knn_full_memory', 'fast', params, [], ds.ids['test'], 0, 'strong')
        self.assertEqual({p for p, *_ in logs}, {'test'})
        self.assertEqual(sum(r for *_, r in logs), 0)  # easy -> fast, hard -> strong


class AgentSplitTest(unittest.TestCase):
    def test_split_is_stratified_and_deterministic(self):
        tasks = [{'id': f'{g}-{i}', 'group': g} for g, n in (('code', 20), ('overlap', 40)) for i in range(n)]
        a, b = split_tasks(tasks), split_tasks(list(reversed(tasks)))
        self.assertEqual(a, b)
        count = lambda g, s: sum(1 for t in tasks if t['group'] == g and a[t['id']] == s)
        self.assertEqual((count('code', 'test'), count('code', 'validation'), count('code', 'train')), (8, 2, 10))
        self.assertEqual((count('overlap', 'test'), count('overlap', 'validation')), (16, 4))

    def test_overlap_task_accepts_any_listed_agent(self):
        rows = [{'agents': ['docx', 'slides']}, {'agents': ['code']}]
        self.assertEqual(accuracy(rows, ['slides', 'map']), 0.5)


class MemoryTest(unittest.TestCase):
    def test_agent_records_skip_not_run_and_count_cached_input(self):
        with tempfile.TemporaryDirectory() as d:
            run = pathlib.Path(d)
            rows = [{'task_id': 'a', 'agent': 'code', 'model': 'm', 'passed': True, 'wall_s': 5.0,
                     'input_tokens': 10, 'cache_read_tokens': 90, 'output_tokens': 7},
                    {'task_id': 'a', 'agent': 'code', 'model': 'n', 'passed': None, 'not_run': True}]
            (run / 'runs.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            recs = memory.agent_records(run, {'a': {}})
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]['input_tokens'], 100)
        self.assertEqual(recs[0]['cost_usd'], 0.0)

    def test_online_append_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / 'records.jsonl').write_text('')
            (d / 'tasks.jsonl').write_text(json.dumps({'task_id': 'a', 'text': 'x'}) + '\n')
            np.save(d / 'embeddings.npy', np.stack([unit(1, 0)]))
            mem = memory.Memory.load(d)
            rec = {'task_id': 'b', 'agent': 'code', 'model': 'm', 'passed': True, 'latency_s': 1.0}
            mem.append_online(d / 'online.jsonl', rec, {'task_id': 'b', 'text': 'y'}, unit(0, 1))
            again = memory.Memory.load(d, online=d / 'online.jsonl')
        self.assertEqual(len(again.records), 1)
        self.assertIn('b', again.vectors)
        self.assertAlmostEqual(float(again.vectors['b'][1]), 1.0, places=5)


if __name__ == '__main__':
    unittest.main()
