# Binary Search Tree Family: Deterministic Audit and Remedy Specification

## Audit basis and current evidence

This is the implementation specification for
`.w8-biayn/data/aider-tasks/aider-dsa/binary-search-tree/`. This change
replaces only this Markdown document; it does not modify a generator, task,
test, dataset, or release artifact.

| Inspected input | Identity |
| --- | --- |
| owner | `src/w8_biayn/integrations/moonlight_binary_search_tree_aider_tasks.py`, SHA-256 `af2e01e797f7a4d24020d6bd78cececb653c5b1d6981964146919f3168cedc20` |
| focused test | `tests/test_moonlight_binary_search_tree_aider_tasks.py`, SHA-256 `782e116b261ed8515d9f22fd70cf993feff7bbf37f27cca91cc68182ecbd9fa5` |
| curriculum | `docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BINARY_SEARCH_TREE_CURRICULUM.md`, SHA-256 `c8eadad5263afdbec90f4ddd4ae740b5853ff574993c4898ab97d867cfa74fc3` |
| holdout manifest | `manifests/aider_sft/aider-polyglot-cpp-26.json`, SHA-256 `7b461f45ae89e2b48390b87ba4bed548d2c39c2c065118c5caa5ad675af313b9`, revision `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f` |
| generation prompt | `docs/aider-tasks-spec/prompts/generate-family-spec.md`, SHA-256 `654f7c7d1154762a195125215e7a73a824b21e84933233967331e22c4be5aeb0` |
| remedy policy | `docs/aider-tasks-spec/verify-and-remedy.md`, SHA-256 `b70619418f188c0063b4e0698776c7f22ca6aa9ca7b908a12ab501f364111208` |

There are 20 roots and 12 files per root. The focused pytest passed
(`2 passed`), and reconstructed prompt boundaries passed for all 20 roots:
only the two `.docs` files and two `files.solution` paths are exposed. Those
facts establish present generator shape only.

Mechanical inspection also found:

- all 20 references store the authoritative index in `std::set<int>`;
- zero references define a repository-owned BST node;
- all 20 hidden tests use `std::set<int> oracle` for 180 steps;
- no hidden test observes nodes, ownership, ordering, deletion shape, or
  augmentation;
- all 20 CMake files use an `ALL` custom target and a host verifier;
- all configs omit source/attribution and an executable private-test role;
- no root has durable locked normal-plus-fresh-sanitizer receipts;
- exact task slugs differ from official `binary-search-tree`, but semantic
  contamination screening is still pending.

The strongest truthful conclusions are: artifacts exist and pass their present
focused test; they are not locally oracle-verified; training suitability,
release readiness, and benchmark uplift are not claimed.

## Priority-1 core-objective audit

The advertised mechanism is a directly owned, pointer-linked, unbalanced binary
search tree whose operations traverse and mutate repository-owned nodes. The
current substantive implementation is `values_` plus delegated
`std::set<int>` calls in `.meta/example.h`. The easiest false substitute is
that exact wrapper.

Every current root has
`primary_core_objective: not_achieved`. Compilation, examples, documentation,
and current test success do not alter this result. Each planned replacement
uses shared family ID `aider-dsa-binary-search-tree-v2`, task-spec revision
`1`, and a new ID under
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree/`. No current
root may be overwritten or described as repaired.

| Current root | Tree hash before | Primary evidence/result | Disposition | Replacement |
| --- | --- | --- | --- | --- |
| `bst-access-key-registry` | `sha256:f296035983d201ad417e2cab95902e98cbd752d80f6776fa980f617a2c316eff` | set wrapper/set oracle; `not_achieved` | `replace` | `bst-access-key-leases-v2` |
| `bst-appointment-index` | `sha256:003be55a3f0ade9545e4c6eb3969239e2b6c3dc0dc997c519f0127bfaa0b0d1c` | same; `not_achieved` | `replace` | `bst-appointment-reservations-v2` |
| `bst-auction-bids` | `sha256:8babf28dcd91037a3ceabfabfb553c6367e817752768597e8a84c27753a5fe7f` | same; `not_achieved` | `replace` | `bst-auction-order-book-v2` |
| `bst-audit-timeline` | `sha256:228faf8ee1ee088ffe4107bf3350026116f531598cf5e46118d02cdbed02a22a` | same; `not_achieved` | `replace` | `bst-audit-retention-log-v2` |
| `bst-cargo-weight-index` | `sha256:89e9c88c0a15c2e5b91b60813436d50ba792e0be281339b9b2eae96dd5097fb3` | same; `not_achieved` | `replace` | `bst-cargo-load-classes-v2` |
| `bst-delivery-zones` | `sha256:a9121f5c126ab96d083525219975b01503f3ca6433fb937a819a380da0fb5b2d` | same; `not_achieved` | `replace` | `bst-delivery-zone-rules-v2` |
| `bst-document-revision-index` | `sha256:0064ed1799dbfc9e5ae1ef21ea99bd75b619e52940318825ad4be305b9aff8d7` | same; `not_achieved` | `replace` | `bst-document-revision-ledger-v2` |
| `bst-energy-meter-readings` | `sha256:f1da632f532470034a0923cc6f03bed2c7a918967bbec870f010d743f74c8db5` | same; `not_achieved` | `replace` | `bst-energy-reading-ledger-v2` |
| `bst-exam-score-index` | `sha256:770717ca3c656759061453093ef1a6755d9dbd2e5745190e2b06f56342b9e5f0` | same; `not_achieved` | `replace` | `bst-exam-score-distribution-v2` |
| `bst-flight-standby` | `sha256:f63d4b2edb3f89efee1e6998221c2e3d63718ca4a377e6262e047ac61d09b05c` | same; `not_achieved` | `replace` | `bst-flight-standby-queue-v2` |
| `bst-library-catalog` | `sha256:a1b44593366c3d632e7c3dce2ef28679a83f4234f0682ccc8b7187250e1aad1e` | same; `not_achieved` | `replace` | `bst-library-shelf-records-v2` |
| `bst-network-port-registry` | `sha256:0d72f17126943c66a541723ec43c49ae33dbba944b408ac45cae64bc25b21ff8` | same; `not_achieved` | `replace` | `bst-network-port-leases-v2` |
| `bst-parking-space-index` | `sha256:782ae158c4ab9d487226843ac5ef2adaf49eb81d500681fdd5f454d1d910bc39` | same; `not_achieved` | `replace` | `bst-parking-free-intervals-v2` |
| `bst-price-book` | `sha256:671dd50cdaab1667b97e528c43d6b070a0011396ae96df813e61d82f15cecb48` | same; `not_achieved` | `replace` | `bst-price-level-book-v2` |
| `bst-scoreboard-ranks` | `sha256:59df853edcf58201066679df76b0258f2400b6b31484f90fc1697f9ebca82837` | same; `not_achieved` | `replace` | `bst-scoreboard-player-ranks-v2` |
| `bst-sensor-thresholds` | `sha256:edd7df3fe8fa599557b62aad38839dd714c439a2c79fac1b65558fcb3d55795a` | same; `not_achieved` | `replace` | `bst-sensor-hysteresis-rules-v2` |
| `bst-ticket-number-index` | `sha256:dbccd714de0053e2d5549f06231a280ef6eb9f9f8ba612241bfb1c7f0dd21a5b` | same; `not_achieved` | `replace` | `bst-ticket-priority-ledger-v2` |
| `bst-transit-departures` | `sha256:dbc2160a2b3eb72b218b083dd94255a9bb9b76217deb6923ddb21c3111fe792f` | same; `not_achieved` | `replace` | `bst-transit-service-board-v2` |
| `bst-version-catalog` | `sha256:1896656053f59f6a429b03fb5a19d8540b40a0c5a813d0974f622ba9f4412e18` | same; `not_achieved` | `replace` | `bst-semver-release-catalog-v2` |
| `bst-warehouse-bins` | `sha256:b8b8b5ca18c510894aa83a623152838a054ba6f484af705b90f01a96338491c7` | same; `not_achieved` | `replace` | `bst-warehouse-bin-inventory-v2` |

Current provenance says `newly-authored in-repository` and names
`w8-biayn`, but records no license/usage decision. Every record therefore
starts `license_screen: pending`. Before generation, resolve it. A reject
result changes the disposition to `reject`, writes a rejection receipt, and
stops; it cannot be waived or deferred.

## Secondary findings

These remain mandatory but cannot obscure the failed core objective:

- **S1:** one renderer produces 20 semantic ordered-set noun variants.
- **S2:** docs omit invalid, empty, duplicate, endpoint, payload, atomicity, and
  overflow rules; some floor/ceiling prose disagrees with implementation.
- **S3:** the common visible trace and 180-step set oracle do not discriminate a
  node tree from the forbidden wrapper.
- **S4:** starters omit special methods; references use the banned substitute;
  no starter-fails/reference-passes/applied-target-equals-reference ladder.
- **S5:** config/provenance omit private-test role, source, attribution, family
  ID, task revision, and license decision.
- **S6:** CMake/verifier lack the checked-in Catch scaffold, locked compiler,
  positive discovery counts, fresh sanitizer tree, and durable receipts.
- **S7:** prompt boundary is currently correct, but whole-file application must
  reject prose, missing/duplicate/unknown files, and unsafe paths.
- **S8:** exact holdout slug is clear; semantic/code/API/test/family screens are
  pending.

# Normative per-root remedy specification

The next twelve headings are the common complete per-root contract. Each remedy
record binds this document and the root-specific row values.

## 1. Identity

Current source inventory ID is
`local-aider-dsa-binary-search-tree-v1`; prior family ID is the currently
implicit `aider-dsa-binary-search-tree-v1`. Each current root uses its audit
table hash, owner path/digest above, disposition `replace`, benchmark and
license screens `pending`, and status `planned`.

Each replacement uses family ID `aider-dsa-binary-search-tree-v2`, task-spec
revision `1`, the mapped new task ID, the mapped parent current ID, output
path
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree/<replacement-id>/`,
and remedy record
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree/.state/remedy/<current-id>.json`.
The record schema is `aider-task-remedy-v1`; it binds this document's final
SHA-256 before a source edit. Authoring is clean-room and may import neither
official assets nor old/balanced-family implementation renderers.

## 2. Objective

Each replacement must observably own and operate an unbalanced binary search
tree. Insert, lookup, predecessor/successor, in-order traversal, and leaf,
one-child, and two-child deletion traverse or mutate its own nodes. A
root-specific augmentation may support a domain query but may not substitute a
library index.

The objective is achieved only when source inspection finds the required
node/root ownership with no authoritative false substitute, and a private
structural probe traverses the actual nodes, proves ordering/ownership/shape/
augmentation after every mutation, and rejects every deliberate substitute.
Until both pass, record
`primary_core_objective: not_achieved`; compilation or behavioral examples
cannot upgrade it.

## 3. Public API

Every declaration is C++17 in `namespace curriculum`. Editable response order
is `<replacement-id>.h`, then `<replacement-id>.cpp`. Headers include only
needed standard headers. Ordinary definitions and destructors are out of line.
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

## 4. Behavior table

The complete API-and-behavior table above is normative per method. These common
rules also apply and must be visible whenever relevant:

| Concern | Required behavior |
| --- | --- |
| invalid input | return the declared failure/empty value and do not mutate |
| duplicate | reject unless the row explicitly says coalesce, replace, or increment multiplicity |
| absent mutation | return `false` and preserve logical state |
| empty query | exact null/empty/zero result stated by the API |
| ordering | exact row comparator; vectors in that order except ranked `top` |
| range | inclusive unless explicitly half-open; reversed input is never normalized |
| ties | exact named secondary key |
| overflow | detect before signed arithmetic; fail atomically |
| exceptions/I/O | documented invalid input does not throw; no I/O |
| ownership | returned records are copies; tree ownership is unique |

Integral keys/counters/timestamps/quantities/prices/ranks are `std::int64_t`;
sizes are `std::size_t`. Positive means `>0`. Named string fields are
nonempty ASCII `[A-Za-z0-9_-]+`. Checked arithmetic must not invoke signed
overflow. Every root publishes the row's example plus an empty/rejected-call
example with exact return and no mutation.

## 5. Implementation invariant

Every class contains a private nested `Node` and
`std::unique_ptr<Node> root_`:

```cpp
struct Node {
  Key key;
  Payload payload;
  std::unique_ptr<Node> left;
  std::unique_ptr<Node> right;
  std::size_t subtree_size;
};
std::unique_ptr<Node> root_;
```

The fields must be authoritative, not a dummy shadow of another index. Copy is
deleted; move/destructor are out of line. Insert/delete recompute size and all
augmentation on recursive return. Two-child deletion transfers the entire
in-order-successor payload, removes that successor, and recomputes ancestors.

| Replacement | Additional exact state |
| --- | --- |
| appointment, delivery-zone, network-port, parking replacements | `max_end` equals maximum interval end in the subtree |
| energy replacement | checked `subtree_sum` equals subtree watt-hours |
| exam replacement | `multiplicity>=1`; subtree size counts occurrences |
| scoreboard replacement | subtree size supports rank under `(-score,player)` |
| warehouse replacement | `max_capacity` equals subtree maximum capacity |
| all others | only exact node-count `subtree_size` |

The tree is intentionally unbalanced. Increasing comparator keys 1..31 yield
31 reachable nodes and height 31. Keys
`8,4,12,2,6,10,14,1,3,5,7,9,11,13,15` yield height 4. Then delete 1 (leaf),
13 (leaf), 14 (one right child), and 8 (two children), checking exact in-order
content and invariants each time.

Under `CURRICULUM_TESTING`, the class declares
`friend struct BstInvariantProbe`. The private test defines it and recursively
reads the actual root/Node fields. Its
`TreeCheck {valid,nodes,occurrences,height}` proves acyclic unique
reachability, strict bounds, exact counts/height/size/augmentation, and
in-order equality with the behavior oracle.

Permitted library use: `unique_ptr`, value types, optionals, strings, output
vectors, temporary test buffers, and the private vector oracle. Forbidden as
authoritative production work: set/map/multi/unordered containers, GNU PBDS,
Boost/third-party trees, sorted vector/array/list indices, heap algorithms,
precomputed/hard-coded cases, or a dummy node tree. The source policy must
distinguish incidental output vectors from member/index storage.

## 6. Starter and reference

The starter header contains the complete public declarations, private Node,
root, copy/move/destructor policy, and test friend. The source compiles with
type-correct neutral incomplete bodies but fails `public_examples`,
`structural_shape`, and `deterministic_trace`.

The independent reference implements node algorithms directly. It imports no
old/balanced renderer, benchmark asset, private fixture, or starter body.
References map one-to-one to both editable files; applying them to a clean
starter reproduces the reference bytes. Forbidden are all section-5
substitutes, an always-true probe, inspection-only tree construction, and trace
special-casing. The old set reference must fail the new suite.

## 7. Tests

Exactly eight Catch cases are discovered:
`public_examples`, `invalid_and_atomic`,
`duplicate_or_payload_update`, `deletion_shapes`,
`ordering_and_boundaries`, `domain_special_rule`,
`deterministic_trace`, and `invariant_and_negative_fixtures`.
The first two are visible; six are private. The probe runs after every accepted
and rejected mutation.

Seeds in replacement-table order are `0xB57A1001`..`0xB57A1014`. Each trace
has exactly 4,096 steps with unsigned-32 wraparound:

```text
state = state * 1664525U + 1013904223U; op = state % 8
state = state * 1664525U + 1013904223U; key_a = 1 + state % 997
state = state * 1664525U + 1013904223U; key_b = 1 + state % 997
state = state * 1664525U + 1013904223U; payload_index = state % 31
```

Operations 0..7 are insert/upsert, erase/remove, exact lookup, predecessor/
floor, successor/ceiling, range/aggregate, domain-special query, and validation
no-op. IDs are `id-00`..`id-30`; intervals use min/max keys; semver uses
`(key_a%4,key_b%20,payload_index)`. A private sorted vector of value records
directly implements published behavior, never calling the reference. Compare
every return and complete in-order output after every step.

Separately compiled negative fixtures and failures:

| Fixture | Substitution | Failure |
| --- | --- | --- |
| `negative-set-wrapper` | current set-backed design | `invariant_not_enforced` |
| `negative-map-wrapper` | map/unordered authoritative index | `invariant_not_enforced` |
| `negative-sorted-vector` | sorted vector plus fake/dummy node | `invariant_not_enforced` |
| `negative-degenerate-node` | nodes declared, hard-coded/precomputed work | `invariant_not_enforced` or trace mismatch |
| `negative-bad-order` | reachable child violates ordering | `invariant_not_enforced` |
| `negative-stale-augmentation` | stale post-delete aggregate | `invariant_not_enforced` on augmented roots |
| `negative-domain-boundary` | endpoint/tie/duplicate/overflow error | named behavior failure |
| `negative-prompt-omission` | private rule omitted from docs | `prompt_contract_incomplete` |

Focused tests materialize fixtures in scratch and assert reason codes. Grepping
the good reference alone is insufficient.

## 8. Files and metadata

| Role | Exact path |
| --- | --- |
| visible docs | `.docs/introduction.md`, `.docs/instructions.md` |
| editable | `<id>.h`, `<id>.cpp` in that order |
| visible/private Catch | `<id>_test.cpp`, `.meta/<id>_private_test.cpp` |
| references | `.meta/example.h` -> header, `.meta/example.cpp` -> source |
| negative fixtures | `.meta/negative/<fixture>/<id>.h|.cpp` |
| metadata | `.meta/config.json`, `.meta/tests.toml`, `.meta/provenance.json` |
| support/build | `CMakeLists.txt`, `test/catch.hpp`, `test/tests-main.cpp` |

Config declares exact solution order, visible/private roles, example mapping,
C++17, blurb, authors, source inventory, family, task revision, and parent.
Only editable files enter `files.solution`. Provenance binds clean-room
method, license evidence, owner/spec/remedy hashes, parent/before hash, support
identities, holdout manifest/normalizer/results, and truthful status
`local task artifact; not admitted SFT data`.

Support is `exercism-catch-v1`; manifest SHA-256
`79b3589a19fe45ff3887692a9d26b908c734cab97eb6c5a6134ffb5a1dc6e99c`.
`test/catch.hpp` is
`e11ac6b2994c046909c4a7c730a6a536e8f9563172563026878b7baadecdf553`;
`test/tests-main.cpp` is
`5847fda35c1320d94f8d088aaf34229d689f66f1da235f885cbb28c8f17e4260`.
CMake template
`src/w8_biayn/aider_sft/assets/aider-sft-cmake-catch-v1/CMakeLists.txt.in`
is `3050f5b5bbc277067fb73990f38748b0cfe56158d5c761d17e8018700578b7b5`.

## 9. Build/oracle

Use network-disabled immutable image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
Bind `/usr/local/bin/g++`, GCC 13.4.0, binary SHA-256
`152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`;
CMake/CTest 3.25.1; Unix Makefiles; C++17; strict warnings; network none;
reviewed seccomp; and fresh scratch.

Normal reference commands:

```bash
cmake -S <root> -B <normal> -G "Unix Makefiles"   -DCMAKE_CXX_COMPILER=/usr/local/bin/g++ -DTASK_VARIANT=reference
cmake --build <normal> --parallel 2
ctest --test-dir <normal> --show-only=json-v1
ctest --test-dir <normal> --output-on-failure
```

Fresh sanitizer repeats in an empty directory with
`-fsanitize=address,undefined -fno-omit-frame-pointer` compilation,
`-fsanitize=address,undefined` linking,
`ASAN_OPTIONS=detect_leaks=1:halt_on_error=1`, and
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`. Applied target repeats
normal/sanitizer after strict whole-file application and byte comparison.
Starter compiles but tests fail.

Receipts bind task/generator/spec/remedy/reference/target hashes; image;
compiler path/version/hash; CMake/CTest/Catch; flags/env/sandbox/seccomp;
commands/times/exits/output digests; discovered names/counts; and binary
hashes. Normal and sanitizer each discover the same exact eight names. Host
runs and reused build trees are non-admissible.

## 10. Family/contamination

Use whole-slug normalizer `aider-whole-slug-v1` and semantic normalizer
`aider-cleanroom-family-v1`: normalize UTF-8/LF, remove comments/domain nouns,
canonicalize identifiers/types/literals, but preserve API arity, control flow,
invariants, algorithms, assertions, and reference structure.

Compare all docs/APIs/starters/references/tests/contracts against the 26-entry
manifest and available bound upstream assets, every root under both local task
trees, all released/local-family manifests, and the other 19 proposals.
Current permanent-holdout result is `pending`: slugs differ, semantic proof
does not exist. Any holdout match yields `benchmark_id_overlap` or
`benchmark_content_overlap`, changes disposition to `reject`, and stops;
renaming is prohibited.

The 20 proposals intentionally share one family. Each retained root must still
have a distinct state model, special invariant/query, and negative-domain
fixture. A normalized duplicate yields `duplicate_task` or
`duplicate_family` and is replaced/excluded, never waived.

## 11. Optional dataset handoff

`not_requested`.

Local remediation ends at `local_family_verified`. It creates no JSONL,
token/mask record, split, release, export, consumer verification, training
authorization, or uplift claim. The legacy converter is not an acceptance
route. Dataset gates require separate authorization.

## 12. Acceptance

### Primary acceptance: genuine BST first

Add this exact owner entrypoint:

```bash
uv run python -m w8_biayn.integrations.moonlight_binary_search_tree_aider_tasks   --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree   --force --verify-core
```

It first freezes records/resolves license, regenerates scratch, and fails unless
all 20 records say `primary_core_objective: achieved`, binding source-policy
pass; exact structural probe/shape/deletion/augmentation results; 4,096-step
oracle equality; failures for set/map/vector/degenerate/bad-order fixtures and
stale augmentation where applicable; and failure of the old reference.
Delegated/dummy/unverifiable cores fail `invariant_not_enforced`. No secondary
success may mark `implemented` while any primary result is `not_achieved`.

| Replacement | Additional primary discriminator |
| --- | --- |
| access-key | deletion retains exact expiry payload |
| appointment | exact `max_end` after overlap search/successor deletion |
| auction | coalescing updates node; zero cancel deletes node |
| audit | predecessor and retention equality traverse sequence nodes |
| cargo | lower bound returns least maximum including equality |
| delivery-zone | closed-boundary overlap plus exact `max_end` |
| document | greatest revision `<=` query, never ceiling |
| energy | exact subtree sums/counts; atomic overflow |
| exam | multiplicity/occurrence size gives exact percentile |
| flight | composite delete promotes only one passenger without ID map |
| library | bytewise `A-2 < A-10` traversal |
| network-port | `max_end` yields first free inclusive port |
| parking | touching coalesce and occupy split/delete via nodes |
| price | exact-budget predecessor; consume zero deletes |
| scoreboard | subtree rank and erase without ID map |
| sensor | greatest enter threshold `<=` value |
| ticket | exact composite deletion without auxiliary map |
| transit | lower-bound time/route tie and exact cancellation |
| semver | predecessor cannot cross major |
| warehouse | `max_capacity` guides least-ID fitting bin |

### Secondary acceptance

Only after primary pass:

```bash
uv run pytest -q tests/test_moonlight_binary_search_tree_aider_tasks.py
uv run python -m w8_biayn.integrations.moonlight_binary_search_tree_aider_tasks   --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree   --force --verify
```

Focused tests validate 20 roots, one family ID, unique IDs, tree manifest,
prompt/whole-file boundaries, roles, support, starter/reference/application
ladder, negative fixtures, and drift. Locked verify requires eight matching
normal/sanitizer names per root, passing reference/applied target, failing
starter, resolved license, passing family/holdout screens, and receipts.

Stable failures include `remedy_spec_incomplete`,
`remedy_disposition_conflict`, `generator_output_drift`, `unsafe_path`,
`whole_format_failed`, `header_source_incoherent`,
`reference_compile_failed`, `target_reference_mismatch`,
`prompt_contract_incomplete`, `invariant_not_enforced`,
`test_discovery_failed`, `zero_tests`, `reference_tests_failed`,
`reference_sanitizer_failed`, `sanitizer_test_count_mismatch`,
`duplicate_task`, `duplicate_family`, `benchmark_id_overlap`, and
`benchmark_content_overlap`.

States are:

```text
unreviewed -> audited -> planned -> implemented -> oracle_verified
  -> semantically_admitted -> local_family_verified
```

`implemented` requires primary `achieved`; later gates cannot establish it.

## Ordered implementation plan

1. Freeze before hashes/records and resolve license; stop rejects.
2. Implement v2 private Nodes, ownership, recursive operations, and
   augmentations first; reuse no set/balanced renderer.
3. Implement structural probe, traces, vector oracle, shapes, and false
   substitutes; require primary `achieved` before continuing.
4. Add exact APIs/docs/coherent starters/independent references/mappings.
5. Add roles/provenance, Catch/CMake, prompt/application, and drift checks.
6. Run locked normal and fresh ASan/UBSan ladders and retain receipts.
7. Run holdout/duplicate/family screens; reject/replace without renaming.
8. Mark `local_family_verified` only after all local gates; leave dataset
   handoff `not_requested`.

## Explicit non-claims

The preserved legacy roots do not contain real BSTs. The v2 materialization
below does not claim locked oracle verification, semantic admission, training
suitability, release readiness, or uplift, and authorizes no dataset conversion,
training, paid call, or benchmark run.

## Implementation handoff — 2026-07-18

The v2 owner is now
`src/w8_biayn/integrations/moonlight_binary_search_tree_aider_tasks.py`; its
wrapper is `examples/slime/moonlight_cpp_perf/prepare_bst_aider_tasks.sh` and
its focused regression is `tests/test_moonlight_binary_search_tree_aider_tasks.py`.
It materializes the 20 replacement IDs only beneath
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree/`, preserving
the legacy root. Each generated root has a `replace` remedy record at the
family-root sibling `.state/remedy/`, an owned nested `Node`, `root_`, recursive
insert/delete helpers, both editable references, the eight named Catch cases,
and prompt/role/family-screen evidence.

The generated family manifest records the before/after tree hashes and the
core result `primary_core_objective: achieved` for all 20 roots. The selected
prompt is `docs/aider-tasks-spec/prompts/implement-family-for-sft.md`. The
focused test, prompt-boundary screen, duplicate/whole-slug screen, and locked
C++17 reference builds all pass. Every root has one receipt for the
network-disabled immutable grader image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
with eight normal and eight fresh ASan/UBSan tests. The generated manifest is
`local_family_verified`. Dataset release, training authorization, and uplift
remain unclaimed.
