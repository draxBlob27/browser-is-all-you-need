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

`prepare_data.sh` performs blocking data admission before model download, Ray,
or GPU rollout:

1. Convert supported C++ rows from `multi_swe_bench_mini.jsonl` into schema-v3
   task JSON and `eval/cpp.jsonl`.
2. Select the official lowercase per-instance image
   `mswebench/<org>_m_<repo>:pr-<number>`, then pin its digest and image ID.
3. Grade directly in that image's repository at the task's exact base revision,
   prepared build directory, and bundled offline test assets. The standard path
   does not clone GitHub repositories.
4. Verify that the image's trusted `test.patch` matches the dataset, mount only
   the candidate or `fix_patch` read-only, and run `/home/fix-run.sh` with
   container networking disabled.
5. Require a successful result and a positive parsed CTest count. Exit zero with
   no discovered tests remains `no_tests_collected`, never a pass.
6. Write `oracle.records.jsonl`, `oracle.summary.json`, and the manifest after
   every task. `--resume` reuses only passing records whose task patches, base
   revision, image digest/ID, and harness protocol fingerprint still match.

This directly fixes two misleading setup failures:

- Slow fresh repository clones no longer consume the build/test timeout. The
  default 1200-second budget applies to the image's build/test command alone.
- `nlohmann/json` uses the official image's preloaded `json_test_data`, so
  `download_test_data` does not need network access inside the offline grader.

For example, Catch2 PR 1608 uses
`mswebench/catchorg_m_catch2:pr-1608` (all repository components must be
lowercase). This preserves the intended GCC/glibc/CMake environment; the
generic GCC 13 image is not the evaluation default.

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
test buckets in task JSON. The prompt never includes those oracle fields.

`eval_base.sh` first runs `verify-data`, so stale, provisional, failed,
incomplete, or fingerprint-mismatched proof stops the lane before model
loading. SLIME then runs rollout-only eval; the reward hook parses one unified
diff, rejects forbidden edits, and grades it through the same digest-pinned
official-image path:

```text
w8_biayn.integrations.slime_multi_swe_cpp.reward_func
```

Aggregation copies the prepared proof into `eval/base.oracle.records.jsonl`;
it does not rerun all oracle builds.

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

Inside the generated SLIME container, prepare all 50 C++ tasks:

```bash
cd /workspace/browser-is-all-you-need

export SLIME_RUN_ID="multi_swe_cpp_all"
export SLIME_MULTI_SWE_DATA_DIR="/workspace/browser-is-all-you-need/.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}/data"
export SLIME_MULTI_SWE_SOURCE=/workspace/browser-is-all-you-need/.w8-biayn/data/multi-swe-bench-mini
export SLIME_MULTI_SWE_EVAL_LIMIT=50
export SLIME_MULTI_SWE_REBUILD_DATA=0
export SLIME_MULTI_SWE_RESUME=1
export SLIME_MULTI_SWE_PULL_IMAGES=auto
export W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS=1200
unset W8_SLIME_MULTI_SWE_SANDBOX_IMAGE

bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
```

A schema-v2 data directory cannot be reused because it was created by the old
clone-based protocol. Rebuild that directory once, then return the knob to
zero:

```bash
export SLIME_MULTI_SWE_REBUILD_DATA=1
bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
export SLIME_MULTI_SWE_REBUILD_DATA=0
```

After interruption or failure, use the same run ID and data directory. This
does not rebuild JSON, pull warm images, clone repositories, or rerun matching
passes; failed, missing, or stale records are retried:

```bash
export SLIME_MULTI_SWE_REBUILD_DATA=0
export SLIME_MULTI_SWE_RESUME=1
export SLIME_MULTI_SWE_PULL_IMAGES=0
bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
```

To refresh only the two observed nlohmann tasks, then finish the blocking
all-task admission:

```bash
PYTHONPATH="$PWD/src" python3 -m w8_biayn.integrations.slime_multi_swe_cpp preflight \
  --data-root "$SLIME_MULTI_SWE_DATA_DIR" \
  --no-pull \
  --resume \
  --task-id nlohmann__json-1323 \
  --task-id nlohmann__json-2099

PYTHONPATH="$PWD/src" python3 -m w8_biayn.integrations.slime_multi_swe_cpp preflight \
  --data-root "$SLIME_MULTI_SWE_DATA_DIR" \
  --no-pull \
  --resume

PYTHONPATH="$PWD/src" python3 -m w8_biayn.integrations.slime_multi_swe_cpp verify-data \
  --data-root "$SLIME_MULTI_SWE_DATA_DIR"
```

A targeted command remains nonzero while any unselected record is missing or
failing; full admission still requires all 50 tasks. Per-task progress is
printed and committed to the local JSONL proof after every task.

Only after `verify-data` succeeds, run the GPU evaluation:

```bash
bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh
```

`SLIME_MULTI_SWE_PULL_IMAGES=auto` pulls on a fresh data build and skips pulls
when the compatible image receipt already exists. Set it to `1` to force
registry checks or `0` when all selected images are known to be local.

For a deliberate generic-image debugging experiment only, set one compatible
override before both preparation and evaluation:

```bash
export W8_SLIME_MULTI_SWE_SANDBOX_IMAGE=w8-biayn-multi-swe-cpp:latest
```

Override mode retains the checkout/cache fallback and is not the standard
per-instance evaluation.

## Operator Checklist

Before starting the paid/base-model rollout:

- [ ] The dataset JSONL is materialized and the SLIME container can reach Docker.
- [ ] `W8_SLIME_MULTI_SWE_SANDBOX_IMAGE` is unset for the standard run.
- [ ] `data/manifest.json` has `schema_version: 3`, `admitted: true`, and
      `harness_mode: official-instance-image`.
- [ ] `data/oracle.summary.json` has `complete: true`, `all_passed: true`, and
      matching expected/task/pass counts.
- [ ] Every oracle row has `tests_collected > 0`, `setup_valid: true`, an
      `oracle_cache_key`, and the immutable sandbox identity.
- [ ] `data/sandbox-images.json` says `mode: official-per-task`.
- [ ] No standard-path process is running `git clone`; only short-lived
      `mswebench/*` containers should appear during grading.
- [ ] Only then run `eval_base.sh` and inspect `base.summary.json`.

Useful read-only checks:

```bash
docker ps --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}'
docker exec w8-slime bash -lc \
  'pgrep -af "slime_multi_swe_cpp|git clone|python3" || true'
PYTHONPATH="$PWD/src" python3 -m w8_biayn.integrations.slime_multi_swe_cpp preflight \
  --data-root "$SLIME_MULTI_SWE_DATA_DIR" \
  --dry-run \
  --resume
PYTHONPATH="$PWD/src" python3 -m w8_biayn.integrations.slime_multi_swe_cpp verify-data \
  --data-root "$SLIME_MULTI_SWE_DATA_DIR"
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

The data-root oracle records are the incremental blocking preflight proof.
Each row includes `correct_answer_source: "fix_patch"`, `tests_collected`,
`no_tests_collected`, the immutable sandbox identity, `harness_mode`, the
fingerprinted `oracle_cache_key`, and failure classification. `manifest.json`
remains `admitted: false` if any record is failed, missing, or stale.

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
- Missing official image: rerun with `SLIME_MULTI_SWE_PULL_IMAGES=1`.
  The default `auto` mode skips registry pulls only when a compatible receipt
  already exists; `0` requires a warm local Docker cache.
- A `git clone` runs for each task: old schema-v2 code/data or a generic image
  override is active. Pull the new commit, unset the override, rebuild data once
  with `SLIME_MULTI_SWE_REBUILD_DATA=1`, then resume.
- `download_test_data` fails and dependent nlohmann tests are `Not Run`: the old
  host-checkout path is active. The schema-v3 standard path uses the official
  image's preloaded `json_test_data`; rebuild once and resume.
- `oracle.summary.json.all_passed` is false: fix the setup before starting the
  model. The lane keeps `manifest.json.admitted` false and exits nonzero.
- Response truncation: raise `SLIME_EVAL_MAX_RESPONSE_LEN`.
- Many patch-apply errors: inspect `base.records.jsonl` for path-policy
  rejections and malformed diffs.
- Many timeouts: inspect both oracle and model records. The default build/test
  timeout is `W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS=1200`; image pulls and the
  removed standard-path clones do not consume this budget.
- Official Multi-SWE results differ: expected. This is a repo-owned SLIME-style
  eval, not the official Multi-SWE evaluator.
