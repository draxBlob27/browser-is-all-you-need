# Identity, Collision, Reset, And Transactional State Expansion Curriculum

Status: implementation-grade clean-room curriculum for exactly 60 local task
roots. This document does not create SFT rows, authorize training, or claim
benchmark uplift.

## Count-plan binding and output

This family implements the complete 60-root cell named **Identity allocation,
collision handling, reset, and transactional state** in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`.

The owner may write generated task roots only below:

```text
.w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/
  identity-collision-reset-transactions/
```

The 731-root legacy tree and the plan-bound 709-root reverify tree are
read-only inventories. Every ID below is a new root with no parent or
replacement lineage. Rejected roots do not count and must be backfilled by a
new contract rather than renamed.

## Common executable contract

Every root is a C++17 whole-file task with exactly two editable files named
after its slug. Visible instructions define the complete public API, owned
state, normal and invalid behavior, duplicate/absent handling, reset or
transaction boundary, deterministic ordering/ties, and bounded resource
behavior. The prompt contains only documentation and starter files. CMake,
tests, references, provenance, negative fixtures, receipts, and `.state`
artifacts remain private.

Every material requirement has a deterministic visible or private assertion.
The owner emits `.meta/requirements.json` as a machine-checkable seven-clause
trace for every root. Each clause must appear verbatim in the public
instructions. The first clause is a hand-authored operation-by-operation
contract covering constructor domains, formulas, return sentinels, ordering,
capacity, overflow, and atomic state effects for that exact root. Every clause
names stable visible/private assertion ordinals or the executed-negative
discriminator with current artifact hashes. Instructions also contain one normative
public `check(...)` example derived from the public case contract; private test
source remains excluded from the prompt.
Each root owns its advertised state mechanism; a generic map-only registry,
monotonic counter, clear-all reset, best-effort batch, or library transaction
substitute is forbidden unless that container is merely incidental to the
specified mechanism. Each root has a compiling plausible false substitute
which the production tests execute and reject.

## Root inventory

The seven diversity fields are: public API; owned state/algorithm;
mutation/selection rules; invalid/boundary behavior; reference control flow;
deterministic oracle; and topic-specific negative fixture. The compact table
names the core mechanism, distinguishing boundary, and easiest coherent false
substitute. The family specification records the full APIs and tests.

| # | Task ID | Core mechanism | Distinguishing boundary | Compiling false substitute |
|---:|---|---|---|---|
| 1 | `idtx-generation-slot-pool` | slot index plus generation handles | stale released handles never revive | bare reusable slot index |
| 2 | `idtx-monotonic-tombstone-registry` | monotonic IDs with permanent tombstones | reset preserves non-reuse history | counter reset to one |
| 3 | `idtx-block-lease-allocator` | contiguous block leases and coalescing gaps | exact-fit and adjacent release merge | first free scalar IDs |
| 4 | `idtx-worker-epoch-id` | worker/epoch/sequence packed identity | clock regression rejects atomically | global counter |
| 5 | `idtx-hierarchical-scope-id` | parent-scoped child sequences | deleting a scope invalidates descendants | flat name map |
| 6 | `idtx-content-probe-id` | deterministic content digest probing | equal payload is idempotent, digest collision probes | hash overwrite |
| 7 | `idtx-dense-handle-table` | dense storage with sparse handle indirection | swap-remove repairs moved indirection | vector position as handle |
| 8 | `idtx-interval-id-leases` | disjoint interval lease index | partial release splits one lease | scalar free list |
| 9 | `idtx-namespace-quota-ids` | per-namespace quotas and local sequences | failed quota allocation consumes nothing | one global quota |
| 10 | `idtx-epoch-sequence-book` | epoch-keyed sequence books | advancing epoch retires old tokens | sequence-only token |
| 11 | `idtx-partition-stride-ids` | disjoint arithmetic progressions | partition reconfiguration rejects live overlap | shared counter |
| 12 | `idtx-capability-token-pool` | opaque capability tokens with revocation | revoked token cannot be reissued in epoch | payload lookup as authority |
| 13 | `idtx-reversible-id-stack` | LIFO allocation checkpoints | rollback restores allocation frontier and release set | counter decrement |
| 14 | `idtx-reserved-band-allocator` | ordered reserved numeric bands | cross-band request never spills silently | unrestricted first fit |
| 15 | `idtx-alias-component-ids` | union-find canonical identity | canonical representative follows deterministic rank tie | flat alias table |
| 16 | `idtx-robin-hood-key-registry` | Robin Hood probe-distance table | erase uses backward shift | linear probe without distance repair |
| 17 | `idtx-cuckoo-route-registry` | two-home displacement with bounded relocation | failed cycle leaves both tables unchanged | overwrite second home |
| 18 | `idtx-quadratic-ticket-table` | quadratic probe sequence | duplicate and full-cycle detection are distinct | linear probing |
| 19 | `idtx-hopscotch-neighborhood-index` | neighborhood bitmap relocation | insertion outside neighborhood relocates chain | unbounded linear scan |
| 20 | `idtx-double-hash-session-table` | coprime secondary-step probing | invalid zero step is normalized deterministically | primary hash only |
| 21 | `idtx-shortest-prefix-aliases` | shortest unique prefix allocation | deletion can shorten surviving aliases | fixed prefix length |
| 22 | `idtx-checksum-bucket-ledger` | checksum buckets plus full-key discrimination | checksum collision preserves insertion order | checksum as identity |
| 23 | `idtx-coordinate-cell-reservations` | 2-D neighborhood collision search | Manhattan distance then row/column tie | row-major first free |
| 24 | `idtx-interval-code-bookings` | interval overlap index | touching half-open bookings do not collide | closed-interval overlap |
| 25 | `idtx-dependency-name-resolver` | dependency-DAG name reservation | cycle-producing alias transaction rolls back | independent map inserts |
| 26 | `idtx-priority-slot-displacement` | priority eviction with stable arrival tie | rejected lower priority leaves slot/order unchanged | last writer wins |
| 27 | `idtx-canonical-slug-registry` | canonicalization plus suffix allocation | explicit suffixes reserve their numeric lane | append count blindly |
| 28 | `idtx-batch-matching-identities` | bipartite augmenting-path assignment | all-or-none batch matching | greedy per request |
| 29 | `idtx-displacement-chain-names` | ordered displacement chain | bounded chain failure reverses prior moves | partial chain commit |
| 30 | `idtx-collision-journal-replay` | collision decisions recorded for replay | divergent replay input is rejected without mutation | recompute from current state |
| 31 | `idtx-generation-stamped-counters` | generation-tagged lazy counters | reset is O(1) and stale cells read zero | clear every cell |
| 32 | `idtx-lazy-epoch-membership` | epoch tags on membership slots | epoch wrap performs safe material reset | tag wrap without clearing |
| 33 | `idtx-snapshot-state-restore` | immutable snapshots and exact restore | restoring unknown snapshot is a no-op failure | reset to empty |
| 34 | `idtx-delta-checkpoint-rewind` | inverse delta log checkpoints | nested rewind applies inverses in reverse order | copy last value only |
| 35 | `idtx-namespace-selective-reset` | hierarchical namespace epochs | subtree reset preserves siblings | global clear |
| 36 | `idtx-expiry-lease-reset` | deadline heap with generation guards | stale heap entry cannot expire renewed lease | deadline-only heap |
| 37 | `idtx-cohort-barrier-reset` | generation barrier cohorts | duplicate arrival rejected; last arrival advances generation | count-only barrier |
| 38 | `idtx-rolling-window-reset` | timestamp window with reset markers | decreasing time rejects without eviction | clear on every gap |
| 39 | `idtx-recovery-fsm-reset` | explicit fault/recovery finite-state machine | reset needs ordered acknowledgement sequence | reset from any state |
| 40 | `idtx-sequence-gap-resync` | contiguous sequence tracker and buffered gaps | resync discards only pre-baseline packets | clear all buffered packets |
| 41 | `idtx-tombstone-compaction-reset` | open-address table compaction epoch | compaction preserves lookup and iteration order | clear tombstones in place |
| 42 | `idtx-quota-period-reset` | boundary-aligned quota epochs | exact boundary belongs to new period | elapsed-duration reset |
| 43 | `idtx-deterministic-seed-reset` | replayable PRNG state checkpoint | seed reset reproduces stream and draw count | reseed without count reset |
| 44 | `idtx-hierarchy-cascade-reset` | dependency-ordered cascade reset | children reset before parent, shared child once | preorder clear |
| 45 | `idtx-rollback-union-find-reset` | union-find without path compression plus rollback stack | rollback to token restores component count | rebuild from surviving edges |
| 46 | `idtx-undo-log-kv` | before-image undo log | abort restores absent versus present values | clear writes on abort |
| 47 | `idtx-write-ahead-ledger` | prepared WAL then durable apply | recovery replays committed records only | apply before journal |
| 48 | `idtx-mvcc-snapshot-store` | version chains and snapshot reads | reader never sees later commit | latest-value map |
| 49 | `idtx-optimistic-version-batch` | read-version validation and atomic write set | one conflict aborts all writes | validate only written keys |
| 50 | `idtx-lock-order-transfer` | deterministic lock-order planning | self-transfer and insufficient balance consume no locks | input-order locking |
| 51 | `idtx-two-phase-resource-commit` | prepare votes and commit decision | any no-vote aborts every prepared participant | commit yes-voters |
| 52 | `idtx-savepoint-stack-store` | nested savepoint undo positions | release merges scope; rollback retains outer transaction | snapshot per savepoint |
| 53 | `idtx-nested-transaction-map` | child overlays merged into parent | child abort exposes parent value | child writes base directly |
| 54 | `idtx-escrow-counter-transaction` | partitioned escrow rights | transfer rights before decrement; no global overspend | global counter check |
| 55 | `idtx-atomic-batch-rename` | rename graph with temporary-cycle handling | duplicate destination aborts complete batch | sequential rename |
| 56 | `idtx-double-entry-transfer` | balanced debit/credit journal | every committed transaction sums to zero | mutate balances without entries |
| 57 | `idtx-inventory-reservation-commit` | reserve/commit/release quantities | failed multi-item reservation consumes nothing | reserve available prefix |
| 58 | `idtx-dependency-dag-transaction` | staged DAG edit with cycle validation | cycle abort restores graph and revision | add edges until cycle found |
| 59 | `idtx-idempotency-key-ledger` | request-key result memoization | same key/different payload is conflict | key returns first result silently |
| 60 | `idtx-saga-compensation-runner` | forward steps with reverse compensations | first failure compensates completed steps exactly once | stop without compensation |

## Family and contamination gates

The owner must reserve all 60 IDs against all three task trees before writing.
It must compare every one of the 1,770 unordered retained pairs in all seven
dimensions conjunctively from emitted docs, API, reference, tests, and negative
fixture. Raw IDs, unique nouns, literals, declared profile labels, or hashes do
not count as differences. Independent focused tests must recompute the exact
pair and dimension decisions.

The owner materializes three coherent controls from one emitted root: a full
filename/type/method/field/variable/prose domain rename with no alias metadata,
constants-or-policy-only change, and opposite-end
selection. Each control must change the intended files, remain role-correct,
compile, pass its self-consistent behavior oracle in clean normal and fresh
ASan/UBSan modes, and be rejected by the production pair evaluator.

All 60 candidates are screened against normalized contracts, APIs, references,
tests, and oracle logic in both existing trees and against the exact 26
official C++ holdouts. A semantic near-match is rejected rather than renamed.

## Completion evidence

Creator preflight requires generator-owned regeneration, prompt and response
boundary validation, unique prompt/reference hashes, all 60 compiled negative
fixtures rejected by executed tests, the 1,770-pair screen, the three coherent
clone controls, cross-tree and benchmark screens, and a receipt binding the
current owner/tree/policy/environment hashes. Mandatory runtime evidence is a
network-disabled Docker run in the repository-pinned C++ sanity image with
positive equal normal and fresh ASan/UBSan discovery for every root and
control. The receipt points to a 186-row ledger binding each task/control ID,
root/reference/test/negative hashes, exact configure/build/discovery/execution
commands, positive discovery count, outcome, and negative-rejecting test. The
owner must reconcile those rows and promote every root's primary objective
before audit handoff. It is `docker_sanity`, not a family-designated locked
oracle. When Docker is unavailable or a campaign gate is host verify only, the
owner's `--verify-host` mode runs the identical per-root contract on the host
toolchain and writes `.state/host-verify.json` (evidence class `host_verify`,
strongest status `host_verify_passed_pending_independent_audit`); host
evidence never substitutes for the mandatory Docker sanity run required by
`local_family_verified`.

Independent audit cycle 01 is immutable under `.state/audits/` and identified
three blocker findings covering public-contract completeness, rename-robust
semantic evidence, and row-auditable runtime receipts. The corresponding
`.state/remedy/` records are preserved across generator-owned regeneration;
they do not count as candidate roots or alter the exact 60-root inventory.
Cycle 02 closed the diversity finding and retained the stable prompt-contract
and control-content-binding findings. The next regeneration must bind nonempty
complete hashes for controls relative to their own roots even though they live
under `.state`.

Only a clean independent audit of the exact final regenerated tree may assign
`local_family_verified`. No SFT release, export, training authorization, or
benchmark-uplift claim follows.
