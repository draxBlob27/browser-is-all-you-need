# Regions And Mazes Expansion Curriculum

Status: implementation contract for 30 clean-room local candidates in the
2,500-root expansion. Completion is bounded by `local_family_verified`; this
document does not authorize JSONL, a dataset release, training, or uplift.

## Count-plan binding and lineage

This family fills exactly the 30-root cell “Ownership, regions, flood behavior,
mazes, and reachability” in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`. Every task has
lineage `new-root` and must materialize only below
`.w8-biayn/data/aider-tasks-expansion-v1/text-grid-logic/regions-mazes/`.
The legacy and reverify trees are immutable comparison inputs. In particular,
this family does not recreate the existing flood-fill, grid-ownership-mapping,
or maze-to-graph contracts.

## Shared public boundary

Each root owns a task-named header/source pair and one task-specific free
function in namespace `regions_mazes`. Inputs are rectangular, non-empty grids
with at most 32 rows and 32 columns. Region tasks document their exact cell
alphabet. Maze tasks use `#` as a wall, `.` as open space, and exactly one each
of `S` and `G`, plus only the extra symbols named by that contract. Invalid
shape, alphabet, marker count, parameter, or duplicate semantic marker returns
`std::nullopt`; valid empty-result cases return an engaged empty vector.

The output is an integer vector whose task-specific encoding is completely
defined in visible instructions. Coordinates are row-major, represented as
`row * width + column`. Ties use the stated row-major or direction order.

## Root inventory

| Task ID | Direct mechanism | Output and distinguishing boundary |
| --- | --- | --- |
| `scanline-span-ledger` | maximal horizontal run scan | row/start/length triples; ragged input invalid |
| `column-transition-ledger` | vertical transition scan | column/row/from/to quadruples over binary cells |
| `component-area-multiset` | queue-based four-neighbor labelling | sorted component areas; diagonal contact is separate |
| `component-perimeter-ledger` | component flood with exposed-edge accounting | row-major seed/perimeter pairs |
| `component-bounding-boxes` | component flood with min/max coordinate state | seed/min-row/min-col/max-row/max-col records |
| `enclosed-void-census` | boundary-background flood followed by hole flood | sorted enclosed-hole areas |
| `boundary-void-frontier` | multi-source boundary-background traversal | per-distance-layer counts for exterior void only |
| `erosion-layer-histogram` | simultaneous four-neighbor peeling | land removals per erosion round |
| `interior-distance-ridges` | land-only boundary distance transform | sorted ridge cell/distance pairs |
| `orthogonal-corner-census` | local 2x2 convex/concave corner accounting | one global convex/concave pair |
| `translation-shape-classes` | normalized coordinate-signature grouping | sorted class multiplicities; rotations remain different |
| `dihedral-shape-classes` | eight-transform canonical coordinate signature | sorted class multiplicities; rotations/reflections merge |
| `threshold-activation-curve` | descending digit activation with DSU unions | threshold/component-count pairs from 9 through 0 |
| `label-contact-lengths` | unlike-label shared-edge aggregation | code-ordered label-code/label-code/contact triples |
| `region-euler-ledger` | component and enclosed-background accounting | land-components/holes/Euler triple |
| `reachable-cell-bfs` | four-neighbor breadth-first traversal | row-major reachable cells from `S` |
| `shortest-route-length` | unweighted BFS | one shortest distance or engaged empty result |
| `shortest-route-count` | BFS distance plus path-count accumulation | distance/count-mod-1,000,003 pair |
| `lexicographic-route-codes` | BFS with predecessor reconstruction | direction codes in `U,L,R,D` priority |
| `shortest-layer-widths` | goal-bounded BFS layer census | reachable counts for layers 0 through goal distance |
| `mandatory-shortest-cells` | forward/reverse distance and arbitrary-precision path-count product | exact-total-overflow flag then row-major cells on every shortest route |
| `dead-end-pruning-rounds` | simultaneous degree-one queue peeling | cells removed per round, preserving `S` and `G` |
| `minimum-wall-breaks` | zero-one BFS | minimum number of entered wall cells |
| `wall-budget-distance` | product-state BFS by used breaks | shortest steps with at most `parameter` breaks |
| `widest-clearance-route` | wall-distance transform plus max-min path | maximum achievable minimum wall clearance |
| `alternating-parity-route` | parity-expanded BFS | shortest route alternating horizontal/vertical moves |
| `right-hand-patrol-cycle` | deterministic orientation automaton | preperiod/cycle-length or exit-step/zero pair |
| `paired-agent-swap-distance` | collision-free product-state BFS | minimum synchronous swaps without vertex/edge collision |
| `key-door-state-route` | position/key-mask BFS | shortest route with `a`/`A` and `b`/`B` constraints |
| `portal-once-route` | BFS with one-use paired digit portal state | shortest route using each digit pair at most once |

## Core implementation and false substitutes

The generator must emit only the direct mechanism named above; it may use
incidental vectors, queues, maps, sets, and disjoint-set arrays, but no generic
runtime mode switch or precomputed answer. Each root has an independent Python
oracle that produces literal visible and hidden expected outputs. The emitted
negative source is coherent and strictly buildable: region negatives replace
the specified result with a task-specific neighboring region statistic, while
maze negatives use a task-specific shortcut such as Manhattan distance,
ordinary reachability, ignored state, or greedy motion. Production tests must
execute and reject every negative.

## Diversity and adversarial clones

The owner compares all 435 unordered retained pairs separately over these
seven dimensions, derived from emitted docs, API, reference control flow,
visible/private tests, and negative source: public API; owned state/algorithm;
mutation/selection rules; invalid/boundary behavior; reference control flow;
deterministic oracle; topic-negative fixture. Every decision is conjunctive.

The owner also materializes three coherent controls from
`mandatory-shortest-cells`: a domain/identifier rename, a constants/policy-only
revision, and an opposite-end tie-selection revision. Each control must change
files, compile, and pass its internally consistent behavior tests, while the
exact production diversity evaluator rejects it as a clone in all seven
dimensions. Focused tests independently inspect pair counts, dimension keys,
per-dimension decisions, changed-file evidence, and control rejection.

Provenance labels are never diversity evidence. The rename control coherently
changes the public task, file, and function identity; the policy control changes
the accepted size limit and boundary assertions; and the opposite-end control
changes direction priority, encoding, reference, and expected results. The
control manifest records only byte-different files. Focused tests reconstruct
all 435 pair decisions and all three control decisions from raw artifacts with
a separate extractor.

## Verification and contamination boundary

Creator preflight requires owner regeneration, prompt/role/reference checks,
cross-tree ID and semantic-lineage screens, the 26-root official holdout
screen, 30 normal and 30 fresh ASan/UBSan reference passes with equal positive
CTest discovery, 30 compiled/executed negative rejections, and both-mode passes
for all three controls in the pinned network-disabled repository C++ sanity
image. Receipts bind owner, curriculum, specification, focused tests, live
tree, deterministic archive/mount, compiler, CMake, image, prompt, starter,
reference, tests, metadata, policies, and results.

Cross-tree evidence uses a digest-bound snapshot taken at creator start. Each
legacy, reverify, and pre-existing sibling-expansion root is read only between
matching before/after tree hashes; the inventory stores its artifact hashes and
normalized semantic token set. The semantic screen consumes those immutable
bytes, not a later live-tree view. A root that cannot be read stably fails the
snapshot. External writers that start after the snapshot do not retroactively
change its audit subject; those later families must screen this family in their
own admission workflow.

The independent audit is read-only. Any finding routes through a preserved
remedy record, owner change, complete regeneration, remediation verification,
and a fresh audit of the exact new tree. Only that fresh audit may assign
`local_family_verified`.

## Audit-cycle-01 remediation

The immutable initial audit remains under the generated family's
`.state/audits/` directory. Stable findings `RM-AUD-001` through
`RM-AUD-006` bind complete visible contracts, independent task-specific and
invalid/boundary assertions, real incremental DSU state, portal cardinality
validation, artifact-derived clone evidence, and semantic lineage screening
across legacy, reverify, every pre-existing sibling expansion root, and all
official holdouts. Regeneration invalidates prior execution evidence and a
fresh independent audit is mandatory.

## Independent re-audit-02 remediation

The preserved second independent audit reopens `RM-AUD-001`, `RM-AUD-002`,
and `RM-AUD-005` and adds `RM-AUD-007`; its prior subject and
`local_family_verified` state do not prove the repaired tree. The owner now
specifies and directly tests the fully trapped right-hand patrol transition,
implements `mandatory-shortest-cells` with exact forward/reverse shortest-path
counts in a base-1,000,000,000 arbitrary-precision representation and exact
path-count-product equality, with a deterministic wrapped-counter
discriminator; it also emits one coherent direction-code
policy in the opposite-end control, and maps every control's default CMake
source to its config-declared editable source. Docker verification compiles
each of those three default control mappings in addition to both reference
modes. Force-regeneration reconciles every owner-generated root to its exact
rendered file set, and both diversity extractors resolve the public header from
the config-declared solution role rather than an arbitrary glob. These are
repair-in-place changes with no rejected or replacement root; complete owner
regeneration and a fresh independent audit remain mandatory.

## Post-remediation re-audit-03 remediation

The immutable third audit report reopens `RM-AUD-005`, keeps `RM-AUD-007`
open for fixed-width wrapping, and adds lifecycle finding `RM-AUD-008`. The
owner captures that audit's exact manifest and per-root before hashes before
regeneration. Force mode removes obsolete generated files, API extraction is
config-driven, and control assertions require the complete top-level role set.
Mandatory shortest-path counting now owns base-1,000,000,000 arbitrary-
precision addition and multiplication and runs a wrapped-counter
discriminator. Every retained root has a revision-2 remedy specification plus
an `aider-task-remedy-v1` record binding its preserved before tree, findings,
spec hash, owner/tests/docs changes, after tree, oracle receipt, and semantic
screens. No root is rejected or replaced; the entire exact tree and Docker
matrix must be regenerated before re-audit 4.

## Post-remediation re-audit-04 remediation

The immutable fourth audit keeps `RM-AUD-007` open because the first named
counter used only 325 routes, and keeps `RM-AUD-008` open because records used
the terminal word `verified` before independent review. Revision 3 replaces
that counter with a bounded 29-by-32 serial grid of 100 independent two-way
diamonds, whose exact shortest-route count is `2^100`. The reachable output
starts with whether the exact total exceeds `2^64-1`; therefore the emitted
unsigned-64 false substitute deterministically fails both production
executables instead of merely being identifiable by source inspection. All 30
records bind the re-audit-4 before state and remain `implemented` through
creator preflight. Only a clean re-audit 5 may authorize the terminal family
cycle and record promotion. No root is rejected or replaced.
