# spiral-matrix — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `spiral-matrix`
- Shard: `1` (failure log line 86146)
- Test outcomes: `[False, False]` (failure log line 86148); result `FAIL` (line 86149)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **86144-86917**
  - Attempt 1 excerpt: "Attempt/log chunk 1, source lines 304-568" (failure log line 86194)
  - Attempt 1 repair excerpt: "Attempt/log chunk 2, source lines 1548-1666" (failure log line 86464)
  - Terminal test log: "Source lines 24859-25181" (failure log lines 86588-86916)
- Raw shard log (cross-check evidence; tasks run concurrently and interleave):
  `modal_run_logs/.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-1/benchmark.log`
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/spiral-matrix/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/spiral-matrix/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/spiral-matrix/spiral_matrix_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` has no spiral-matrix entry).

## 2. Benchmark Contract (Ground Truth)

File set: `spiral_matrix.h` + `spiral_matrix.cpp`, namespace `spiral_matrix`.

Public API (`.meta/example.h:9`):

```cpp
[[nodiscard]] std::vector<std::vector<uint32_t>> spiral_matrix(uint32_t size);
```

- The function is named **after the namespace/exercise** (`spiral_matrix::spiral_matrix`), takes a `uint32_t` size, and returns `std::vector<std::vector<uint32_t>>` — fixed-width **unsigned** element type, requiring `#include <cstdint>` and `#include <vector>` in the header (`.meta/example.h:4-5`).
- The test enforces the exact return type through `operator==` against `std::vector<std::vector<uint32_t>>` expected values (`spiral_matrix_test.cpp:13,19,24,32,41,51`) and calls the function as `spiral_matrix::spiral_matrix(N)` (`spiral_matrix_test.cpp:14,20,28,37,47,58`).
- Edge cases: size `0` must return an **empty** vector (test line 12-15, the only always-on test); sizes 1-5 under `EXERCISM_RUN_ALL_TESTS` (test lines 17-59). Fill starts at 1 top-left, clockwise inward spiral.
- Exception policy: **none** — no input is rejected; degenerate input (0) returns an empty matrix rather than throwing.
- Output-format constraint (benchmark harness, `edit_format: whole`, result JSON at failure log line 86861): every changed file must be returned as a *whole-file listing* — filename line, opening ```` ``` ````, entire file content, closing ```` ``` ```` — per the system prompt (failure log line 86158).

## 3. Failure Anatomy

The model's spiral-fill **algorithm was correct** (it hand-verified sizes 1, 3, 4 in its thinking, failure log lines 86318-86333). Both attempts failed at **compile time** on API-contract mismatches, and the repair turns never addressed the real errors.

### Attempt 1 — invented the wrong API, then hallucinated a phantom syntax error

- Turn 1: with empty starter files (no existing function to copy a name from), the model **invented** `std::vector<std::vector<int>> generate(int n)`. Thinking: "a common signature is `std::vector<std::vector<int>> generate(int n)`. Let's assume the function name is `generate`" (failure log line 86221, source line 328). Emitted as `diff`-fenced hunks (` ```diff `, failure log lines 86366, 86386), not the mandated whole-file listings. Two contract violations: wrong function name (`generate` vs `spiral_matrix`) and wrong element type (`int` vs `uint32_t`).
- Repair turns 1-3 (shard-1 log edits at lines 1645, 4392, 6185): each "Fix any errors below" prompt showed **only the header line marked with █ and no compiler error text** (failure log lines 86446-86453, source 553-560). The model hallucinated a pre-C++11 `>>`-vs-`> >` template-parsing ambiguity as the cause: "the `>>` token can be interpreted as the right shift operator... The standard fix for this is to add a space" (failure log lines 86474-86483, source 1556-1563). It changed `>>` to `> >` (failure log line 86556, source 1637), then on turn 2 emitted an **empty ` ```diff ` block** (shard-1 log line ~4385: `spiral_matrix.h` followed by an empty diff fence, "Applied edit" at shard line 4392 — a no-op), then on turn 3 **flip-flopped back** to no-space `>>` (shard-1 log, answer before line 6185: `-std::vector<std::vector<int> > generate(int n);` / `+std::vector<std::vector<int>> generate(int n);`).
- Terminal attempt-1 compile error (shard-1 log line 6248): `/aider/spiral-matrix/spiral_matrix_test.cpp:14:40: error: ‘spiral_matrix’ is not a member of ‘spiral_matrix’; did you mean ‘spiral_matrix’?` — the test calls `spiral_matrix::spiral_matrix(0)` (test line 14) but the model's function is still named `generate`. `Tests failed` at shard-1 log line 6366.

### Attempt 2 — fixed the name, kept the wrong type, repair turns repeated the phantom fix

- Turn 1 (shard-1 log, answer applied at lines 8767-8768): this time the model had attempt 1's real compiler output in context and correctly **renamed** `generate` → `spiral_matrix` ("This resolves the error \"'spiral_matrix' is not a member of 'spiral_matrix'\"", shard-1 log line 8684). But it kept `std::vector<std::vector<int>>` — the `int` vs `uint32_t` mismatch survived.
- Repair turns 1-3 (shard-1 log edits at 14385-14386, 14891-14892, 21087-21088): the fix prompts again showed only the █-marked header line (shard-1 log lines 8770-8785, 14388-14403). The model **re-hallucinated the same `>>` ambiguity**, now claiming it caused the "not a member" error it had already fixed (shard-1 log, thinking before line 14385: "The error \"'spiral_matrix' is not a member of 'spiral_matrix'\" occurs because the compiler treats `>>` as the right-shift operator"). Fix turns 2 and 3 again produced **empty diff blocks** (no-op answers before shard lines 14891 and 21087).
- Terminal attempt-2 compile error (failure log line 86630, source line 24896): `catch.hpp:2314:98: note: deduced conflicting types for parameter ‘_Tp’ (‘std::vector<unsigned int>’ and ‘std::vector<int>’)` — Catch's `compareEqual(lhs == rhs)` cannot compare the test's `std::vector<std::vector<uint32_t>>` expected value against the model's `std::vector<std::vector<int>>` return. Build fails (`make` errors at failure log lines 86849-86851, source 25115-25117); `Tests failed` at failure log line 86854 (source 25120).
- Result JSON: `"tests_outcomes": [false, false]` (failure log lines 86862-86865), `"num_user_asks": 8` (line 86871) — 2 attempts × (1 answer + 3 repair turns); `"num_malformed_responses": 0` (line 86873).

### Hard evidence vs inference

- Hard evidence: invented signature `generate(int)` returning `vector<vector<int>>` (failure log lines 86375, 86392); attempt-1 compiler error naming `spiral_matrix` missing (shard line 6248); attempt-2 compiler error `vector<unsigned int>` vs `vector<int>` (failure log line 86630); empty diff no-op turns (shard lines ~4385, ~14880, ~21060); `> >` flip-flop diffs (failure log lines 86555-86556; shard log before lines 6185 and 14385).
- Inference (root cause): the model has no reliable convention for deriving an exercism-style API from an empty starter (name the function after the namespace; use fixed-width unsigned types for "natural numbers"), and under error-free repair prompts it confabulates a plausible-sounding C++ problem instead of re-examining the signature. The harness never surfaced the `uint32_t` requirement to the model (fix prompts contained only the █-marked line), so attempt 2's type error was arguably undiscoverable inside the run — but a model with fixed-width-type discipline would have chosen `uint32_t` up front.

## 4. Knowledge / Capability Gaps

- **G1 — API-contract discovery under an underspecified prompt.** With an empty namespace, the model guessed `generate(int)` instead of the exercism convention `spiral_matrix::spiral_matrix(uint32_t)` (failure log line 86221). It lacked the prior "function named after the exercise namespace" and "derive the signature the hidden tests will call".
- **G2 — Repair-turn confabulation with sparse feedback.** Shown only a marked line, the model invented a phantom `>>` shift-operator ambiguity (failure log lines 86474-86483) and repeated it across 5 of 6 repair turns in both attempts, instead of stating "no visible error" and re-checking name/signature against the task.
- **G3 — Outdated C++ knowledge applied as a fix.** The belief that `std::vector<std::vector<int>>` is a syntax error needing `> >` is pre-C++11 lore; on C++17 (the benchmark compiler is GCC 13) it is a non-issue. The model flip-flopped between the two spellings across turns (failure log lines 86555-86556; shard log before lines 6185, 14385).
- **G4 — Fixed-width integer type discipline.** "Natural numbers" plus exercism conventions call for `uint32_t` from `<cstdint>`; the model used `int` and never reconsidered it, producing the terminal `vector<unsigned int>` vs `vector<int>` equality-deduction failure (failure log line 86630).
- **G5 — Whole-file format discipline.** The system prompt mandates whole-file listings; the model answered with ` ```diff ` hunks (failure log lines 86366, 86386, 86548) and, worse, **empty** diff blocks that applied as no-ops and burned repair turns (shard lines 4392, 14891, 21087). The harness tolerated this (`num_malformed_responses: 0`), so it never blocked the run, but it turned repair turns into wasted budget.
- **G6 — No-op / loop detection on retry.** Turns 2-3 of both attempts changed nothing substantive (empty diffs, space flip-flop). The model did not recognize it was stuck repeating itself and did not escalate to re-reading the task contract.

## 5. SFT Task Specifications

Note on exception policy: the spiral-matrix contract has **no throwing API** — its policy is "degenerate input returns empty, never throws". Specs 9-10 teach exactly that no-throw/empty-return policy in other domains; specs 11-12 teach a conventional `std::invalid_argument` policy for contrast, since the model must learn to distinguish the two.

### Spec 01: concentric-char-rug
- Files: `concentric_rug.cpp`, `concentric_rug.h` (test file: `concentric_rug_test.cpp`)
- API: namespace `concentric_rug`; `[[nodiscard]] std::vector<std::vector<char>> concentric_rug(uint32_t size);` — fills an N×N grid with ring characters `'a'`,`'b'`,... from the outside in; size 0 returns `{}`. No exceptions.
- Prompt shape: weaving-workshop story; starter files contain only include guard + empty namespace (same starter state as the failed task).
- Target capability: G1 — derive the function name from the namespace and choose container-of-container return type without being told.
- Target answer shape: two whole-file listings; header gains `#include <cstdint>`, `#include <vector>`; impl in `.cpp`; no diff fences.
- Difficulty / variation: foundational; char element type instead of integer.

### Spec 02: whole-file-rewrite-discipline
- Files: `ticket_grid.cpp`, `ticket_grid.h` (test file: `ticket_grid_test.cpp`)
- API: namespace `ticket_grid`; `[[nodiscard]] std::vector<std::vector<uint32_t>> ticket_grid(uint32_t rows, uint32_t cols);` — row-major sequential numbering; 0 in either dimension returns `{}`.
- Prompt shape: theater seat-numbering story; system prompt repeats the whole-file listing contract verbatim and the user message warns "do not use diff format".
- Target capability: G5 — emit whole-file listings only, both files, no `@@` hunks, no empty blocks.
- Target answer shape: filename line + fenced full content for `.h` and `.cpp`, complete from include guard to `#endif`.
- Difficulty / variation: 2-parameter size; rectangular (non-square) output.

### Spec 03: boustrophedon-field
- Files: `boustrophedon.cpp`, `boustrophedon.h` (test file: `boustrophedon_test.cpp`)
- API: namespace `boustrophedon`; `[[nodiscard]] std::vector<std::vector<uint32_t>> boustrophedon(uint32_t size);` — ox-plow (alternating-direction rows) numbering starting at 1; size 0 returns `{}`.
- Prompt shape: ancient plowing-story wrapper; empty-namespace starter.
- Target capability: G1 + G4 — namespace-named function plus `uint32_t` fixed-width elements from `<cstdint>`.
- Target answer shape: header+impl whole files; `<cstdint>` included in the header.
- Difficulty / variation: row-direction alternation instead of spiral; simpler algorithm isolates the signature skill.

### Spec 04: layer-cake-header-split
- Files: `layer_cake.cpp`, `layer_cake.h` (test file: `layer_cake_test.cpp`)
- API: namespace `layer_cake`; `[[nodiscard]] std::vector<std::vector<uint32_t>> layer_cake(uint32_t layers);` — each inner vector is one constant layer value; 0 layers returns `{}`.
- Prompt shape: bakery story; starter `.cpp` already contains an inline (wrong-place) definition that must be moved so the header holds only the declaration.
- Target capability: header/impl separation — declaration-only header, definition in `.cpp`, matching signatures.
- Target answer shape: whole files; no function body in the header.
- Difficulty / variation: starts from a misplaced-definition starter rather than empty files.

### Spec 05: voxel-stack-header-split
- Files: `voxel_stack.cpp`, `voxel_stack.h` (test file: `voxel_stack_test.cpp`)
- API: namespace `voxel_stack`; `struct Voxel { uint32_t x; uint32_t y; uint32_t z; };` plus `[[nodiscard]] std::vector<Voxel> voxel_stack(uint32_t height);` — declares the struct in the header, builds the stack in the `.cpp`; height 0 returns `{}`.
- Prompt shape: 3-D printing story; empty-namespace starter pair.
- Target capability: header/impl separation with a user-defined struct; keep type definition in the header, logic in the `.cpp`.
- Target answer shape: whole files; `#include <cstdint>` and `<vector>` in header.
- Difficulty / variation: struct + flat vector instead of nested vectors.

### Spec 06: repair-sparse-feedback-restate
- Files: `fountain_rings.cpp`, `fountain_rings.h` (test file: `fountain_rings_test.cpp`)
- API: namespace `fountain_rings`; `[[nodiscard]] std::vector<std::vector<uint32_t>> fountain_rings(uint32_t rings);`
- Prompt shape: two-turn repair task. Turn 1 the model solves normally. Turn 2 is a "Fix any errors below. ## See relevant line below marked with █" prompt whose marked line is already correct. Target: the model states no error is visible, re-verifies the signature against the task, and returns the unchanged whole files.
- Target capability: G2 + G6 — do not confabulate a phantom fix; no-op gracefully with whole files, not empty diffs.
- Target answer shape: short explanation + unchanged whole-file listings.
- Difficulty / variation: feedback contains zero error text, mirroring the failed run's fix prompts.

### Spec 07: repair-real-compiler-error-rename
- Files: `orchard_rows.cpp`, `orchard_rows.h` (test file: `orchard_rows_test.cpp`)
- API: namespace `orchard_rows`; `[[nodiscard]] std::vector<std::vector<uint32_t>> orchard_rows(uint32_t rows);`
- Prompt shape: two-turn repair. Turn 1 answer uses an invented name (`plant(int)`) — injected as the given wrong first answer. Turn 2 shows a real compiler error `'orchard_rows' is not a member of 'orchard_rows'`. Target: rename the function in both files.
- Target capability: G2 — parse an actual compiler error and make the minimal correct rename across header and impl.
- Target answer shape: both whole files with only the identifier changed.
- Difficulty / variation: repair driven by a genuine error message, contrast with Spec 06's empty feedback.

### Spec 08: contrastive-nested-template-myth
- Files: `star_chart.cpp`, `star_chart.h` (test file: `star_chart_test.cpp`)
- API: namespace `star_chart`; `[[nodiscard]] std::vector<std::vector<uint32_t>> star_chart(uint32_t magnitude_levels);`
- Prompt shape: contrastive row — the prompt includes a "junior developer note" claiming `vector<vector<uint32_t>>` must be written `> >` to compile; the correct answer ignores the note and explains C++11 made the space unnecessary.
- Target capability: G3 — reject outdated pre-C++11 `>>` folklore; nested template closers are fine in modern C++.
- Target answer shape: correct whole files using `>>`, plus one sentence debunking the note.
- Difficulty / variation: negative/contrastive spec; wrong-advice resistance.

### Spec 09: empty-on-zero-garden-beds
- Files: `garden_beds.cpp`, `garden_beds.h` (test file: `garden_beds_test.cpp`)
- API: namespace `garden_beds`; `[[nodiscard]] std::vector<std::vector<uint32_t>> garden_beds(uint32_t beds);` — bed 0..n-1 planting counts; **0 beds returns an empty vector, never throws**.
- Prompt shape: allotment-garden story; tests emphasize the size-0 case first.
- Target capability: exception policy (no-throw) — degenerate input returns an empty container rather than throwing or UB.
- Target answer shape: whole files; early return `{}` for 0.
- Difficulty / variation: policy is stated only implicitly ("there may be no beds at all").

### Spec 10: empty-on-zero-window-frames
- Files: `window_frames.cpp`, `window_frames.h` (test file: `window_frames_test.cpp`)
- API: namespace `window_frames`; `[[nodiscard]] std::vector<std::vector<uint32_t>> window_frames(uint32_t floors, uint32_t windows_per_floor);` — any zero dimension returns `{}`; no exceptions.
- Prompt shape: architecture-firm story; starter has a throwing guard (`if (n == 0) throw ...`) that must be removed.
- Target capability: exception policy (no-throw) — recognize and remove an inappropriate throw for degenerate input.
- Target answer shape: whole files with the throw replaced by an empty return.
- Difficulty / variation: repair-of-policy rather than greenfield.

### Spec 11: throw-on-negative-lottery
- Files: `lottery_drum.cpp`, `lottery_drum.h` (test file: `lottery_drum_test.cpp`)
- API: namespace `lottery_drum`; `[[nodiscard]] std::vector<uint32_t> lottery_drum(int32_t balls);` — throws `std::invalid_argument` when `balls < 0`; 0 returns `{}`.
- Prompt shape: raffle story; the contract explicitly documents the throw.
- Target capability: exception policy (throwing) — distinguish "invalid input throws" from Spec 09/10's "degenerate input returns empty"; include `<stdexcept>`.
- Target answer shape: whole files; guard clause throwing `std::invalid_argument`.
- Difficulty / variation: signed parameter so negatives are representable.

### Spec 12: throw-on-oversize-checkpoint
- Files: `rail_yard.cpp`, `rail_yard.h` (test file: `rail_yard_test.cpp`)
- API: namespace `rail_yard`; `[[nodiscard]] std::vector<std::vector<uint32_t>> rail_yard(uint32_t tracks);` — throws `std::out_of_range` when `tracks > 1000`.
- Prompt shape: railway story with an explicit capacity limit.
- Target capability: exception policy (throwing) — pick `std::out_of_range` for a bounds violation vs `std::invalid_argument` for a value violation.
- Target answer shape: whole files; `<stdexcept>` include; documented throw condition.
- Difficulty / variation: exception-type selection judgment.

### Spec 13: edge-size-one-ink-stamp
- Files: `ink_stamp.cpp`, `ink_stamp.h` (test file: `ink_stamp_test.cpp`)
- API: namespace `ink_stamp`; `[[nodiscard]] std::vector<std::vector<uint32_t>> ink_stamp(uint32_t size);` — border-only fill (hollow square); size 0 → `{}`, size 1 → `{{1}}`.
- Prompt shape: print-shop story.
- Target capability: edge cases — size 0 and size 1 both terminate correctly with no out-of-bounds writes.
- Target answer shape: whole files; loops written so the size-1 case cannot double-write.
- Difficulty / variation: hollow fill makes the size-1 degenerate case trickier than a full spiral.

### Spec 14: edge-rectangular-honeycomb
- Files: `honeycomb.cpp`, `honeycomb.h` (test file: `honeycomb_test.cpp`)
- API: namespace `honeycomb`; `[[nodiscard]] std::vector<std::vector<uint32_t>> honeycomb(uint32_t rows, uint32_t cols);` — spiral fill of a **rectangular** grid; any zero dimension → `{}`.
- Prompt shape: apiary story.
- Target capability: edge cases — generalize ring-walking to unequal bounds without overrun (the failed task's four-pointer logic breaks silently if rows≠cols is mishandled).
- Target answer shape: whole files; independent top/bottom/left/right bounds.
- Difficulty / variation: rectangular spiral — harder algorithmic sibling of the benchmark task.

### Spec 15: edge-counterclockwise-vinyl
- Files: `vinyl_groove.cpp`, `vinyl_groove.h` (test file: `vinyl_groove_test.cpp`)
- API: namespace `vinyl_groove`; `[[nodiscard]] std::vector<std::vector<uint32_t>> vinyl_groove(uint32_t size);` — counterclockwise inward spiral starting at bottom-left.
- Prompt shape: record-pressing story.
- Target capability: edge cases — direction/start-corner parameterization; off-by-one discipline when the walk starts away from (0,0).
- Target answer shape: whole files; explicit direction-rotation helper.
- Difficulty / variation: reversed orientation and start corner.

### Spec 16: overflow-safe-anthill
- Files: `anthill.cpp`, `anthill.h` (test file: `anthill_test.cpp`)
- API: namespace `anthill`; `[[nodiscard]] std::vector<std::vector<uint64_t>> anthill(uint32_t size);` — cell value is `size*size - <spiral position>`; must not overflow for size up to 65535.
- Prompt shape: myrmecology story.
- Target capability: G4 + overflow — choose `uint64_t` when products exceed 32 bits; cast before multiplying.
- Target answer shape: whole files; `static_cast<uint64_t>(size) * size` style widening.
- Difficulty / variation: 64-bit element type; overflow reasoning.

### Spec 17: uint16-element-quilt
- Files: `patchwork_quilt.cpp`, `patchwork_quilt.h` (test file: `patchwork_quilt_test.cpp`)
- API: namespace `patchwork_quilt`; `[[nodiscard]] std::vector<std::vector<uint16_t>> patchwork_quilt(uint16_t size);`
- Prompt shape: quilting-bee story.
- Target capability: G4 — exact-width type fidelity (`uint16_t`, not `int` or `uint32_t`) so test-side `vector<vector<uint16_t>>` equality compiles.
- Target answer shape: whole files; `<cstdint>` in header; all intermediate values cast to the element type.
- Difficulty / variation: smallest fixed-width type; narrowing-cast care.

### Spec 18: repair-type-mismatch-from-compiler-dump
- Files: `mosaic_tiles.cpp`, `mosaic_tiles.h` (test file: `mosaic_tiles_test.cpp`)
- API: namespace `mosaic_tiles`; `[[nodiscard]] std::vector<std::vector<uint32_t>> mosaic_tiles(uint32_t size);`
- Prompt shape: two-turn repair. Given first answer uses `std::vector<std::vector<int>>`; turn 2 shows a Catch `compareEqual` dump ending in "deduced conflicting types for parameter '_Tp' ('std::vector<unsigned int>' and 'std::vector<int>')". Target: change the element type to `uint32_t` in both files.
- Target capability: G4 + G2 — read a template-deduction failure and fix the signedness mismatch, the exact terminal error of this task.
- Target answer shape: whole files with only the type (and `<cstdint>` include) changed.
- Difficulty / variation: repair driven by the same compiler-signature as the failed run.

### Spec 19: format-no-elision-long-file
- Files: `skyscraper.cpp`, `skyscraper.h` (test file: `skyscraper_test.cpp`)
- API: namespace `skyscraper`; `[[nodiscard]] std::vector<std::vector<uint32_t>> skyscraper(uint32_t floors);` plus three small helper functions declared in the header.
- Prompt shape: construction-story; the correct implementation is long (~120 lines), tempting elision.
- Target capability: G5 — never elide with `...` or "rest unchanged"; full content of both files every turn.
- Target answer shape: complete whole-file listings including every helper body.
- Difficulty / variation: length pressure on the format contract.

### Spec 20: format-two-file-atomicity
- Files: `canal_locks.cpp`, `canal_locks.h` (test file: `canal_locks_test.cpp`)
- API: namespace `canal_locks`; `[[nodiscard]] std::vector<std::vector<uint32_t>> canal_locks(uint32_t locks);`
- Prompt shape: river-navigation story; turn 2 asks for a rename of a helper, which touches both files.
- Target capability: G5 — when a change spans header and impl, return **both** whole files, never just one.
- Target answer shape: two whole-file listings with consistent signatures.
- Difficulty / variation: cross-file consistency under a small change.

### Spec 21: diagonal-telescope-array
- Files: `telescope_array.cpp`, `telescope_array.h` (test file: `telescope_array_test.cpp`)
- API: namespace `telescope_array`; `[[nodiscard]] std::vector<std::vector<uint32_t>> telescope_array(uint32_t size);` — diagonal (Cantor-style) enumeration of an N×N grid.
- Prompt shape: radio-astronomy story; empty-namespace starter.
- Target capability: G1 — again derive name-from-namespace and `uint32_t` containers, in a different traversal domain.
- Target answer shape: whole files; header includes `<cstdint>`, `<vector>`.
- Difficulty / variation: anti-diagonal walk; different index arithmetic.

### Spec 22: zigzag-ridge-trail
- Files: `ridge_trail.cpp`, `ridge_trail.h` (test file: `ridge_trail_test.cpp`)
- API: namespace `ridge_trail`; `[[nodiscard]] std::vector<std::vector<uint32_t>> ridge_trail(uint32_t size);` — column-wise boustrophedon (alternating up/down columns).
- Prompt shape: mountaineering story; empty-namespace starter.
- Target capability: G1 + G4 — signature convention and fixed-width types, third domain.
- Target answer shape: whole files; empty-vector return for size 0.
- Difficulty / variation: column-major variant of Spec 03.

### Spec 23: repair-flip-flop-detection
- Files: `clock_dial.cpp`, `clock_dial.h` (test file: `clock_dial_test.cpp`)
- API: namespace `clock_dial`; `[[nodiscard]] std::vector<uint32_t> clock_dial(uint32_t marks);`
- Prompt shape: three-turn repair. Turn 1 answer has a genuine off-by-one. Turn 2 fix prompt shows only a █-marked line with no error text; the correct behavior is to leave formatting alone and re-check boundary logic, not to toggle cosmetic spellings. Turn 3 shows the real failing assertion; the model fixes the off-by-one.
- Target capability: G6 + G2 — recognize when a prior "fix" was cosmetic churn, revert focus to semantics.
- Target answer shape: turn 2 returns unchanged whole files with a "no error visible at the marked line" note; turn 3 returns the boundary fix.
- Difficulty / variation: explicitly trains against the flip-flop loop observed in the run.

### Spec 24: namespace-nested-api
- Files: `submarine_sonar.cpp`, `submarine_sonar.h` (test file: `submarine_sonar_test.cpp`)
- API: namespace `submarine_sonar { namespace grid { ... } }`; `[[nodiscard]] std::vector<std::vector<uint32_t>> grid::sweep(uint32_t range);`
- Prompt shape: naval story; tests call `submarine_sonar::grid::sweep(...)`.
- Target capability: G1 — honor nested-namespace naming exactly when deriving the callable path.
- Target answer shape: whole files with nested namespace blocks and matching closing comments.
- Difficulty / variation: two-level namespace; naming path fidelity.

### Spec 25: empty-diff-rejection
- Files: `paper_folding.cpp`, `paper_folding.h` (test file: `paper_folding_test.cpp`)
- API: namespace `paper_folding`; `[[nodiscard]] std::vector<uint32_t> paper_folding(uint32_t folds);`
- Prompt shape: origami story; after a correct turn 1, turn 2 says "Fix any errors below" with no marked error at all. Correct response: explain nothing needs changing and either omit file listings or return identical whole files — never an empty code fence.
- Target capability: G5 + G6 — empty/no-op responses must be explicit prose, not empty diff blocks that waste a turn.
- Target answer shape: prose-only "no changes needed" reply (or unchanged whole files).
- Difficulty / variation: pure format/behavior discipline, no algorithm.

### Spec 26: return-by-value-nodiscard
- Files: `beehive_frames.cpp`, `beehive_frames.h` (test file: `beehive_frames_test.cpp`)
- API: namespace `beehive_frames`; `[[nodiscard]] std::vector<std::vector<uint32_t>> beehive_frames(uint32_t frames);`
- Prompt shape: beekeeping story; starter header lacks `[[nodiscard]]` and the tests call the function in an unevaluated context that triggers a warning-as-error build.
- Target capability: G1 — replicate contract attributes (`[[nodiscard]]`) in the declaration.
- Target answer shape: whole files with the attribute present.
- Difficulty / variation: attribute fidelity, a detail the failed task's contract also carries (`.meta/example.h:9`).

### Spec 27: starter-trust-message
- Files: `cargo_manifest.cpp`, `cargo_manifest.h` (test file: `cargo_manifest_test.cpp`)
- API: namespace `cargo_manifest`; `[[nodiscard]] std::vector<std::vector<uint32_t>> cargo_manifest(uint32_t crates);`
- Prompt shape: shipping story; the conversation includes an *outdated* earlier version of the files, then a "Trust this message as the true contents" block — matching the failed task's prompt structure.
- Target capability: G1 — edit only the trusted latest file state; ignore stale earlier versions.
- Target answer shape: whole files based strictly on the trusted snapshot.
- Difficulty / variation: prompt-robustness dimension absent from other specs.

### Spec 28: multi-ring-stadium-seating
- Files: `stadium_seating.cpp`, `stadium_seating.h` (test file: `stadium_seating_test.cpp`)
- API: namespace `stadium_seating`; `[[nodiscard]] std::vector<std::vector<uint32_t>> stadium_seating(uint32_t rings);` — ring r contains seat numbers for that ring only (ragged rows allowed).
- Prompt shape: sports-venue story.
- Target capability: edge cases — ragged (non-rectangular) nested vectors; each row sized independently.
- Target answer shape: whole files; per-row `std::vector<uint32_t>` construction.
- Difficulty / variation: non-uniform inner lengths break assumptions of square-grid code.

### Spec 29: clockwise-rotation-lambda
- Files: `carousel.cpp`, `carousel.h` (test file: `carousel_test.cpp`)
- API: namespace `carousel`; `[[nodiscard]] std::vector<std::vector<uint32_t>> carousel(uint32_t size);`
- Prompt shape: fairground story; instructions suggest modeling direction as a rotatable vector.
- Target capability: algorithmic structuring — direction-walk with rotate-on-blocked (the reference's technique) vs four-pointer rings; either accepted if correct, teaching there are two clean formulations.
- Target answer shape: whole files; small direction-rotation helper (lambda or free function in anonymous namespace).
- Difficulty / variation: contrasts implementation strategies for the same contract.

### Spec 30: repair-wrong-file-targeted
- Files: `lighthouse_beam.cpp`, `lighthouse_beam.h` (test file: `lighthouse_beam_test.cpp`)
- API: namespace `lighthouse_beam`; `[[nodiscard]] std::vector<std::vector<uint32_t>> lighthouse_beam(uint32_t sectors);`
- Prompt shape: two-turn repair; the █-marked line is in the `.cpp`, but the actual defect (missing `<cstdint>` include) is in the `.h`. Target: fix the header even though the marker points elsewhere.
- Target capability: G2 — don't anchor on the marked line; diagnose the whole file set.
- Target answer shape: both whole files, header gaining the include.
- Difficulty / variation: misleading feedback localization.

## 6. Acceptance & Validation Gates

- **Parser validity:** every training-row answer must parse as Aider whole-file listings — filename line, fenced block, full content, no `@@` hunks, no empty fences, no elision markers. Rows failing the parser are rejected outright (G5).
- **Compile + test receipts:** each implemented spec must compile with GCC 13 `-std=c++17 -Wall -Werror` and pass its own `_test.cpp`; receipts (command + exit code) stored with the row.
- **Hidden-edge coverage:** every spec's test file must include the degenerate case (size 0 / empty return, or the documented throw) plus at least one non-square or size-1 case where applicable (G4, edge-case specs).
- **Signedness audit:** grep the answer for `std::vector<std::vector<int>>` or bare `int` element types where the contract says fixed-width; reject rows that regress to `int` (G4 — the exact terminal failure here).
- **Repair-turn quality gate:** for repair specs, the second-turn answer must reference the actual error text when present, and must not introduce cosmetic-only churn (e.g., `>>`→`> >` toggles) when feedback is empty (G2, G3, G6).
- **Contamination check:** spec stories, file names, function names, and test fixtures must not duplicate `spiral-matrix` or any other benchmark exercise; verify with a name/fixture diff against `polyglot-benchmark/cpp/exercises/practice/`.
- **Whole-file output rule:** sample-check 100% of rows at ingest that each changed file's listing compiles standalone as the complete file.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 after drafting:

1. **Failure-log citations re-read via `sed`/grep over lines 86144-86917.** Verified: shard `1` (86146), outcomes `[False, False]` (86148), chunk-1 marker (86194), the "Let's assume the function name is `generate`" quote (86221, source 328), the `+std::vector<std::vector<int>> generate(int n);` diff lines (86375, 86392, sources 482/499), ` ```diff ` fences (86366, 86386, 86548), fix prompt `# Fix any errors below, if possible.` (86443, source 550), the █-marked header line (86453, source 560), the phantom `>>` reasoning quote (86474-86483, sources 1556-1563), the `> >` "fix" diff (86555-86556, sources 1636-1637), terminal-log header (86588-86590), the type-conflict note `deduced conflicting types for parameter '_Tp' ('std::vector<unsigned int>' and 'std::vector<int>')` (86630, source 24896), `Tests failed` (86854, source 25120), and result-JSON fields (86862-86873). All matched as cited. Line-number corrections made during this re-read: `edit_format: "whole"` moved from 86858 to **86861**; the system-prompt format-contract citation narrowed from "86156-86172" to **86158**; the fix-prompt marked-line range corrected from "86450-86456" to **86446-86453**; the `make` error lines corrected from "86851-86853" to **86849-86851**. Sections 2 and 3 were updated accordingly.
2. **Shard-1 raw-log citations re-checked.** Verified: attempt-1 terminal error `'spiral_matrix' is not a member of 'spiral_matrix'` at shard line 6248; `Tests failed` at 6366 and 25115; applied edits at 546-547, 1645, 4392, 6185 (attempt 1) and 8767-8768, 14385-14386, 14891-14892, 21087-21088 (attempt 2); empty diff blocks immediately before the 4392, 14891, and 21087 "Applied edit" lines; the flip-flop diffs before 6185 and 14385; the rename thinking before 8767 (quote at shard line 8684; an early draft's "~8685" was tightened to 8684). Correction made during cross-check: an early draft attributed the fix prompts' missing compiler text only to attempt 1; re-reading showed attempt 2's fix prompts also showed only the █-marked line (shard lines 8770-8785, 14388-14403), and section 3 was corrected to say so for both attempts.
3. **API claims re-checked against ground truth.** `.meta/example.h:9` declares `[[nodiscard]] std::vector<std::vector<uint32_t>> spiral_matrix(uint32_t size);` with `<cstdint>`/`<vector>` at lines 4-5; test calls `spiral_matrix::spiral_matrix(N)` and compares against `std::vector<std::vector<uint32_t>>` at `spiral_matrix_test.cpp:13-14,19-20,24-28,32-37,41-47,51-58`; size-0 empty-vector case at lines 12-15. No exception policy exists in the contract — the doc states this explicitly and the spec set handles it via no-throw (Specs 09-10) and throwing-contrast (Specs 11-12) rows.
4. **Outcome array / shard** in section 1 match the section header (86146-86148) and the run summary (`[False, False]`, shard 1).
5. No ground-truth problems: `.meta/example.h`, `.meta/example.cpp`, and the test file are present and consistent.
