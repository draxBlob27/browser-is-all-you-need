# Moonlight Polyglot C++ Base Eval Design Note

Status: implemented as an optional base-eval lane. The implementation lives in
`examples/slime/moonlight_polyglot_cpp/` and
`src/w8_biayn/integrations/slime_polyglot_cpp.py`.

This file records the design boundary. The canonical operator runbook is
`examples/slime/moonlight_polyglot_cpp/README.md`; keep setup commands,
environment knobs, response examples, artifact paths, and failure checks there
instead of duplicating them here.

## Purpose

The lane answers one side-benchmark question:

> How does the base Moonlight checkpoint perform on the C++ subset of
> `Aider-AI/polyglot-benchmark` under the repo's SLIME/SGLang rollout-only
> harness?

It is separate from active PIE C++ performance RL. It does not train, does not
run SFT or GRPO, does not use the PIE `v0 -> v1` speed reward, and does not
produce official Aider leaderboard numbers.

## Current Contract

- Source data: C++ exercises from `Aider-AI/polyglot-benchmark`, cloned under
  ignored local state such as `.w8-biayn/data/polyglot-benchmark`.
- Lane stages: `prepare_data.sh` and `eval_base.sh` only.
- Data output: one SLIME eval JSONL at `data/eval/cpp.jsonl` plus copied
  exercise trees under the run data directory.
- Prompt shape: whole-file replacement. The model must return one `path` block
  followed by one C++ code block for every editable solution file.
- File policy: only solution files from `.meta/config.json` are editable. Tests,
  examples, docs, metadata, and build files are forbidden.
- Reward path: copy the exercise, apply replacements, then run the C++ Exercism
  CMake build in the dedicated Docker sandbox.
- Timeout: `W8_SLIME_POLYGLOT_TEST_TIMEOUT_SECONDS`, default `180` seconds.

## Scoring And Summaries

Strict scoring is pass/fail correctness, not speed:

| Case | Score | Reason |
| --- | ---: | --- |
| Invalid response format | `-1.0` | `invalid_format` |
| Unknown, duplicate, or missing file | `-1.0` | `invalid_files` |
| Compile failure | `-0.5` | `compile_error` |
| Test timeout | `-0.5` | `timeout` |
| Tests run but fail | `0.0` | `tests_failed` |
| All tests pass | `1.0` | `passed` |

Eval rows and reward records carry repo-owned `category` and `categories`
fields for concept heatmaps. `base.summary.json` includes `category_summary`
and diagnostic `recovered_*` rates for invalid-format responses that can be
best-effort parsed and tested. Recovery diagnostics never change strict
`score`, `pass_rate`, or `all_tests_pass`.

The summary deliberately omits PIE speed metrics such as
`correct_and_faster_rate`, `runtime_speedup`, and child-process CPU nanoseconds.

## Artifacts

A run writes local evidence under:

```text
.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/
  data/manifest.json
  data/eval/cpp.jsonl
  data/tasks/cpp/exercises/practice/<exercise>/
  stages/base-eval/run.log
  stages/base-eval/run_receipt.txt
  stages/base-eval/vram_usage.csv
  stages/base-eval/vram_peak.txt
  rollout_dumps/base_eval_0.pt
  eval/base.records.jsonl
  eval/base.summary.json
```

Do not commit benchmark clones, generated data, rollout dumps, logs, summaries,
or run receipts.

## Relationship To Aider Benchmarking

Official Aider-compatible numbers should be produced with Aider's benchmark
harness. This lane measures the model under a repo-owned prompt/parser/reward
loop; Aider's route measures Aider plus the model. Keep the result families
labeled separately.

## Validation

For doc or lane changes, run the focused Polyglot checks first:

```bash
uv run --extra dev pytest tests/test_slime_polyglot_cpp.py
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
```

For a live GPU smoke, start with a small `SLIME_POLYGLOT_EVAL_LIMIT`, then run
the two lane wrappers from the lane README and inspect `base.records.jsonl`,
`base.summary.json`, `run.log`, and `run_receipt.txt` before raising the limit.
