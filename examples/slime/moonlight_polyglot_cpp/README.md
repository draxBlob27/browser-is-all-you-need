# SLIME Moonlight Polyglot C++ Base Eval

This lane evaluates the base `Moonlight-16B-A3B-Instruct` checkpoint on the C++
subset of `Aider-AI/polyglot-benchmark` using the repo's SLIME/SGLang
rollout-only shape.

It is not an official Aider leaderboard run. Official Aider-compatible numbers
should still be produced with Aider's benchmark harness. This lane measures the
model under a repo-owned whole-file prompt/parser/reward loop and writes the
same kind of local receipts as the active Moonlight PIE lane.

This README is the canonical operator runbook for the lane. Repo-wide docs
should link here instead of repeating setup knobs, response-contract details, or
artifact field descriptions.

## What It Does

`prepare_data.sh` first runs a blocking correct-answer setup check. For every
selected exercise it reads the reference files declared by
`.meta/config.json` under `files.example`, maps each `.meta/example.*` file to
the unique editable solution file with the same extension, and runs that
materialized reference through the exact Docker test path used for model
responses. Header-only references intentionally leave the inert starter
`.cpp` file in place.

The schema-v2 preflight flushes each result to `oracle.records.jsonl` before
starting the next exercise, then rereads those records to produce
`oracle.summary.json`. Each passing record binds the exact copied exercise
tree and reference-file mapping to the grader protocol, timeout, test command,
resource limits, configured image, and immutable local Docker image ID through
`oracle_input_sha256`.

Before admitting `manifest.json`, validation rereads the records, summary, and
eval JSONL and rejects any malformed, forged, duplicated, stale, missing, or
extra evidence.

After admission, the eval JSONL is:

```text
.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/data/eval/cpp.jsonl
```

Each eval row carries `metadata.category` and multi-label
`metadata.categories`. The cloned Polyglot subset only includes file-role
metadata plus blurbs, so the category map is repo-owned and deterministic. It
also carries `metadata.oracle_setup_valid: true` and
`metadata.oracle_correct_answer_source: "files.example"`; reference contents
are never included in the prompt.

`eval_base.sh` runs SLIME debug rollout-only eval against the base Moonlight
HuggingFace checkpoint and scores each response by replacing the editable
solution files in a copied Exercism exercise, then running the C++ test build:

```bash
mkdir -p build
cd build
cmake -DEXERCISM_RUN_ALL_TESTS=1 -G "Unix Makefiles" ..
make
```

The reward hook is:

```text
w8_biayn.integrations.slime_polyglot_cpp.reward_func
```

## Setup

From the repo root on the GPU host:

```bash
./scripts/bootstrap.sh
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime setup

git clone https://github.com/Aider-AI/polyglot-benchmark \
  .w8-biayn/data/polyglot-benchmark
```

Build the Polyglot C++ sandbox image. The dry-run form prints the exact
Dockerfile. The image includes Boost.DateTime for the date exercises, and the
runtime sandbox allows 2,048 processes/threads because `bank-account`'s
official concurrency test creates 1,000 threads:

```bash
uv run python -m w8_biayn.integrations.slime_polyglot_cpp sandbox-image --dry-run
uv run python -m w8_biayn.integrations.slime_polyglot_cpp sandbox-image
```

Then enter the SLIME container:

```bash
bash .w8-biayn/slime/run-container.sh
```

## Run

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
export W8_SLIME_POLYGLOT_SANDBOX_IMAGE=w8-biayn-polyglot-cpp:latest

bash examples/slime/moonlight_polyglot_cpp/prepare_data.sh
python -m w8_biayn.integrations.slime_polyglot_cpp verify-data \
  --data-root ".w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/data"
bash examples/slime/moonlight_polyglot_cpp/eval_base.sh
```

Start with a small `SLIME_POLYGLOT_EVAL_LIMIT`. Raise or unset it only after
the data manifest, rollout dump, and summary JSON are clean.

## Artifacts

The lane writes:

```text
.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/
  data/
    manifest.json
    oracle.records.jsonl
    oracle.summary.json
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

The summary reports strict pass rate, mean reward, invalid-format rate,
invalid-file rate, compile-error rate, timeout rate, tests-failed rate, and
`category_summary` for heatmaps over the multi-label exercise categories. It
also reports diagnostic `recovered_format_rate`, `recovered_pass_rate`, and
`recovered_task_pass_rate` for invalid-format responses that can be
best-effort parsed and tested. Those recovered fields do not change strict
`score`, `pass_rate`, or `all_tests_pass`; they identify format-teachable
failures for later SFT data review. The lane deliberately does not report PIE
speed metrics such as `correct_and_faster_rate`.

`base.summary.json` embeds the oracle check recomputed by `verify-data`, not
an unverified manifest flag. Require `oracle_setup_check.complete: true`,
`oracle_setup_check.all_passed: true`, schema version 2, and oracle protocol
version 1 before attributing a failed model response to the model.
`oracle.records.jsonl` preserves per-exercise task/grader fingerprints,
immutable sandbox-image identity, reference mappings, return code, and
timeout/compile/test classification. `oracle.summary.json` is recomputed from
those records and provides the aggregate proof.

## Response Contract

The model must return replacements for every editable solution file:

````text
```path
relative/path/from/exercise/root.cpp
```

```cpp
complete replacement file contents
```
````

Any prose outside these path/code pairs is invalid. The grader rejects edits to
tests, examples, docs, metadata, build files, duplicate paths, and missing
solution files. Invalid-format responses may still be best-effort parsed into
`recovered_*` diagnostics, but that path never changes strict reward or pass
fields.

## Failure Checks

- Missing benchmark checkout: clone `Aider-AI/polyglot-benchmark` under
  `.w8-biayn/data/polyglot-benchmark` or set `SLIME_POLYGLOT_SOURCE`.
- Missing sandbox image: run the `sandbox-image` command above or set
  `W8_SLIME_POLYGLOT_SANDBOX_IMAGE` to a compatible CMake-capable image.
- Oracle preflight failure: inspect `data/oracle.records.jsonl` and
  `data/oracle.summary.json`. No `manifest.json` or eval JSONL is admitted when
  any `files.example` reference fails under the current checkout, sandbox
  image, or timeout. A schema-v1 manifest, changed task file, image ID, timeout,
  mapping, record, summary, or eval task set is also rejected as stale or
  inconsistent. Re-run `prepare_data.sh` after intentional task/grader changes;
  otherwise fix the setup or corrupted artifact before evaluating the model.
- Response truncation: raise `SLIME_EVAL_MAX_RESPONSE_LEN` to `8192`.
- Many timeouts: inspect `base.records.jsonl` and the sandbox logs. The default
  test timeout is `W8_SLIME_POLYGLOT_TEST_TIMEOUT_SECONDS=180`.
- Official Aider results differ: expected. This lane is a repo-owned
  SLIME-style eval, not the Aider edit harness.
