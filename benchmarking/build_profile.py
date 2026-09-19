"""Build router-consumable profiles from a completed benchmark run.

Capability values are category pass rates computed from saved case scores.
Runtime numbers come from the run; peak_vram_gb is declared from the agreed
target deployment, not measured through the API.
"""
import argparse
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent

# Declared serving targets for the router's VRAM contract. Strong model is
# served on a larger multi-GPU pool; fast model on a small pool. Provider
# hardware is not public, so these are the agreed planning assumptions.
TARGET_DEPLOYMENTS = {
    'glm-5.3-flash': {
        'total_vram_gb': 160,
        'hardware': '2 x NVIDIA H100 80 GB',
        'precision': 'FP8',
    },
    'deepseek-v4.1-flash': {
        'total_vram_gb': 640,
        'hardware': '8 x NVIDIA H100 80 GB',
        'precision': 'FP8',
    },
}
DECLARED_CONTEXT = {
    'glm-5.3-flash': 202_752,
    'deepseek-v4.1-flash': 163_840,
}


def load_results(run_dir, model):
    model_dir = run_dir / model
    return [json.loads(path.read_text()) for path in sorted(model_dir.glob('*.json'))]


def tokens_per_second(result):
    usage = result.get('usage') or {}
    tokens = usage.get('completion_tokens')
    latency = result.get('latency_ms')
    if not tokens or not latency:
        return None
    return tokens / (latency / 1000)


def build_profile(model, results):
    by_category = {}
    for entry in results:
        by_category.setdefault(entry['category'], []).append(entry['score']['passed'])
    capabilities = {category: round(sum(passes) / len(passes), 4)
                    for category, passes in sorted(by_category.items())}
    rates = [tps for entry in results if (tps := tokens_per_second(entry['result']))]
    target = TARGET_DEPLOYMENTS[model]
    return {
        'model_slug': model,
        'capabilities': capabilities,
        'runtime': {
            'tokens_per_second': round(statistics.median(rates), 2) if rates else 0.0,
            'peak_vram_gb': target['total_vram_gb'],
            'usable_context': DECLARED_CONTEXT[model],
        },
        'features': {
            'tool_calling': capabilities.get('tool_use', 0) > 0,
            'multimodal': False,
        },
        'target_deployment': target,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', help='benchmarking/results/<run> directory')
    args = parser.parse_args(argv)
    run_dir = pathlib.Path(args.run_dir).resolve()
    meta = json.loads((run_dir / 'meta.json').read_text())
    profiles = []
    for model in meta['models']:
        results = load_results(run_dir, model)
        if not results:
            raise SystemExit(f'No saved case results for {model} in {run_dir}')
        profile = build_profile(model, results)
        profiles.append(profile)
        print(json.dumps(profile, indent=2))
    output = run_dir / 'profiles.json'
    output.write_text(json.dumps(profiles, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
