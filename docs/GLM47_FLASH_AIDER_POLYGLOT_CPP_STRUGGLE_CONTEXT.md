# GLM-4.7-Flash Aider Polyglot C++ Struggle Context

Status: context note for agents planning or reviewing Aider-style C++ SFT data.

This document explains where base `zai-org/GLM-4.7-Flash` struggled in the
Modal-hosted official Aider Polyglot C++ base evaluation, and what that implies
for the repository's SFT data generation goals. It is not a benchmark runner,
not a leaderboard claim, and not PIE performance-RL evidence.

Use this with:

- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`
- `examples/modal/glm47_flash_aider_polyglot_cpp/README.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_VISUALIZATION_SPEC.md`

The official Aider Polyglot C++ task IDs remain a permanent benchmark holdout.
Do not put those tasks, their tests, their references, their prompts, their
model outputs, or close semantic copies into the SFT dataset.

## Evidence Used

Primary evidence:

- Run ID: `glm47-p8b-20260712095217`
- Mode: independent pass@1/pass@8 by cumulative Aider try depth
- Model: `zai-org/GLM-4.7-Flash`
- Model revision: `7dd20894a642a0aa287e9827cb1a1f7f91386b67`
- Aider commit: `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`
- Polyglot commit: `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`
- Evidence completeness: 8/8 samples, 208/208 task/sample cells
- Modal teardown proof: `modal_app_stopped: true`
- Local receipt: `.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/glm47-p8b-20260712095217/run_receipt.json`
- Local visualization report: `.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/report.md`

Corroborating sequential full-run evidence:

- Run ID: `glm47-flash-aider-cpp-20260711192046`
- Aider `pass_rate_1`: 0.0
- Aider `pass_rate_2`: 15.4
- Well-formed cases: 100.0 percent
- Local stats: `.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/glm47-flash-aider-cpp-20260711192046/full/stats.json`

The generated `.w8-biayn/` files are local evidence and stay ignored by Git.
This checked-in document records only the conclusions needed for future agents.

## Headline Failure Shape

| Metric | Value | Interpretation |
|---|---:|---|
| `pass@1_try1` | 0.0048076923 | The first whole-file edit almost never passed. |
| `pass@1_try2` | 0.1730769231 | The same trajectory's repair turn helped but still left most cells failing. |
| `pass@8_try1` | 0.0384615385 | With eight independent tries, only one task had any initial pass. |
| `pass@8_try2` | 0.4230769231 | Eight independent trajectories plus one repair turn solved 11/26 tasks at least once. |

Cell-level totals from the complete independent run:

| Outcome | Count |
|---|---:|
| Passed on try 1 | 1 |
| Recovered on try 2 | 35 |
| Failed tests after try 2 | 131 |
| Final outcome context exhausted | 41 |
| Total cells | 208 |

The main signal is not "Aider could not parse the answers." The model usually
produced syntactically usable edits, but they usually failed the tests or ran
out of usable output budget before reaching a passing edit.

## Formatting And Protocol Issues

Observed structured diagnostics:

- `num_malformed_responses`: 1 event in 208 independent cells.
- `syntax_errors`: 0.
- `indentation_errors`: 0.
- `lazy_comments`: 0.
- `test_timeouts`: 0.
- Cells with `num_exhausted_context_windows > 0`: 51/208.
- Total exhausted-context-window events: 56.
- Cells with `num_error_outputs > 0`: 51/208.

Aider's `num_exhausted_context_windows` field is a provider output-limit
diagnostic in this lane. It should be read as a real model-behavior problem,
but not as proof that the infrastructure failed.

SFT implication:

- Keep assistant targets compact and final-answer focused.
- Teach exact whole-file edit discipline and complete compilable file states.
- Avoid long, meandering reasoning in supervised targets.
- Preserve token/mask evidence and sequence-length admission gates.
- Treat format as necessary but insufficient: format compliance alone will not
fix the observed low correctness rate.

## Topic Gaps

| Topic | Try-2 successes | Task coverage by try 2 | Tasks never solved in this run |
|---|---:|---:|---|
| Time & date | 0/24 | 0/3 | `clock`, `gigasecond`, `meetup` |
| Text & parsing | 1/32 | 1/4 | `crypto-square`, `diamond`, `kindergarten-garden` |
| Logic, grids & games | 4/32 | 1/4 | `queen-attack`, `spiral-matrix`, `zebra-puzzle` |
| State & concurrency | 5/32 | 2/4 | `bank-account`, `parallel-letter-frequency` |
| Algorithms & data structures | 14/48 | 3/6 | `binary-search-tree`, `circular-buffer`, `sublist` |
| Numerical reasoning | 12/40 | 4/5 | `all-your-base` |

The strongest relative areas were numerical reasoning and algorithms/data
structures, but even there the model was inconsistent and often needed try-2
test feedback. The weakest clusters were time/date and text/parsing.

## Task-Level Read

Never solved across all eight independent trajectories:

- Time/date: `clock`, `gigasecond`, `meetup`
- Text/parsing/layout: `crypto-square`, `diamond`, `kindergarten-garden`
- Data structures: `binary-search-tree`, `circular-buffer`, `sublist`
- State/concurrency: `bank-account`, `parallel-letter-frequency`
- Logic/search/grid: `queen-attack`, `spiral-matrix`, `zebra-puzzle`
- Numeric conversion: `all-your-base`

Intermittently solved only after repair:

- `allergies`, `complex-numbers`, `dnd-character`, `grade-school`,
  `knapsack`, `linked-list`, `perfect-numbers`, `phone-number`, `robot-name`,
  `space-age`

One task had any first-try success:

- `yacht`: 1/8 initial passes, 4/8 cumulative try-2 passes.

This suggests GLM-4.7-Flash can sometimes exploit Aider's second-turn test
feedback, but its first edit is not reliably close enough. The SFT target
should be high-quality one-shot C++ task completion, not benchmark transcript
memorization.

## Areas To Improve With SFT Data

### 1. First-Try Whole-File Correctness

The primary gap is first-turn correctness. SFT rows should teach the model to
produce a complete, compilable, test-passing file state on the first answer.
Rows should emphasize:

- exact public API shape requested by starter files;
- preserving required namespaces, class names, headers, and signatures;
- complete implementation rather than partial snippets;
- tests implied by examples, edge cases, and hidden oracle behavior;
- no edits to build commands or harness files.

### 2. Compact Response Discipline

The model often spends too much output budget before landing a useful edit.
The SFT pipeline should make the desired answer shape boring and repeatable:

- short rationale only when the lane requires it;
- final file contents exactly where the consumer expects them;
- no extra prose around code;
- no duplicate or competing implementations;
- token-admitted rows that fit the locked sequence budget.

### 3. C++ Interface And Type Discipline

Many Polyglot exercises are small, but they are strict about exact interfaces.
The SFT pool should contain non-benchmark tasks that stress:

- const-correct member functions and value semantics;
- header/source split behavior;
- enum/class/namespace conventions;
- exception behavior and invalid-input handling;
- standard-library containers, iterators, algorithms, and ownership;
- deterministic random/stateful APIs where tests expect stable behavior.

### 4. Time, Date, And Modular Arithmetic

The run solved none of the time/date tasks. Add semantically distinct
non-benchmark tasks that cover:

- modular clock arithmetic, wraparound, and negative offsets;
- date increments and calendar edge cases;
- weekday selection, ordinal dates, and "last weekday" style logic;
- use of the expected C++ date/time or Boost-style APIs when the scaffold
  requires them.

### 5. Text Parsing And Layout

Text/parsing was nearly blank. Add tasks that cover:

- normalization and filtering of characters;
- columnar and rectangular string transforms;
- whitespace and newline-sensitive output;
- phone-number and identifier cleaning;
- mapping names or labels to fixed positions;
- exact string shape under edge cases.

### 6. Data Structures And Invariants

Some data-structure tasks recovered after feedback, but tree, circular-buffer,
and sublist-style tasks never solved. Add tasks that cover:

- insert/traverse/query behavior for tree-like structures;
- circular index arithmetic and overwrite semantics;
- linked ownership, copy/move, and iterator-like behavior;
- subsequence, supersequence, and equality edge cases;
- boundary conditions for empty, singleton, and duplicate-heavy inputs.

### 7. State, Concurrency, And Determinism

The model struggled with stateful and concurrency-adjacent tasks. Add tasks that
cover:

- account state machines and open/closed transitions;
- thread-safe updates where the scaffold requires them;
- parallel reductions with deterministic results;
- unique-name generation with collision handling;
- state reset behavior across repeated tests.

### 8. Logic, Search, And Constraint Problems

The logic/grid cluster remained mostly unsolved. Add tasks that cover:

- small exhaustive search with clear pruning;
- grid coordinate transforms;
- combinatorial scoring;
- constraint propagation over named entities;
- matrix fill/traversal order.

### 9. Numeric Conversion And Bit/Set Reasoning

Numerical tasks were comparatively better, but failures like `all-your-base`
show gaps in exact conversion logic. Add tasks that cover:

- arbitrary-base conversion and invalid digit handling;
- bitmask-backed sets;
- integer classification;
- rational or complex arithmetic APIs;
- overflow-conscious integer loops.

## How Agents Should Use This

When creating or reviewing SFT data, aim for tasks that teach the missing skill
without contaminating the benchmark:

- Use official Aider task IDs only as denylist and capability labels.
- Prefer semantically distinct non-benchmark tasks from pinned, licensed
  sources.
- Keep source/root families isolated across train, validation, and internal
  test.
- Verify starter, reference, normal tests, and sanitizer tests in the pinned
  sandbox.
- Preserve hidden tests and references outside released training rows.
- Record category, difficulty, provenance, contamination, token, and mask
  evidence.
- Do not use target-model benchmark responses or repair histories as SFT rows.

The goal of the SFT data generation pipeline is not to memorize these 26
Polyglot tasks. The goal is to build a verified, private-asset-free,
SLIME-compatible C++ supervised dataset that teaches GLM-4.7-Flash the
underlying behaviors it currently misses: compact answer discipline, exact C++
interfaces, and reliable first-try correctness across small but strict
programming tasks.
