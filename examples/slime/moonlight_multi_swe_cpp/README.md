# SLIME Moonlight Multi-SWE C++ Base Eval

This lane evaluates the base `Moonlight-16B-A3B-Instruct` checkpoint on the C++
subset of `ByteDance-Seed/Multi-SWE-bench_mini` using the repo's
SLIME/SGLang rollout-only shape.

It is not active PIE C++ performance training, does not run SFT or GRPO, and
does not report PIE speed metrics. It is also not an official Multi-SWE
leaderboard run unless the repo-owned prompt, parser, sandbox, and test harness
are replaced with the official evaluator and labeled that way.

This README is the canonical operator runbook for the lane. Repo-wide docs
should link here instead of duplicating setup knobs, response contract details,
or artifact field descriptions.

## What It Does

`prepare_data.sh` converts the C++ rows from `multi_swe_bench_mini.jsonl` into
one eval JSONL file:

```text
.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}/data/eval/cpp.jsonl
```

The bridge is:

```text
w8_biayn.integrations.slime_multi_swe_cpp
```

It filters to these C++ repositories:

- `catchorg/Catch2`
- `fmtlib/fmt`
- `nlohmann/json`
- `simdjson/simdjson`
- `yhirose/cpp-httplib`

Each eval row keeps grading-only fields such as `fix_patch`, `test_patch`, and
test buckets in task JSON under the run data directory. The prompt does not
include those oracle fields.

`eval_base.sh` runs SLIME debug rollout-only eval against the base Moonlight
Hugging Face checkpoint. The reward hook parses a single unified diff, rejects
forbidden file edits, applies the dataset `test_patch`, applies the candidate
patch, then runs the repository-specific C++ harness in Docker:

```text
w8_biayn.integrations.slime_multi_swe_cpp.reward_func
```

## Setup

From the repo root on the GPU host:

```bash
./scripts/bootstrap.sh
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime setup

git lfs install
git clone https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini \
  .w8-biayn/data/multi-swe-bench-mini
```

Build the Multi-SWE C++ sandbox image. The dry-run form prints the exact
Dockerfile:

```bash
uv run python -m w8_biayn.integrations.slime_multi_swe_cpp sandbox-image --dry-run
uv run python -m w8_biayn.integrations.slime_multi_swe_cpp sandbox-image
```

Then enter the SLIME container:

```bash
bash .w8-biayn/slime/run-container.sh
```

## Run

Inside the SLIME container:

```bash
cd /workspace/browser-is-all-you-need

export SLIME_RUN_ID="moonlight_multi_swe_cpp_$(date -u +%Y%m%d%H%M%S)"
export SLIME_MULTI_SWE_SOURCE=/workspace/browser-is-all-you-need/.w8-biayn/data/multi-swe-bench-mini
export SLIME_MULTI_SWE_EVAL_LIMIT=3
export SLIME_EVAL_MAX_RESPONSE_LEN=16384
export SLIME_NUM_GPUS=4
export SLIME_TENSOR_MODEL_PARALLEL_SIZE=2
export SLIME_EXPERT_MODEL_PARALLEL_SIZE=4
export SLIME_SGLANG_MEM_FRACTION=0.45
export W8_SLIME_MULTI_SWE_SANDBOX_IMAGE=w8-biayn-multi-swe-cpp:latest

bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh
```

Start with a small `SLIME_MULTI_SWE_EVAL_LIMIT`. Raise or unset it only after
the data manifest, rollout dump, and summary JSON are clean.

## Artifacts

The lane writes:

```text
.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}/
  data/
    manifest.json
    eval/cpp.jsonl
    tasks/<instance_id>/task.json
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
invalid-file rate, patch-apply error rate, harness-error rate, compile-error
rate, timeout rate, tests-failed rate, and `repo_summary`. It also reports
diagnostic `recovered_*` rates for invalid-format responses that can be
best-effort parsed and tested. Those recovered fields do not change strict
`score`, `pass_rate`, or `all_tests_pass`.

The lane deliberately omits PIE speed metrics such as
`correct_and_faster_rate`, runtime speedup, and child-process CPU nanoseconds.

## Response Contract

The model must return exactly one unified diff patch in one fenced `diff`
block:

````text
```diff
diff --git a/include/fmt/core.h b/include/fmt/core.h
...
```
````

Any prose outside the diff block is invalid. The grader rejects binary patches,
unsafe paths, and edits to tests, examples, docs, build files, CI files,
generated files, and files introduced by the dataset `test_patch`.

Invalid-format responses may still be best-effort parsed into `recovered_*`
diagnostics, but that path never changes strict reward or pass fields.

## Failure Checks

- Missing dataset checkout: clone
  `ByteDance-Seed/Multi-SWE-bench_mini` under
  `.w8-biayn/data/multi-swe-bench-mini` or set `SLIME_MULTI_SWE_SOURCE`.
- Non-default JSONL location: set `SLIME_MULTI_SWE_JSONL`.
- Missing sandbox image: run the `sandbox-image` command above or set
  `W8_SLIME_MULTI_SWE_SANDBOX_IMAGE` to a compatible CMake-capable image.
- Response truncation: raise `SLIME_EVAL_MAX_RESPONSE_LEN`.
- Many patch-apply errors: inspect `base.records.jsonl` for path policy
  rejections and malformed diffs.
- Many timeouts: inspect `base.records.jsonl` and the sandbox logs. The default
  test timeout is `W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS=600`.
- Official Multi-SWE results differ: expected. This lane is a repo-owned
  SLIME-style eval, not the official Multi-SWE evaluator.
