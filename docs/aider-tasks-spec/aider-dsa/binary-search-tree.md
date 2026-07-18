# Deterministic remedy specification: binary-search-tree family

## Scope and current evidence

This is the implementation specification for the generated family at
`.w8-biayn/data/aider-tasks/aider-dsa/binary-search-tree`.  It replaces no
task artifact in this change.  The family generator is
`src/w8_biayn/integrations/moonlight_binary_search_tree_aider_tasks.py`; its
focused structural regression is
`tests/test_moonlight_binary_search_tree_aider_tasks.py`; the prompt-facing
consumer is `src/w8_biayn/integrations/moonlight_aider_task_eval.py`; and the
legacy one-row converter is `moonlight_aider_task_sft.py`/
`moonlight_aider_tasks_sft.py`.  The permanent benchmark manifest is
`manifests/aider_sft/aider-polyglot-cpp-26.json` at Polyglot revision
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.

The current family has 20 roots, each with 12 files: two visible documents,
two editable starters, CMake, a visible test, two examples, a hidden test,
test metadata, configuration, and provenance.  Every current root is marked
`local task artifact; not admitted SFT data`.  `uv run pytest -q
tests/test_moonlight_binary_search_tree_aider_tasks.py` passed: **2 passed in
0.09s**.  That establishes generator/output and whole-file-answer shape only;
it is not an oracle, contamination, SFT, release, or benchmark result.

The manifest lists `binary-search-tree` as a permanent holdout.  The current
task IDs do not equal that slug, and this review found no copied official asset
in the generated roots.  That is not a passing semantic screen.  Every
replacement below remains `benchmark_screen: pending` until the repository
contamination gate compares its instructions, API, starter, reference, and
tests with the frozen manifest and all current/released families.

| Current root | Current special operation | Disposition | Replacement root and family |
| --- | --- | --- | --- |
| `bst-access-key-registry` | count | replace | `bst-access-key-leases-v2` / `bst-access-key-leases-v2` |
| `bst-appointment-index` | inclusive starts | replace | `bst-appointment-reservations-v2` / `bst-appointment-reservations-v2` |
| `bst-auction-bids` | strict floor | replace | `bst-auction-order-book-v2` / `bst-auction-order-book-v2` |
| `bst-audit-timeline` | inclusive IDs | replace | `bst-audit-retention-log-v2` / `bst-audit-retention-log-v2` |
| `bst-cargo-weight-index` | nearest | replace | `bst-cargo-load-classes-v2` / `bst-cargo-load-classes-v2` |
| `bst-delivery-zones` | inclusive boundaries | replace | `bst-delivery-zone-rules-v2` / `bst-delivery-zone-rules-v2` |
| `bst-document-revision-index` | inclusive revisions | replace | `bst-document-revision-ledger-v2` / `bst-document-revision-ledger-v2` |
| `bst-energy-meter-readings` | range count/sum | replace | `bst-energy-reading-ledger-v2` / `bst-energy-reading-ledger-v2` |
| `bst-exam-score-index` | percentile | replace | `bst-exam-score-distribution-v2` / `bst-exam-score-distribution-v2` |
| `bst-flight-standby` | remove eligible | replace | `bst-flight-standby-queue-v2` / `bst-flight-standby-queue-v2` |
| `bst-library-catalog` | call-number range | replace | `bst-library-shelf-records-v2` / `bst-library-shelf-records-v2` |
| `bst-network-port-registry` | first free | replace | `bst-network-port-leases-v2` / `bst-network-port-leases-v2` |
| `bst-parking-space-index` | nearest | replace | `bst-parking-free-intervals-v2` / `bst-parking-free-intervals-v2` |
| `bst-price-book` | budget range | replace | `bst-price-level-book-v2` / `bst-price-level-book-v2` |
| `bst-scoreboard-ranks` | one-based rank | replace | `bst-scoreboard-player-ranks-v2` / `bst-scoreboard-player-ranks-v2` |
| `bst-sensor-thresholds` | threshold range | replace | `bst-sensor-hysteresis-rules-v2` / `bst-sensor-hysteresis-rules-v2` |
| `bst-ticket-number-index` | unresolved range | replace | `bst-ticket-priority-ledger-v2` / `bst-ticket-priority-ledger-v2` |
| `bst-transit-departures` | departure window | replace | `bst-transit-service-board-v2` / `bst-transit-service-board-v2` |
| `bst-version-catalog` | compatible release | replace | `bst-semver-release-catalog-v2` / `bst-semver-release-catalog-v2` |
| `bst-warehouse-bins` | vacant range | replace | `bst-warehouse-bin-inventory-v2` / `bst-warehouse-bin-inventory-v2` |

`replace` is required before a root can be selected: the existing objective is
not distinguishable from a trivial `std::set<int>` wrapper, and the 20 roots
are semantic/template duplicates.  No current root is retained, renamed, or
repaired in place.  A later benchmark-content overlap changes that replacement
root to `reject`; it must never be renamed to evade the holdout.

## Findings requiring replacement

1. **F1 — false BST objective (blocker):** all headers store
   `std::set<int> values_`; references delegate every operation to it.  The
   names claim a BST curriculum but neither prompt nor tests require a
   repository-owned node tree.
2. **F2 — twenty noun substitutions (blocker):** the generator has one
   `TaskSpec`, header renderer, reference renderer, starter renderer, test
   renderer, and CMake renderer.  Range, count, rank, promote, sum, nearest,
   floor, percentile, and first-free are all minor variants of the same
   positive unique-integer ordered-set contract.
3. **F3 — incomplete visible contract (major):** docs omit empty-result,
   endpoint, invalid-range, mutation, payload, and public-example rules.  In
   particular, `best_at_or_below` and `latest_not_newer_than` are described
   like floors while the generated common implementation returns a ceiling.
4. **F4 — tests do not prove the claim (blocker):** visible tests are one
   common trace; private tests add only a deterministic 180-step `std::set`
   comparison.  They do not observe nodes, ordering invariants, payload rules,
   duplicate policy beyond one key, or the advertised domain behavior.
5. **F5 — starter/reference incoherence (major):** every starter omits the
   declared special-operation definitions, while references use the banned
   container.  The current verifier checks only references, not the required
   starter-fails/reference-passes/applied-target-equals-reference ladder.
6. **F6 — roles and provenance are insufficient (major):** config omits
   `source` and attribution, omits the executable private-test role, and
   provenance has neither a license/usage decision, generator digest, stable
   family ID, nor a resolved benchmark decision.
7. **F7 — nonconforming build/oracle (blocker):** CMake uses hand-written
   mains and an `ALL` custom target instead of the repository C++17/Catch
   scaffold.  `verify()` uses host tools, does not select `Unix Makefiles` or
   the locked compiler, does not retain receipts, and does not require equal
   positive normal/sanitizer discovery.
8. **F8 — unsafe handoff route (blocker):** the old one-row converter can
   render `.meta/example.*` directly to JSONL and has no primary-pipeline
   provenance, contamination, target-application, token/mask, split, or
   producer/consumer proof.  It is not an admission route.

## Common replacement contract

Each replacement has exactly these editable files, in this response and
`files.solution` order: `<replacement-id>.h`, then `<replacement-id>.cpp`.
The header declares the public API only; the source owns all ordinary
definitions.  `.docs/introduction.md` states a domain scenario; `.docs/
instructions.md` states every rule in the relevant table below and includes
the two stated public examples.  Neither document identifies the task as a
diagnostic, a local artifact, a BST exercise, or a benchmark analogue.

All key, counter, timestamp, quantity, money-in-microunits, and rank values
are `std::int64_t`.  Inputs that a root calls positive reject `<= 0`; an
invalid input returns `false` or `std::nullopt` and has no mutation.  A failed
operation is atomic.  Vectors are sorted by the stated key comparator.  A
range with `first > last` is empty and is never normalized.  All arithmetic
uses checked `std::int64_t` addition/subtraction: an overflow returns
`std::nullopt` (query) or `false` (mutation), with no mutation.  Strings used
as IDs are nonempty ASCII `[A-Za-z0-9_-]+`; invalid IDs are treated as invalid
input.  No API throws for documented invalid input or performs I/O.

Every declaration in the next table is in `namespace curriculum`; its header
includes `<cstddef>`, `<cstdint>`, `<memory>`, `<optional>`, `<string>`,
`<string_view>`, `<utility>`, and `<vector>` exactly when a listed declaration
uses it. The private `Node` definition stays in the source file.

Each replacement owns a direct pointer-node binary-search tree:

```cpp
struct Node {
  Key key;
  Payload payload;
  std::unique_ptr<Node> left, right;
  std::size_t subtree_size;
  // only roots whose table says so also store subtree_sum, max_end, or max_free.
};
```

The exact ordering comparator is the table key.  Insertion, lookup,
predecessor, successor, in-order traversal, and deletion (leaf, one child,
two children) must operate on these nodes.  Two-child deletion replaces the
erased node with its in-order successor payload and removes that successor;
all affected augmentation is recomputed on return from recursion.  The
following are forbidden as indexed storage or as a substitute for the node
tree: `std::set`, `std::map`, `std::multiset`, `std::multimap`, every
`std::unordered_*`, GNU PBDS, Boost containers, third-party trees, a sorted
vector, and an array/list scanned as the authoritative index.  Tests may use a
simple vector of records as a behavior oracle only.

When compiled with `CURRICULUM_TESTING`, every header exposes only:

```cpp
struct TreeCheck { bool valid; std::size_t nodes; std::size_t height; };
TreeCheck validate_for_test() const;
```

`valid` means unique ownership; no cycles; strict comparator ordering; exact
`subtree_size`; exact root-specific augmentation; and a reported height equal
to recursive node height.  The implementation must not compile a test-only
method that merely returns a constant.  Private test source also performs a
source-policy scan for the forbidden container spellings and declares an
`invariant_not_enforced` failure for a missing/false validator, invalid
augmentation, sorted-vector substitute, legacy `std::set` wrapper, or a
deliberately malformed parent/child ordering fixture.

All references are independent readable node-tree implementations, not copied
starter bodies or test-specific case tables.  A reference may share the public
types but not implementation renderer functions or generated code bodies.

## Replacement APIs and behavior

The following declarations are complete.  Every listed record has ordinary
value semantics; returned records are copies.  `std::string_view` inputs are
validated using the ASCII rule above.  `key` names the exact BST comparator;
when it is composite, fields compare left-to-right.

| Replacement | Complete API, key, and required behavior |
| --- | --- |
| `bst-access-key-leases-v2` | `struct KeyLease { std::int64_t key, expires_at; std::string owner; }; class AccessKeyLeases { public: bool grant(KeyLease); bool revoke(std::int64_t key); std::optional<KeyLease> active_at(std::int64_t key, std::int64_t now) const; std::vector<KeyLease> expiring_in(std::int64_t first, std::int64_t last) const; std::size_t size() const; };` Key=`key`; `key` and `expires_at` are positive; unique key; grant rejects duplicate/invalid owner; active returns no value when absent or `expires_at < now`; expiry equality is active. `expiring_in` is inclusive by expiry. Example: key 7 expiring 10 is active at 10, not 11. |
| `bst-appointment-reservations-v2` | `struct Appointment { std::int64_t start, duration; std::string id; }; class AppointmentReservations { public: bool reserve(Appointment); bool cancel(std::string_view id); std::optional<Appointment> at_or_after(std::int64_t time) const; std::vector<Appointment> in_window(std::int64_t first, std::int64_t last) const; };` Key=`start`; all numeric fields positive, end is checked `start+duration`; IDs unique; intervals are half-open `[start,end)` and may touch but not overlap. `in_window` returns appointments whose start is in inclusive bounds. Node stores `max_end`; overlap search must use it. Example: `[10,15)` and `[15,20)` are valid; `[14,16)` is rejected. |
| `bst-auction-order-book-v2` | `struct BidLevel { std::int64_t price, quantity; }; class AuctionOrderBook { public: bool add(BidLevel); bool cancel(std::int64_t price, std::int64_t quantity); std::optional<BidLevel> best_not_above(std::int64_t limit) const; std::vector<BidLevel> levels(std::int64_t first, std::int64_t last) const; };` Key=`price`; add coalesces an existing level with checked quantity addition; cancel rejects absent/over-cancel and erases a level at zero; best is greatest price `<= limit`. Example: price 10 quantity 2 plus 3 becomes 5; cancelling 5 removes it. |
| `bst-audit-retention-log-v2` | `struct AuditEvent { std::int64_t sequence, retained_until; std::string category; }; class AuditRetentionLog { public: bool append(AuditEvent); bool erase(std::int64_t sequence); std::vector<AuditEvent> retained_at(std::int64_t now) const; std::optional<AuditEvent> before(std::int64_t sequence) const; };` Key=`sequence`; all numeric fields positive, category valid; sequence is unique; retained equality is retained; output is ascending sequence. Example: until 40 remains at 40 and is absent at 41. |
| `bst-cargo-load-classes-v2` | `struct LoadClass { std::int64_t maximum_weight; std::string code; }; class CargoLoadClasses { public: bool define(LoadClass); bool erase(std::int64_t maximum_weight); std::optional<LoadClass> classify(std::int64_t weight) const; };` Key=`maximum_weight`; positive maximum and valid unique code; code is also unique; classify returns least maximum `>= weight`; no class for nonpositive/too-heavy weight. Example: maxima 10,20 classify 10 as 10 and 11 as 20. |
| `bst-delivery-zone-rules-v2` | `struct ZoneRule { std::int64_t first, last; std::string zone; }; class DeliveryZoneRules { public: bool add(ZoneRule); bool remove(std::int64_t first); std::optional<ZoneRule> locate(std::int64_t address) const; };` Key=`first`; first/last positive and `first<=last`; zones valid; closed intervals may not overlap; locate returns the single containing rule. Node stores `max_end`. Example: `[1,10]` and `[11,20]` are valid; `[10,12]` is rejected. |
| `bst-document-revision-ledger-v2` | `struct Revision { std::int64_t number; std::string author, digest; }; class DocumentRevisionLedger { public: bool record(Revision); bool erase(std::int64_t number); std::optional<Revision> latest_not_after(std::int64_t number) const; std::vector<Revision> between(std::int64_t first, std::int64_t last) const; };` Key=`number`; positive unique number and valid strings; latest is greatest `<= number`, never a ceiling. Example: revisions 2,5 queried at 4 yields 2. |
| `bst-energy-reading-ledger-v2` | `struct Reading { std::int64_t timestamp, watt_hours; }; class EnergyReadingLedger { public: bool record(Reading); bool erase(std::int64_t timestamp); std::optional<std::int64_t> sum_between(std::int64_t first, std::int64_t last) const; std::size_t count_between(std::int64_t first, std::int64_t last) const; };` Key=`timestamp`; timestamps positive/unique; watt_hours is nonnegative; `sum_between` is inclusive and null only on invalid range or overflow; empty valid range has sum 0. Node stores checked `subtree_sum`. |
| `bst-exam-score-distribution-v2` | `class ExamScoreDistribution { public: bool add(std::int64_t score); bool remove(std::int64_t score); std::size_t count() const; std::optional<std::int64_t> percentile(std::int64_t percent) const; };` Key=`score`; scores are 0..100 inclusive and duplicates increment a node multiplicity; remove decrements/removes one occurrence; percentile accepts 1..100 and returns rank `ceil(percent*count/100)` in ascending multiset order. Node stores multiplicity and subtree size. Example: scores 10,10,90 have percentile(50)=10. |
| `bst-flight-standby-queue-v2` | `struct StandbyPassenger { std::string id; std::int64_t priority, sequence; }; class FlightStandbyQueue { public: bool enqueue(StandbyPassenger); bool withdraw(std::string_view id); std::optional<StandbyPassenger> promote(std::int64_t minimum_priority); };` Key=`(priority,sequence)`; priority/sequence positive, IDs unique; lowest eligible priority wins and lower sequence breaks a tie; promote removes exactly the returned passenger. Example: same priority sequences 4 then 9 promotes 4 first. |
| `bst-library-shelf-records-v2` | `struct ShelfRecord { std::string call_number, title; }; class LibraryShelfRecords { public: bool shelve(ShelfRecord); bool withdraw(std::string_view call_number); std::optional<ShelfRecord> first_at_or_after(std::string_view call_number) const; std::vector<ShelfRecord> section(std::string_view first, std::string_view last) const; };` Key=bytewise unsigned-ASCII lexical `call_number`; all strings valid; call number unique; invalid/reversed lexical range is empty. Example: `A-2` sorts before `A-10` because comparison is bytewise. |
| `bst-network-port-leases-v2` | `struct PortLease { std::int64_t first, last; std::string owner; }; class NetworkPortLeases { public: bool reserve(PortLease); bool release(std::int64_t first); std::optional<std::int64_t> first_free(std::int64_t first, std::int64_t last) const; };` Key=`first`; ports are 1..65535; closed lease ranges do not overlap; exact `first` identifies a lease; first_free returns the least unleased port in inclusive bounds. Node stores `max_end`; valid range `[10,12]` plus `[14,14]` yields 13. |
| `bst-parking-free-intervals-v2` | `struct FreeInterval { std::int64_t first, last; }; class ParkingFreeIntervals { public: bool release(FreeInterval); bool occupy(std::int64_t space); std::optional<std::int64_t> nearest_free(std::int64_t request) const; };` Key=`first`; positive closed intervals are stored maximal and disjoint; release rejects any overlap but coalesces touching intervals; occupy splits/removes its containing interval. Nearest uses absolute distance with a lower-number tie; difference is checked. Example: release `[4,5]`, `[6,7]` stores `[4,7]`; occupy 5 leaves `[4,4]`,`[6,7]`. |
| `bst-price-level-book-v2` | `struct PriceLevel { std::int64_t price, available; }; class PriceLevelBook { public: bool upsert(PriceLevel); bool consume(std::int64_t price, std::int64_t amount); std::optional<PriceLevel> best_not_above(std::int64_t budget) const; };` Key=`price`; both fields positive; upsert replaces availability at a price; consume rejects absent/over-consumption and removes at zero; best is greatest `<= budget`. Example: level 20 is returned for budget 20, not skipped. |
| `bst-scoreboard-player-ranks-v2` | `struct PlayerScore { std::string player; std::int64_t score; }; class ScoreboardPlayerRanks { public: bool upsert(PlayerScore); bool erase(std::string_view player); std::optional<std::size_t> rank_of(std::string_view player) const; std::vector<PlayerScore> top(std::size_t count) const; };` Key=`(-score,player)`; player valid, score nonnegative, player unique; rank is one-based in descending score then lexical player order; `top(0)` is empty. Node stores subtree size; an auxiliary direct ID lookup is forbidden, so erase/find must traverse the tree. |
| `bst-sensor-hysteresis-rules-v2` | `struct HysteresisRule { std::int64_t enter_at, exit_at; std::string mode; }; class SensorHysteresisRules { public: bool add(HysteresisRule); bool remove(std::int64_t enter_at); std::optional<HysteresisRule> active_rule(std::int64_t value) const; };` Key=`enter_at`; values positive with `exit_at < enter_at`, valid mode, and unique enter threshold; active rule is greatest enter threshold `<= value`; none before the first. Example: enter 20/exit 15 activates at 20 and candidate selection stays that rule at 21. |
| `bst-ticket-priority-ledger-v2` | `struct Ticket { std::int64_t number, priority; std::string owner; }; class TicketPriorityLedger { public: bool open(Ticket); bool close(std::int64_t number); std::optional<Ticket> next_for(std::string_view owner) const; std::vector<Ticket> priority_range(std::int64_t first, std::int64_t last) const; };` Key=`(priority,number)`; positive unique number/priority and valid owner; lowest priority then number wins; closing is by ticket number and must locate/delete the composite key without an auxiliary map. |
| `bst-transit-service-board-v2` | `struct Departure { std::int64_t time; std::string route; }; class TransitServiceBoard { public: bool add(Departure); bool cancel(std::int64_t time, std::string_view route); std::optional<Departure> next(std::int64_t time) const; std::vector<Departure> window(std::int64_t first, std::int64_t last) const; };` Key=`(time,route)`; time positive, route valid, pair unique; `next` is least key whose time is `>=` query and uses lexical route tie; window includes all departures with inclusive time bounds. |
| `bst-semver-release-catalog-v2` | `struct Version { std::int64_t major, minor, patch; }; class SemverReleaseCatalog { public: bool publish(Version); bool withdraw(Version); std::optional<Version> latest_compatible(Version) const; };` Key=lexicographic `(major,minor,patch)`; components nonnegative; unique version; compatible means same major and `<=` requested minor/patch; query with no same-major published compatible version returns null. Example: 2.1.0 is not compatible with 1.99.99. |
| `bst-warehouse-bin-inventory-v2` | `struct Bin { std::int64_t id, capacity; std::string sku; }; class WarehouseBinInventory { public: bool store(Bin); bool remove(std::int64_t id); std::optional<Bin> first_fitting(std::int64_t minimum_capacity) const; std::vector<Bin> aisle(std::int64_t first, std::int64_t last) const; };` Key=`id`; IDs/capacities positive, SKU valid, IDs unique; `first_fitting` is the least ID whose capacity is at least the request, not simply the first ID at/after capacity. Node stores subtree `max_capacity`; range is inclusive ID order. |

For each row, the required public examples are the example in its cell and a
second boundary example: empty tree returns `std::nullopt`/empty vector/zero
count as its return type dictates; no mutation follows any rejected call.
The visible documents must state both examples verbatim in prose, without
revealing reference code or private test data.

## Deterministic tests, oracle, and acceptance

Each root has exactly eight Catch2 test cases: `public_examples`,
`invalid_and_atomic`, `duplicate_or_payload_update`, `deletion_shapes`,
`ordering_and_boundaries`, `domain_special_rule`, `deterministic_trace`, and
`invariant_and_negative_fixtures`. For interval roots,
`domain_special_rule` covers overlap/coalescing; for augmented roots, it
covers the augmentation query. `tests.toml` names only those executed groups
and does not claim random testing or balancing. Normal and sanitizer
discovery must each report exactly eight tests for every replacement root.

For the trace, use the root seed in table order from `0xB57A1001` through
`0xB57A1014`.  Execute exactly 4,096 steps with unsigned-32 wraparound:

```text
state = state * 1664525U + 1013904223U       # draw 1
op = state % 8
state = state * 1664525U + 1013904223U       # draw 2
key_a = 1 + state % 997
state = state * 1664525U + 1013904223U       # draw 3
key_b = 1 + state % 997
state = state * 1664525U + 1013904223U       # draw 4
payload_index = state % 31
```

Operations 0..7 are, respectively: root-specific insert/upsert; root-specific
erase/remove; exact lookup; predecessor/floor; successor/ceiling; range or
aggregate query; root-specific special query; and no-op validation.  For
composite/string records, `payload_index` chooses the ASCII ID `id-00` through
`id-30`; intervals use `min(key_a,key_b)`/`max(key_a,key_b)`; semver uses
`(key_a % 4, key_b % 20, payload_index)`.  The private oracle is a sorted
`std::vector` of value records implementing the table comparator, interval
overlap, multiplicity, and aggregate rules directly.  It compares every
public return and complete in-order result after each step and calls
`validate_for_test()` after every mutation.  This is deterministic
property-testing evidence, not test content to place in a prompt.

Each root must include these negative fixtures and prove they fail: the old
`std::set<int>` wrapper; a sorted-vector implementation; a node tree with one
bad child ordering; an augmentation-stale variant where applicable; and a
previously plausible domain error (inclusive/exclusive endpoint, duplicate
coalescing, overlap, tie, or overflow as appropriate).  The old generator's
reference must also fail the new API compile test.  The independent reference
must pass every normal and sanitizer test.  These are acceptance conditions
for every replacement, not optional quality checks.

## Files, metadata, build, and handoff gates

The generator must create fresh roots rather than overwrite current roots.
For every replacement, roles are:

| Role | Exact path |
| --- | --- |
| visible documentation | `.docs/introduction.md`, `.docs/instructions.md` |
| editable files | `<replacement-id>.h`, `<replacement-id>.cpp` |
| visible Catch test | `<replacement-id>_test.cpp` |
| private Catch test | `.meta/<replacement-id>_private_test.cpp` |
| reference mapping | `.meta/example.h`, `.meta/example.cpp` |
| role/test/provenance metadata | `.meta/config.json`, `.meta/tests.toml`, `.meta/provenance.json` |
| support/build | `CMakeLists.txt`, content-addressed repository C++17/Catch scaffold |

`config.json` must declare safe, existing, mutually exclusive `files.solution`
in header/source order, `files.test` including both test sources through a
private-test role, and two unambiguous examples.  It must also contain a
meaningful blurb, clean-room source, attribution, `task_spec_revision: 2`,
the new family ID, and C++17 language identity.  Provenance must bind
clean-room authoring method, license/usage result, source inventory ID,
generator path/revision hash, parent-current-root ID, benchmark decision,
and the SHA-256 of this document.  It must not call a root admitted before
the lifecycle succeeds.

Use the repo-owned C++17 Catch scaffold.  In the locked, network-disabled
grader image, configure the starter, normal reference, applied target, and a
fresh sanitizer reference using `-G "Unix Makefiles"` and the fingerprinted
compiler.  Discover Catch tests separately from compilation; require positive
and equal normal/sanitizer counts; run Catch without CTest/default-`ALL`
ambiguity; and preserve receipts for task tree, reference mapping, generator,
image, compiler path/version/hash, CMake/Catch identities, flags, seccomp
policy, commands, output hashes, names/counts, duration, and exit status.
The current host verifier is not an acceptable substitute.

Before a replacement can be released, the primary `future approved admission`
lifecycle must: freeze identities; inventory license/provenance; run the
normal/sanitizer oracle; run whole-slug and semantic contamination plus family
screens; select indivisible family splits; render code-only whole-file targets
in lexicographic normalized path order; apply them to a clean starter and
byte-compare both editable files to the reference; enforce the 8,192-token
limit and `w8-aider-sft-mask-v2`; finalize and producer-verify; export a
private-asset-free bundle; then `verify-export` it with the pinned
model/tokenizer/template/adapter identities.  The legacy one-row converter is
forbidden.  These gates must fail with the documented primary reason codes,
including `benchmark_content_overlap`, `duplicate_family`,
`invariant_not_enforced`, `prompt_contract_incomplete`,
`target_reference_mismatch`, and `consumer_token_evidence_mismatch`.

## Ordered implementation plan and non-claims

1. Write one immutable `.state/remedy/<replacement-id>.json` for each current
   root with `schema_version: aider-task-remedy-v1`, the pre-change tree and
   generator hashes, the `replace` disposition, sorted `F1`–`F8`, this
   document hash, and pending benchmark/license screens.
2. Replace the BST generator with an independent v2 renderer and focused tests;
   do not import the old renderer, reference, tests, CMake, or balanced-tree
   renderer.  Materialize the 20 new IDs in fresh scratch output.
3. Implement the exact visible contracts, node trees, independent references,
   Catch tests, policy scans, metadata, and scaffold above; regenerate roots.
4. Prove structural/prompt boundaries and every named negative fixture; then
   run the locked normal and sanitizer reference/application oracle and retain
   receipts.
5. Run the benchmark, duplication, and family screens.  Reject any root with
   an official or semantic holdout match; do not select more than one member
   of an unresolved semantic family.
6. Run renderer, target-application, token/mask, split, producer, export, and
   consumer verification.  Only then may records become `local_scope_only`.

This document does not claim that any current or replacement root is oracle
verified, training-suitable, local-scope-only, benchmark-safe, or capable of
benchmark uplift.  It does not authorize implementation, generation, training,
or conversion of these artifacts in this change.
