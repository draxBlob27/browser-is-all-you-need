# zebra-puzzle — Failure Learning Document

Date of analysis: 2026-07-24. Eval run: `glm47-aider-expansion-sft-fixed26-20260723T091839Z` (GLM-4.7 SFT, Aider Polyglot C++, whole edit format).

## 1. Task Identity & Evidence Pointers

- Task slug: `zebra-puzzle`
- Shard: `1`
- Test outcomes: `[False, False]` (test run 1 FAIL — compile error; test run 2 FAIL — test timeout)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md`, lines 89397–115244 (header at 89397–89402; attempt chunk 1 at 89447, covering source lines 9574–10273; attempt chunk 2 at 90152, covering source lines 15390–16089; a large raw-shard excerpt follows at 90859 (`Source lines 16469-40849:`), containing interleaved foreign tasks plus zebra-puzzle's later turns and the terminal `Tests timed out!` at 115202 with the result JSON at 115203–115244).
- Raw shard log (cross-check evidence): `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-1/benchmark.log`. The failure log's quoted "source lines" are line numbers in this shard log, but the failure-log excerpts number them with a small positive offset (e.g. failure log 90886 quotes source line `16493:` for the text that is raw shard log line 16491) — verified during cross-check; both numbers are given where they differ. The shard log interleaves 8 concurrent tasks; foreign-task turns (phone-number, yacht, space-age, robot-name, sublist, queen-attack, parallel-letter-frequency, spiral-matrix) appear between zebra-puzzle turns and inside the failure log's big excerpt.
- Ground truth (read-only): `polyglot-benchmark/cpp/exercises/practice/zebra-puzzle/`
  - Reference: `.meta/example.h`, `.meta/example.cpp`
  - Tests: `zebra_puzzle_test.cpp`
  - Starters (NOT the solution): `zebra_puzzle.cpp`, `zebra_puzzle.h` at the exercise root. The starter header declares only `struct Solution`; it does **not** declare `solve()`.
- Existing analog dir: none for zebra-puzzle under `aider-fixed26-analogs/` (granularity reference: `aider-fixed26-analogs/fixed26-b001-all-your-base/`).
- Result JSON (failure log 115203–115244): `"tests_outcomes": [false, false]`, `"test_timeouts": 1`, `"num_error_outputs": 0`, `"num_user_asks": 1`, `"num_exhausted_context_windows": 0`, `"num_malformed_responses": 0`, `"edit_format": "whole"`, 3 chat turns.

## 2. Benchmark Contract (Ground Truth)

File set: `zebra_puzzle.h` + `zebra_puzzle.cpp`, namespace `zebra_puzzle`.

Public API (from `.meta/example.h`):

- `.meta/example.h:6` — `namespace zebra_puzzle {`
- `.meta/example.h:8-11` — `struct Solution { std::string drinksWater; std::string ownsZebra; };`
- `.meta/example.h:13` — `Solution solve();` (free function inside the namespace; takes no arguments; **not declared in the starter header**, so the model must add the declaration itself)

Semantics enforced by `zebra_puzzle_test.cpp`:

- `:9` — `zebra_puzzle::Solution solution = zebra_puzzle::solve();` (calling convention: namespace-qualified free function returning the struct by value)
- `:11` — `REQUIRE(solution.drinksWater == "Norwegian");`
- `:17` — `REQUIRE(solution.ownsZebra == "Japanese");`

So the struct fields hold **nationality strings** (the *person* who drinks water / owns the zebra), not the attribute values (`"Water"`, `"Zebra"`). The reference computes them by scanning the solved houses for the pet/drink and mapping the house's nationality through a string table (`.meta/example.cpp:248-261`, `nationalityStrings` at `:19-23`).

Exception policy: none — the contract has no throwing behavior.

Performance constraint (implicit but decisive): the instructions state "There are 24 billion (5!⁵ = 24,883,200,000) possible solutions, so try ruling out as many solutions as possible" (user instructions, failure log 89438). The reference solves it by nested `next_permutation` over five attribute vectors with layered constraint checks that `continue` early (`.meta/example.cpp:181-241`). Any solver that enumerates the full space without pruning, or whose constraint check can never be satisfied, will not terminate within the harness test timeout — and the harness killed this run: `Tests timed out!` (failure log 115202).

Output-format constraints: Aider *whole* edit format — filename line, opening fence, **entire file content**, closing fence; never diff hunks, never elisions (system prompt, failure log 89406–89428; restated in the user instructions, failure log 89438).

## 3. Failure Anatomy

The zebra-puzzle session had 3 model turns, then two recorded test outcomes: a compile-error failure and a test-timeout failure.

### Turn 1 (shard 9574–11508; failure log chunk 1 = 89447–90150, source lines 9574–10273) — wrong manual solution, diff-format answer

The model spent ~700 lines of thinking solving the logic puzzle by hand and reached a **wrong** answer:

> `Thus, the **Norwegian** drinks water, and the **Englishman** owns the zebra.` (raw shard log 11063–11064; the correct zebra owner per the tests is `"Japanese"`, `zebra_puzzle_test.cpp:17`)

It then answered in ```` ```diff ```` unified-diff fences for both files despite the whole-file mandate:

> `zebra_puzzle.h` / ```` ```diff ```` / `@@ -8,8 +8,10 @@` / `+Solution solve();` (raw shard log 11069–11078)
> `zebra_puzzle.cpp` / ```` ```diff ```` / `@@ -1,3 +1,336 @@` (raw shard log 11087–11090)

The header hunk correctly adds the missing `Solution solve();` declaration (matching `.meta/example.h:13`). The cpp hunk implements a backtracking solver whose `isValid` **hardcodes the manually-derived house indices as fixed positions**, including mutually contradictory ones — clue 2 encoded as `houses[3]` must be Englishman+Red (raw shard log 11163), clue 14 as `houses[3]` must be Japanese+Chess (raw shard log 11216): both cannot hold, so `isValid` can never return true. Aider applied the diffs anyway (`Applied edit to zebra_puzzle.cpp / .h`, raw shard log 11507–11508) and replied with a marked-line reflection prompt (`# Fix any errors below, if possible.`, marking the `drinksWater`/`ownsZebra` struct fields, raw shard log 11515–11525).

### Turn 2 (shard 15390–16288; failure log chunk 2 = 90152–90855, source lines 15390–16089) — rewrite keeps hardcoded indices and wrong return semantics

Facing the vague marked-line prompt, the model re-emitted the solver, again as a ```` ```diff ```` hunk (raw shard log 16000–16004: `zebra_puzzle.cpp` / ```` ```diff ```` / `@@ -95,13 +95,10 @@`). Its thinking explicitly settled the return-value semantics — wrongly:

> `15970:             return Solution{to_string(houses[0].beverage),`
> `15975:         Wait, Norwegian drinks water (House 0). Englishman owns zebra (House 3).`
> `15976:         So `to_string(houses[0].beverage)` is "Water".`
> (failure log 90735–90741, quoting source lines 15970–15976)

i.e. it decided `drinksWater` should be the string `"Water"` (the beverage) and `ownsZebra` the string `"Zebra"` (the pet) — the tests require the nationalities `"Norwegian"` / `"Japanese"` (`zebra_puzzle_test.cpp:11,17`). The applied file (echoed at raw shard log 16292–16464) shows:

- `isValid` still checking fixed indices, e.g. clue 2 as `if (houses[3].nationality != Nationality::Englishman || houses[3].color != Color::Red) return false;` and clue 14 as `if (houses[3].nationality != Nationality::Japanese || houses[3].hobby != Hobby::Chess) return false;` — contradiction retained;
- `solve()` returning `Solution{to_string(houses[0].beverage), to_string(houses[3].pet)}` — attribute strings, not nationalities;
- `solveRecursive(int index, std::array<House,5>&)` defined **after** `solve()` with no forward declaration, calling itself through 5 nested loops over all 5 colors × 5 nationalities × 5 pets × 5 beverages × 5 hobbies per recursion level (3125 combos/level, depth 5) with **no all-different pruning and no early constraint checks** — an effectively non-terminating search when `isValid` is unsatisfiable.

### Test run 1 (shard 16468–16501; failure log 90880–90897) — compile failure

> `16493: /aider/zebra-puzzle/zebra_puzzle.cpp:130:9: error: ‘solveRecursive’ was not declared in this scope`
> `16494:   130 |     if (solveRecursive(0, houses)) {`
> (failure log 90886–90887; raw shard log 16491–16492)

`solve()` calls `solveRecursive` before its definition and no declaration is in scope. Outcome false #1.

### Turn 3 (shard 28956–29988; failure log 103463–104375) — minimal compile fix only

The model correctly diagnosed the error (`Forward declaration!`, failure log 103463, source line 29070) and answered with another ```` ```diff ```` hunk adding:

> `29980: +// Forward declaration to ensure compiler recognizes solveRecursive before`
> `29981: solve() calls it`
> `29982: +bool solveRecursive(int index, std::array<House, 5>& houses);`
> (failure log 104373–104375, quoting source lines 29980–29982)

It fixed **only** the declaration order — it did not re-examine the contradictory constraints, the missing pruning, or the return-value semantics, even though the reflection context gave no new information beyond the compiler error. Applied at raw shard log 29988. The final file (echoed at failure log 104512, source line 30119, and 104529–104530, source lines 30136–30137) still returns:

> `30137:         return Solution{to_string(houses[0].beverage), to_string(houses[3].pet)};`

### Test run 2 (shard 30175 → 40809; failure log 115202–115244) — timeout

The test binary was built and started (raw shard log 30175) but never finished; the harness killed it:

> `40809:  38%|███▊      | 5/13 [11:08<18:02, 135.27s/it]Tests timed out!` (failure log 115202)
> `"tests_outcomes": [false, false]` (failure log 115209–115212), `"test_timeouts": 1` (failure log 115215), `"num_user_asks": 1` (failure log 115221), `"num_exhausted_context_windows": 0` (failure log 115222)

Because `isValid` requires `houses[3]` to be simultaneously Englishman (clue 2 encoding) and Japanese (clue 14 encoding), and simultaneously Red and Green (clue 4 encoding), no assignment can satisfy it; `solveRecursive` therefore explores the full ~3125⁵ ≈ 3×10¹⁷ leaf space with no pruning and never returns. Even had it terminated, `solve()` would have returned `{"Water", "Zebra"}`-style attribute strings and failed both assertions.

### Hard evidence vs. inference

Hard evidence: wrong manual conclusion "the **Englishman** owns the zebra" (raw shard 11063–11064); ```` ```diff ```` fences in all three answers (raw shard 11069–11090, 16000–16004, 29966–29988); hardcoded index constraints incl. the `houses[3]` Englishman/Japanese contradiction (raw shard 11163, 11216); the self-trace fixing wrong return semantics (failure log 90735–90741); compile error `'solveRecursive' was not declared in this scope` (failure log 90886); forward-declaration-only repair (failure log 104373–104375); final return of `to_string(houses[0].beverage), to_string(houses[3].pet)` (failure log 104529–104530); `Tests timed out!` + `"test_timeouts": 1` (failure log 115202, 115215).

Inference (root-cause categories): (a) the model solved the puzzle by hand in its thinking, got it wrong, and then baked that wrong hand-solution into the code as fixed positional constraints instead of encoding the 15 clues as general relations — a deduction error became an unsatisfiable constraint set; (b) it has no complexity intuition for combinatorial search: 5 nested attribute loops per recursion level with zero pruning, ignoring the prompt's explicit "rule out as many solutions as possible" hint; (c) it decided field semantics from its own narrative ("So `to_string(houses[0].beverage)` is `"Water"`") rather than from the struct field names (`drinksWater` = *who* drinks water); (d) on repair turns it fixes only the literal error reported and never re-audits surrounding logic; (e) it defaults to diff fences despite a whole-file system prompt.

## 4. Knowledge / Capability Gaps

- **G1 — Format-contract discipline (whole-file listings).** All three answers used ```` ```diff ```` unified-diff fences under a `whole` edit-format prompt that demands entire-file listings (raw shard 11069–11090, 16000–16004, 29966–29988 vs. failure log 89406–89428; `"edit_format": "whole"` at failure log 115208). Aider happened to apply them; the behavior is non-compliant and fragile.
- **G2 — Combinatorial-search design: pruning, distinctness, termination.** The solver nests 5 attribute loops (3125 combos) per recursion level to depth 5 with no all-different enforcement and no early constraint rejection (raw shard 16292–16464), ignoring the prompt's own 24-billion hint (failure log 89438). The reference's layered `next_permutation` + early `continue` structure (`.meta/example.cpp:181-241`) is exactly the idiom the model lacks. Directly caused the timeout (failure log 115202).
- **G3 — Don't hardcode a hand-derived answer; encode constraints generally.** The model manually solved (wrongly — "Englishman owns zebra", raw shard 11063–11064) and then wrote `isValid` as fixed-index assertions (`houses[3]` must be Englishman+Red and Japanese+Chess, raw shard 11163, 11216), producing a mutually contradictory, unsatisfiable validator. Clues like "next to" / "immediately to the right of" must be encoded as relations over positions, not as memorized indices.
- **G4 — Return-value semantics: identity vs. attribute.** The contract's fields name a *person* (`drinksWater`, `ownsZebra`) and the tests require nationality strings (`zebra_puzzle_test.cpp:11,17`; reference maps nationality→string, `.meta/example.cpp:248-261`). The model returned the attribute values themselves (`to_string(houses[0].beverage)`, `to_string(houses[3].pet)`; failure log 90735–90741, 104529–104530).
- **G5 — C++ declaration order / forward declarations.** `solve()` called `solveRecursive` before any declaration was visible → hard compile error (failure log 90886). The model needed a compiler round-trip to learn that a free function must be declared before use (fixed at failure log 104373–104375).
- **G6 — Repair-turn shallowness.** The turn-3 repair addressed only the literal compiler diagnostic and shipped without re-checking logic, constraints, or semantics — converting a compile failure into a timeout failure (failure log 103463, 104373–104375, then 115202). A repair turn should re-audit the whole file when the fix is trivially local but the task is computationally risky.

## 5. SFT Task Specifications (28 specs)

Answer-blind: no benchmark test fixtures, clue text, or reference code are copied. Every spec lists an exact API the dataset author designs; stories are new and none reuse the zebra/houses wrapper. The contract has no exception policy, so the exception-policy spec minimum does not apply; two exception-flavored specs are still included for robustness (Specs 19, 28).

### Spec 01: whole-file-orchard-harvest
- Files: `orchard_harvest.cpp`, `orchard_harvest.h` (test file: `orchard_harvest_test.cpp`)
- API: namespace `orchard`; `int total_crates(const std::vector<int>& picks, int crate_capacity);` — no exceptions.
- Prompt shape: orchard apple-crating story; starter files contain only the namespace skeleton; system prompt demands whole-file listings.
- Target capability: G1 — return two complete file listings, filename line + plain fence, no diff hunks, no prose inside fences.
- Target answer shape: two whole-file listings; header with include guard + declaration; cpp with definition.
- Difficulty / variation: foundational; trivial logic, all grading weight on format.

### Spec 02: whole-file-canoe-rental
- Files: `canoe_rental.cpp`, `canoe_rental.h` (test file: `canoe_rental_test.cpp`)
- API: namespace `marina`; `double rental_cost(int hours, bool weekend);` and `int canoes_needed(int paddlers);`
- Prompt shape: canoe-rental pricing story; the user message repeats the whole-file rule twice (mirroring the eval prompt's redundancy).
- Target capability: G1 — resist the strong prior to answer with ` ```diff ` hunks for "modify this file" requests.
- Target answer shape: two whole-file listings, both files complete.
- Difficulty / variation: two functions; format is the only real demand.

### Spec 03: header-impl-planetarium-show
- Files: `planetarium_show.cpp`, `planetarium_show.h` (test file: `planetarium_show_test.cpp`)
- API: namespace `planetarium`; `struct Show { std::string title; int minutes; };` + `Show longest_show(const std::vector<Show>& shows);`
- Prompt shape: planetarium schedule story; starter header declares the struct only — the function declaration must be added by the model (mirrors starter lacking `solve()`).
- Target capability: G2-adjacent API completion + header/impl separation: add the missing declaration to the header, define out-of-line in the cpp.
- Target answer shape: header gains `Show longest_show(const std::vector<Show>& shows);` inside the namespace; cpp defines `planetarium::longest_show`.
- Difficulty / variation: discovering that the starter header is incomplete (direct analog of the missing `solve()` declaration).

### Spec 04: header-impl-beekeeper-apiary
- Files: `apiary.cpp`, `apiary.h` (test file: `apiary_test.cpp`)
- API: namespace `bees`; `struct Hive { std::string name; double kg_honey; };` + `double total_honey(const std::vector<Hive>& hives);` + `std::string richest_hive(const std::vector<Hive>& hives);`
- Prompt shape: beekeeper harvest story; empty namespace skeletons in both files.
- Target capability: header/impl separation — struct + declarations in header, all definitions in cpp; `<vector>`, `<string>` includes in the header because its declarations need them.
- Target answer shape: guarded header, out-of-line definitions, no `using namespace std;` in the header.
- Difficulty / variation: two free functions sharing one struct.

### Spec 05: forward-decl-forest-trail
- Files: `forest_trail.cpp`, `forest_trail.h` (test file: `forest_trail_test.cpp`)
- API: namespace `trail`; `bool reachable(int from, int to, const std::vector<std::vector<int>>& adj);` implemented via a file-local helper `bool visit(int node, int target, const std::vector<std::vector<int>>& adj, std::vector<bool>& seen);` defined **after** `reachable` in the cpp.
- Prompt shape: forest trail-network story; instructions require the helper to be defined after the public function.
- Target capability: G5 — add a forward declaration (or file-local prototype) before the point of use; know that C++ requires declaration before use.
- Target answer shape: cpp orders: includes → namespace → helper prototype → `reachable` definition → helper definition.
- Difficulty / variation: exact diagnostic the run hit, new domain, single file focus.

### Spec 06: identity-vs-attribute-seating
- Files: `banquet_seating.cpp`, `banquet_seating.h` (test file: `banquet_seating_test.cpp`)
- API: namespace `banquet`; `struct SeatInfo { std::string windowGuest; std::string headGuest; };` + `SeatInfo analyze(const std::vector<std::string>& guests, const std::vector<std::string>& seats);` where `seats[i]` is the seat type ("window", "aisle", "head", ...) of guest `guests[i]`; fields must contain **guest names**, never seat types.
- Prompt shape: banquet seating-chart story.
- Target capability: G4 — fields named for a *who* must carry the identity string, not the attribute value; read semantics from field names.
- Target answer shape: lookup loop mapping attribute→index→guest name; return struct by value.
- Difficulty / variation: direct repair of the `"Water"` vs `"Norwegian"` confusion without the puzzle story.

### Spec 07: solver-pruning-tile-grid
- Files: `tile_grid.cpp`, `tile_grid.h` (test file: `tile_grid_test.cpp`)
- API: namespace `tiles`; `bool fill_grid(std::vector<std::vector<int>>& grid);` — fill an N×N grid (N ≤ 4 given partially filled) so each row and column contains 1..N exactly once.
- Prompt shape: garden tile-laying story with Latin-square rules stated in prose.
- Target capability: G2 — backtracking with immediate constraint checks after each placement (prune at partial states), not generate-all-then-test.
- Target answer shape: recursive helper checking row/column conflicts before recursing; returns on first complete valid grid.
- Difficulty / variation: small N keeps tests fast; grading includes a termination-time budget.

### Spec 08: solver-permutation-early-reject
- Files: `shift_planner.cpp`, `shift_planner.h` (test file: `shift_planner_test.cpp`)
- API: namespace `clinic`; `std::vector<int> assign_nurses(int nurses, const std::vector<std::pair<int,int>>& incompatible_pairs);` — return a permutation of nurse→shift with no incompatible pair adjacent; empty vector if none.
- Prompt shape: clinic shift-scheduling story; prose warns "there are n! orders — reject bad prefixes early".
- Target capability: G2 — `std::next_permutation` with early `continue` on partial violation, or recursive prefix pruning; never enumerate-and-test-all blindly.
- Target answer shape: permutation loop with a `valid_prefix(k)` check inside the recursion/iteration.
- Difficulty / variation: sibling of the reference idiom (layered permutations) in miniature.

### Spec 09: contrastive-hardcoded-vs-general
- Files: `vault_dial.cpp`, `vault_dial.h` (test file: `vault_dial_test.cpp`)
- API: namespace `vault`; `int find_combination(const std::vector<int>& clues);`
- Prompt shape: contrastive pair — candidate A hardcodes an answer the (scripted) reasoning derived by hand; candidate B encodes the clue relations and searches. Row labels A wrong / B right with a one-line rationale.
- Target capability: G3 — a solver must encode the stated relations generally; a hand-derived constant is fragile and, here, wrong.
- Target answer shape: annotated A/B pair; target is B's general search.
- Difficulty / variation: pure judgment row, minimal code.

### Spec 10: edge-unsatisfiable-courier
- Files: `courier_routes.cpp`, `courier_routes.h` (test file: `courier_routes_test.cpp`)
- API: namespace `courier`; `std::vector<int> plan(int stops, const std::vector<std::pair<int,int>>& must_precede);` — topological-style ordering; return `{}` when constraints are cyclic/unsatisfiable, and must do so in well under a second.
- Prompt shape: courier stop-ordering story; one documented test case has contradictory constraints.
- Target capability: G3+G2 — detect unsatisfiability and return the contract's empty result fast, instead of searching forever.
- Target answer shape: search with visited-state cutoff or cycle detection; defined empty-vector return.
- Difficulty / variation: directly counters the never-terminating `isValid`-always-false failure.

### Spec 11: edge-all-different-quilt
- Files: `quilt_pattern.cpp`, `quilt_pattern.h` (test file: `quilt_pattern_test.cpp`)
- API: namespace `quilt`; `bool arrange(std::vector<std::string>& strips);` — arrange 5 fabric strips so each color and each pattern appears exactly once per row band.
- Prompt shape: quilting-bee story.
- Target capability: G2 — enforce bijection/all-different constraints *during* search (used-set pruning), the exact pruning missing from the failed solver.
- Target answer shape: per-attribute `std::array<bool,N> used` bookkeeping; unmark on backtrack.
- Difficulty / variation: two independent all-different dimensions.

### Spec 12: edge-adjacency-symmetry-parade
- Files: `parade_order.cpp`, `parade_order.h` (test file: `parade_order_test.cpp`)
- API: namespace `parade`; `std::vector<std::string> order_floats(const std::vector<std::string>& floats, const std::vector<std::pair<std::string,std::string>>& next_to);`
- Prompt shape: street-parade lineup story; "X marches next to Y" rules.
- Target capability: G3 — encode "next to" as a symmetric relation (check both `|i-j|==1` directions), unlike positional hardcoding.
- Target answer shape: helper `adjacent(i,j)` used uniformly; no fixed-index assertions.
- Difficulty / variation: symmetric adjacency; sibling Spec 23 covers directional adjacency.

### Spec 13: repair-declaration-order
- Files: `lighthouse_keeper.cpp`, `lighthouse_keeper.h` (test file: `lighthouse_keeper_test.cpp`)
- API: namespace `light`; `int flashes_per_night(int dusk_min, int dawn_min, int period_min);` via file-local helper `int count_intervals(int span, int period)` defined after the public function.
- Prompt shape: two-turn. Turn 1 (scripted wrong answer) calls the helper before defining it, no prototype → compiler error `error: 'count_intervals' was not declared in this scope`. Turn 2 shows that exact diagnostic.
- Target capability: G5+G6 — map `'<fn>' was not declared in this scope` to "add a forward declaration or reorder", emitting the whole corrected cpp.
- Target answer shape: whole cpp listing with prototype added; one-sentence explanation.
- Difficulty / variation: exact repair mapping the run performed (this time taught as the *first* response, not after a round-trip).

### Spec 14: repair-timeout-to-pruning
- Files: `maze_rat.cpp`, `maze_rat.h` (test file: `maze_rat_test.cpp`)
- API: namespace `maze`; `int shortest_path(const std::vector<std::string>& grid);`
- Prompt shape: two-turn. Turn 1 (scripted) is a brute-force all-paths enumeration with no visited set; turn 2 says "Tests timed out!" with no other diagnostic.
- Target capability: G2+G6 — read a bare timeout as an algorithmic-complexity bug; add memoization/visited-set pruning, not cosmetic changes.
- Target answer shape: whole cpp re-emitted with BFS or memoized DFS; brief rationale citing exponential blowup.
- Difficulty / variation: timeout-only feedback, the run's terminal failure mode.

### Spec 15: repair-field-semantics
- Files: `chess_club.cpp`, `chess_club.h` (test file: `chess_club_test.cpp`)
- API: namespace `club`; `struct MatchResult { std::string winnerName; std::string topScorerName; };` + `MatchResult summarize(const std::vector<std::pair<std::string,int>>& player_scores);`
- Prompt shape: two-turn. Turn 1 (scripted wrong answer) fills the fields with score strings / category labels instead of player names. Turn 2 shows failing output `REQUIRE(result.winnerName == "Ada")` got `"97"`-style value.
- Target capability: G4+G6 — map an assertion mismatch to the field-semantics bug (identity vs. attribute), fix the mapping, not the formatting.
- Target answer shape: whole cpp with index→name lookup; both files listed.
- Difficulty / variation: repairs the exact `to_string(attribute)` mistake with new domain.

### Spec 16: format-whole-under-pressure
- Files: `glacier_survey.cpp`, `glacier_survey.h` (test file: `glacier_survey_test.cpp`)
- API: namespace `glacier`; `std::vector<double> moving_average(const std::vector<double>& samples, int window);`
- Prompt shape: glacier sensor story with a ~70-line implementation to tempt elision and diff-style "small change" answers; prompt demands whole files.
- Target capability: G1 — no ` ```diff `, no `...` elision, no "rest unchanged", even for long files.
- Target answer shape: complete 70-line listing.
- Difficulty / variation: length pressure on format discipline.

### Spec 17: format-both-files-changed
- Files: `vineyard_blend.cpp`, `vineyard_blend.h` (test file: `vineyard_blend_test.cpp`)
- API: namespace `vineyard`; `struct Blend { std::string name; double ratio; };` + `std::vector<Blend> normalize(std::vector<Blend> blends);`
- Prompt shape: winemaking story; both starter files contain a deliberate defect so both genuinely need edits.
- Target capability: G1 — when two files change, emit two complete listings; never fix one file and go silent on the other.
- Target answer shape: two self-contained whole-file listings in one response.
- Difficulty / variation: multi-file completeness.

### Spec 18: api-discovery-add-declaration
- Files: `observatory_dome.cpp`, `observatory_dome.h` (test file: `observatory_dome_test.cpp`)
- API: namespace `dome`; starter header declares `struct Reading { double azimuth; double elevation; };` only; tests call `dome::Reading average(const std::vector<Reading>&);`.
- Prompt shape: observatory story; the prompt says "don't change names of existing functions or classes" and shows only the struct — model must infer and add the missing free-function declaration.
- Target capability: header completion discipline (the run's one correct move — adding `Solution solve();` — reinforced): add declarations without disturbing existing ones.
- Target answer shape: header with struct preserved verbatim plus the new declaration; cpp with definition.
- Difficulty / variation: positive-reinforcement sibling of Spec 03.

### Spec 19: exception-empty-input-observatory
- Files: `tide_table.cpp`, `tide_table.h` (test file: `tide_table_test.cpp`)
- API: namespace `tides`; `double highest_tide(const std::vector<double>& heights);` — throws `std::domain_error` on empty input.
- Prompt shape: tide-table story; prose names the exception type.
- Target capability: exception-policy precision (contract here is tiny but exact) — throw the named type from the named condition.
- Target answer shape: one guard + `throw std::domain_error("...")`; `<stdexcept>` in cpp.
- Difficulty / variation: keeps exception discipline in the mix although the zebra contract has none.

### Spec 20: complexity-estimation-recital
- Files: `recital_seats.cpp`, `recital_seats.h` (test file: `recital_seats_test.cpp`)
- API: namespace `recital`; `int count_valid_arrangements(int people, const std::vector<std::pair<int,int>>& apart);`
- Prompt shape: recital seating story; prose states the input size (≤ 8) and asks the model to choose a method that finishes "instantly".
- Target capability: G2 — pick search strategy from input-size arithmetic (8! = 40320 fine with pruning; 5^25 not); the target reasoning names the estimated leaf count before coding.
- Target answer shape: pruned backtracking counter; brief complexity note in prose, no comments dumping.
- Difficulty / variation: graded on the stated estimate matching the implementation's actual cost.

### Spec 21: constraint-ordering-tea-tasting
- Files: `tea_tasting.cpp`, `tea_tasting.h` (test file: `tea_tasting_test.cpp`)
- API: namespace `tea`; `std::vector<int> tasting_order(const std::vector<std::pair<int,int>>& before_after);`
- Prompt shape: tea-tasting sequence story with many pairwise constraints.
- Target capability: G2 — check the most-constraining relations first / fail fast; ordering of checks for early rejection.
- Target answer shape: constraint checks ordered cheapest-first inside the search loop.
- Difficulty / variation: same capability as Spec 08, different mechanic (check ordering vs. prefix pruning).

### Spec 22: derive-dont-memorize-ferry
- Files: `ferry_manifest.cpp`, `ferry_manifest.h` (test file: `ferry_manifest_test.cpp`)
- API: namespace `ferry`; `std::string missing_vehicle(const std::vector<std::string>& expected, const std::vector<std::string>& boarded);`
- Prompt shape: ferry-loading story; the narrative embeds a worked example whose answer is easy to memorize — tests use different inputs.
- Target capability: G3 — compute from inputs, never bake the example's answer into code; hidden-input generalization.
- Target answer shape: set-difference computation; no literal answer strings.
- Difficulty / variation: anti-memorization guard, complements Spec 09.

### Spec 23: edge-directional-right-of
- Files: `bookshelf_order.cpp`, `bookshelf_order.h` (test file: `bookshelf_order_test.cpp`)
- API: namespace `shelf`; `bool satisfies(const std::vector<std::string>& books, const std::vector<std::pair<std::string,std::string>>& immediately_right_of);`
- Prompt shape: bookshelf arrangement story; "A sits immediately to the right of B" rules.
- Target capability: G3 — directional adjacency (`pos(A) == pos(B) + 1` exactly), distinct from symmetric "next to".
- Target answer shape: position lookup + exact offset check; boundary-safe (no `i-1` at index 0).
- Difficulty / variation: sibling of Spec 12 isolating directionality and boundary safety.

### Spec 24: edge-boundary-adjacency-dock
- Files: `dock_mooring.cpp`, `dock_mooring.h` (test file: `dock_mooring_test.cpp`)
- API: namespace `docks`; `std::vector<int> moor(const std::vector<std::pair<int,int>>& neighbor_rules, int berths);`
- Prompt shape: marina mooring story; rules reference the first and last berths.
- Target capability: G2+G3 — adjacency checks at both ends of the line without out-of-range access (the reference's `i==0` / `i==4` special cases, generalized).
- Target answer shape: guarded neighbor indexing (`i > 0`, `i + 1 < n`) in the constraint checker.
- Difficulty / variation: boundary-condition drill.

### Spec 25: contrastive-enumerate-vs-prune
- Files: `garden_beds.cpp`, `garden_beds.h` (test file: `garden_beds_test.cpp`)
- API: namespace `garden`; `std::vector<int> plant_order(int beds, const std::vector<std::pair<int,int>>& not_adjacent);`
- Prompt shape: contrastive pair — candidate A enumerates all n! orders and tests each complete one; candidate B prunes partial orders. Row labels A wrong (too slow) / B right.
- Target capability: G2 — complexity-level contrast: same correctness, different asymptotics; B is the target.
- Target answer shape: annotated A/B pair; target is B.
- Difficulty / variation: isolates the pruning decision from all other skills.

### Spec 26: self-check-before-emit-summit
- Files: `summit_log.cpp`, `summit_log.h` (test file: `summit_log_test.cpp`)
- API: namespace `summit`; `struct Result { std::string firstClimber; std::string lastClimber; };` + `Result analyze(const std::vector<std::pair<std::string,int>>& finishes);`
- Prompt shape: mountain-race story; instructions end with "before answering, restate what each struct field must contain".
- Target capability: G4+G6 — self-verification habit: target answer includes a two-line field-semantics restatement that matches the code actually emitted (counters the false self-trace pattern).
- Target answer shape: brief restatement + whole files whose code agrees with it.
- Difficulty / variation: graded on trace/code agreement.

### Spec 27: repair-vague-marker-commit
- Files: `hot_springs.cpp`, `hot_springs.h` (test file: `hot_springs_test.cpp`)
- API: namespace `springs`; `int warmest_pool(const std::vector<int>& temps);` throws `std::domain_error` on empty.
- Prompt shape: two-turn. Turn 1 answer has a real but unmarked bug (off-by-one skipping element 0). Turn 2 is `# Fix any errors below, if possible.` with an unrelated-looking line █-marked and no compiler text.
- Target capability: G6 — on vague marked-line prompts, audit the whole file and commit to a substantive whole-file fix; never emit an empty diff or "looks correct".
- Target answer shape: whole cpp with the loop-bound fix; one-sentence rationale.
- Difficulty / variation: teaches whole-file re-audit instead of marker fixation.

### Spec 28: namespace-helper-hygiene
- Files: `meteor_watch.cpp`, `meteor_watch.h` (test file: `meteor_watch_test.cpp`)
- API: namespace `meteor`; `int visible_showers(const std::vector<double>& magnitudes, double limit);` with file-local helpers in an anonymous namespace inside the cpp; header exposes only the public function.
- Prompt shape: meteor-observing story.
- Target capability: header/impl hygiene — helpers not in the header, no `using namespace std;` at header scope, header compiles standalone.
- Target answer shape: minimal guarded header; anonymous-namespace helpers in cpp.
- Difficulty / variation: include/namespace placement discipline.

Gap coverage: G1 → Specs 01, 02, 16, 17. G2 → Specs 07, 08, 10, 11, 14, 20, 21, 24, 25. G3 → Specs 09, 10, 12, 22, 23, 24. G4 → Specs 06, 15, 26. G5 → Specs 05, 13. G6 → Specs 13, 14, 15, 26, 27. Required mix: format-contract ≥2 (01, 02, 16, 17); header/impl separation ≥2 (03, 04, 18, 28); exception policy — contract has none, 2 included anyway (19, 27); edge cases ≥3 (10, 11, 12, 23, 24); repair/retry ≥2 (13, 14, 15, 27); contrastive ≥1 (09, 25). No two specs share a story wrapper.

## 6. Acceptance & Validation Gates

For every row built from the specs above, before inclusion in SFT:

1. **Parser validity:** the target response must parse under the Aider whole-file listing format — bare filename line, opening fence, entire file, closing fence; zero diff hunks, zero elisions (grep for `^```diff`, `+ `/`- ` hunk lines, `...` placeholders, `rest of`, `unchanged`).
2. **Compile + test receipt:** apply the target files to a scratch copy of the spec's exercise, build with the project's CMake/Catch2 harness, and require 100% test pass; store the build log hash as the receipt.
3. **Termination budget:** every solver spec (07, 08, 10, 11, 14, 20, 21, 24, 25) must ship a test that completes under a hard wall-clock budget (e.g. 5 s) with a deliberately adversarial case (unsatisfiable or worst-case input), so rows teach termination, not just correctness. Record runtime in the receipt.
4. **No-hardcode scan:** target answers for solver specs must not contain the expected output as a string/integer literal; grep targets against the spec's expected answers.
5. **Field-semantics check:** for struct-returning specs (03, 04, 06, 15, 18, 26), tests must assert that fields carry identity strings (names), never attribute/category strings — and include one decoy where the attribute value would also be a plausible string.
6. **Hidden-edge coverage:** each spec's test file must include the edge cases named in its API bullet (unsatisfiable input, boundary adjacency, directional vs. symmetric rules, empty input) plus at least one case not shown in the prose examples.
7. **Repair-turn realism:** for two-turn specs (13, 14, 15, 27), the scripted first answer must be a plausible, compilable-except-as-designed wrong answer, and the second-turn prompt must mirror the real harness style (`# Fix any errors below, if possible.` + █-marked snippet, or a bare `Tests timed out!`).
8. **Contamination check:** diff every spec's story, clue text, test inputs, and expected outputs against `polyglot-benchmark/cpp/exercises/practice/zebra-puzzle/`; no shared string literals (no `"Norwegian"`/`"Japanese"` answer pairs, no 15-clue structures, no five-houses framing), no copied reference code. APIs must differ in names even when capabilities overlap.
9. **Whole-file rule on targets:** target answers for repair turns must re-emit **all** editable files in full, not only the file named in the error snippet.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the shard-1 benchmark log, and the ground-truth files:

- **Outcome array / shard:** re-read failure log lines 89397–89402: shard `1`, outcomes `[False, False]`, result `FAIL` — matches section 1. The terminal JSON was re-verified at failure log 115209–115212 (`"tests_outcomes": [false, false]`), 115215 (`"test_timeouts": 1`), 115221 (`"num_user_asks": 1`), 115222 (`"num_exhausted_context_windows": 0`), 115202 (`Tests timed out!`, quoting source line 40809).
- **Log citations re-read:** every quoted line was re-fetched with `sed`/grep and confirmed: failure log 90735–90741 (source 15970–15976, return-semantics trace), 90886–90887 (source 16493–16494, compile error), 103463 (source 29070, "Forward declaration!"), 104373–104375 (source 29980–29982, forward-declaration diff), 104512 / 104529–104530 (source 30119, 30136–30137, final code echo), 115202–115222 (terminal result). Raw-shard citations confirmed: 11063–11064 (wrong manual conclusion), 11069–11090 (turn-1 diff answer), 11163 / 11216 (contradictory hardcoded `houses[3]` checks), 11507–11508 (applied edits), 16000–16004 (turn-2 diff fence), 16288 (applied), 16292–16464 (file echo with hardcoded `isValid`, wrong return, no pruning), 29966–29988 (turn-3 diff answer, applied at 29988), 30175 (test run start), 40809–40849 (timeout + JSON).
- **Line-numbering discrepancy found and documented:** the failure log's embedded source-line numbers run +2 relative to the raw shard log around the compile error (failure log 90886 quotes source line `16493:` whose text is raw shard log line 16491); section 3 cites both numbers where they differ. No other citation discrepancies.
- **API claims re-checked:** `.meta/example.h:6,8-11,13` (namespace, `struct Solution`, `Solution solve();`) and `zebra_puzzle_test.cpp:9,11,17` (calling convention, `"Norwegian"`, `"Japanese"`) re-read and match section 2. Confirmed the starter header at the exercise root declares only `struct Solution` (no `solve()`), as stated in sections 1–2. Confirmed the contract has no exception policy; the spec-set mix note in section 5 reflects this. Reference solver structure (`.meta/example.cpp:181-241` permutations with early `continue`; `:248-261` nationality-string extraction; `:19-23` string table) re-read and matches.
- **Corrections made during cross-check:** (1) added the source-line offset note for the compile-error citation (the offset varies by chunk: +2 at the compile error, +5 at the turn-3 diff, because progress-bar lines are counted differently); (2) initially drafted turn 2 as a whole-file answer — corrected after re-reading raw shard 16000–16004 showing it was also a ```` ```diff ```` fence, so section 3 and G1 now state all three answers used diff fences; (3) clarified that the two recorded outcomes are one compile-error test run and one timeout test run within a single 3-turn session (chat_hashes has 3 pairs), not two independent sessions; (4) fixed the forward-declaration quote block — the added lines are failure log 104373–104375 (its printed source lines 29980–29982; raw shard 29975–29977), not 29977–29988; (5) fixed the "24 billion" hint citation to failure log 89438 (the single-line user-instructions JSON string), the big-excerpt start to 90859, and the turn-3 raw-shard diff span to 29966–29988; (6) fixed the turn-1 answer span to raw shard 11069–11090 (header hunk 11069–11083 incl. `+Solution solve();` at 11078, cpp ```` ```diff ```` fence at 11089–11090) after re-reading those exact lines.
- **Ground-truth status:** `.meta/example.h`, `.meta/example.cpp`, and `zebra_puzzle_test.cpp` all present and mutually consistent; no ground-truth problem encountered.
