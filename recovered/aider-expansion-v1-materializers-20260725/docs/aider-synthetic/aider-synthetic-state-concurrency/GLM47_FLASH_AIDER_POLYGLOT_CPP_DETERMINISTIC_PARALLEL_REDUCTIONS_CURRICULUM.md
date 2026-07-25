# Deterministic Parallel Reductions Expansion Curriculum v2

## Authority and remediation status

This is the executable 60-root curriculum for the binding count-plan cell
`State/concurrency -> Deterministic parallel partition, reduction, and merge`.
It materializes only below
`.w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/deterministic-parallel-reductions/`.
Cycle 1 (`sha256:232dd7bac4b72355a6973591da7a239614df5da57cf2a09083c91f8e1a6cdb6c`)
was independently audited as `replace`; zero cycle-1 roots are retained. Its
audit and nine remedy records remain immutable under the family `.state/`.

The v2 owner is `src/w8_biayn/integrations/moonlight_dpr_v2.py`; case contracts
are split across the five `moonlight_dpr_v2_*cases.py` modules and focused tests
are `tests/test_moonlight_dpr_v2.py`. These are clean-room local candidate
roots, not SFT rows, a release, training authorization, or uplift evidence.
The 26 official Aider C++ roots remain permanent holdouts.

## Learning and executable contract

The family teaches deterministic serial specifications for parallel work:
partitioning, partial-state construction, fixed-order reduction, ordered
reassembly, and convergent state reconciliation. Every counted root owns a
materially different C++17 API, state/algorithm, selection rules, invalid and
boundary behavior, reference control flow, deterministic oracle, and compiling
topic-specific false substitute. Identifiers, domains, constants, opposite
endpoints, and raw hashes never establish diversity.

Each prompt exposes only its docs and task-named header/source. The complete
header is editable; the source is a coherent stub. Private references implement
the advertised partial/state/merge mechanism directly. Global shortcuts,
generic policy switches, completion-order state, randomness, timing, files,
networking, threads, and benchmark assets are forbidden. Every material
invalid, empty, duplicate, tie, ordering, overflow, or malformed-state rule is
exercised by visible/private assertions. Each reference and its independently
mutated false substitute compile with strict C++17; the reference passes and
the false substitute fails the same production tests in both normal and fresh
ASan/UBSan builds.

## Binding inventory

Each entry states the owned mechanism; detailed APIs, boundaries, and negative
transformations are authoritative in the v2 case modules and emitted contract.

### Decomposition (12)

- `dpr-minimax-contiguous-cuts`: exhaustive minimax contiguous cuts with lexicographic ties.
- `dpr-key-affinity-shards`: FNV-1a key-affinity shards with stable filtering.
- `dpr-halo-stencil-tiles`: disjoint cores and clipped stencil halos.
- `dpr-frame-aligned-slices`: nearest cumulative targets constrained to frame boundaries.
- `dpr-morton-grid-tiles`: bit-interleaved Morton ordering with contiguous rank ownership.
- `dpr-speed-aware-list-schedule`: exact-rational projected-finish list scheduling.
- `dpr-antichain-work-waves`: wave-delayed stable Kahn antichains.
- `dpr-component-affinity-shards`: canonical connected-component shard affinity.
- `dpr-sparse-row-lpt-shards`: CSR-row longest-processing-time assignment.
- `dpr-stable-three-way-scatter`: block-counted stable less/equal/greater scatter.
- `dpr-permutation-cycle-shards`: minimum-rotated permutation cycles kept unsplit.
- `dpr-block-cyclic-matrix-tiles`: two-dimensional block-cyclic process-grid ownership.

### Numeric and ordered algebra (12)

- `dpr-exact-mean-quotient`: checked sum/count with Euclidean quotient/remainder.
- `dpr-modular-product-fold`: double-and-add modular partial product tree.
- `dpr-polynomial-chunk-compose`: Horner segment summaries composed by power.
- `dpr-ordered-matrix-chain`: source-ordered noncommutative matrix products.
- `dpr-checked-dot-product`: checked per-shard products and total merge.
- `dpr-first-prefix-overflow`: prefix-extrema localization of first overflow.
- `dpr-chan-variance-state`: balanced count/first/second-moment state merge.
- `dpr-paired-covariance-state`: bivariate marginals and co-moment reduction.
- `dpr-rational-weighted-centroid`: checked mass and first-moment partials.
- `dpr-max-subarray-monoid`: cross-boundary total/prefix/suffix/best merge.
- `dpr-longest-equal-run`: endpoint-aware cross-shard equal-run merge.
- `dpr-bracket-balance-summary`: net/minimum-prefix summaries with global carry.

### Structural summaries and scans (12)

- `dpr-dfa-transform-compose`: per-shard full DFA transformation composition.
- `dpr-exclusive-block-scan`: local exclusive scans plus block-total carries.
- `dpr-segmented-inclusive-scan`: carry propagation only before the first reset.
- `dpr-earliest-constraint-failure`: canonical indices and earliest failure selection.
- `dpr-stable-topk-summary`: bounded per-shard top-K and stable ordered merge.
- `dpr-majority-summary-verify`: Boyer-Moore partials followed by exact verification.
- `dpr-cross-shard-inversion-count`: sorted merge with cross-inversion accounting.
- `dpr-pareto-frontier-merge`: partial pruning followed by global re-pruning.
- `dpr-sparse-coo-canonical-merge`: sorted COO accumulation with zero cancellation.
- `dpr-convex-hull-fragment-merge`: fragment hulls followed by a global rehull.
- `dpr-sorted-shard-median`: rank-selecting K-way traversal of sorted shards.
- `dpr-priority-reservoir-merge`: mergeable bottom-K identity-priority reservoir.

### Ordered merge and reconciliation (12)

- `dpr-loser-tree-run-merge`: head-only deterministic multi-run tournament merge.
- `dpr-keyed-conflict-reconcile`: highest revision with explicit equal-revision conflict.
- `dpr-provenance-interval-union`: sweep emitting exact active-source bitsets.
- `dpr-nonoverlap-hunk-merge`: identical-deduplicating half-open hunk reconciliation.
- `dpr-asof-stream-join`: latest-not-after join over stable merged updates.
- `dpr-seamed-tile-assembly`: exact cover with overlap seam agreement.
- `dpr-causal-version-reconcile`: vector-clock dominance and concurrent survivors.
- `dpr-column-batch-row-merge`: row-ID outer merge requiring all named columns.
- `dpr-edge-shards-to-csr`: duplicate-edge accumulation into exact CSR.
- `dpr-labeled-coverage-stitch`: exact labeled interval cover with adjacent-label coalescing.
- `dpr-quorum-certificate-reduce`: maximum-term distinct-member quorum/equivocation.
- `dpr-domain-separated-merkle-fold`: index-canonical domain-separated Merkle fold.

### Composite reductions (12)

- `dpr-canonical-connectivity-merge`: minimum-root DSU component canonicalization.
- `dpr-sharded-topological-order`: deduplicated-edge lexicographically least Kahn order.
- `dpr-permutation-compose`: validated source-ordered permutation composition.
- `dpr-spatial-moments-summary`: mass, first, and second spatial moments.
- `dpr-canonical-minimum-spanning-forest`: weight-first canonical Kruskal forest.
- `dpr-lexicographic-shortest-paths`: nonnegative Dijkstra with predecessor ties.
- `dpr-scc-condensation-merge`: mutual-reachability SCCs and condensation edges.
- `dpr-deque-steal-trace-replay`: owner-LIFO/thief-FIFO deque event replay.
- `dpr-sequence-gap-certificate`: interval reassembly with overlap and gap evidence.
- `dpr-retry-state-lattice`: monotone per-request terminal-state join.
- `dpr-two-phase-commit-log`: participant-complete prepare-gated decisions.
- `dpr-pn-counter-state-merge`: componentwise-max state-based PN-counter join.

## Diversity, contamination, and evidence

The owner rereads emitted docs, headers, references, visible/private tests, and
negative sources. It evaluates all `60*59/2 = 1770` pairs conjunctively over
the exact seven hard dimensions using artifact-derived, identifier/domain/
literal/endpoint-neutral structural shingles. It also materializes coherent
domain-rename, constants-policy, and opposite-end controls from the frame-cut
root plus a dimensional-wrapper sparse-map clone; all four must build and pass their own behavior tests while the
production evaluator rejects them in every dimension. Focused tests inspect
the pair table and artifact signatures independently.

Before materialization the owner freezes both protected trees and all other
expansion roots. It reconciles every frozen config/tree hash, persists every
candidate/external comparison, screens all 26 official holdouts, and requires
exact comparison counts. In particular the rejected cycle-1 histogram,
watermark/event, RLE, generation barrier, and simple interval-union contracts
are absent from the v2 inventory.

Final creator evidence uses the pinned network-disabled C++ sanity image. The
receipt records every task/control mode separately: discovered tests, positive
exit, negative exits, and safe log hashes, plus owner/case/curriculum/spec/test,
tree/archive/mount, compiler, CMake, image, and policy hashes. The owner also
provides a `--verify-host` mode running the same per-root normal and fresh
ASan/UBSan contract on the host; its receipt binds the current owner and tree
but upgrades the manifest only to `host_verified_pending_docker_sanity`.
Structural verification alone records `pending_execution`. Creator or
remediation preflight cannot close the loop; only a clean fresh independent
audit of the exact v2 hash plus a bound pinned-image receipt may assign
`local_family_verified`.

Dataset handoff remains `not_requested`.
