"""Modal deployment for the outcome-trained Qwen router.

    .venv/bin/modal deploy training/modal_outcome_app.py

POST {"user_task": "...", "requires_tools": false, "preference": "balanced"} to
the route endpoint. Preferences: balanced (default), cheap, fast, accurate.
The service adds the measured candidate profiles itself, scores every
candidate slug, and returns the pick, the model-derived probabilities, and
the threshold chosen on validation (artifacts/outcome-router-4m-v1/serving.json).
The router's probability for the fastest model is its easy-task score. When the
score reaches the preference's threshold, the task goes to that preference's easy
model; below it, to the fallback. Confidence is the raw probability of the pick.
"""
import json
import pathlib

import modal

APP_NAME = 'agent-route-outcome-router'
BASE_MODEL = 'Qwen/Qwen3-0.6B'
BASE_REVISION = 'c1899de289a04d12100db370d81485cdf75e47ca'
MODEL_CACHE = '/model-cache'
ADAPTER_PATH = '/router-adapter'
ARTIFACT = pathlib.Path(__file__).resolve().parents[1] / 'artifacts' / 'outcome-router-4m-v1'

image = (
    modal.Image.debian_slim(python_version='3.11')
    .uv_pip_install(
        'torch==2.6.0',
        'transformers==4.51.3',
        'peft==0.15.2',
        'accelerate==1.6.0',
        'safetensors==0.5.3',
        'fastapi[standard]==0.115.12',
    )
    .env({'HF_HOME': MODEL_CACHE, 'HF_HUB_DISABLE_TELEMETRY': '1'})
    .add_local_dir(str(ARTIFACT / 'adapter'), ADAPTER_PATH, copy=True)
    .add_local_file(str(ARTIFACT / 'serving.json'), '/root/serving.json', copy=True)
    .add_local_file('training/outcome_router.py', '/root/outcome_router.py', copy=True)
)

app = modal.App(APP_NAME)
cache = modal.Volume.from_name('agent-route-huggingface-cache', create_if_missing=True)


@app.cls(image=image, gpu='T4', volumes={MODEL_CACHE: cache}, timeout=300,
         startup_timeout=600, scaledown_window=300, max_containers=1)
class OutcomeRouter:
    @modal.enter()
    def load(self):
        import sys

        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        sys.path.insert(0, '/root')
        from outcome_router import candidate_probabilities

        self.score = candidate_probabilities
        self.serving = json.loads(pathlib.Path('/root/serving.json').read_text())
        self.tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, revision=BASE_REVISION, cache_dir=MODEL_CACHE)
        base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, revision=BASE_REVISION, cache_dir=MODEL_CACHE,
                                                    torch_dtype=torch.float16, attn_implementation='sdpa')
        self.model = PeftModel.from_pretrained(base, ADAPTER_PATH).to('cuda').eval()
        cache.commit()

    @modal.fastapi_endpoint(method='POST', requires_proxy_auth=True, docs=False)
    def route(self, request: dict):
        import time

        task = request.get('user_task')
        if not isinstance(task, str) or not task.strip():
            return {'error': 'user_task must be a nonempty string'}
        serving = self.serving
        preference = request.get('preference', 'balanced')
        if preference not in serving['preferences']:
            return {'error': f'preference must be one of {sorted(serving["preferences"])}'}
        router_input = {
            'user_task': task[:1600] + (f'\n[... {len(task) - 2000} characters omitted ...]\n' + task[-400:]
                                        if len(task) > 2000 else task[1600:]),
            'requires_tools': bool(request.get('requires_tools', False)),
            'approx_input_tokens': len(task) // 4,
            'candidates': serving['candidates'],
        }
        start = time.perf_counter()
        probs = self.score(self.model, self.tokenizer, router_input)
        routing_ms = round((time.perf_counter() - start) * 1000, 1)
        rule = serving['preferences'][preference]
        easy_score = probs[serving['easy_score']]
        pick = rule['easy'] if easy_score >= rule['threshold'] else serving['fallback']
        return {'model_slug': pick, 'confidence': round(probs[pick], 4), 'probabilities': probs,
                'preference': preference, 'easy_score': round(easy_score, 4),
                'threshold': rule['threshold'], 'routing_ms': routing_ms,
                'router': serving['router'], 'base_revision': BASE_REVISION}
