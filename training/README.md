# Qwen3 router fine-tuning

This workflow trains Qwen3-0.6B with LoRA to choose between the measured
glm-5.3-flash and deepseek-v4.1-flash profiles. It returns only model_slug and
confidence.

## Data contract

task_families.json contains 120 independently written tasks across coding,
education, safe finance, documents, research, office work, everyday requests,
reasoning, tools, long context, spreadsheets, and simple editing. The file
assigns 80 families to training, 20 to validation, and 20 to the sealed test
split. A family never crosses a split.

The generator expands those families to 6,400 training, 800 validation, and
800 test examples. It varies candidate order, anonymous model aliases, hardware
constraints, and bounded copies of the measured profiles. It does not call a
hosted model. Labels come from the deterministic policy in common.py.

Run this from the repository root:

    python training/generate_data.py
    python -m unittest discover -s training -p test_data.py

data/manifest.json records the seed, generator settings, profile version,
source hashes, split hashes, family counts, category distribution, and
canonical label distribution. Generated data stays out of Git.

## Colab training

Use the Colab MCP for GPU work. Keep credentials in Colab secrets. Training
does not need the Command Code API key, but later benchmark or execution work may.

Start with a smoke run:

    python training/train.py --max-steps 3 --limit 32 --accumulation 1 --output artifacts/smoke

Then run the full validation-gated pipeline:

    python -u training/run_pipeline.py

The full run uses rank 8 LoRA on the attention projections, batch size 8 with
two-step accumulation, fp16, gradient checkpointing, and the pinned
Qwen3-0.6B revision. Transformers saves once per epoch and restores the
checkpoint with the lowest validation loss before export. The pipeline
evaluates only the validation split.

Its output under artifacts/qwen3-router/ includes:

- the LoRA adapter and merged checkpoint;
- training and validation logs;
- training-report.json, including the base revision, hyperparameters, data
  hashes, selected checkpoint, and validation loss;
- validation-report.json;
- training-manifest.json, which links the data, profile, training, and
  validation evidence.

The validation gate requires at least 80% policy agreement, less than 1%
invalid output, and zero hard-constraint violations.

If validation improves but narrowly misses the agreement gate, refine from the
selected LoRA adapter without opening the test split:

    python -u training/run_pipeline.py \
      --epochs 1 \
      --adapter artifacts/qwen3-router/checkpoint-800 \
      --output artifacts/qwen3-router-refined

## Held-out test

Do not run this command while tuning:

    python training/evaluate.py \
      --model artifacts/qwen3-router/merged \
      --split test \
      --allow-held-out-test \
      --report artifacts/qwen3-router/test-report.json

The explicit flag is deliberate. Freeze the checkpoint, data hashes, routing
policies, and scoring rules before opening the test split. Validation is the
default when --split is omitted.

Evaluation reports policy agreement, output validity, invalid slugs, hard
constraint violations, candidate-order agreement, per-category results, and
latency. Policy agreement measures imitation of the deterministic teacher. It
does not measure whether a Command Code model completes the selected task.

## Local interface

    python training/infer.py --model artifacts/qwen3-router/merged

Send one JSON request per line with user_task, candidate_models, profiles, and
any known requires_tools, input_tokens, or available_vram_gb values. The
wrapper rejects malformed output and hard-constraint violations.

## Pinned libraries

- Transformers 4.51.3
- PEFT 0.15.2
- Accelerate 1.6.0
- safetensors 0.5.3
