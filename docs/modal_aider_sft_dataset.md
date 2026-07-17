# Running the Aider SFT Dataset on Modal

This note records how to run the prepared Aider SFT data with the existing
Aider-native Modal launcher, without changing the SFT training scripts.

## Dataset

The local prepared dataset is:

```text
.w8-biayn/data/aider-tasks-sft/sft/train.jsonl
```

It contains 401 training rows. Its existing JSONL structure is compatible with
the Miles SFT launcher:

```json
{
  "task_id": "avl-api-rate-limits",
  "label": "avl-api-rate-limits",
  "messages": [
    {"role": "user", "content": "...Aider whole-edit task..."},
    {"role": "assistant", "content": "...complete filename and fenced file listings..."}
  ],
  "metadata": {
    "task_id": "avl-api-rate-limits",
    "subset": "train",
    "purpose": "balanced-search-tree"
  }
}
```

The current SFT command passes `--input-key messages` and
`--metadata-key metadata` to Miles. Each row has the required two-message
conversation (`user`, then `assistant`) and non-empty content. Do **not**
convert it into the PIE raw-task schema or change its Aider whole-edit answer
format.

Optionally, the messages may include explicit loss masks:

```json
"messages": [
  {"role": "user", "content": "...", "step_loss_mask": 0},
  {"role": "assistant", "content": "...", "step_loss_mask": 1}
]
```

This is not required: the repository's canonical PIE SFT JSONL also omits
these fields.

## Why the Modal Volume layout matters

`examples/modal/aider_sft_native.py` sets:

```text
MILES_CPP_DATA_DIR=/workspace/assets/aider-polyglot-cpp
```

`scripts/train_sft.sh` then requires both:

```text
${MILES_CPP_DATA_DIR}/manifest.json
${MILES_CPP_DATA_DIR}/sft/train.jsonl
```

If the manifest is absent, the script tries to rebuild the repository's PIE
dataset from task JSON. That is not suitable for this already-prepared Aider
JSONL.

Upload or copy the data into the persistent `glm47-assets` Modal Volume so its
isolated remote layout is exactly:

```text
/workspace/assets/
  aider-polyglot-cpp/
    manifest.json
    sft/
      train.jsonl
    official_tokenizer_preflight_report.json
```

Use the existing local `train.jsonl` as the remote `sft/train.jsonl`. A minimal
acceptable manifest is:

```json
{
  "kind": "aider-sft-dataset",
  "schema_version": 1,
  "profile": "aider-tasks-sft",
  "counts": {
    "train": 401
  },
  "files": {
    "sft_train": "sft/train.jsonl"
  }
}
```

The current launcher only checks that the manifest and the training JSONL
exist; Miles reads the JSONL itself.

## Run sequence

Prepare the base model and converted checkpoint if not already present, upload
the Aider dataset to the isolated path above, then run:

```bash
modal run examples/modal/aider_sft_native.py::smoke
modal run examples/modal/aider_sft_native.py::sft
```

The generic `/workspace/assets/prepared` path is deliberately not used for
Aider. The isolated Aider directory prevents collisions with PIE or other
prepared datasets. The persistent Modal Volume path is required because the
launcher does not use the local source-data path as its training input.

The isolated-path smoke test passed after publication. It read
`/workspace/assets/aider-polyglot-cpp/sft/train.jsonl`, reported 321 rows, and
verified the training checksum:

```text
257f2aef6ccb1d3f02764eeb976c0ea233f2f36fb5b2dbd26ac8b1d4f22037a5
```

The generic `/workspace/assets/prepared` location was left unchanged during
the isolated Aider publication.

## Relevant files

- `examples/modal/aider_sft_native.py`: sets the Modal Volume mount and the
  isolated Aider data path.
- `examples/sft.sh`: canonical SFT environment defaults.
- `scripts/train_sft.sh`: validates the prepared data and launches Miles.
- `src/glm47_posttraining/integrations/miles_cpp_perf.py`: shows the canonical
  SFT JSONL fields expected by this training path.

## Plan: one merged SFT run and two held-out evaluations

The intended end state is one LoRA SFT run trained on a merged Aider and Stack
dataset, evaluated against both a held-out Aider task set and the separate
Aider-Polyglot-C++ benchmark.

```text
Aider train.jsonl ─┐
                   ├─ validate + filter + split ──→ merged training JSONL
Stack train.jsonl ─┘                                    │
                                                        ▼
                                               one Modal SFT run
                                                        │
                         ┌──────────────────────────────┴─────────────────────────────┐
                         ▼                                                            ▼
            held-out Aider task evaluator                            Aider-Polyglot-C++ evaluator
         format → parse → compile → tests                        format → parse → compile → tests
                         │                                                            │
                         └──────────────────────────────┬─────────────────────────────┘
                                                        ▼
                                      base-model versus SFT-adapter comparison report
```

### 1. Freeze the original inputs

Keep these inputs immutable:

```text
.w8-biayn/data/aider-tasks-sft/sft/train.jsonl        # 401 rows
.w8-biayn/data/external/SFT-Train-Stack-2/train.jsonl # 478 rows
```

Write all derived data under a new directory such as
`.w8-biayn/data/runs/aider-stack-v1/`. Record source filenames, source
revisions, source checksums, row counts, and the creation date in a manifest.

### 2. Validate and normalize the rows

Create a preparation step that validates JSON syntax, the required
`user`-then-`assistant` message order, non-empty contents, and unique task IDs
across both sources. Preserve the existing Aider whole-edit format. Add source
provenance to each derived row, for example:

```json
"metadata": {
  "source_dataset": "aider-tasks",
  "source_task_id": "avl-api-rate-limits"
}
```

or:

```json
"metadata": {
  "source_dataset": "sft-train-stack-2",
  "source_task_id": "doubly-linked-list-task_1-pr_1"
}
```

### 3. Filter examples that exceed the context length

The current configuration uses a 4,096-token sequence length. Measure the
fully rendered conversations using the exact GLM-4.7 tokenizer and chat
template, then exclude examples that do not fit, recording their IDs and token
counts in `excluded_overlength.jsonl`.

Do not silently truncate assistant answers. The downloaded Stack dataset has
very large examples and cannot be concatenated unchanged. Increasing sequence
length is a separate runtime change requiring a new H100 validation.

### 4. Define held-out evaluation sets before merging

The Aider data must be split into `train`, `validation`, and `test` before the
SFT JSONL is created. Where possible, split by task family/category rather
than randomly, so near variants cannot appear in both train and test. Preserve
the runnable task fixtures, compiler configuration, and hidden tests for the
validation and test partitions.

Treat Stack rows as training-only unless they have independently runnable test
harnesses. Keep the Aider-Polyglot-C++ benchmark separate: no benchmark sample
may enter any training partition.

The derived layout should be similar to:

```text
aider-stack-v1/
  manifest.json
  train.jsonl
  validation.jsonl
  test.jsonl
  excluded_overlength.jsonl
  task-fixtures/
    validation/
    test/
```

### 5. Implement an Aider-specific evaluator

The existing PIE evaluator is not appropriate for this data. Add an evaluator
that, for each held-out task:

1. Renders the existing Aider prompt.
2. Generates a response with fixed decoding settings.
3. Validates and parses Aider whole-edit filename/fenced-code output.
4. Rejects missing or unexpected files.
5. Materializes generated source files in an isolated workspace.
6. Compiles and runs the task's tests.
7. Saves a structured per-task result.

Aggregate at least valid-format rate, parse/materialization rate, compilation
rate, individual-test pass rate, full-task solve rate, per-purpose/source
breakdowns, and base-model-versus-SFT deltas. Evaluate correctness by compiling
and testing generated code, not reference-answer string matching.

Run a small smoke subset first, then validation and final test splits.

### 6. Evaluate Aider-Polyglot-C++ separately

Add or connect an adapter for the benchmark's own prompt renderer, expected
response format, build settings, and hidden tests. Use its predefined split
unchanged. First confirm the benchmark's local task location and harness
format. It is an external generalization test, not a source of training rows.

### 7. Create the merged training file

Only after the split and length filter are fixed, concatenate:

```text
length-valid Aider training rows + length-valid Stack rows
  → deterministic shuffle with a fixed seed
  → aider-stack-v1/train.jsonl
```

The derived manifest must contain source counts before and after filtering,
per-source contribution, excluded IDs/reasons, split IDs, tokenizer and model
revisions, sequence length, shuffle seed, and the final JSONL checksum.

### 8. Run one Modal SFT job

Upload the derived training file, manifest, and official tokenizer report to
the isolated Aider location:

```text
/workspace/assets/aider-polyglot-cpp/
  manifest.json
  sft/
    train.jsonl
  official_tokenizer_preflight_report.json
```

Then use the standard commands:

```bash
modal run examples/modal/aider_sft_native.py::smoke
modal run examples/modal/aider_sft_native.py::sft
```

Record the Modal run ID and output LoRA adapter path.

### 9. Compare base model and SFT adapter

First evaluate the unchanged base GLM-4.7-Flash model on the held-out Aider
sets and Aider-Polyglot-C++. Then run the identical evaluators with the SFT
adapter. Keep temperature, top-p, maximum response tokens, chat-template
settings, and samples per task fixed between runs.

The final report should include training provenance and completion status, then
base/SFT metrics and deltas for both held-out Aider and Aider-Polyglot-C++,
with breakdowns and failed-sample records.
