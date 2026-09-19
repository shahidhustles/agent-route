# Mid-sem review demo

The demo is an offline playback of ticket 01 evidence. It makes no Zen request and spends no credits.

## Clean start

From a fresh checkout with Bun installed:

```sh
bun install --frozen-lockfile
bun run demo
```

The command prints both measured profiles, runs the hard filters and router locally, then displays the saved Zen response, deterministic score, token use, latency, throughput, calculated request cost, and strategy comparison.

Run one prepared case:

```sh
bun run demo -- --example fast
bun run demo -- --example quality
```

To demonstrate typed task entry, copy the exact task printed by `bun run demo -- --example fast`, then pass it with `--task`. Saved mode rejects unknown text because it has no audited execution evidence for arbitrary tasks.

## Colab playback

```python
!curl -fsSL https://bun.sh/install | bash
import os
os.environ["PATH"] = f'{os.environ["HOME"]}/.bun/bin:' + os.environ["PATH"]
!bun install --frozen-lockfile
!bun run demo
```

No API key is needed.

## Optional live mode

Do not use this during ordinary review playback. It makes one paid Zen call for the selected example. All four guards are required:

```sh
ZEN_API_KEY=... \
DEMO_ALLOW_PAID_CALLS=I_UNDERSTAND \
bun run demo -- --example fast --live --allow-paid-call --max-cost-usd 0.001
```

The demo estimates the maximum request cost before the call and stops if it exceeds the cap. Live and saved modes print the same fields.

## Learned router on Modal

Deploy the trained Qwen3-0.6B LoRA router:

```sh
scripts/setup-modal-router.sh
```

The wizard handles Modal login, deployment, endpoint protection, `.env.modal`, and a route-only smoke test.

Set the deployed endpoint URL and proxy-token values, then start the paste-in flow:

```sh
export MODAL_ROUTER_URL=https://YOUR-ENDPOINT.modal.run
export MODAL_PROXY_TOKEN_ID=wk-...
export MODAL_PROXY_TOKEN_SECRET=ws-...
bun run demo:interactive
```

The setup wizard stores these values in `.env.modal`. The package command loads that ignored file automatically, so later sessions only need `bun run demo:interactive`.

The terminal prints the exact JSON sent to the learned router and the exact Zen request it would make. It does not call Zen unless you also pass `--execute-zen --allow-paid-call --max-cost-usd AMOUNT` and set both `ZEN_API_KEY` and `DEMO_ALLOW_PAID_CALLS=I_UNDERSTAND`.

## Review sequence

1. Point out GLM's document-QA score and DeepSeek's throughput.
2. Run `bun run demo -- --example fast` and show the DeepSeek selection.
3. Run `bun run demo -- --example quality` and show the VRAM filter plus GLM selection.
4. Finish on the saved strategy table. Say plainly that the learned comparison is pending because the merged checkpoint is absent.

## Fallback recording

Record `bun run demo` in a terminal after the final checkout passes. Keep the recording under three minutes. Store the video outside Git, then add its review-day location here. Until a person records it, the saved playback itself is the fallback.
