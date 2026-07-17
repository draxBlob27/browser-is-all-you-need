# Algorithm And Data-Structure Topics For GLM C++ SFT Planning

Status: curriculum-planning taxonomy. This is not a claim that every example
below was evaluated in the Aider benchmark.

The complete GLM-4.7-Flash Modal/Aider C++ evaluation identifies data-structure
and collection behavior as an area that needs more reliable first-try
implementation. This note names the underlying topics at useful curriculum
granularity. The official Aider tasks remain benchmark holdouts: do not add
them, their tests, their references, or close semantic copies to SFT data.

See `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md` for the run
evidence and broader curriculum implications.

## Linked Structure Invariants

Implementations must preserve a network of relationships after every mutation:
insertion, removal, traversal, and boundary handling.

- **Doubly linked lists** — keep `prev` and `next` synchronized at each splice.
- **Binary search trees** — preserve the insertion path, parent/child
  relationships, and min/max removal behavior.
- **AVL and red-black trees** — preserve BST ordering while rotations retain
  balance invariants.
- **Tries** — maintain child-map consistency and separate prefix from terminal
  marking.
- **Skip lists** — keep multi-level `next[]` links consistent.
- **XOR linked lists** — encode and traverse the `prev ^ next` link correctly.
- **Threaded binary trees** — distinguish ordinary children from null pointers
  repurposed as inorder threads.
- **Union-find (disjoint set)** — maintain parent pointers while applying path
  compression.
- **LRU caches** — coordinate a hashmap with a doubly linked list and evict
  the correct node after every access or insertion.

The benchmark's `binary-search-tree` and `linked-list` exercises are examples
of this topic; they must remain holdouts.

## Bounded Queue And Ring-Buffer Semantics

These problems are state machines over a fixed-capacity sequence. Correctness
depends on read/write cursors, the full-versus-empty distinction, wraparound,
and any overwrite or eviction rule.

- **Circular buffers** — read/write indices and force-write behavior.
- **Bounded blocking queues** — the same capacity state machine plus blocking
  and synchronization rules.
- **Sliding-window maximum** — a monotonic deque maintained for a bounded
  moving window.
- **Circular deques** — wraparound operations at both ends.
- **Producer-consumer rings** — ring-buffer state plus synchronization
  invariants.
- **LFU caches** — bounded capacity paired with frequency and recency
  bookkeeping for eviction.

The benchmark's `circular-buffer` exercise is an example of this topic and
must remain a holdout.

## Collection Classification And Ordering Semantics

These tasks go beyond storing values: they require rules for grouping,
duplicates, ordering, containment, and edge-case classification.

- **Grade rosters or ordered registries** — group by key, maintain a canonical
  ordering, and reject duplicates.
- **Contiguous sequence matching** — determine equality, sublist, superlist,
  and empty-sequence cases.
- **Robot simulations** — apply state and directional transition rules in the
  specified order.
- **Interval scheduling and range classification** — reason about containment
  and overlap, the range analogue of sequence containment.
- **Run-length encoding** — group consecutive equal values and correctly
  collapse or expand runs.
- **Matching brackets** — use a stack to validate nested structural
  containment.
- **Multisets (bags)** — preserve count-aware duplicate semantics.
- **Priority queues (heaps)** — preserve ordering invariants after each push
  and pop.

The benchmark's `grade-school` and `sublist` exercises are examples of this
topic; they must remain holdouts.

## Use In Data Design

Create semantically distinct, licensed tasks that exercise one or more of the
topics above. Keep source families isolated across splits, retain hidden tests
outside training rows, and apply the repository's contamination and admission
gates before adding any candidate to an SFT release.
