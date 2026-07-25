# binary-search-tree — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `binary-search-tree`
- Shard: `0` (failure log section header, line 4270: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 4272; terminal JSON `tests_outcomes: [false, false]`, failure log lines 5671-5673 / raw shard-0 lines 39853-39855)
- Result: `FAIL` (failure log line 4273)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **4268-5710**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log` (binary-search-tree run spans source lines ~1519-39900; interleaved with concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/binary-search-tree/.meta/example.h` (header-only reference; no `.meta/example.cpp` exists)
  - `polyglot-benchmark/cpp/exercises/practice/binary-search-tree/binary_search_tree_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Failure log excerpts are partial.** Chunk 1 (failure log 4318+, source 1519-2010) covers attempt 1's answer; chunk 2 (failure log 4815+, source 21256-21955) covers retry thinking; the attempt-1 test failure and the attempt-2 answer exist only in the raw shard-0 log, cited as "shard-0 line N". The terminal test log is failure log 5520-5710 (source ~39720-39900).
2. **Interleaved shard log.** Concurrent tasks' `Only 3 reflections allowed` / `Applied edit` lines appear between binary-search-tree lines in shard-0; binary-search-tree lines were traced by grepping `binary_search_tree` / `binary_tree`.
3. **Reference layout.** The reference is entirely in `.meta/example.h` (a header-only template); there is no `.meta/example.cpp`. This is itself part of the contract lesson (templates + iterators live in the header).

## 2. Benchmark Contract (Ground Truth)

File set: `binary_search_tree.h` + `binary_search_tree.cpp`, namespace `binary_search_tree`.

Public API (from `.meta/example.h`, enforced by `binary_search_tree_test.cpp`):

- `template<typename T> class binary_tree final` (example.h:16-17) — snake_case, templated, `final`. The test aliases `using tree_ptr = typename std::unique_ptr<binary_search_tree::binary_tree<T>>;` (binary_search_tree_test.cpp:11-12) and constructs `tree_ptr<T>(new binary_search_tree::binary_tree<T>(*data_iter))` (test:28).
- `using binary_tree_ptr = std::unique_ptr<binary_tree>;` (example.h:21) — children are owned by `std::unique_ptr`.
- `explicit binary_tree(TParam&& data)` — perfect-forwarding constructor (example.h:23-29).
- `void insert(TParam&& data);` (example.h:40-42) — test: `tree->insert(*data_iter)` (test:31).
- `const T& data() const`, `const binary_tree_ptr& left() const`, `const binary_tree_ptr& right() const` (example.h:44-46) — accessors return **const references**, children as `const std::unique_ptr&`. Enforced by `test_leaf`: `REQUIRE(data == tree->data()); REQUIRE((bool) tree->left() == has_left);` (test:16-17) and by the terminal compile errors when raw pointers are returned instead (failure log 5550+, source 39732+).
- `binary_tree_iter begin() const; binary_tree_iter end() const;` (example.h:48-49) with a nested `class binary_tree_iter final` (example.h:57+) providing in-order traversal — required for the range-for `for (auto& x : *tree)` (test:90-95) that drives `test_sort`.
- Non-copyable, non-movable (example.h:33-37).
- Ordering: equal values go **left** (`value <= current` → left), enforced by `same_number_at_left_node` (test:50-56).

Exception policy: none enforced by the visible test file.

Templates used: `uint32_t` and `std::string` (test:36+, 128+), so the design must be a real template — not int-only.

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: textbook API invented, contract ignored)

**What the model emitted.** A **diff-hunk answer** (failure log 4676-4782, source 1874-1980) shipping a generic textbook BST: `struct Node { int data; Node* left; Node* right; };` and `class BinarySearchTree { BinarySearchTree(); ~BinarySearchTree(); void insert(int value); bool search(int value) const; Node* root; }` (failure log 4691-4706, source 1889-1904) — PascalCase class, `int`-only, raw owning pointers, no template, no `unique_ptr`, no `data()/left()/right()` accessors, no iterator, plus a `search()` the contract never asks for. The header hunk again contains a mangled guard line `-#endif // BINARY_SEARCH_TREE_H+#endif // BINARY_SEARCH_TREE_H` (failure log 4710, source 1908). The destructor's "helper lambda" calls itself with no capture — `auto deleteRecursive = [](Node* node) { ... deleteRecursive(node->left); ... };` (failure log 4725-4733, source 1923-1931) — which does not compile (name not captured/deduced in its own body). Applied (failure log 4781-4782, source 1979-1980).

**Test run 1 — compile failure** (shard-0 25710-26048): `error: 'binary_tree' is not a member of 'binary_search_tree'` at `using tree_ptr = typename std::unique_ptr<binary_search_tree::binary_tree<T>>;` (shard-0 25710-25714, quoting binary_search_tree_test.cpp:12), cascading `tree_ptr does not name a type` errors (shard-0 25720+), ending `Tests failed: .../binary-search-tree` (shard-0 26048).

### Attempt 2 (retry with compiler output) — outcome False (compile failure: right class name, wrong everything else)

**What the retry changed.** The retry thinking is impressively diagnostic — "The test ... is looking for a templated class `binary_search_tree::binary_tree<T>` with specific interface methods (`data()`, `left()`, `right()`), whereas the provided implementation ... has a non-templated class `BinarySearchTree`" and "the class name **must** be `binary_tree`, not `BinarySearchTree`. It must be templated" (shard-0 30845-30899). But the rewrite (shard-0 31430-31540, applied shard-0 31764) kept the old internal design and only re-skinned the surface:

- Still a `Node* root` wrapper design instead of the node-IS-the-tree reference shape; the header used `binary_search_tree::Node` without template arguments, producing `binary_search_tree.h:32:9: error: missing template argument list after 'binary_search_tree::Node'` (failure log 5542, source 39724).
- `T data() const` returning **by value**, with `return T(); // Return default value if empty` (shard-0 31460-31463) instead of `const T&` to the node's own data.
- `binary_tree<T>* left() / right()` returning **raw pointers** (shard-0 31466-31472) instead of `const std::unique_ptr<binary_tree<T>>&` — terminal errors: `error: invalid initialization of reference of type 'tree_ptr<unsigned int>&' {aka 'const std::unique_ptr<...>&'} from expression of type 'binary_tree<unsigned int>*'` at test lines 54, 62, 70, 78-85 (failure log 5550-5601, source 39732-39783) and the `std::string` analogues (failure log 5608-5638, source 39790-39820).
- `std::vector<T> begin() / end()` returning **vectors** (shard-0 31501-31520) instead of an iterator type — terminal errors at the range-for: `error: no match for 'operator++' (operand type is 'std::vector<unsigned int>')` and `no match for 'operator*'` at test:95 (failure log 5646-5655, source 39828-39837).
- A spurious `make_tree` "global helper for the test" appended (shard-0 31525-31540) — inventing test-side infrastructure in the editable files.
- The self-calling uncaptured lambda bug persisted verbatim (shard-0 31447-31456).

`Tests failed: .../binary-search-tree` (failure log 5663, source 39845); JSON `tests_outcomes: [false, false]` (failure log 5671-5673).

### Hard evidence vs inference

- Hard evidence: invented attempt-1 API (failure log 4691-4706), mangled hunk (failure log 4710), non-compiling recursive lambda (failure log 4725-4733), attempt-1 `'binary_tree' is not a member` errors (shard-0 25710-25720), attempt-2's raw-pointer accessors (shard-0 31466-31472) and vector "iterators" (shard-0 31501-31520) with their exact compile errors (failure log 5550-5655), spurious `make_tree` (shard-0 31525+).
- Inference: this is the hardest API surface in the fixed26 set (template + unique_ptr ownership + const-ref accessors + custom iterator), and the model fell back to the canonical textbook BST twice. Attempt 2 shows the model can *read* the required interface from compiler errors (its analysis at shard-0 30845-30899 is essentially correct) but cannot *produce* the corresponding design: it renamed the class and kept the raw-pointer/vector idioms it knows, missing (a) node-as-tree ownership via `unique_ptr`, (b) const-ref return discipline, and (c) what a C++ input iterator actually requires (a type with `operator++`, `operator*`, `operator!=` usable in a range-for). The gap is capability, not comprehension.

## 4. Knowledge / Capability Gaps

- **G1 — Canonical exercism-cpp tree API.** `binary_tree<T>` node-as-tree (each node is a tree), snake_case, templated — invented away in favor of `BinarySearchTree` + `Node` (failure log 4691-4706), costing attempt 1 (shard-0 25710-25714).
- **G2 — Smart-pointer ownership design.** Children held as `std::unique_ptr` and exposed as `const unique_ptr&`; the model used raw `Node*`/`binary_tree<T>*` in both attempts (failure log 4691-4693, shard-0 31466-31472; terminal errors failure log 5550-5601).
- **G3 — Const-ref accessor discipline.** `const T& data() const` vs the model's by-value `T data() const` with a fabricated default-for-empty semantics (shard-0 31460-31463).
- **G4 — Iterator protocol.** Range-for needs `begin()/end()` returning a type with `operator++`, `operator*`, `operator!=`; returning `std::vector<T>` from `begin()` (shard-0 31501-31520) shows the model doesn't know the protocol's minimum surface (terminal errors failure log 5646-5655).
- **G5 — Recursive lambda pitfall.** A lambda cannot call itself without a capture/`std::function`/y-combinator; the same non-compiling pattern shipped in both attempts (failure log 4725-4733; shard-0 31447-31456).
- **G6 — Template member-use discipline.** Inside `template<typename T> class binary_tree`, a nested/independent `Node` template must be used with its argument list (`Node<T>`); the attempt-2 header error `missing template argument list after 'binary_search_tree::Node'` (failure log 5542) shows the gap.
- **G7 — Whole-file format contract.** Both answers were ```` ```diff ```` hunks under `edit_format: whole` (failure log 4682-4683; shard-0 31430+), including a mangled guard line (failure log 4710).
- **G8 — Don't ship test-side helpers.** Inventing a `make_tree` free function "for the test" (shard-0 31525-31540) pollutes the editable files with scaffolding the tests neither need nor tolerate.

## 5. SFT Task Specifications (26 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-tide-gauge
- Files: gauge.cpp, gauge.h (test file: gauge_test.cpp)
- API: namespace `coast`; `class gauge { public: void record(double meters); double last() const; };`
- Prompt shape: tidal gauge logger; whole-file instruction prominent.
- Target capability: G7 — complete whole-file listings only.
- Target answer shape: two whole-file listings, no diff fences.
- Difficulty / variation: minimal; format-only trap.

### Spec 02: node-is-tree-recursive-file-index
- Files: file_index.h, file_index.cpp (test file: file_index_test.cpp)
- API: namespace `indexer`; `template<typename T> class ordered_node final { public: explicit ordered_node(const T& key); void insert(const T& key); const T& key() const; const std::unique_ptr<ordered_node>& left() const; const std::unique_ptr<ordered_node>& right() const; };`
- Prompt shape: sorted file-key index where every node is itself an index; story avoids tree terminology.
- Target capability: G1 — node-as-tree design: no wrapper class, no separate Node struct; each node owns children.
- Target answer shape: single templated class; children as `unique_ptr` members.
- Difficulty / variation: core design prior in fresh domain.

### Spec 03: unique-ptr-children-family-tree
- Files: lineage.h, lineage.cpp (test file: lineage_test.cpp)
- API: namespace `genealogy`; `template<typename T> class person_node { public: explicit person_node(const T& name); void add_child(const T& name); const std::unique_ptr<person_node>& first_child() const; };`
- Prompt shape: genealogy records.
- Target capability: G2 — `std::unique_ptr` child ownership; no `delete` anywhere; destructor `= default`.
- Target answer shape: `<memory>` included; make_unique insertion; default dtor.
- Difficulty / variation: smart-pointer ownership isolation.

### Spec 04: const-ref-accessors-mineral-catalog
- Files: catalog.h, catalog.cpp (test file: catalog_test.cpp)
- API: namespace `geology`; `template<typename T> class sample_bin { public: explicit sample_bin(const T& label); const T& label() const; const std::unique_ptr<sample_bin>& next() const; };`
- Prompt shape: mineral sample storage.
- Target capability: G3 — accessors return `const T&` / `const unique_ptr&`; never by value, never raw pointer.
- Target answer shape: exact qualifiers; tests bind references.
- Difficulty / variation: return-type discipline.

### Spec 05: no-default-on-empty-semaphore
- Files: gate_log.h, gate_log.cpp (test file: gate_log_test.cpp)
- API: namespace `canal`; `template<typename T> class entry { public: explicit entry(const T& v); const T& value() const; };`
- Prompt shape: canal lock entries; spec text warns: every node always has a value — never fabricate a default for an "empty" node.
- Target capability: G3 — value-semantics honesty: a node always holds its data; no `return T();` escape hatches.
- Target answer shape: data returned directly; no empty-state branch.
- Difficulty / variation: counter-trains the `return T();` fabrication.

### Spec 06: iterator-protocol-word-chain
- Files: chain.h, chain.cpp (test file: chain_test.cpp)
- API: namespace `words`; `template<typename T> class chain { public: class iterator { public: iterator& operator++(); const T& operator*() const; bool operator!=(const iterator&) const; }; iterator begin() const; iterator end() const; };`
- Prompt shape: linked word chain traversed by range-for in tests.
- Target capability: G4 — minimum iterator surface for range-for: `++`, `*`, `!=`; `begin()`/`end()` return the iterator type, not containers.
- Target answer shape: nested iterator class with exactly the three operators.
- Difficulty / variation: protocol drill with a simple forward walk.

### Spec 07: inorder-iterator-pond-sizes
- Files: pond_index.h, pond_index.cpp (test file: pond_index_test.cpp)
- API: namespace `wetlands`; `template<typename T> class size_tree { /* node-as-tree, sorted insert, nested in-order iterator */ };`
- Prompt shape: sorted pond-size registry; tests sort via range-for.
- Target capability: G4 — in-order traversal iterator over a BST (stack-based or parentless state machine), yielding ascending order.
- Target answer shape: iterator holds a stack or state; `++` advances in-order; `end()` compares equal at exhaustion.
- Difficulty / variation: the reference's exact iterator behavior, fresh wrapper.

### Spec 08: equal-goes-left-dup-policy-stable-marks
- Files: mark_book.h, mark_book.cpp (test file: mark_book_test.cpp)
- API: namespace `school`; `template<typename T> class grade_tree { public: explicit grade_tree(const T& mark); void insert(const T& mark); /* left/right accessors */ };`
- Prompt shape: exam-mark tree where duplicate marks must land on the LEFT; story states the policy explicitly.
- Target capability: edge cases — `<=` vs `<` insertion policy; duplicates placed per spec.
- Target answer shape: `<=` branch to left (or as the spec dictates), with a one-line rationale.
- Difficulty / variation: duplicate-policy precision.

### Spec 09: recursive-lambda-pitfall-maze-solver
- Files: maze.cpp, maze.h (test file: maze_test.cpp)
- API: namespace `puzzle`; `bool solvable(const std::vector<std::string>& grid);`
- Prompt shape: repair — history answer uses `auto dfs = [](int r, int c){ ... dfs(...); };` and fails with `error: use of 'dfs' before deduction` (or 'not declared in this scope'); turn 2 asks for the fix.
- Target capability: G5 — recognize self-calling lambda diagnostics; fix via a named private member function, `std::function`, or an explicit helper.
- Target answer shape: recursion moved to a proper function; no uncaptured self-reference.
- Difficulty / variation: the exact bug shipped twice in the failure log.

### Spec 10: template-node-args-skyline
- Files: skyline.h, skyline.cpp (test file: skyline_test.cpp)
- API: namespace `city`; `template<typename T> class height_tree { struct node { T v; std::unique_ptr<node> l, r; }; std::unique_ptr<node> root_; };`
- Prompt shape: repair — history header uses bare `node*`/`node{...}` where the template context needs `node` (nested is fine) vs an independent `Node<T>` template needing arguments; turn 2 shows `missing template argument list`.
- Target capability: G6 — know when a nested class needs no argument list vs an independent template always needs `Node<T>`.
- Target answer shape: consistent nested-node usage (or `Node<T>` everywhere if independent).
- Difficulty / variation: template-name discipline.

### Spec 11: header-only-template-tree-orchard-rows
- Files: row_index.h, row_index.cpp (test file: row_index_test.cpp)
- API: namespace `farm`; `template<typename T> class row_tree { /* full implementation in header */ };`
- Prompt shape: orchard row index; note says the build compiles the cpp separately and the type is a template.
- Target capability: header-only templates — all definitions (including the iterator) in the header; cpp keeps include + empty namespace.
- Target answer shape: everything in the header; trivial cpp.
- Difficulty / variation: placement discipline for templates (links to linked-list learnings).

### Spec 12: perfect-forwarding-ctor-parcel-depot
- Files: depot.h, depot.cpp (test file: depot_test.cpp)
- API: namespace `logistics`; `template<typename T> class slot { public: template<typename U> explicit slot(U&& value); };`
- Prompt shape: parcel depot slots constructed from both lvalues and rvalues.
- Target capability: advanced — forwarding-reference constructor with `std::forward`; `<utility>` included.
- Target answer shape: `T value_;` initialized via `std::forward<U>(value)`.
- Difficulty / variation: mirrors the reference's `TParam&&` idiom.

### Spec 13: noncopyable-node-art-vault
- Files: vault_index.h, vault_index.cpp (test file: vault_index_test.cpp)
- API: namespace `museum`; `template<typename T> class piece_node { public: piece_node(const piece_node&) = delete; piece_node& operator=(const piece_node&) = delete; };`
- Prompt shape: art-vault index; ownership is unique, copying must be impossible.
- Target capability: rule-of-five for unique ownership — delete copy (and move, per spec) operations.
- Target answer shape: deleted special members; `= default` dtor.
- Difficulty / variation: special-member discipline.

### Spec 14: rename-to-test-contract-tide-pools
- Files: pool_index.h, pool_index.cpp (test file: pool_index_test.cpp)
- API: namespace `shore`; test expects `template<typename T> class creature_tree` with `data()/left()/right()`; history answer shipped `class TidePoolTree` + `struct Node`; turn 2 shows `'creature_tree' is not a member of 'shore'`.
- Prompt shape: repair — full surface replacement, not a rename-only patch.
- Target capability: G1/G4 — when the whole surface is wrong, replace it wholesale (class shape, accessors, ownership), not just the name.
- Target answer shape: whole files with the contract surface; old types gone.
- Difficulty / variation: wholesale-replacement repair.

### Spec 15: no-test-side-helpers-bird-ringing
- Files: ring_register.h, ring_register.cpp (test file: ring_register_test.cpp)
- API: namespace `birds`; `template<typename T> class register_tree { /* contract only */ };`
- Prompt shape: repair turn where the temptation is to add a `make_register` helper "for the tests"; instructions forbid adding unrequested free functions.
- Target capability: G8 — implement exactly the contract; never ship test-side scaffolding in editable files.
- Target answer shape: no extra free functions.
- Difficulty / variation: surface-minimalism.

### Spec 16: vector-is-not-an-iterator-photo-roll
- Files: roll.h, roll.cpp (test file: roll_test.cpp)
- API: namespace `darkroom`; `template<typename T> class frame_chain { public: class iterator { /* ++, *, != */ }; iterator begin() const; iterator end() const; };`
- Prompt shape: contrastive — history answer returns `std::vector<T>` from `begin()`; compiler output shows `no match for 'operator++' (operand type is 'std::vector<...>')`; fix by implementing a real iterator.
- Target capability: G4 — map this exact diagnostic family to "begin() must return an iterator type".
- Target answer shape: nested iterator class; vectors gone from the interface.
- Difficulty / variation: negative-example-first with the log's diagnostic.

### Spec 17: raw-pointer-return-repair-freight-cars
- Files: consist.h, consist.cpp (test file: consist_test.cpp)
- API: namespace `rail`; `template<typename T> class car { public: const std::unique_ptr<car>& next() const; };`
- Prompt shape: repair — history returns `car<T>*` from `next()`; compiler shows `invalid initialization of reference of type 'const std::unique_ptr<...>&' ... from expression of type 'car<T>*'`; fix the return type and the storage it exposes.
- Target capability: G2/G3 — this diagnostic means the exposed ownership type is wrong; fix storage AND accessor together.
- Target answer shape: `unique_ptr` member + const-ref accessor.
- Difficulty / variation: ownership-repair drill with the log's diagnostic.

### Spec 18: template-two-types-stardate
- Files: registry.h, registry.cpp (test file: registry_test.cpp)
- API: namespace `fleet`; `template<typename T> class registry_tree { /* contract */ };`
- Prompt shape: starship registry; hidden tests instantiate with an unsigned integer type AND `std::string`.
- Target capability: G1/G6 — genuinely generic templates: no `int` assumptions anywhere (comparisons, default values, streams).
- Target answer shape: compiles for both instantiations.
- Difficulty / variation: generality check.

### Spec 19: string-tree-insertion-lexicon
- Files: lexicon.h, lexicon.cpp (test file: lexicon_test.cpp)
- API: namespace `words`; `template<typename T> class word_tree { /* sorted insert + in-order iteration */ };`
- Prompt shape: dictionary word tree; hidden tests insert strings and expect lexicographic order via iteration.
- Target capability: G1/G4 — operator< driven ordering works unchanged for strings.
- Target answer shape: same code path for any orderable T.
- Difficulty / variation: string-instantiation edge.

### Spec 20: insertion-iterative-vs-recursive-canyon-gauge
- Files: depth_tree.h, depth_tree.cpp (test file: depth_tree_test.cpp)
- API: namespace `canyon`; `template<typename T> class depth_tree { public: void insert(const T& v); };`
- Prompt shape: depth readings; spec allows either iterative or recursive insert but demands no unbounded recursion risk for 10k sorted inputs.
- Target capability: implementation judgment — iterative insert loop; avoid recursion-depth blowup on degenerate input.
- Target answer shape: iterative insert with parent tracking or unique_ptr reference walking.
- Difficulty / variation: robustness angle.

### Spec 21: depth-iterative-destroy-glacier-cores
- Files: core_stack.h, core_stack.cpp (test file: core_stack_test.cpp)
- API: namespace `ice`; `template<typename T> class core_tree { /* unique_ptr children */ };`
- Prompt shape: deep ice-core tree; spec notes naive recursive destruction is acceptable here but the ownership must remain unique_ptr-driven (no manual delete).
- Target capability: G2 — trust unique_ptr recursive destruction; never write manual post-order delete.
- Target answer shape: no destructor body at all.
- Difficulty / variation: ownership trust vs manual cleanup instinct.

### Spec 22: end-iterator-sentinel-lantern-line
- Files: lanterns.h, lanterns.cpp (test file: lanterns_test.cpp)
- API: namespace `festival`; `template<typename T> class lantern_line { public: class iterator { /* ... */ }; iterator begin() const; iterator end() const; };`
- Prompt shape: lantern line; hidden tests compare `it != line.end()` in a manual loop (not just range-for).
- Target capability: G4 — sentinel equality semantics: exhausted iterator equals `end()`.
- Target answer shape: `operator!=` comparing internal state/node pointers.
- Difficulty / variation: iterator-equality nuance.

### Spec 23: no-empty-fence-terrarium
- Files: terrarium.cpp, terrarium.h (test file: terrarium_test.cpp)
- API: namespace `glass`; `class climate { public: void vent(int minutes); int humidity() const; };`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines, no compiler output.
- Target capability: G7 — no empty fences; whole unchanged files or explicit no-change statement.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 24: const-iteration-window-box
- Files: planter.h, planter.cpp (test file: planter_test.cpp)
- API: namespace `balcony`; `template<typename T> class herb_row { public: class iterator { public: const T& operator*() const; /* ++, != */ }; iterator begin() const; iterator end() const; };`
- Prompt shape: herb-row traversal; tests iterate a `const` object.
- Target capability: G4/G3 — const begin/end and const-deref iterator; `begin() const`.
- Target answer shape: const-qualified begin/end; `operator*` returns `const T&`.
- Difficulty / variation: const-correctness in iterators.

### Spec 25: whole-file-consolidation-tide-station
- Files: station.h, station.cpp (test file: station_test.cpp)
- API: namespace `weather`; `template<typename T> class reading_tree { /* contract */ };`
- Prompt shape: three-turn chat — diff answer, repair, final consolidation request.
- Target capability: G7 — final turn re-emits clean whole files with all fixes.
- Target answer shape: whole files, no diff fences, all repairs present.
- Difficulty / variation: consolidation discipline.

### Spec 26: capability-capstone-archipelago-survey
- Files: island_index.h, island_index.cpp (test file: island_index_test.cpp)
- API: namespace `survey`; `template<typename T> class island_tree final { public: using ptr = std::unique_ptr<island_tree>; explicit island_tree(const T& name); void insert(const T& name); const T& data() const; const ptr& left() const; const ptr& right() const; class iterator { public: iterator& operator++(); const T& operator*() const; bool operator!=(const iterator&) const; }; iterator begin() const; iterator end() const; island_tree(const island_tree&) = delete; island_tree& operator=(const island_tree&) = delete; };`
- Prompt shape: archipelago survey index; prompt underdetermines all names but specifies behaviors (sorted insert, duplicates left, iterable ascending, unique ownership).
- Target capability: G1+G2+G3+G4 capstone — full contract-shaped tree with iterator, header-only, whole files.
- Target answer shape: complete conventional implementation; nothing invented, nothing missing.
- Difficulty / variation: integrative final spec mirroring the full reference surface.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, trailing newline present. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass in the benchmark's CMake/Catch2 shape; for template specs, tests instantiate at least two unrelated types (integral + `std::string`). Receipt stored.
3. **Ownership gate**: no raw owning pointers, no `delete`, no manual post-order cleanup in targets — mechanically grepped; children must be `std::unique_ptr` with const-ref accessors.
4. **Iterator gate**: range-for and manual `!= end()` loops over a const object must compile and yield sorted order (including duplicates-left policy) — exercised by each spec's tests.
5. **Repair-turn gate**: repair specs (09, 10, 14, 16, 17) must seed turn-1 answers that genuinely produce the shown diagnostics; turn-2 targets must fix the seeded defects completely.
6. **Lambda-pitfall gate**: no target contains a self-referencing uncaptured lambda — mechanically grepped.
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce binary-search-tree's (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the raw shard-0 log, and ground truth:

1. **Re-read every cited line/range** and confirmed quotes verbatim: failure log 4270-4273 (header), 4676-4782 (attempt-1 answer; class surface 4691-4706 = source 1889-1904, mangled guard 4710 = source 1908, recursive lambda 4725-4733 = source 1923-1931, applied 4781-4782), 4815-4830 (retry thinking start), 5520-5710 (terminal block; Node template-arg error 5542 = source 39724, raw-pointer errors 5550-5638 = source 39732-39820, iterator errors 5646-5655 = source 39828-39837, Tests failed 5663 = source 39845, `tests_outcomes: [false, false]` 5671-5673 = source 39853-39855); shard-0 25710-25720 (attempt-1 `'binary_tree' is not a member` errors quoting test:12), 26048 (attempt-1 Tests failed), 30845-30899 (correct interface diagnosis), 31430-31540 (attempt-2 rewrite: by-value data 31460-31463, raw-pointer accessors 31466-31472, vector begin/end 31501-31520, spurious make_tree 31525+, persistent lambda bug 31447-31456), 31764 (applied).
2. **Re-checked every API claim** against `.meta/example.h` (template `binary_tree final` lines 16-17, `binary_tree_ptr` alias line 21, forwarding ctor lines 23-29, insert lines 40-42, const-ref accessors lines 44-46, begin/end lines 48-49, nested `binary_tree_iter final` line 57+, deleted copy/move lines 33-37) and `binary_search_tree_test.cpp` (`tree_ptr` alias lines 11-12, construction line 28, insert line 31, `test_leaf` REQUIREs lines 16-17, duplicates-left case lines 50-56, range-for lines 90-95, string instantiation lines 128+). Verified `.meta/` contains no `example.cpp` — stated explicitly in section 1 note 3. All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 0, result FAIL — matches header (4270-4273) and terminal JSON (5671-5673).
4. **Corrections made during cross-check**:
   - Draft described the attempt-2 rewrite as "renamed the class only"; re-reading shard-0 31430-31540 shows it also re-templated the implementation and added accessors — the accurate framing (right names, wrong ownership/accessor/iterator idioms) is now in section 3.
   - The recursive-lambda defect was initially noted only for attempt 1; re-check shows it persisted verbatim into attempt 2 (shard-0 31447-31456) — recorded in both anatomy entries and G5.
   - Failure-log line numbers for the terminal JSON corrected after re-grep: `tests_outcomes` at 5671-5673 (draft said 5668-5670); the attempt-1 class surface span corrected to 4691-4706 (draft said 4689-4704).
5. **No ground-truth problems**: `.meta/example.h` and `binary_search_tree_test.cpp` are present, consistent, and authoritative; the absence of `.meta/example.cpp` is intentional (header-only template reference), not missing ground truth.
