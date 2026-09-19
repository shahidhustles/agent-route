"""Aggregate evaluation rows and write Markdown plus machine-readable summaries."""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def metrics(rows):
    count = len(rows)
    values = lambda key: [row[key] for row in rows if row[key] is not None]
    return {
        'count': count,
        'policy_agreement': sum(row['policy_agreement'] for row in rows) / count,
        'downstream_success': sum(row['success'] for row in rows) / count,
        'invalid_output_rate': sum(row['invalid_output'] for row in rows) / count,
        'constraint_violation_rate': sum(row['constraint_violation'] for row in rows) / count,
        'routing_latency_median_ms': statistics.median(values('routing_time_ms')),
        'execution_latency_median_ms': statistics.median(values('execution_latency_ms')),
        'token_rate_median': statistics.median(values('token_rate')) if values('token_rate') else None,
        'request_cost_usd': round(sum(values('request_cost_usd')), 8),
        'routing_errors': sum(row['routing_error'] is not None for row in rows),
        'execution_errors': sum(row['execution_error'] is not None for row in rows),
    }


def build_report(result):
    by_strategy = defaultdict(list)
    by_category = defaultdict(lambda: defaultdict(list))
    for row in result['rows']:
        by_strategy[row['strategy']].append(row)
        by_category[row['category']][row['strategy']].append(row)
    return {
        'kind': result['kind'],
        'benchmark_version': result['benchmark_version'],
        'seed': result['seed'],
        'workload_sha256': result['workload_sha256'],
        'aggregate': {key: metrics(rows) for key, rows in sorted(by_strategy.items())},
        'categories': {category: {key: metrics(rows) for key, rows in sorted(groups.items())}
                       for category, groups in sorted(by_category.items())},
    }


def markdown(report):
    lines = [f'# Routing strategy evaluation', '',
             f'Run kind: `{report["kind"]}`. Benchmark: `{report["benchmark_version"]}`. '
             f'Seed: `{report["seed"]}`. Workload SHA-256: `{report["workload_sha256"]}`.', '',
             '| Strategy | Agreement | Success | Invalid | Violations | Route ms | Zen ms | tok/s | Cost USD | Errors |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name, item in report['aggregate'].items():
        lines.append(f'| {name} | {item["policy_agreement"]:.1%} | {item["downstream_success"]:.1%} | '
                     f'{item["invalid_output_rate"]:.1%} | {item["constraint_violation_rate"]:.1%} | '
                     f'{item["routing_latency_median_ms"]:.3f} | {item["execution_latency_median_ms"]:.1f} | '
                     f'{item["token_rate_median"] or 0:.1f} | {item["request_cost_usd"]:.6f} | '
                     f'{item["routing_errors"] + item["execution_errors"]} |')
    lines.extend(['', '## Per-category evidence', ''])
    for category, strategies in report['categories'].items():
        lines.append(f'### {category.replace("_", " ")}')
        lines.append('')
        lines.append('| Strategy | Success | Agreement | Zen ms | Cost USD |')
        lines.append('| --- | ---: | ---: | ---: | ---: |')
        for name, item in strategies.items():
            lines.append(f'| {name} | {item["downstream_success"]:.1%} | {item["policy_agreement"]:.1%} | '
                         f'{item["execution_latency_median_ms"]:.1f} | {item["request_cost_usd"]:.6f} |')
        lines.append('')
    lines.append('Audit the per-task decisions in [evaluation/results.json](evaluation/results.json). '
                 'Each row names its response file under [evaluation/cache/](evaluation/cache/).')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=HERE / 'results.json')
    parser.add_argument('--json', type=Path, default=HERE.parent / 'evaluation-summary.json')
    parser.add_argument('--markdown', type=Path, default=HERE.parent / 'evaluation.md')
    args = parser.parse_args(argv)
    report = build_report(json.loads(args.input.read_text()))
    args.json.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    args.markdown.write_text(markdown(report), encoding='utf-8')


if __name__ == '__main__':
    main()
