"""OpenAI-compatible client for the Command Code hosted candidate models."""
import json
import time
import urllib.error
import urllib.request

BASE_URL = 'https://api.commandcode.ai/provider/v1'
USER_AGENT = 'agent-route-benchmark/1.0'
RATE_LIMIT_BACKOFF = (5, 15, 45)

# Command Code routes provider-prefixed model IDs; benchmarks and evidence
# keep the bare internal slugs and translate only at the wire.
PROVIDER_MODEL_IDS = {
    'glm-5.3-flash': 'z-ai/glm-5.3-flash',
    'deepseek-v4.1-flash': 'deepseek/deepseek-v4.1-flash',
}


def provider_model_id(model):
    return PROVIDER_MODEL_IDS.get(model, model)


def redact_headers(headers):
    return {key: ('[REDACTED]' if 'auth' in key.lower() or 'key' in key.lower() else value)
            for key, value in headers.items()}


class CommandCodeClient:
    def __init__(self, api_key):
        self.api_key = api_key

    def chat(self, model, case, timeout=120):
        """Call chat/completions once, waiting out 429 rate limits."""
        payload = {
            'model': model,
            'messages': case['messages'],
            'temperature': 0,
            'max_tokens': case['max_tokens'],
        }
        if case.get('tools'):
            payload['tools'] = case['tools']
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
            'User-Agent': USER_AGENT,
        }
        request = urllib.request.Request(
            f'{BASE_URL}/chat/completions',
            data=json.dumps(payload).encode(),
            headers=headers,
            method='POST',
        )
        for attempt, backoff in enumerate((*RATE_LIMIT_BACKOFF, 0)):
            start = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = json.loads(response.read())
                break
            except urllib.error.HTTPError as error:
                if error.code != 429 or backoff == 0:
                    raise
                wait = error.headers.get('Retry-After')
                time.sleep(float(wait) if wait else backoff)
        latency_ms = round((time.monotonic() - start) * 1000)
        choice = raw['choices'][0]
        message = choice.get('message') or {}
        return {
            'content': message.get('content'),
            'tool_calls': message.get('tool_calls') or [],
            'finish_reason': choice.get('finish_reason'),
            'usage': raw.get('usage') or {},
            'model': raw.get('model'),
            'latency_ms': latency_ms,
        }
