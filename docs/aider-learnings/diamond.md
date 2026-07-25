# diamond — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `diamond`
- Shard: `0` (failure log section header, line 11852: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 11854; terminal JSON `tests_outcomes: [false, false]`, failure log lines 13123-13126 / raw shard-0 lines 19122-19125)
- Result: `FAIL` (failure log line 11855)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **11850-13154**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log` (diamond run spans source lines ~14080-19151; interleaved with concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/diamond/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/diamond/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/diamond/diamond_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Chunk-1 bleed-over.** "Attempt/log chunk 1, source lines 13841-14079" (failure log 11900-12143) is the *grade-school* task (grade_school thinking/answers, `grade_school_test.cpp` errors at failure log 12052-12060, its Tests failed at 12067). Diamond material begins in chunk 2 (failure log 12144+, source 15825+).
2. **Attempt-1 answer is only in the raw shard log.** The failure log excerpts start at attempt-1's tail; the attempt-1 answer itself (`print_diamond`) and its test failure were recovered from raw shard-0, cited as "shard-0 line N".
3. **Citation scheme.** Failure-log lines carry the log's raw-shard source-line prefixes; raw shard-0 lines are labeled "shard-0".

## 2. Benchmark Contract (Ground Truth)

File set: `diamond.h` + `diamond.cpp`, namespace `diamond`.

Public API (from `.meta/example.h`, enforced by `diamond_test.cpp`):

- `std::vector<std::string> rows(char middle_letter);` — a **value-returning** free function (example.h:7; `#pragma once` header with `<string>` and `<vector>`, example.h:1-4). The test compares vectors of strings: `REQUIRE(diamond::rows('A') == expected);` with `std::vector<std::string> expected{"A"};` (diamond_test.cpp:29-31), and multi-row expectations like `{" A ", "B B", " A "}` for `'B'` (diamond_test.cpp:35-40).

Exception policy: none.

Behavior contract (example.cpp:4-24): for middle letter L, produce `2·(L-'A')+1` strings; row i (ascending from 'A' to L) is `outer` spaces + letter + `inner` spaces + (letter again if not 'A') + `outer` spaces, where `outer = L - c` and `inner = (c - 'A')*2 - 1`; the second half mirrors the first (example.cpp:20-22). Degenerate case: `rows('A')` is exactly `{"A"}` (example.cpp:5). Every row has equal length (a square figure).

Not the contract: printing. The reference returns data; nothing writes to `std::cout`. A `print_diamond`-style side-effect API cannot satisfy `REQUIRE(rows(...) == expected)`.

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: invented print API + wrong geometry)

**What the model emitted.** A **diff-hunk answer** (shard-0 14219-14292): `void print_diamond(char letter);` in the header and a `std::cout`-printing implementation (shard-0 14233, 14252-14290). The printed geometry is wrong twice over: each row emits only *outer* spaces around a single letter (`spaces = center - current_char_val; print c;` with no inner spacing — shard-0 14258-14270), and the row letters descend from the middle letter (`char c = 'A' + std::abs(center - i);` puts the widest letter at the top instead of 'A'). The planning thinking explicitly chose the invention: "Let's call it `void print_diamond(char letter);`" (shard-0 14128) and "'Don't change names': I added a new function `print_diamond`. This is the minimal change required" (shard-0 14202-14204). Applied (shard-0 14293-14294).

**Test run 1 — compile failure** (shard-0 ~14400-14436): `error: 'rows' is not a member of 'diamond'` at diamond_test.cpp:47, 58, and further lines (shard-0 14400-14406). `Tests failed: .../diamond` (shard-0 14436).

### Attempt 2 (retry with compiler output) — outcome False (compile failure: `rows` misread as a row-count function)

**What the retry changed.** The model read the diagnostic correctly but guessed the wrong semantics: "the test file `diamond_test.cpp` is calling a function `diamond::rows(char)`... I need to add the `rows` function... `int rows(char letter)`, which calculates the number of rows based on the letter's position (e.g., 'A' is 1 row, 'C' is 3 rows)" (failure log 12249-12264, source 15927-15942), then added `int rows(char letter) { return letter - 'A' + 1; }` while **keeping** `print_diamond` (failure log 12277-12299, source 15955-15973). Still diff format; applied (failure log 12302-12303, source 15980-15981).

Two independent defects: (a) **return type** — `rows` must return `std::vector<std::string>` (the test compares it to a vector), not `int`; (b) **even the count was wrong** — the row count is `2·(L-'A')+1` (5 for 'C'), not `L-'A'+1` (3).

**Terminal result — compile failure** (failure log 12849-13154, source 18853-19151; and the identical earlier round inside chunk 2 at failure log 12398, source 16076): `error: no match for 'operator==' (operand types are 'int' and 'std::vector<std::__cxx11::basic_string<char>>')` at `REQUIRE(diamond::rows('A') == expected);` diamond_test.cpp:29 (failure log 12706, source 16384; terminal repeat at source ~19110), with the long candidate-note cascade (failure log 13086-13107, source 19085-19106). `Tests failed: .../diamond` (failure log 13115, source 19114); JSON `tests_outcomes: [false, false]` (failure log 13123-13126).

### Hard evidence vs inference

- Hard evidence: invented `print_diamond` (shard-0 14233, 14252-14290), geometry defects (no inner spacing, inverted row order — shard-0 14258-14270), attempt-1 `'rows' is not a member` errors (shard-0 14400-14406, 14436), attempt-2 `int rows` addition (failure log 12277-12299), terminal `operator==` type-mismatch error (failure log 12706, 13086-13107, 13115).
- Inference: attempt 1 is the boldest API invention in the set — the model chose a *printing* function for an exercise whose harness can only compare returned values, apparently pattern-matching "diamond" to console-art exercises from training. Attempt 2 then shows a semantic-guessing failure: told only that `rows` is missing, it guessed "number of rows" instead of "the rows themselves" — a plausible English reading that one quoted test line (`REQUIRE(diamond::rows('A') == expected)` with a vector on the right) would have disambiguated. The deeper geometry knowledge (outer/inner spacing formula, mirror half) was never demonstrated in either attempt.

## 4. Knowledge / Capability Gaps

- **G1 — Value-returning vs printing APIs.** Benchmark harnesses compare return values; side-effect print functions are untestable in this shape (contract: example.h:7 returns `std::vector<std::string>`; invented as `void print_diamond` at shard-0 14233).
- **G2 — Semantic inference from the function name + usage.** `rows(char)` returning a vector of row strings vs a row count — the model guessed count (failure log 12255-12264) and even guessed the count formula wrong (`n` instead of `2n-1`).
- **G3 — Mining quoted test usage.** The attempt-1 errors quoted `diamond_test.cpp` lines whose `REQUIRE(... == expected)` shape reveals the return type; the model never looked (terminal error failure log 12706 shows what was visible).
- **G4 — Diamond/figure geometry.** Correct construction: outer spacing `L - c`, inner spacing `2(c - 'A') - 1`, ascending letters then mirror (example.cpp:7-22). Attempt 1 had neither inner spacing nor ascending order (shard-0 14258-14270).
- **G5 — Whole-file format contract.** Diff-hunk answers in both attempts (shard-0 14219-14233; failure log 12277-12280).
- **G6 — Repair scope discipline.** Keeping the dead `print_diamond` while patching (failure log 12276/12290, source 15954/15968) — harmless here, but the contract-minimal surface (`rows` only) was never reached.

## 5. SFT Task Specifications (22 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-ribbon
- Files: ribbon.cpp, ribbon.h (test file: ribbon_test.cpp)
- API: namespace `gift`; `std::string wrap(const std::string& box);`
- Prompt shape: gift-wrap ribbon printer; whole-file instruction prominent.
- Target capability: G5 — complete whole-file listings only.
- Target answer shape: two whole-file listings, no diff fences.
- Difficulty / variation: minimal; format-only trap.

### Spec 02: value-not-print-banner-lines
- Files: banner.cpp, banner.h (test file: banner_test.cpp)
- API: namespace `stadium`; `std::vector<std::string> render(const std::string& word);`
- Prompt shape: stadium banner renderer; story stresses tests compare returned lines (a temptation to `std::cout` is explicitly forbidden).
- Target capability: G1 — return data structures; never print in library functions.
- Target answer shape: vector-building implementation; no iostream include.
- Difficulty / variation: the core diamond gap, minimal wrapper.

### Spec 03: print-api-repair-scoreboard
- Files: scoreboard.cpp, scoreboard.h (test file: scoreboard_test.cpp)
- API: namespace `arena`; test expects `std::vector<std::string> lines(int score);`; history answer shipped `void print(int score)` writing to cout; turn 2 shows `'lines' is not a member of 'arena'`.
- Prompt shape: repair — replace the print API with a value-returning one; remove the old function.
- Target capability: G1/G3 — wholesale API replacement, not addition alongside.
- Target answer shape: print function gone; value function present.
- Difficulty / variation: repair for the attempt-1 mistake.

### Spec 04: return-type-from-require-sandwich
- Files: sandwich.cpp, sandwich.h (test file: sandwich_test.cpp)
- API: namespace `deli`; (underdetermined: tests do `REQUIRE(deli::layers('M') == expected)` with a `std::vector<std::string>` expected).
- Prompt shape: repair — turn 2 compiler output quotes the REQUIRE line with a vector on the right and a missing-function error; history answer guessed `int layers(char)`.
- Target capability: G2/G3 — infer return type from the compared-against value in quoted test usage.
- Target answer shape: `std::vector<std::string> layers(char);`.
- Difficulty / variation: the exact attempt-2 misread, corrected.

### Spec 05: odd-count-formula-tier-stand
- Files: stand.cpp, stand.h (test file: stand_test.cpp)
- API: namespace `market`; `int tiers(char widest);`
- Prompt shape: market display stand; tier count for widest letter L is `2·(L-'A')+1`.
- Target capability: G2 — derive odd-count (2n−1) formulas; test at 'A', 'B', 'C'.
- Target answer shape: one-line formula.
- Difficulty / variation: formula-precision companion to the count misread.

### Spec 06: outer-inner-spacing-kite
- Files: kite.cpp, kite.h (test file: kite_test.cpp)
- API: namespace `sky`; `std::vector<std::string> frame(char widest);`
- Prompt shape: kite frame strings; each row has leading spaces and a gap between two markers; widths given by position.
- Target capability: G4 — two independent spacing quantities per row (edge + middle), computed from the row index.
- Target answer shape: named local spacing variables; append-based row construction.
- Difficulty / variation: spacing-math drill.

### Spec 07: mirror-half-pendant
- Files: pendant.cpp, pendant.h (test file: pendant_test.cpp)
- API: namespace `jewel`; `std::vector<std::string> shape(int half);`
- Prompt shape: pendant outline; bottom half mirrors the top (excluding the middle row).
- Target capability: G4 — mirror construction by re-using computed rows in reverse, not recomputing.
- Target answer shape: second loop appending `rows[i]` for i descending from half-1.
- Difficulty / variation: mirror idiom (reference style).

### Spec 08: degenerate-single-row-coin
- Files: coin.cpp, coin.h (test file: coin_test.cpp)
- API: namespace `mint`; `std::vector<std::string> engrave(char letter);`
- Prompt shape: coin engraving; the smallest input yields exactly one one-character row, no padding.
- Target capability: edge cases — degenerate input returns exactly the minimal figure, handled first.
- Target answer shape: early return `{"X"}` for the minimal case.
- Difficulty / variation: degenerate-case discipline.

### Spec 09: equal-width-rows-mosaic
- Files: mosaic.cpp, mosaic.h (test file: mosaic_test.cpp)
- API: namespace `tile`; `std::vector<std::string> panel(char widest);`
- Prompt shape: mosaic panel; hidden tests assert every row has identical length (square figure).
- Target capability: G4 — pad every row to the figure width (trailing spaces included).
- Target answer shape: trailing padding appended; no trimmed rows.
- Difficulty / variation: square-invariant drill.

### Spec 10: ascending-then-descending-letters-sampler
- Files: sampler.cpp, sampler.h (test file: sampler_test.cpp)
- API: namespace `stitch`; `std::vector<std::string> ladder(char top);`
- Prompt shape: stitch sampler; letters ascend from 'A' then descend; 'A' appears at both outer rows only.
- Target capability: G4 — ascending letter progression anchored at 'A' (not descending from the middle letter).
- Target answer shape: forward char loop for the top half.
- Difficulty / variation: counter-trains the inverted order of attempt 1.

### Spec 11: vector-string-return-type-garland
- Files: garland.cpp, garland.h (test file: garland_test.cpp)
- API: namespace `festival`; `std::vector<std::string> strands(int count);`
- Prompt shape: garland maker; header must include `<string>` and `<vector>`.
- Target capability: API/hygiene — exact return type `std::vector<std::string>` with the right includes.
- Target answer shape: both includes in the header; declaration matches definition.
- Difficulty / variation: type + include fidelity.

### Spec 12: string-append-construction-lantern-rows
- Files: lantern_rows.cpp, lantern_rows.h (test file: lantern_rows_test.cpp)
- API: namespace `lantern`; `std::string row(int left_pad, char glyph, int gap);`
- Prompt shape: lantern row builder; build via `append(n, ' ')` and `+=`.
- Target capability: string construction idiom — `std::string::append(count, char)` for repeated padding.
- Target answer shape: append-based builder, no char-by-char loops.
- Difficulty / variation: construction idiom.

### Spec 13: no-iostream-library-rule-embosser
- Files: emboss.cpp, emboss.h (test file: emboss_test.cpp)
- API: namespace `print`; `std::vector<std::string> plate(char letter);`
- Prompt shape: embossing plate generator; spec text: "these files are a library; they must not perform I/O."
- Target capability: G1 — no `<iostream>` in library answers; side-effect freedom.
- Target answer shape: no iostream include; pure value computation.
- Difficulty / variation: purity discipline.

### Spec 14: pragma-once-style-badge
- Files: badge.cpp, badge.h (test file: badge_test.cpp)
- API: namespace `conference`; `std::string render(const std::string& name);`
- Prompt shape: conference badge; starter header uses `#pragma once` — keep it.
- Target capability: header hygiene — match the starter's guard style.
- Target answer shape: `#pragma once` preserved; no mixed guard styles.
- Difficulty / variation: style-matching foundational.

### Spec 15: whole-file-on-retry-quilt
- Files: quilt.cpp, quilt.h (test file: quilt_test.cpp)
- API: namespace `craft`; `std::vector<std::string> patch(char widest);`
- Prompt shape: turn 1 answer in diff-hunk format (malformed); turn 2 repeats whole-file requirement.
- Target capability: G5 — format recovery on retry.
- Target answer shape: whole files, same semantics.
- Difficulty / variation: conditioned format repair.

### Spec 16: no-empty-fence-tapestry
- Files: tapestry.cpp, tapestry.h (test file: tapestry_test.cpp)
- API: namespace `loom`; `int width(char widest);`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines, no compiler output.
- Target capability: G5 — no empty fences; whole unchanged files or explicit no-change statement.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 17: remove-dead-function-repair-marquee
- Files: marquee.cpp, marquee.h (test file: marquee_test.cpp)
- API: namespace `cinema`; test expects only `std::vector<std::string> scroll(char letter);`; history answer kept a dead `void show(char)` alongside.
- Prompt shape: repair — add the correct function AND delete the unused invented one; header surface must be exactly the contract.
- Target capability: G6 — prune invented leftovers during repair.
- Target answer shape: only the contract function remains.
- Difficulty / variation: cleanup repair.

### Spec 18: contrastive-count-vs-content-totem
- Files: totem.cpp, totem.h (test file: totem_test.cpp)
- API: namespace `trail`; test expects `std::vector<std::string> faces(char widest);`.
- Prompt shape: contrastive — history shows `int faces(char)` (count interpretation) failing with `no match for 'operator==' (operand types are 'int' and 'std::vector<...>')`; target implements the content interpretation.
- Target capability: G2/G3 — map this operator== diagnostic to "return the collection, not a scalar".
- Target answer shape: vector-returning implementation.
- Difficulty / variation: negative-example-first with the log's diagnostic.

### Spec 19: spacing-formula-derivation-arrow
- Files: arrow.cpp, arrow.h (test file: arrow_test.cpp)
- API: namespace `archery`; `std::vector<std::string> target(char ring);`
- Prompt shape: archery target rings; story gives widths verbally ("each inner ring is two characters wider than the next"), target must derive the numeric spacing law.
- Target capability: G4 — translate a verbal growth rule into a per-index formula.
- Target answer shape: formula with a one-line derivation comment.
- Difficulty / variation: derivation skill.

### Spec 20: char-arithmetic-sundial-letters
- Files: glyphs.cpp, glyphs.h (test file: glyphs_test.cpp)
- API: namespace `ruin`; `char shift(char base, int steps); std::vector<std::string> wheel(char widest);`
- Prompt shape: ruin glyph wheel; letter arithmetic from 'A'.
- Target capability: char arithmetic — `'A' + offset` and `letter - 'A'` without sign/overflow slips.
- Target answer shape: explicit int offsets; no char overflow.
- Difficulty / variation: arithmetic hygiene.

### Spec 21: full-figure-capstone-hourglass
- Files: hourglass.cpp, hourglass.h (test file: hourglass_test.cpp)
- API: namespace `time`; `std::vector<std::string> bulbs(char widest);` — ascending then mirrored letter rows with outer and inner spacing, degenerate 'A' case.
- Prompt shape: hourglass bulb outline with prose geometry spec; names underdetermined, behaviors pinned.
- Target capability: G1+G2+G4 capstone — complete figure generator returning lines.
- Target answer shape: complete conventional implementation; whole files.
- Difficulty / variation: integrative final spec mirroring the full reference surface.

### Spec 22: usage-first-reading-observatory-dome
- Files: dome_lines.cpp, dome_lines.h (test file: dome_lines_test.cpp)
- API: namespace `sky`; (underdetermined; hidden tests pin the signature).
- Prompt shape: two-turn scripted chat — turn 1 must FIRST restate the required function signature (from test-usage quotes provided in the prompt) before any implementation; turn 2 implements.
- Target capability: G3 — habit: extract and state the contract from usage before writing code.
- Target answer shape: turn 1 = signature restatement; turn 2 = conforming whole files.
- Difficulty / variation: process-behavior capstone.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, trailing newline present. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass in the benchmark's CMake/Catch2 shape; receipt stored.
3. **Purity gate**: no target contains `std::cout`, `printf`, or `<iostream>` in the editable files — mechanically grepped.
4. **API-conformance gate**: exact return type `std::vector<std::string>` (or as specified) with matching declaration/definition and required includes — checked by compiling tests that compare against expected vectors.
5. **Geometry gate**: figure specs' tests must include the degenerate single-row case, equal-width verification, ascending-then-mirror letter order, and outer/inner spacing values at multiple sizes.
6. **Repair-turn gate**: repair specs (03, 04, 17, 18) must seed turn-1 answers producing the shown diagnostics; turn-2 targets fix the full defect and prune invented leftovers.
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce diamond's (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the raw shard-0 log, and ground truth:

1. **Re-read every cited line/range** and confirmed quotes verbatim: failure log 11852-11855 (header), 12052-12067 (grade-school bleed in chunk 1), 12247-12303 (attempt-2 thinking + `int rows` answer = source 15925-15981; the `int rows(char letter) { return letter - 'A' + 1; }` body at 12295-12297 = source 15971-15973), 12398 (attempt-2-era `operator==` error = source 16076), 12706 (same error repeated = source 16384), 12849-13154 (terminal block; candidate cascade 13086-13107 = source 19085-19106, Tests failed 13115 = source 19114), 13123-13126 (`tests_outcomes: [false, false]` = source 19122-19125); shard-0 14128 (naming invention quote), 14202-14204 ("minimal change" rationale), 14219-14292 (attempt-1 diff answer), 14233 (`print_diamond` declaration), 14252-14290 (print implementation; geometry defects at 14258-14270), 14293-14294 (applied), 14400-14406 (attempt-1 `'rows' is not a member` errors quoting test:47/58), 14436 (attempt-1 Tests failed).
2. **Re-checked every API claim** against `.meta/example.h` (`std::vector<std::string> rows(char middle_letter);` line 7, `#pragma once` + includes lines 1-4), `.meta/example.cpp` (degenerate 'A' case line 5, outer/inner spacing + ascending construction lines 7-19, mirror lines 20-22), and `diamond_test.cpp` (vector comparison `REQUIRE(diamond::rows('A') == expected)` lines 29-31, 'B' expectation lines 35-40). All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 0, result FAIL — matches header (11852-11855) and terminal JSON (13123-13126).
4. **Corrections made during cross-check**:
   - Chunk 1 (source 13841-14079) is entirely the grade-school task — documented as bleed (section 1 note 1), excluded from the failure anatomy.
   - The attempt-1 answer is not in the failure log's excerpts; it was recovered from the raw shard-0 log (shard-0 14219-14292) and is labeled accordingly (section 1 note 2).
   - Draft said the attempt-2 `operator==` error appeared only in the terminal block; re-grep shows the same diagnostic also inside chunk 2 (failure log 12398, source 16076, and 12706, source 16384) — both occurrences are now cited.
   - Corrected four citation line numbers after re-grep: attempt-2 thinking/answer spans 12249-12264 (draft said 12247-12262), the `int rows` body is at 12295-12297 (draft said 12297-12299), the kept `print_diamond` lines are at 12276/12290 (draft said 12283), and the count-guess quote is at 12255-12264 (draft said 12257-12262).
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `diamond_test.cpp` are present, consistent, and authoritative.
