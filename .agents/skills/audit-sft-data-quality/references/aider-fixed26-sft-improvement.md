# Aider Fixed-26 SFT Improvement Findings

Use this reference when authoring, remediating, projecting, or auditing local
Aider-style C++ data intended to improve the Aider Polyglot C++ fixed-26
evaluation or a derivative held-out benchmark with the same skill shape.

## Source Evidence

The active local diagnosis is recorded in:

- `aider_sft_dataset_improvement_report.md`
- `aider_sft_dataset_improvement_report.json`

That report inspected `aider-tasks-expansion-v1-sft/sft/train.jsonl`, generated
on 2026-07-23. The dataset had 1,425 unique rows and no duplicate task IDs. It
was structurally usable, but the compared SFT run did not improve benchmark
solving: post-SFT pass@1 was `0/26`, pass@2 was `3/26`, while the PDF base
eval was `0/26` pass@1 and `4/26` pass@2. Error outputs increased from 6 to 9,
and context exhaustion increased from 6 to 9.

Primary diagnosis: the corpus was a synthetic, header-only, single-turn
monoculture. Zero exact overlap with fixed-26 labels is good contamination
hygiene, but it is not sufficient alignment. The benchmark stresses
Exercism-style C++ APIs, stateful classes, exceptions, templates/operators,
multi-file edits, exact output shapes, project conventions, and retry repair
behavior.

## Holdout Boundary

Official Aider Polyglot fixed-26 tasks remain holdouts. Do not copy their
prompts, tests, reference answers, filenames, exact task labels, or executable
contracts into training data. Build answer-blind analogs that teach the latent
capability while changing identifiers, domains, fixtures, surface wording, and
private tests.

Zero exact overlap is only a minimum contamination gate. A batch can pass exact
overlap checks and still be rejected for target mismatch.

## Priority Skill Families

Add answer-blind analog coverage for the failed fixed-26 families before adding
more generic synthetic rows:

- all-your-base
- allergies
- bank-account
- binary-search-tree
- circular-buffer
- clock
- complex-numbers
- crypto-square
- diamond
- dnd-character
- gigasecond
- grade-school
- kindergarten-garden
- meetup
- parallel-letter-frequency
- perfect-numbers
- phone-number
- queen-attack
- space-age
- spiral-matrix
- sublist
- yacht
- zebra-puzzle

Also add first-try and repair variants for the second-try-only families:

- knapsack
- linked-list
- robot-name

## Batch Shape

For any new batch whose stated goal is Aider fixed-26 SFT improvement, require
the planning inventory to record file-layout, API-shape, interaction-mode, and
skill-family counts.

Do not ask a model/provider/agent prompt to generate the full next campaign in
one shot. Run the campaign as a sequence of bounded authoring requests. Each
request should create, remediate, or improve one coherent batch of 40-100 task
roots, with a stable `batch_id`, included root IDs, deferred family/count
backlog, prior-batch overlap checks, and batch-local verification receipts.
Requests below 40 roots require an explicit smaller scope or an exhausted
remaining backlog. Requests above 100 roots must be split before authoring.

Target new high-quality task instances, not just more rows. A smaller verified
benchmark-shaped batch is preferable to a larger synthetic header-only batch:
1,200 verified benchmark-shaped tasks are more valuable than 5,000 unverified
or weakly verified header-only rows.

Default count targets:

| Target | Count |
| --- | ---: |
| Minimum useful next run | 1,000 new benchmark-shaped rows/tasks |
| Better next batch | about 2,000 new rows/tasks |
| Normal target band | 1,500 to 2,500 new high-quality rows/tasks |
| Above this point | quality and verification dominate count above 3,000 |

Good next-mixture target, unless the user gives a narrower experiment:

| Bucket | Count |
| --- | ---: |
| Failed fixed-26 analogs, 23 tasks x 40-60 each | 920-1,380 |
| Second-try-only families: knapsack, linked-list, robot-name | 180-300 |
| Multi-file C++ API discipline tasks | 250-400 |
| Repair trajectories with compiler/test feedback | 300-500 |
| Keep current v1 synthetic rows, filtered | 300-600 |

Aim for about 2,000 total new verified rows/tasks, then mix in about 300-500
cleaned rows from the current dataset. The current v1 synthetic rows are a
filtered anchor component; they do not count as new benchmark-shaped coverage.

Default role mix, if a percentage view is more useful than absolute counts:

| Role | Target Share |
| --- | ---: |
| Failed fixed-26 analogs | 55% |
| Second-try-only family variants | 15% |
| General C++ API discipline | 15% |
| Highest-quality current synthetic anchors | 10% |
| Format-only examples | 5% |

Default file-layout mix:

| Layout | Target Share |
| --- | ---: |
| Single-file tasks | 50% |
| Paired `.h` plus `.cpp` edits | 35% |
| Multi-file or project-context tasks | 15% |

A 100% header-only batch is not acceptable for this target unless the user
explicitly requests a narrow header-only ablation and the result is labeled as
such. Do not claim such an ablation is the report-driven improvement batch.

## Root And Row Requirements

Each retained root or row must have deterministic evidence:

- executable public contract written before the reference;
- prompt starter that fails at least one target test;
- target/reference that compiles with the intended C++17 or benchmark compiler
  policy;
- target/reference passing visible and hidden generated tests;
- fresh sanitizer evidence when code is in scope;
- at least one coherent plausible-but-wrong implementation that compiles and is
  rejected by the production tests;
- whole-edit parser or response-boundary validation for model-facing rows;
- digest-bound prompt, starter, target/reference, tests, generator, compiler or
  image, and verifier-policy receipts.

Missing current compile/test/sanitizer or wrong-substitute evidence is
`review`, `repair-and-reverify`, or `not_completed`; it is not admission.
Every new task should have compile/test receipts. Do not trade this gate away
to reach a larger count.

## Repair Data

The current failed SFT run learned whole-edit formatting but did not improve
solving. Future SFT mixtures should include 20% to 30% repair trajectories when
the row schema and training request authorize them.

Use concise real feedback:

- an initial whole-edit answer with a realistic compile or test failure;
- the actual compiler/test output, redacted to exclude private references or
  hidden fixture text;
- a corrected whole-edit answer;
- no explanatory prose in the final answer beyond the required row contract.

Local task-family verification by itself does not create repair rows. When a
workflow only creates local roots, record enough negative-fixture and failure
evidence to support a later authorized repair-row builder, and state that no
repair-data mixture has been produced.

## Prompt And Token Hygiene

Fail or repair generated prompts and rows that duplicate top-level instruction
headers such as `# Instructions`. Track answer length, prompt length, and
starter-to-answer copy ratio. High-copy rows are not automatically wrong, but
they need an explicit teaching reason and should be down-weighted or reviewed
when the semantic diff is small.

Prefer concise, task-specific scaffolding. Do not add generated boilerplate,
large helper libraries, or repeated policy text unless the capability requires
it. Reducing noise is part of the context-exhaustion mitigation.

## Acceptance Gate Before SFT

Do not start or recommend another SFT run for this target until the selected
manifest can report:

- valid JSONL with the expected chat schema;
- zero exact and semantic leakage from fixed-26 official prompts, tests,
  references, and executable contracts;
- 100% current compile/test receipts for assistant targets;
- 100% whole-edit parser pass for model-facing targets;
- zero duplicate instruction headers;
- coverage for all 26 benchmark-shaped family buckets or an explicit narrower
  experiment label;
- at least 1,000 new benchmark-shaped rows/tasks for a minimum useful next run,
  with 1,500-2,500 new high-quality rows/tasks as the normal target band;
- a mixture ledger for failed-family analogs, second-try-only families,
  multi-file API discipline, repair trajectories, and filtered current
  synthetic anchors;
- at least 30% multi-file or project-context rows for the report-driven batch;
- at least 20% repair trajectories when the training format authorizes repair;
- per-row task ID, source hash, prompt hash, target hash, compiler command,
  test result, and stdout/stderr digest.

If a projected or generated corpus does not meet these gates, label it as a
local projection, ablation, or candidate pool rather than an improvement-ready
SFT dataset.
