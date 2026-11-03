"""Pick the Command Code agent-x-model tasks: 10 per agent from `agents-v1`, by a fixed seeded rule.

    .venv/bin/python agents/pick_tasks.py            # writes benchmarking/suites/agents-cc-v1.manifest.json

Eligible: the agent's own tasks (group == agent). Code skips the two hard LiveCodeBench tasks and the two MBPP+
tasks that took over 100k input tokens in the free-tier run (code-10, code-20). Within an agent the order is a
shuffle seeded by SEED, so the first N per agent are a fair cut when the budget forces fewer tasks.
"""
import json
import pathlib
import random

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUITE = ROOT / 'benchmarking' / 'suites' / 'agents-v1.jsonl'
OUT = ROOT / 'benchmarking' / 'suites' / 'agents-cc-v1.manifest.json'
SEED = 20261031
PER_AGENT = 10
AGENTS = ['code', 'spreadsheet', 'data-analysis', 'docx', 'slides', 'diagram', 'map', 'scene-3d']
EXPENSIVE_CODE = {'code-10-mbppplus-468', 'code-20-mbppplus-590'}


def eligible(task):
    if task['group'] != task['agents'][0] or len(task['agents']) != 1:
        return False
    if task['group'] == 'code':
        return task.get('difficulty') != 'hard' and task['id'] not in EXPENSIVE_CODE
    return True


def main():
    tasks = [json.loads(l) for l in SUITE.read_text().splitlines() if l.strip()]
    picked = {}
    for agent in AGENTS:
        pool = sorted(t['id'] for t in tasks if t['group'] == agent and eligible(t))
        random.Random(f'{SEED}:{agent}').shuffle(pool)
        picked[agent] = pool[:PER_AGENT]
    OUT.write_text(json.dumps({'seed': SEED, 'per_agent': PER_AGENT, 'source_suite': 'agents-v1', 'tasks': picked}, indent=1) + '\n')
    print({a: len(v) for a, v in picked.items()})


if __name__ == '__main__':
    main()
