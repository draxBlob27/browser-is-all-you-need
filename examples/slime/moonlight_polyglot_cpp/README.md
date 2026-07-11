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

The launcher enables SLIME's `--rollout-skip-special-tokens` decoding flag so
Moonlight's terminal control token (for example `<|im_end|>`) is not retained
as response text. `stages/base-eval/run_receipt.txt` records
`rollout_skip_special_tokens=1` for this contract.

Start with a small `SLIME_POLYGLOT_EVAL_LIMIT`. Raise or unset it only after
the data manifest, rollout dump, and summary JSON are clean.

## Compare Pass@1 And Pass@8

After two complete evaluations over the same task set, use the offline
`compare-runs` command. It reads existing artifacts; it does not load a model,
rerun SLIME, or invoke Docker:

```bash
PASS1_RUN=/path/to/moonlight_polyglot_pass1_run
PASS8_RUN=/path/to/moonlight_polyglot_pass8_run
REPORT_OUT=.w8-biayn/slime/moonlight-polyglot-cpp/reports/pass1-vs-pass8

uv run python -m w8_biayn.integrations.slime_polyglot_cpp compare-runs \
  --run "$PASS1_RUN" \
  --run "$PASS8_RUN" \
  --out "$REPORT_OUT"
```

The command derives `k` from `eval/base.records.jsonl` and requires exactly
the same positive sample count for every task in a run. It then requires both
run receipts to be successful; recomputes each stored summary from its records;
requires the embedded schema-v2 oracle proof; compares task IDs and immutable
task/grader/image fingerprints; and checks the model, sampling, response-limit,
sandbox, and timeout receipt fields. It rejects a comparison when any of those
inputs differ. Future receipts record `eval_n_samples_per_prompt` explicitly,
but record-based derivation keeps historical runs reportable.

The generated report is category-first:

- `category_pass_at_k.svg`: the primary grouped horizontal bar chart;
- `category_sample_outcomes.svg`: 100% stacked bars for strict individual
  sample outcomes;
- `overall_pass_at_k.svg`: the two overall task-level bars;
- `category_gain.svg`: a compact dumbbell view of the same category pass
  rates;
- `comparison.summary.json`, `category_summary.csv`, and
  `task_outcomes.csv`: machine-readable chart sources;
- `report.md`: an index that embeds all charts and records interpretation
  rules.

The source `base.summary.json` retains its fine-grained, multi-label diagnostic
taxonomy. For presentation, the comparison uses six mutually-exclusive groups
so that each exercise contributes exactly once and each bar has a useful
denominator:

- Algorithms & data structures
- Text & parsing
- Numerical reasoning
- Time & date
- State & concurrency
- Logic, grids & games

`pass@k` here is the empirical fraction of tasks with at least one strict pass
among exactly `k` samples. The stacked outcome chart instead counts individual
samples, so it has a different denominator. Recovered-format results remain
diagnostic and never count as strict passes. The two runs are independently
sampled, so the reporter does not force pass@8 to be monotonic over pass@1 for
every category.

For the two July 11 runs, the command shape is:

```bash
uv run python -m w8_biayn.integrations.slime_polyglot_cpp compare-runs \
  --run /home/pipeshift/browser-is-all-you-need-sanil/browser-is-all-you-need/.w8-biayn/slime/moonlight-polyglot-cpp/runs/moonlight_polyglot_p1_smoke_20260711085134 \
  --run /home/pipeshift/browser-is-all-you-need-sanil/browser-is-all-you-need/.w8-biayn/slime/moonlight-polyglot-cpp/runs/moonlight_polyglot_p1_full_20260711091339 \
  --out /home/pipeshift/browser-is-all-you-need-sanil/browser-is-all-you-need/.w8-biayn/slime/moonlight-polyglot-cpp/reports/moonlight_polyglot_pass1_vs_pass8_20260711
```

Use `--force` only to overwrite the known files in an intentional report
directory. Generated reports remain local evidence under `.w8-biayn/` and
must not be committed.

## Optional Gemini One-Task Sanity Check

This is a paid external-API canary for the prompt/parser/grader seam, not a
Polyglot benchmark, pass@k result, Moonlight replacement, or official Aider
comparison. It sends exactly one admitted row's saved `prompt` to Gemini,
persists the raw response, and grades that unmodified text through this lane's
strict parser and Docker tests. It does not add a system prompt, structured
output schema, oracle files, test files, response repair, or parser relaxation.
`recovered_*` remains diagnostic only and never changes `strict_pass`.

Run this on the host after Polyglot data admission and sandbox-image setup; no
SLIME container or GPU is required. Use the same task that needs a cross-model
check, for example `all-your-base`. Dry-run first to inspect the exact request
without using an API key or making a paid request:

Use a host-owned output path. SLIME run directories can be root-owned when the
lane container created them, so the host user may be unable to write beneath
their `eval/` directory.

```bash
export SLIME_RUN_ID=<admitted-polyglot-run-id>
export POLYGLOT_DATA_ROOT="$PWD/.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/data"
export GEMINI_SANITY_OUT="$HOME/.w8-biayn/gemini-sanity/${SLIME_RUN_ID}/all-your-base"

uv run --extra gemini python -m w8_biayn.integrations.slime_polyglot_cpp \
  gemini-sanity \
  --data-root "$POLYGLOT_DATA_ROOT" \
  --task-id cpp/all-your-base \
  --out "$GEMINI_SANITY_OUT" \
  --model gemini-3.5-flash \
  --temperature 0 \
  --top-p 1 \
  --seed 42 \
  --max-output-tokens 8192 \
  --dry-run
```

For the single paid request, export the key in the shell and remove
`--dry-run`. `GOOGLE_API_KEY` takes precedence over `GEMINI_API_KEY`, matching
the official SDK; only the environment-variable name is recorded, never its
value. Do not put either key in committed files or command arguments.

```bash
export GEMINI_API_KEY=<secret>

uv run --extra gemini python -m w8_biayn.integrations.slime_polyglot_cpp \
  gemini-sanity \
  --data-root "$POLYGLOT_DATA_ROOT" \
  --task-id cpp/all-your-base \
  --out "$GEMINI_SANITY_OUT" \
  --model gemini-3.5-flash \
  --temperature 0 \
  --top-p 1 \
  --seed 42 \
  --max-output-tokens 8192

jq '{strict_pass, strict_reason, recovered_pass, recovered_reason,
     model, finish_reason, oracle_setup_check}' \
  "$GEMINI_SANITY_OUT/summary.json"
```

The command rejects mutable `*-latest` model aliases; record and pass an exact
model id from the [official Gemini model list](https://ai.google.dev/gemini-api/docs/models).
API-key behavior follows the
[official Gemini key guidance](https://ai.google.dev/gemini-api/docs/generate-content/api-key).
Use `--force` only for an intentional replacement; otherwise a nonempty output
directory blocks the paid call. Before making the paid API request, the command
verifies that both the output directory and its parent are writable, so a
permission error does not consume a Gemini request.

Artifacts are `prompt.txt` (verbatim admitted prompt), `response.txt` (raw API
text), `request.json` (redacted request receipt), `record.json` (the normal
strict reward record), and `summary.json` (oracle proof plus strict and
diagnostic outcomes). A strict Gemini pass is useful evidence that a strong
external model can satisfy this one task and contract. Any failure remains a
failure; manual cleanup or recovered output must not be reported as passing.

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
    gemini-sanity/<task>/
      prompt.txt
      response.txt
      request.json
      record.json
      summary.json
  ../../reports/<comparison-name>/
    comparison.summary.json
    category_summary.csv
    task_outcomes.csv
    overall_pass_at_k.svg
    category_pass_at_k.svg
    category_sample_outcomes.svg
    category_gain.svg
    report.md
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

Tokenizer control tokens are removed by the SLIME/SGLang decoding path, not by
this parser. A literal `<|im_end|>` that reaches the parser therefore remains
invalid, just like any other text outside the required fence pairs. Historical
artifacts are not rewritten; rerun evaluation after updating the launcher.

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
- Responses end in a literal `<|im_end|>`: the run used an older launcher or
  did not activate SLIME special-token skipping. Update the checkout, rerun the
  base evaluation, and confirm `rollout_skip_special_tokens=1` in the receipt.
- Many timeouts: inspect `base.records.jsonl` and the sandbox logs. The default
  test timeout is `W8_SLIME_POLYGLOT_TEST_TIMEOUT_SECONDS=180`.
- Official Aider results differ: expected. This lane is a repo-owned
  SLIME-style eval, not the Aider edit harness.
