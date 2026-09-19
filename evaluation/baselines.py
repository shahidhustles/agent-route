"""Routing policies used by the end-to-end comparison."""
import hashlib
import json
import random
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('glm-5.3-flash', 'deepseek-v4.1-flash')
STRATEGIES = ('random', 'round_robin', 'static_rule', 'heuristic', 'learned', 'oracle')
QUALITY_CATEGORIES = {'reasoning', 'coding', 'document_qa', 'long_context'}


def eligible(profile, task):
    return ((not task.get('requires_tools', False) or profile['features']['tool_calling'])
            and profile['runtime']['usable_context'] >= task.get('input_tokens', 0)
            and (task.get('available_vram_gb') is None
                 or profile['target_deployment']['total_vram_gb'] <= task['available_vram_gb']))


def _heuristic(task, profiles):
    requirements = task['requirements']
    candidates = [profile for profile in profiles if eligible(profile, task)]
    if not candidates:
        raise ValueError('No eligible candidate models')

    def score(profile):
        capabilities = profile['capabilities']
        sufficient = all(capabilities[key] >= demand - .01
                         for key, demand in requirements.items() if demand >= .8)
        quality = sum(min(capabilities[key] / max(demand, .01), 1.15) * demand
                      for key, demand in requirements.items()) / sum(requirements.values())
        fastest = max(item['runtime']['tokens_per_second'] for item in candidates)
        speed = profile['runtime']['tokens_per_second'] / fastest
        return int(sufficient) + .72 * quality + .28 * speed

    ranked = sorted(candidates, key=lambda profile: (-score(profile), profile['model_slug']))
    margin = score(ranked[0]) - score(ranked[1]) if len(ranked) > 1 else 1
    return ranked[0]['model_slug'], round(.55 + min(.4, max(0, margin)), 3)


def _oracle(candidates, outcomes):
    saved = [outcomes[model] for model in candidates if model in outcomes]
    if not saved:
        raise ValueError('Oracle requires saved outcomes for at least one eligible candidate')
    saved.sort(key=lambda item: (-int(item['success']), item['execution_latency_ms'],
                                item['request_cost_usd'], item['model_slug']))
    return saved[0]['model_slug'], 1.0


def route(strategy, task, profiles, index, seed, learned=None, outcomes=None):
    """Return one stable result shape for every policy, with safe fallback."""
    started = time.perf_counter()
    candidates = [profile['model_slug'] for profile in profiles if eligible(profile, task)]
    if not candidates:
        raise ValueError(f'No eligible candidates for {task["task_id"]}')
    invalid = False
    error = None
    try:
        if strategy == 'random':
            digest = hashlib.sha256(f'{seed}:{task["task_id"]}'.encode()).digest()
            model, confidence = random.Random(digest).choice(candidates), 1 / len(candidates)
            reason = f'seeded random selection, seed {seed}'
        elif strategy == 'round_robin':
            model, confidence = candidates[index % len(candidates)], 1 / len(candidates)
            reason = 'workload index modulo eligible candidates'
        elif strategy == 'static_rule':
            preferred = MODELS[0] if task['category'] in QUALITY_CATEGORIES else MODELS[1]
            model = preferred if preferred in candidates else candidates[0]
            confidence, reason = .7, 'fixed category rule'
        elif strategy == 'heuristic':
            model, confidence = _heuristic(task, profiles)
            reason = 'existing profile heuristic'
        elif strategy == 'learned':
            if learned is None:
                raise ValueError('Learned strategy requires a router checkpoint')
            result = learned(task, [p for p in profiles if p['model_slug'] in candidates])
            model, confidence = result['model_slug'], result['confidence']
            reason = 'Qwen3 router checkpoint'
        elif strategy == 'oracle':
            model, confidence = _oracle(candidates, outcomes or {})
            reason = 'best saved success, then latency, cost, and model ID'
        else:
            raise ValueError(f'Unknown routing strategy: {strategy}')
        invalid = model not in candidates or type(confidence) not in (int, float) or not 0 <= confidence <= 1
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exception:
        invalid, error = True, f'{type(exception).__name__}: {exception}'
    if invalid:
        model, confidence = _heuristic(task, profiles)
        reason = 'invalid policy output replaced by heuristic'
    return {
        'strategy': strategy,
        'task_id': task['task_id'],
        'category': task['category'],
        'model_slug': model,
        'confidence': confidence,
        'reason': reason,
        'routing_time_ms': round((time.perf_counter() - started) * 1000, 3),
        'invalid_output': invalid,
        'constraint_violation': model not in candidates,
        'routing_error': error,
    }
