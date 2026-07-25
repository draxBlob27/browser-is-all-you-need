# linked-list — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `linked-list`
- Shard: `1` (failure log section header, line 33361: "- Shard: `1`")
- Test outcomes: `[False, True]` (failure log line 33363; terminal JSON `tests_outcomes: [false, true]`, failure log lines 60489-60492 / raw shard lines 67414-67417)
- Result: `PASS` (failure log line 33364) — attempt 1 failed, retry (attempt 2) passed.
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **33359-60544**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-1/benchmark.log` (linked-list run spans source lines ~17160-67467; heavily interleaved with 7 concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/linked-list/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/linked-list/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/linked-list/linked_list_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Chunk-1 bleed-over.** "Attempt/log chunk 1, source lines 16766-17169" (failure log lines 33409-33817) is the tail of the *space-age* task (space_age thinking, `space_age_test.cpp` compile errors at failure log 33717-33732). The linked-list run starts at source line 17160 (`fnames: .../linked-list/linked_list.h,...`, failure log 33806).
2. **Interleaved shard log.** The "Where It Failed / Terminal Test Log" block (failure log 34511-60544, source lines 41441-67467) interleaves concurrently running tasks: sublist (`Tests failed .../sublist`, failure log 38215), meetup (45839), knapsack (45988), parallel-letter-frequency (46668), phone-number (56938), queen-attack (59448), and a queen-attack THINKING block at failure log 57779+ (source 64704+, "_white"/"_black" member discussion). None of that is linked-list model confusion; linked-list lines were traced by grepping `linked_list` / `linked-list.dir` / `List<int>`.
3. **Citation scheme.** Quotes cite failure-log line numbers with the log's own raw-shard source-line prefixes (e.g. failure log 34542 = source 41467).

## 2. Benchmark Contract (Ground Truth)

File set: `linked_list.h` + `linked_list.cpp`, namespace `linked_list`.

Public API (from `.meta/example.h` and enforced by `linked_list_test.cpp`):

- `template <typename T> class List` (example.h:17-18), constructed as `linked_list::List<int> llist{};` (linked_list_test.cpp:15, 23, 31, ...).
- `void push(T entry)` (example.h:26) — append at end; test: `llist.push(...)` then `REQUIRE(7 == llist.pop())` (test:16-17).
- `T pop()` (example.h:30) — remove+return last (test:17, 26-27).
- `T shift()` (example.h:32) — remove+return first (test:33, 40-41).
- `void unshift(T entry)` (example.h:28) — prepend (test:44-49).
- `size_t count()` (example.h:44) — element count incl. after mutation (test:66-87).
- `bool erase(T entry)` (example.h:34-42) — remove first matching element, return whether found (test:112-152).

Exception policy: `pop()`/`shift()` on an empty list throw `std::runtime_error` (example.h:50-52, `"Cannot remove elements from empty list."`). **Not enforced by the visible test file** (no `REQUIRE_THROWS` in linked_list_test.cpp); the "popping to empty doesn't break the list" cases (test:90-110) only verify the list stays usable after being drained.

Critical structural contract: **the reference implements the entire template in the header** (example.h:17-67 — all member functions defined inline inside `class List`); `.meta/example.cpp` is an empty translation unit (example.cpp:1-5, just the include and an empty namespace). Template member definitions in a `.cpp` are invisible to other translation units unless explicitly instantiated — this is exactly the trap that failed attempt 1. The test instantiates only `List<int>` (test:15-178).

Edge cases enforced: interleaved push/pop/shift/unshift ordering (test:52-63), count after mutations (test:78-87), drain-then-reuse (test:90-110), erase the only element (test:112-117), erase absent value returns false (test:119+).

## 3. Failure Anatomy

### Attempt 1 — outcome False (link failure: template definitions in `.cpp` + diff-format answer)

**What the model emitted.** After planning thinking (failure log 33821+, source 17792+: "Template class `List`... `push`... `pop`... `shift`... `unshift`... `count`... `erase`", source 17799-17806), the answer (failure log 34295, source 18266 `► **ANSWER**`) delivered **diff-hunk file listings** (`linked_list.h` / ```` ```diff ```` / `@@ -1,5 +1,33 @@`, failure log 34297-34300, source 18268-18271; `linked_list.cpp` `@@ -1,5 +1,116 @@`, source 18310-18313) despite `edit_format: whole` and a system prompt demanding whole files. Aider applied them ("Applied edit to linked_list.h/.cpp", failure log 34463-34464, source 18434-18435).

**The defect.** All template member definitions were placed in `linked_list.cpp` (failure log 34391-34457, source 18362-18427: `template <typename T> void List<T>::push(...)` etc.) with **no explicit template instantiation**. The header held declarations only. When the test TU was linked, every `List<int>` member was an unresolved symbol.

**Compiler/linker evidence** (failure log 34517-34720, source 41442-41645):

```
41467: /aider/linked-list/linked_list_test.cpp:15:(.text+0x2a): undefined reference to `linked_list::List<int>::List()'
41468: ... undefined reference to `linked_list::List<int>::push(int const&)'
41469: ... undefined reference to `linked_list::List<int>::pop()'
```
(failure log 34542-34544; ~90 more identical undefined references through failure log 34715, then `collect2: error: ld returned 1 exit status` and `Tests failed: .../linked-list`, failure log 34720 = source 41645.)

Note the build compiled `linked_list.cpp.o` and `linked_list_test.cpp.o` cleanly (source 41462-41464) — this is purely a link-time template-visibility failure, not a syntax error.

**Secondary artifact.** The post-apply marked listing of the header shows a spurious overload `void shift(const T& value);` next to `T shift();` (failure log 34482-34483, source 18455-18456) — an artifact of the diff-hunk answer/apply cycle that no test referenced; later turns removed it.

### Attempt 2 (retry with linker output) — outcome True (PASS)

**What the retry changed.** The retry thinking correctly diagnosed the root cause: "*linked_list.cpp*: ... Include the implementations (already present). **Add explicit instantiations.**" (failure log 36683, source 43608), sketching `template class linked_list::List<int>;` (failure log 36688-36690, source 43613-43615). The answer — **again in ```` ```diff ```` format** — appended to the cpp:

```
43756: +    // Explicit template instantiation for int
43757: +    template class linked_list::List<int>;
43758: +    template class linked_list::List<std::string>;
```
(failure log 36831-36833; applied, failure log 36840-36841 = source 43765-43766.)

**Post-fix churn.** Aider kept sending signal-free lint prompts (`# Fix any errors below, if possible.` with █ markers; failure log 36843+). The marked lines repeatedly pointed at the explicit-instantiation lines themselves (failure log 57770-57772, source 64695-64697), and the model burned turns second-guessing the correct fix — "The explicit instantiation was the solution." (failure log 57403, source 64328) vs. worrying CMake wasn't linking the cpp (failure log 57358, source 64283) — and emitted **empty ```` ```diff ```` blocks** for both files (failure log 58870-58880, source 65795-65805), which Aider no-op "applied" (failure log 58884-58885, source 65809-65810). The final turn re-emitted **whole files** with both explicit instantiations retained (failure log 60296-60385, source 67221-67382: `template class linked_list::List<int>;` / `template class linked_list::List<std::string>;`, source 67378-67379), applied at failure log 60221-60222 (source 67146-67147).

**Terminal result.** Build and full pass: `[100%] Built target linked-list`, `All tests passed (42 assertions in 19 test cases)` (failure log 60477-60479, source 67402-67404); result JSON `tests_outcomes: [false, true]` (failure log 60489-60492).

### Hard evidence vs inference

- Hard evidence: diff-format answers (failure log 34297, 36831), template definitions in `.cpp` without instantiation (failure log 34391-34457), link errors (failure log 34542-34715), the instantiation fix (failure log 36831-36833), empty diff no-ops (failure log 58870-58880), final pass (failure log 60479).
- Inference: root cause of attempt 1 is (a) not knowing/applying the rule that template member definitions must live in the header (as the reference does) or be explicitly instantiated, compounded by (b) diff-format emission under a whole-file contract. The retry succeeded because the linker diagnostic is explicit and the model mapped it to "add explicit instantiation". The post-fix churn shows weak no-op-reply policy under signal-free █ prompts. Note the model never adopted the reference's idiomatic header-only approach — explicit instantiation is a valid but less general fix (it must enumerate every `T`; here `List<std::string>` was instantiated although the tests only use `int`).

## 4. Knowledge / Capability Gaps

- **G1 — Template/translation-unit linkage rule.** Definitions of class-template members in a `.cpp` are not instantiated for other TUs; attempt 1 shipped exactly that (failure log 34391-34457) and failed at link time (failure log 34542). The model knew the *data structure* cold but not the build-level contract.
- **G2 — Whole-file format contract.** Both the attempt-1 answer and the retry fix were emitted as ```` ```diff ```` hunks under `edit_format: whole` (failure log 34297-34300, 36831); the retry's diff even required Aider to apply hunks to a 116-line expansion. Format non-compliance is a recurring tax on every turn.
- **G3 — Idiomatic header-only template design.** The reference puts the whole template in the header (example.h:17-67, empty example.cpp). The model defaulted to a non-template header/impl split and then patched with explicit instantiation — a local fix, not the canonical design for header-shipped templates.
- **G4 — Repair behavior under signal-free retry prompts.** With █ markers and no error text, the model re-litigated the already-correct instantiation fix (failure log 57358-57544, source 64283-64444) and answered with empty diff blocks (failure log 58870-58880) instead of stating "no error visible" and re-emitting unchanged files.
- **G5 — Defensive scope creep in fixes.** The final cpp instantiates `List<std::string>` although the test only uses `List<int>` (failure log 60383-60384, source 67378-67379; test file uses only `int`). Harmless here, but shows fixes are not calibrated to the actual requirement surface.

## 5. SFT Task Specifications (26 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-habit-tracker
- Files: habit_tracker.cpp, habit_tracker.h (test file: habit_tracker_test.cpp)
- API: namespace `habits`; `class tracker { public: void check_in(const std::string& habit); int streak(const std::string& habit) const; };`
- Prompt shape: daily-habit streak app; starter files are guard + empty namespace; instructions demand whole-file listings.
- Target capability: G2 — emit complete files, never diff hunks.
- Target answer shape: two whole-file listings, declarations in header, definitions in cpp.
- Difficulty / variation: minimal surface; format is the only trap.

### Spec 02: whole-file-on-retry-seed-inventory
- Files: seed_vault.cpp, seed_vault.h (test file: seed_vault_test.cpp)
- API: namespace `garden`; `class vault { public: void store(const std::string& seed, int grams); int grams_of(const std::string& seed) const; };`
- Prompt shape: seed-bank storage; turn 1 shows a model answer in diff-hunk format (treated as malformed), turn 2 repeats the whole-file requirement.
- Target capability: G2 — format recovery on retry: second answer must be whole files.
- Target answer shape: whole files with identical semantics to the diff attempt.
- Difficulty / variation: conditions on a prior malformed answer.

### Spec 03: template-header-only-observatory-queue
- Files: observation_queue.h, observation_queue.cpp (test file: observation_queue_test.cpp)
- API: namespace `observatory`; `template <typename T> class queue { public: void enqueue(T item); T dequeue(); bool empty() const; };`
- Prompt shape: telescope observation-request queue; starter has both files; note says the build compiles the cpp separately.
- Target capability: G1/G3 — define all template members inside the header (inline in-class or below the class in the same header); cpp keeps only the include + empty namespace.
- Target answer shape: header-only implementation; no member definitions in the cpp.
- Difficulty / variation: the canonical fix (not explicit instantiation).

### Spec 04: template-header-only-freezer-stack
- Files: freezer_stack.h, freezer_stack.cpp (test file: freezer_stack_test.cpp)
- API: namespace `lab`; `template <typename T> class stack { public: void push(const T& v); T pop(); size_t depth() const; };`
- Prompt shape: cryo-lab sample stack (LIFO).
- Target capability: G1/G3 — header-only template; variation with `const T&` push and `size_t` accessor.
- Target answer shape: whole header with inline definitions; cpp nearly empty.
- Difficulty / variation: LIFO semantics instead of FIFO to prevent memorization.

### Spec 05: explicit-instantiation-codec-registry
- Files: codec.h, codec.cpp (test file: codec_test.cpp)
- API: namespace `media`; `template <typename T> class codec { public: T decode(const std::string& wire) const; };` with definitions in the cpp and, at the bottom, explicit instantiation only for the two types the tests use (`int`, `double`).
- Prompt shape: telemetry codec library where the team mandates definitions stay in the cpp for compile times.
- Target capability: G1 — when definitions live in a cpp, add `template class ns::X<T>;` for exactly the required types; know this is the alternative to header-only.
- Target answer shape: cpp ends with explicit instantiation lines; header declares only.
- Difficulty / variation: teaches the *other* legal pattern and its enumerate-every-T cost (contrast with Spec 03/04).

### Spec 06: linker-error-repair-aquaponics
- Files: tank_cycle.h, tank_cycle.cpp (test file: tank_cycle_test.cpp)
- API: namespace `aqua`; `template <typename T> class cycle { public: void add(T reading); T latest() const; };`
- Prompt shape: repair — turn 1 (in prompt history) defined members in the cpp; turn 2 shows `undefined reference to 'aqua::cycle<double>::latest() const'` linker errors.
- Target capability: G1/G4 — map "undefined reference to template member" to missing header definition / missing explicit instantiation; fix by moving definitions to the header.
- Target answer shape: whole header with definitions moved in; cpp reduced to include + empty namespace; no unrelated edits.
- Difficulty / variation: repair turn with real linker diagnostics.

### Spec 07: linker-error-repair-coffee-roast
- Files: roast_log.h, roast_log.cpp (test file: roast_log_test.cpp)
- API: namespace `roastery`; `template <typename T> class log { public: void record(const T& entry); std::vector<T> entries() const; };`
- Prompt shape: repair — same seeded link failure, different domain; fix by explicit instantiation this time (spec constrains: "keep definitions in the cpp").
- Target capability: G1 — choose instantiation when the prompt forbids moving definitions; instantiate exactly the tested type(s).
- Target answer shape: cpp gains `template class roastery::log<int>;` only; header unchanged.
- Difficulty / variation: constraint forces the Spec-05 pattern under repair pressure.

### Spec 08: doubly-linked-deque-theory-carpool
- Files: ride_line.h, ride_line.cpp (test file: ride_line_test.cpp)
- API: namespace `carpool`; `template <typename T> class line { public: void join_back(T name); void join_front(T name); T leave_back(); T leave_front(); int size() const; };`
- Prompt shape: carpool pickup line, double-ended joins/leaves.
- Target capability: G1/G3 — doubly linked node manipulation (prev/next), header-only template, correct pointer rewiring on both ends.
- Target answer shape: header with Node struct + both-end operations; destructor frees nodes.
- Difficulty / variation: core data-structure skill in a fresh wrapper.

### Spec 09: sentinel-node-rink-roster
- Files: roster.h, roster.cpp (test file: roster_test.cpp)
- API: namespace `rink`; `template <typename T> class roster { public: roster(); void add(T skater); bool remove(T skater); int count() const; };`
- Prompt shape: ice-rink session roster; story notes removals happen mid-list.
- Target capability: edge cases — mid-list removal, remove-only-element, remove-absent returns false; sentinel or head/tail symmetry.
- Target answer shape: header-only template; removal handles head/tail/middle uniformly.
- Difficulty / variation: isolates the erase-by-value semantics.

### Spec 10: drain-and-reuse-ticket-window
- Files: window.h, window.cpp (test file: window_test.cpp)
- API: namespace `cinema`; `template <typename T> class window_queue { public: void arrive(T person); T serve(); bool empty() const; };`
- Prompt shape: box-office line that empties completely then refills.
- Target capability: edge cases — after draining to empty, head/tail pointers must reset so reuse works; no dangling pointer.
- Target answer shape: single-element and last-element paths reset both ends.
- Difficulty / variation: targets the classic head/tail desync bug.

### Spec 11: no-empty-listing-bakery-orders
- Files: order_board.cpp, order_board.h (test file: order_board_test.cpp)
- API: namespace `bakery`; `class board { public: void add(const std::string& item); int pending() const; };`
- Prompt shape: multi-turn — turn 2 says "Fix any errors below" with █-marked lines that contain no defect.
- Target capability: G4 — never answer with an empty code block; re-emit whole unchanged files or state no change is needed.
- Target answer shape: whole unchanged files plus one sentence; never an empty fence.
- Difficulty / variation: no-op-reply policy, non-template domain.

### Spec 12: marker-points-at-the-fix-beehive
- Files: hive.h, hive.cpp (test file: hive_test.cpp)
- API: namespace `apiary`; `template <typename T> class hive_log { public: void note(T event); T last() const; };` (header-only).
- Prompt shape: repair turn where █ markers point at a line that is already the correct fix (e.g. a correct include), and no compiler output is given.
- Target capability: G4 — do not revert or re-litigate a correct line just because it is marked; verify against the error evidence (none) and leave it.
- Target answer shape: unchanged whole files with a brief rationale.
- Difficulty / variation: counter-trains the linked-list "re-litigate the instantiation" churn.

### Spec 13: count-after-mutation-recycling
- Files: bin.h, bin.cpp (test file: bin_test.cpp)
- API: namespace `recycling`; `template <typename T> class bin { public: void toss(T item); T take(); int items() const; };`
- Prompt shape: recycling station bin; tests interleave toss/take and check `items()` after each.
- Target capability: edge cases — size counter invariant under every interleaving (increment/decrement exactly once per operation).
- Target answer shape: counter maintained in all paths including error paths that don't change size.
- Difficulty / variation: invariant-focused, fresh domain.

### Spec 14: exception-on-empty-library-bookdrop
- Files: bookdrop.h, bookdrop.cpp (test file: bookdrop_test.cpp)
- API: namespace `library`; `template <typename T> class bookdrop { public: void deposit(T book); T collect(); };` `collect` on empty throws `std::runtime_error`.
- Prompt shape: overnight book-return slot; prompt states empty collection must throw.
- Target capability: exception policy — `std::runtime_error` on empty removal, `<stdexcept>` included, throw before mutating state.
- Target answer shape: guard clause first; no counter/pointer changes on the throw path.
- Difficulty / variation: adds an enforced exception policy (absent from the benchmark task's tests).

### Spec 15: erase-first-occurrence-playlist-dedup
- Files: dedup.h, dedup.cpp (test file: dedup_test.cpp)
- API: namespace `tunes`; `template <typename T> class playlist { public: void add(T song); bool drop_first(T song); int length() const; };`
- Prompt shape: playlist cleanup removing only the first duplicate.
- Target capability: edge cases — first-occurrence-only removal (not all occurrences), return value reflects found/not-found.
- Target answer shape: traversal stops after first match; duplicates beyond the first survive.
- Difficulty / variation: semantics-precision trap (remove-all vs remove-first).

### Spec 16: contrastive-template-placement-weatherballoon
- Files: sonde.h, sonde.cpp (test file: sonde_test.cpp)
- API: namespace `balloon`; `template <typename T> class readings { public: void push(T r); T pop(); };`
- Prompt shape: contrastive — prompt history shows a wrong answer (definitions in cpp, no instantiation) with its linker error, then asks for the corrected version.
- Target capability: G1/G3 — recognize the anti-pattern from its diagnostic and produce the header-only design.
- Target answer shape: corrected whole files; one line noting why the original failed to link.
- Difficulty / variation: negative-example-first ordering.

### Spec 17: header-self-sufficiency-campsite
- Files: gear_list.h, gear_list.cpp (test file: gear_list_test.cpp)
- API: namespace `camp`; `template <typename T> class gear { public: void pack(T item); std::vector<T> all() const; };`
- Prompt shape: camping gear checklist; starter header uses `std::vector` but forgets `<vector>`.
- Target capability: header self-sufficiency — a header must compile standalone; include what you use where you use it.
- Target answer shape: header gains the missing includes; cpp adds nothing redundant.
- Difficulty / variation: hygiene complement to template placement.

### Spec 18: value-vs-ref-params-climbing-gym
- Files: route_wall.h, route_wall.cpp (test file: route_wall_test.cpp)
- API: namespace `climbing`; `template <typename T> class wall { public: void set_route(const T& route); T route() const; };`
- Prompt shape: climbing-gym route setter; prompt notes T may be expensive to copy.
- Target capability: API judgment — const-ref in, value out; match qualifiers exactly.
- Target answer shape: signatures as specified; tests bind temporaries to the const-ref.
- Difficulty / variation: signature-fidelity angle.

### Spec 19: minimal-diff-repair-ski-lift
- Files: lift_queue.h, lift_queue.cpp (test file: lift_queue_test.cpp)
- API: namespace `ski`; `class lift_queue { public: void board(int pass_id); int next(); };`
- Prompt shape: repair — turn 2 shows one concrete compile error (missing `#include <stdexcept>`); surrounding code contains a style smell that is NOT an error.
- Target capability: G4/G5 — fix exactly the reported error; do not touch unrelated lines.
- Target answer shape: whole files differing only in the include; mechanical minimal-diff check applies.
- Difficulty / variation: minimal-repair discipline.

### Spec 20: no-defensive-scope-creep-star-chart
- Files: chart.h, chart.cpp (test file: chart_test.cpp)
- API: namespace `astro`; `template <typename T> class chart { public: void plot(T star); T brightest() const; };`
- Prompt shape: repair — linker error names exactly one missing instantiation (`chart<double>`); the fix must instantiate only that type, not a guessed set.
- Target capability: G5 — calibrate the fix to the diagnostic; do not add speculative instantiations "just in case".
- Target answer shape: single `template class astro::chart<double>;` added; nothing else.
- Difficulty / variation: counter-trains the gratuitous `List<std::string>` instantiation.

### Spec 21: whole-file-final-answer-ferry
- Files: ferry_lane.h, ferry_lane.cpp (test file: ferry_lane_test.cpp)
- API: namespace `harbor`; `template <typename T> class lane { public: void queue(T vehicle); T board(); int waiting() const; };`
- Prompt shape: three-turn chat — turn 1 diff answer (malformed), turn 2 repair, turn 3 asks for the final state of both files.
- Target capability: G2 — final consolidation turn re-emits clean whole files incorporating all accepted fixes.
- Target answer shape: whole files, no diff fences, all prior fixes present.
- Difficulty / variation: mirrors the linked-list final-turn consolidation.

### Spec 22: node-ownership-vineyard-rows
- Files: vine_rows.h, vine_rows.cpp (test file: vine_rows_test.cpp)
- API: namespace `vineyard`; `template <typename T> class rows { public: rows(); ~rows(); void plant(T vine); T harvest(); };`
- Prompt shape: vineyard row manager with raw owning pointers; destructor must free all nodes.
- Target capability: ownership semantics — destructor walks and deletes; no leak, no double-delete on the single-element path.
- Target answer shape: delete-before-advance loop; last-element path nulls both ends.
- Difficulty / variation: RAII/ownership gap underpinning list correctness.

### Spec 23: smart-pointer-list-alternative-museum
- Files: exhibit_line.h, exhibit_line.cpp (test file: exhibit_line_test.cpp)
- API: namespace `museum`; `template <typename T> class line { public: void add(T exhibit); bool remove(T exhibit); int count() const; };`
- Prompt shape: museum exhibit line; prompt allows `std::shared_ptr`/`std::make_shared` for links.
- Target capability: modern alternative — implement links with smart pointers (as the reference does) so no manual delete is needed.
- Target answer shape: header includes `<memory>`; no raw `delete` anywhere.
- Difficulty / variation: contrastive idiom to Spec 22, same data structure.

### Spec 24: empty-namespace-starter-discipline-marina
- Files: dock_register.h, dock_register.cpp (test file: dock_register_test.cpp)
- API: namespace `marina`; `template <typename T> class slips { public: void assign(T boat, int slip); T boat_at(int slip) const; };`
- Prompt shape: starter files contain only `#pragma once` + empty namespace; full design required.
- Target capability: G2/G3 — from an empty starter, produce the whole conventional layout (guards kept, namespace comments, header-only template).
- Target answer shape: complete conventional files; starter boilerplate preserved verbatim.
- Difficulty / variation: greenfield-from-empty like the benchmark task.

### Spec 25: interleaved-ops-juggling-club
- Files: club_queue.h, club_queue.cpp (test file: club_queue_test.cpp)
- API: namespace `juggling`; `template <typename T> class props { public: void add_back(T p); void add_front(T p); T take_back(); T take_front(); int held() const; };`
- Prompt shape: juggling-club prop rack; tests hammer random interleavings of all four operations and verify order and count.
- Target capability: edge cases — full deque-style operation algebra; both ends must stay consistent under arbitrary interleaving.
- Target answer shape: symmetric front/back implementations; shared helper for insert/remove allowed.
- Difficulty / variation: hardest behavioral spec; mirrors test:52-63 interleaving pressure.

### Spec 26: bool-erase-contract-lost-and-found
- Files: found_box.h, found_box.cpp (test file: found_box_test.cpp)
- API: namespace `lostfound`; `template <typename T> class box { public: void deposit(T item); bool claim(T item); int remaining() const; };`
- Prompt shape: lost-and-found box; `claim` returns whether the item was present.
- Target capability: API contract fidelity — boolean result semantics (true only when an element was actually removed) and count updated only on success.
- Target answer shape: single traversal returning false at end; count untouched on miss.
- Difficulty / variation: return-value-contract precision, fresh wrapper.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — filename line, one fenced block per file, no diff hunks, no empty fences, no elision comments. Parser receipt required.
2. **Compile+link+test receipt**: hidden tests build (compile AND link) against the target answer in the benchmark's CMake/Catch2 shape; receipt stored. For template specs, the link step must be exercised from a separate test TU (a header-only sanity compile is not sufficient).
3. **Repair-turn gate**: for repair specs (06, 07, 16, 19, 20), the seeded turn-1 answer must actually produce the seeded linker/compiler failure, and the turn-2 target must eliminate it — both runs receipted.
4. **Template-placement gate**: for header-only specs (03, 04, 08-10, ...), the target cpp contains no member definitions; for explicit-instantiation specs (05, 07, 20), the cpp instantiates exactly the specified types — checked mechanically.
5. **Hidden-edge coverage**: list specs' tests must include interleaved ops, drain-then-reuse, erase-only-element, erase-absent, and count-after-mutation cases.
6. **Contamination check**: stories, identifiers, and fixtures must not reproduce linked-list's (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
7. **Minimal-repair gate**: specs 19/20 enforce a mechanical minimal diff between turn-1 and turn-2 targets.
8. **Answer-blind review**: a reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log and ground truth:

1. **Re-read every cited failure-log line/range** via sed and confirmed quotes verbatim: 33361-33364 (header), 33717-33732 (space-age bleed in chunk 1), 33821 (attempt-1 thinking start, source 17792), 34295-34300 (ANSWER + diff fence), 34391-34457 (cpp template definitions), 34463-34464 (applied), 34482-34483 (spurious `void shift(const T& value);` overload in post-apply marked listing), 34542-34544 (first undefined references), 34715-34720 (collect2 / Tests failed), 36683-36690 (retry diagnosis "Add explicit instantiations"), 36831-36833 (instantiation diff), 36840-36841 (applied), 57770-57772 (█ markers on instantiation lines), 58870-58885 (empty diff no-op answers), 60221-60222 (final apply), 60296-60385 (final whole-file answer, instantiations at source 67378-67379), 60477-60479 (pass), 60489-60492 (`tests_outcomes: [false, true]`).
2. **Re-checked every API claim** against `.meta/example.h` (template `List` at lines 17-18; push/unshift/pop/shift/erase/count at lines 26-44; `std::runtime_error` policy at lines 50-52; fully header-defined through line 67), `.meta/example.cpp` (empty TU, lines 1-5), and `linked_list_test.cpp` (`List<int>` construction line 15; accessor REQUIREs 16-17, 26-27, 33, 40-41, 48-49, 68-87; drain-reuse 90-110; erase 112-152; no `REQUIRE_THROWS` anywhere — verified by grep, exit 1). All contract claims match.
3. **Outcome array and shard**: `[False, True]`, shard 1, result PASS — matches header (33361-33364) and terminal JSON (60489-60492).
4. **Corrections made during cross-check**:
   - Interleaving attribution: the sublist/meetup/knapsack/parallel-letter-frequency/phone-number/queen-attack `Tests failed` blocks and the queen-attack THINKING block inside the section's terminal range (e.g. failure log 38215, 57779+) are concurrent-task shard-log interleaving, not linked-list model output; documented in section 1 note 2 instead of the failure anatomy.
   - Chunk-1 (source 16766-17169) is the space-age task tail; noted as slice-boundary bleed (section 1 note 1).
   - Draft stated the retry added only `List<int>` instantiation; re-reading failure log 36831-36833 (source 43756-43758) shows the retry diff added **both** `List<int>` and `List<std::string>` on the first repair turn — corrected in section 3 and in G5 (the speculative-instantiation habit was present from the first repair, not just the final answer).
   - Corrected five citation line numbers after re-grep: the `fnames:` run-start marker is at failure log 33806 (draft said ~33803), the █ markers on the instantiation lines are at failure log 57770-57772 (draft said 57720-57722), "The explicit instantiation was the solution." is at failure log 57403 (draft said ~57428), the CMake-worry line is at failure log 57358 (draft said ~57383), and the queen-attack THINKING bleed begins at failure log 57779 (draft said ~57729).
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `linked_list_test.cpp` are present, consistent, and authoritative.
