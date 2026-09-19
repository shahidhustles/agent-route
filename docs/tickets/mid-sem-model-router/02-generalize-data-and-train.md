# 02 - Generalize data and train the router

## Goal

Produce family-isolated, domain-neutral routing splits from the benchmark profiles and train a reproducible Qwen3-0.6B router checkpoint in Colab.

## Files

Create:
- `training/task_families.json`

Modify:
- `training/generate_data.py`
- `training/common.py`
- `training/train.py`
- `training/evaluate.py`
- `training/run_pipeline.py`
- `training/test_data.py`
- `training/test_training.py`
- `training/colab.ipynb`
- `training/README.md`

## Implementation notes

- Replace the industrial templates with independently phrased tasks covering coding, education, safe finance, documents, research, office work, everyday requests, reasoning, tools, long context, spreadsheets, and simple editing.
- Give every source task a family ID and assign whole families to train, validation, or held-out test.
- Generate labels with the existing deterministic policy and the profiles from ticket 01.
- Record the seed, generator settings, profile version, split counts, category and label distributions, and SHA-256 hashes in the data manifest.
- Fine-tune Qwen3-0.6B with LoRA. Choose the final checkpoint using training and validation evidence only.
- Use the Colab MCP for all GPU work. It must launch or reconnect to the Colab run, monitor training, inspect logs and validation output, and retrieve the checkpoint, configuration, logs, and manifests. Keep the Zen key and other credentials in Colab secrets.

## Blocked by

- 01 - Benchmark Zen models and build profiles

## Done when

- Regeneration produces the same split hashes from the recorded seed and settings.
- No task family crosses split boundaries and no MRPL task appears in any split.
- The downloaded checkpoint is linked to its base-model revision, profile version, data hashes, hyperparameters, and validation result.
- Validation policy agreement is at least 80%, invalid router output is below 1%, and hard-constraint violations are zero.
- The held-out test has not been opened or evaluated.
