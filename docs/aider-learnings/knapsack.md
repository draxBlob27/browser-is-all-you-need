# knapsack — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `knapsack`
- Shard: `1` (failure log section header, line 18429: "- Shard: `1`")
- Test outcomes: `[False, True]` (failure log line 18431; terminal JSON `tests_outcomes: [false, true]`, failure log lines 33303-33306 / raw shard lines 66836-66839)
- Result: `PASS` (failure log line 18432) — attempt 1 failed, retry (attempt 2) passed.
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **18427-33358**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-1/benchmark.log` (knapsack run spans source lines ~40853-66889; interleaved with 7 concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/knapsack/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/knapsack/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/knapsack/knapsack_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Chunk-1 bleed-over.** "Attempt/log chunk 1, source lines 40560-40862" (failure log 18477-18784) is the tail of the *robot-name* task (thinking about `error: 'robot' in namespace 'robot_name'`, failure log 18506, source 40586). The knapsack run starts at source line 40853 (`fnames: .../knapsack/knapsack.h,...`, failure log 18773).
2. **Interleaved shard log.** The "Where It Failed / Terminal Test Log" block (failure log 19114-33358) opens with *meetup* compile errors (failure log 19124+, source 52657+), and contains meetup, parallel-letter-frequency (failure log 19971+), and queen-attack content (a queen_attack.h diff answer at failure log 32665-32700, source 66198-66233 — foreign-task bleed, not knapsack model output). Knapsack lines were traced by grepping `knapsack` / `maximum_value` / `solve_knapsack`.
3. **Citation scheme.** Quotes cite failure-log line numbers with the log's raw-shard source-line prefixes.

## 2. Benchmark Contract (Ground Truth)

File set: `knapsack.h` + `knapsack.cpp`, namespace `knapsack`.

Public API (from `.meta/example.h`):

- `struct Item { int weight; int value; };` (example.h:9-13) — the test builds `const std::vector<knapsack::Item> items{{100, 1}};` etc. (knapsack_test.cpp:21, 28, 36, 44, 52, 61), so member order `{weight, value}` matters for brace initialization.
- `int maximum_value(int maximum_weight, const std::vector<Item>& items);` (example.h:15) — **capacity first, items second, const-ref vector**. Enforced by every assertion: `REQUIRE(knapsack::maximum_value(max_weight, items) == 0);` (knapsack_test.cpp:13, 22, 30, 38, 46, 55, 65).
- Free function inside `namespace knapsack` (example.h:6-17) — no class, no static methods.

Exception policy: none — the contract has no throwing behavior and no invalid-input cases in the test file.

Implementation notes (reference): `.meta/example.cpp:6-15` uses a 1-D DP (`std::vector<int> dp(maximum_weight + 1)`, descending weight loop) and relies on a transitive `<algorithm>` for `std::max` (only `<vector>` is included via the header). A 2-D DP (as the model eventually shipped) is equally correct; parameter *names* (`maximum_weight` vs `capacity`) are not part of the contract.

Edge cases enforced: empty item list → 0 (test:9-13), single too-heavy item → 0 (test:18-22), greedy-by-weight fails (test:25-30), greedy-by-value fails (test:33-38), larger instances: 8 items → 900 (test:49-55), 15 items → 1458 (test:58-65).

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: invented function name + swapped parameter order)

**What the model emitted.** The answer (failure log 19003, source 42318 `► **ANSWER**`) delivered **diff-hunk file listings** under `edit_format: whole`: `knapsack.h` ```` ```diff ```` adding `#include <vector>` and a declaration, `knapsack.cpp` ```` ```diff ```` adding the definition (failure log 19006-19080, source 42320-42397). Applied by Aider (failure log 19086-19087, source 42401-42402).

**The defect — invented API.** The model declared and defined:

```
42338: +int solve_knapsack(const std::vector<Item>& items, int capacity);
42357: +int solve_knapsack(const std::vector<Item>& items, int capacity)
```
(failure log 19021/19040, source 42338/42357.)

Both the **name** (`solve_knapsack`, invented) and the **parameter order** (`items, capacity`, swapped) diverge from the contract `maximum_value(max_weight, items)`. The DP algorithm itself was already correct.

**Compiler evidence.** The test build failed with `'maximum_value' is not a member of 'knapsack'` at every call site — `knapsack_test.cpp:13:23`, `:22:23`, `:30:23`, `:38:23`, `:46:23`, `:55:23`, `:65:23` (failure log 19307-19373, source 52840-52906) — ending in `Tests failed: .../knapsack` (failure log 19380, source 52913).

### Attempt 2 (retry with compiler output) — outcome True (PASS)

**What the retry changed.** Shown the real compiler errors, the model diagnosed both defects precisely (failure log 30541-30596, source 64074-64129):

```
64076: The compilation errors occur because the test file is calling a function named
64077: `maximum_value`, but the provided implementation defines a function named
64078: `solve_knapsack`. Additionally, the test passes arguments in the order
64079: `(max_weight, items)`, so the function signature needs to match that order.
64097: -int solve_knapsack(const std::vector<Item>& items, int capacity);
64098: +int maximum_value(int capacity, const std::vector<Item>& items);
```
(failure log 30543-30546, 30564-30565.) The rename+reorder was applied in both files (failure log 30595-30596, source 64128-64129) — still in ```` ```diff ```` format.

**Post-fix churn.** Aider kept sending signal-free `# Fix any errors below, if possible.` prompts with █ markers. The model verbally concluded "No changes are required" (failure log 31835-31838, source 65368-65371) but still emitted **empty ```` ```diff ```` fences** for both files (failure log 31844-31854, source 65377-65387; again at failure log 31951-31953, source 65484-65486; and failure log 33160-33172, source 66693-66705), each no-op "applied" (failure log 31858-31859, 31957, 33176-33177). The final turn consolidated into a correct **whole-file** response (failure log 33202-33270, source 66735-66803: `int maximum_value(int capacity, const std::vector<Item>& items);`, source 66754).

**Terminal result.** `[100%] Built target knapsack`, `All tests passed (7 assertions in 7 test cases)` (failure log 33291-33293, source 66824-66826); result JSON `tests_outcomes: [false, true]` (failure log 33303-33306).

### Hard evidence vs inference

- Hard evidence: diff-format answers (failure log 19006-19022), invented `solve_knapsack(items, capacity)` (failure log 19021/19040), compile errors (failure log 19307-19373), retry rename+reorder (failure log 30564-30565, 30583-30584), empty-diff no-ops (failure log 31844-31854, 33160-33172), final pass (failure log 33293).
- Inference: attempt-1 root cause is API invention — the prompt does not name the required function, and the model confidently coined `solve_knapsack` instead of deriving the canonical Exercism name `maximum_value`, and guessed the parameter order `(items, capacity)` instead of `(capacity, items)`. The algorithmic core (0/1 knapsack DP) was never the problem. The repair succeeded immediately once the compiler output named the expected symbol — evidence that given signal, repair is strong; without signal (█-only prompts), the model still wastes turns emitting empty fences instead of a clean no-change whole-file answer.

## 4. Knowledge / Capability Gaps

- **G1 — Canonical Exercism C++ API naming.** The expected free-function name `maximum_value` was invented as `solve_knapsack` (failure log 19021), costing a full failed attempt (failure log 19307). The model needs a prior for deriving conventional API names from the exercise family rather than coining descriptive names.
- **G2 — Parameter-order fidelity.** The model swapped to `(items, capacity)` (failure log 19021/19040) vs the contract `(capacity, items)` (example.h:15; test:13). Argument order is part of the API contract and cannot be guessed from the story.
- **G3 — Whole-file format contract.** Attempt 1 and the repair were both ```` ```diff ```` hunks under `edit_format: whole` (failure log 19006-19022, 30557-30591); the final consolidation turn was the first whole-file answer (failure log 33202+).
- **G4 — Signal-free retry handling.** With █ markers and no error text, the model said "No changes are required" yet emitted empty ```` ```diff ```` fences (failure log 31844-31854, 33160-33172) instead of re-emitting whole unchanged files or omitting listings. Empty fences burn reflection turns as no-op "Applied edit"s.
- **G5 — Prompt-underdetermination strategy.** The story prompt gives no function name/signature; the model never hedged (e.g. matching the exercise stem + test-facing conventions) and committed to a guess. When the contract is underdetermined, the policy should be: prefer the canonical exercism-cpp API shape, keep the surface minimal (one free function + the given struct), don't add speculative extras.

## 5. SFT Task Specifications (24 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-tide-pool
- Files: tide_log.cpp, tide_log.h (test file: tide_log_test.cpp)
- API: namespace `tides`; `double average_level(const std::vector<double>& readings);`
- Prompt shape: coastal tide gauge summaries; starter files guard + empty namespace; whole-file instruction prominent.
- Target capability: G3 — complete file listings only.
- Target answer shape: two whole-file listings; declaration in header, definition in cpp.
- Difficulty / variation: minimal surface; format-only trap.

### Spec 02: whole-file-on-retry-orchard
- Files: harvest.cpp, harvest.h (test file: harvest_test.cpp)
- API: namespace `orchard`; `int total_crates(const std::vector<int>& per_tree);`
- Prompt shape: apple-harvest tally; turn 1 shows a diff-hunk answer (malformed), turn 2 repeats whole-file requirement.
- Target capability: G3 — format recovery on retry.
- Target answer shape: whole files, same semantics as the diff attempt.
- Difficulty / variation: conditioned on prior malformed answer.

### Spec 03: canonical-name-guess-ferry-capacity
- Files: ferry.cpp, ferry.h (test file: ferry_test.cpp)
- API: namespace `ferry`; `struct Vehicle { int length; int toll; };` `int maximum_revenue(int deck_length, const std::vector<Vehicle>& vehicles);`
- Prompt shape: ferry loading optimization story; prompt does NOT state the function name; instructions say "don't change names of existing functions" and the starter namespace is the only anchor.
- Target capability: G1 — derive the conventional API name from the exercise-stem convention (result-describing noun phrase, snake_case) rather than coining `solve_ferry`-style names.
- Target answer shape: single free function + given struct; no invented class wrappers.
- Difficulty / variation: name-underdetermined prompt, the core knapsack gap.

### Spec 04: param-order-backpack-analog-bakery
- Files: oven.cpp, oven.h (test file: oven_test.cpp)
- API: namespace `bakery`; `struct Pastry { int minutes; int rating; };` `int best_rating(int oven_minutes, const std::vector<Pastry>& pastries);`
- Prompt shape: oven scheduling with a time budget; hidden tests call `best_rating(minutes, pastries)` — budget first.
- Target capability: G2 — resource-first, candidates-second parameter order fidelity.
- Target answer shape: signature exactly as specified; definition mirrors it.
- Difficulty / variation: order trap with budget-vs-items asymmetry.

### Spec 05: param-order-contrastive-library
- Files: shelf.cpp, shelf.h (test file: shelf_test.cpp)
- API: namespace `library`; `struct Book { int width; int score; };` `int top_score(int shelf_width, const std::vector<Book>& books);`
- Prompt shape: contrastive — prompt history shows a wrong answer with `(books, shelf_width)` order and its compile error, then asks for the fix.
- Target capability: G2 — trust the test-facing call order as ground truth.
- Target answer shape: corrected signature in both files; one-line note.
- Difficulty / variation: negative-example-first.

### Spec 06: struct-brace-order-campsite
- Files: gear.cpp, gear.h (test file: gear_test.cpp)
- API: namespace `camp`; `struct Pack { int kilos; int joy; };` `int max_joy(int kilo_limit, const std::vector<Pack>& packs);`
- Prompt shape: hiking pack selection; tests brace-initialize `Pack{kilo, joy}`.
- Target capability: struct member declaration order matches documented `{weight-like, value-like}` order for aggregate init.
- Target answer shape: members declared in the documented order; no constructors added (aggregate preserved).
- Difficulty / variation: aggregate-initialization fidelity.

### Spec 07: dp-01-knapsack-analog-toolbox
- Files: toolbox.cpp, toolbox.h (test file: toolbox_test.cpp)
- API: namespace `workshop`; `struct Tool { int bulk; int usefulness; };` `int max_usefulness(int trunk_space, const std::vector<Tool>& tools);`
- Prompt shape: car-trunk tool selection.
- Target capability: 0/1 knapsack DP — each item usable at most once; descending-weight 1-D DP or correct 2-D DP.
- Target answer shape: correct DP; greedy solutions must fail hidden tests.
- Difficulty / variation: core algorithm in fresh wrapper.

### Spec 08: dp-edge-empty-freight
- Files: freight.cpp, freight.h (test file: freight_test.cpp)
- API: namespace `cargo`; `struct Crate { int volume; int priority; };` `int max_priority(int hold_volume, const std::vector<Crate>& crates);`
- Prompt shape: freight-plane loading; hidden tests include empty list and all-too-heavy cases expecting 0.
- Target capability: edge cases — empty input and zero-feasible-item inputs return 0 without crashing.
- Target answer shape: DP initialized to zeros; no special-casing needed but verified.
- Difficulty / variation: boundary-empty focus.

### Spec 09: greedy-trap-photo-safari
- Files: safari.cpp, safari.h (test file: safari_test.cpp)
- API: namespace `safari`; `struct Stop { int hours; int sightings; };` `int max_sightings(int trip_hours, const std::vector<Stop>& stops);`
- Prompt shape: safari itinerary planning; hidden tests include cases where best ratio-first selection is suboptimal.
- Target capability: algorithm judgment — recognize greedy-by-ratio fails; use exact DP.
- Target answer shape: exact DP, no ratio sorting.
- Difficulty / variation: anti-greedy training signal.

### Spec 10: rename-repair-lighthouse
- Files: beacon.cpp, beacon.h (test file: beacon_test.cpp)
- API: namespace `coast`; the test expects `int brightest_arc(int range, const std::vector<Lamp>& lamps);`; attempt 1 (in history) shipped `int solve_beacon(const std::vector<Lamp>& lamps, int range);`; turn 2 shows `error: 'brightest_arc' is not a member of 'coast'`.
- Prompt shape: repair/retry with the exact compile diagnostic.
- Target capability: G1/G2/G4 — rename and reorder to match the diagnostic; change nothing else.
- Target answer shape: whole files with only the signature fixed; algorithm body untouched.
- Difficulty / variation: pure signature repair.

### Spec 11: no-empty-fence-planetarium
- Files: show.cpp, show.h (test file: show_test.cpp)
- API: namespace `stars`; `int total_runtime(const std::vector<int>& segments);`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines and no compiler output.
- Target capability: G4 — state no error is visible and re-emit whole unchanged files; never empty fences.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 12: minimal-surface-no-speculation-aquifer
- Files: well.cpp, well.h (test file: well_test.cpp)
- API: namespace `water`; `struct Spring { int liters; int purity; };` `int best_purity(int daily_liters, const std::vector<Spring>& springs);`
- Prompt shape: water-source selection; temptation surface: instructions warn against adding helper classes/methods not requested.
- Target capability: G5 — minimal API surface: exactly one free function + the given struct; no speculative extras.
- Target answer shape: no extra classes, overloads, or helpers in the header.
- Difficulty / variation: surface-discipline.

### Spec 13: header-impl-split-vineyard-blend
- Files: blend.cpp, blend.h (test file: blend_test.cpp)
- API: namespace `winery`; `struct Barrel { int gallons; int score; };` `int best_blend(int tank_gallons, const std::vector<Barrel>& barrels);`
- Prompt shape: wine blending; starter has everything inline in the header (wrong for this spec) — asked to split conventionally.
- Target capability: header/impl separation for non-template code: struct + declaration in header, definition in cpp with namespace qualification.
- Target answer shape: header guard, includes (`<vector>`) in the file that uses them.
- Difficulty / variation: refactor direction inline→split.

### Spec 14: include-what-you-use-greenhouse
- Files: climate.cpp, climate.h (test file: climate_test.cpp)
- API: namespace `garden`; `int best_harvest(int bed_count, const std::vector<Bed>& beds);` using `std::max` in the cpp.
- Prompt shape: greenhouse bed allocation; starter cpp uses `std::max` without `<algorithm>` (relies on transitive include).
- Target capability: include hygiene — explicitly include `<algorithm>` for `std::max`, `<vector>` for `std::vector`.
- Target answer shape: explicit includes in the using file.
- Difficulty / variation: counters the transitive-include habit the reference itself exhibits.

### Spec 15: dp-1d-vs-2d-memory-climbing
- Files: expedition.cpp, expedition.h (test file: expedition_test.cpp)
- API: namespace `alpine`; `struct Kit { int weight; int warmth; };` `int max_warmth(int pack_weight, const std::vector<Kit>& kits);`
- Prompt shape: expedition gear; story mentions very large capacities, nudging memory efficiency.
- Target capability: space-optimized 1-D DP with descending weight loop; understand why descending prevents item reuse.
- Target answer shape: 1-D DP; comment noting the descending-loop invariant.
- Difficulty / variation: advanced — optimization beyond correctness.

### Spec 16: unbounded-contrastive-candy
- Files: candy.cpp, candy.h (test file: candy_test.cpp)
- API: namespace `shop`; `struct Sweet { int grams; int joy; };` `int max_joy_unbounded(int bag_grams, const std::vector<Sweet>& sweets);`
- Prompt shape: contrastive — story explicitly allows taking the same sweet repeatedly (unbounded knapsack); prompt history shows a 0/1 solution failing a hidden test.
- Target capability: distinguish 0/1 vs unbounded knapsack; ascending loop for unbounded.
- Target answer shape: ascending-weight DP; note the difference from 0/1.
- Difficulty / variation: algorithm-variant discrimination.

### Spec 17: repair-swap-only-birdwatching
- Files: counts.cpp, counts.h (test file: counts_test.cpp)
- API: namespace `birds`; test expects `int rarest_total(int hours, const std::vector<Watch>& watches);`; history answer has parameters swapped only (name correct).
- Prompt shape: repair — compiler error shows argument-type mismatch from the swapped order; fix is reorder only.
- Target capability: G2/G4 — minimal signature repair; no body edits.
- Target answer shape: whole files; only the parameter order changed.
- Difficulty / variation: isolates order repair from rename repair.

### Spec 18: free-function-vs-class-ant-farm
- Files: colony.cpp, colony.h (test file: colony_test.cpp)
- API: namespace `ants`; `struct Chamber { int size; int food; };` `int max_food(int tunnels, const std::vector<Chamber>& chambers);`
- Prompt shape: contrastive — history shows a class-wrapped `AntSolver::solve` answer failing against tests that call a free function.
- Target capability: G1/G5 — match the expected surface kind (free function in namespace, not a class).
- Target answer shape: free function at namespace scope; no class.
- Difficulty / variation: surface-kind fidelity.

### Spec 19: whole-file-final-answer-ski-resort
- Files: lift_pass.cpp, lift_pass.h (test file: lift_pass_test.cpp)
- API: namespace `resort`; `struct Run { int minutes; int thrill; };` `int max_thrill(int daylight, const std::vector<Run>& runs);`
- Prompt shape: three-turn chat — diff answer, repair, then final consolidation request.
- Target capability: G3 — final turn re-emits clean whole files incorporating accepted fixes.
- Target answer shape: whole files, no fences-with-hunks, all fixes present.
- Difficulty / variation: consolidation discipline.

### Spec 20: zero-capacity-glider
- Files: glider.cpp, glider.h (test file: glider_test.cpp)
- API: namespace `soaring`; `struct Part { int grams; int lift; };` `int max_lift(int gram_budget, const std::vector<Part>& parts);`
- Prompt shape: glider build; hidden tests include budget 0 (expect 0) and a zero-weight part with positive value (must be taken).
- Target capability: edge cases — zero budget, zero-weight items; loop bounds and DP init must handle both.
- Target answer shape: loops from 0 handled; zero-weight items included correctly.
- Difficulty / variation: numeric boundary traps.

### Spec 21: large-instance-dp-warehouse
- Files: warehouse.cpp, warehouse.h (test file: warehouse_test.cpp)
- API: namespace `depot`; `struct Pallet { int slots; int revenue; };` `long max_revenue(int dock_slots, const std::vector<Pallet>& pallets);`
- Prompt shape: warehouse dock allocation with many pallets; hidden tests use 15+ items and large totals.
- Target capability: correct DP at scale; return-type awareness (`long` per spec) and no overflow in accumulation.
- Target answer shape: DP with the specified wider return type.
- Difficulty / variation: scale + type-width awareness.

### Spec 22: const-ref-vector-signature-apiary
- Files: honey.cpp, honey.h (test file: honey_test.cpp)
- API: namespace `bees`; `struct Comb { int cells; int yield; };` `int best_yield(int frame_count, const std::vector<Comb>& combs);`
- Prompt shape: apiary frame selection; tests pass const vectors.
- Target capability: signature fidelity — `const std::vector<T>&` parameter (not by value, not non-const ref).
- Target answer shape: exact qualifiers in declaration and definition.
- Difficulty / variation: qualifier precision.

### Spec 23: no-rename-existing-struct-meteor
- Files: shower.cpp, shower.h (test file: shower_test.cpp)
- API: namespace `sky`; starter header already contains `struct Meteor { int magnitude; int rarity; };` — model must add `int best_watch(int night_hours, const std::vector<Meteor>& meteors);` without touching the struct.
- Prompt shape: meteor-shower planning; starter provides the struct; instruction: don't change existing names.
- Target capability: G1/G5 — preserve existing declarations verbatim; add only what's missing.
- Target answer shape: struct byte-identical; new function appended.
- Difficulty / variation: additive-only edit discipline.

### Spec 24: underdetermined-api-policy-tidepools
- Files: rockpool.cpp, rockpool.h (test file: rockpool_test.cpp)
- API: namespace `pools`; `struct Creature { int space; int charm; };` `int max_charm(int pool_space, const std::vector<Creature>& creatures);`
- Prompt shape: rock-pool exhibit; prompt underdetermines the function name; spec text (dataset-side) documents the naming policy: derive from the requested result ("maximum charm" → `max_charm`-family conventional name fixed by the hidden contract).
- Target capability: G5/G1 — under underdetermination, pick the conventional result-describing name and budget-first order, and keep the surface minimal.
- Target answer shape: single conventional free function.
- Difficulty / variation: meta-policy capstone combining G1+G2+G5.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, no elisions. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass against the target answer in the benchmark's CMake/Catch2 harness shape; receipt (command + exit code) stored.
3. **API-shape gate**: function name, parameter order, and qualifiers match the spec exactly; struct member order matches the spec's documented aggregate-init order. Checked by compiling the spec's test against the target.
4. **Repair-turn gate**: repair specs (05, 10, 17, 18) must seed a turn-1 answer that genuinely produces the shown diagnostic, and the turn-2 target must fix exactly that — mechanically minimal diff.
5. **Hidden-edge coverage**: DP specs' tests must include empty list, zero budget, all-too-heavy, greedy-trap, and ≥15-item cases.
6. **No-op-turn gate**: for signal-free retry specs (11), the target must contain no empty fences and no content changes — verified byte-wise.
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce knapsack's (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log and ground truth:

1. **Re-read every cited failure-log line/range** via sed/grep and confirmed quotes verbatim: 18429-18432 (header), 18506 (robot-name bleed), 18773 (fnames run-start), 19003-19087 (attempt-1 diff answer; invented declaration at 19021 = source 42338, definition at 19040 = source 42357), 19124 (meetup bleed), 19307-19373 (`'maximum_value' is not a member` errors), 19380 (Tests failed), 30541-30596 (retry diagnosis + rename/reorder diffs), 31833-31859 and 31941-31957 and 33152-33177 (empty-diff no-op answers), 32665-32700 (queen-attack bleed), 33202-33270 (final whole-file response), 33291-33293 (build + pass), 33303-33306 (`tests_outcomes: [false, true]`).
2. **Re-checked every API claim** against `.meta/example.h` (`struct Item{weight,value}` lines 9-13; `int maximum_value(int maximum_weight, const std::vector<Item>& items);` line 15), `.meta/example.cpp` (1-D DP lines 6-15), and `knapsack_test.cpp` (call order `maximum_value(max_weight, items)` at lines 13, 22, 30, 38, 46, 55, 65; brace-init member order at 21, 28, 36, 44, 52, 61; no throw cases). All contract claims match.
3. **Outcome array and shard**: `[False, True]`, shard 1, result PASS — matches header (18429-18432) and terminal JSON (33303-33306).
4. **Corrections made during cross-check**:
   - Interleaving attribution: meetup compile errors (19124+), parallel-letter-frequency content (19971+), and the queen_attack diff answer (32665-32700) inside the section are concurrent-task shard-log bleed, not knapsack model output — documented in section 1 note 2, excluded from the failure anatomy.
   - Chunk-1 (source 40560-40862) is the robot-name task tail; noted as slice-boundary bleed (section 1 note 1).
   - Draft described the final response turn as beginning with the ANSWER marker at 66685; re-reading failure log 33152-33202 shows the 66685 answer was another empty-diff no-op, and the actual final whole-file response is the benchmark `response:` at failure log 33202 (source 66735-66803) — corrected in section 3.
   - Noted during ground-truth re-check: the model's final parameter name `capacity` differs from the reference's `maximum_weight`; verified this is contract-irrelevant (parameter names are not part of the API) and stated as such in section 2 rather than flagged as a defect.
   - Corrected one citation line number after re-grep: the third empty-diff no-op answer starts at failure log 33160 (draft said 33161).
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `knapsack_test.cpp` are present, consistent, and authoritative. (Observation only: the reference relies on a transitive `<algorithm>` for `std::max`; not a defect, used as motivation for Spec 14.)
