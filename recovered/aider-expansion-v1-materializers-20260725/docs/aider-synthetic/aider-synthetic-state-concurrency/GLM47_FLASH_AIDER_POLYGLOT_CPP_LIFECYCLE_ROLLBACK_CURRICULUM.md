# GLM-4.7-Flash C++ Lifecycle And Rollback Curriculum

Status: executable clean-room curriculum for 70 local expansion candidates.
It is not an SFT release, training authorization, or benchmark-uplift claim.

## Count-plan cell and output boundary

This family implements the binding 70-root cell `State/concurrency -> Lifecycle
state machines, invalid transitions, and rollback` in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`.

The owner may materialize only beneath:

```text
.w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/lifecycle-rollback/
```

Both legacy generated trees are read-only collision and semantic-screen inputs.
No root in this family has an ancestor or replacement relation: every retained
root records `lineage: new-root` and clean-room repository authorship.

## Learning objective

Each task combines one rollback protocol with one lifecycle topology. The
rollback protocol determines how pre-transaction state is preserved and
restored. The topology determines the legal transitions and the state that
those transitions own. A root is correct only when a valid batch commits in
order and the first invalid transition restores the exact pre-batch observable
state.

The matrix is deliberately compositional, not a domain-renaming exercise. A
pair sharing a topology still uses different rollback storage, commit flow,
and failure unwinding. A pair sharing a rollback protocol still owns different
state, transition guards, observable ordering, and trace oracle. The generator
must emit only the fields and operations needed by the selected combination.

## Exact 70-root inventory

| Rollback protocol | Linear guarded | Branch approval | Cyclic retry | Fork/join | Keyed instances | Dependency graph | Quota reservation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Atomic snapshot | `snapshot-linear-lifecycle` | `snapshot-branch-lifecycle` | `snapshot-cyclic-lifecycle` | `snapshot-fork-join-lifecycle` | `snapshot-keyed-lifecycle` | `snapshot-dependency-lifecycle` | `snapshot-quota-lifecycle` |
| Inverse compensation | `inverse-linear-lifecycle` | `inverse-branch-lifecycle` | `inverse-cyclic-lifecycle` | `inverse-fork-join-lifecycle` | `inverse-keyed-lifecycle` | `inverse-dependency-lifecycle` | `inverse-quota-lifecycle` |
| Named savepoint | `savepoint-linear-lifecycle` | `savepoint-branch-lifecycle` | `savepoint-cyclic-lifecycle` | `savepoint-fork-join-lifecycle` | `savepoint-keyed-lifecycle` | `savepoint-dependency-lifecycle` | `savepoint-quota-lifecycle` |
| Nested frames | `nested-linear-lifecycle` | `nested-branch-lifecycle` | `nested-cyclic-lifecycle` | `nested-fork-join-lifecycle` | `nested-keyed-lifecycle` | `nested-dependency-lifecycle` | `nested-quota-lifecycle` |
| Write-ahead validation | `wal-linear-lifecycle` | `wal-branch-lifecycle` | `wal-cyclic-lifecycle` | `wal-fork-join-lifecycle` | `wal-keyed-lifecycle` | `wal-dependency-lifecycle` | `wal-quota-lifecycle` |
| Copy-on-write shadow | `cow-linear-lifecycle` | `cow-branch-lifecycle` | `cow-cyclic-lifecycle` | `cow-fork-join-lifecycle` | `cow-keyed-lifecycle` | `cow-dependency-lifecycle` | `cow-quota-lifecycle` |
| Persistent version chain | `version-linear-lifecycle` | `version-branch-lifecycle` | `version-cyclic-lifecycle` | `version-fork-join-lifecycle` | `version-keyed-lifecycle` | `version-dependency-lifecycle` | `version-quota-lifecycle` |
| Field undo log | `undo-linear-lifecycle` | `undo-branch-lifecycle` | `undo-cyclic-lifecycle` | `undo-fork-join-lifecycle` | `undo-keyed-lifecycle` | `undo-dependency-lifecycle` | `undo-quota-lifecycle` |
| Saga compensation stack | `saga-linear-lifecycle` | `saga-branch-lifecycle` | `saga-cyclic-lifecycle` | `saga-fork-join-lifecycle` | `saga-keyed-lifecycle` | `saga-dependency-lifecycle` | `saga-quota-lifecycle` |
| Epoch checkpoint | `epoch-linear-lifecycle` | `epoch-branch-lifecycle` | `epoch-cyclic-lifecycle` | `epoch-fork-join-lifecycle` | `epoch-keyed-lifecycle` | `epoch-dependency-lifecycle` | `epoch-quota-lifecycle` |

## Rollback protocol contracts

1. **Atomic snapshot** copies the exact owned topology state once before the
   batch and restores that copy on failure. No partial history survives.
2. **Inverse compensation** records one inverse record after each successful
   event and applies inverse records in reverse order on failure.
3. **Named savepoint** creates a monotonically numbered savepoint, applies the
   batch, and rolls back to that named savepoint on failure; a consumed token
   is absent afterward.
4. **Nested frames** pushes a transaction frame containing the entry state;
   success merges the frame and failure pops and restores only the innermost
   frame.
5. **Write-ahead validation** appends events to a private journal, replays the
   journal against validation state, and mutates live state only after the full
   replay succeeds.
6. **Copy-on-write shadow** clones the live topology object, applies events to
   the shadow, and swaps the shadow into live state only on success.
7. **Persistent version chain** appends an immutable observable version after
   every successful event and truncates the chain back to its entry version on
   failure.
8. **Field undo log** records the old value of each field immediately before
   mutation and restores those field records in reverse order on failure.
9. **Saga compensation stack** emits a topology-specific compensating action
   for every accepted event and executes the compensations in reverse order if
   a later event fails.
10. **Epoch checkpoint** binds an entry snapshot to the current generation;
    failure restores it and advances the generation so stale checkpoint tokens
    cannot be reused.

## Lifecycle topology contracts

1. **Linear guarded** owns one phase in `[0,3]`; action `n` is legal only when
   `n == phase + 1`. Completion is terminal and duplicates are invalid.
2. **Branch approval** accepts `open` only from dormant, then exactly one of
   positive-value approval or negative-value rejection. Both terminal branches
   reject all later events and zero is invalid.
3. **Cyclic retry** accepts `start -> fail -> retry` in order; retry returns to
   start and increments a bounded retry count. Wrong order or a fourth retry is
   invalid.
4. **Fork/join** accepts each worker key `0,1,2` once, in any order, and permits
   join only after all three arrived. Duplicate/out-of-range arrivals and early
   join are invalid.
5. **Keyed instances** creates a positive key, advances it once, then closes
   it. Duplicate creation, absent advance/close, and changes after close are
   invalid. Observation is ascending by key.
6. **Dependency graph** activates nodes `0..3`; node 1 and 2 require node 0,
   and node 3 requires both 1 and 2. Duplicate, out-of-range, or unmet
   dependency activation is invalid.
7. **Quota reservation** owns ten units and per-key reservations. Reserve needs
   a positive unique key and positive available amount; commit needs an open
   reservation; release returns an open reservation. Missing, duplicate,
   non-positive, and over-capacity operations are invalid.

## Public surface and observable state

Every root uses its slug for the editable `<slug>.h` and `<slug>.cpp` files.
The header declares a root-specific namespace, `Event`, `View`, and `Machine`.
`Machine::apply_batch(const std::vector<Event>&)` is the common transaction
entrypoint and `Machine::view()` returns the complete deterministic observable
state. Each rollback protocol adds its own public evidence method (for example
`savepoint_count`, `version_count`, or `generation`) and each topology adds its
own query (for example `phase`, `arrivals`, `instances`, `active_nodes`, or
`available`). These overlays make every composed API structurally distinct.

`apply_batch({})` succeeds without changing state. An invalid event returns
`false`; the complete topology `View` and topology queries equal their entry
values. Protocol receipts are deliberately separate: snapshot increments its
restore receipt once; inverse and saga increment once per accepted-prefix event
and never for the rejected event; savepoint allocation and epoch generation are
monotone even though their live records are consumed. Temporary frame, journal,
undo, and compensation collections are empty at return. Integer arithmetic is
bounded to the documented small ranges.

## Tests and false substitutes

Each root has visible tests for a valid transition and an atomic failure, plus
private deterministic tests for empty input, duplicates, absent state,
boundaries, ordering, topology completion, protocol-specific evidence, and a
fixed 64-event mixed trace checked after every operation against a separately
implemented vector/map/scalar model. The private oracle is not a repeated or
renamed visible scenario.

Each root also contains a compiled `.meta/negative.cpp`. It applies events
directly and returns on the first invalid event without invoking the selected
rollback protocol. It must compile with the exact strict flags and be rejected
by the same visible/private tests. A compile failure is not negative evidence.

## Diversity and clone controls

The owner compares all `70 * 69 / 2 = 2,415` unordered pairs over these seven
separate emitted-artifact dimensions. Decisions use normalized role-scoped
artifact shingles and executable contract witnesses only; provenance semantic
descriptors and matrix coordinates are excluded from the signal:

1. public API;
2. owned state or algorithm;
3. mutation and selection rules;
4. invalid and boundary behavior;
5. reference control flow;
6. deterministic oracle;
7. topic-specific negative fixture.

Every decision must cite nonempty witnesses from docs, header, reference, and
tests. The screen normalizes identifiers, literals, domain nouns, and endpoint
direction. It must reject coherent, buildable controls derived from an emitted
root for domain/identifier rename, constants/policy-only change, and
opposite-end selection. Controls live only below family `.state/controls/` and
never count as tasks. The opposite-end control must be a genuine descending
keyed observation with matching docs, reference, visible/private expectations,
and an executed two-key discriminator; an equivalent emptiness check is not a
valid control. Endpoint-direction normalization must still classify that
coherent behavioral variant as a prohibited family clone.

## Provenance and non-claims

The contracts, implementation, and tests are newly authored in this repository
under the repository's license. The permanent 26-root Aider C++ holdout and
both existing generated trees are comparison inputs only. Prompts expose only
documentation and the two declared starter files. References, tests, CMake,
provenance, screens, receipts, and controls remain private.

Local completion can reach only `local_family_verified` after a current
network-disabled Docker normal/fresh-ASan-UBSan receipt and a clean fresh audit.
It creates no JSONL, split, release, training permission, or uplift evidence.
