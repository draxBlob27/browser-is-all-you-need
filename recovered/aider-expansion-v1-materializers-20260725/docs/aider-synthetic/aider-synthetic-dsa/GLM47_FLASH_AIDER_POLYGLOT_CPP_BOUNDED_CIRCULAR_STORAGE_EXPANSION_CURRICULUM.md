# Bounded and Circular Storage Expansion Curriculum

Status: cycle-04 remediation specification for 60 clean-room local candidates;
55 rejected template roots are replaced by the case-owned IDs below.
It implements the binding State/concurrency count-plan cell “Bounded and
circular storage with explicit capacity policies.” It does not create SFT rows,
authorize training, or claim benchmark uplift.

## Identity and output boundary

- Family ID: `aider-expansion-v1-bounded-circular-storage-v1`.
- Selected design prompt:
  `docs/aider-tasks-spec/prompts/generate-family-spec.md`.
- Owner:
  `src/w8_biayn/integrations/moonlight_bounded_circular_storage_expansion.py`.
- Focused test:
  `tests/test_moonlight_bounded_circular_storage_expansion.py`.
- Only generated output:
  `.w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/bounded-circular-storage/`.
- Lineage: every retained task is a new root with no parent or replacement.
  The owner must reject IDs and semantic contracts found anywhere below
  `.w8-biayn/data/aider-tasks/`, `.w8-biayn/data/aider-tasks-reverify/`, or the
  rest of `.w8-biayn/data/aider-tasks-expansion-v1/`.
- Task content is original repository-authored material under `CC0-1.0`.
  Official Aider C++ roots, prompts, tests, references, responses, and retry
  histories are permanent holdouts and are not authoring inputs.

The family excludes FIFO blocking queues, ordinary circular buffers/deques,
producer-consumer rings, timer wheels, round-robin rotors, serial replay
windows, multi-subscriber cursor logs, generation barriers, and the other
contracts already reserved by the existing trees. A domain rename, a capacity
constant, an overflow toggle, or an opposite-end choice is not a new root.

## Common executable contract

Each root exposes one task-specific C++17 class in `<task-id>.h` and implements
it in `<task-id>.cpp`. Capacity is fixed at construction and never grows.
Construction with zero capacity throws `std::invalid_argument`. Methods that
accept an invalid index, malformed range, impossible size, or arithmetic value
that would overflow throw `std::invalid_argument` or `std::overflow_error` as
stated in the per-root row, without mutation. Duplicate insertion, absent
lookup/removal, full-capacity admission, ordering, and ties are explicitly
defined below. Empty queries return the declared empty value and never expose
uninitialized storage.

Every root must contain:

- visible docs and exactly two editable files, ordered header then source;
- an incomplete coherent starter and complete private reference replacements;
- one visible test executable and one private deterministic boundary/invariant
  test executable;
- one compiling plausible-but-wrong source that fails behavior tests rather
  than compilation or timeout;
- strict C++17 CMake, `Unix Makefiles`, `-Wall -Wextra -Wpedantic -Werror`, and
  two positive CTests in both normal and fresh ASan/UBSan builds;
- role-safe config/provenance/tests metadata and prompt-boundary evidence.

## Root contracts

The API column is a concise curriculum-level surface summary. The generated
task header is the authoritative exact declaration, including public handle
and result types. `snapshot()`-like methods define the observable order used by
tests. `cap` always means the immutable constructor capacity.

### Allocation and layout mechanisms (1–10)

| ID | Public surface summary | Required mechanism and behavior | Deterministic discriminator |
| --- | --- | --- | --- |
| `capacity-buddy-pool` | `BuddyPool(size_t power_of_two); optional<Block> allocate(size_t); bool release(Block); size_t largest_free() const;` | Own power-of-two free lists and recursively split the smallest fitting block; coalesce only with the XOR buddy on release. Non-power-of-two construction and zero/oversize requests are invalid; duplicate release is false; equal blocks choose the lower offset. | Reject first-fit intervals: allocate 3, 3, release both, then require an 8-byte coalesced block at offset 0. |
| `capacity-run-bitmap` | `RunBitmap(size_t cap); optional<size_t> claim(size_t run, size_t alignment); bool free(size_t start,size_t run); vector<pair<size_t,size_t>> free_runs() const;` | Own occupancy bits plus a summary word per 64 slots; find the lowest aligned clear run crossing word boundaries. Invalid alignment is non-power-of-two; overlapping/absent free is false; tie is lowest start. | Reject a word-local scanner with a clear run spanning slots 62–66. |
| `capacity-size-class-arena` | `SizeClassArena(vector<size_t> classes,size_t bytes); optional<Handle> acquire(size_t); bool release(Handle); vector<size_t> free_per_class() const;` | Partition backing storage into declared ascending size classes, allocate from the smallest fitting class, and maintain intrusive per-class free chains. Duplicate classes/requests above largest are invalid; stale/double release is false; lowest slot breaks ties. | Reject a single global free list by exhausting only the smallest class while a larger class remains free. |
| `capacity-indirect-compacting-slab` | `IndirectCompactingSlab(size_t slots); optional<Handle> emplace(int); optional<int> get(Handle) const; bool erase(Handle); vector<Move> compact();` | Own stable generational handle slots separately from movable physical cells; compaction packs live cells and updates every handle-to-physical indirection. | Reject index-equals-physical handles by erasing a middle cell, compacting, and resolving the moved handle. |
| `capacity-checkpoint-arena` | `CheckpointArena(size_t bytes); optional<size_t> append(vector<uint8_t>); size_t checkpoint() const; bool rewind(size_t); vector<uint8_t> bytes() const;` | Use a monotone cursor over fixed bytes; checkpoints are prior cursor positions and rewind invalidates later checkpoints. Empty append is valid and returns cursor; overflow returns null without mutation; rewind to unknown/future is false. | Reject per-object free-list semantics by rewinding across three variable appends and requiring exact prefix restoration. |
| `extent-compaction-ledger` | `ExtentCompactionLedger(size_t bytes); optional<Token> put(vector<uint8_t>); bool erase(Token); vector<Move> compact(); optional<vector<uint8_t>> read(Token) const;` | Own variable extents and stable tokens; stable compaction moves live payloads left and updates token-to-offset mapping while reporting moves in old-offset order. Empty payload is invalid; full returns null; stale token is absent. | Reject offset-as-token storage: erase a middle extent, compact, then read both moved tokens. |
| `opposing-stack-arena` | `OpposingStackArena(size_t bytes); optional<Span> push_low(size_t); optional<Span> push_high(size_t); bool pop_low(); bool pop_high(); pair<size_t,size_t> fronts() const;` | Allocate stack-like extents from opposite ends of one array and prevent front crossing. Zero request is invalid; full returns null; empty pop is false; each side is independently LIFO. | Reject two independent capacities by filling low then proving high cannot cross the shared frontier. |
| `lazy-page-frame-directory` | `LazyPageFrameDirectory(size_t virtual_pages,size_t frames); optional<size_t> map(size_t page); bool unmap(size_t page); optional<size_t> frame(size_t page) const; vector<size_t> mapped_pages() const;` | Own a two-level sparse directory plus a lowest-frame free bitmap; allocate second-level tables lazily and delete empty ones. Invalid page is rejected; duplicate map returns existing frame; absent unmap false. | Reject a dense page vector through a private allocated-directory count invariant after mapping distant pages. |
| `coalescing-tag-allocator` | `CoalescingTagAllocator(size_t units); optional<Block> allocate(size_t); bool release(Block); vector<Block> free_blocks() const;` | Maintain physical boundary tags and an address-ordered free chain; split only when a nonempty remainder remains and coalesce both adjacent free blocks. Zero request invalid; best fit then lowest offset; double release false. | Reject one-sided coalescing with free-right, free-left, free-middle followed by a whole-heap request. |
| `reserved-shared-lease-pool` | `ReservedSharedLeasePool(vector<size_t> quotas,size_t reserve); optional<Lease> claim(size_t tenant); bool release(Lease); bool transfer(Lease,size_t tenant); vector<size_t> usage() const;` | Own tenant-reserved slots plus a shared reserve. A tenant consumes reserved capacity before shared; transfer is atomic and preserves whether the lease is reserved/shared where legal. Invalid tenant throws; full returns null; stale/double release false. | Reject global-only capacity by saturating one tenant while another tenant's reservation remains claimable. |

### Wrapped record and spatial mechanisms (11–20)

| ID | Public surface summary | Required mechanism and behavior | Deterministic discriminator |
| --- | --- | --- | --- |
| `framed-byte-wrap-log` | `FramedByteWrapLog(size_t bytes); optional<uint64_t> append(vector<uint8_t>); bool discard_through(uint64_t); optional<vector<uint8_t>> read(uint64_t) const; vector<uint64_t> ids() const;` | Store length-prefixed variable records in a byte ring, emitting an explicit wrap marker when a record cannot fit contiguously. No overwrite; empty record valid; IDs monotone and overflow-checked; discard is inclusive. | Reject byte-by-byte split records by requiring one wrap marker and contiguous reconstruction after head reclamation. |
| `crc-recovery-frame-store` | `CrcRecoveryFrameStore(size_t bytes); bool write(uint16_t,vector<uint8_t>); optional<Frame> read(); bool inject_incomplete(...); size_t corrupt_count() const;` | Store raw bounded bytes containing type, length, CRC16, and payload; reads skip and count corrupt complete frames but retain incomplete tails. Oversize/empty payload rejected; no overwrite. | Reject structured-frame storage by corrupting one raw payload byte and separately retaining an injected incomplete tail. |
| `two-span-packet-ledger` | `TwoSpanPacketLedger(size_t bytes); optional<uint32_t> stage(vector<uint8_t>); optional<pair<Span,Span>> spans(uint32_t) const; bool consume(uint32_t);` | Permit at most two physical spans for one logical packet across the end boundary and keep packet descriptors in insertion order. Empty/oversize invalid; only the oldest packet may be consumed. | Reject forced-contiguous placement using a packet whose only fit is split across the boundary. |
| `retire-gated-snapshot-wheel` | `RetireGatedSnapshotWheel(size_t slots); uint64_t publish(vector<int>); optional<vector<int>> acquire(uint64_t) const; bool retire_before(uint64_t); vector<uint64_t> generations() const;` | Store immutable snapshots in circular slots, refusing publish while overwriting an unretired generation. Empty snapshot valid; generations monotone and overflow-checked; retirement is prefix-only. | Reject unconditional overwrite by filling all slots and publishing before retirement. |
| `segmented-delta-samples` | `SegmentedDeltaSamples(size_t cap); bool append(int64_t); optional<int64_t> at(size_t age) const; vector<int64_t> decode() const;` | Keep a circular base plus checked signed deltas; start a new base segment when delta does not fit 16 bits. Full evicts the oldest complete sample; age zero is newest; invalid age absent. | Reject 16-bit truncation with alternating values around both delta limits across wrap. |
| `maximal-run-event-shelf` | `MaximalRunEventShelf(size_t runs); bool append(int code); bool pop_oldest(); vector<pair<int,size_t>> runs() const; size_t event_count() const;` | Store bounded maximal `(code,count)` runs; equal adjacent codes merge without consuming a run, and popping one event shrinks/removes the oldest run. Full with a new code is false. | Reject one-slot-per-event with a long equal run admitted after all run slots otherwise fill. |
| `cross-word-symbol-pack` | `CrossWordSymbolPack(size_t symbols,uint8_t width); bool push(uint32_t); optional<uint32_t> pop(); vector<uint32_t> values() const;` | Pack fixed-width symbols into a circular bit address space, correctly handling symbols split across machine words. Width 1–17; out-of-range value invalid; full false; FIFO pop. | Reject word-aligned packing with a 17-bit symbol starting at bit 63. |
| `origin-mapped-row-grid` | `OriginMappedRowGrid(size_t rows,size_t columns,size_t stride); bool replace(size_t logical_row,vector<int>); vector<int> column(size_t) const; void rotate_rows(int64_t);` | Own padded physical rows and a logical-to-physical circular origin; replace maps through the origin and never touches padding. Invalid shape/index throws; signed rotation normalizes. | Reject physical row movement by checking padding canaries and logical replacement after negative rotation. |
| `floor-mod-torus-grid` | `FloorModTorusGrid(size_t rows,size_t cols); void set(size_t,size_t,int); int wrapped_at(int64_t,int64_t) const; vector<int> window(int64_t,int64_t,size_t,size_t) const;` | Own a bounded 2-D torus with floor-mod indexing and row-major wrapped windows. Zero dimensions invalid; set requires in-range coordinates; window area overflow throws. | Reject C++ remainder indexing with negative coordinates crossing both axes. |
| `contiguous-sequence-window` | `ContiguousSequenceWindow(size_t cap,uint64_t first); bool append(uint64_t, int); optional<int> get(uint64_t) const; bool trim_before(uint64_t); pair<uint64_t,uint64_t> range() const;` | Map contiguous checked sequence numbers to circular slots; append must equal next sequence and never overwrite untrimmed data. Empty range is `[next,next)`; trim is monotone. | Reject modulo-only aliasing by querying an old sequence whose slot has been reused after trim. |

### Admission and eviction mechanisms (21–30)

| ID | Public surface summary | Required mechanism and behavior | Deterministic discriminator |
| --- | --- | --- | --- |
| `reference-bit-clock-cache` | `ReferenceBitClockCache(size_t cap); optional<int> get(int); optional<int> put(int,int); vector<int> hand_order() const;` | Own slots, reference bits, and a clock hand; hit sets the bit, insertion sweeps and clears bits until an unreferenced victim. Duplicate key replaces value; cap full returns evicted key. | Reject LRU by a trace where clock hand and recency choose different victims. |
| `two-lane-promotion-cache` | `TwoLanePromotionCache(size_t probation,size_t protected_cap); optional<int> access(int); optional<int> insert(int,int); pair<vector<int>,vector<int>> lanes() const;` | New keys enter probation MRU; a probation hit promotes to protected MRU and demotes protected LRU if needed. Zero lane capacities invalid; duplicate insert replaces in place. | Reject one-list LRU by requiring promotion/demotion order after alternating lane hits. |
| `epoch-aged-frequency-cache` | `EpochAgedFrequencyCache(size_t cap,size_t epoch); optional<int> get(int); optional<int> put(int,int); void tick(size_t); vector<pair<int,size_t>> frequencies() const;` | Maintain saturating frequencies and halve all counts at logical epoch boundaries; evict minimum frequency then oldest touch. Epoch zero invalid; duplicate put counts as touch. | Reject lifetime LFU with a once-hot key that must age below a recent key. |
| `ratio-cost-unit-cache` | `RatioCostUnitCache(size_t units); optional<int> put(int,int,size_t,size_t); optional<int> get(int); size_t used() const;` | Variable-size entries have recompute cost; evict minimal `cost/size` by cross multiplication, then oldest, until enough units exist. Zero size/oversize invalid; overflow-safe products required. | Reject LRU and floating comparison with near-equal large integer ratios. |
| `nested-pin-lru-cache` | `NestedPinLruCache(size_t cap); optional<int> put(int,int); optional<int> pin(int); bool unpin(int); optional<int> erase(int); vector<int> evictable_order() const;` | LRU only among unpinned entries; pin counts nest, pinned entries cannot erase/evict, and insertion fails atomically if every victim is pinned. | Reject boolean pins with two pins followed by one unpin and an eviction attempt. |
| `transitive-dependency-cache` | `TransitiveDependencyCache(size_t cap); bool put(int,vector<int>); bool erase(int); vector<int> closure(int) const; vector<int> keys() const;` | Admit a key only when all dependencies exist; erase atomically removes the key and every transitive dependent in reverse topological/tie-key order. Duplicate key invalid; cycles rejected. | Reject direct-dependent-only erase with a three-level dependency chain. |
| `clean-only-dirty-cache` | `CleanOnlyDirtyCache(size_t cap); optional<int> put(int,int,bool); bool mark_clean(int); vector<pair<int,int>> flush_plan() const; vector<int> keys() const;` | Evict clean LRU only; if all candidates dirty, put fails and reports no eviction. Flush plan orders dirty entries by dirty epoch then key without mutating them. | Reject unconditional LRU by filling with dirty entries and proving atomic admission failure. |
| `tri-state-expiry-cache` | `TriStateExpiryCache(size_t cap); void advance(uint64_t); bool put(int,optional<int>,uint64_t); optional<optional<int>> get(int); vector<int> expiry_order() const;` | Store positive and negative results with logical expiry; lazily purge expired entries before access/admission and order equal expiry by insertion serial. Zero TTL invalid; clock overflow throws. | Reject truthy-value filtering by retrieving a live negative result distinct from absence. |
| `count-min-admission-cache` | `CountMinAdmissionCache(size_t cap,size_t width); optional<int> request(int,optional<int>); vector<int> keys() const; vector<uint16_t> counters() const;` | Maintain a four-row saturating count-min sketch; on miss with a value, admit only if estimated frequency exceeds the LRU victim, ties reject. Width zero invalid; hits update sketch and recency. | Reject admit-everything LRU using a scan-resistant hot-key trace. |
| `atomic-member-group-cache` | `AtomicMemberGroupCache(size_t units); bool put_group(int,vector<pair<int,int>>); bool erase_group(int); optional<int> get(int) const; vector<int> groups() const;` | Groups occupy units equal to member count and are admitted/evicted atomically by oldest group touch; duplicate member across groups invalid; oversize and partial admission fail without mutation. | Reject per-entry eviction with a group that can fit only if a whole older group leaves. |

### Bounded index mechanisms (31–40)

| ID | Public surface summary | Required mechanism and behavior | Deterministic discriminator |
| --- | --- | --- | --- |
| `radix-prefix-slot-trie` | `RadixPrefixSlotTrie(size_t nodes,uint8_t bits); bool insert(uint32_t,uint8_t,int); bool erase(uint32_t,uint8_t); optional<int> longest_prefix(uint32_t) const; size_t nodes_used() const;` | Own a bounded binary radix-node pool. Insert allocates the lowest free node along the prefix bits and rolls back atomically when the pool is exhausted; lookup returns the deepest terminal prefix and erase clears only the exact terminal. | Reject a flat masked-key map or full-key-only path by requiring distinct one-bit and two-bit prefixes to match the same query at different depths. |
| `alternating-cuckoo-stash` | `AlternatingCuckooStash(size_t per_table,size_t stash); bool insert(int,int); optional<int> find(int) const; bool erase(int); vector<int> stash_keys() const;` | Two tables/two hashes, bounded alternating displacement, then bounded stash. Duplicate replaces; insertion rollback is atomic when stash is full. | Reject single-table probing with a generated displacement cycle and rollback check. |
| `neighborhood-hop-bitmap` | `NeighborhoodHopBitmap(size_t slots,size_t neighborhood); bool insert(int,int); optional<int> find(int) const; bool erase(int); vector<uint64_t> hop_bits() const;` | Move an empty slot backward through neighborhood swaps and maintain home-bucket bitmaps. Invalid neighborhood 1 or >64; duplicate replaces; full false. | Reject plain linear probing with an entry found only through its home hop bitmap after relocation. |
| `serial-probe-pair-multimap` | `SerialProbePairMultimap(size_t slots); bool add(int,int); bool erase_one(int,int); vector<int> values(int) const; size_t tombstones() const;` | Store duplicate key/value pairs in probe order with tombstones; exact duplicate rejected; values preserve insertion serial despite wrap. Full false; absent erase false. | Reject stop-at-first-tombstone lookup with wrapped collision and deletion. |
| `clustered-remainder-counter` | `ClusteredRemainderCounter(size_t slots,uint8_t remainder_bits); bool add(uint64_t); bool remove(uint64_t); uint16_t count(uint64_t) const; vector<uint16_t> run_lengths() const;` | Maintain quotient-cluster metadata and sorted remainder runs with saturating counts. Invalid bit width/overflowing count rejected; absent remove false. | Reject independent modulo counters using two hashes sharing quotient but different remainders. |
| `arena-generation-interner` | `ArenaGenerationInterner(size_t bytes,size_t slots); optional<uint32_t> intern(string_view); optional<string> resolve(uint32_t) const; bool release(uint32_t); size_t bytes_used() const;` | Own a byte arena plus open-address index and generation IDs; equal live strings share ID/refcount, released space coalesces, stale IDs absent. Empty string valid. | Reject hash-only identity with colliding strings and stale-ID reuse. |
| `restart-prefix-key-block` | `RestartPrefixKeyBlock(size_t bytes,size_t restart); bool append(string); optional<string> at(size_t) const; optional<size_t> lower_bound(string_view) const; vector<size_t> restarts() const;` | Append strictly increasing strings using prefix/suffix encoding and full restart keys every `restart`; atomic false on capacity. Empty key valid; duplicate/out-of-order invalid. | Reject previous-key-only decoding by random access beginning at the required restart. |
| `atomic-dual-key-index` | `AtomicDualKeyIndex(size_t cap); bool link(int,int); bool unlink_left(int); bool unlink_right(int); optional<int> right_of(int) const; optional<int> left_of(int) const;` | Own two open-address indexes sharing one slot record and enforce one-to-one mapping atomically. Duplicate identical link true; conflicting side false; full false. | Reject independently updated maps by attempting a conflict and comparing both directions unchanged. |
| `epoch-clear-dense-set` | `EpochClearDenseSet(size_t universe,size_t cap); bool insert(size_t); bool erase(size_t); bool contains(size_t) const; void clear(); vector<size_t> dense() const;` | Dense/sparse arrays plus generation stamps make clear O(1); erase swaps last into hole. Invalid value throws; duplicate false; insertion order changes only through swap erase. | Reject zeroing sparse entries on clear via an operation-count invariant and generation wrap recovery test. |
| `rank-select-bit-directory` | `RankSelectBitDirectory(size_t bits); bool set(size_t); bool clear(size_t); size_t rank(size_t) const; optional<size_t> select(size_t) const; size_t ones() const;` | Own fixed bit words plus per-word population summaries; rank consumes full block counts and select skips summarized blocks before scanning one word. | Reject a linear unsummarized bit set by mutating a bit without refreshing its block count. |

### Bounded history and recovery mechanisms (41–50)

| ID | Public surface summary | Required mechanism and behavior | Deterministic discriminator |
| --- | --- | --- | --- |
| `inverse-mutation-journal` | `InverseMutationJournal(size_t records); bool set(int,int); optional<int> get(int) const; size_t mark() const; bool rollback(size_t); vector<pair<int,int>> state() const;` | Log inverse records for each mutation; a mark is a journal sequence, rollback applies inverses in reverse and discards later marks. Full journal makes set fail atomically. | Reject snapshot-per-mark storage through a private record-count invariant and interleaved key rewrites. |
| `retained-version-window` | `RetainedVersionWindow(size_t versions); bool publish(uint64_t,int); optional<int> at(uint64_t) const; bool retain_from(uint64_t); vector<uint64_t> versions() const;` | Store strictly increasing version/value pairs in a circular window without overwrite until prefix retention advances. Duplicate/out-of-order invalid; absent false; version overflow checked. | Reject modulo-only versions by querying a retired and then reused slot. |
| `checkpointed-delta-history` | `CheckpointedDeltaHistory(size_t units,size_t checkpoint_every); bool mutate(int,int); optional<int> read(size_t,int) const; vector<size_t> checkpoints() const;` | Store periodic full snapshots and intervening key deltas within a shared unit budget; reconstruction starts at nearest prior snapshot. Mutation evicts only complete oldest checkpoint segments. | Reject replay-from-current-state with historical reads across segment eviction. |
| `optimistic-reservation-transaction` | `OptimisticReservationTransaction(size_t units); optional<uint64_t> begin(size_t); bool write(uint64_t,int,int); bool commit(uint64_t); bool abort(uint64_t); vector<pair<int,int>> committed() const;` | Reserve units before staging key changes; commits apply atomically in key order, conflicts with keys changed since begin fail and release reservation. Invalid/stale transaction false. | Reject eager writes by observing committed state before commit and after conflict rollback. |
| `committed-prefix-ring-journal` | `CommittedPrefixRingJournal(size_t records); optional<uint64_t> append(int); bool commit_through(uint64_t); bool truncate_uncommitted(); size_t trim_committed(size_t); vector<int> committed() const;` | A fixed optional-record ring carries monotone LSNs and an explicit committed prefix; trim reclaims only committed head records and append reuses wrapped slots. | Reject commit-latest semantics because a gap prevents committed-prefix trimming and safe slot reuse. |
| `first-write-rollback-stack` | `FirstWriteRollbackStack(size_t cells); bool assign(size_t,int); optional<uint64_t> checkpoint(); bool restore(uint64_t); bool release(uint64_t); vector<int> values() const;` | Copy-on-write cells store per-checkpoint old values once; nested checkpoints restore/release only in stack order. Invalid cell throws; full undo storage makes assign false atomically. | Reject logging every write without first-write coalescing by repeated writes under a tight capacity. |
| `pending-result-idempotency-cache` | `PendingResultIdempotencyCache(size_t bytes); optional<Decision> begin(string_view,uint64_t); bool finish(uint64_t,vector<uint8_t>); optional<vector<uint8_t>> replay(string_view) const; bool evict_done(size_t);` | Keys map to pending tokens or completed byte results; repeated begin returns pending/completed decision, never a second token. Only oldest completed results may be evicted; pending never evicts. | Reject key-to-latest-token map with duplicate begin before finish. |
| `persistent-branch-node-history` | `PersistentBranchNodeHistory(size_t nodes); optional<uint64_t> fork(uint64_t); bool append(uint64_t,int); optional<uint64_t> merge(uint64_t,uint64_t); vector<int> materialize(uint64_t) const;` | Own bounded persistent parent-linked history nodes; fork shares prefix, append adds node, merge accepts only ancestor-compatible branches and appends unique suffix. Full false atomically. | Reject copied flat vectors through shared-node accounting and divergent-branch merge rejection. |
| `reader-epoch-reclamation-pool` | `ReaderEpochReclamationPool(size_t slots,size_t readers); optional<Handle> put(int); bool erase(Handle); void enter(size_t); void leave(size_t); size_t reclaim(); vector<int> live() const;` | Deleted slots receive retire epochs and reenter the free list only when all active reader epochs are newer. Invalid reader throws; stale handles false; nested enter invalid. | Reject immediate reuse by holding one reader across erase and exhausting all other slots. |
| `sealed-dual-bank-log` | `SealedDualBankLog(size_t records); bool append(int); bool seal(); void inject_partial_seal(); vector<int> recover() const; size_t active_bank() const;` | Alternate banks only after writing records, checksum, and final generation seal; recovery selects highest valid sealed generation and ignores partial newer bank. Full active bank requires seal. | Reject newest-generation-only recovery with an injected partial seal. |

### Partitioning and capacity-policy mechanisms (51–60)

| ID | Public surface summary | Required mechanism and behavior | Deterministic discriminator |
| --- | --- | --- | --- |
| `largest-remainder-quota-table` | `LargestRemainderQuotaTable(size_t slots,vector<size_t> weights); vector<size_t> quotas() const; bool resize(size_t);` | Allocate integer quotas by largest remainder using overflow-safe products; ties use tenant index and every positive weight gets no implicit minimum. Resize recomputes atomically; all-zero weights invalid. | Reject floor-only division when remainders determine the last slots. |
| `neighbor-borrowing-lane-array` | `NeighborBorrowingLaneArray(size_t slots,size_t lanes); bool push(size_t,int); optional<int> pop(size_t); vector<size_t> limits() const; bool rebalance();` | Each lane has a base reservation and may borrow contiguous free slots from its clockwise neighbor; rebalance repays empty borrowed tails without moving live elements. Invalid lane throws. | Reject global queue capacity by blocking a nonadjacent borrow despite global free slots. |
| `highest-score-node-directory` | `HighestScoreNodeDirectory(size_t slots); bool add_node(int,uint64_t); bool remove_node(int); optional<int> owner(uint64_t) const; vector<size_t> loads(vector<uint64_t>) const;` | For each bounded virtual slot choose highest overflow-safe rendezvous score among live nodes; node add/remove changes no stored keys because ownership is computed. Duplicate node false; no nodes absent. | Reject key modulo node count with a fixed removal-stability fixture. |
| `rectangle-generation-grid` | `RectangleGenerationGrid(size_t rows,size_t cols); optional<RectLease> reserve(size_t,size_t); bool release(RectLease); vector<size_t> row_free() const;` | Find lowest-row/lowest-column all-free rectangle using per-row run summaries; reservation is atomic across stripes and leases carry generations. Invalid/oversize absent; stale release false. | Reject row-independent reservation with a rectangle whose rows have disjoint free spans. |
| `replay-safe-escrow-ledger` | `ReplaySafeEscrowLedger(vector<size_t> grants); bool transfer(size_t,size_t,size_t,uint64_t); bool spend(size_t,size_t); vector<size_t> balances() const;` | Transfers carry unique sequence IDs and atomically move bounded rights; duplicate sequence replays prior decision, insufficient rights false, arithmetic overflow throws. | Reject debit-then-credit mutation using an overflowing destination and unchanged balances. |
| `summary-tree-free-index` | `SummaryTreeFreeIndex(size_t slots); bool occupy(size_t); bool release(size_t); optional<size_t> first_free(size_t) const; size_t free_count(size_t,size_t) const;` | Maintain a multi-level summary tree of free bits for logarithmic successor and range counts. Invalid indices/ranges throw; duplicate operation false; absent successor null. | Reject linear scan through a private visited-summary-node upper bound on a large sparse index. |
| `surplus-donor-lease-pool` | `SurplusDonorLeasePool(vector<size_t> reserved,size_t shared); optional<Lease> acquire(size_t); bool release(Lease); bool recall(size_t); vector<size_t> borrowed() const;` | Tenants use reservation, then shared, then borrow unused reservation from highest-surplus tenant; recall blocks new borrowing and reclaims only as borrowed leases return. | Reject undifferentiated reserve accounting with deterministic donor selection and recall trace. |
| `minimum-watermark-record-log` | `MinimumWatermarkRecordLog(size_t units,size_t consumers); bool append(uint64_t,size_t); bool acknowledge(size_t,uint64_t); size_t reclaim(); vector<uint64_t> retained() const;` | Variable-unit records reclaim only below the minimum monotone consumer watermark; append never overwrites retained records. Invalid consumer/retrograde ack false; sequence contiguous. | Reject maximum-watermark reclamation while one lagging consumer still needs a record. |
| `packed-priority-unit-shelf` | `PackedPriorityUnitShelf(size_t units); bool put(int,size_t,int); bool reprioritize(int,int); bool erase(int); vector<int> layout() const;` | Variable-width items occupy a packed shelf; admission compacts then evicts lowest priority, ties newest ID, until fit. Reprioritize is stable and atomic; oversize false. | Reject eviction-before-compaction when holes alone suffice for a new item. |
| `rollback-spill-routing-banks` | `RollbackSpillRoutingBanks(vector<size_t> banks); bool put(size_t,int); optional<int> take(size_t); vector<vector<int>> layout() const;` | Insert into requested bounded bank, then spill along a fixed acyclic routing graph to the first bank with room while preserving within-bank order; on no route, rollback all moves. | Reject global-first-free placement and non-atomic cascade failure with a three-bank trace. |

## Starter, reference, and file roles

For task ID `x`, `files.solution` is exactly `["x.h", "x.cpp"]` and
`files.example` is exactly `[".meta/example.h", ".meta/example.cpp"]`.
The public header contains only the declared API and necessary public value
types. The starter source defines every method but throws
`std::logic_error("not implemented")` or returns an obviously incomplete empty
value. It contains no production helper or answer fragment. The reference owns
the named mechanism directly; standard containers are permitted only for
output values, incidental lookup, or independent test models and may not
replace the advertised storage mechanism.

`.docs/introduction.md` and `.docs/instructions.md` are prompt-visible.
References, tests, CMake, provenance, config, receipts, controls, and negative
sources are private. Prompt construction must prove that no `.meta`, test,
CMake, receipt, or provenance path/content enters the prompt, and the exact
assistant reference must list the header then source and no other file.

## Diversity and adversarial clone contract

The owner must reread actual emitted artifacts and compare all `60 * 59 / 2 =
1770` unordered pairs. Each pair must differ in every dimension separately:

1. normalized public API shape and observable state;
2. necessary owned state and substantive algorithm;
3. mutation, admission, selection, and reclamation rules;
4. invalid, duplicate, absent, full, empty, boundary, tie, and overflow rules;
5. identifier/literal-neutral reference control-flow and state-use graph;
6. deterministic visible/private oracle assertions and trace model; and
7. compiled topic-specific false substitute and its rejection witness.

No aggregate score can pass a pair that fails one dimension. The normalizer
removes comments, strings, task/domain names, identifiers, literals, capacity
constants, endpoint direction, and error text while retaining type/arity,
state-use, control flow, operation relations, and assertions. Every dimension
must have nonempty evidence and a positive candidate/control separation margin.

Create three complete controls from `rollback-spill-routing-banks`: a domain and
identifier rename, a capacity-policy-only change, and an opposite-end
selection change. Each control must change the intended emitted files, remain
role-safe, compile, and pass its own two normal and two sanitizer behavior
tests. The exact production pair evaluator must reject each control in all
seven dimensions. Focused tests independently tokenize/extract evidence and
inspect all 1770 per-dimension decisions without calling the production feature
helper.

## Existing-tree and benchmark screen

Before writing, freeze sorted inventories and hashes for both existing trees
and the current expansion tree. Refuse any exact task ID, prompt hash,
starter hash, reference hash, test hash, explicit lineage, or normalized
semantic-contract conflict. Compare docs, API, reference control flow, tests,
and oracle relations—not just slugs. Refuse symlink/hardlink output and any
output outside the exact expansion family. No `--force` option weakens these
checks.

Screen the exact 26 official C++ holdout IDs and, when the pinned checkout is
available, their normalized prompt/API/reference/test contracts. In
particular, the official `circular-buffer` contract is excluded: no root is a
FIFO read/write buffer with full-write reject/overwrite behavior.

## Build, oracle, and receipt

Creator preflight must regenerate from the owner, pass focused tests, validate
whole-file response boundaries, execute all 60 false substitutes, pass the
1770-pair family screen and cross-tree/holdout screens, then run the exact tree
in the pinned repository C++ sanity image with `--network none`. Each root and
each coherent control must discover and pass exactly two CTests in a clean
normal build and a separate fresh ASan/UBSan build. Every false substitute must
compile with the same warnings and be rejected by at least one executed test
in both modes.

The owner also provides a host-only verification mode (`--verify-host`) that
runs the same per-root contract on the host toolchain: clean normal and fresh
ASan/UBSan CMake/`Unix Makefiles` builds of each reference and each coherent
control, exactly two discovered CTests per mode, executed rejection of every
compiling false substitute in both modes, and a `.state/host-verify.json`
receipt binding the owner, tree, compiler path/version/hash, CMake version,
commands, and per-mode counts. Host evidence is `host_verify`, never a Docker
sanity or locked-oracle substitute; it requires a manifest from a current
`--verify-core` run and fails closed on owner/tree drift. Verify-only
invocations (no `--force`) are supported: the timestamped
`.state/source-inventory.json` snapshot is refreshed on every run while
generated task output keeps its drift protection.

The append-only cycle manifest and receipt bind curriculum, owner, focused
test, tree, prompt, editable files, starters, references, visible/private
tests, metadata, provenance, negative sources, controls, compiler path/version/
hash, CMake, image, network policy, commands, normal/sanitizer counts,
cross-tree inventories, holdout policy, family screen, and result digests.
Any owner, artifact, test, policy, or environment change invalidates earlier
receipts.

## Acceptance and non-claims

The requested count is satisfied only by exactly 60 current roots with no
`review`, `replace`, `reject`, collision, contamination, or unresolved
hard-gate disposition. A clean creator preflight is followed by a read-only
independent audit. Findings route through immutable remedy records, owner
changes, complete regeneration, remediation verification, and a fresh audit of
the new exact tree. Only that fresh clean audit may report
`local_family_verified`.

Local completion does not create SFT JSONL, select a split, authorize training,
release a dataset, or establish benchmark uplift. Dataset handoff is
`not_requested`.

## Docs Alignment (Remediation Docs Phase)

The model-facing `.docs` follow the official Aider Polyglot C++ conventions.
`.docs/introduction.md` is a `# <Title>` header plus a domain-motivating
narrative about fixed-capacity storage, followed by the case summary. It never
states the contract or mentions the evaluation harness.
`.docs/instructions.md` starts with `# Instructions`, keeps the complete
Contract / Mechanism / Boundaries rules, adds a `## Examples` section
rendering the visible check's concrete cases, and phrases the mechanism
requirement naturally ("Build the mechanism directly: <substitute> cannot
reproduce the documented behavior.") instead of the "## Required mechanism"
scaffold and "must own the mechanism / may not replace" framing. The
generator's focused test asserts this docs shape and rejects meta/audit
vocabulary in both docs files.
