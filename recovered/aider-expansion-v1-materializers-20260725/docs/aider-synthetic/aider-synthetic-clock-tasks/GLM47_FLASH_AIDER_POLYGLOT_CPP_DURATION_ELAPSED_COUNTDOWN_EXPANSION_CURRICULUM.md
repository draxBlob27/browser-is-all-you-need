# Duration, Elapsed-Time, and Countdown Expansion Curriculum

Status: implementation-owned clean-room curriculum for exactly 80 new local
candidate roots in the `Duration, elapsed-time, countdown, and lifecycle
state` cell of the 2,500-root count plan. This document does not authorize an
SFT projection, dataset release, training run, or benchmark-uplift claim.

## Evidence and boundary

The capability cell is allocated 80 new roots by
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`. Before every
materialization, the owner inventories both existing generated trees and the
expansion tree, reserves every existing task ID and semantic lineage, and
screens the exact 26 official Aider Polyglot C++ holdouts. Existing clock,
countdown, duration-formatting, elapsed-accumulation, interval, cache, queue,
and scheduling roots are immutable comparison inputs. No proposal below is a
replacement, rename, or copy of one of them.

The deterministic proposal inventory is
`src/w8_biayn/integrations/moonlight_duration_elapsed_countdown_expansion_cases.py`.
Its 80 records are the contract-first source for the generator. Each record
fixes a unique ID, title, subtopic, mechanism, public API shape, invalid rule,
ordering rule, boundary/tie rule, and executable strategy before the private
reference is rendered.

## Root allocation

The retained curriculum is the full Cartesian product of eight duration
transforms and ten reducers. IDs are `<transform>-<reducer>`.

| Transform | Count | Mechanism |
| --- | ---: | --- |
| `weighted-span` | 10 | Ceiling units of span × amount by positive weight. |
| `clipped-window` | 10 | Half-open intersection of the record and reserve/deadline windows. |
| `countdown-budget` | 10 | Enabled remaining budget after span consumption; disabled records retain the limit. |
| `deadline-slack` | 10 | Nonnegative deadline minus end in sequence order. |
| `retry-delay` | 10 | Amount plus sequence-weighted delay. |
| `active-lifecycle` | 10 | Enabled lifetime weighted by generation + 1. |
| `serial-schedule` | 10 | Serial completion cursor advanced by span plus setup amount. |
| `remaining-forecast` | 10 | Ceiling weighted units of span consumption above reserve. |

The ten reducer suffixes are `total`, `ceiling-average`, `carry-remainder`,
`peak-witness`, `threshold-count`, `positive-total`, `first-crossing`,
`capped-total`, `stable-change-count`, and `alternating-balance`.

## Common executable contract

Every root exposes one task-specific C++17 class, a task-specific `Entry`
shape, a `Report`, and one operation selected by subtopic (`integrate`,
`replay`, `simulate`, `schedule`, or `analyze`). The exact declarations are
generated from the pre-reference proposal inventory. The visible contract
defines the meaning of every field and the root-specific mechanism; the
starter is coherent but incomplete. Inputs remain caller-owned.

Every root states and tests normal, every declared invalid-field class,
duplicate, absent/empty, transform boundary, reducer boundary, genuinely
unsorted input, primary-key ties, negative limit, representable near-limit,
and overflow-or-proved-range-bound behavior. Every assertion compares the
complete report. Malformed or duplicate records are rejected atomically.
Whole-report policy failures return no partial result.
Checked `long long` arithmetic is mandatory. The reference may use incidental
vectors, sets, sorting, and output buffers, but it may not delegate the named
mechanism to a generic policy switch, a precomputed answer, a renamed task, or
benchmark code.

For every root, `.meta/negative_false_substitute.cpp` changes the reducer and
`.meta/negative_transform.cpp` changes the transform. Both are strict-warning,
compilable coherent misconceptions. The production visible/private tests must
execute and reject both. Neither enters a model-facing prompt.

## Diversity and clone controls

The family is accepted only when all `80 * 79 / 2 = 3,160` unordered pairs
pass each of these seven dimensions separately: public API; owned state or
algorithm; mutation/selection rules; invalid/boundary behavior; reference
control flow; deterministic oracle; and topic-specific negative fixture.
Evidence is extracted from emitted docs, task-named public headers, references,
visible/private tests, and reference-to-negative deltas. A single aggregate
score cannot pass a pair.

Each pair also has distinct multi-fixture behavior vectors independent of task
names and public constants. The owner materializes four non-counted coherent
controls under family `.state`: domain/identifier rename, constants/policy-only,
opposite-end selection, and superficial-token-difference. Each control changes
files, builds, and passes its coherent tests. The evaluator computes its actual
behavior vector: the opposite-order vector differs, while the other three equal
their base. Computed behavior or duplicate contract dimensions must reject it.

Cross-tree screening compares all candidates with legacy, reverify, and the
self-excluding expansion inventory using exact normalized role hashes and
identifier/literal-neutral bottom-64 five-gram contract signatures. Similarity
at or above 0.95 fails closed. The superficial clone is the mandatory positive
near-match control. The separate 26-root benchmark-holdout screen remains.

## Materialization and evidence

The sole output is:

```text
.w8-biayn/data/aider-tasks-expansion-v1/time-date/duration-elapsed-countdown/
```

The owner refuses both existing task trees, output symlinks, foreign roots,
cross-tree ID collisions, and semantic holdout overlap. It preserves raw
proposals, candidate/selected/rejected manifests, inventories, controls,
cycle/audit reports, invalidated evidence, and digest-bound receipts beneath
the family `.state` directory.

Creator preflight requires strict prompt/role/reference mapping, unique task,
prompt, answer, and reference hashes, the complete seven-dimension pair
matrix, all clone controls, the exact holdout screen, and the pinned
network-disabled Docker sanity image. Every retained root and control must
pass clean normal and fresh ASan/UBSan builds with positive equal discovery;
both negatives for every root must compile and be rejected by executed tests.

The owner's `--verify-host` lane runs the same normal, fresh ASan/UBSan,
negative-rejection, and control builds on the host toolchain and writes a
`host_verify` receipt bound to the current tree and owner hashes. It is
campaign evidence only; it is not `docker_sanity` and cannot set
`local_family_verified`.

Only a clean independent re-audit of the exact final regenerated tree may set
`local_family_verified`. Local verification does not create SFT rows, release
readiness, training authorization, or benchmark uplift.
