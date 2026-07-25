# Producer-Consumer Behavior Structures: 60-Root Expansion Curriculum

Status: executable clean-room expansion contract. The 60 roots described here
are local candidate material only. They do not create SFT rows, authorize
training, or claim benchmark uplift.

## Count-plan cell and output boundary

This curriculum implements the complete 60-root
`Producer-consumer synchronization, closure, and backpressure` cell in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`.

The owner may write only beneath:

```text
.w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/producer-consumer-behavior-structures/
```

The legacy and reverify trees are immutable comparison inputs. In particular,
the existing producer-consumer ring roots are reserved. This family does not
recreate a ring, circular buffer, renamed queue, or any existing task ID.

## Shared task contract

Each root is a deterministic C++17 state-machine task. Its public API models
producer admission, consumer release, and lifecycle signals without timing
sleeps. The model replaces exactly `<task-id>.h` and `<task-id>.cpp`. The
visible contract defines normal, invalid, duplicate, absent, full, closure,
ordering, and tie behavior. Hidden tests remain private.

The core objective is the task-specific coordination protocol. `std::queue`,
`std::deque`, and queue adaptors are forbidden as the substantive mechanism.
Incidental `std::vector`, `std::map`, and `std::set` storage is allowed only
when the protocol's explicit admission, ownership, release, rollback, and
closure transitions remain implemented by the candidate.

Roots whose mechanism names retention — consumer cursors, acknowledgement
quorums, branch barriers, replay windows, lag budgets, tombstone
confirmations, durable commit frontiers, or terminal ledgers — must implement
that reclamation executably: a released record stays in the retained view
until the named eligibility (minimum cursor, quorum mask, barrier mask,
contiguous frontier, or compaction) holds, and the model oracle asserts the
retained-until-eligible state together with per-root cursor, acknowledgement,
frontier, committed, or terminal snapshot fields. Every other root erases
exactly the selected record on release.

Every root has a coherent compiled false implementation that violates its
specific protocol while preserving the public API. The false substitute varies
by root across three named invariant violations: admission or release
eligibility-gate inversion, documented release-payload substitution, and
documented release-order reversal; a single shared mutation pattern across the
family is not acceptable. Admission and release eligibility are gated on the
root's owned protocol state before any mutation or selection; tautological
predicates that hold on every normal state are forbidden. The visible, hidden, and
model tests must reject it. Normal and fresh ASan/UBSan verification must
discover the same positive test count in the pinned network-disabled C++
sanity image.

## Root inventory

The six groups are presentation aids, not reusable policy templates. Every row
has a distinct public operation set, owned state, admission/mutation rules,
invalid and boundary behavior, release ordering and ties, deterministic model
oracle, and executable negative fixture.

### Admission and backpressure

| Task ID | Core mechanism |
| --- | --- |
| `credit-window-dispatcher` | Per-producer credits are reserved on admission and returned only by matching completion. |
| `deficit-fair-ingress` | Signed source deficits accumulate quanta and gate variable-cost work. |
| `reservation-ticket-gate` | Monotonic tickets reserve bounded positions and cancellation compacts only unclaimed tickets. |
| `byte-budget-mailbox` | Variable-size messages consume byte budget rather than item slots, with exact refund accounting. |
| `deadline-shed-buffer` | Full admission evicts only the least urgent pending item under stable admission ties. |
| `keyed-replacement-inbox` | A pending key is replaced in place and never receives a second ordering position. |
| `burst-token-admitter` | Producer-specific burst tokens refill only from explicit epochs and cannot be borrowed. |
| `dependency-ready-staging` | Items remain staged until all named prerequisite tokens have arrived. |
| `tenant-waterline-gate` | Global high/low waterlines pause and resume tenants without losing per-tenant FIFO state. |
| `quorum-capacity-admitter` | Admission reserves capacity across a declared consumer quorum and rolls back atomically on shortage. |

### Closure and lifecycle

| Task ID | Core mechanism |
| --- | --- |
| `half-close-duplex-handoff` | Producer and consumer halves close independently; accepted work drains before terminal completion. |
| `phased-drain-controller` | Open, sealing, draining, and stopped phases have distinct legal transitions. |
| `poison-free-stop-barrier` | Explicit producer retirement replaces sentinel payloads and releases stop only after all retire. |
| `producer-lease-shutdown` | Live producer leases delay closure and expired leases relinquish only their owned reservations. |
| `epoch-sealed-inbox` | A sealed epoch rejects late writes while later epochs may stage independently. |
| `abortable-batch-handoff` | Abort removes an uncommitted batch atomically while committed batches remain drainable. |
| `reopen-generation-mailbox` | Reopening creates a new generation; stale handles cannot publish or consume. |
| `cascading-stage-closure` | Downstream closure propagates upstream only after each intermediate stage drains. |
| `orphan-reclaim-handoff` | Owner retirement reclaims only unacknowledged work and preserves completed ownership history. |
| `terminal-error-broadcast` | One terminal error is observed once by every registered consumer after its accepted prefix. |

### Multi-consumer retention

| Task ID | Core mechanism |
| --- | --- |
| `consumer-cursor-retention` | Work remains retained until all active consumer cursors pass it. |
| `quorum-ack-reclaimer` | An item is reclaimed after a fixed acknowledgement quorum, independent of laggards. |
| `lag-budget-fanout` | Consumers exceeding a lag budget lose only the skipped prefix and receive an exact gap count. |
| `snapshot-subscriber-mailbox` | Subscribers begin from an immutable registration snapshot followed by live changes. |
| `topic-mask-fanout` | Per-consumer topic masks determine delivery while global admission order is preserved. |
| `durable-offset-tracker` | Committed offsets advance contiguously despite out-of-order acknowledgements. |
| `slow-reader-evictor` | A deterministic lag score evicts one slow reader and immediately recomputes reclaimability. |
| `replay-window-handoff` | Rejoining consumers may replay a bounded acknowledged suffix without blocking reclamation. |
| `branch-barrier-delivery` | A branch group releases the next item only after every branch reaches its current barrier. |
| `selective-redelivery-table` | Negative acknowledgements schedule only named consumers for redelivery. |

### Deterministic scheduling

| Task ID | Core mechanism |
| --- | --- |
| `deficit-round-robin-mailbox` | Per-lane deficits and costs choose a deterministic fair drain sequence. |
| `aging-fair-consumer-pool` | Waiting age promotes consumers ahead of later higher-weight consumers. |
| `weighted-source-drainer` | A finite weighted service schedule resumes exactly where the prior drain stopped. |
| `deadline-slack-dispatcher` | Minimum slack wins, then smaller sequence, without recomputing historical admission time. |
| `producer-turnstile` | Active producers receive cyclic turns and skipped inactive producers do not consume turns. |
| `locality-batch-scheduler` | Same-affinity work batches up to a limit before deterministic cross-affinity rotation. |
| `anti-starvation-lane-picker` | Consecutive priority picks are capped and force the oldest lower lane. |
| `dependency-topology-dispatcher` | Ready work releases in stable topological order with cycle rejection. |
| `work-steal-lease-board` | Idle consumers steal the oldest unleased task and leases return to their origin on expiry. |
| `cohort-fair-release` | Complete cohorts rotate by cohort age while preserving member order. |

### Acknowledgement and ownership

| Task ID | Core mechanism |
| --- | --- |
| `ack-timeout-retry-ledger` | Explicit logical ticks expire acknowledgements into bounded retry attempts. |
| `idempotency-key-handoff` | Duplicate keys share one terminal result without creating duplicate pending work. |
| `two-phase-delivery-slot` | Prepared ownership becomes visible only after commit; rollback restores the slot. |
| `lease-renewal-queue` | Only the current lease token may renew, complete, or abandon an item. |
| `nack-classification-router` | Retryable, terminal, and reroute negative acknowledgements have disjoint transitions. |
| `exactly-once-commit-table` | Delivery and durable commit are separate; replay suppresses committed identifiers. |
| `deduplicating-replay-ledger` | A bounded terminal ledger suppresses retries until explicit compaction. |
| `ownership-transfer-token` | Transfer invalidates the old owner token before the new owner can complete. |
| `tombstone-confirmation-log` | Deletion tombstones persist until every required consumer confirms them. |
| `compensation-workflow-inbox` | Failed terminal work emits exactly one compensating item with linked lineage. |

### Batch, frontier, and release structures

| Task ID | Core mechanism |
| --- | --- |
| `watermark-join-coordinator` | Inputs release only below the minimum declared producer watermark. |
| `dual-threshold-batch-assembler` | A batch seals on count or accumulated weight, whichever explicit event crosses first. |
| `partition-fence-merger` | Per-partition prefixes merge only through the greatest common fence. |
| `sequence-gap-tolerance-gate` | A bounded gap budget releases sequence prefixes and reports deterministic skips. |
| `aggregate-delta-flusher` | Keyed deltas coalesce until a flush barrier emits stable first-key order. |
| `transactional-microbatch-log` | Begin/append/commit/rollback isolates batches and assigns commit order atomically. |
| `checksum-sealed-workset` | A workset becomes consumable only when its declared count and checksum both match. |
| `affinity-cohort-assembler` | Items form stable affinity cohorts with an explicit incomplete-cohort policy. |
| `causal-frontier-emitter` | Vector-frontier dominance gates release and concurrent ties use admission order. |
| `monotonic-version-release` | Per-key versions release contiguous updates and reject stale or conflicting revisions. |

## Seven-dimension and clone gates

The production evaluator reads emitted docs, headers, references, visible and
hidden tests, and negative fixtures. It compares all `60 * 59 / 2 = 1,770`
unordered pairs. Every pair must differ materially in each of these
dimensions, and each dimension is judged on two aspects: executable topology
(shingles over an identifier-collapsed structural token stream) and contract
prose (mechanism, state model, and contract content words with task-derived
identifiers stripped). A pair passes a dimension when either aspect differs
beyond the 0.94 threshold; a pair similar on both aspects is a clone even
under different names, so identifier naming never counts as diversity:

1. public API;
2. owned state;
3. coordination algorithm and control flow;
4. mutation and release rules;
5. invalid, duplicate, absent, and boundary behavior;
6. ordering and tie behavior; and
7. deterministic oracle plus topic-specific false substitute.

The focused tests independently inspect every per-dimension decision. They
also materialize three coherent controls from an emitted root: a complete
domain/identifier rename, a public policy-constant change with matching tests,
and an opposite-end release implementation with matching expected behavior.
Each control must change files, build and pass its own behavior tests, and then
be rejected by the exact production family evaluator because it shares at
least one substantive dimension with its parent.

## Provenance and non-claims

All contracts, code, and tests are newly authored in this repository from the
count-plan capability statement. Official Aider prompts, tests, references,
model responses, and retry histories are permanent holdouts and are not
creation inputs. Completion is at most `local_family_verified`; it is not SFT
release, training authorization, or benchmark-uplift evidence.
