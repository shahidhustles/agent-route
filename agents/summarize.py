"""Summarise a phase 2 agent run: pass rate per agent x model, wall time, tokens, and overlap outcomes.

    .venv/bin/python agents/summarize.py benchmarking/results/<run>

Reads runs.jsonl and, for judged runs not yet merged, judge/judged.jsonl. Prints Markdown tables and writes
summary.json next to runs.jsonl. A judged run counts as passed only with a passing automatic check and a
judge score >= 7; runs still waiting for the judge are left out of pass rates and counted separately.
"""
import argparse
import json
import pathlib
import statistics

AGENTS = ['code', 'spreadsheet', 'data-analysis', 'docx', 'slides', 'diagram', 'map', 'scene-3d']
SHORT = {'opencode/deepseek-v4.1-flash-free': 'DeepSeek', 'opencode/nemotron-3.5-super-vl-free': 'Nemotron',
         'opencode/glm-5.3-flash-free': 'GLM', 'opencode/mimo-v2.6-flash-free': 'MiMo',
         'cc/deepseek/deepseek-v4.1-flash': 'DeepSeek', 'cc/nvidia/nemotron-3.5-super-vl': 'Nemotron',
         'cc/z-ai/glm-5.3-flash': 'GLM', 'cc/xiaomi/mimo-v2.6-flash': 'MiMo'}


def load(run_dir, pass_at):
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
                r['judge'] = {'score': j['score'], 'note': j['note']}
                r['passed'] = j['score'] >= pass_at
    return runs


def fmt_rate(rs):
    scored = [r for r in rs if r.get('passed') is not None and not r.get('not_run')]
    if not scored:
        return '-'
    return f'{sum(r["passed"] for r in scored) / len(scored):.2f} ({sum(r["passed"] for r in scored)}/{len(scored)})'


def med(xs):
    return statistics.median(xs) if xs else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run')
    parser.add_argument('--pass-at', type=int, default=7)
    args = parser.parse_args(argv)
    run_dir = pathlib.Path(args.run).resolve()
    runs = load(run_dir, args.pass_at)
    models = [m for m in SHORT if any(r['model'] == m for r in runs)]
    done = [r for r in runs if not r.get('not_run')]
    out = {'records': len(runs), 'not_run': len(runs) - len(done),
           'waiting_for_judge': sum(1 for r in done if r.get('passed') is None)}
    lines = [f'Records: {len(runs)} ({out["not_run"]} not run, {out["waiting_for_judge"]} waiting for the judge).', '']

    lines += ['Pass rate by agent (all tasks the agent ran, overlap included):', '',
              '| Agent | ' + ' | '.join(SHORT[m] for m in models) + ' |', '|---|' + '---:|' * len(models)]
    table = {}
    for a in AGENTS:
        row = []
        for m in models:
            rs = [r for r in runs if r['agent'] == a and r['model'] == m]
            row.append(fmt_rate(rs))
            table[f'{a}|{m}'] = row[-1]
        lines.append(f'| {a} | ' + ' | '.join(row) + ' |')
    lines.append('| all | ' + ' | '.join(fmt_rate([r for r in runs if r['model'] == m]) for m in models) + ' |')
    out['pass_rate'] = table

    lines += ['', 'Cost per run by model (median wall time; mean model calls and tokens; input = new + cached):', '',
              '| Model | Runs | Median wall (s) | Calls | Input tokens | Cached share | Output tokens | Timeouts | Errors |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    out['cost'] = {}
    for m in models:
        rs = [r for r in done if r['model'] == m]
        if not rs:
            continue
        inp = statistics.mean(r['input_tokens'] + r['cache_read_tokens'] for r in rs)
        cached = sum(r['cache_read_tokens'] for r in rs) / max(1, sum(r['input_tokens'] + r['cache_read_tokens'] for r in rs))
        row = {'runs': len(rs), 'median_wall_s': med([r['wall_s'] for r in rs]),
               'mean_calls': statistics.mean(r['model_calls'] for r in rs), 'mean_input': inp, 'cached_share': cached,
               'mean_output': statistics.mean(r['output_tokens'] for r in rs),
               'timeouts': sum(bool(r.get('timed_out')) for r in rs), 'errors': sum(bool(r.get('errors')) for r in rs)}
        out['cost'][m] = row
        lines.append(f'| {SHORT[m]} | {row["runs"]} | {row["median_wall_s"]:.0f} | {row["mean_calls"]:.1f} | '
                     f'{row["mean_input"]:,.0f} | {row["cached_share"]:.2f} | {row["mean_output"]:,.0f} | '
                     f'{row["timeouts"]} | {row["errors"]} |')

    lines += ['', 'Median wall time (s) by agent:', '', '| Agent | ' + ' | '.join(SHORT[m] for m in models) + ' |',
              '|---|' + '---:|' * len(models)]
    for a in AGENTS:
        cells = []
        for m in models:
            w = med([r['wall_s'] for r in done if r['agent'] == a and r['model'] == m])
            cells.append('-' if w is None else f'{w:.0f}')
        lines.append(f'| {a} | ' + ' | '.join(cells) + ' |')

    # Overlap tasks: per task and model, which acceptable agents passed.
    ov = [r for r in done if r.get('overlap')]
    groups = {}
    for r in ov:
        groups.setdefault((r['task_id'], r['model']), []).append(r)
    families = {}
    for (tid, m), rs in groups.items():
        fam = '-'.join(tid.split('-')[:2])
        f = families.setdefault((fam, m), {'tasks': 0, 'any': 0, 'by_agent': {}, 'only': {}, 'agents': set()})
        if any(r['passed'] is None for r in rs):
            continue
        f['tasks'] += 1
        winners = [r['agent'] for r in rs if r['passed']]
        f['any'] += bool(winners)
        for r in rs:
            f['agents'].add(r['agent'])
            f['by_agent'][r['agent']] = f['by_agent'].get(r['agent'], 0) + bool(r['passed'])
        if len(winners) == 1:
            f['only'][winners[0]] = f['only'].get(winners[0], 0) + 1
    lines += ['', 'Overlap tasks: tasks where at least one acceptable agent passed, and passes per agent:', '',
              '| Overlap family | Model | Tasks | Any agent passed | Passes per agent | Only this agent passed |',
              '|---|---|---:|---:|---|---|']
    out['overlap'] = {}
    for (fam, m), f in sorted(families.items(), key=lambda kv: (kv[0][0], models.index(kv[0][1]))):
        per = ', '.join(f'{a} {n}' for a, n in sorted(f['by_agent'].items()))
        only = ', '.join(f'{a} {n}' for a, n in sorted(f['only'].items())) or '-'
        lines.append(f'| {fam} | {SHORT[m]} | {f["tasks"]} | {f["any"]} | {per} | {only} |')
        out['overlap'][f'{fam}|{m}'] = {k: (sorted(v) if isinstance(v, set) else v) for k, v in f.items()}

    judged = [r for r in done if r.get('judge')]
    if judged:
        lines += ['', 'Judge scores (runs that passed the automatic check), mean score and share >= 7:', '',
                  '| Agent | ' + ' | '.join(SHORT[m] for m in models) + ' |', '|---|' + '---:|' * len(models)]
        for a in ('docx', 'slides', 'map'):
            cells = []
            for m in models:
                s = [r['judge']['score'] for r in judged if r['agent'] == a and r['model'] == m]
                cells.append(f'{statistics.mean(s):.1f}, {sum(x >= args.pass_at for x in s) / len(s):.2f}' if s else '-')
            lines.append(f'| {a} | ' + ' | '.join(cells) + ' |')

    text = '\n'.join(lines)
    print(text)
    (run_dir / 'summary.json').write_text(json.dumps(out, indent=1, default=str) + '\n')
    (run_dir / 'summary.md').write_text(text + '\n')


if __name__ == '__main__':
    main()
