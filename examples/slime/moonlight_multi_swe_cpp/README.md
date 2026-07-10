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

`prepare_data.sh` now performs blocking data admission before any model download,
Ray startup, or GPU rollout:

1. Convert supported C++ rows from `multi_swe_bench_mini.jsonl` into schema-v2
   task JSON and `eval/cpp.jsonl`.
2. Select the official per-instance image
   `mswebench/<org>_m_<lowercase-repo>:pr-<number>` for every task.
3. Pull each selected image, resolve its immutable digest/image ID, and stamp the
   task plus `sandbox-images.json`.
4. Apply each grading-only dataset `fix_patch` and run the same repository
   harness used for model answers.
5. Admit the manifest only if every oracle returns zero and CTest reports a
   positive test count.

For example, Catch2 PR 1608 uses
`mswebench/catchorg_m_catch2:pr-1608` (all repository components must be
lowercase). This preserves the task's intended GCC/glibc/CMake environment;
the generic GCC 13 image is not the evaluation default.

The bridge is:

```text
w8_biayn.integrations.slime_multi_swe_cpp
```

It supports these C++ repositories:

- `catchorg/Catch2`
- `fmtlib/fmt`
- `nlohmann/json`
- `simdjson/simdjson`
- `yhirose/cpp-httplib`

Each eval row keeps grading-only fields such as `fix_patch`, `test_patch`, and
test buckets in task JSON under the run data directory. The prompt does not
include those oracle fields.

`eval_base.sh` first runs `verify-data`, so stale, provisional, failed, or
missing admission artifacts stop the lane before model loading. SLIME then runs
debug rollout-only eval against the base Moonlight checkpoint. The reward hook
parses one unified diff, rejects forbidden edits, applies the dataset
`test_patch`, applies the candidate patch, and runs the repository-specific C++
harness in the task's digest-pinned image:

```text
w8_biayn.integrations.slime_multi_swe_cpp.reward_func
```

All harnesses run `cd build && ctest --output-on-failure`, which works with the
official images' older CMake versions. Exit code 0 is insufficient: zero or
unreported collected tests is `no_tests_collected`, a harness error and a failed
oracle/model result. This prevents `No tests were found!!!` from becoming a
false pass.

Aggregation copies the prepared oracle proof into
`eval/base.oracle.records.jsonl`; it does not need to rerun all oracle builds.

## Setup

From the repo root on the target host:

```bash
./scripts/bootstrap.sh
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime setup
```

Install Git LFS if `git lfs install` says that `lfs` is not a Git command. On
Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y git-lfs
git lfs install
```

For a fresh dataset checkout:

```bash
git clone https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini \
  .w8-biayn/data/multi-swe-bench-mini
git -C .w8-biayn/data/multi-swe-bench-mini lfs pull
```

If the clone command already returned to the shell prompt, it is finished; do
not clone again. Install Git LFS and run only the `git -C ... lfs pull` command.

Enter the repo-generated SLIME container. It owns the repo mount, Docker socket,
host Docker CLI, caches, and short Ray temp directory needed by the nested
reward containers:

```bash
bash .w8-biayn/slime/run-container.sh
```

The generic image builder remains available for isolated harness debugging, but
is not part of the normal operator flow:

```bash
uv run python -m w8_biayn.integrations.slime_multi_swe_cpp sandbox-image --dry-run
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

# Leave W8_SLIME_MULTI_SWE_SANDBOX_IMAGE unset for official per-task images.
unset W8_SLIME_MULTI_SWE_SANDBOX_IMAGE

bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh
```

`prepare_data.sh` pulls images and compiles/tests every selected oracle, so it
can take several minutes and emit long build logs. Use
`SLIME_MULTI_SWE_PULL_IMAGES=0` only when every selected image is already in the
local Docker cache; image inspection and the oracle checks still run.

For a deliberate debugging experiment only, set one compatible image before
both preparation and evaluation:

```bash
export W8_SLIME_MULTI_SWE_SANDBOX_IMAGE=w8-biayn-multi-swe-cpp:latest
```

Such data is admitted in `override` mode and `verify-data` requires the same
override during evaluation. Do not present override-mode results as the default
per-instance evaluation.

## Operator Checklist

Before starting the paid/base-model rollout:

- [ ] `git lfs install` succeeds and the dataset JSONL is materialized.
- [ ] Docker is reachable from `.w8-biayn/slime/run-container.sh`.
- [ ] `W8_SLIME_MULTI_SWE_SANDBOX_IMAGE` is unset for the standard run.
- [ ] `prepare_data.sh` exits 0 after all image pulls and oracle tests.
- [ ] `data/manifest.json` has `schema_version: 2` and `admitted: true`.
- [ ] `data/oracle.summary.json` has `all_passed: true` and matching task/pass
      counts.
- [ ] Every `data/oracle.records.jsonl` row has `tests_collected > 0` and records
      the selected sandbox image.
- [ ] `data/sandbox-images.json` says `mode: official-per-task` and records
      immutable identities.
- [ ] Only then run `eval_base.sh` and inspect `base.summary.json`.

Useful checks:

```bash
uv run python -m w8_biayn.integrations.slime_multi_swe_cpp preflight \
  --data-root "${SLIME_RUN_ROOT:-.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}}/data" \
  --dry-run
uv run python -m w8_biayn.integrations.slime_multi_swe_cpp verify-data \
  --data-root "${SLIME_RUN_ROOT:-.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}}/data"
```

## Artifacts

The lane writes:

```text
.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}/
  data/
    manifest.json
    oracle.records.jsonl
    oracle.summary.json
    sandbox-images.json
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
    base.oracle.records.jsonl
    base.summary.json
```

The data-root oracle records are the blocking preflight proof. Each row includes
`correct_answer_source: "fix_patch"`, `tests_collected`,
`no_tests_collected`, the selected sandbox image/ID, and failure classification.
`manifest.json` remains `admitted: false` if any record fails.

The eval summary reports strict pass rate, mean reward, invalid-format rate,
invalid-file rate, patch-apply error rate, harness-error rate,
`no_tests_collected_rate`, compile-error rate, timeout rate, tests-failed rate,
and `repo_summary`. It also reports diagnostic `recovered_*` rates for
invalid-format responses that can be best-effort parsed and tested. Recovered
fields do not change strict `score`, `pass_rate`, or `all_tests_pass`.

`base.summary.json` includes `oracle_setup_check`, backed by the copied
`base.oracle.records.jsonl`. Require `oracle_setup_check.all_passed: true` before
interpreting model pass rates.

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

- `git: 'lfs' is not a git command`: install `git-lfs`, run `git lfs install`,
  then `git -C .w8-biayn/data/multi-swe-bench-mini lfs pull`.
- Docker reports `repository name ... must be lowercase`: use the generated
  lowercase tag, for example `mswebench/catchorg_m_catch2:pr-1608`.
- Catch2 fails on `MINSIGSTKSZ` under GCC 13/glibc 2.36: an override or generic
  image is active. Unset `W8_SLIME_MULTI_SWE_SANDBOX_IMAGE`, rebuild the run
  data, and confirm the Catch2 task uses its official image.
- `No tests were found!!!`: this is now `no_tests_collected`, never a pass. The
  harness must run CTest from `build/`; inspect `data/oracle.records.jsonl`.
- Missing dataset checkout: clone `ByteDance-Seed/Multi-SWE-bench_mini` under
  `.w8-biayn/data/multi-swe-bench-mini` or set `SLIME_MULTI_SWE_SOURCE`.
- Missing official image: rerun `prepare_data.sh`; it pulls selected images by
  default. `SLIME_MULTI_SWE_PULL_IMAGES=0` requires a warm local Docker cache.
- `oracle.summary.json.all_passed` is false: fix the setup before starting the
  model. The lane keeps `manifest.json.admitted` false and exits nonzero.
- Response truncation: raise `SLIME_EVAL_MAX_RESPONSE_LEN`.
- Many patch-apply errors: inspect `base.records.jsonl` for path-policy
  rejections and malformed diffs.
- Many timeouts: inspect both oracle and model records. The default timeout is
  `W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS=600`.
- Official Multi-SWE results differ: expected. This is a repo-owned SLIME-style
  eval, not the official Multi-SWE evaluator.
