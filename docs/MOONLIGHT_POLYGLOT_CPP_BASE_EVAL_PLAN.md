# Moonlight Polyglot C++ Base Eval Plan

This document is a future implementation plan for evaluating the base
`moonshotai/Moonlight-16B-A3B-Instruct` model on the C++ subset of
`Aider-AI/polyglot-benchmark` using a workflow that resembles the current
repo-owned Moonlight `eval_base.sh` lane.

Status: implemented as an optional base-eval lane. Implementation lives in `examples/slime/moonlight_polyglot_cpp/` and `src/w8_biayn/integrations/slime_polyglot_cpp.py`.

## Goal

Build a repo-style SLIME/SGLang base evaluation lane for Aider Polyglot C++
exercises:

```text
prepare_data.sh -> eval_base.sh -> base.records.jsonl + base.summary.json
```

The intended lane should:

- use Moonlight through SLIME/SGLang, like the active Moonlight PIE lane;
- evaluate only C++ exercises from `Aider-AI/polyglot-benchmark`;
- grade correctness by compiling and running Exercism C++ tests;
- write local receipts and summary artifacts under `.w8-biayn/slime/...`;
- avoid training, SFT, GRPO, PIE reward, speed reward, and Aider's edit
  harness internals.

## Non-Goals

This plan does not define an official Aider leaderboard run. Official
leaderboard-comparable Aider Polyglot results should be produced with Aider's
benchmark harness.

This plan also does not train Moonlight. It is base eval only. If later work
adds SFT or GRPO on Polyglot, create a separate design because the dataset,
reward, and task contract are different from PIE C++ performance RL.

## Why A Separate Lane Is Needed

The existing Moonlight base-eval lane is PIE-specific:

- tasks are slower-to-faster C++ optimization tasks;
- prompts contain PIE `v0` and visible tests;
- reward parses one `<reasoning>...</reasoning>` block plus one fenced C++
  program;
- grading uses `w8_biayn.cpp_perf.reward.compute_reward`;
- summary fields include correctness-gated runtime and speedup metrics.

Aider Polyglot C++ is a different task:

- exercises are Exercism-style coding tasks;
- the model edits one or more existing solution files;
- tests are project-local CMake/CTest or Make targets;
- success is pass/fail correctness, not speed improvement;
- the model should not be forced into the PIE single-file optimized-program
  format.

Therefore, keep the current PIE lane unchanged and add a new Polyglot-specific
bridge and lane.

## Proposed Files

Add a new example lane:

```text
examples/slime/moonlight_polyglot_cpp/
  README.md
  prepare_data.sh
  eval_base.sh
  moonlight_polyglot_cpp.sh
```

Add a new Python bridge:

```text
src/w8_biayn/integrations/slime_polyglot_cpp.py
```

Optional tests:

```text
tests/test_slime_polyglot_cpp.py
```

Do not modify `examples/slime/moonlight_cpp_perf/` for this work except for
small shared fixes that genuinely apply to both lanes.

## Data Source

Clone the benchmark under ignored local state:

```bash
git clone https://github.com/Aider-AI/polyglot-benchmark \
  .w8-biayn/data/polyglot-benchmark
```

Only consume C++ exercises:

```text
.w8-biayn/data/polyglot-benchmark/cpp/exercises/practice/*
```

Each exercise usually has:

```text
.meta/config.json
.docs/introduction.md
.docs/instructions.md
.docs/instructions.append.md   # optional
<solution files>
<test files>
<example files>
CMakeLists.txt
```

Use `.meta/config.json` as the source of truth for file roles. Aider's harness
uses these fields:

```json
{
  "files": {
    "solution": ["..."],
    "test": ["..."],
    "example": ["..."]
  }
}
```

The model may edit only solution files after excluding tests, examples,
`.meta/**`, `.docs/**`, and build metadata.

## Generated Data Layout

The new `prepare_data.sh` should write:

```text
.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/data/
  eval/cpp.jsonl
  manifest.json
  tasks/cpp/exercises/practice/<exercise>/
```

This lane is base-eval only, so it does not need `sft/train.jsonl` or
`grpo/train.jsonl`. If SLIME requires a `--prompt-data` file even in
`--debug-rollout-only` mode, write a tiny placeholder prompt file from the same
eval set and document that it is not trained on.

Recommended manifest shape:

```json
{
  "kind": "slime-polyglot-cpp-dataset",
  "schema_version": 1,
  "data_source": "Aider-AI/polyglot-benchmark",
  "language": "cpp",
  "profile": "moonlight-polyglot-cpp",
  "run_id": "moonlight_polyglot_cpp_...",
  "source_root": ".w8-biayn/data/polyglot-benchmark",
  "output_dir": ".w8-biayn/slime/...",
  "counts": {
    "eval": 45,
    "copied_exercises": 45
  },
  "files": {
    "eval": "eval/cpp.jsonl"
  }
}
```

Use the real count from the checked-out benchmark. Do not hard-code it.

## JSONL Row Shape

Each line in `eval/cpp.jsonl` should be one exercise:

```json
{
  "prompt": "full model prompt",
  "label": "cpp/<exercise-name>",
  "task_id": "cpp/<exercise-name>",
  "problem_id": "<exercise-name>",
  "split": "eval",
  "metadata": {
    "benchmark": "aider-polyglot",
    "language": "cpp",
    "exercise": "<exercise-name>",
    "exercise_path": "tasks/cpp/exercises/practice/<exercise-name>",
    "source_exercise_path": ".w8-biayn/data/polyglot-benchmark/cpp/exercises/practice/<exercise-name>",
    "solution_files": ["relative/path.cpp"],
    "test_files": ["relative/test.cpp"],
    "example_files": ["relative/example.cpp"]
  }
}
```

`metadata.exercise_path` should be relative to the generated data root, so the
reward hook can resolve it inside SLIME workers with `W8_BIAYN_DATA_DIR`.

## Prompt Contract

Use a whole-file contract first. It is easier to parse reliably than Aider diff
formats and works well with SLIME debug rollouts.

The prompt should include:

- exercise instructions from `.docs/introduction.md`, `.docs/instructions.md`,
  and optional `.docs/instructions.append.md`;
- the list of editable solution files;
- the current contents of each editable solution file;
- a strict output format.

Recommended output format:

````text
Return replacements for every editable solution file and no other files.

For each file, use this exact format:

```path
relative/path/from/exercise/root.cpp
```

```cpp
complete replacement file contents
```

Do not include tests, examples, build files, markdown, or explanations outside
the required blocks.
````

The parser should require each `path` block to be followed by one code block.
The language tag for code may be `cpp`, `c++`, `cc`, `hpp`, or empty. Reject
unknown paths and duplicate paths.

For a first implementation, require all editable solution files to be returned.
Later, this can be relaxed to allow omitted unchanged files, but that makes the
parser and audit trail less direct.

## Reward Hook

Implement:

```python
async def reward_func(args: Any, sample: Any, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    ...
```

Mirror the batch behavior from `w8_biayn.integrations.slime_cpp_perf.reward_func`.

For one sample:

1. Read `sample.metadata`.
2. Resolve `metadata.exercise_path` under `W8_BIAYN_DATA_DIR`.
3. Copy the exercise to a temporary working directory.
4. Parse `sample.response` into path/content replacements.
5. Verify all replacement paths are allowed solution files.
6. Overwrite solution files in the temp exercise.
7. Run the C++ test command in an isolated environment.
8. Return a reward record.

Recommended scores:

| Case | Score | Reason |
| --- | ---: | --- |
| Invalid response format | `-1.0` | `invalid_format` |
| Unknown, duplicate, or missing file | `-1.0` | `invalid_files` |
| Compile failure | `-0.5` | `compile_error` |
| Test timeout | `-0.5` | `timeout` |
| Tests run but fail | `0.0` | `tests_failed` |
| All tests pass | `1.0` | `passed` |

Return records with fields compatible with existing eval aggregation:

```json
{
  "score": 1.0,
  "reason": "passed",
  "task_id": "cpp/<exercise-name>",
  "problem_id": "<exercise-name>",
  "split": "eval",
  "all_tests_pass": true,
  "tests_passed": 1,
  "tests_total": 1,
  "compile_error": false,
  "sanitizer_error": false,
  "timeout": false,
  "invalid_format": false,
  "language": "cpp",
  "benchmark": "aider-polyglot",
  "exercise": "<exercise-name>"
}
```

If per-test counts are difficult to extract from CMake output, set
`tests_passed=1` and `tests_total=1` for all-pass, else `0/1`. Keep raw logs in
the record only when an explicit `W8_SLIME_POLYGLOT_INCLUDE_LOGS=1` environment
variable is set, to avoid huge debug dumps.

## Test Command

The reward hook should match Aider's C++ test behavior:

```bash
mkdir -p build
cd build
cmake -DEXERCISM_RUN_ALL_TESTS=1 -G "Unix Makefiles" ..
make
```

Run with a timeout. Aider uses a three-minute timeout per test command. The
Polyglot lane should default to the same value:

```text
W8_SLIME_POLYGLOT_TEST_TIMEOUT_SECONDS=180
```

Prefer Docker isolation for untrusted generated code. Reuse the existing C++
sandbox image if it has the required CMake/GTest/Exercism dependencies. If it
does not, add a new explicit sandbox image and document/build it through a
repo-owned command rather than relying on global packages.

The reward path must not run untrusted model code directly on the host.

## Aggregation

The bridge should provide:

```bash
python -m w8_biayn.integrations.slime_polyglot_cpp aggregate-debug \
  --label base \
  --debug-rollout "${RUN_ROOT}/rollout_dumps/base_eval_0.pt" \
  --out "${RUN_ROOT}/eval"
```

It can initially reuse:

```python
w8_biayn.cpp_perf.eval.aggregate_eval_records
```

because that aggregator already summarizes common fields such as score,
pass/fail, timeout, and compile error. If the output becomes misleading because
of speed-specific fields, add a small Polyglot-specific aggregator instead.

Required artifacts:

```text
.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/eval/base.records.jsonl
.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/eval/base.summary.json
```

Useful summary keys:

- total samples;
- mean score;
- pass rate;
- compile-error count/rate;
- timeout count/rate;
- invalid-format count/rate;
- tests-failed count/rate.

Do not report speedup, correct-and-faster rate, child-process CPU nanoseconds,
or PIE reference metrics for this benchmark.

## Shell Runner

`moonlight_polyglot_cpp.sh` should mirror the structure of
`examples/slime/moonlight_cpp_perf/moonlight_cpp_perf.sh`, but support only:

```text
prepare-data
base-eval
```

Defaults:

```bash
RUN_ID="${SLIME_RUN_ID:-moonlight_polyglot_cpp}"
RUN_ROOT="${SLIME_RUN_ROOT:-${REPO_ROOT}/.w8-biayn/slime/moonlight-polyglot-cpp/runs/${RUN_ID}}"
DATA_DIR="${SLIME_POLYGLOT_DATA_DIR:-${RUN_ROOT}/data}"
POLYGLOT_SOURCE="${SLIME_POLYGLOT_SOURCE:-${REPO_ROOT}/.w8-biayn/data/polyglot-benchmark}"
EVAL_LIMIT="${SLIME_POLYGLOT_EVAL_LIMIT:-4}"

HF_CHECKPOINT="${SLIME_HF_CHECKPOINT:-/root/models/Moonlight-16B-A3B-Instruct}"
HF_MODEL_ID="${SLIME_HF_MODEL_ID:-moonshotai/Moonlight-16B-A3B-Instruct}"
REF_LOAD_DIR="${SLIME_REF_LOAD_DIR:-${HF_CHECKPOINT}_torch_dist}"

EVAL_MAX_RESPONSE_LEN="${SLIME_EVAL_MAX_RESPONSE_LEN:-4096}"
EVAL_TEMPERATURE="${SLIME_EVAL_TEMPERATURE:-0}"
EVAL_TOP_P="${SLIME_EVAL_TOP_P:-1}"
```

The base eval stage should use SLIME rollout-only mode:

```bash
--debug-rollout-only
--prompt-data "${DATA_DIR}/eval/cpp.jsonl"
--input-key prompt
--label-key label
--metadata-key metadata
--apply-chat-template
--reward-key score
--num-rollout 0
--eval-interval 1
--eval-prompt-data polyglot_cpp "${DATA_DIR}/eval/cpp.jsonl"
--n-samples-per-eval-prompt "${SLIME_EVAL_N_SAMPLES_PER_PROMPT:-1}"
--eval-max-response-len "${EVAL_MAX_RESPONSE_LEN}"
--eval-temperature "${EVAL_TEMPERATURE}"
--eval-top-p "${EVAL_TOP_P}"
--custom-rm-path w8_biayn.integrations.slime_polyglot_cpp.reward_func
--save-debug-rollout-data "${RUN_ROOT}/rollout_dumps/base_{rollout_id}.pt"
```

If SLIME writes the eval dump at a different label-specific path, keep that
path in `run_receipt.txt` and use it in the aggregate step.

## Operator Flow

From the repo root on a GPU machine:

```bash
./scripts/bootstrap.sh
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime setup

git clone https://github.com/Aider-AI/polyglot-benchmark \
  .w8-biayn/data/polyglot-benchmark

bash .w8-biayn/slime/run-container.sh
```

Inside the SLIME container:

```bash
cd /workspace/browser-is-all-you-need

export SLIME_RUN_ID="moonlight_polyglot_cpp_$(date -u +%Y%m%d%H%M%S)"
export SLIME_POLYGLOT_SOURCE=/workspace/browser-is-all-you-need/.w8-biayn/data/polyglot-benchmark
export SLIME_POLYGLOT_EVAL_LIMIT=10
export SLIME_EVAL_MAX_RESPONSE_LEN=4096
export SLIME_NUM_GPUS=4
export SLIME_TENSOR_MODEL_PARALLEL_SIZE=2
export SLIME_EXPERT_MODEL_PARALLEL_SIZE=4
export SLIME_SGLANG_MEM_FRACTION=0.45

bash examples/slime/moonlight_polyglot_cpp/prepare_data.sh
bash examples/slime/moonlight_polyglot_cpp/eval_base.sh
```

For a full C++ run, unset or raise `SLIME_POLYGLOT_EVAL_LIMIT` after a smoke
passes.

## Expected Artifacts

```text
.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/
  data/
    manifest.json
    eval/cpp.jsonl
    tasks/cpp/exercises/practice/<exercise>/
  stages/base-eval/
    run.log
    run_receipt.txt
    vram_usage.csv
    vram_peak.txt
  rollout_dumps/
    base_eval_0.pt
  eval/
    base.records.jsonl
    base.summary.json
```

`run_receipt.txt` should include:

- run id;
- run root;
- source benchmark path;
- eval limit;
- model checkpoint;
- response length;
- SGLang memory settings;
- debug rollout path;
- summary path.

## Validation Before Handoff

Add tests that cover:

- C++ exercise discovery from a tiny synthetic Polyglot-like tree;
- `.meta/config.json` parsing;
- prompt construction with docs and editable files;
- JSONL row shape and manifest;
- response parser accepts valid path/code pairs;
- response parser rejects unknown files, duplicate files, missing files, and
  extra prose if the format is strict;
- reward hook returns `invalid_format` without running tests when parsing
  fails;
- aggregation writes `base.records.jsonl` and `base.summary.json`;
- shell scripts are executable and pass `bash -n`.

Then run:

```bash
uv run --extra dev pytest tests/test_slime_polyglot_cpp.py
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
```

For a live smoke on GPU, run one or two exercises first:

```bash
export SLIME_POLYGLOT_EVAL_LIMIT=2
bash examples/slime/moonlight_polyglot_cpp/prepare_data.sh
bash examples/slime/moonlight_polyglot_cpp/eval_base.sh
```

Inspect:

```text
eval/base.records.jsonl
eval/base.summary.json
stages/base-eval/run.log
stages/base-eval/run_receipt.txt
```

Do not claim a complete benchmark until every selected C++ exercise has a
record and there are no unexplained missing reward records.

## Common Failure Modes

### Model Returns Explanations Instead Of Files

Keep the prompt strict and score invalid output as `invalid_format`. Do not try
to salvage arbitrary prose in the first implementation.

### Model Edits Tests

Reject unknown or forbidden paths. The model may edit only files listed in
`metadata.solution_files`.

### CMake Dependencies Missing

Do not install dependencies by hand on the host. Update the sandbox image or
bootstrap path so a fresh machine can reproduce the eval.

### Response Truncation

Raise:

```bash
export SLIME_EVAL_MAX_RESPONSE_LEN=8192
```

If truncation remains common, record it explicitly in the reward record and
summary.

### Slow Tests Or Hangs

Keep the default timeout at 180 seconds and record `timeout=true`. If many
exercises time out because the sandbox is too slow, tune the sandbox rather
than hiding the timeout.

### Official Aider Numbers Do Not Match

That is expected. This lane uses a SLIME whole-file output protocol, not
Aider's full editing loop. Use Aider's own benchmark harness for official or
leaderboard-comparable numbers.

## Relationship To Official Aider Benchmarking

Official Aider-style benchmarking should be run separately:

```bash
./benchmark/benchmark.py <run-name> \
  --model openai/<served-model-name> \
  --edit-format whole \
  --languages cpp \
  --exercises-dir polyglot-benchmark \
  --threads 1 \
  --tries 2
```

That route measures Aider plus the model. The SLIME lane in this plan measures
the model under a repo-owned prompt/parser/reward loop. Keep the two result
families labeled separately.

## Implementation Checklist

1. Add `src/w8_biayn/integrations/slime_polyglot_cpp.py`.
2. Add parser and data-builder unit tests.
3. Add the Moonlight Polyglot shell lane.
4. Add lane README with the operator flow above.
5. Ensure generated data and benchmark clones stay under `.w8-biayn/`.
6. Run a two-exercise smoke.
7. Run the full C++ eval.
8. Save `base.records.jsonl`, `base.summary.json`, `run_receipt.txt`, and
   `run.log` as local evidence.

