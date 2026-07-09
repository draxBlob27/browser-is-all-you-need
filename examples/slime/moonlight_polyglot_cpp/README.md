# SLIME Moonlight Polyglot C++ Base Eval

This lane evaluates the base `Moonlight-16B-A3B-Instruct` checkpoint on the C++
subset of `Aider-AI/polyglot-benchmark` using the repo's SLIME/SGLang
rollout-only shape.

It is not an official Aider leaderboard run. Official Aider-compatible numbers
should still be produced with Aider's benchmark harness. This lane measures the
model under a repo-owned whole-file prompt/parser/reward loop and writes the
same kind of local receipts as the active Moonlight PIE lane.

## What It Does

`prepare_data.sh` converts Polyglot C++ exercises into one eval JSONL file:

```text
.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/data/eval/cpp.jsonl
```

Each eval row carries `metadata.category` and multi-label
`metadata.categories`. The cloned Polyglot subset only includes file-role
metadata plus blurbs, so the category map is repo-owned and deterministic.

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
Dockerfile:

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

The summary reports pass rate, mean reward, invalid-format rate, invalid-file
rate, compile-error rate, timeout rate, tests-failed rate, and
`category_summary` for heatmaps over the multi-label exercise categories. It
deliberately does not report PIE speed metrics such as
`correct_and_faster_rate`.

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
solution files.

## Failure Checks

- Missing benchmark checkout: clone `Aider-AI/polyglot-benchmark` under
  `.w8-biayn/data/polyglot-benchmark` or set `SLIME_POLYGLOT_SOURCE`.
- Missing sandbox image: run the `sandbox-image` command above or set
  `W8_SLIME_POLYGLOT_SANDBOX_IMAGE` to a compatible CMake-capable image.
- Response truncation: raise `SLIME_EVAL_MAX_RESPONSE_LEN` to `8192`.
- Many timeouts: inspect `base.records.jsonl` and the sandbox logs. The default
  test timeout is `W8_SLIME_POLYGLOT_TEST_TIMEOUT_SECONDS=180`.
- Official Aider results differ: expected. This lane is a repo-owned
  SLIME-style eval, not the Aider edit harness.

