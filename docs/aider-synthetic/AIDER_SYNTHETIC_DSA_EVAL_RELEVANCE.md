
| Curriculum (20 proposed roots) | Topic | Relevance to the Aider evaluation |
|---|---|---|
| Balanced search tree (`avl-*`, `rb-*`) | AVL/red-black ordered mutation, rank/range/neighbor queries | **Very high.** `binary-search-tree` was never solved. Teach the underlying ordered-tree capability without producing a close benchmark variant. |
| Binary search tree (`bst-*`) | Ordered pointer invariants; predecessor/successor/range queries | **Very high, direct holdout-adjacent gap.** Targets the never-solved `binary-search-tree` capability. |
| Bounded blocking queue (`bbq-*`) | Mutex/condition-variable FIFO, closure, backpressure | **High.** Reinforces the weak state/concurrency cluster, including never-solved `bank-account` and `parallel-letter-frequency`. |
| Circular buffer (`ring-*`) | Fixed-capacity FIFO, cursors, wraparound, overwrite policy | **Very high, direct holdout-adjacent gap.** `circular-buffer` was never solved; apply particularly strict decontamination review. |
| Circular deque (`cdeque-*`) | Two-ended circular state, wraparound, under/overflow | **High.** Builds bounded-state behavior related to the unsolved circular-buffer capability, while remaining benchmark-adjacent. |
| Doubly linked list (`dll-*`) | Ownership and bidirectional-link invariants | **High.** `linked-list` only succeeded after repair; valuable for one-shot pointer-structure correctness. |
| Interval scheduling (`interval-*`) | Overlap, containment, endpoint policy, allocation | **High.** Covers time/date-like boundary and logic/constraint reasoning without duplicating a holdout. |
| LFU cache (`lfu-*`) | Frequency buckets, recency tie-breaking, eviction | **Medium-high.** Builds stateful invariant discipline; no direct LFU holdout exists. |
| LRU cache (`lru-*`) | Map plus recency-linked-list coherence | **High.** Extends linked-list and state-management correctness with strict mutation invariants. |
| Nested structure validation (`nested-*`) | Stack parsing, quoted/escaped/comment regions, diagnostics | **High.** Directly addresses the weak text/parsing cluster and its edge cases. |
| Ordered registry (`registry-*`) | Identity, grouping, membership, reassignment, ordered queries | **High.** Decontaminated capability analogue of repair-only `grade-school`. |
| Priority queue (`pq-*`) | Heap invariants, stable ties, updates/cancellation | **Medium.** General algorithms/data-structures coverage: relatively stronger, but still inconsistent, in the evaluation. |
| Producer-consumer ring (`pcr-*`) | Ring invariants plus synchronization/backpressure | **High.** Combines circular-state and concurrency weaknesses. |
| Robot state simulation (`robot-*`) | Typed commands, modes, transitions, constrained movement | **Medium-high.** Targets state machines and exact interface behavior, adjacent to repair-only stateful tasks such as `robot-name`. |
| Run-length encoding (`rle-*`) | Grouping, canonical encoding/decoding, stream boundaries | **High.** Adds text/parsing coverage without reusing benchmark text tasks. |
| Sequence pattern (`sequence-*`) | Matching, alignment, spans, ordered-sequence policy | **Very high, direct holdout-adjacent gap.** Decontaminated capability analogue of never-solved `sublist`. |
| Skip list (`skip-*`) | Multi-level links, ordered mutation, rank/index accounting | **Medium-high.** Broadens ordered-structure invariant practice beyond the failed BST capability. |
| Sliding-window maximum (`swmax-*`) | Monotonic deque, expiry, equal-value ties | **Medium.** Useful algorithmic practice, though not tied to a named benchmark failure. |
| Threaded binary tree (`threaded-*`) | Child-vs-thread invariants, bidirectional traversal | **High.** Deepens the failed tree-like capability through a different representation. |
| Trie (`trie-*`) | Prefix maps, terminal markers, deletion, normalization | **High.** Bridges data structures with weak text/prefix parsing and deterministic ordering. |
| XOR linked list (`xor-*`) | Slot-index XOR-link representation, traversal/mutation | **Medium-high.** Advanced linked-structure invariants using safe slot IDs rather than raw-pointer XOR. |