"""Agent x model table for the paid Command Code run, for the agent router.

    .venv/bin/python agents/analyze_cc.py benchmarking/results/agents-cc-20261031

Reads runs.jsonl plus judge/judged.jsonl (judged runs pass with a passing automatic check and judge score >= 7).
Tables use only complete rows: (task, agent) pairs that every model finished and scored, so each model faces the
same tasks. Prints Markdown and writes analysis.json next to runs.jsonl.

Per agent x model: pass rate with a 95% Wilson interval, mean cost (proxy list-price count), median wall time.
Per agent: the cheapest model within 0.05 pass rate of DeepSeek, and the fastest by median wall time. A pick
counts as separated only when the two Wilson intervals do not overlap.
"""
import argparse
import json
import math
import pathlib
import statistics

AGENTS = ['code', 'spreadsheet', 'data-analysis', 'docx', 'slides', 'diagram', 'map', 'scene-3d']
MODELS = ['cc/deepseek/deepseek-v4.1-flash', 'cc/z-ai/glm-5.3-flash', 'cc/xiaomi/mimo-v2.6-flash',
          'cc/nvidia/nemotron-3.5-super-vl']
SHORT = {'cc/deepseek/deepseek-v4.1-flash': 'DeepSeek', 'cc/z-ai/glm-5.3-flash': 'GLM',
         'cc/xiaomi/mimo-v2.6-flash': 'MiMo', 'cc/nvidia/nemotron-3.5-super-vl': 'Nemotron'}
BASE = MODELS[0]
PASS_AT = 7
TOLERANCE = 0.05


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def load(run_dir):
    runs = [json.loads(l) for l in (run_dir / 'runs.jsonl').read_text().splitlines() if l.strip()]
    judged = {}
    path = run_dir / 'judge' / 'judged.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                j = json.loads(line)
                judged[j['key']] = j
    for r in runs:
        if r.get('needs_judge') and r.get('passed') is None and not r.get('not_run'):
            j = judged.get(f'{r["task_id"]}|{r["agent"]}|{r["model"]}')
            if j:
                r['passed'] = j['score'] >= PASS_AT
    return [r for r in runs if r['model'] in MODELS]


def cell(rs):
    k = sum(bool(r['passed']) for r in rs)
    lo, hi = wilson(k, len(rs))
    return {'n': len(rs), 'passed': k, 'rate': k / len(rs), 'lo': lo, 'hi': hi,
            'mean_cost': statistics.mean(r['cost_usd'] for r in rs),
            'median_wall_s': statistics.median(r['wall_s'] for r in rs)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run')
    args = parser.parse_args(argv)
    run_dir = pathlib.Path(args.run).resolve()
    runs = load(run_dir)
    finished = [r for r in runs if not r.get('not_run')]
    unscored = [r for r in finished if r.get('passed') is None]
    groups = {}
    for r in finished:
        groups.setdefault((r['agent'], r['task_id']), {})[r['model']] = r
    complete = {k: v for k, v in groups.items() if len(v) == len(MODELS) and all(x.get('passed') is not None for x in v.values())}
    out = {'finished_runs': len(finished), 'unscored_runs': len(unscored), 'complete_rows': len(complete),
           'incomplete_rows': len(groups) - len(complete), 'cells': {}, 'picks': {}}
    lines = [f'Finished runs {len(finished)}; unscored {len(unscored)}; complete rows (all four models scored) '
             f'{len(complete)} of {len(groups)}.', '']
    lines += ['Pass rate (passed/n), 95% Wilson interval; mean cost USD; median wall s:', '',
              '| Agent | ' + ' | '.join(SHORT[m] for m in MODELS) + ' |', '|---|' + '---|' * len(MODELS)]
    for a in AGENTS:
        cells = {}
        for m in MODELS:
            rs = [v[m] for (ag, _), v in complete.items() if ag == a]
            if rs:
                cells[m] = cell(rs)
        if not cells:
            continue
        out['cells'][a] = cells
        lines.append(f'| {a} | ' + ' | '.join(
            f'{c["rate"]:.2f} ({c["passed"]}/{c["n"]}) [{c["lo"]:.2f}, {c["hi"]:.2f}]; ${c["mean_cost"]:.4f}; {c["median_wall_s"]:.0f}s'
            if (c := cells.get(m)) else '-' for m in MODELS) + ' |')
        base = cells.get(BASE)
        ok = [m for m, c in cells.items() if base and c['rate'] >= base['rate'] - TOLERANCE]
        cheapest = min(ok, key=lambda m: cells[m]['mean_cost']) if ok else None
        fastest = min(cells, key=lambda m: cells[m]['median_wall_s'])
        pick = {'cheapest_within_0.05_of_deepseek': cheapest, 'fastest': fastest}
        if cheapest and base:
            c, b = cells[cheapest], base
            pick['cheapest_saving'] = 1 - c['mean_cost'] / b['mean_cost']
            # Separated: the pick's cost is below DeepSeek's AND its pass interval is not clearly below DeepSeek's.
            pick['cheapest_pass_separated_from_deepseek'] = cheapest != BASE and (c['lo'] > b['hi'] or c['hi'] < b['lo'])
        best = max(cells, key=lambda m: cells[m]['rate'])
        pick['best_pass'] = best
        pick['best_pass_separated_from_deepseek'] = bool(base) and best != BASE and cells[best]['lo'] > base['hi']
        pick['deepseek_separated_above'] = [m for m in cells if m != BASE and base and base['lo'] > cells[m]['hi']]
        out['picks'][a] = pick
    lines += ['', 'All agents pooled:', '', '| Model | Pass rate [95% CI] | Mean cost | Median wall s |', '|---|---|---:|---:|']
    for m in MODELS:
        rs = [v[m] for v in complete.values()]
        if rs:
            c = cell(rs)
            out['cells'].setdefault('all', {})[m] = c
            lines.append(f'| {SHORT[m]} | {c["rate"]:.3f} ({c["passed"]}/{c["n"]}) [{c["lo"]:.2f}, {c["hi"]:.2f}] | ${c["mean_cost"]:.4f} | {c["median_wall_s"]:.0f} |')
    lines += ['', 'Per-agent picks (cheapest within 0.05 pass rate of DeepSeek; fastest by median wall time):', '',
              '| Agent | Cheapest within 0.05 | Saving vs DeepSeek | Fastest | Intervals separate? |', '|---|---|---:|---|---|']
    for a, p in out['picks'].items():
        sep = []
        if p.get('cheapest_pass_separated_from_deepseek'):
            sep.append('cheapest pass differs from DeepSeek')
        if p['deepseek_separated_above']:
            sep.append('DeepSeek above ' + ', '.join(SHORT[m] for m in p['deepseek_separated_above']))
        lines.append(f'| {a} | {SHORT.get(p["cheapest_within_0.05_of_deepseek"], "-")} | '
                     f'{p.get("cheapest_saving", 0):.0%} | {SHORT[p["fastest"]]} | {"; ".join(sep) or "no"} |')
    cost = {}
    for r in finished:
        cost.setdefault(r['agent'], []).append(r['cost_usd'])
    out['mean_cost_per_run_by_agent'] = {a: statistics.mean(v) for a, v in cost.items()}
    out['total_usd'] = sum(r['cost_usd'] for r in finished)
    (run_dir / 'analysis.json').write_text(json.dumps(out, indent=1) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
