# Cross-Midnight, Fixed-Offset, And Meeting-Intersection Expansion Curriculum

Status: implementation contract for exactly 90 new clean-room local task roots.
The roots are candidate material only; this document does not create SFT rows,
authorize training, or claim benchmark uplift.

## Count-plan binding and evidence

This family implements the complete 90-root cell named “Cross-midnight,
fixed-offset, meeting, and interval intersections” in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`. Before creation,
the owner must inventory both existing trees, exclude every `.state` path, and
reconcile the documented 709-root reverify inventory hash. All new roots must
be written only beneath:

```text
.w8-biayn/data/aider-tasks-expansion-v1/time-date/cross-midnight-offsets-meetings/
```

The official Aider C++ `clock`, `gigasecond`, and `meetup` tasks, together with
all other 23 official C++ roots, are permanent holdouts. This family uses no
benchmark prompt, test, reference, response, retry, or API as an authoring
input.

## Executable family design

The 90 roots are the Cartesian product of ten input transformations and nine
analyses. A root is the exact composition of one transformation and one
analysis; neither stage is optional. This yields 90 distinct mechanism pairs,
not 90 domain labels over one policy switch. The generated reference contains
only its selected pair and no run-time mode dispatch.

### Ten transformations

| Key | Task-ID prefix | Owned input and mechanism | Invalid/boundary rule |
| --- | --- | --- | --- |
| `wrap` | `overnight` | Daily start/end/load records; unwrap one lower end by 1,440 minutes. | Endpoints are 0..1439; equality is invalid; one wrap only. |
| `offset` | `fixed-offset` | Local start/end, fixed UTC offset, and load; subtract offset then floor-normalize. | Offset is -840..840; local ranges may wrap once. |
| `day` | `day-projected` | Local endpoints, day index, and load; project onto day zero or one. | Day is 0 or 1; the unwrapped end must not exceed 2,880. |
| `repeat` | `recurring` | Start, duration, period, repeat count, and load; expand bounded arithmetic occurrences. | Positive fields, at most eight repeats, every end within the two-day horizon. |
| `clip` | `horizon-clipped` | Source interval, private clip interval, and load; intersect each pair. | Both ranges are nonempty; an empty intersection is omitted, not invalid. |
| `buffer` | `buffer-expanded` | Source interval, before/after buffers, and load; dilate asymmetrically. | Buffers are nonnegative and may not cross 0 or 2,880. |
| `participant` | `participant-normalized` | Multiple uniquely identified local windows per participant; normalize to UTC and retain only each participant's nonempty common intersection. | Window IDs are unique, participant IDs/priorities are positive, offsets are bounded, and one participant cannot change priority between windows. |
| `capacity` | `capacity-weighted` | Room identity, interval, and capacity; carry capacity as interval load. | Capacity is positive; ranges are nonempty on 0..2,880. |
| `precedence` | `precedence-shifted` | Interval, earlier-listed predecessor, lag, and load; propagate the predecessor lower bound. | A predecessor is zero or already present; lag is nonnegative; shifted end stays in range. |
| `blackout` | `blackout-subtracted` | Source interval, contained optional blackout, and load; retain zero, one, or two pieces. | The blackout is empty or contained; endpoint-touching pieces preserve half-open semantics. |

### Nine analyses

| Key | Task-ID suffix | Result/API and substantive analysis | Ordering/tie/boundary rule |
| --- | --- | --- | --- |
| `union` | `merged-coverage` | `CoverageReport`; sort and union intervals. | Touching intervals merge; report total minutes and segment count. |
| `peak` | `peak-load` | `PeakReport`; weighted event sweep. | End events precede starts at ties; earliest maximum wins. |
| `exact` | `exact-coverage` | `ExactReport`; difference array and exact-load accumulation. | Exact load is caller supplied and positive; greater load does not count. |
| `slot` | `earliest-quorum-slot` | `SlotReport`; threshold-run scan for a requested duration. | Positive threshold/duration; earliest qualifying run wins. |
| `gap` | `longest-gap` | `GapReport`; clip, union, and scan the complement inside a caller horizon. | Earliest longest gap wins; a horizon is nonempty in 0..2,880. |
| `rooms` | `room-demand` | `RoomReport`; busy/free two-heap interval partitioning. | Touching reuses a room; smallest reusable room wins. |
| `weighted` | `weighted-exposure` | `WeightReport`; integrate event-sweep load in signed 64-bit arithmetic. | Report exact load-time area and maximum load. |
| `order` | `stable-order` | `OrderReport`; sort derived identities by start/end/ID. | All three keys are ascending and deterministic. |
| `conflicts` | `conflict-audit` | `ConflictReport`; enumerate unique positive-overlap identity pairs. | Touching is not overlap; pairs are canonical and sorted. |

## Exact root inventory

For every prefix in the transformation table, materialize these nine suffixes
in this order:

```text
merged-coverage
peak-load
exact-coverage
earliest-quorum-slot
longest-gap
room-demand
weighted-exposure
stable-order
conflict-audit
```

The exact task ID is `<prefix>-<suffix>`. The ten prefixes times nine suffixes
are the complete 90-root retained inventory. Every lineage is
`cross-midnight-offset-meeting/<transform-key>/<analysis-key>/v1`. No root is a
replacement or revision of an existing task.

## Per-root public contract

Each root declares one transformation-specific input struct, one
analysis-specific report struct, and one free C++17 function named
`analyze_<transform-key>_<analysis-key>`. The input vector is borrowed by const
reference and never mutated. Result vectors are owned. Inputs with invalid or
duplicate positive identities return the default `valid=false` report without
partial output. Empty input is valid unless a caller analysis parameter is
invalid. All intervals are half-open.

The exact declarations, examples, normal/invalid behavior, ordering, ties,
overflow behavior, and file order are frozen in the 90 creation contracts
generated under the family’s `.state/contracts/` before reference files are
written. Those contracts are audit inputs and are not prompt-visible.

## Primary core objective

Every reference must implement both selected mechanisms directly. Permitted
incidental facilities are vectors, sets for duplicate-ID validation, arrays,
maps for predecessor lookup, sorting, and priority queues when the selected
analysis requires them. Forbidden substitutes include:

- skipping wrap, day, offset, clipping, buffer, recurrence, precedence, load,
  or blackout transformation;
- applying an analysis directly to untransformed local intervals;
- using one generic run-time policy switch across roots;
- treating half-open endpoints as closed;
- replacing exact-load selection with at-least selection;
- changing earliest to latest, start-order to reverse-order, or stable room
  reuse to arbitrary allocation;
- hard-coding the visible examples or precomputing outputs.

## Tests and negative fixtures

Every root has one visible and one private deterministic executable. Both use
hard-coded expected behavior independent of the emitted C++ reference. The
private executable directly asserts empty-input behavior, field-for-field input
immutability, unique/positive/bounded identities, the 1,000-record limit,
bounded weights and arithmetic, every applicable transformation rule, atomic
default output for every invalid query, reducer-parameter rejection, half-open
behavior, and deterministic tie/order semantics. Every invalid probe snapshots
and compares the exact argument passed to the API. Every root also has an
explicit same-start plus touching fixture and direct valid probes at ID
200,000,000, weight 1,000,000, and exactly 1,000 records.
The clip and participant rows additionally execute valid fixtures whose
transformed result is empty, proving omission without invalid rejection and
proving input immutability on those branches. A generated
`.meta/requirements.json` ledger maps every material contract item to exact
`W8_ASSERT` markers; creator preflight fails if a required marker is absent.
Each root’s coherent false substitute starts from the complete
reference and applies two compiling changes: one transformation-specific fault
and one analysis-specific fault. At least one of the same two tests must reject
the false substitute in normal and fresh ASan/UBSan modes.

## Seven-dimension diversity and clone controls

The owner must read the emitted header, instructions, reference, visible and
private tests, and reference-to-negative edit script. It must compare all
`90 * 89 / 2 = 4,005` unordered root pairs in each of these dimensions:

1. public API;
2. owned state or algorithm;
3. mutation and selection rules;
4. invalid and boundary behavior;
5. reference control flow;
6. deterministic oracle;
7. topic-specific negative fixture.

Every dimension must have distinct normalized evidence and remain below the
recorded near-clone threshold. One aggregate score cannot pass a pair.

The exact production evaluator must also reject three coherent, buildable
controls derived from emitted roots: a domain/identifier rename, a horizon-
constant/policy change, and a descending-start opposite-selection clone. Each
control must pass its own reference behavior tests before it can count as clone
evidence.

## Provenance, contamination, and execution gates

The owner must fail closed on a task-ID collision in any of the three task
trees, semantic-lineage overlap with either existing tree, any official
holdout slug/content near-match, unsafe file roles, prompt leakage, duplicate
prompt/reference hashes, zero test discovery, unequal normal/sanitizer counts,
or a false substitute that passes. Docker verification uses the repository’s
pinned C++ sanity image with `--network none`; it is `docker_sanity`, not a
family-designated locked oracle. When Docker is out of scope, the owner’s
`--verify-host` mode runs the same clean normal and fresh ASan/UBSan reference
build/run semantics on the host toolchain with positive equal discovery counts
and compiled false-substitute rejection for every root and control; it is
`host_verify` evidence, not `docker_sanity` or `locked_oracle` evidence.

The strongest possible status here is `local_family_verified`, and only a
fresh independent audit of the exact post-remediation tree may assign it. No
SFT release, split, JSONL, token/mask evidence, training authorization, or
benchmark-uplift claim follows.
