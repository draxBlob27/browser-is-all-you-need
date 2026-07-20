# Overflow-Safe Date Math Family Remediation Specification

## Scope and controlling inputs

This specification controls the clean-room re-verification of
`overflow-safe-date-math` for family type `aider-text-grid-reshaping`. The
selected workflow prompt is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`. The user
explicitly authorizes a hard counted-family bound of 8–12 roots; this v2 design
counts exactly 10.

The immutable legacy input is:

```text
.w8-biayn/data/aider-tasks/aider-dates-and-clocks/overflow-safe-date-math/
```

The only generated remediation output is:

```text
.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/overflow-safe-date-math/
```

This is local candidate material. Dataset rows, token or mask evidence,
splits, exports, training, release readiness, and benchmark uplift are not
requested.

## Legacy audit findings

All ten legacy roots have different domain nouns but share the same public
record/policy/result schema, the same validate-ID loop, the same month-then-day
record transform, the same atomic-clear branch, and the same two tests after
identifier substitution. Raw source hashes differ only because task IDs and
class/type names are embedded. The family therefore does not meet the hard
logic-and-implementation diversity rule.

The findings applied to every legacy root are:

- `OVERFLOW-DATE-001-shared-generic-reference`: one generic calendar-record
  loop implements every claimed domain objective;
- `OVERFLOW-DATE-002-semantic-duplicate-family`: all roots are renamed
  semantic copies;
- `OVERFLOW-DATE-003-nondiscriminating-tests`: one leap-day example and one
  atomic range failure cannot establish the root-specific claims; and
- `OVERFLOW-DATE-004-missing-hard-rule-evidence`: no complete seven-dimension
  all-pairs screen, coherent adversarial controls, executed per-root negative,
  or tree-bound Docker receipt exists for the legacy family.

Per the deterministic disposition rule, the lexicographically smallest
independently salvageable objective, `safe-date-audit-export`, is
`repair-in-place`. The other nine legacy template roots are `replace` and
receive new task IDs. The pre-change hashes and complete per-root contracts are
stored under the re-verification root's `.state/remedy/` directory before
task-behavior implementation.

## Counted roots and mechanisms

| Legacy ID | V2 task ID | Disposition | Required primary mechanism |
| --- | --- | --- | --- |
| `safe-date-audit-export` | `safe-date-audit-export` | repair-in-place | Checked closed-window shifting and stable multi-bucket classification. |
| `safe-date-grant-reporting` | `checked-grant-dependency-shift` | replace | Kahn topological traversal and maximum inherited-delay propagation with atomic commit. |
| `safe-date-lease-amendment` | `transactional-lease-amendments` | replace | Sequence-preserving transactional fold over unit-specific month/day amendments. |
| `safe-date-library-preservation` | `preservation-policy-join` | replace | Validated two-table policy join with stable per-item diagnostics. |
| `safe-date-manufacturing-cycle` | `bounded-service-recurrence` | replace | K-way chronological merge of bounded per-machine recurrences. |
| `safe-date-medical-protocol` | `clinical-milestone-expansion` | replace | Bounded cumulative/direct indexed gap expansion. |
| `safe-date-retention` | `retention-stage-calculator` | replace | Checked year-to-month conversion followed by two-stage review/purge calculation. |
| `safe-date-satellite-ephemeris` | `epoch-span-partitioner` | replace | Closed-interval intersection and before/inside/after segmentation. |
| `safe-date-supply-chain` | `checked-stage-pipeline` | replace | DAG critical-path evaluation with maximum-predecessor selection and mixed offsets. |
| `safe-date-voucher-expiry` | `voucher-lifecycle-ledger` | replace | Event-sourced per-voucher finite-state replay with checked pause transfer. |

Every root owns a distinct API, state or algorithm, mutation or selection
rule, invalid/boundary contract, reference control flow, deterministic oracle,
and topic-specific false substitute. A generic `Date` value and incidental
Gregorian conversion helpers are support logic and do not count as the root's
primary mechanism.

## Emitted task contract

Each counted root contains:

```text
.docs/introduction.md
.docs/instructions.md
.meta/config.json
.meta/provenance.json
.meta/tests.toml
.meta/example.h
.meta/example.cpp
.meta/task_hidden_test.cpp
.meta/oracle_test.cpp
.meta/negative.cpp
<task-id>.h
<task-id>.cpp
task_visible_test.cpp
CMakeLists.txt
```

Only the task-named header and source are editable. The prompt exposes the two
docs and those two starter files. It excludes tests, reference files,
provenance, CMake, the negative fixture, state, screens, and receipts. The
reference pair maps one-to-one and in the same order as `files.solution`.

The starter is coherent but incomplete. The reference is independently
authored and must implement the root's required primary mechanism. The visible
test covers the public example, the private test covers contract boundaries,
and the independent oracle test compares complete behavior without reusing the
reference control flow. `.meta/negative.cpp` must compile under the same strict
flags and then fail an executed test.

## Hard diversity rule

The production evaluator rereads emitted artifacts. It compares every one of
the `10 * 9 / 2 = 45` unordered pairs separately in exactly these seven
dimensions:

1. public API;
2. owned state or algorithm;
3. mutation or selection rules;
4. invalid and boundary behavior;
5. reference control flow;
6. deterministic oracle; and
7. topic-specific negative fixture.

Every dimension decision is required; the family pair passes only when all
seven pass. IDs, declared profile labels, and raw hashes are not evidence. The
screen records normalized feature fingerprints, overlap values, thresholds,
and per-dimension decisions for every pair.

The exact production evaluator must also reject three coherent clones derived
from `safe-date-audit-export`:

- a domain/identifier-renamed clone;
- a constants-or-policy-only clone that changes a public diagnostic revision
  consistently in header, reference, and tests; and
- an opposite-end-selection clone that consistently selects the last rather
  than first rejected window.

Every control must change nonempty emitted files, remain role-correct, compile,
and pass its own normal and sanitizer behavior tests before its semantic
rejection is accepted. Focused tests independently inspect exact root/pair
counts, the seven-dimension set, every decision, changed-file lists, behavior
coherence, and control rejection.

## Topic-specific negative fixtures

Each counted root has one complete, buildable false implementation:

- unchecked wrapping day shifts;
- direct-only grant extensions;
- sorted or partially committed lease amendments;
- silent default preservation policy;
- machine-block rather than chronological recurrence output;
- noncumulative-only clinical gaps;
- 365-day years or purge-from-creation retention;
- half-open epoch endpoints;
- first-predecessor rather than maximum-predecessor supply stages; and
- unchanged expiry on voucher reactivation or illegal suspended redemption.

A negative compilation failure is not evidence. The same discovered tests
must execute and reject the built negative target.

## Benchmark separation

The bound inventory is the exact 26 official Aider Polyglot C++ roots. The
screen covers emitted docs, public APIs, references, visible/private/oracle
tests, and normalized control flow for all `10 * 26 = 260` comparisons. Whole
slug checks are necessary but not sufficient. `clock`, `gigasecond`, and
`meetup` receive particular scrutiny; no root exposes clock-of-day arithmetic,
a fixed billion-second offset, or weekday-occurrence selection.

## Build and evidence contract

The owner uses C++17, `Unix Makefiles`, and strict
`-Wall -Wextra -Wpedantic -Werror`. Host normal and fresh ASan/UBSan builds are
iteration evidence. Final evidence uses the repository-pinned C++ sanity image
with Docker networking disabled and is labeled `docker_sanity`, not
`locked_oracle`.

For every root and coherent control, normal and fresh ASan/UBSan configurations
must discover the same positive test count. The receipt binds the deterministic
archive, live and independently mounted tree hashes, generator and reference
hashes, image identity, compiler/CMake versions, exact commands, network
policy, discovered counts, and executed-negative outcomes. Any artifact or
owner change invalidates prior family screens and receipts.

## Completion

`local_family_verified` requires generator-owned regeneration, prompt and role
validation, all 45 conjunctive family comparisons, all three coherent control
rejections after successful builds, all 260 holdout comparisons, every
executed topic-negative rejection, and accepted current-tree Docker normal and
sanitizer evidence. If Docker or the pinned image is unavailable, the truthful
status is `not_completed` or `pending_execution`.
