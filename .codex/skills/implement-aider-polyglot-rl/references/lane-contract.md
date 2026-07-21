# Aider Polyglot RL Lane Contract

## Contents

1. Change boundary
2. Current PIE coupling
3. Required Aider surfaces
4. Data and task contract
5. Grader and reward contract
6. Miles and launcher contract
7. Evaluation and tests

## 1. Change Boundary

Treat this work as a lane migration, not an infrastructure rewrite.

Reuse without behavioral changes:

- `src/glm47_posttraining/integrations/miles_glm47_bridge.py`
- `src/glm47_posttraining/integrations/miles_train_with_glm47_bridge.py`
- `src/glm47_posttraining/integrations/miles_convert_with_glm47_bridge.py`
- checkpoint conversion and adapter preparation scripts
- existing LoRA, SGLang, Megatron, topology, batching, and rollout-dump logic

Keep the PIE lane and established infrastructure methods intact. Add
Aider-specific modules, launch configuration, and metrics alongside them. Do
not factor, rename, or generalize shared helpers during this lane migration.
If the current infrastructure exposes no usable boundary, report that exact
blocker and request explicit scope expansion before editing it.

## 2. Current PIE Coupling

| Existing surface | PIE assumption | Aider action |
|---|---|---|
| `cpp_perf/schema.py` | One C++20 program, inline tests, runtime reference | Add a separate multi-file `AiderTask` schema. |
| `cpp_perf/dataset.py` | Visible tests plus reasoning and one C++ block | Add an SFT-compatible whole-file renderer with no tests. |
| `cpp_perf/reward.py` | Single-block parser, recovery shaping, speed reward | Add strict named-file parsing and correctness-only tiers. |
| `cpp_perf/sandbox.py` | `candidate.cpp`, stdin/stdout fixtures, online reference timing | Add fresh repository-copy build/test/sanitizer grading. |
| `cpp_perf/eval.py` | Correct-and-faster and runtime gates | Add Aider pass, repair, build/test, and compliance metrics. |
| `integrations/miles_cpp_perf.py` | Loads `CppTask` and invokes PIE grading | Reuse only its Miles hook and concurrency shape. |
| `scripts/train_grpo.sh` | PIE builder, reward path, eval name, image, variables | Keep it intact and add a separate Aider launcher. |
| `examples/grpo.sh` | Canonical PIE defaults and local reward backend | Add a separate Aider wrapper; require isolated grading. |
| `wandb_posttraining.py` | PIE speedup tables and promotion fields | Add Aider-specific tables and gates without fake speed fields. |
| `scripts/evaluate.py` | PIE generation and scoring | Keep it; add an Aider evaluator. |

## 3. Required Aider Surfaces

Use this target layout unless the repository already contains an equivalent
surface:

```text
src/glm47_posttraining/aider_rl/
  __init__.py
  schema.py
  admission.py
  curriculum.py
  dataset.py
  prompt.py
  parser.py
  sandbox.py
  reward.py
  eval.py

src/glm47_posttraining/integrations/
  miles_aider_rl.py

docker/
  aider_cpp_grader.Dockerfile

scripts/
  train_aider_grpo.sh
  evaluate_aider.py

examples/
  aider_grpo.sh
```

Use repository-owned data commands:

```text
python -m glm47_posttraining.aider_rl.dataset draft-schema
python -m glm47_posttraining.aider_rl.dataset admit ...
python -m glm47_posttraining.aider_rl.dataset build ...
python -m glm47_posttraining.aider_rl.dataset verify ...
python -m glm47_posttraining.aider_rl.dataset oracle ...
python -m glm47_posttraining.aider_rl.dataset summarize ...
python -m glm47_posttraining.aider_rl.dataset ready ...
```

All bundle commands that validate tasks must receive the exact checkpoint
tokenizer and must re-tokenize prompt/reference pairs. The `ready` command is
the complete pre-GPU gate: immutable bundle verification plus Docker oracle
preflight and sequence-budget evidence.

## 4. Data and Task Contract

An admitted task must bind:

- schema, task, family, semantic-lineage, capability, and split identity;
- ordered editable file paths and exact starter bytes or hashes;
- introduction and instructions;
- private visible/hidden test identities and positive counts;
- private reference mapping;
- repository-owned C++17 configure, build, and test commands;
- normal and sanitizer oracle receipts;
- task-tree, prompt, parser, reward, grader-image, compiler, tokenizer, and
  split fingerprints;
- provenance and contamination receipts;
- prompt, answer, loss-mask, and total token counts/hashes; and
- a versioned failure-rubric catalog fingerprint, an exact visible/hidden test
  partition, and immutable targeted-mutant specifications.

Produce this bundle shape:

```text
manifest.json
curriculum.catalog.json
task-manifest.jsonl
admission.records.jsonl
oracle.records.jsonl
mutation.records.jsonl
tasks/
grpo/train.jsonl
eval/anchor.jsonl
eval/validation.jsonl
eval/internal-test.jsonl
```

Public prompt rows may contain safe identity metadata and an immutable task
pointer. Keep tests, references, CMake files, provenance, and receipts private.
Split by complete family and semantic lineage, not by row.

The documented Aider SFT `manifest.json` plus `sft/train.jsonl` is not an RL
task bundle. Require original clean-room task roots. Keep the documented
401-row SFT lineage distinct from historical 715-row and 709-row projections.

## 5. Grader and Reward Contract

For each candidate:

1. Resolve an immutable allowlisted task.
2. Create a unique fresh task and build root.
3. Parse exactly one complete block for every allowed file.
4. Reject unsafe or non-allowlisted file state.
5. Apply replacements only to the trusted scratch copy.
6. Configure and compile with the locked toolchain.
7. Discover positive visible and hidden test counts.
8. Run normal visible and hidden tests separately under limits.
9. On full normal success, create a second fresh sanitizer build.
10. Rediscover matching positive tests and run ASan/UBSan tests.
11. Return a versioned private receipt and delete mutable state.

Require Docker isolation with no network, read-only root, unprivileged user,
dropped capabilities, no new privileges, bounded CPU/memory/PIDs/files/time,
and only a scratch mount writable. Do not offer the PIE local backend as an
Aider evidence mode.

Use non-overlapping starting reward tiers. For partial semantic progress, score
each behavior rubric first and compute
`p = sum(weight_r * q_r) / sum(weight_r)`. Do not weight raw test cases across
rubrics. Cap `p` at `0.5` while any critical rubric is incomplete. Aggregate
suite results must equal their admitted rubric partitions or the sample is an
infrastructure failure.

| Outcome | Reward |
|---|---:|
| Invalid or unsafe whole edit | `-1.0` |
| Configure, compile, or candidate timeout failure | `-0.5` |
| Some normal tests fail | `-0.2 + 0.4 * p` |
| All normal tests pass but sanitizer fails | `0.3` |
| Full success after bounded repair | `0.8` |
| Full success on first edit | `1.0` |

Calibrate weights with controlled references, targeted mutants, and a no-update
rollout before training. Never let partial or repaired success equal first-edit
full correctness. Remove infrastructure failures and retry; do not assign them
policy reward.

## 6. Miles and Launcher Contract

Keep the Miles sample/list reward callable shape, metadata transport, bounded
batch concurrency, and `score` reward key. Change only the task loader, parser,
grader, record fields, and failure classification.

The Aider launcher must select:

```text
--prompt-data <aider-root>/grpo/train.jsonl
--input-key prompt
--label-key label
--metadata-key metadata
--custom-rm-path glm47_posttraining.integrations.miles_aider_rl.reward_func
--reward-key score
--eval-prompt-data aider_cpp <aider-eval-jsonl>
```

Use Aider-owned configuration such as `MILES_AIDER_DATA_DIR`,
`MILES_AIDER_TASKS_DIR`, `GLM47_AIDER_GRADER_IMAGE`, and
`GLM47_AIDER_REWARD_WORKERS`. Do not change meanings of existing PIE variables.
Derive response limits from admission token evidence rather than PIE defaults.

Start with group size eight and one-shot scoring. A repair bridge must preserve
same-trajectory state, bounded redacted feedback, one trainer-reaching sample,
`metadata.round_number`, and detached or masked first-turn credit.

## 7. Evaluation and Tests

Report at least:

- strict one-shot pass rate and empirical pass@8;
- cumulative second-edit correctness when repair exists;
- repair conversion conditional on first-edit failure;
- configure, compile, visible, hidden, and sanitizer pass rates;
- strict format and allowed-file compliance;
- capability/family results and anchor retention;
- reward distribution and zero-variance group fraction;
- removed infrastructure failures by reason; and
- tokens, context exhaustion, grader latency, and throughput.

Test:

- schema validation and immutable identity;
- failure-catalog consistency, exact rubric partitioning, and diagnostic mutant
  admission;
- prompt/private boundary;
- named-file parser and all unsafe path cases;
- fresh normal and sanitizer builds with positive test discovery;
- every reward boundary and infrastructure classification;
- Miles single and batch sample shapes;
- Aider launcher arguments, variables, preflight, and eval name;
- Aider W&B records without PIE runtime fields; and
- unchanged PIE unit, integration, and script-profile behavior.

Run a 16-to-32-task, capability-balanced, eight-sample no-update rollout canary
before a training canary. Scale only when rubric record shape is exact, reward
tiers are correct, infrastructure failures are negligible, prompts leak no
private data, capability shares match the catalog, and prompt groups show useful
reward variance.
