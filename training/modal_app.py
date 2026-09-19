"""Modal deployment for the profile-conditioned Qwen router."""
import modal

APP_NAME = 'agent-route-qwen-router'
BASE_MODEL = 'Qwen/Qwen3-0.6B'
BASE_REVISION = 'c1899de289a04d12100db370d81485cdf75e47ca'
MODEL_CACHE = '/model-cache'
ADAPTER_PATH = '/router-adapter'

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
    .add_local_dir(
        'artifacts/qwen3-router-refined-portable/adapter',
        ADAPTER_PATH,
        copy=True,
    )
    .add_local_file('training/common.py', '/root/common.py', copy=True)
)

app = modal.App(APP_NAME)
cache = modal.Volume.from_name('agent-route-huggingface-cache', create_if_missing=True)


@app.cls(
    image=image,
    gpu='T4',
    volumes={MODEL_CACHE: cache},
    timeout=300,
    startup_timeout=600,
    scaledown_window=300,
    max_containers=1,
)
class RouterService:
    @modal.enter()
    def load(self):
        import sys
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        sys.path.insert(0, '/root')
        from common import prompt, validate_output

        self.prompt = prompt
        self.validate_output = validate_output
        self.tokenizer = AutoTokenizer.from_pretrained(
            BASE_MODEL,
            revision=BASE_REVISION,
            cache_dir=MODEL_CACHE,
        )
        base = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            revision=BASE_REVISION,
            cache_dir=MODEL_CACHE,
            torch_dtype=torch.float16,
            attn_implementation='sdpa',
        )
        self.model = PeftModel.from_pretrained(base, ADAPTER_PATH).to('cuda').eval()
        cache.commit()

    @modal.fastapi_endpoint(method='POST', requires_proxy_auth=True, docs=False)
    def route(self, request: dict):
        import torch

        rendered = self.prompt(self.tokenizer, request)
        inputs = self.tokenizer(
            rendered,
            return_tensors='pt',
            add_special_tokens=False,
        ).to('cuda')
        if inputs.input_ids.shape[1] + 96 > self.model.config.max_position_embeddings:
            raise ValueError('Routing request exceeds router context')
        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=96,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        raw = self.tokenizer.decode(
            output[0, inputs.input_ids.shape[1]:],
            skip_special_tokens=True,
        ).strip()
        result = self.validate_output(raw, request)
        return {**result, 'router': 'qwen3-0.6b-lora', 'base_revision': BASE_REVISION}
