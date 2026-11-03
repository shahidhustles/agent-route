"""Replay: one model per chat from the Modal model router, against the per-agent table and always-DeepSeek.

    bun --env-file=.env.modal scripts/modal-picks.ts          # asks the deployed router, writes modal-picks.json
    .venv/bin/python routing/session_eval.py                  # writes artifacts/router/session.json

Each of the 80 `agents-cc-20261031` tasks is treated as the first message of its own chat. The Modal router sees the
task text only, picks a model per preference, and the outcome of that model on that task is looked up from the
recorded runs. The per-agent table numbers come from artifacts/router/loto.json (leave-one-task-out).
"""
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from agent_model import MODELS, PREFERENCES, load_grid  # noqa: E402
from memory import Memory  # noqa: E402
from pair_eval import paired_ci  # noqa: E402

SLUG = {'deepseek-v4.1-flash': 'deepseek/deepseek-v4.1-flash', 'glm-5.3-flash': 'z-ai/glm-5.3-flash',
        'mimo-v2.6-flash': 'xiaomi/mimo-v2.6-flash', 'nemotron-3.5-super-vl': 'nvidia/nemotron-3.5-super-vl'}
OUT = ROOT / 'artifacts' / 'router'


def main():
    grid = load_grid(Memory.load())
    tasks = sorted(grid.outcomes)
    picks = {}
    for row in json.loads((OUT / 'modal-picks.json').read_text()):
        picks[(row['task_id'], row['preference'])] = SLUG[row['model_slug']]
    loto = json.loads((OUT / 'loto.json').read_text())['preferences']
    ref = [grid.outcomes[t]['deepseek/deepseek-v4.1-flash'] for t in tasks]
    result = {}
    for pref in PREFERENCES:
        chosen = [grid.outcomes[t][picks[(t, pref)]] for t in tasks]
        passed = np.array([c[0] for c in chosen])
        cost = np.array([c[2] for c in chosen])
        wall = np.array([c[1] for c in chosen])
        d_pass = paired_ci(passed, [r[0] for r in ref])
        d_cost = paired_ci(cost, [r[2] for r in ref])
        share = {m: round(sum(picks[(t, pref)] == m for t in tasks) / len(tasks), 3) for m in MODELS}
        table = loto[pref]['per_agent_table']
        result[pref] = {
            'modal_session': {'pass': float(passed.mean()), 'mean_cost_usd': float(cost.mean()),
                              'median_wall_s': float(np.median(wall)), 'model_share': share,
                              'pass_vs_deepseek_ci95': d_pass, 'cost_vs_deepseek_ci95': d_cost},
            'per_agent_table': {k: table[k] for k in ('pass', 'mean_cost_usd', 'median_wall_s', 'model_share')},
            'always_deepseek': {k: loto[pref]['always_deepseek'][k] for k in ('pass', 'mean_cost_usd', 'median_wall_s')}}
        print(pref, 'modal', round(passed.mean(), 3), round(cost.mean(), 5), round(float(np.median(wall)), 1), share,
              '| table', table['pass'], round(table['mean_cost_usd'], 5), round(table['median_wall_s'], 1),
              '| deepseek', loto[pref]['always_deepseek']['pass'], round(loto[pref]['always_deepseek']['mean_cost_usd'], 5))
    (OUT / 'session.json').write_text(json.dumps({'tasks': len(tasks), 'preferences': result}, indent=1))


if __name__ == '__main__':
    main()
