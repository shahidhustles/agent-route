import pathlib
import sys
import unittest

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agent_model import MODELS, Grid, PairTable, select_tolerance, table_estimates  # noqa: E402
from pair_eval import loto_picks, oracle_pick  # noqa: E402
from policy import REFERENCE, Estimate, choose_by_tolerance, loto_splits  # noqa: E402

DS, GLM, MIMO, NEM = MODELS


def est(p, wall, cost, n=100):
    return Estimate(alpha=p * n, beta=(1 - p) * n, latency_s=wall, cost_usd=cost, neighbours=10)


class ToleranceRuleTest(unittest.TestCase):
    def setUp(self):
        self.e = {DS: est(0.90, 20, 0.0050), GLM: est(0.86, 15, 0.0030), MIMO: est(0.70, 60, 0.0010),
                  NEM: est(0.88, 5, 0.0080)}

    def test_cheapest_within_tolerance_of_deepseek(self):
        # GLM is 0.04 below DeepSeek, MiMo is 0.20 below
        self.assertEqual(choose_by_tolerance(self.e, 'cheap', 0.05, MODELS)[0], GLM)
        self.assertEqual(choose_by_tolerance(self.e, 'balanced', 0.05, MODELS)[0], GLM)
        self.assertEqual(choose_by_tolerance(self.e, 'cheap', 0.01, MODELS)[0], DS)
        self.assertEqual(choose_by_tolerance(self.e, 'cheap', 0.25, MODELS)[0], MIMO)

    def test_fast_takes_the_fastest_eligible_model(self):
        self.assertEqual(choose_by_tolerance(self.e, 'fast', 0.05, MODELS)[0], NEM)
        self.assertEqual(choose_by_tolerance(self.e, 'fast', 0.0, MODELS)[0], DS)  # Nemotron 0.88 < 0.90

    def test_accurate_takes_the_highest_pass_and_ties_go_to_deepseek(self):
        self.assertEqual(choose_by_tolerance(self.e, 'accurate', 0.3, MODELS)[0], DS)
        tie = {**self.e, GLM: est(0.90, 15, 0.0030)}
        self.assertEqual(choose_by_tolerance(tie, 'accurate', 0.0, MODELS)[0], DS)
        better = {**self.e, GLM: est(0.95, 15, 0.0030)}
        self.assertEqual(choose_by_tolerance(better, 'accurate', 0.0, MODELS)[0], GLM)

    def test_ranking_lists_eligible_first_and_marks_them(self):
        _, ranked = choose_by_tolerance(self.e, 'cheap', 0.05, MODELS)
        self.assertEqual(ranked[0]['model'], GLM)
        self.assertEqual({r['model'] for r in ranked if r['eligible']}, {DS, GLM, NEM})
        self.assertEqual(ranked[-1]['model'], MIMO)

    def test_thompson_with_a_seed_repeats(self):
        a = choose_by_tolerance(self.e, 'cheap', 0.05, MODELS, 'thompson', np.random.default_rng(1))[0]
        b = choose_by_tolerance(self.e, 'cheap', 0.05, MODELS, 'thompson', np.random.default_rng(1))[0]
        self.assertEqual(a, b)


class LeaveOneOutTest(unittest.TestCase):
    def test_every_task_is_held_out_once_and_never_in_its_own_train(self):
        ids = [f't{i}' for i in range(7)]
        folds = list(loto_splits(ids))
        self.assertEqual([h for h, _ in folds], ids)
        for held, train in folds:
            self.assertNotIn(held, train)
            self.assertEqual(sorted(train + [held]), sorted(ids))

    def grid(self, flip=None):
        """Twelve code tasks; GLM passes all but is cheaper, MiMo fails everything."""
        rng = np.random.default_rng(0)
        outcomes, agent, vectors = {}, {}, {}
        for i in range(12):
            v = rng.normal(size=8).astype(np.float32)
            vectors[f't{i}'] = v / np.linalg.norm(v)
            agent[f't{i}'] = 'code'
            outcomes[f't{i}'] = {DS: (1.0, 20.0, 0.005), GLM: (1.0, 10.0, 0.002), MIMO: (0.0, 50.0, 0.001),
                                 NEM: (1.0, 5.0, 0.008)}
        if flip:
            outcomes[flip] = {m: (1.0 - o[0], o[1], o[2]) for m, o in outcomes[flip].items()}
        return Grid(outcomes, agent, vectors)

    def test_pick_never_uses_the_held_out_tasks_own_outcome(self):
        base, _ = loto_picks(self.grid(), seeds=2)
        for target in ('t3', 't8'):
            flipped, _ = loto_picks(self.grid(flip=target), seeds=2)
            for key in base:
                if key[0] in ('oracle', 'random'):
                    continue
                self.assertEqual(base[key][target], flipped[key][target], (key, target))

    def test_cheap_learns_the_cheaper_model_that_passes(self):
        picks, _ = loto_picks(self.grid(), seeds=2)
        # MiMo is cheapest but never passes, so no tolerance the search accepts lets it in
        self.assertEqual(picks[('knn_greedy', 'cheap')]['t0'], [GLM])

    def test_tolerance_search_falls_back_to_zero_when_cheaper_models_lose_passes(self):
        g = self.grid()
        tol, detail = select_tolerance(g, g.ids)
        self.assertEqual(tol['accurate'], 0.0)
        self.assertGreaterEqual(detail['always_deepseek_pass'], 1.0)
        picks_cost = [r for r in detail['search']['cheap'] if r['tolerance'] == tol['cheap']][0]
        self.assertGreaterEqual(picks_cost['pass'], 1.0 - 0.05)


class PairTableTest(unittest.TestCase):
    def test_unseen_pair_borrows_the_pooled_model_rate(self):
        t = PairTable({GLM: {'prior_rate': 0.5, 'prior_latency': 1.0, 'prior_cost': 0.1}})
        v = np.array([1.0, 0.0], np.float32)
        t.add(v, 'code', GLM, 1.0, 10.0, 0.002)
        t.add(v, 'code', GLM, 1.0, 10.0, 0.002)
        e = t.estimates(v, 'diagram')[GLM]  # no diagram rows: pooled rate (1+2)/(2+2) = 0.75
        self.assertAlmostEqual(e.p_success, 0.75)
        self.assertAlmostEqual(e.cost_usd, 0.002)
        self.assertAlmostEqual(t.estimates(v, 'diagram')[DS].p_success, 0.5)  # nothing known about DeepSeek

    def test_empty_table_table_estimate_is_flat(self):
        g = LeaveOneOutTest().grid()
        e = table_estimates(g, [], 't0')
        self.assertAlmostEqual(e[DS].p_success, 0.5)


class OracleTest(unittest.TestCase):
    def test_oracle_picks_cheapest_or_fastest_passing_model(self):
        g = LeaveOneOutTest().grid()
        self.assertEqual(oracle_pick(g, 't0', 'cheap'), GLM)
        self.assertEqual(oracle_pick(g, 't0', 'fast'), NEM)
        g.outcomes['t0'] = {m: (0.0, o[1], o[2]) for m, o in g.outcomes['t0'].items()}
        self.assertEqual(oracle_pick(g, 't0', 'cheap'), REFERENCE)


if __name__ == '__main__':
    unittest.main()
