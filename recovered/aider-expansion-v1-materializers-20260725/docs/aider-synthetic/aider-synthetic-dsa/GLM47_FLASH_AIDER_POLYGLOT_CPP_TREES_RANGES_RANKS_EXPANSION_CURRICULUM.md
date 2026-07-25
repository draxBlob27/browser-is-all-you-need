# Trees, Ranges, and Ranks Expansion Curriculum

Status: executable clean-room curriculum for 35 new local task roots. This is
candidate authoring material only; it is not an SFT release, training
authorization, or benchmark-uplift claim.

## Count-plan cell and output boundary

This family fills exactly the 35-root cell named “Ordered trees, range, rank,
predecessor, and successor invariants” in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`.

The sole generated output is:

```text
.w8-biayn/data/aider-tasks-expansion-v1/algorithms-data-structures/trees-ranges-ranks/
```

The owner must inventory both existing generated trees, reserve every existing
ID and semantic lineage, refuse either legacy tree as output, reject links into
them, and never copy or rename an existing root. The official 26 Aider
Polyglot C++ roots are permanent holdouts; in particular, `binary-search-tree`
is not a creation input and no root below implements the benchmark's insertion
and traversal contract.

## Learning objective

Teach compact one-shot C++17 implementations of materially different ordered
index, range-query, rank-selection, predecessor, successor, persistence, and
spatial-search mechanisms. Each reference must directly implement its named
mechanism. Standard ordered containers, a fully sorted answer vector,
hard-coded cases, and a runtime policy switch are forbidden when they replace
the advertised core.

## Root inventory

| # | Task ID | Primary mechanism | Contract discriminator |
|---:|---|---|---|
| 1 | `treap-split-rank-ledger` | randomized-priority split/merge treap with subtree sizes | duplicate counts survive split/merge and rank is strict-less |
| 2 | `splay-neighbor-cursor` | rotations that splay the last accessed neighbor | root witness changes after predecessor/successor queries |
| 3 | `scapegoat-range-rebuilder` | root-alpha weight check and subtree rebuild | rebuild counter and inorder preservation after skewed inserts |
| 4 | `weight-balanced-quantile-index` | AVL height rotations with multiplicities | select uses subtree multiplicity, not unique-node count |
| 5 | `aa-tree-gap-catalog` | AA skew/split levels | predecessor/successor gaps preserve AA level invariants |
| 6 | `two-three-tree-rank-pages` | 2–3 node split propagation | page occupancy and rank across promoted middle keys |
| 7 | `btree-page-successor-index` | minimum-degree-3 B-tree insertion | successor crosses child/page boundaries without flattening |
| 8 | `bplus-leaf-range-scan` | internal separators plus linked leaves | inclusive scan follows leaf links and retains duplicate payloads |
| 9 | `interval-tree-overlap-rank` | BST ordered by start with max-end augmentation | closed overlap count prunes by max-end |
| 10 | `segment-tree-min-count` | immutable iterative segment tree storing minimum and frequency | half-open range returns both minimum and its count |
| 11 | `lazy-segment-affine-sum` | lazy affine transform composition | multiply/add updates compose in chronological order |
| 12 | `segment-tree-first-prefix` | max-prefix augmentation and descent | first threshold witness differs from total-sum lower bound with negatives |
| 13 | `fenwick-rank-locator` | immutable Fenwick prefix sums plus binary lifting | smallest one-based index reaching a cumulative rank |
| 14 | `fenwick-range-delta-ledger` | dual Fenwick range-add/range-sum transform | inclusive updates and queries handle left boundary zero |
| 15 | `fenwick-two-dimensional-rectangles` | immutable 2-D Fenwick inclusion/exclusion | rectangle sum uses four prefixes and rejects inverted bounds |
| 16 | `persistent-kth-version-index` | path-copy frequency segment trees | kth plus its range multiplicity uses the difference of two roots |
| 17 | `persistent-range-sum-diff` | path-copy point updates | historical versions remain immutable after later updates |
| 18 | `wavelet-matrix-range-quantile` | stable bit partitions with prefix-zero ranks | signed-coordinate compression and range kth descent |
| 19 | `wavelet-tree-frequency-window` | recursive value partition with prefix routes | count-equal and count-less share one routed tree |
| 20 | `merge-sort-tree-threshold-count` | segment tree of sorted node vectors | range `<= threshold` count visits logarithmic cover nodes |
| 21 | `fractional-cascade-band-search` | merged catalogs with bridge indices | one binary search drives successor queries in every catalog |
| 22 | `sparse-table-idempotent-range` | overlapping sparse-table decomposition | inclusive gcd query uses two overlapping power blocks |
| 23 | `disjoint-sparse-table-fold` | level-wise disjoint prefix/suffix folds | non-idempotent ordered digit concatenation preserves direction |
| 24 | `sqrt-decomposition-rank-updates` | mutable blocks with sorted mirrors | point updates remove one duplicate and rank queries span partial blocks |
| 25 | `mo-distinct-range-replay` | offline Mo ordering and moving frequency window | answers return to original query order after block-snake traversal |
| 26 | `implicit-treap-reversal-rank` | implicit-index treap with lazy reversal | reversals compose lazily and kth follows subtree sizes |
| 27 | `rope-avl-range-hash` | AVL rope with length and rolling-hash augmentation | splice and substring hash preserve concatenation order |
| 28 | `binary-trie-predecessor-xor` | fixed-width binary trie with subtree counts | maximum-XOR partner follows opposing bits with smaller-key ties |
| 29 | `patricia-prefix-successor` | compressed binary Patricia branches | successor respects first differing bit and compressed prefixes |
| 30 | `van-emde-boas-successor-set` | immutable recursive universe clusters and summary | min/max, empty clusters, and successor at cluster boundaries |
| 31 | `range-tree-orthogonal-count` | balanced x-tree with sorted y catalogs | closed rectangle count uses canonical x nodes and y binary searches |
| 32 | `kd-tree-rectangle-report` | alternating-axis median tree with bounding boxes | report prunes disjoint boxes and returns IDs in lexical order |
| 33 | `priority-search-three-sided` | heap-on-y/search-on-x priority search tree | three-sided query combines x split and y heap pruning |
| 34 | `interval-union-covered-rank` | disjoint canonical covered-interval set | covering merges touching spans and selects kth covered coordinate |
| 35 | `cartesian-rmq-ancestor-index` | Cartesian min-tree plus Euler-depth RMQ | leftmost equal minimum is the LCA of endpoint nodes |

## Shared task contract

Every root exposes a root-specific C++17 request/result API in task-named
header/source files. Its emitted exhaustive schema is the sole operation
contract and specifies operand mapping, valid/invalid ranges, uniqueness,
absence, ordering, and ties. Requests are in-domain only when their documented
mathematical results fit signed 64-bit arithmetic. The starter is coherent but
incomplete. References, visible/private tests, negative fixtures, CMake,
provenance, and receipts remain private.

Each task has one compiled coherent false substitute selected for its easiest
failure mode—for example flatten-and-sort instead of maintained augmentation,
eager copying instead of persistence, endpoint-only selection instead of full
range semantics, or a naive uncompressed trie instead of Patricia branching.
The same production tests must build that substitute cleanly and reject it.

## Diversity and clone controls

The owner compares all `35 * 34 / 2 = 595` unordered pairs over seven separate
dimensions derived from emitted docs, API, reference control flow, tests, and
negative fixtures:

1. public API;
2. owned state or algorithm;
3. mutation and selection rules;
4. invalid and boundary behavior;
5. reference control flow;
6. deterministic oracle;
7. topic-specific negative fixture.

Every dimension is conjunctive. The production evaluator must also reject
coherent emitted-root controls for domain/identifier rename,
constants-or-policy-only change, and opposite-end selection. Focused tests use
an independent extractor and inspect every per-dimension decision rather than
trusting the evaluator's top-level status.

## Oracle and evidence

The owner uses the pinned repository C++ sanity image with Docker network
disabled, explicit `Unix Makefiles`, strict warnings, one clean normal build,
and a separate fresh ASan/UBSan build for every root and clone control. Each
mode must discover equal positive visible/private tests. Every false substitute
must compile under the same strict flags and be rejected by executed tests.
Receipts bind live/archive/mounted tree hashes, owner/curriculum/spec/test
hashes, prompt/starter/reference/test/metadata hashes, image/toolchain/command
identity, network policy, counts, and results.

The owner also provides a host-only verification mode
(`--verify-host`, evidence class `host_verify`) for campaigns whose gate is
host verification only. It stages every root and clone control into a
temporary directory (never mutating the materialized tree), builds clean
normal and fresh ASan/UBSan references with the host toolchain through
explicit `Unix Makefiles`, requires equal positive discovery of two tests per
mode, executes each compiled false substitute to a failing test result, and
writes `.state/host-verify-receipt.json` bound to the owner, mechanisms,
cases, curriculum, specification, focused-test, tree, family-screen,
manifest, and source-inventory hashes plus host compiler/CMake identities.
Host evidence never upgrades to `docker_sanity` or `locked_oracle`, and a
host-only campaign caps the family's strongest status at
`campaign_verified_host_only`.

## Workflow status

The terminal local status may be `local_family_verified` only after creator
preflight and a fresh independent audit of the exact post-remediation tree.
Rejected/replaced candidates never count toward 35. Dataset handoff is
`not_requested`.

Cycle-02 audit subject
`sha256:4b6468218ed6161eb3d37747832fc8cdcbcd25826feee7e543566f8ce5e00658`
left all 35 roots at `repair-and-reverify`. Its six findings are the binding
remediation input for revision 2: one exhaustive emitted contract, an
independent false-representation oracle plus exact witness/metamorphic checks,
coherent root-specific negatives, identifier/literal-neutral seven-dimension
screening, three compiling controls with actual changed-file diffs, and a
stable-inventory non-self-staling Docker receipt. No earlier receipt or audit
is evidence for the regenerated revision.

Revision 2 regenerates the family from
`sha256:a49e6e9b8f53d9b19c47c5ca3d80b6f8b6ebf458d49fea8f685e7b666f50a26c`
to `sha256:8f1b8268a43ddcf51067d36d1573e93939ad3994f73b81ca40287c1d74bd679c`.
No root ID or lineage changed. The curriculum remains at
`pending_fresh_execution` until the final pinned Docker receipt and fresh
independent audit bind this exact revision.

Cycle-03 audit subject
`sha256:444ec9aa58c8f136197d5f2f85fafbb9e3a302420898aeea05cc636ce90a0e56`
kept all 35 roots in remediation for five content findings. Revision 3
publishes every witness field and counting convention, exercises treap
duplicate insertion and `INT64_MAX`, validates unused operands, adds malformed
record/duplicate-ID/empty-Patricia counterexamples, and removes the
persistent-kth/wavelet-matrix API collision by returning kth plus multiplicity
only from the persistent task. Public-API diversity excludes owned-mechanism
prose. The regenerated non-state tree is
`sha256:52bf59a4dc4fb51125790c173679c9e8d1e11ad71a95d25a56a2cdc994bc78d9`;
its status remains `pending_fresh_execution` until a new receipt and audit.

## Docs Alignment (Remediation Docs Phase)

The model-facing `.docs` follow the official Aider Polyglot C++ conventions.
`.docs/introduction.md` is a `# <Title>` header plus a domain-motivating
narrative about ordered-index structures; it never states the contract or
mentions the evaluation harness. `.docs/instructions.md` starts with
`# Instructions`, keeps the full Public API / Required behavior contract
(every rule the private tests enforce), adds a `## Examples` section with a
concrete request-to-result case drawn from the visible checks, and expresses
the mechanism requirement as natural implementation notes: the witness
counters are observable, so library ordered containers, per-query re-sorting,
hard-coded outputs, container-library delegation, and runtime strategy
switches cannot produce them. The named false substitute remains documented
as an observable-behavior requirement. The generator's focused test asserts
this docs shape and rejects meta/audit vocabulary in both docs files.
