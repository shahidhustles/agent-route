"""Model choice for a chosen agent, from real agent runs (`agents-cc-20261031` plus online records).

PairTable keeps one OutcomeTable per agent. For one task and agent it returns, per model, a Beta posterior on
passing (prior centred on that agent-model pair's own pass rate, shrunk towards the similarity-weighted
neighbours among the agent's past tasks), plus wall time and cost estimates. A pair with no rows borrows the
model's pooled rate over all agents, and before any agent run exists, its single-call rate from the chat records.

Grid is the complete outcome table the evaluation replays: grid.outcomes[task][model] = (passed, wall_s, cost_usd)
for the agent that ran the task. select_tolerance picks the pass tolerance of policy.choose_by_tolerance on a set
of tasks by leave-one-task-out, so the choice never uses the outcome it is later scored on.
"""
import dataclasses
import statistics

import numpy as np

from policy import REFERENCE, Estimate, OutcomeTable, Params, choose_by_tolerance

MODELS = [REFERENCE, 'z-ai/glm-5.3-flash', 'xiaomi/mimo-v2.6-flash', 'nvidia/nemotron-3.5-super-vl']
SHORT = {'deepseek/deepseek-v4.1-flash': 'DeepSeek', 'z-ai/glm-5.3-flash': 'GLM', 'xiaomi/mimo-v2.6-flash': 'MiMo',
         'nvidia/nemotron-3.5-super-vl': 'Nemotron'}
AGENT_RUN = 'agents-cc-20261031'
TOLERANCES = [0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 1.0]
# How much pass rate the tolerance search may give up against always-DeepSeek (inner leave-one-out), per preference.
SLACK = {'balanced': 0.02, 'cheap': 0.05, 'fast': 0.05}
PREFERENCES = ('accurate', 'balanced', 'fast', 'cheap')
PARAMS = Params(k=10, prior=2.0)


@dataclasses.dataclass
class Grid:
    outcomes: dict  # task -> model -> (passed, wall_s, cost_usd)
    agent: dict     # task -> agent that ran it
    vectors: dict   # task -> embedding

    @property
    def ids(self):
        return sorted(self.outcomes)


def load_grid(mem, run=AGENT_RUN, models=MODELS):
    """Tasks that every model finished and scored in one agent run."""
    outcomes, agent = {}, {}
    for r in mem.records:
        if r['run'] == run and r['model'] in models and r['passed'] is not None:
            outcomes.setdefault(r['task_id'], {})[r['model']] = (float(r['passed']), r['latency_s'], r['cost_usd'])
            agent[r['task_id']] = r['agent']
    outcomes = {t: o for t, o in outcomes.items() if len(o) == len(models)}
    return Grid(outcomes, {t: agent[t] for t in outcomes}, {t: mem.vectors[t] for t in outcomes})


def chat_priors(mem, models=MODELS):
    """Single-call pass rate, wall time and cost per model: the prior before any agent run exists."""
    out = {}
    for m in models:
        rows = [r for r in mem.records if r['agent'] == 'chat' and r['model'] == m and r['passed'] is not None]
        if rows:
            out[m] = {'prior_rate': (1 + sum(r['passed'] for r in rows)) / (2 + len(rows)),
                      'prior_latency': statistics.mean(r['latency_s'] for r in rows),
                      'prior_cost': statistics.mean(r['cost_usd'] for r in rows)}
    return out


class PairTable:
    """Agent x model outcome memory with pooled per-model fallbacks."""

    def __init__(self, priors=None):
        self.tables = {}
        self.pool = {}  # model -> [n, passes, wall, cost]
        self.priors = priors or {}

    def add(self, vector, agent, model, passed, wall_s, cost_usd):
        self.tables.setdefault(agent, OutcomeTable()).add(vector, model, passed, wall_s, cost_usd)
        p = self.pool.setdefault(model, [0, 0.0, 0.0, 0.0])
        p[0] += 1
        p[1] += float(passed)
        p[2] += wall_s
        p[3] += cost_usd

    def count(self, agent, model):
        return self.tables[agent].count(model) if agent in self.tables else 0

    def _prior(self, model):
        n, passes, wall, cost = self.pool.get(model, [0, 0, 0, 0])
        if n:
            return {'prior_rate': (1 + passes) / (2 + n), 'prior_latency': wall / n, 'prior_cost': cost / n}
        return self.priors.get(model, {})

    def estimates(self, vector, agent, models=MODELS, params=PARAMS):
        table = self.tables.get(agent) or OutcomeTable()
        return {m: table.estimate(vector, m, params, **self._prior(m)) for m in models}


def build_table(grid, ids, priors=None):
    table = PairTable(priors)
    for t in ids:
        for m, (passed, wall, cost) in grid.outcomes[t].items():
            table.add(grid.vectors[t], grid.agent[t], m, passed, wall, cost)
    return table


def knn_estimates(grid, train_ids, task, priors=None):
    return build_table(grid, train_ids, priors).estimates(grid.vectors[task], grid.agent[task])


def table_estimates(grid, train_ids, task, priors=None):
    """Per-agent table: that agent's pass rate, median wall time and mean cost per model over the training tasks."""
    same = [t for t in train_ids if grid.agent[t] == grid.agent[task]]
    out = {}
    for m in MODELS:
        o = [grid.outcomes[t][m] for t in same]
        passes = sum(x[0] for x in o)
        out[m] = Estimate(alpha=1 + passes, beta=1 + len(o) - passes,
                          latency_s=statistics.median(x[1] for x in o) if o else 0.0,
                          cost_usd=statistics.mean(x[2] for x in o) if o else 0.0, neighbours=len(o))
    return out


ESTIMATORS = {'knn': knn_estimates, 'table': table_estimates}


def select_tolerance(grid, ids, estimator='knn', priors=None, tolerances=TOLERANCES):
    """Pick one tolerance per preference using only `ids`. Each task in `ids` is estimated from the others
    (leave-one-task-out), then for every tolerance the picks' mean pass, wall time and cost are measured.
    The chosen tolerance minimises cost (balanced, cheap) or wall time (fast) subject to pass staying within
    SLACK of always-DeepSeek on the same tasks; with none feasible it falls back to 0. `accurate` needs none."""
    est = ESTIMATORS[estimator]
    inner = {j: est(grid, [t for t in ids if t != j], j, priors) for j in ids}
    base_pass = statistics.mean(grid.outcomes[t][REFERENCE][0] for t in ids)
    chosen, detail = {}, {}
    for pref, slack in SLACK.items():
        rows = []
        for tol in tolerances:
            picks = [choose_by_tolerance(inner[j], pref, tol, MODELS)[0] for j in ids]
            o = [grid.outcomes[j][m] for j, m in zip(ids, picks)]
            rows.append({'tolerance': tol, 'pass': statistics.mean(x[0] for x in o),
                         'wall_s': statistics.mean(x[1] for x in o), 'cost_usd': statistics.mean(x[2] for x in o)})
        col = 'wall_s' if pref == 'fast' else 'cost_usd'
        ok = [r for r in rows if r['pass'] >= base_pass - slack - 1e-9]
        chosen[pref] = min(ok, key=lambda r: (r[col], r['tolerance']))['tolerance'] if ok else 0.0
        detail[pref] = rows
    chosen['accurate'] = 0.0
    return chosen, {'always_deepseek_pass': base_pass, 'search': detail}
