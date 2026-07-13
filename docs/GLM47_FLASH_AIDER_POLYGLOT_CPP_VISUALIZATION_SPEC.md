# GLM-4.7-Flash Aider Polyglot C++ Visualization Specification

Status: implemented by `src/w8_biayn/modal_aider_visualization.py` and covered by `tests/test_modal_aider_visualization.py`.

This document specifies a deterministic, read-only visualization report for the
independent GLM-4.7-Flash Aider Polyglot C++ Modal evaluation. It is an
implementation contract for an AI coding agent. The benchmark protocol,
formulas, and evidence admission rules remain authoritative in:

- `examples/modal/glm47_flash_aider_polyglot_cpp/README.md`;
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_MODAL_BASE_EVAL_PLAN.md`;
- `src/w8_biayn/modal_aider_polyglot_cpp.py`;
- `tests/test_modal_aider_polyglot_cpp.py`.

The visualizer consumes admitted artifacts without changing, flattening,
repairing, or rescoring them. It is an offline analysis surface, not another
benchmark runner and not an official Aider leaderboard publisher.

## 1. Goals

The report must answer:

1. What are the four admitted independent-sampling benchmark values?
2. Which tasks are consistently solved, retry-dependent, unstable, or never
   solved?
3. How much does the second Aider try recover from first-try failures?
4. Which failures correlate with context exhaustion, token use, long runtime,
   or repeated interaction?
5. Is the evidence complete enough for a final model claim, or is it only an
   in-progress diagnostic?

It must remain useful with a validated prefix such as samples 1 through 7, but
partial data must never be presented as a completed `pass@8` result.

## 2. Non-goals

The implementation must not:

- contact Modal, Hugging Face, GitHub, SGLang, or an inference API;
- allocate paid resources or require Modal/HF credentials;
- modify the canonical run tree or its `artifact_manifest.json`;
- parse generated reasoning or embed model response text;
- reinterpret Aider prompt, edit, test, or retry behavior;
- rename raw Aider `pass_rate_1` or `pass_rate_2` as pass@1 or pass@2;
- calculate or publish pass@2 through pass@7;
- merge an older one-sample run into this eight-trajectory result family;
- turn infrastructure exceptions into model failures;
- infer failure details absent from structured persisted fields;
- claim an official Aider leaderboard score.

## 3. Terminology And Formulas

The experiment has two axes:

- **sample/trajectory breadth**: eight isolated trajectories per task;
- **Aider try depth**: an initial try and, after an initial failure, one
  sequential repair try using feedback from that same trajectory.

For task `i`, sample `s`, and cumulative try depth `t`:

```text
y[i,s,1] = 1 when try 1 passes, otherwise 0
y[i,s,2] = 1 when try 1 or try 2 passes, otherwise 0
c[i,t]   = sum over the eight samples of y[i,s,t]
```

The only final benchmark metrics are:

```text
pass@1_try1
pass@1_try2
pass@8_try1
pass@8_try2
```

For a complete run:

```text
task_pass_at_1_try_t(i) = c[i,t] / 8
task_pass_at_8_try_t(i) = 1 if c[i,t] > 0 else 0
```

Each metric is the mean of its task value over the exact 26 tasks. Preserve:

```text
pass@1_try1 <= pass@1_try2
pass@8_try1 <= pass@8_try2
pass@1_try1 <= pass@8_try1
pass@1_try2 <= pass@8_try2
```

There is no required ordering between `pass@1_try2` and `pass@8_try1`.

Try-2 values are cumulative. A cell passing try 1 remains successful at try
depth 2 although Aider skips the second model call. A first-try failure must
have exactly one persisted second-try outcome before the cell is complete.

## 4. Evidence Authority And Inputs

Treat these files in descending authority:

1. Per-task `.aider.results.json` for outcomes and numeric diagnostics.
2. Matching nonempty `.aider.chat.history.md` for completeness and hashes only;
   its contents are not visualization input.
3. Per-sample Aider `stats.json` and `stats.txt`.
4. Repository-derived `samples.jsonl`, both success matrices, and
   `pass-at-1-and-8-by-try.json` for a final run.
5. `run_receipt.json` and `artifact_manifest.json` for final admission.
6. Redacted config, command/request metadata, settings hashes, and fresh-tree
   receipts for identity and seed display.

The complete input layout is:

```text
runs/<run-id>/
  config.redacted.json
  runner.identity.json
  run_receipt.json
  artifact_manifest.json
  independent-pass-at-1-and-8/
    sample-01/ ... sample-08/
      command.json
      request-metadata.json
      fresh-tree.receipt.json
      model-settings.yml
      model-settings.sha256
      stats.json
      stats.txt
      <official-result-directory>/
        cpp/exercises/practice/<task-id>/
          .aider.results.json
          .aider.chat.history.md
    samples.jsonl
    success-matrix.try1.json
    success-matrix.try2.json
    pass-at-1-and-8-by-try.json
    pass-at-1-and-8-by-try.csv
    report.md
```

Never use `sampling-smoke-v1` cells as full-run cells. A separately labeled
smoke appendix may be produced only when explicitly requested.

## 5. Desired Implementation Surface

Implement a pure offline module, preferably:

```text
src/w8_biayn/modal_aider_visualization.py
tests/test_modal_aider_visualization.py
```

Desired command:

```bash
uv run python -m w8_biayn.modal_aider_visualization \
  --run-root .w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/<run-id> \
  --output-root .w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/<run-id>
```

For a validated in-progress prefix, add `--allow-partial`.

The benchmark execution entrypoint remains `run.sh`; visualization is never
added to the paid launch flow. Use explicit paths rather than secret-bearing
environment configuration. Derive run ID and redacted identity from evidence.

The current `validate_local_artifacts` function receives a
`ModalAiderConfig`. Refactor or wrap its file-only reconciliation so this
visualizer can validate from `config.redacted.json` and an explicit run root.
The visualization CLI must not call `ModalAiderConfig.from_env`, require
credential exports, or invent placeholder secrets merely to enter validation.

Fail when output exists unless `--overwrite` is explicit. Overwrite may replace
only a prior report carrying a matching visualization manifest; it must not
recursively remove an arbitrary user directory.

### 5.1 Output Location

Never write below `runs/<run-id>/`. Extra chart files there would break the
canonical `artifact_manifest.json` reconciliation. Use:

```text
.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/<run-id>/
```

Generated reports are ignored local artifacts and must not be committed.

### 5.2 Rendering Stack

Prefer an offline dependency-free stack:

- Python standard library for validation, normalization, CSV, JSON, HTML, SVG;
- self-contained CSS and optional small vanilla JavaScript for filtering and
  table sorting;
- no CDN, remote font, analytics, external image, or network script;
- SVG figures suitable for documentation and presentations.

If a plotting dependency is introduced, put it in a narrow optional dependency
extra, pin a supported range, update setup documentation, and keep output
offline and deterministic.

## 6. Admission Modes

The evidence selects one of two modes; a user label cannot promote evidence.

### 6.1 Final Mode

Final mode requires:

- independent pass@1/pass@8 eval mode;
- exactly samples 1 through 8 and 26 matching tasks in every sample;
- existing independent-sample admission passes for every sample;
- 208 unique task/sample cells and no infrastructure exception;
- stored rows, matrices, summary, CSV, and Markdown match recomputation;
- receipt status is complete and `modal_app_stopped` is true;
- existing `validate_local_artifacts` manifest reconciliation passes.

Only final mode displays the four official benchmark metrics.

### 6.2 Partial Mode

Partial mode is enabled only with `--allow-partial`. It requires:

- a contiguous completed prefix `sample-01` through `sample-N`, `1 <= N < 8`;
- the same 26 task IDs in every included sample;
- validated metadata, settings identity, result rows/histories, and stats;
- the expected seed schedule and config fingerprint;
- no exception or incomplete try cell in the admitted prefix.

A sample without validated stats is incomplete and does not enter any
denominator. A gap such as samples 1, 2, 4 is an error.

Every partial page and export must say:

```text
PARTIAL DIAGNOSTIC — N OF 8 TRAJECTORIES COMPLETE — NOT PASS@8
```

Partial mode must not emit the four final metric keys. It may emit:

```text
observed_trajectory_success_rate_try1
observed_trajectory_success_rate_try2
observed_task_coverage_try1
observed_task_coverage_try2
```

For `N` completed samples:

```text
observed_trajectory_success_rate_try_t =
    sum(y[i,s,t]) / (26 * N)

observed_task_coverage_try_t =
    count(tasks with any admitted success by t) / 26
```

These are progress diagnostics, not final benchmark values.

### 6.3 Invalid Evidence

Fail closed when identities, tasks, seeds, outcomes, histories, hashes, stats,
or final manifest reconciliation disagree. Do not render capability charts from
invalid evidence.

## 7. Normalized Cell Schema

Use one normalized row per task/sample cell:

```json
{
  "task_id": "grade-school",
  "sample_index": 1,
  "seed": 20260712,
  "attempts_made": 2,
  "raw_tests_outcomes": [false, true],
  "try1_success": false,
  "try2_success": true,
  "recovered_on_try2": true,
  "outcome": "passed_try2",
  "prompt_tokens": 34393,
  "completion_tokens": 25448,
  "duration_seconds": 319.3449,
  "num_user_asks": 8,
  "num_error_outputs": 0,
  "num_exhausted_context_windows": 0,
  "num_malformed_responses": 0,
  "syntax_errors": 0,
  "indentation_errors": 0,
  "lazy_comments": 0,
  "test_timeouts": 0,
  "official_result_path": ".../.aider.results.json",
  "official_result_sha256": "<sha256>",
  "chat_history_path": ".../.aider.chat.history.md",
  "chat_history_sha256": "<sha256>",
  "config_fingerprint": "<sha256>"
}
```

Reuse production helpers for two-try admission, seeds, hashes, and
classification. Prefer extracting the row builder from
`build_independent_pass_report` into one public pure helper rather than
copying formulas into two drifting implementations.

Exclusive primary outcome priority remains:

1. `passed_try1`;
2. `passed_try2`;
3. `context_exhausted` when no try passed and its counter is positive;
4. `malformed_response` when no try passed, context was not exhausted, and its
   counter is positive;
5. `failed_tests` otherwise.

Diagnostic fields can overlap. Label context exhaustion, malformed response,
error output, syntax error, and timeout as non-exclusive flags; never force
them into a misleading stacked total.

Token and duration values cover the whole task trajectory. Do not split them by
try unless upstream adds structured per-try fields. Do not graph null
`thinking_tokens`.

## 8. Report Page Order

1. identity, evidence status, and admission banner;
2. headline metrics or partial diagnostics;
3. task/sample outcome matrices;
4. task difficulty and retry benefit;
5. sample stability and cumulative coverage;
6. token, duration, interaction, and failure diagnostics;
7. evidence completeness and optional operational timeline;
8. sortable cell-level evidence table;
9. formulas, methodology, and limitations.

Every figure needs a title, interpretation sentence, denominator, legend,
units, and a nearby link to its CSV/JSON source table.

## 9. Required Visualizations

### V1. Evidence Status And Identity Header

Show final/partial status, run ID, result-family label, model repo/revision,
Aider/Polyglot commits, edit/sampling/token settings, completed samples over 8,
admitted cells over 208, seed schedule, receipt/manifest/stopped-App gates, and
generator identity. Never show secrets or bearer values.

### V2. Four-Metric Benchmark Summary

Final mode only. Render grouped vertical bars plus an exact-value table:

- x groups: independent breadth 1 and 8;
- within each: cumulative try 1 and try 2;
- y: task-average rate, 0% through 100%;
- exact percentage above each bar;
- subtitle: `repo-derived independent pass@1/pass@8 by cumulative Aider try depth`.

Recompute and compare stored values before rendering. Explain that breadth 1
measures trajectory reliability, breadth 8 measures whether any trajectory
solved a task, and try 2 includes try-1 passes. Do not include raw Aider
`pass_rate_1/2` or label try 2 as pass@2.

### V3. Task By Sample Outcome Matrices

Render two aligned 26-by-8 heatmaps with identical task order.

Try-1 cells: initial pass, initial failure, or partial missing.

Cumulative try-2 cells: passed initially, recovered on try 2, remained failed,
or partial missing.

Rows are task IDs; columns are sample IDs with seeds. Use deterministic hardest
first order:

1. cumulative try-2 successes ascending;
2. try-1 successes ascending;
3. task ID ascending.

Use glyphs as well as color: `I` initial, `R` repaired, `F` final failure, `—`
missing. Context exhaustion may be an orange outline, not a replacement for the
outcome. Provide an alphabetical companion table.

### V4. Per-task Difficulty And Retry Gain

Render a horizontal paired-dot/lollipop chart in V3 task order:

- x: successful trajectories 0..8, or 0..N in partial mode;
- first dot: `c[i,1]`;
- second dot: `c[i,2]`;
- segment: trajectories recovered by try 2.

Show exact `c_try1/denominator` and `c_try2/denominator` values. In partial mode
the title must say `among N completed trajectories`. This is the primary
fine-tuning-target visual: zero cumulative successes indicate direct review;
large retry gains indicate initial planning/edit weakness rather than complete
inability.

### V5. Retry Transition And Recovery

Render an overall stacked bar and one stacked bar per sample using exclusive
cell states:

```text
passed_initially
recovered_on_try2
failed_after_try2
```

Denominator: `26 * completed_samples`. Show counts and percentages. Also show:

```text
retry_recovery_rate = recovered_on_try2 /
    (recovered_on_try2 + failed_after_try2)
```

If no cell reaches try 2, show `not applicable`, not zero. A Sankey may be an
additional view, but exact bars/table are required.

### V6. Cumulative Solved-task Coverage

Render two lines and marginal-new-task bars. For each fixed seed-prefix length
`s`:

```text
coverage_try_t(s) =
    count(tasks with any success in samples 1..s by t) / 26
```

Lines represent initial and cumulative-try-2 coverage; bars show newly covered
tasks from each sample. Title it `Cumulative solved-task coverage by completed
trajectory`. Never name intermediate points pass@2 through pass@7. The curve is
order-sensitive because it follows the frozen seed schedule; say so.

### V7. Per-sample Stability

Render paired bars per sample showing try-1 task success percentage, cumulative
try-2 percentage, recovered count, final-failure count, and seed. Recompute from
rows and compare raw Aider stats only as validation. If shown in a secondary
table, preserve names `Aider pass_rate_1` and `Aider pass_rate_2`.

### V8. Task Outcome-pattern Summary

Render counts and member task lists for exact mutually exclusive classes, for
`N` completed samples:

- `initially_always_solved`: `c_try1 == N`;
- `retry_needed_for_full_coverage`: `c_try1 < N` and `c_try2 == N`;
- `intermittently_solved`: `0 < c_try2 < N`;
- `never_solved`: `c_try2 == 0`.

This compact capability profile requires no subjective task taxonomy.

### V9. Structured Failure Diagnostics

Render small-multiple heatmaps on the task/sample grid for available structured
counts:

- context-window exhaustion;
- malformed response;
- error output;
- syntax error;
- test timeout;
- optionally indentation errors and lazy comments.

Show numeric counts, state that panels overlap, and never sum them as exclusive
failures. Context exhaustion remains diagnostic and does not invalidate a
complete row or erase a pass.

### V10. Token Use And Efficiency

Render:

1. prompt tokens versus completion tokens, using logarithmic axes when useful;
2. total tokens versus duration when duration exists;
3. box summaries for initial passes, try-2 recoveries, and final failures.

One point is one task/sample cell. Color by primary outcome, mark context
exhaustion with shape/outline, and expose task/sample/seed/tokens/duration in
the table or tooltip. Show medians, interquartile ranges, and raw counts. Do not
infer monetary cost; the local endpoint reports zero cost.

### V11. Runtime And Interaction Intensity

Render median task duration with min/max whiskers, per-sample total task
duration, and `num_user_asks` versus duration colored by outcome. Optionally
rank `num_error_outputs`. Use seconds/minutes explicitly. Official task
`duration` is end-to-end task time, not isolated model execution time.

### V12. Evidence Completeness Matrix

Render samples 1..8 against required evidence:

- command/request metadata and expected seed;
- fresh-tree receipt;
- settings file and matching hash;
- unique official result directory;
- exactly 26 result rows and 26 nonempty histories;
- stats JSON/text;
- admitted task set and config fingerprint.

Use text plus color for complete, incomplete, missing. Final mode also shows
receipt, manifest, matrices, summary, and stopped-App gates. This visual must
explain why an interrupted sample is excluded.

### V13. Operational Timeline Appendix

Optional and diagnostic-only. Use structured receipt/result/archive timestamps
and an optional explicitly supplied host log. Show sample spans where reliable,
timeouts, preemptions, resumes, incomplete-attempt archives, downloads, and
stopped-App verification. Keep infrastructure events visually separate from
model outcomes and label inferred timestamps. Never make terminal-log parsing
an admission dependency.

## 10. Required Evidence Table

Include one sortable/filterable row per admitted task/sample cell with:

```text
task_id
sample_index
seed
attempts_made
raw_tests_outcomes
try1_success
try2_success
recovered_on_try2
outcome
prompt_tokens
completion_tokens
duration_seconds
num_user_asks
num_error_outputs
num_exhausted_context_windows
num_malformed_responses
syntax_errors
test_timeouts
official_result_sha256
chat_history_sha256
config_fingerprint
```

HTML may link to safe relative evidence paths, but must not embed history or
generated content. Escape all artifact-derived text in HTML, SVG, Markdown,
and CSV.

## 11. Accessibility And Visual Style

Use color-blind-safe semantics and never communicate status by color alone:

```text
initial pass       #2E7D32  glyph I
try-2 recovery     #1565C0  glyph R
final model fail   #90A4AE  glyph F
context exhausted  #EF6C00  outline/glyph C
malformed response #8E24AA  glyph M
missing/partial    #FFFFFF  hatch/glyph —
infrastructure bad #C62828  glyph !
```

Requirements:

- at least 12 px figure and 14 px HTML body text;
- adequate contrast and repeated glyph legends;
- SVG `<title>` and `<desc>` elements;
- a tabular equivalent for every chart;
- one decimal in figures, full precision in JSON;
- explicit units and logarithmic-axis labels;
- untruncated task IDs or a full adjacent table;
- usable 1280 px desktop and landscape print layouts;
- print CSS that keeps legends and admission banners.

## 12. Output Contract

Desired tree:

```text
reports/<run-id>/
  index.html
  report.md
  visualization_manifest.json
  data/
    report.normalized.json
    cells.csv
    tasks.csv
    samples.csv
    coverage-by-prefix.csv
    retry-transitions.csv
    diagnostics.csv
    evidence-completeness.csv
  figures/
    01-four-metrics.svg                 # final only
    02-try1-matrix.svg
    03-try2-transition-matrix.svg
    04-task-difficulty.svg
    05-retry-transitions.svg
    06-cumulative-coverage.svg
    07-sample-stability.svg
    08-outcome-patterns.svg
    09-diagnostics.svg
    10-token-efficiency.svg
    11-runtime-interactions.svg
    12-evidence-completeness.svg
    13-operational-timeline.svg          # when input exists
```

Normalized JSON must include schema/generator versions, source/run identity,
evidence mode, completed samples/seeds, tasks/cells, final metrics only in
final mode, partial descriptive metrics only in partial mode, summaries,
admission results, and redacted configuration.

The visualization manifest records relative output paths, byte sizes, SHA-256
hashes, evidence mode, config fingerprint, source manifest hash when final, and
generator identity. Never add it to the benchmark artifact manifest.

Write through a temporary sibling directory and atomically rename only after
all tables and figures succeed.

## 13. Determinism

For identical input bytes and generator version, normalized tables and chart
geometry must match. Enforce stable sorting/JSON/newlines, Python `csv`,
locale-independent numbers, no unfixed random jitter, no traversal-order
dependence, and no use of modification time as capability data. Isolate report
generation timestamps from calculated values.

Recompute summaries from normalized admitted rows. In final mode compare them
to all stored rows, matrices, CSV, and summary before rendering.

## 14. Security And Privacy

- Never read Modal credentials from environment.
- Reject or redact bearer values and secret-shaped fields.
- Never embed reasoning, answer text, code, raw chat history, response bodies,
  or raw server output.
- Use numeric usage, structured outcomes, hashes, safe task IDs, and redacted
  identities only.
- Escape HTML/SVG/Markdown and reject traversal in evidence links.
- Reject output inside the canonical run tree.
- Do not follow symlinks outside the selected run root.
- Apply existing `ensure_secret_free` logic to normalized and rendered output.

## 15. Suggested Decomposition

```text
load_visualization_run(run_root, allow_partial) -> AdmittedVisualizationRun
discover_completed_sample_prefix(run_root) -> list[SampleEvidence]
normalize_independent_cells(samples) -> list[Cell]
validate_final_report_against_cells(run_root, cells) -> FinalMetrics
build_task_summaries(cells, completed_samples) -> list[TaskSummary]
build_sample_summaries(cells) -> list[SampleSummary]
build_retry_summary(cells) -> RetrySummary
build_coverage_prefix(cells) -> list[CoveragePoint]
build_diagnostic_summaries(cells) -> DiagnosticSummary
build_completeness(run_root) -> CompletenessMatrix
render_svg_*(normalized_report) -> str
render_html(normalized_report, figure_paths) -> str
render_markdown(normalized_report, figure_paths) -> str
write_report_atomically(report, output_root) -> Path
```

Use dataclasses or typed dictionaries. Keep raw mappings out of renderers. If
production aggregation needs refactoring, first add characterization tests and
preserve existing behavior/artifacts.

## 16. Testing Requirements

### 16.1 Loader And Admission

- accept a complete 26-by-8-by-try fixture;
- accept a contiguous validated 26-by-7 prefix only with partial mode;
- reject partial evidence without the flag and reject non-contiguous samples;
- reject mismatched tasks, seeds, fingerprints, histories, and try semantics;
- reject exception-only rows;
- reject final mode without complete/stopped receipt or matching manifest;
- keep sampling smoke separate.

### 16.2 Transformations

- reproduce the four production metrics exactly in final mode;
- emit no final metric keys in partial mode;
- verify partial rates/denominators for `N=1` and `N=7`;
- verify retry states sum to `26 * N` and no-retry recovery is N/A;
- verify coverage and marginal-new-task counts;
- verify deterministic task ordering and task-pattern exhaustiveness;
- verify diagnostic overlap and token/duration null/outlier handling;
- verify final metric order invariance and fixed-prefix diagnostic order.

### 16.3 Rendering And Output

- render every required final figure/table;
- suppress V2 in partial mode and show the exact partial warning everywhere;
- ensure no pass@2 through pass@7 appears;
- ensure partial output makes no final pass@8 claim outside the mandatory
  warning and methodology explanation;
- verify SVG accessibility and non-color glyphs;
- verify HTML escaping and absence of external resources;
- verify deterministic JSON/CSV/SVG for a fixed fixture;
- verify visualization-manifest hashes and relative paths;
- reject output inside the run tree and unsafe overwrite targets;
- scan all output for supplied secret sentinels.

Run at minimum:

```bash
uv run --extra dev pytest \
  tests/test_modal_aider_polyglot_cpp.py \
  tests/test_modal_aider_visualization.py
uv run --extra dev ruff check \
  src/w8_biayn/modal_aider_polyglot_cpp.py \
  src/w8_biayn/modal_aider_visualization.py \
  tests/test_modal_aider_polyglot_cpp.py \
  tests/test_modal_aider_visualization.py
uv run python -m compileall src tests
```

## 17. Acceptance Criteria

Implementation is complete when:

- a fresh clone generates a report from local evidence without network or
  credentials;
- canonical run bytes and artifact manifest remain unchanged;
- a seven-sample prefix yields a prominent partial diagnostic and no final
  benchmark claim;
- an admitted stopped eight-sample run yields exactly the four production
  metric names and values;
- all figures/tables agree with normalized official rows;
- every chart has machine-readable and accessible text equivalents;
- generation is deterministic, secret-free, and atomic;
- invalid/infrastructure-incomplete evidence fails closed;
- existing and visualization tests pass.

## 18. Current-run Example

After implementation, generate a partial report for the current run with:

```bash
uv run python -m w8_biayn.modal_aider_visualization \
  --run-root \
  .w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/glm47-p8b-20260712095217 \
  --output-root \
  .w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217 \
  --allow-partial
```

After all eight samples, aggregate files, complete receipt, artifact
reconciliation, and stopped-App proof exist, rerun without `--allow-partial`
to produce the final report.
