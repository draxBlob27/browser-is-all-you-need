# Overflow-Safe Accumulation, Scoring, and Combinatorial Arithmetic Curriculum

Status: executable clean-room curriculum for exactly 40 new local Aider-format
C++17 roots. Family ID:
`aider-expansion-v1-overflow-scoring-combinatorial-v1`.

## Scope and count-plan cell

This family implements the complete 40-root cell named **Overflow-safe
accumulation, scoring, and combinatorial arithmetic** in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`. It writes only:

```text
.w8-biayn/data/aider-tasks-expansion-v1/
  numerical-arithmetic/overflow-scoring-combinatorial/
```

The legacy and reverify trees are read-only collision and semantic-lineage
inputs. The 26 official Aider Polyglot C++ roots, their content, and close
semantic copies remain evaluation-only holdouts.

## Learning objective

The model must produce a complete first-try whole-file implementation that
performs exact integer arithmetic without undefined behavior or silent
wraparound, implements the named scoring policy in the documented order, and
uses the stated combinatorial recurrence or cancellation strategy. A wrapped,
saturated, floating-point, factorial-first, or generic renamed substitute is a
failure even when it matches a small happy-path example.

## Binding inventory

The inventory contains 14 overflow mechanisms, 13 scoring mechanisms, and 13
combinatorial mechanisms. Each row is a new root with no parent or replacement
lineage.

| Cluster | Task IDs and primary mechanisms |
| --- | --- |
| Overflow (14) | `checked-batch-total` checked addition; `checked-batch-product` checked multiplication; `capped-credit-ledger` transactional signed ledger; `checked-weighted-load` checked dot product; `reserve-prefix-floor` prefix invariant; `checked-arithmetic-series` parity-cancelled progression; `checked-geometric-series` repeated-power fold; `interval-charge-fold` ordered duration charging; `box-volume-budget` checked volume budget; `histogram-moment` indexed first moment; `checked-horner-polynomial` multiply-add evaluation; `fraction-cross-sum` rational cross numerator; `multiplicity-path-cost` traversal expansion; `depth-weighted-tree-budget` validated parent-depth fold. |
| Scoring (13) | `capped-rubric-score` per-category caps; `decaying-event-score` age decay; `streak-bonus-score` triangular run bonuses; `midrank-basis-points` tie-aware percentile; `weighted-median-mark` cumulative-weight selection; `trimmed-mean-mark` symmetric order trimming; `round-robin-table-score` W/D/L weights; `penalty-budget-score` subtractive budget; `progressive-tier-score` piecewise usage; `weighted-quorum-margin` participation-gated margin; `harmonic-placement-score` reciprocal ranks; `trapezoid-curve-score` exact area; `smoothed-reliability-score` Laplace smoothing. |
| Combinatorial (13) | `exact-binomial-coefficient` gcd-cancelled product; `falling-arrangement-count` falling factorial; `multiset-arrangement-count` incremental interleaving; `catalan-structure-count` Catalan convolution; `derangement-assignment-count` derangement recurrence; `stirling-partition-count` Stirling DP; `bell-partition-count` Bell triangle; `rectangular-lattice-route-count` route DP; `weak-composition-count` stars and bars; `bounded-composition-count` capacity DP; `multinomial-category-count` sequential choices; `onto-mapping-count` inclusion-exclusion; `ballot-prefix-count` strict ballot formula. |

## Per-root executable contract

Before reference authoring, the owner binds each root's exact public input
record, normal and invalid inputs, identity behavior, overflow boundary,
ordering or tie policy, and named forbidden substitute. All roots expose a
task-specific input record and one `evaluate` operation returning
`std::optional<std::uint64_t>`. The common return envelope is deliberate; the
input state, arithmetic mechanism, control flow, and failure policy are not
parameterized variants.

Every root must contain deterministic visible and private assertions for its
normal result and an invalid or overflow result. Its compiled false substitute
must preserve the API and compile cleanly but implement the root's easiest
plausible wrong mechanism. The production private test must execute and reject
that substitute.

## Diversity and adversarial-clone contract

The owner must inspect all 780 unordered retained-root pairs across these seven
dimensions separately: public API; owned state or algorithm; mutation or
selection rules; invalid and boundary behavior; reference control flow;
deterministic oracle; and topic-specific negative fixture. Every pair must pass
all seven decisions. IDs, declared kind labels, and raw hashes are not evidence.

The exact production evaluator must additionally reject coherent, buildable
controls for a domain/identifier rename, a constants-or-policy-only variation,
and an opposite-end traversal variation. Each control must change emitted
files, pass its own reference behavior tests in normal and fresh sanitizer
builds, and remain outside the selected manifest.

## Materialization and verification

The owner is
`src/w8_biayn/integrations/moonlight_overflow_scoring_combinatorial_aider_tasks.py`.
It must reserve IDs against all three trees, refuse legacy/reverify outputs and
symlink escapes, preserve raw/selected/rejected proposal records separately,
validate prompt roles, screen the exact existing corpus and all 26 holdouts,
and bind receipts to the owner, curriculum, specification, focused test, task
tree, references, tests, image, compiler, policy, and result hashes.

Normal and fresh ASan/UBSan evidence must run in the pinned repository C++
sanity image with networking disabled. Both modes must discover the same two
positive tests for every retained root and every coherent clone control. Every
compiled false substitute must be executed and rejected in both modes.

Creator preflight is not terminal evidence. A read-only independent audit of
the exact subject must follow. Every finding routes through a preserved remedy
record, owner edit, complete regeneration, and fresh audit.

The private oracle must exercise a normal case, an invalid or overflow case,
the mechanism's empty/identity/tie/order boundary, and the declared resource
limit. Input vectors longer than 4096 elements are invalid. Dynamic programs
use a one-million-cell budget, with the explicit 1024-row Bell and 4096-entry
Catalan limits. A negative fixture passes only when the normal expected-result
assertion rejects it (exit 2); failing merely on the invalid-input assertion is
not discriminator evidence.

## Audit/remediation cycle 1

The immutable cycle-001 audit subject
`sha256:eead3421aaff82250476c07aad77de28cf716d6f05cc3f9f5e80c54edadb0d82`
reported `not_completed` with findings `OSC-AUD-001` through `OSC-AUD-009`.
All nine are `repair-in-place`. The owner remediation binds the complete source
and holdout inventories, screens legacy, reverify, and other expansion roots,
neutralizes task identity in diversity evidence, distributes the three clone
controls across overflow/scoring mechanisms, expands private properties and
resource gates, binds complete per-root evidence, and repairs the four concrete
arithmetic-policy defects plus discriminator behavior. No cycle-001 receipt is
valid for the regenerated family.

## Audit/remediation cycle 2

The immutable cycle-002 audit subject
`sha256:9535c99af368009a4a8f753c95541d63b5e396555235cc72f74899a660cab237`
reported `not_completed` with findings `OSC-AUD-010` through `OSC-AUD-015`.
All six are `repair-in-place`. Cycle 3 refreshes the complete comparison corpus,
fixes expansion-other accounting, and screens cross-corpus lineage through the
same seven independent artifact scopes used within the family. It replaces
unchecked cell-count products with division guards, validates extreme trim
counts without wrapping, validates every progressive tier before returning,
and caps geometric iteration at one million terms. Focused private tests bind
each counterexample. No cycle-001 or cycle-002 receipt is valid for the cycle-3
subject; only a fresh independent audit of that exact subject may close it.

Cycle-3 subject
`sha256:759cd024f34ac6f861f890638a4c486da180eeaba37d5b6931e4f4c3219f140c`
was invalidated before audit when a concurrent expansion-family regeneration
changed 110 bound comparison roots and introduced one new root. It is preserved
as non-terminal evidence. The next creator subject uses a new append-only cycle
number and a fully refreshed comparison snapshot.

## Audit/remediation cycle 8

The immutable cycle-008 audit subject
`sha256:df24c528f4fe9ef0f3d1c5cd33c6e32722e5f01fa1edfa350624190f352823cb`
reported `not_completed`. It reopened `OSC-AUD-002`, `OSC-AUD-003`, and
`OSC-AUD-010`, and added `OSC-AUD-016` through `OSC-AUD-018`. The owner repair
short-circuits zero-volume boxes before irrelevant products, advances decay
powers only when another event remains, and replaces the bounded-composition
triple loop with a sliding-window dynamic program whose work is proportional
to the documented cell budget. Private assertions now bind the audit's exact
counterexamples plus previously uncovered identity and invalid branches. The
focused evaluator independently reconstructs the exact seven artifact scopes
and reconciles every persisted per-pair, per-dimension decision. All prior
receipts and subjects are stale until complete regeneration, Docker evidence,
and a clean fresh audit.

## Audit/remediation cycle 12

The cycle-012 audit subject
`sha256:af12fadd2f15a9d355228db123f94ecacf262b4d27e10adf4c573cdcdaf8a1a8`
was invalidated by both shared-corpus drift and an auditor protocol violation,
but its independent reference review added binding finding `OSC-AUD-019`.
`progressive-tier-score` now returns the zero-cost identity for zero usage with
an empty tier schedule after validating every supplied tier, and its private
oracle binds that exact counterexample. Complete owner regeneration and fresh
Docker normal/sanitizer/negative evidence are required before a new creator
subject may be audited.

## Non-claims

Passing roots may reach only `local_family_verified`. This curriculum does not
create JSONL rows, select a split, authorize an SFT release or training run, or
claim benchmark uplift.

## Docs Alignment (Remediation Docs Phase)

The model-facing `.docs` follow the official Aider Polyglot C++ conventions.
`.docs/introduction.md` is a `# <Title>` header plus a domain-motivating
narrative about combinatorial counting; it never states the contract or
mentions the evaluation harness. `.docs/instructions.md` keeps the
`# Instructions` header and the complete contract (overflow-before-operation,
rejection budgets, empty/zero identities, determinism), adds a `## Examples`
section with the visible input and its exact expected result, and expresses
the mechanism naturally ("The operation is the <mechanism>: <rule>") with the
substitute constraint kept as "A generic approach based on <substitute> does
not satisfy this contract." The "core mechanism is **...**" scaffold phrasing,
the self-referential "does not satisfy this task", and the harness-speak
"compact enough for a complete whole-file response" are removed. The
generator's focused test asserts this docs shape and rejects meta/audit
vocabulary in both docs files.
