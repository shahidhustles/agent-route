"""Generate reproducible family-isolated router data from measured profiles."""
import argparse
import copy
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from common import eligible, label, validate_request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = 26117
SPLIT_SIZES = {'train': 6400, 'validation': 800, 'test': 800}
MEASURED_MODELS = {'glm-5.3-flash', 'deepseek-v4.1-flash'}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(profile_path, family_path):
    profiles = json.loads(profile_path.read_text(encoding='utf-8'))
    profiles = [profile for profile in profiles if profile['model_slug'] in MEASURED_MODELS]
    if {profile['model_slug'] for profile in profiles} != MEASURED_MODELS:
        raise ValueError('Training profiles must contain both measured Command Code candidates')
    source = json.loads(family_path.read_text(encoding='utf-8'))
    families = []
    for category in source['categories']:
        for task in category['tasks']:
            families.append({**task, 'category': category['id'],
                'requirements': category['requirements'],
                'requires_tools': category.get('requires_tools', False),
                'input_tokens': category.get('input_tokens', 1024)})
    if len(families) != 120 or len({item['family_id'] for item in families}) != 120:
        raise ValueError('task_families.json must contain 120 unique families')
    if any('mrpl' in item['text'].lower() for item in families):
        raise ValueError('MRPL tasks are forbidden')
    return profiles, source, families


def varied_profiles(rng, baseline):
    profiles = copy.deepcopy(baseline)
    canonical = {profile['model_slug']: profile['model_slug'] for profile in profiles}
    synthetic = rng.random() < .7
    if synthetic:
        for profile in profiles:
            profile['capabilities'] = {
                key: round(max(.05, min(1, value + rng.uniform(-.12, .12))), 2)
                for key, value in profile['capabilities'].items()
            }
            profile['runtime']['tokens_per_second'] = round(
                profile['runtime']['tokens_per_second'] * rng.uniform(.75, 1.25), 2)
    anonymous = rng.random() < .5
    if anonymous:
        aliases = rng.sample(range(100, 1000), len(profiles))
        for profile, alias in zip(profiles, aliases):
            original = profile['model_slug']
            profile['model_slug'] = f'model_{alias}'
            canonical[profile['model_slug']] = original
    rng.shuffle(profiles)
    return profiles, synthetic, anonymous, canonical


def make_row(rng, family, baseline):
    profiles, synthetic, anonymous, canonical = varied_profiles(rng, baseline)
    request = {
        'user_task': family['text'],
        'candidate_models': [profile['model_slug'] for profile in profiles],
        'profiles': profiles,
        'requires_tools': family['requires_tools'],
        'input_tokens': family['input_tokens'],
    }
    if family['category'] in {'long_context', 'documents', 'research'}:
        request['input_tokens'] = rng.choice([4096, 32768, family['input_tokens']])
    if rng.random() < .2:
        request['available_vram_gb'] = rng.choice([160, 640])
    if not any(eligible(profile, request) for profile in profiles):
        request.pop('available_vram_gb', None)
    validate_request(request)
    output = label(request, family['requirements'])
    return {
        'input': request,
        'output': output,
        'metadata': {
            'family_id': family['family_id'],
            'category': family['category'],
            'anonymous': anonymous,
            'synthetic_profiles': synthetic,
            'canonical_label': canonical[output['model_slug']],
            'requirements': family['requirements'],
        },
    }


def generate(seed=DEFAULT_SEED, profile_version=None):
    profile_path = ROOT / 'training-profiles.json'
    family_path = ROOT / 'training/task_families.json'
    baseline, family_source, families = load_inputs(profile_path, family_path)
    profile_version = profile_version or family_source['profile_version']
    rng = random.Random(seed)
    destination = ROOT / 'data'
    destination.mkdir(exist_ok=True)
    manifest = {
        'generator_version': 2,
        'seed': seed,
        'settings': {
            'split_sizes': SPLIT_SIZES,
            'measured_models': sorted(MEASURED_MODELS),
            'profile_perturbation_probability': .7,
            'profile_capability_delta': .12,
            'anonymous_probability': .5,
        },
        'profile_version': profile_version,
        'profile_source': {'path': 'training-profiles.json', 'sha256': sha256(profile_path)},
        'family_source': {'path': 'training/task_families.json', 'sha256': sha256(family_path)},
        'provenance': 'Author-written domain-neutral task families with deterministic policy labels.',
        'splits': {},
    }
    for split, size in SPLIT_SIZES.items():
        split_families = [family for family in families if family['split'] == split]
        if not split_families:
            raise ValueError(f'No families assigned to {split}')
        rows = [make_row(rng, split_families[index % len(split_families)], baseline)
                for index in range(size)]
        rng.shuffle(rows)
        content = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
        output = destination / f'{split}.jsonl'
        output.write_text(content, encoding='utf-8', newline='\n')
        manifest['splits'][split] = {
            'count': len(rows),
            'sha256': hashlib.sha256(content.encode()).hexdigest(),
            'family_count': len(split_families),
            'families': sorted(family['family_id'] for family in split_families),
            'categories': dict(sorted(Counter(row['metadata']['category'] for row in rows).items())),
            'labels': dict(sorted(Counter(row['metadata']['canonical_label'] for row in rows).items())),
            'anonymous': sum(row['metadata']['anonymous'] for row in rows),
            'synthetic_profiles': sum(row['metadata']['synthetic_profiles'] for row in rows),
        }
    manifest_path = destination / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--profile-version')
    arguments = parser.parse_args()
    generate(arguments.seed, arguments.profile_version)
