"""Routing policy: agent vote and model choice from similar past outcomes.

Agent: similarity-weighted vote over the k nearest tasks with known acceptable agents.
Model: for each candidate, the k nearest past outcomes of that model give a Beta posterior on success,
with a prior of strength `prior` centred on the model's global pass rate in memory. Latency and cost are
neighbour means shrunk toward the model's global mean with the same strength. The score is

    P(success) - w_time * latency / latency_scale - w_cost * cost / cost_scale

where the scales are fixed medians from training data, so weights are unitless. Greedy uses the posterior
mean; Thompson sampling draws P(success) from the posterior.
"""
import dataclasses

import numpy as np

PREFERENCES = ('accurate', 'balanced', 'fast', 'cheap')


def agent_vote(query, vectors, labels, k=10, exclude=None):
    """Rank agents for one task. labels[i] lists the acceptable agents of memory task i; an overlap task
    splits its vote evenly. Returns [(agent, share)] sorted by share, shares summing to 1."""
    sims = vectors @ query
    order = [i for i in np.argsort(-sims, kind='stable') if exclude is None or i not in exclude][:k]
    votes = {}
    for i in order:
        w = max(float(sims[i]), 1e-6)
        for a in labels[i]:
            votes[a] = votes.get(a, 0.0) + w / len(labels[i])
    total = sum(votes.values()) or 1.0
    return sorted(((a, v / total) for a, v in votes.items()), key=lambda x: (-x[1], x[0]))


@dataclasses.dataclass
class Estimate:
    alpha: float
    beta: float
    latency_s: float
    cost_usd: float
    neighbours: int

    @property
    def p_success(self):
        return self.alpha / (self.alpha + self.beta)


@dataclasses.dataclass
class Params:
    k: int = 10
    prior: float = 2.0
    latency_scale: float = 1.0
    cost_scale: float = 1.0
    weights: dict = dataclasses.field(default_factory=lambda: {p: (0.0, 0.0) for p in PREFERENCES})


class OutcomeTable:
    """Online model-choice memory: rows of (task vector, model, passed, latency, cost)."""

    def __init__(self, dim=384):
        self.dim = dim
        self.rows = {}  # model -> lists

    def add(self, vector, model, passed, latency_s, cost_usd):
        r = self.rows.setdefault(model, {'vec': [], 'passed': [], 'lat': [], 'cost': [], 'mat': None})
        r['vec'].append(np.asarray(vector, np.float32))
        r['passed'].append(float(passed))
        r['lat'].append(float(latency_s))
        r['cost'].append(float(cost_usd))
        r['mat'] = None

    def count(self, model):
        return len(self.rows.get(model, {'passed': []})['passed'])

    def _arrays(self, model):
        r = self.rows[model]
        if r['mat'] is None:
            r['mat'] = (np.stack(r['vec']), np.array(r['passed']), np.array(r['lat']), np.array(r['cost']))
        return r['mat']

    def estimate(self, query, model, params, prior_rate=None, prior_latency=None, prior_cost=None):
        """Beta posterior and shrunk latency/cost for one model. prior_* fill in when the model has no rows."""
        n = self.count(model)
        if n:
            vecs, passed, lat, cost = self._arrays(model)
            rate = (1 + passed.sum()) / (2 + n)
            g_lat, g_cost = lat.mean(), cost.mean()
            sims = vecs @ query
            top = np.argsort(-sims, kind='stable')[:params.k]
            w = np.clip(sims[top], 1e-6, None)
            hits, wsum = float(w @ passed[top]), float(w.sum())
            n_lat, n_cost = float(w @ lat[top]), float(w @ cost[top])
        else:
            rate, g_lat, g_cost = 0.5, 0.0, 0.0
            hits = wsum = n_lat = n_cost = 0.0
        if prior_rate is not None and n == 0:
            rate = prior_rate
        if prior_latency is not None and n == 0:
            g_lat = prior_latency
        if prior_cost is not None and n == 0:
            g_cost = prior_cost
        s = params.prior
        return Estimate(alpha=s * rate + hits, beta=s * (1 - rate) + (wsum - hits),
                        latency_s=(s * g_lat + n_lat) / (s + wsum), cost_usd=(s * g_cost + n_cost) / (s + wsum),
                        neighbours=min(n, params.k))


def utility(p, latency_s, cost_usd, preference, params):
    w_time, w_cost = params.weights[preference]
    return p - w_time * latency_s / params.latency_scale - w_cost * cost_usd / params.cost_scale


def choose_model(table, query, models, preference, params, mode='greedy', rng=None, priors=None):
    """Pick a model. Returns (model, ranked) where ranked is [(model, score, Estimate)] best first."""
    priors = priors or {}
    ranked = []
    for m in models:
        est = table.estimate(query, m, params, **priors.get(m, {}))
        p = rng.beta(est.alpha, est.beta) if mode == 'thompson' else est.p_success
        ranked.append((m, utility(p, est.latency_s, est.cost_usd, preference, params), est))
    ranked.sort(key=lambda x: -x[1])  # stable: ties keep the candidate order
    return ranked[0][0], ranked


# Tolerance rule for agent runs. The goal is "finish about as well as DeepSeek, as cheaply as possible":
# models whose estimated pass probability sits within `tolerance` of the reference model's are eligible, and
# the preference picks among them. `accurate` ignores cost and speed and takes the highest pass probability.
REFERENCE = 'deepseek/deepseek-v4.1-flash'
TARGET = {'balanced': 'cost_usd', 'cheap': 'cost_usd', 'fast': 'latency_s'}


def choose_by_tolerance(estimates, preference, tolerance, models=None, mode='greedy', rng=None, reference=REFERENCE):
    """Rank models for one agent. `estimates` maps model -> Estimate; `models` fixes the tie-break order
    (the reference model first). Returns (model, ranked) where ranked is [{model, p, eligible, ...}] best
    first: eligible models by cheapest (cheap, balanced) or fastest (fast), then the rest by pass probability.
    Thompson mode draws each model's pass probability from its Beta posterior before the rule runs."""
    models = list(models or estimates)
    p = {m: (float(rng.beta(estimates[m].alpha, estimates[m].beta)) if mode == 'thompson' else estimates[m].p_success)
         for m in models}
    ref_p = p.get(reference, max(p.values()))
    if preference == 'accurate':
        order = sorted(models, key=lambda m: (-p[m], models.index(m)))
        eligible = {m: m == order[0] or p[m] >= p[order[0]] - 1e-12 for m in models}
    else:
        eligible = {m: p[m] >= ref_p - tolerance - 1e-12 for m in models}
        key = TARGET[preference]
        order = sorted(models, key=lambda m: (not eligible[m],
                                              getattr(estimates[m], key) if eligible[m] else -p[m],
                                              models.index(m)))
    ranked = [{'model': m, 'p_pass': p[m], 'eligible': bool(eligible[m]), 'wall_s': float(estimates[m].latency_s),
               'cost_usd': float(estimates[m].cost_usd), 'neighbours': estimates[m].neighbours} for m in order]
    return order[0], ranked


def loto_splits(ids):
    """Leave-one-task-out: yield (held_out, train_ids) for every task. The held-out task never appears in train."""
    ids = list(ids)
    for i, held in enumerate(ids):
        yield held, ids[:i] + ids[i + 1:]
