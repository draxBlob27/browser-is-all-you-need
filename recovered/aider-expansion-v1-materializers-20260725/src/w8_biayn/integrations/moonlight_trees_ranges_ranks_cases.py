"""Clean-room inventory for the 35-root trees/ranges/ranks expansion.

This catalog deliberately contains no second, aspirational operation contract.
The exhaustive per-strategy schema emitted by the owner is the only public
behavior contract; each row here owns only identity, mechanism, and the
coherent false representation exercised by the tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TreeRangeRankCase:
    task_id: str
    mechanism: str
    false_substitute: str
    strategy: int

    @property
    def title(self) -> str:
        return self.task_id.replace("-", " ").title()


_ROWS = (
    ('treap-split-rank-ledger', 'random-priority split/merge treap with multiplicity and subtree-size augmentation', 'flatten all keys into a sorted vector after every operation'),
    ('splay-neighbor-cursor', 'bottom-up splay tree with last-access root semantics', 'binary-search a sorted vector without changing a root witness'),
    ('scapegoat-range-rebuilder', 'root-alpha weight check with inorder flatten and balanced rebuild', 'use an unbalanced BST and fabricate the rebuild counter'),
    ('weight-balanced-quantile-index', 'height-balanced AVL rotations over duplicate-counted ordered nodes', 'delegate storage and selection to std::multiset'),
    ('aa-tree-gap-catalog', 'AA-tree skew and split level maintenance', 'store a sorted vector and never maintain AA levels'),
    ('two-three-tree-rank-pages', '2-3 search tree with upward split propagation and subtree counts', 'use a binary tree while reporting invented page occupancy'),
    ('btree-page-successor-index', 'minimum-degree-three B-tree insertion and page descent', 'sort all keys and perform upper_bound without B-tree pages'),
    ('bplus-leaf-range-scan', 'B+ separator pages with linked duplicate-bearing leaves', 'sort records and filter them without linked leaves'),
    ('interval-tree-overlap-rank', 'start-ordered interval tree augmented by subtree maximum end', 'scan every interval and sort answers after each query'),
    ('segment-tree-min-count', 'immutable iterative segment tree of minimum/count monoids', 'scan each queried range linearly'),
    ('lazy-segment-affine-sum', 'lazy segment tree with affine tag composition', 'eagerly update every element for every transform'),
    ('segment-tree-first-prefix', 'segment tree storing total sum and maximum nonempty prefix', 'assume all values are nonnegative and lower_bound cumulative sums'),
    ('fenwick-rank-locator', 'immutable Fenwick cumulative counts with binary-lifting select', 'build every prefix and linearly scan it'),
    ('fenwick-range-delta-ledger', 'dual Fenwick difference transform for range add/range sum', 'loop over every element in each update'),
    ('fenwick-two-dimensional-rectangles', 'two-dimensional Fenwick build and rectangle prefix inclusion/exclusion', 'sum every cell in every requested rectangle'),
    ('persistent-kth-version-index', 'path-copy frequency segment roots for subarray order statistics', 'copy and sort every subarray at query time'),
    ('persistent-range-sum-diff', 'path-copy point-update segment versions', 'copy the entire array for each version'),
    ('wavelet-matrix-range-quantile', 'wavelet-matrix stable bit partitions with prefix-zero ranks', 'sort each query slice independently'),
    ('wavelet-tree-frequency-window', 'recursive value-domain wavelet tree with prefix routing', 'scan every window for each query'),
    ('merge-sort-tree-threshold-count', 'segment tree whose canonical nodes own sorted catalogs', 'scan and compare every element in the range'),
    ('fractional-cascade-band-search', 'fractional-cascaded sorted catalogs with bridge indices', 'binary-search every catalog independently'),
    ('sparse-table-idempotent-range', 'overlapping sparse table for idempotent gcd', 'fold every value in every range'),
    ('disjoint-sparse-table-fold', 'disjoint sparse table for ordered non-idempotent concatenation', 'use overlapping sparse-table blocks as though concatenation were idempotent'),
    ('sqrt-decomposition-rank-updates', 'mutable square-root blocks with sorted mirrors', 'sort every query subarray from scratch'),
    ('mo-distinct-range-replay', 'offline Mo block-snake ordering with moving frequency window', 'use an unordered set scan independently for every range'),
    ('implicit-treap-reversal-rank', 'implicit-index treap with lazy reversal and subtree sizes', 'call std::reverse eagerly on a vector'),
    ('rope-avl-range-hash', 'AVL rope with subtree length and polynomial hash augmentation', 'store one flat string and recompute every substring hash'),
    ('binary-trie-predecessor-xor', 'fixed-width counted binary trie for maximum-XOR partner selection', 'scan every stored key for the maximum-XOR partner'),
    ('patricia-prefix-successor', 'compressed binary Patricia trie keyed by first differing bit', 'use an uncompressed one-node-per-bit trie'),
    ('van-emde-boas-successor-set', 'immutable recursive van-Emde-Boas clusters and summary', 'scan a boolean universe linearly'),
    ('range-tree-orthogonal-count', 'balanced x-range tree with sorted y catalogs', 'scan all points for each rectangle'),
    ('kd-tree-rectangle-report', 'alternating-axis median kd-tree with subtree bounding boxes', 'scan all points and filter them'),
    ('priority-search-three-sided', 'priority search tree with y-heap and x partition', 'scan every point for each query'),
    ('interval-union-covered-rank', 'canonical disjoint covered-interval set with rank selection', 'maintain a boolean value for every coordinate in a fixed array'),
    ('cartesian-rmq-ancestor-index', 'leftmost-min Cartesian tree with Euler tour and depth RMQ', 'scan each range or use a direct value sparse table without a Cartesian tree'),
)

CASES = tuple(
    TreeRangeRankCase(task_id, mechanism, false_substitute, strategy=index)
    for index, (task_id, mechanism, false_substitute) in enumerate(_ROWS)
)

assert len(CASES) == 35
assert len({case.task_id for case in CASES}) == 35
assert len({case.mechanism for case in CASES}) == 35
