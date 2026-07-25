# Aider Fixed-26 Batch Invocation Prompts

Personal copy-paste runbook for launching many independent AI-agent sessions to
create the next Aider C++ fixed-26 improvement task batches.

This document is an invocation aid only. It is not a dataset release, training
authorization, benchmark-uplift claim, or evidence that any generated root is
verified. Every batch still needs the repository create -> audit -> remediate
-> fresh-audit loop.

## Use Pattern

Use one batch per AI-agent session. Do not ask one agent to generate the full
1,500-2,500 task campaign.

For each batch:

1. Copy one batch card from the catalog below.
2. Paste it together with the "Specification Prompt" into a fresh AI-agent
   session.
3. Review the produced spec.
4. Paste the same batch card together with the "Implementation Prompt" into a
   fresh or resumed AI-agent session.
5. Do not move to projection/training until the exact regenerated tree receives
   a clean `audit-sft-data-quality` pass.

Normal request size is 40-100 new or improved roots. A request below 40 roots
must explain the smaller scope. A request above 100 roots must be split.

## Specification Prompt

Paste this with one batch card.

```text
Use the aider-sft-task-creator workflow.

Create the next fixed-26 improvement batch specification only.

Use the batch card below exactly. Create or update only SPEC_DOCUMENT_PATH.
Do not implement generated task roots. Do not create JSONL, token/mask
evidence, exports, training runs, or benchmark-uplift claims.

Read and follow:
- AGENTS.md
- README.md
- ROADMAP.md
- docs/AIDER_SFT_SCOPE.md
- .agents/skills/w8-biayn-framework/SKILL.md
- .agents/skills/aider-sft-task-creator/SKILL.md
- .agents/skills/audit-sft-data-quality/SKILL.md
- .agents/skills/audit-sft-data-quality/references/aider-fixed26-sft-improvement.md
- docs/aider-tasks-spec/prompts/generate-family-spec.md

Batch rules:
- one request only: 40-100 new or improved clean-room task roots;
- official Aider Polyglot C++ fixed-26 tasks are permanent holdouts;
- do not copy official wording, APIs, tests, references, filenames, task
  labels, examples, or executable contracts;
- prefer benchmark-shaped C++ tasks with Exercism-like API discipline,
  .h/.cpp or project-context surfaces where useful, stateful classes,
  exceptions, operators/free functions, exact output shapes, and retry/repair
  support evidence;
- every proposed root must specify compile/test receipt requirements,
  sanitizer expectations, a coherent wrong substitute, and a hidden test plan;
- include batch_id, included root IDs, deferred backlog, overlap checks against
  previous batches and existing roots, file-layout/API-shape counts, and the
  reason every root improves the prior dataset.

Return a complete implementation-grade Markdown specification. End with
explicit non-claims: local candidate material only; no SFT release; no training
authorization; no benchmark uplift.

<PASTE ONE BATCH CARD HERE>
```

## Implementation Prompt

Paste this after the corresponding specification exists.

```text
Use docs/aider-tasks-spec/prompts/implement-family-for-sft.md.

Implement and locally verify only the batch in the batch card below.

Do not implement any other batch. Do not hand-edit generated task output.
Change the owning curriculum/specification, generator/materializer, scaffold,
and focused tests, then regenerate only TASK_FAMILY_ROOT.

Read and follow:
- AGENTS.md
- README.md
- ROADMAP.md
- docs/AIDER_SFT_SCOPE.md
- .agents/skills/w8-biayn-framework/SKILL.md
- .agents/skills/aider-sft-task-creator/SKILL.md
- .agents/skills/aider-task-family-remediation/SKILL.md
- .agents/skills/audit-sft-data-quality/SKILL.md
- .agents/skills/audit-sft-data-quality/references/aider-fixed26-sft-improvement.md
- docs/aider-tasks-spec/prompts/implement-family-for-sft.md

Implementation rules:
- materialize and verify only 40-100 roots from this batch;
- preserve clean-room holdout separation from all official fixed-26 tasks;
- keep prompts free of references, tests, CMake, provenance, receipts, and
  hidden assets;
- require owner regeneration, focused structural tests, prompt-boundary
  validation, normal reference tests, fresh ASan/UBSan evidence, executed
  wrong-substitute rejection, duplicate/family screening, and benchmark
  contamination screening;
- if Docker or a locked runtime is unavailable, record the exact blocker as
  not_completed instead of weakening the gate;
- return the regenerated exact tree, batch ledger, receipt paths, failed or
  deferred roots, and strongest truthful status;
- do not create JSONL, token/mask evidence, exports, training runs, or
  benchmark-uplift claims.

<PASTE THE SAME BATCH CARD HERE>
```

## Audit Prompt

Use after implementation. Paste with the same batch card.

```text
Use the audit-sft-data-quality skill as a read-only audit.

Audit only the exact generated tree from this batch. Do not repair it.

Read the batch specification, generated roots, owner/generator, focused tests,
receipts, hidden tests, references, prompt-boundary evidence, negative-fixture
evidence, and benchmark/duplicate screens. Produce stable finding IDs,
per-root dispositions, and an explicit pass/review/repair/reject decision.

Check the fixed-26 improvement gates:
- 40-100 roots in this request unless explicitly smaller;
- no official fixed-26 wording/API/test/reference/executable-contract overlap;
- every retained root has compile/test/sanitizer or exact blocker evidence;
- every retained root has a coherent wrong substitute that compiles and fails;
- no duplicate # Instructions header or private path leak;
- batch ledger separates included roots from deferred backlog.

Do not claim SFT release, training authorization, or benchmark uplift.

<PASTE THE SAME BATCH CARD HERE>
```

## Batch Catalog

Paste exactly one card per AI-agent session.

### Failed Fixed-26 Analogs

```text
BATCH_ID=fixed26-b001-all-your-base
BUCKET=failed-fixed26-analog
TARGET_FAMILY=all-your-base
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b001-all-your-base
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b001-all-your-base.md
GOAL=Create 50 clean-room base-conversion analog roots covering invalid bases, digit bounds, leading-zero normalization, empty input, overflow-safe accumulation, and canonical output forms without copying official all-your-base content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b002-allergies
BUCKET=failed-fixed26-analog
TARGET_FAMILY=allergies
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b002-allergies
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b002-allergies.md
GOAL=Create 50 clean-room enum/bit-flag API roots covering membership queries, stable list ordering, ignored unknown bits, named flag sets, boundary masks, and API discipline without copying official allergies content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b003-bank-account
BUCKET=failed-fixed26-analog
TARGET_FAMILY=bank-account
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b003-bank-account
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b003-bank-account.md
GOAL=Create 50 clean-room stateful lifecycle roots covering open/close invariants, rejected operations, exception semantics, rollback, repeated calls, and concurrent-like sequencing without copying official bank-account content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b004-binary-search-tree
BUCKET=failed-fixed26-analog
TARGET_FAMILY=binary-search-tree
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b004-binary-search-tree
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b004-binary-search-tree.md
GOAL=Create 50 clean-room tree roots covering insertion, ownership, traversal order, duplicate policy, recursion/iteration edges, mutation traces, and forbidden sorted-container substitutes without copying official binary-search-tree content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b005-circular-buffer
BUCKET=failed-fixed26-analog
TARGET_FAMILY=circular-buffer
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b005-circular-buffer
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b005-circular-buffer.md
GOAL=Create 50 clean-room bounded-storage roots covering capacity, read/write, overwrite behavior, empty/full errors, wraparound, copy/move edges, and state traces without copying official circular-buffer content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b006-clock
BUCKET=failed-fixed26-analog
TARGET_FAMILY=clock
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b006-clock
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b006-clock.md
GOAL=Create 50 clean-room modular-time roots covering normalization, negative offsets, day wrap, equality, formatting, arithmetic, and boundary transitions without copying official clock content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b007-complex-numbers
BUCKET=failed-fixed26-analog
TARGET_FAMILY=complex-numbers
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b007-complex-numbers
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b007-complex-numbers.md
GOAL=Create 50 clean-room numeric type roots covering operators/free functions, precision, equality tolerances, division edges, transcendental helpers where appropriate, and multi-file API discipline without copying official complex-numbers content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b008-crypto-square
BUCKET=failed-fixed26-analog
TARGET_FAMILY=crypto-square
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b008-crypto-square
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b008-crypto-square.md
GOAL=Create 50 clean-room string-grid formatting roots covering normalization, grid dimensions, padding, grouping, exact output shapes, Unicode-free C++17 string handling, and boundary inputs without copying official crypto-square content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b009-diamond
BUCKET=failed-fixed26-analog
TARGET_FAMILY=diamond
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b009-diamond
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b009-diamond.md
GOAL=Create 50 clean-room ASCII-shape roots covering symmetry, width, line count, center/edge characters, exact whitespace, invalid inputs, and shape-specific wrong substitutes without copying official diamond content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b010-dnd-character
BUCKET=failed-fixed26-analog
TARGET_FAMILY=dnd-character
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b010-dnd-character
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b010-dnd-character.md
GOAL=Create 50 clean-room small-rules-engine roots covering bounded pseudo-random-free scoring, modifiers, aggregate invariants, generated stat objects, edge rules, and deterministic tests without copying official dnd-character content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b011-gigasecond
BUCKET=failed-fixed26-analog
TARGET_FAMILY=gigasecond
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b011-gigasecond
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b011-gigasecond.md
GOAL=Create 50 clean-room date/time offset roots covering large second/day offsets, leap days, month boundaries, local-date style APIs, overflow checks, and exact date outputs without copying official gigasecond content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b012-grade-school
BUCKET=failed-fixed26-analog
TARGET_FAMILY=grade-school
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b012-grade-school
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b012-grade-school.md
GOAL=Create 50 clean-room ordered-registry roots covering add/move/remove, stable sorted returns, duplicate policy, grade/group partitions, state mutation, and API return values without copying official grade-school content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b013-kindergarten-garden
BUCKET=failed-fixed26-analog
TARGET_FAMILY=kindergarten-garden
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b013-kindergarten-garden
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b013-kindergarten-garden.md
GOAL=Create 50 clean-room mapping/assignment roots covering fixed roster ordering, two-row or multi-row layout parsing, symbol lookup, invalid symbols, stable result order, and exact API names without copying official kindergarten-garden content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b014-meetup
BUCKET=failed-fixed26-analog
TARGET_FAMILY=meetup
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b014-meetup
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b014-meetup.md
GOAL=Create 50 clean-room calendar-selection roots covering nth/last/teenth-like weekday rules, month boundaries, invalid selectors, leap-year cases, and exact date APIs without copying official meetup content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b015-parallel-letter-frequency
BUCKET=failed-fixed26-analog
TARGET_FAMILY=parallel-letter-frequency
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b015-parallel-letter-frequency
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b015-parallel-letter-frequency.md
GOAL=Create 50 clean-room deterministic aggregation roots covering chunking, case normalization, stable merge order, empty inputs, non-letter filtering, and parallel-like APIs without copying official parallel-letter-frequency content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b016-perfect-numbers
BUCKET=failed-fixed26-analog
TARGET_FAMILY=perfect-numbers
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b016-perfect-numbers
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b016-perfect-numbers.md
GOAL=Create 50 clean-room integer-classification roots covering divisor sums, invalid values, boundary values, overflow-safe loops, enum/category APIs, and wrong-class discriminators without copying official perfect-numbers content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b017-phone-number
BUCKET=failed-fixed26-analog
TARGET_FAMILY=phone-number
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b017-phone-number
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b017-phone-number.md
GOAL=Create 50 clean-room lexical canonicalization roots covering punctuation stripping, country/prefix rules, invalid digit positions, formatting, normalization, and exception/result APIs without copying official phone-number content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b018-queen-attack
BUCKET=failed-fixed26-analog
TARGET_FAMILY=queen-attack
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b018-queen-attack
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b018-queen-attack.md
GOAL=Create 50 clean-room grid-relation roots covering coordinate validation, same-row/column/diagonal-like relations, collision rejection, board bounds, and exact boolean APIs without copying official queen-attack content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b019-space-age
BUCKET=failed-fixed26-analog
TARGET_FAMILY=space-age
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b019-space-age
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b019-space-age.md
GOAL=Create 50 clean-room unit-conversion roots covering named scales, precision, large inputs, per-unit methods/free functions, invalid unit handling, and stable numeric outputs without copying official space-age content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b020-spiral-matrix
BUCKET=failed-fixed26-analog
TARGET_FAMILY=spiral-matrix
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b020-spiral-matrix
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b020-spiral-matrix.md
GOAL=Create 50 clean-room matrix traversal/fill roots covering exact shape, clockwise/counterclockwise variants that are not official copies, rectangular cases, boundaries, and traversal-order discriminators without copying official spiral-matrix content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b021-sublist
BUCKET=failed-fixed26-analog
TARGET_FAMILY=sublist
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b021-sublist
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b021-sublist.md
GOAL=Create 50 clean-room sequence-relation roots covering equal/proper-sub/proper-super/unequal classification, empty sequences, repeated values, stable enum APIs, and false prefix/suffix substitutes without copying official sublist content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b022-yacht
BUCKET=failed-fixed26-analog
TARGET_FAMILY=yacht
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b022-yacht
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b022-yacht.md
GOAL=Create 50 clean-room scoring-engine roots covering category-specific scoring, invalid category/input, duplicate dice/count rules, boundary categories, and exact integer outputs without copying official yacht content.
DEFERRED_BACKLOG=Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b023-zebra-puzzle
BUCKET=failed-fixed26-analog
TARGET_FAMILY=zebra-puzzle
TARGET_COUNT=50
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b023-zebra-puzzle
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-analogs/fixed26-b023-zebra-puzzle.md
GOAL=Create 50 clean-room small constraint-solving roots covering finite-domain assignments, uniqueness, adjacency/order constraints, exact query answers, contradiction handling, and solver/test discriminators without copying official zebra-puzzle content.
DEFERRED_BACKLOG=Second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.
```

### Second-Try-Only Families

```text
BATCH_ID=fixed26-b024-knapsack
BUCKET=second-try-only-family
TARGET_FAMILY=knapsack
TARGET_COUNT=60
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-second-try/fixed26-b024-knapsack
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-second-try/fixed26-b024-knapsack.md
GOAL=Create 60 clean-room optimization/selection roots covering capacity, exact tie rules, boundary weights, reconstruction, invalid items, and repair-support failure evidence without copying official knapsack content.
DEFERRED_BACKLOG=linked-list, robot-name, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b025-linked-list
BUCKET=second-try-only-family
TARGET_FAMILY=linked-list
TARGET_COUNT=60
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-second-try/fixed26-b025-linked-list
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-second-try/fixed26-b025-linked-list.md
GOAL=Create 60 clean-room linked-structure roots covering ownership, push/pop, insert/remove, iteration, empty/singleton states, copy/move behavior, and repair-support failure evidence without copying official linked-list content.
DEFERRED_BACKLOG=robot-name, multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b026-robot-name
BUCKET=second-try-only-family
TARGET_FAMILY=robot-name
TARGET_COUNT=60
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-second-try/fixed26-b026-robot-name
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-second-try/fixed26-b026-robot-name.md
GOAL=Create 60 clean-room unique-identifier lifecycle roots covering allocation, reset, collision avoidance, deterministic tests, exhausted pools, formatting, and repair-support failure evidence without copying official robot-name content.
DEFERRED_BACKLOG=Multi-file API discipline, repair-support batches, and filtered current anchors.
```

### Multi-File C++ API Discipline

```text
BATCH_ID=fixed26-b027-mfapi-classes-exceptions
BUCKET=multi-file-api-discipline
TARGET_FAMILY=classes-exceptions
TARGET_COUNT=75
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-mfapi/fixed26-b027-mfapi-classes-exceptions
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-mfapi/fixed26-b027-mfapi-classes-exceptions.md
GOAL=Create 75 clean-room multi-file .h/.cpp roots emphasizing stateful classes, exact exception types, invalid-operation behavior, public/private separation, and Catch tests that reject wrong exception or state behavior.
DEFERRED_BACKLOG=Remaining multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b028-mfapi-operators-templates
BUCKET=multi-file-api-discipline
TARGET_FAMILY=operators-templates
TARGET_COUNT=75
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-mfapi/fixed26-b028-mfapi-operators-templates
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-mfapi/fixed26-b028-mfapi-operators-templates.md
GOAL=Create 75 clean-room multi-file roots emphasizing overloaded operators, free functions, light templates where appropriate, value semantics, comparison/streaming behavior, and precise numeric/string outputs.
DEFERRED_BACKLOG=Remaining multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b029-mfapi-project-layout
BUCKET=multi-file-api-discipline
TARGET_FAMILY=project-layout
TARGET_COUNT=75
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-mfapi/fixed26-b029-mfapi-project-layout
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-mfapi/fixed26-b029-mfapi-project-layout.md
GOAL=Create 75 clean-room project-context roots emphasizing multiple editable production files, namespace layout, support headers, CMake-hidden tests, strict file roles, and whole-file response ordering.
DEFERRED_BACKLOG=Remaining multi-file API discipline, repair-support batches, and filtered current anchors.
```

```text
BATCH_ID=fixed26-b030-mfapi-stateful-lifecycle
BUCKET=multi-file-api-discipline
TARGET_FAMILY=stateful-lifecycle
TARGET_COUNT=75
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-mfapi/fixed26-b030-mfapi-stateful-lifecycle
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-mfapi/fixed26-b030-mfapi-stateful-lifecycle.md
GOAL=Create 75 clean-room multi-file roots emphasizing reset, rollback, idempotence, repeated construction, copy/move state, invalid transition rejection, and private randomized traces.
DEFERRED_BACKLOG=Repair-support batches and filtered current anchors.
```

### Repair-Support Batches

These create task roots plus negative-fixture/failure evidence for later
authorized repair-trajectory row builders. They do not create SFT rows.

```text
BATCH_ID=fixed26-b031-repair-compile-feedback
BUCKET=repair-support
TARGET_FAMILY=compile-feedback
TARGET_COUNT=80
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-repair-support/fixed26-b031-repair-compile-feedback
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-repair-support/fixed26-b031-repair-compile-feedback.md
GOAL=Create 80 clean-room roots with coherent wrong substitutes that produce realistic compile/type/link errors, plus redaction-safe failure summaries for later repair trajectories. Do not create JSONL repair rows.
DEFERRED_BACKLOG=Remaining repair-support batches and filtered current anchors.
```

```text
BATCH_ID=fixed26-b032-repair-test-feedback
BUCKET=repair-support
TARGET_FAMILY=test-feedback
TARGET_COUNT=80
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-repair-support/fixed26-b032-repair-test-feedback
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-repair-support/fixed26-b032-repair-test-feedback.md
GOAL=Create 80 clean-room roots with coherent wrong substitutes that compile but fail public or hidden behavioral tests, plus redaction-safe failure summaries for later repair trajectories. Do not create JSONL repair rows.
DEFERRED_BACKLOG=Remaining repair-support batches and filtered current anchors.
```

```text
BATCH_ID=fixed26-b033-repair-state-edge-feedback
BUCKET=repair-support
TARGET_FAMILY=state-edge-feedback
TARGET_COUNT=80
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-repair-support/fixed26-b033-repair-state-edge-feedback
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-repair-support/fixed26-b033-repair-state-edge-feedback.md
GOAL=Create 80 clean-room roots with stateful edge-case wrong substitutes around rollback, repeated calls, empty/singleton states, stale IDs, and ordering. Preserve redaction-safe failure evidence for later repair rows.
DEFERRED_BACKLOG=Remaining repair-support batches and filtered current anchors.
```

```text
BATCH_ID=fixed26-b034-repair-multifile-feedback
BUCKET=repair-support
TARGET_FAMILY=multifile-feedback
TARGET_COUNT=80
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-repair-support/fixed26-b034-repair-multifile-feedback
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-repair-support/fixed26-b034-repair-multifile-feedback.md
GOAL=Create 80 clean-room multi-file roots with wrong substitutes that omit one file, mismatch declarations/definitions, misuse namespaces, or fail linking, plus redaction-safe failure evidence for later repair rows.
DEFERRED_BACKLOG=Remaining repair-support batches and filtered current anchors.
```

```text
BATCH_ID=fixed26-b035-repair-format-whole-edit-feedback
BUCKET=repair-support
TARGET_FAMILY=whole-edit-feedback
TARGET_COUNT=80
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-repair-support/fixed26-b035-repair-format-whole-edit-feedback
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-repair-support/fixed26-b035-repair-format-whole-edit-feedback.md
GOAL=Create 80 clean-room roots that stress whole-file response boundaries, multi-file ordering, missing/extra file rejection, and parser-compatible final answers. Preserve redaction-safe failure evidence for later repair rows.
DEFERRED_BACKLOG=Filtered current anchors.
```

### Current Synthetic Anchor Filtering

These are not new-task generation prompts. Use them only after new task batches
exist, when you want to select cleaned anchors from the existing synthetic
dataset. They should not be counted as new benchmark-shaped coverage.

```text
BATCH_ID=fixed26-b036-filter-current-synthetic-01
BUCKET=filtered-current-synthetic-anchor
TARGET_FAMILY=current-synthetic-filter
TARGET_COUNT=100
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-filtered-anchors/fixed26-b036-filter-current-synthetic-01.md
GOAL=Audit and select up to 100 high-quality current synthetic anchor rows/roots from existing verified material. Reject duplicate # Instructions headers, high-copy rows without teaching value, stale receipts, private leaks, and weak header-only duplicates. Do not create new task roots unless remediation is explicitly routed through an owner.
DEFERRED_BACKLOG=Remaining current synthetic anchor filtering.
```

```text
BATCH_ID=fixed26-b037-filter-current-synthetic-02
BUCKET=filtered-current-synthetic-anchor
TARGET_FAMILY=current-synthetic-filter
TARGET_COUNT=100
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-filtered-anchors/fixed26-b037-filter-current-synthetic-02.md
GOAL=Audit and select up to 100 additional high-quality current synthetic anchor rows/roots from existing verified material, excluding all IDs selected by prior filter batches. Do not create new task roots unless remediation is explicitly routed through an owner.
DEFERRED_BACKLOG=Remaining current synthetic anchor filtering.
```

```text
BATCH_ID=fixed26-b038-filter-current-synthetic-03
BUCKET=filtered-current-synthetic-anchor
TARGET_FAMILY=current-synthetic-filter
TARGET_COUNT=100
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-filtered-anchors/fixed26-b038-filter-current-synthetic-03.md
GOAL=Audit and select up to 100 additional high-quality current synthetic anchor rows/roots from existing verified material, excluding all IDs selected by prior filter batches. Do not create new task roots unless remediation is explicitly routed through an owner.
DEFERRED_BACKLOG=Remaining current synthetic anchor filtering.
```

```text
BATCH_ID=fixed26-b039-filter-current-synthetic-04
BUCKET=filtered-current-synthetic-anchor
TARGET_FAMILY=current-synthetic-filter
TARGET_COUNT=100
TASK_FAMILY_ROOT=.w8-biayn/data/aider-tasks-expansion-v1
SPEC_DOCUMENT_PATH=docs/aider-synthetic/aider-fixed26-filtered-anchors/fixed26-b039-filter-current-synthetic-04.md
GOAL=Audit and select up to 100 additional high-quality current synthetic anchor rows/roots from existing verified material, excluding all IDs selected by prior filter batches. Do not create new task roots unless remediation is explicitly routed through an owner.
DEFERRED_BACKLOG=No additional default backlog. Add another filter batch only if the cleaned-anchor target remains short.
```

## Suggested Parallel Launch Order

Start with independent specification sessions for batches `b001` through `b010`.
After those specs exist, launch implementation sessions for the same batch IDs.
Keep a simple external tracker with these columns:

```text
batch_id
spec_status
implementation_status
audit_status
root_count_verified
blocker
next_action
```

Do not merge or project a batch into SFT rows until `audit_status` is clean for
the exact regenerated tree.
