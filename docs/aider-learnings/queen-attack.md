# queen-attack — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `queen-attack`
- Shard: `1` (failure log section header, line 65818: "- Shard: `1`")
- Test outcomes: `[False, False]` (failure log line 65820; terminal JSON `tests_outcomes: [false, false]`, failure-log source lines 66381-66384 / raw shard log lines 66369-66372)
- Result: `FAIL` (failure log line 65821)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **65817-66798**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-1/benchmark.log` (queen-attack run: lines 19912-66396)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/queen-attack/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/queen-attack/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/queen-attack/queen_attack_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` only covers b001-b007, no queen-attack).

### Evidence-handling notes (important for reading the log)

1. **Chunk-1 bleed-over.** The failure log's "Attempt/log chunk 1, source lines 19696-19928" (failure log lines 65867-66104) is dominated by the tail of the *yacht* task (source lines 19696-19915: yacht thinking, yacht test failures, yacht result JSON). The queen-attack run only begins at source line 19916 (`main_model.max_chat_history_tokens` / `fnames: ...queen-attack/queen_attack.cpp,...`). This is a slice-boundary artifact, not model confusion.
2. **Interleaved shard log.** The shard-1 `benchmark.log` interleaves concurrently running tasks. Between queen-attack lines there are blocks of `spiral-matrix`, `knapsack`, `sublist`, `linked-list`, etc. content (e.g. shard lines 20222-21107 are spiral-matrix, *not* a queen-attack hallucination — spiral-matrix's own run was in flight; its result JSON is at shard line 25117). Queen-attack-specific lines were traced by grepping for `queen`/`Chessboard`/`chess_board`.
3. **Line-number offset.** The failure log's "Terminal Test Log" block cites "Source lines 66345-66434" and prefixes lines 66345-66434; in the raw shard log the same content sits ~12 lines earlier (e.g. failure-log prefix 66363 `error: 'abs' is not a member of 'std'` = raw shard line 66351). Quotes below cite whichever source they were taken from, labeled explicitly.

## 2. Benchmark Contract (Ground Truth)

File set: `queen_attack.h` + `queen_attack.cpp`, namespace `queen_attack`.

Public API (`.meta/example.h`):

- `class chess_board` — snake_case name (example.h:10). The test constructs `queen_attack::chess_board board{white, black}` (queen_attack_test.cpp:14).
- `chess_board(const std::pair<int, int>& white, const std::pair<int, int>& black);` (example.h:13) — const-ref pair parameters.
- `std::pair<int, int> white() const` / `std::pair<int, int> black() const` accessors (example.h:18-25), enforced by `REQUIRE(white == board.white()); REQUIRE(black == board.black());` (queen_attack_test.cpp:16-17).
- `operator std::string() const;` (example.h:27; implemented example.cpp:24-44, 8x8 `W`/`B`/`_` rendering). Not exercised by the visible test file, but part of the reference surface.
- `bool can_attack() const;` (example.h:29), enforced by queen_attack_test.cpp:64, 71, 78, 85, 92, 99, 106, 113.

Exception policy (`.meta/example.cpp:13-21`): the constructor throws `std::domain_error` when
- both queens occupy the same position (`"Both queens cannot occupy the same position."`, example.cpp:13-15) — enforced by queen_attack_test.cpp:57;
- any coordinate is `< 0` or `> 7` (`"Both queens must be placed on the board."`, example.cpp:16-21) — enforced by queen_attack_test.cpp:26, 34, 42, 50 (`REQUIRE_THROWS_AS(..., std::domain_error)`).

Position semantics: `std::pair<int,int>` is `{row, column}` (example.cpp:48-51 compares `.first` for rows, `.second` for columns). Attack rule (example.cpp:46-52): same row, same column, or either diagonal — the reference avoids `std::abs` entirely by comparing signed differences `(white_.first - black_.first) == (white_.second - black_.second)` and `== (black_.second - white_.second)`.

Edge cases enforced: both diagonals in all four directions (queen_attack_test.cpp:81-107), the reflected-diagonal non-attack case `{4,1}` vs `{2,5}` must be false (queen_attack_test.cpp:109-114).

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: invented API + wrong output format)

**What the model emitted.** After a long thinking block (raw shard lines 19925-20127) in which it explicitly debated class naming — "I'll create a class `Chessboard` or `QueenAttack`... `Chessboard` is standard for this specific Exercism track problem. I will use `Chessboard`" (shard 19948-20103) — the answer (shard 20128-20190) delivered:

- **Diff-hunk file listings, not whole files**, despite `edit_format: whole` (shard 19918) and a system prompt demanding entire-file listings: shard 20130-20145 shows `queen_attack.h` followed by ```` ```diff ```` and `@@ -1,8 +1,20 @@` hunks; shard 20159-20190 the same for `queen_attack.cpp`. One hunk is even malformed: `-#endif // QUEEN_ATTACK_H+private:` (shard 20152).
- **An invented API**: `class Chessboard` (PascalCase) with constructor `Chessboard(std::pair<int, int> white, std::pair<int, int> black)`, `bool can_attack() const`, and private members `_white`/`_black` (shard 20142-20152). No `white()`/`black()` accessors, no `std::domain_error` validation, no `operator std::string`.
- **Missing include**: the `.cpp` uses `std::abs(...)` (shard 20186-20188) but neither file includes `<cstdlib>` or `<cmath>` (header includes only `<utility>`, shard 20137).

**Reflection thrash.** Aider then sent lint-style retry prompts `# Fix any errors below, if possible.` with █-marked lines in `queen_attack.h` only (shard 20196-20215). The model's thinking (failure-log chunk 2, source lines 35984-36575) shows it hunting for a non-existent header error — "Is there a missing `;`? No. Is there a missing `const`? No." (source 36435-36436) — and emitting an **empty diff block** as its answer (source 36540-36544: `queen_attack.h` / ```` ```diff ```` / ```` ``` ````). This empty-listing pattern recurred at raw shard 46261-46277 and 65190-65200.

**Test result.** The first build failed to compile (raw shard 39706+):
- shard 39708: `error: 'chess_board' in namespace 'queen_attack' does not name a type; did you mean 'Chessboard'?` — the test demands `chess_board`, the model shipped `Chessboard`.
- shard 39713: `error: 'board' was not declared in this scope` at `REQUIRE(white == board.white())` — missing accessors.

### Attempt 2 (retry with compiler output) — outcome False (compile failure: `std::abs`)

**What the retry got right.** Shown the test compile errors, the model correctly diagnosed the naming mismatch — "To resolve the compilation errors, I must rename the class to `chess_board` and add the requested public methods." (raw shard 41991-41997) — and produced a (still diff-format) answer renaming `Chessboard` → `chess_board` and adding `white()`/`black()` accessors (shard 42001-42061).

**What the retry still missed.**

1. **No exception policy.** The attempt-1 compiler output had quoted the test's throw expectations verbatim (e.g. shard 39721: `REQUIRE_THROWS_AS((queen_attack::chess_board{white, black}), std::domain_error)`). The model even noticed in later thinking: "The test file (from Turn 8) expects `std::domain_error` if queens are on the same square. The current code does *not* check for this." (shard 46023-46025) and "There is no check for `white == black`." (shard 46035). It never implemented the validation — the final constructor body is empty except the initializer list (final response, shard 66280-66320 region).
2. **No `<cstdlib>`/`<cmath>` for `std::abs`.** The model considered exactly this failure twice and talked itself out of it:
   - source 36233-36236: "What if the error is that `std::abs` is not included? `#include <cmath>` is needed for `std::abs` with integers in older compilers, or `<cstdlib>`? Actually, `std::abs(int)` is usually in `<cstdlib>`, but `<cmath>` usually brings it in via overloads." — then dropped the thread because "in the *header*, only declarations are present."
   - source 36482-36487: "`std::abs` is used. If the compiler is very strict... `std::abs(int)` might not be found if `cmath` is not included... Actually, `std::abs(int)` is in `<cstdlib>`. `<cmath>` usually pulls it in."
3. **Hallucinated style "fixes" under vague █ prompts.** With retry prompts marking only header lines and giving no error text, the model guessed: "Let's assume the most robust 'fix'... 1. Constructor parameters: `const std::pair<int, int>&`. 2. Member variables: `const`." (raw shard 66016-66019), answering with const-ref/const-member diffs (shard 66187-66257) while the real defect sat untouched in the `.cpp`.

**Terminal result.** Final response (raw shard 66270-66320: whole-file `queen_attack.h` + `queen_attack.cpp`) still calls `std::abs` with no include. Build output (failure-log source lines 66362-66368; raw shard 66350-66356):

```
queen_attack.cpp: In member function 'bool queen_attack::chess_board::can_attack() const':
queen_attack.cpp:21:17: error: 'abs' is not a member of 'std'
   21 |     return std::abs(_white.first - _black.first) == std::abs(_white.second - _black.second);
queen_attack.cpp:21:58: error: 'abs' is not a member of 'std'
```

`Tests failed: .../queen-attack` (failure-log source line 66373). Latent additional failure even if it had compiled: the five `REQUIRE_THROWS_AS(..., std::domain_error)` cases (queen_attack_test.cpp:26, 34, 42, 50, 57) would have failed at runtime because the constructor validates nothing.

### Hard evidence vs inference

- Hard evidence: diff-format answer (shard 20132-20133), invented `Chessboard` API (shard 20142), missing accessors (shard 39713), missing include (shard 66351-66356), empty diff blocks (source 36542-36544), no validation in final code (shard 66280-66320).
- Inference: root cause is a combination of (a) weak whole-file format discipline, (b) no prior on the canonical Exercism C++ API shape for this exercise family, (c) shaky `std::abs` include hygiene compounded by a reasoning habit of raising the correct hypothesis and discarding it without verification, and (d) repair behavior that invents plausible style fixes when the retry prompt carries no concrete error signal.

## 4. Knowledge / Capability Gaps

- **G1 — Whole-file format contract.** Model emitted ```` ```diff ```` hunks and empty ```` ```diff ```` blocks under `edit_format: whole` (shard 20132, source 36542-36544, shard 46261-46277). Every "Applied edit" after an empty block was a no-op that burned one of 3 reflections.
- **G2 — Canonical Exercism C++ API conventions.** Snake-case class name (`chess_board`), accessor pair `white()`/`black()`, `{row, column}` pair semantics. Model confidently invented `Chessboard` (shard 19948-20103, 20142) and paid a full failed attempt for it (shard 39708).
- **G3 — `std::abs` include hygiene.** `std::abs(int)` requires `<cstdlib>` (or `<cmath>` overloads); `<utility>` does not provide it. Model raised this hypothesis twice (source 36233-36236, 36482-36487) and discarded it both times; terminal compile error proves the gap (shard 66351).
- **G4 — Repair behavior under signal-free retry prompts.** When the retry prompt marks lines with █ but shows no error text, the model hallucinated style errors (const-ref params, const members — shard 66009-66013) instead of (a) stating no error is visible in the marked lines, and (b) widening the search to the other editable file (the `.cpp`, where the actual error lived). Thinking loops of 500+ lines (source 35984-36537) with repeated "Wait, the prompt says..." cycles show no convergence strategy.
- **G5 — Exception policy / input validation.** The contract requires `std::domain_error` for same-square and off-board positions. The model saw the `REQUIRE_THROWS_AS` lines in attempt-1 output (shard 39721-39752), explicitly acknowledged the missing check (shard 46023-46042), and still shipped a validating-nothing constructor (shard 66280-66320).

## 5. SFT Task Specifications (28 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-weather-logger
- Files: weather_logger.cpp, weather_logger.h (test file: weather_logger_test.cpp)
- API: namespace `weather`; `class reading_log { public: void add(double celsius); double average() const; int count() const; };`
- Prompt shape: a backyard weather-station story; starter files contain only include guard + empty namespace; edit_format instruction demands whole-file listings.
- Target capability: G1 — always emit complete file contents, never diff hunks or elisions.
- Target answer shape: two whole-file listings; header with declarations only, cpp with definitions; full guard boilerplate repeated verbatim.
- Difficulty / variation: small surface; the trap is a mid-answer temptation to show a patch — training target must not.

### Spec 02: no-empty-listing-library-catalog
- Files: catalog.cpp, catalog.h (test file: catalog_test.cpp)
- API: namespace `library`; `class catalog { public: bool add_book(const std::string& isbn); bool contains(const std::string& isbn) const; };`
- Prompt shape: branch-library catalog; multi-turn — turn 2 says "Fix any errors below" with marked lines that contain no defect.
- Target capability: G1/G4 — never answer with an empty code block; if nothing needs changing, re-emit the whole unchanged file or state no change is needed.
- Target answer shape: either whole unchanged files or a one-sentence "no errors found" plus whole files; never an empty fence.
- Difficulty / variation: teaches the no-op-reply policy directly, unlike Spec 01's fresh implementation.

### Spec 03: whole-file-on-retry-inventory
- Files: inventory.cpp, inventory.h (test file: inventory_test.cpp)
- API: namespace `stockroom`; `class inventory { public: void restock(const std::string& sku, int qty); int level(const std::string& sku) const; };`
- Prompt shape: warehouse inventory; attempt 1 shown as a model answer in diff-hunk format (treated as malformed), turn 2 repeats the whole-file requirement.
- Target capability: G1 — format recovery: second turn must switch to whole-file listings, not another diff.
- Target answer shape: whole files on turn 2 with identical semantics to the diff attempt.
- Difficulty / variation: explicitly conditions on a prior malformed answer.

### Spec 04: header-impl-split-vault
- Files: vault.cpp, vault.h (test file: vault_test.cpp)
- API: namespace `bank`; `class vault { public: explicit vault(int capacity); bool deposit(int bars); int balance() const; private: int capacity_; int held_; };`
- Prompt shape: bank vault gold-bar tracking; starter has everything inline in the header (wrong) — the request asks to split declarations/definitions conventionally.
- Target capability: header/impl separation — declarations + member data in `.h`, out-of-line definitions in `.cpp` with `vault::` qualification.
- Target answer shape: header keeps guard, class body, private members; cpp includes only its own header plus what it uses.
- Difficulty / variation: refactoring direction (inline → split) rather than greenfield.

### Spec 05: include-what-you-use-sensor-grid
- Files: sensor_grid.cpp, sensor_grid.h (test file: sensor_grid_test.cpp)
- API: namespace `sensors`; `class grid { public: grid(int rows, int cols); double reading(int r, int c) const; void set(int r, int c, double v); private: std::vector<std::vector<double>> cells_; };`
- Prompt shape: environmental sensor mesh; starter header forgets `<vector>` (relies on transitive include).
- Target capability: header self-sufficiency — every header must compile standalone; include what you use in the file that uses it.
- Target answer shape: header gains `<vector>`; cpp adds nothing redundant.
- Difficulty / variation: defect is a missing include in the *header*, complementing Spec 11/12 (missing include in cpp).

### Spec 06: domain-error-battleship-grid
- Files: fleet_board.cpp, fleet_board.h (test file: fleet_board_test.cpp)
- API: namespace `fleet`; `class board { public: board(std::pair<int,int> ship_a, std::pair<int,int> ship_b); bool in_range() const; };` constructor throws `std::domain_error` if either coordinate is outside `[0,9]` or both ships share a cell.
- Prompt shape: naval strategy board game with two patrol ships; tests (hidden from prompt) require `std::domain_error`.
- Target capability: G5 — constructor-time validation with `std::domain_error` for out-of-range and co-located pieces.
- Target answer shape: cpp includes `<stdexcept>`; validation before any other logic; distinct messages per failure kind.
- Difficulty / variation: two failure kinds (range + collision) in one constructor.

### Spec 07: domain-error-parking-garage
- Files: garage.cpp, garage.h (test file: garage_test.cpp)
- API: namespace `parking`; `class garage { public: garage(int floors, int spots_per_floor); std::pair<int,int> park(int floor, int spot); };` `park` throws `std::domain_error` on negative or ≥-capacity floor/spot.
- Prompt shape: multi-storey parking allocation terminal.
- Target capability: G5 — validate both components of a coordinate pair against asymmetric bounds.
- Target answer shape: bounds derived from constructor state, not hard-coded literals.
- Difficulty / variation: bounds are runtime state (vs Spec 06's fixed board), forcing member-driven checks.

### Spec 08: exception-choice-contrastive-robot-arm
- Files: robot_arm.cpp, robot_arm.h (test file: robot_arm_test.cpp)
- API: namespace `robotics`; `class arm { public: void move_to(double angle_deg); };` throws `std::domain_error` when angle is outside the arm's physical `[0,180]` arc; throws `std::invalid_argument` when angle is NaN.
- Prompt shape: pick-and-place robot arm controller.
- Target capability: G5 — choose the right standard exception (`domain_error` for value-outside-valid-domain, `invalid_argument` for malformed input) and be consistent.
- Target answer shape: two distinct throw sites with `<stdexcept>` included; no custom exception classes.
- Difficulty / variation: contrastive — spec text explains the wrong single-exception approach vs the correct split.

### Spec 09: snake-case-accessors-checkers
- Files: draughts.cpp, draughts.h (test file: draughts_test.cpp)
- API: namespace `draughts`; `class game_board { public: game_board(const std::pair<int,int>& red, const std::pair<int,int>& black); std::pair<int,int> red() const; std::pair<int,int> black() const; bool can_capture() const; };`
- Prompt shape: English draughts/checkers position evaluator; prompt notes tests reference "existing names" without listing them, and the starter namespace is the only hint.
- Target capability: G2 — snake_case class naming and const accessor pairs returning `std::pair<int,int>` by value.
- Target answer shape: accessors defined inline or in cpp; member init via ctor initializer list.
- Difficulty / variation: direct analog of the failed naming/accessor pattern, new domain.

### Spec 10: const-accessor-gps-tracker
- Files: tracker.cpp, tracker.h (test file: tracker_test.cpp)
- API: namespace `gps`; `class tracker { public: tracker(const std::pair<double,double>& start); std::pair<double,double> position() const; void move(double dlat, double dlng); };`
- Prompt shape: hiking GPS breadcrumb device.
- Target capability: G2 — const-correctness discipline: accessors `const`, mutators non-const; pass pairs by const ref.
- Target answer shape: signature qualifiers exactly as specified; tests mutate then read, so qualifier errors fail compile.
- Difficulty / variation: double-typed pairs (vs int) to prevent memorized copying.

### Spec 11: cstdlib-abs-manhattan-cabs
- Files: dispatch.cpp, dispatch.h (test file: dispatch_test.cpp)
- API: namespace `cabs`; `int manhattan(std::pair<int,int> a, std::pair<int,int> b);` (sum of absolute coordinate differences).
- Prompt shape: taxi dispatch distance estimator on a city grid.
- Target capability: G3 — using `std::abs` on `int` requires `#include <cstdlib>` in the implementing `.cpp`.
- Target answer shape: cpp includes `<cstdlib>` explicitly; no reliance on transitive includes.
- Difficulty / variation: free function (not class) to vary surface.

### Spec 12: abs-diagonal-laser-turret
- Files: turret.cpp, turret.h (test file: turret_test.cpp)
- API: namespace `defense`; `class turret { public: turret(std::pair<int,int> self); bool aligned_diagonal(std::pair<int,int> target) const; };` — true iff `|dx| == |dy|`.
- Prompt shape: grid-based laser turret that can only fire along diagonals.
- Target capability: G3 + edge reasoning — diagonal alignment via absolute differences, with correct include.
- Target answer shape: `std::abs` with `<cstdlib>`, or a sign-comparison formulation that avoids `abs` entirely (both acceptable; spec teaches knowing both).
- Difficulty / variation: allows the no-abs alternative, teaching the model there are two valid idioms.

### Spec 13: same-cell-rejection-drones
- Files: airspace.cpp, airspace.h (test file: airspace_test.cpp)
- API: namespace `drones`; `class airspace { public: airspace(std::pair<int,int> alpha, std::pair<int,int> bravo); bool collision_course() const; };` constructor throws `std::domain_error` if `alpha == bravo`.
- Prompt shape: two delivery drones sharing an airspace grid.
- Target capability: G5/G2 — equality comparison of `std::pair` and the co-location throw, an edge case the model skipped.
- Target answer shape: `if (alpha == bravo) throw std::domain_error(...)` before any other check.
- Difficulty / variation: isolates the single easiest-to-forget validation.

### Spec 14: boundary-cells-laser-maze
- Files: maze.cpp, maze.h (test file: maze_test.cpp)
- API: namespace `laser_maze`; `class board { public: static constexpr int size = 10; bool on_board(std::pair<int,int> cell) const; };` — cells `0` and `size-1` are valid; `-1` and `size` are not.
- Prompt shape: laser-maze puzzle validator.
- Target capability: edge-case boundaries — off-by-one at both ends of a coordinate range.
- Target answer shape: inclusive bounds check `>= 0 && < size`; tests probe exactly `0`, `size-1`, `size`, `-1`.
- Difficulty / variation: `static constexpr` member adds a header/impl nuance.

### Spec 15: four-diagonals-archery
- Files: range.cpp, range.h (test file: range_test.cpp)
- API: namespace `archery`; `bool same_lane(std::pair<int,int> a, std::pair<int,int> b);` — true iff targets sit on a shared 45° lane in any of the four diagonal directions.
- Prompt shape: archery range lane assignment.
- Target capability: edge cases — all four sign combinations of (Δrow, Δcol); the reflected-non-diagonal case must be false.
- Target answer shape: `std::abs(dr) == std::abs(dc)` (with `<cstdlib>`) or signed-difference equality for both diagonal families.
- Difficulty / variation: includes the tricky false-positive case (differences equal only after reflection).

### Spec 16: negative-coords-warehouse-robot
- Files: floorbot.cpp, floorbot.h (test file: floorbot_test.cpp)
- API: namespace `warehouse`; `class floorbot { public: floorbot(std::pair<int,int> dock); void place(std::pair<int,int> cell); };` both throw `std::domain_error` on any negative coordinate.
- Prompt shape: warehouse floor robot that must never accept negative shelf coordinates.
- Target capability: G5 — negative-side validation only (upper bound delegated elsewhere), catching asymmetric-check bugs.
- Target answer shape: per-component `< 0` checks in both entry points.
- Difficulty / variation: validation split across two functions.

### Spec 17: repair-abs-not-member-bishop-dock
- Files: dock.cpp, dock.h (test file: dock_test.cpp)
- API: namespace `harbor`; `class dock { public: bool diagonal_clearance(std::pair<int,int> a, std::pair<int,int> b) const; };`
- Prompt shape: repair/retry — attempt 1 (provided in prompt history) computes `std::abs` differences but includes only `<utility>`; turn 2 supplies the compiler error `error: 'abs' is not a member of 'std'` and asks for a fix.
- Target capability: G3/G4 — map this exact compiler diagnostic to a missing `<cstdlib>` include; minimal one-line fix, whole file re-emitted.
- Target answer shape: whole cpp with `#include <cstdlib>` added; no unrelated edits.
- Difficulty / variation: the minimal-diff repair discipline (don't touch anything else).

### Spec 18: repair-rename-to-test-card-game
- Files: table.cpp, table.h (test file: table_test.cpp)
- API: namespace `cards`; the test expects `class card_table`; attempt 1 (in prompt history) shipped `class CardTable`; turn 2 shows `error: 'card_table' in namespace 'cards' does not name a type; did you mean 'CardTable'?`.
- Prompt shape: repair/retry — rename the class to the snake_case name the test references, update all definitions consistently.
- Target capability: G2/G4 — trust the compiler's "did you mean" as ground truth for the expected API name; rename in header AND cpp.
- Target answer shape: whole files with class renamed everywhere (declaration, ctor/dtor, out-of-line definitions).
- Difficulty / variation: pure rename repair; no logic changes allowed.

### Spec 19: vague-marker-no-error-thermostat
- Files: thermostat.cpp, thermostat.h (test file: thermostat_test.cpp)
- API: namespace `home`; `class thermostat { public: void set_target(int celsius); int target() const; };`
- Prompt shape: repair turn where marked lines (█) are actually correct and no compiler output is given.
- Target capability: G4 — recognize a signal-free prompt; respond that no error is visible and re-emit whole files unchanged rather than inventing "fixes" (no const-ref churn, no gratuitous `const`).
- Target answer shape: unchanged whole files + one sentence explaining nothing was broken.
- Difficulty / variation: directly counter-trains the queen-attack const-ref/const-member hallucination.

### Spec 20: marker-in-header-error-in-cpp-traffic-light
- Files: signal.cpp, signal.h (test file: signal_test.cpp)
- API: namespace `traffic`; `class signal { public: std::string next(std::string current) const; };`
- Prompt shape: retry prompt marks header lines with █, but the true defect (e.g. missing `<stdexcept>` or a wrong return) is in the cpp; prompt history includes both files.
- Target capability: G4 — widen diagnosis beyond the marked file: inspect the other editable file before concluding anything.
- Target answer shape: whole cpp with the real fix; header re-emitted unchanged (or not listed).
- Difficulty / variation: marker placement as a red herring.

### Spec 21: contrastive-naming-darts
- Files: scoreboard.cpp, scoreboard.h (test file: scoreboard_test.cpp)
- API: namespace `darts`; expected `class score_board` with `int total() const; void add_throw(int pts);`.
- Prompt shape: contrastive spec — prompt history shows a wrong PascalCase `ScoreBoard` answer that failed to compile against the test, then asks for the corrected version.
- Target capability: G2 — Exercism-family C++ naming prior: snake_case types matching the exercise stem, not invented PascalCase.
- Target answer shape: corrected whole files; commentary one line noting the rename.
- Difficulty / variation: negative-example-first ordering (wrong answer shown, then fixed).

### Spec 22: whole-file-repair-playlist
- Files: playlist.cpp, playlist.h (test file: playlist_test.cpp)
- API: namespace `music`; `class playlist { public: void add(const std::string& title); bool remove(const std::string& title); size_t size() const; };`
- Prompt shape: two-turn repair — turn 1 model answer is a diff hunk with a genuine logic bug (off-by-one in remove); turn 2 shows the failing assertion.
- Target capability: G1 + repair — fix the logic AND upgrade to whole-file format simultaneously.
- Target answer shape: whole files, fixed loop bounds, no diff fences.
- Difficulty / variation: combines format recovery with a real bug fix.

### Spec 23: throw-before-store-ticket-gate
- Files: gate.cpp, gate.h (test file: gate_test.cpp)
- API: namespace `transit`; `class gate { public: void admit(int zone); int admitted() const; private: int admitted_; };` `admit` throws `std::domain_error` for zones outside `[1,3]` and must not increment state on throw.
- Prompt shape: subway fare gate with zone validation.
- Target capability: G5 — exception safety ordering: validate first, mutate after; thrown calls leave object state untouched.
- Target answer shape: check precedes mutation; tests call `admit` with bad zone then verify count unchanged.
- Difficulty / variation: state-semantics angle on validation.

### Spec 24: header-guards-config-loader
- Files: config_loader.cpp, config_loader.h (test file: config_loader_test.cpp)
- API: namespace `appconfig`; `std::string lookup(const std::string& key);`
- Prompt shape: app configuration loader; starter header has no include guard at all.
- Target capability: header hygiene — `#if !defined(X_H)` / `#define` / `#endif // X_H` guard discipline matching the starter's existing style.
- Target answer shape: guard macro derived from filename; closing `#endif` comment preserved.
- Difficulty / variation: foundational; style-matching to existing boilerplate.

### Spec 25: namespace-discipline-aquarium
- Files: tank.cpp, tank.h (test file: tank_test.cpp)
- API: namespace `aquarium`; `class tank { public: void add_fish(int n); int fish() const; };`
- Prompt shape: aquarium stocking tracker; a decoy temptation to `using namespace std;` at header scope is mentioned as forbidden in instructions.
- Target capability: namespace discipline — all symbols inside `namespace aquarium`, no header-level `using`, closing-brace comment `} // namespace aquarium`.
- Target answer shape: fully qualified `std::string`/`std::size_t` in header; no `using` directives.
- Difficulty / variation: foundational; pairs with Spec 24 as hygiene basics.

### Spec 26: string-conversion-maze-renderer
- Files: maze_view.cpp, maze_view.h (test file: maze_view_test.cpp)
- API: namespace `maze`; `class view { public: view(int rows, int cols); void mark(int r, int c, char ch); operator std::string() const; };` — rows joined by `\n`, trailing newline per row.
- Prompt shape: ASCII maze renderer with a string-conversion operator.
- Target capability: G2 — hidden API surface: implicit conversion operators declared in the header and defined out-of-line; exact output formatting (separators, trailing newline).
- Target answer shape: `operator std::string() const;` declared in class; definition in cpp via `std::ostringstream` with `<sstream>` included.
- Difficulty / variation: mirrors the untested-but-required `operator std::string` surface of the reference.

### Spec 27: no-speculative-changes-calendar
- Files: calendar.cpp, calendar.h (test file: calendar_test.cpp)
- API: namespace `sched`; `class calendar { public: void book(int day); bool is_booked(int day) const; };`
- Prompt shape: repair turn with a concrete, single compile error (missing semicolon); the working code also contains a style smell (pass-by-value pair) that is NOT an error.
- Target capability: G4 — fix exactly the reported error; do not "improve" unrelated signatures, which risks breaking the test-facing API.
- Target answer shape: whole files differing only in the semicolon; by-value signature untouched.
- Difficulty / variation: counter-trains gratuitous const-ref edits from the failure log.

### Spec 28: row-col-semantics-theater-seats
- Files: seating.cpp, seating.h (test file: seating_test.cpp)
- API: namespace `theater`; `class seating { public: seating(std::pair<int,int> reserved_a, std::pair<int,int> reserved_b); bool same_row() const; bool same_seat_number() const; };` — pair is `{row, seat}`.
- Prompt shape: theater reservation conflict checker; documentation line states pairs are `{row, seat_number}`.
- Target capability: G2 — honor documented component order of `std::pair` instead of assuming `{x,y}`; read prompt semantics before naming members.
- Target answer shape: member names/comments reflecting row/seat; `.first` compared for rows, `.second` for seat numbers.
- Difficulty / variation: advanced — semantic-fidelity trap for models that default to `(x, y)`.

## 6. Acceptance & Validation Gates

Rows built from these specs enter training only if all gates pass:

1. **Format gate**: target answers parse as Aider whole-file listings — filename line, single fenced block per file, no diff hunks, no empty fences, no elision comments. Parser receipt required.
2. **Compile+test receipt**: each task's hidden test suite compiles and passes against the target answer in the same CMake/Catch2 harness shape as the benchmark; receipt (command + exit code) stored with the row.
3. **Repair-turn gate**: for repair/retry specs (17-20, 22, 27), the turn-1 answer must actually produce the seeded compiler/test failure, and the turn-2 target must fix it — both runs receipted.
4. **Hidden-edge coverage**: tests for exception-policy specs must include boundary values (0, max, max+1, -1) and the co-location case; diagonal specs must include all four directions plus the reflected non-diagonal false case.
5. **Contamination check**: story, identifiers, and test fixtures must not reproduce queen-attack's (or any polyglot-benchmark task's) instructions, test names, or reference code; automated diff/similarity screen against `polyglot-benchmark/`.
6. **API-shape gate**: class/function names follow the snake_case Exercism C++ convention derived from the exercise stem; signature qualifiers (const, ref) match the spec exactly.
7. **Minimal-repair gate**: for minimal-fix specs (17, 27), diff between turn-1 and turn-2 target files must touch only the fault — enforced mechanically.
8. **Answer-blind review**: a human (or second model) confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the raw shard-1 log and ground truth:

1. **Re-read every cited failure-log/shard line range** and confirmed quotes: shard 19948-20103 (naming deliberation), 20128-20194 (attempt-1 diff answer + malformed hunk at 20152), 39708/39713 (attempt-1 compile errors), 41991-42061 (attempt-2 rename fix), 46023-46042 (model noticed missing `domain_error`), 36233-36236 and 36482-36487 (raised-and-discarded `std::abs` include hypothesis, cited via failure-log source-line prefixes), 36540-36544 (empty diff answer), 46261-46277 and 65190-65200 (empty diff answers), 66016-66019 (hallucinated const-ref/const "fix" rationale) and 66187-66257 (the const-ref/const-member diff answer), 66270-66320 (final whole-file response), 66350-66356 raw = failure-log prefixes 66362-66368 (`'abs' is not a member of 'std'`).
2. **Re-checked every API claim** against `.meta/example.h` (class `chess_board` line 10, ctor line 13, accessors lines 18-25, `operator std::string` line 27, `can_attack` line 29), `.meta/example.cpp` (domain_error policy lines 13-21, no-abs diagonal formulation lines 46-52), and `queen_attack_test.cpp` (accessor REQUIREs lines 16-17, throw cases lines 26/34/42/50/57, attack cases lines 60-114). All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 1, result FAIL — matches failure-log header (lines 65818-65821) and terminal JSON (`tests_outcomes: [false, false]`).
4. **Corrections made during cross-check**:
   - Initial reading suggested the model hallucinated `spiral-matrix` content inside the queen-attack chat (raw shard 20222-21107); cross-check against the shard log's task-start/result markers (spiral-matrix run interleaved, its result JSON at shard 25117) showed this is concurrent-task log interleaving, NOT model confusion. Documented in section 1 note 2 instead of the failure anatomy.
   - Failure-log chunk 1 (source 19696-19928) is mostly the yacht task's tail; noted as slice-boundary bleed (section 1 note 1) rather than evidence about queen-attack.
   - Discovered and documented the ~12-line offset between the failure log's "source line" prefixes and the raw shard log for the terminal test log (section 1 note 3); both numbering schemes are labeled at each citation.
   - Corrected three citation line numbers after re-grep: the "most robust fix" rationale is at shard 66016-66019 (draft said 66009-66013), its diff answer spans shard 66187-66257 (draft said 66226-66257), and the first verbatim `REQUIRE_THROWS_AS` quote in attempt-1 compiler output is at shard 39721 (draft said 39719-39721; G5 citation widened to 39721-39752).
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `queen_attack_test.cpp` are present, consistent, and authoritative; no fallback or substitution was needed.
