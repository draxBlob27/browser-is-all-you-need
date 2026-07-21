# Aider RL Failure-Derived Rubric Curriculum

## Purpose

This is the task-authoring and acceptance contract for turning aggregate Aider
SFT/evaluation failures into executable clean-room RL rewards. It does not
authorize official Aider Polyglot material for training. Official prompts,
tests, references, model outputs, retries, and semantic copies remain excluded.

The scored unit is a behavior rubric backed by an isolated private test group:

```text
aggregate failure evidence
  -> abstract failure mode
  -> reusable behavior rubric
  -> unrelated clean-room task lineage
  -> private rubric test group
  -> targeted faulty implementation (mutant)
  -> rubric-weighted scalar reward
```

The checked-in starting catalog is
`configs/aider_rl/failure_rubric_catalog.v1.json`. It records six capability
weights, fifteen abstract failure modes, and fifteen reusable rubrics derived
from the observed category-level weaknesses. It contains no benchmark task
content.

## Clean-room separation

Failure analysis may produce only an abstract record such as “negative
normalization uses remainder instead of mathematical modulo.” The task author
then creates an unrelated specification, API, names, examples, test oracle, and
data generator. A contamination reviewer must approve the resulting lineage.

For stronger operational separation, the analyst who saw official evaluation
material should hand the author only catalog IDs and abstract behavior. The
author should not receive official task text, private tests, model responses,
or retry histories.

## Validate the catalog

```bash
python -m glm47_posttraining.aider_rl.curriculum validate-catalog \
  --catalog configs/aider_rl/failure_rubric_catalog.v1.json
```

Catalog validation fails when capability weights do not sum to one, identities
are duplicated, a rubric references an unknown failure mode, or capability
ownership is inconsistent. Admission fingerprints the complete catalog, so a
catalog change requires exact task readmission. The admitted root and bundle
each retain `curriculum.catalog.json`; verification compares every resolved
rubric definition with that snapshot rather than trusting a fingerprint alone.

## Author a task draft

Generate the current JSON schema:

```bash
python -m glm47_posttraining.aider_rl.dataset draft-schema
```

In addition to the task tree, build commands, tests, references, and evidence,
every `task.draft.json` must now declare:

- at least two catalog rubric bindings;
- an exact partition of all visible and hidden tests across those rubrics;
- independent normal and sanitizer discovery/run commands for each partition;
- at least one intentional faulty implementation under `.mutants/`;
- at least one targeted-failure and one unrelated-pass expectation per mutant;
- enough mutants that every task rubric is targeted at least once.

An abbreviated binding is:

```json
{
  "rubrics": [
    {
      "rubric_id": "validation.atomic_rejection",
      "test_groups": [
        {
          "visibility": "hidden",
          "expected_count": 4,
          "discover": ["ctest", "--test-dir", "{build}", "-N", "-L", "rubric_atomic"],
          "run": ["ctest", "--test-dir", "{build}", "--output-on-failure", "-L", "rubric_atomic"],
          "sanitizer_discover": ["ctest", "--test-dir", "{build}", "-N", "-L", "rubric_atomic"],
          "sanitizer_run": ["ctest", "--test-dir", "{build}", "--output-on-failure", "-L", "rubric_atomic"]
        }
      ]
    }
  ],
  "mutants": [
    {
      "mutant_id": "mutate-before-validate",
      "files": [
        {
          "target_path": "src/registry.cpp",
          "source_path": ".mutants/mutate-before-validate/src/registry.cpp"
        }
      ],
      "expected_fail_rubric_ids": ["validation.atomic_rejection"],
      "expected_pass_rubric_ids": ["validation.complete_rejection"]
    }
  ]
}
```

Each mutant must replace every editable file exactly once. It must compile and
reach semantic tests; a format or compile failure is not diagnostic evidence.
Admission rejects a mutant when it passes a targeted rubric or fails a rubric
declared unrelated. Mutation evidence is written privately to
`mutation.records.jsonl` in the built bundle.

## Admit and build

When clean-room roots are available:

```bash
python -m glm47_posttraining.aider_rl.dataset admit \
  --source /immutable/aider-clean-room-drafts \
  --out /immutable/aider-admitted \
  --tokenizer /exact/checkpoint-tokenizer \
  --grader-lock docker/aider_cpp_grader.lock.json \
  --curriculum configs/aider_rl/failure_rubric_catalog.v1.json

python -m glm47_posttraining.aider_rl.dataset build \
  --source /immutable/aider-admitted \
  --out /immutable/aider-rl-bundle \
  --tokenizer /exact/checkpoint-tokenizer

python -m glm47_posttraining.aider_rl.dataset ready \
  --root /immutable/aider-rl-bundle \
  --tokenizer /exact/checkpoint-tokenizer
```

`ready` reports rubric counts, mutant count, and the curriculum fingerprint in
addition to split, oracle, and token evidence. It is still a pre-GPU gate; it
does not replace the no-update rollout canary.

## Rubric-aware reward

For rubric `r`, let `q_r` be its passed normal cases divided by its admitted
case count. The semantic progress value is:

```text
semantic_progress = sum(weight_r * q_r) / sum(weight_r)
```

Rubrics, rather than individual test cases, own reward weight. Adding twenty
near-duplicate cases to one rubric therefore cannot make it dominate a task.
If any critical rubric is incomplete, semantic progress is capped at `0.5`.
The existing non-overlapping outcome tiers remain, with partial semantic reward
computed as `-0.2 + 0.4 * semantic_progress`.

Aggregate suite counts and the sum of rubric partitions must agree. Missing,
extra, or mismatched rubric evidence is an infrastructure error and is removed
from policy learning. Full reward additionally requires all normal tests, all
rubric partitions, and fresh sanitizer tests to pass.

Independent rubric execution intentionally costs more grader time than one
aggregate CTest invocation. Measure this in the no-update canary before scaling;
do not weaken diagnostic isolation merely to hide grader cost.

## No-update canary gate

Score 16 to 32 capability-balanced tasks with eight SFT-checkpoint samples per
task, then run:

```bash
python -m glm47_posttraining.aider_rl.curriculum analyze-canary \
  --catalog configs/aider_rl/failure_rubric_catalog.v1.json \
  --records /path/to/no-update.records.jsonl \
  --group-size 8
```

Every record must carry `task_id`, `rollout_id`, `capability_tags`, `rubric_ids`,
`rubric_scores`, `score`, and `infrastructure_error`. The default gate requires:

- 16 to 32 distinct tasks;
- exactly eight samples in every rollout group;
- exact rubric ID/score shape with scores in `[0, 1]`;
- no more than 50% zero-variance eligible groups;
- no more than 2% infrastructure failures; and
- each capability share within 0.20 of its catalog target.

A `not_ready` result blocks the update canary. Fix task difficulty, rubric
partitioning, task sampling, or infrastructure. Do not manufacture variance by
inflating rewards.

## Dataset readiness status

The authoring, grading, mutation-admission, reward, and canary contracts are
implemented. Actual training remains blocked until clean-room task roots are
authored, admitted, and pass the no-update gate. Once those roots exist, no
trainer or Miles infrastructure changes are required: build the bundle, run
`ready`, generate the no-update records, run the canary analyzer, and launch the
existing Aider GRPO profile only after the report says `ready`.
