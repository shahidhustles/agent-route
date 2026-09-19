# EDI Mid-Sem Review Checklist

## Project framing

The mid-sem deliverable is a **model-level routing prototype** for the larger EDI project, **Agent Route: Adaptive Agent Routing System**. It demonstrates that tasks can be routed to suitable language models using measured capability profiles.

The end-sem project will extend this foundation from model routing to routing between heterogeneous agents using historical outcomes and adaptive learning.

## Critical path

**Benchmark models → generate real profiles → generalize the dataset → retrain the router → compare baselines → demonstrate routing and task execution**

## 1. Choose the candidate models

- [x] Select two candidates available through Zen.
- [x] Assign every model a stable `model_slug`.
- [ ] Record the exact model and checkpoint version.
- [ ] Record the quantization format and level.
- [ ] Record the inference engine and serving configuration.
- [ ] Record the benchmark hardware and software environment.

### Completion criteria

- [ ] A versioned candidate-model manifest exists.
- [ ] Every candidate can be loaded and queried successfully.
- [ ] The configuration is sufficient for someone else to reproduce a run.

## 2. Build the model benchmarking engine

- [x] Define a common benchmark-task schema.
- [x] Define a common model-adapter interface.
- [ ] Add benchmark tasks for reasoning.
- [ ] Add benchmark tasks for coding.
- [ ] Add benchmark tasks for tool use.
- [ ] Add benchmark tasks for document question answering.
- [ ] Add benchmark tasks for structured output.
- [ ] Add benchmark tasks for instruction following.
- [ ] Add benchmark tasks for long-context handling.
- [x] Run exactly the same tasks and scoring rules on every candidate model.
- [x] Measure correctness or task success.
- [ ] Measure time to first token and total latency.
- [x] Measure output tokens per second.
- [ ] Measure peak VRAM usage.
- [ ] Measure usable context length.
- [ ] Record tool-calling and multimodal support.
- [x] Save raw requests, responses, timings, scores, errors, and run metadata.

### Completion criteria

- [ ] One command can run the benchmark suite for a selected model.
- [ ] Interrupted runs can be inspected and safely resumed or rerun.
- [ ] Results are machine-readable and auditable from raw outputs.
- [ ] Repeated runs do not silently overwrite earlier evidence.

## 3. Generate measured model profiles

- [ ] Define how each raw benchmark metric maps to a `ModelProfile` field.
- [ ] Define normalization rules for capability scores.
- [ ] Generate profiles automatically from benchmark results.
- [ ] Include provenance linking every profile to its benchmark run.
- [ ] Validate generated profiles with the existing schema.
- [ ] Replace placeholders in `training-profiles.json`.
- [ ] Replace placeholders in `profiles.ts`.
- [ ] Replace placeholders in the runtime registry.
- [ ] Keep serving details separate from measured capability scores where practical.

### Completion criteria

- [ ] No claimed capability value is an unexplained placeholder.
- [ ] Profiles can be regenerated from saved benchmark results.
- [ ] Training and runtime use the same versioned profile set.

## 4. Generalize the routing dataset

- [ ] Keep MRPL workflows as one explicit industrial category.
- [ ] Add domain-neutral software and coding tasks.
- [ ] Add education tasks.
- [ ] Add finance tasks that do not require unsafe or personalized advice.
- [ ] Add general document tasks.
- [ ] Add research and information-synthesis tasks.
- [ ] Add administration and office-work tasks.
- [ ] Add everyday user requests.
- [ ] Add simple tasks where a smaller model should be preferred.
- [ ] Add reasoning, tool-use, long-context, and spreadsheet-oriented tasks.
- [ ] Write independently phrased prompts instead of primarily swapping entity names in templates.
- [ ] Assign source or template-family identifiers to examples.
- [ ] Prevent related templates and close variants from crossing data splits.
- [ ] Review category and difficulty balance.
- [ ] Remove duplicates and near-duplicates.

### Completion criteria

- [ ] MRPL examples are only one part of a broader corpus.
- [ ] Split construction prevents template-family leakage.
- [ ] Dataset statistics document domains, categories, difficulty, and label distribution.

## 5. Regenerate router training data

- [ ] Generate new training, validation, and held-out test files using measured profiles.
- [ ] Record the profile version used for generation.
- [ ] Record generator settings and random seeds.
- [ ] Compute and save hashes for all generated splits.
- [ ] Review category balance across splits.
- [ ] Review model-selection label balance across splits.
- [ ] Manually inspect a representative sample of tasks and labels.
- [ ] Correct generator or policy errors before training.

### Completion criteria

- [ ] The dataset is reproducible from committed code and recorded settings.
- [ ] Sampled labels are defensible using the measured profiles.
- [ ] The held-out test split is frozen and not used during development.

## 6. Retrain the learned router

- [ ] Fine-tune Qwen3-0.6B on the updated training split.
- [ ] Record the base-model version.
- [ ] Record hyperparameters and training configuration.
- [ ] Record dataset and profile hashes.
- [ ] Track training and validation loss.
- [ ] Save versioned checkpoints and logs.
- [ ] Iterate using training and validation results only.
- [ ] Do not inspect or tune against the held-out test results.

### Completion criteria

- [ ] A reproducible final checkpoint is selected from validation evidence.
- [ ] The exact checkpoint, dataset, profiles, and configuration are linked.

## 7. Evaluate router quality

- [ ] Measure overall routing accuracy or policy agreement.
- [ ] Measure per-category routing accuracy.
- [ ] Produce a confusion matrix by selected and expected model.
- [ ] Count invalid JSON responses.
- [ ] Count invalid or unavailable model slugs.
- [ ] Count tool-use constraint violations.
- [ ] Count context-window constraint violations.
- [ ] Test candidate-order sensitivity.
- [ ] Analyze failures for simple tasks.
- [ ] Analyze failures for reasoning tasks.
- [ ] Analyze failures for long-context tasks.
- [ ] Record routing latency separately from model execution latency.

### Completion criteria

- [ ] The final checkpoint passes the agreed validation thresholds.
- [ ] Failure cases and limitations are documented, not only aggregate accuracy.

## 8. Implement routing baselines

- [x] Random selection.
- [x] Round-robin selection.
- [x] Static rule-based selection.
- [x] Existing heuristic router.
- [x] Learned router interface. Full downstream run pending.
- [x] Oracle selection based on known benchmark outcomes.
- [x] Expose every strategy through the same routing interface.
- [x] Make random behavior reproducible with a recorded seed.

### Completion criteria

- [ ] Every strategy receives the same candidate set and workload.
- [ ] Every strategy produces results in the same output format.

## 9. Run end-to-end routing evaluation

- [x] Create a fixed evaluation workload.
- [ ] Route each task using every routing strategy.
- [ ] Execute the task on the selected primary model.
- [ ] Score downstream task success.
- [ ] Measure total latency and separate routing from execution time.
- [ ] Measure throughput and resource usage.
- [ ] Record inference cost or a clearly labelled local-compute proxy.
- [ ] Report router policy agreement separately from downstream task success.
- [ ] Compare aggregate and per-category results.

### Completion criteria

- [ ] Results show whether learned routing improves outcomes over baselines.
- [ ] All strategies are compared under the same conditions.
- [ ] Raw execution evidence is retained for auditability.

## 10. Run the held-out test once

- [ ] Freeze the dataset.
- [ ] Freeze measured profiles.
- [ ] Freeze the router checkpoint.
- [ ] Freeze baseline implementations and evaluation rules.
- [ ] Record all artifact hashes before the run.
- [ ] Run the untouched held-out test split once.
- [ ] Save aggregate and per-category results.
- [ ] Do not tune the router after viewing the held-out result.

### Completion criteria

- [ ] The final result is reproducible and clearly separated from validation results.
- [ ] Any later changes are reported as a new experimental version, not part of the frozen run.

## 11. Build the mid-sem demonstration

The live demonstration should show this sequence:

- [x] A user enters one of the prepared audited tasks.
- [x] The router receives the task and measured candidate profiles.
- [x] Hard constraints remove incompatible models.
- [x] The learned Modal router selects a model in interactive mode. Saved playback uses the profile heuristic.
- [x] The terminal shows the selected model, confidence, evidence, and routing time.
- [x] A saved Zen execution supplies the model response.
- [x] The output and execution metrics are displayed.
- [x] The terminal report compares the completed strategies and marks learned pending.
- [x] A saved run is available if live inference fails.

### Completion criteria

- [ ] The demonstration works from a clean start using documented commands.
- [ ] The complete flow fits within the review time limit.
- [ ] The demo does not depend on unmeasured or placeholder claims.

## 12. Prepare the review material

- [ ] State the Agent Route problem and motivation.
- [ ] Explain why model-level routing is the mid-sem phase.
- [ ] Present the benchmarking architecture.
- [ ] Present measured model profiles and their provenance.
- [ ] Explain dataset composition and MRPL generalization.
- [ ] Explain the router model and training method.
- [ ] Compare learned routing with the baselines.
- [ ] Present validation and held-out results separately.
- [ ] Separate routing quality from downstream model task success.
- [ ] State limitations honestly.
- [ ] Present the end-sem path to heterogeneous agent routing using historical outcomes and adaptive learning.
- [ ] Prepare architecture, data-flow, results, and timeline diagrams.
- [ ] Prepare likely viva questions and concise answers.

### Completion criteria

- [ ] Slides, report, demonstration, and repository use consistent terminology and numbers.
- [ ] Every reported metric can be traced to a saved experiment.
- [ ] The scope difference between mid-sem and end-sem is explicit.

## Claims to avoid

- [ ] Do not present the existing 82.875% validation agreement as real-world task success.
- [ ] Do not describe placeholder capability values as benchmark results.
- [ ] Do not claim general-purpose routing from an MRPL-heavy dataset.
- [ ] Do not combine router latency and primary-model execution latency into one unexplained number.
- [ ] Do not use the held-out test split for checkpoint selection or tuning.
- [ ] Do not present the full adaptive heterogeneous-agent router as already completed.

## Progress summary

- [ ] Candidate models finalized
- [ ] Benchmarking engine complete
- [ ] Measured profiles generated
- [ ] Dataset generalized
- [ ] Training data regenerated and frozen
- [ ] Router retrained
- [ ] Validation complete
- [ ] Baselines complete
- [ ] End-to-end evaluation complete
- [ ] Held-out test complete
- [ ] Mid-sem demo complete
- [ ] Review material complete
