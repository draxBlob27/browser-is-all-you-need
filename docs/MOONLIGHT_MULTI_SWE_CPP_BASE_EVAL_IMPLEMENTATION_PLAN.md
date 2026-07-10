# Moonlight Multi-SWE C++ Base Eval Implementation Plan

Status: implemented as an optional base-eval lane. The implementation lives in
`examples/slime/moonlight_multi_swe_cpp/` and
`src/w8_biayn/integrations/slime_multi_swe_cpp.py`. The canonical operator
runbook is `examples/slime/moonlight_multi_swe_cpp/README.md`.

Target shape: add an optional SLIME rollout-only base-eval lane for the C++
subset of `ByteDance-Seed/Multi-SWE-bench_mini`, analogous to the existing
Moonlight Polyglot C++ base-eval lane. Keep it separate from active PIE
performance RL and do not report PIE speed metrics for it.

## Source Dataset Facts

Use the Hugging Face dataset:

```text
https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini
```

The dataset card states that Multi-SWE-bench mini contains 400 total instances:
50 instances each for Python, Java, TypeScript, JavaScript, Go, Rust, C, and
C++. The C++ subset spans these repositories:

- `catchorg/Catch2`
- `fmtlib/fmt`
- `nlohmann/json`
- `simdjson/simdjson`
- `yhirose/cpp-httplib`

The repository file list shows the main data file as:

```text
multi_swe_bench_mini.jsonl
```

Expected datum fields from the dataset card:

- `org`, `repo`, `number`, `state`, `title`, `body`, `base`
- `resolved_issues`
- `fix_patch`
- `test_patch`
- `fixed_tests`, `p2p_tests`, `f2p_tests`, `s2p_tests`, `n2p_tests`
- `run_result`, `test_patch_result`, `fix_patch_result`
- `instance_id`

Use `git lfs` or Hugging Face's normal dataset download flow. Generated clones
and extracted tasks belong under `.w8-biayn/` and must not be committed.

## Scope And Non-Goals

This lane answers:

> How does the base Moonlight checkpoint perform on C++ Multi-SWE issue-fixing
> instances under a repo-owned SLIME/SGLang rollout-only harness?

It is not:

- PIE C++ optimization training.
- SFT or GRPO.
- A speed-uplift benchmark.
- An official Multi-SWE leaderboard run unless the implementation exactly
  matches the official evaluator and is labeled that way.
- A multi-language benchmark. Keep the first implementation C++ only.

Do not write a custom trainer. Reuse SLIME debug rollout-only eval, the repo's
lane wrapper pattern, and the existing local receipt shape.

## Existing Code To Read First

Before implementing, read:

- `README.md`
- `ROADMAP.md`
- `.agents/skills/w8-biayn-framework/SKILL.md`
- `docs/MOONLIGHT_POLYGLOT_CPP_BASE_EVAL_PLAN.md`
- `examples/slime/moonlight_polyglot_cpp/README.md`
- `examples/slime/moonlight_polyglot_cpp/moonlight_polyglot_cpp.sh`
- `src/w8_biayn/integrations/slime_polyglot_cpp.py`
- `src/w8_biayn/integrations/slime_swe_agent_cpp_perf.py`
- `src/w8_biayn/integrations/swe_agent_driver.py`

The Polyglot lane provides the SLIME base-eval shell shape, artifact layout,
debug-rollout aggregation pattern, strict parser/recovered diagnostics pattern,
and tests. The SWE-agent lane provides useful lessons for real repository
checkouts, file-state grading, concurrency, timeouts, and failure telemetry.

## Implemented Files

Implemented optional lane:

```text
examples/slime/moonlight_multi_swe_cpp/
  README.md
  prepare_data.sh
  eval_base.sh
  moonlight_multi_swe_cpp.sh
```

Implemented integration module:

```text
src/w8_biayn/integrations/slime_multi_swe_cpp.py
```

Implemented focused tests:

```text
tests/test_slime_multi_swe_cpp.py
```

Repo-wide documentation was updated in `README.md`, `ROADMAP.md`,
`.agents/REPO_GUIDE.md`, and `.agents/skills/w8-biayn-framework/SKILL.md`
alongside the implementation.

## Lane Constants And Env Vars

Use names that mirror Polyglot but do not reuse its env vars:

```text
DATA_SOURCE = "ByteDance-Seed/Multi-SWE-bench_mini"
BENCHMARK = "multi-swe-bench-mini"
LANGUAGE = "cpp"
DATASET_KIND = "slime-multi-swe-cpp-dataset"
DEFAULT_SANDBOX_IMAGE = "w8-biayn-multi-swe-cpp:latest"
```

Suggested environment variables:

```text
SLIME_MULTI_SWE_SOURCE
SLIME_MULTI_SWE_JSONL
SLIME_MULTI_SWE_EVAL_LIMIT
SLIME_MULTI_SWE_PROFILE
W8_SLIME_MULTI_SWE_SANDBOX_IMAGE
W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS
W8_SLIME_MULTI_SWE_INCLUDE_LOGS
W8_SLIME_MULTI_SWE_ORACLE_SETUP_CHECK
SLIME_MULTI_SWE_SKIP_ORACLE_CHECK
```

Default source path:

```text
.w8-biayn/data/multi-swe-bench-mini
```

Default JSONL path:

```text
${SLIME_MULTI_SWE_SOURCE}/multi_swe_bench_mini.jsonl
```

Default run root:

```text
.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}
```

## Dataset Builder

Implement `build-data` in `slime_multi_swe_cpp.py`.

Required behavior:

1. Load `multi_swe_bench_mini.jsonl`.
2. Filter to C++ instances by the allowlisted `(org, repo)` pairs above.
3. Respect `--eval-limit`; start with a low default for local smoke.
4. Write one SLIME eval JSONL:

   ```text
   ${RUN_ROOT}/data/eval/cpp.jsonl
   ```

5. Write one task JSON per instance:

   ```text
   ${RUN_ROOT}/data/tasks/<instance_id>/task.json
   ```

6. Write a manifest:

   ```text
   ${RUN_ROOT}/data/manifest.json
   ```

Each SLIME row should look like this:

```json
{
  "prompt": "...",
  "label": "cpp/<instance_id>",
  "task_id": "<instance_id>",
  "problem_id": "<instance_id>",
  "split": "eval",
  "metadata": {
    "benchmark": "multi-swe-bench-mini",
    "data_source": "ByteDance-Seed/Multi-SWE-bench_mini",
    "language": "cpp",
    "org": "fmtlib",
    "repo": "fmt",
    "instance_id": "...",
    "task_path": "tasks/<instance_id>/task.json"
  }
}
```

Task JSON can retain grading-only fields such as `fix_patch`, `test_patch`,
test buckets, and run results. The prompt must not include those fields.

## Prompt Contract

Start with a single-turn patch contract. This is the closest analogue to the
Polyglot lane while preserving the SWE benchmark's repository-patch shape.

Prompt should include:

- Repository: `<org>/<repo>`.
- Base branch or base commit from the `base` field, if available.
- PR title and issue body.
- Resolved issue text from `resolved_issues`, when present.
- Optional deterministic, non-oracle file context from the base checkout.

Prompt must not include:

- `fix_patch`
- `test_patch`
- `fixed_tests`, `p2p_tests`, `f2p_tests`, `s2p_tests`, `n2p_tests`
- `run_result`, `test_patch_result`, `fix_patch_result`
- Oracle hunk locations extracted from `fix_patch`

Output contract:

````text
Return exactly one unified diff patch and nothing else.

```diff
diff --git a/path/file.cpp b/path/file.cpp
...
```
````

Reject prose outside the fenced block. A diagnostic-only recovery parser may
accept raw unified diff text or a single unlabeled fence, but recovered patches
must never change strict `score`, `pass_rate`, or `all_tests_pass`.

## Repository Checkout And Harness

Multi-SWE tasks are real repository issues, so the reward path needs a checkout
and repo-specific tests. Do not fake this by only parsing patches.

Implement a repo harness registry with one entry per C++ repository:

```text
catchorg/Catch2
fmtlib/fmt
nlohmann/json
simdjson/simdjson
yhirose/cpp-httplib
```

Each harness entry should define:

- Git URL.
- How to resolve the base commit from the datum's `base` field.
- Dependency setup commands inside the sandbox image.
- Build directory policy.
- Test commands.
- Timeout and memory defaults.
- Which paths are forbidden for model patches.

The reward flow:

1. Create a scratch directory.
2. Clone or restore the target repository at the base commit.
3. Apply `test_patch`.
4. Parse the model response.
5. Reject forbidden paths before applying.
6. Run `git apply --check` for the model patch.
7. Apply the model patch.
8. Run the repo harness tests.
9. Return a strict correctness record.

The implementation can cache source checkouts under `.w8-biayn/cache/` or
inside the run data directory, but it must keep cache keys explicit:
`org`, `repo`, base commit, and dataset revision. Do not vendor repository
checkouts into git.

## Patch Safety Rules

Reject patches that:

- Touch tests, examples, docs, CI, package metadata, generated files, or build
  system files unless a repo harness explicitly allows the path.
- Touch files introduced by `test_patch`.
- Use absolute paths or `..`.
- Include binary patches.
- Modify `.git`, submodules, lock files, or vendored dependency directories.
- Contain duplicate patches for the same file when the patch parser can detect
  it.

Use structured patch parsing where practical. If the implementation shells out
to `git apply --check`, still perform a lightweight path preflight before the
shell command so forbidden edits are reported as `invalid_files`, not merely
`patch_apply_error`.

## Scoring

Use correctness-only scoring:

| Case | Score | Reason |
| --- | ---: | --- |
| Invalid response format | `-1.0` | `invalid_format` |
| Forbidden file edit | `-1.0` | `invalid_files` |
| Patch does not apply | `-0.75` | `patch_apply_error` |
| Checkout, setup, or harness error | `-0.5` | `harness_error` |
| Compile failure | `-0.5` | `compile_error` |
| Test timeout | `-0.5` | `timeout` |
| Tests run but fail | `0.0` | `tests_failed` |
| Required tests pass | `1.0` | `passed` |

Do not report PIE metrics such as `correct_and_faster_rate`, runtime speedup,
or child-process CPU nanoseconds. This is an issue-resolution benchmark, not a
performance benchmark.

Reward records should include:

```text
task_id
instance_id
org
repo
score
reason
all_tests_pass
invalid_format
invalid_files
patch_apply_error
harness_error
compile_error
timeout
tests_failed
tests_passed_count
tests_failed_count
wall_time_s
logs_truncated
```

Include raw logs only when `W8_SLIME_MULTI_SWE_INCLUDE_LOGS=1`; otherwise keep
short error excerpts to avoid huge JSONL records.

## Oracle Calibration Gate

Before enabling full eval, prove the harness on every admitted C++ instance:

1. Base checkout plus `test_patch` should fail at least one expected test when
   the dataset says it should.
2. Base checkout plus `test_patch` plus `fix_patch` should pass the required
   tests.
3. A no-op model patch should not pass issue-fixing tests.
4. An invalid patch should return `patch_apply_error`.
5. A patch that edits tests should return `invalid_files`.

Write a local calibration report under the run data or eval directory. Do not
commit generated calibration output.

If a repo has flaky or expensive tests, gate that repo behind an explicit
allowlist entry in the harness registry and record the reason in the manifest.

## SLIME Runner Shape

Mirror the Polyglot base-eval script structure:

```bash
bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh
```

`stage_args` should use:

```text
--debug-rollout-only
--prompt-data ${DATA_DIR}/eval/cpp.jsonl
--input-key prompt
--label-key label
--metadata-key metadata
--apply-chat-template
--reward-key score
--num-rollout 0
--n-samples-per-prompt 1
--eval-prompt-data multi_swe_cpp ${DATA_DIR}/eval/cpp.jsonl
--n-samples-per-eval-prompt 1
--eval-max-response-len ${SLIME_EVAL_MAX_RESPONSE_LEN:-16384}
--custom-rm-path w8_biayn.integrations.slime_multi_swe_cpp.reward_func
```

Use W&B project names and local receipts distinct from Polyglot:

```text
slime-moonlight-multi-swe-cpp
```

## Expected Operator Flow After Implementation

Host setup:

```bash
./scripts/bootstrap.sh
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime setup

git lfs install
git clone https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini \
  .w8-biayn/data/multi-swe-bench-mini

uv run python -m w8_biayn.integrations.slime_multi_swe_cpp sandbox-image
```

Inside the SLIME container:

```bash
cd /workspace/browser-is-all-you-need

export SLIME_RUN_ID="moonlight_multi_swe_cpp_$(date -u +%Y%m%d%H%M%S)"
export SLIME_MULTI_SWE_SOURCE=/workspace/browser-is-all-you-need/.w8-biayn/data/multi-swe-bench-mini
export SLIME_MULTI_SWE_EVAL_LIMIT=3
export SLIME_EVAL_MAX_RESPONSE_LEN=16384
export W8_SLIME_MULTI_SWE_SANDBOX_IMAGE=w8-biayn-multi-swe-cpp:latest

bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh
```

Start with `SLIME_MULTI_SWE_EVAL_LIMIT=1` or `3`. Raise it only after the data
manifest, calibration report, rollout dump, records JSONL, and summary JSON are
clean.

## Artifact Layout

Expected run layout:

```text
.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}/
  data/
    manifest.json
    eval/cpp.jsonl
    tasks/<instance_id>/task.json
    calibration.records.jsonl
    calibration.summary.json
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

`base.oracle.records.jsonl` and `base.summary.json.oracle_setup_check` are
written by default during aggregation. They apply each task's grading-only
`fix_patch` after the dataset `test_patch` and run the same repository harness
used for model patches. This is the setup-side proof that the local checkout,
Docker image, timeout, and harness can pass the known correct answer.

`base.summary.json` should include:

- `count`
- `pass_rate`
- `mean_reward`
- `invalid_format_rate`
- `invalid_files_rate`
- `patch_apply_error_rate`
- `harness_error_rate`
- `compile_error_rate`
- `timeout_rate`
- `tests_failed_rate`
- `repo_summary`
- `oracle_setup_check` with `correct_answer_source: "fix_patch"`, pass counts,
  reason counts, `all_passed`, and repo summaries
- diagnostic `recovered_*` rates, if a recovery parser is implemented

## Tests To Add

Add focused unit tests before live GPU work:

- Dataset builder writes eval rows, task JSON, and manifest.
- C++ filter admits only the five allowlisted C++ repos.
- Prompt excludes `fix_patch`, `test_patch`, test buckets, and run results.
- Prompt includes title/body/resolved issue material.
- Strict parser accepts exactly one fenced `diff` block.
- Strict parser rejects prose, multiple patch blocks, empty patches, binary
  patches, and raw code blocks.
- Recovery parser, if present, is diagnostic-only.
- Path preflight rejects test edits, docs, CI, absolute paths, and traversal.
- Reward returns `invalid_format` without running checkout or tests.
- Reward returns `invalid_files` before `git apply`.
- Reward returns `patch_apply_error` for bad diffs.
- Reward can be tested with a fake harness that returns pass, fail, compile
  error, timeout, and harness error.
- Aggregation writes records and summary without PIE speed metrics.
- Aggregation runs the default oracle setup check with a fake harness and writes
  `base.oracle.records.jsonl`.
- Example scripts exist and pass `bash -n`.
- Lane runner is base-eval only; no SFT or GRPO wrappers.
- README documents setup, response contract, artifacts, and failure checks.

## Validation Commands

For the implementation pass:

```bash
uv run --extra dev pytest tests/test_slime_multi_swe_cpp.py
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
```

When repo-wide docs or skills are updated:

```bash
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/w8-biayn-framework
```

For a live smoke, use a tiny `SLIME_MULTI_SWE_EVAL_LIMIT` and inspect:

```text
data/manifest.json
data/calibration.summary.json
rollout_dumps/base_eval_0.pt
eval/base.records.jsonl
eval/base.oracle.records.jsonl
eval/base.summary.json
stages/base-eval/run.log
stages/base-eval/run_receipt.txt
```

## Future Agentic Variant

If single-turn patch output is too weak or too artificial, implement a separate
agentic variant instead of silently changing this lane's contract. Reuse the
SWE-agent/OpenAI-adapter pattern from `slime_swe_agent_cpp_perf.py`, let the
agent edit a real checkout, then grade the final repository state with the
same Multi-SWE harness. Keep the single-turn and agentic results labeled
separately because they measure different capabilities.
