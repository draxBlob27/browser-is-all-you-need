# crypto-square — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `crypto-square`
- Shard: `0` (failure log section header, line 10168: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 10170; terminal JSON `tests_outcomes: [false, false]`, failure log lines 11810-11813 / raw shard-0 lines 38519-38522)
- Result: `FAIL` (failure log line 10171)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **10166-11849**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log` (crypto-square run spans source lines ~2880-38590; interleaved with concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/crypto-square/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/crypto-square/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/crypto-square/crypto_square_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Failure log omits the attempt-2 answer and attempt-1 test run.** Chunk 1 (failure log 10216+, source 2880-3489) is attempt 1; chunk 2 (failure log 10831+, source 27299-27998) is retry thinking. The attempt-1 test failure, the attempt-2 rename answer, and the reflection churn exist only in the raw shard-0 log, cited as "shard-0 line N".
2. **Cross-references.** Crypto-square thinking also leaks into the *circular-buffer* section's chunk 1 (failure log 5761-6465, source 37531-38230) — same raw shard-0 source range cited there as bleed.
3. **Citation scheme.** Failure-log lines carry the log's raw-shard source-line prefixes; raw shard-0 lines are labeled "shard-0".

## 2. Benchmark Contract (Ground Truth)

File set: `crypto_square.h` + `crypto_square.cpp`, namespace `crypto_square`.

Public API (from `.meta/example.h`, enforced by `crypto_square_test.cpp`):

- `class cipher` — lowercase (example.h:10). The test constructs temporaries: `crypto_square::cipher("").normalized_cipher_text()` (crypto_square_test.cpp:10), `cipher("... --- ...")` (test:17), `cipher("A")` (test:21), `cipher("@1,%!")` (test:29), etc.
- `cipher(std::string const& text);` — constructor **takes the plaintext and stores it (normalized)** (example.h:13, 26; example.cpp:33-36). This is a stateful object, not a one-shot function.
- `std::string normalize_plain_text() const;` (example.h:15)
- `std::size_t size() const;` — rectangle dimension (example.h:17; example.cpp:43-50: smallest `length` with `length² >= text_.size()`).
- `std::vector<std::string> plain_text_segments() const;` — row chunks (example.h:19; example.cpp:52-60).
- `std::string cipher_text() const;` (example.h:21; example.cpp:62-69: normalized ciphertext with spaces removed).
- `std::string normalized_cipher_text() const;` (example.h:23) — the method every visible test calls.

Exception policy: none.

Behavior contract: normalize (drop whitespace/punctuation, lowercase — example.cpp:20-26), arrange in `r` rows × `c` columns (`c >= r`, `c - r <= 1`), read down columns, emit chunks separated by spaces (`normalized_cipher_text`), or without spaces (`cipher_text`). Edge cases: empty plaintext → empty ciphertext (test:8-11), normalization-only-to-empty → empty (test:16-19), single letters after symbol stripping (test:24-33).

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: invented one-shot API)

**What the model emitted.** A **diff-hunk answer** (failure log 10710-10806, source 3371-3467): `class Cipher { public: std::string encode(const std::string& text); };` (failure log 10724-10727, source 3385-3388) with a stateless `Cipher::encode` implementation doing normalize → rectangle → column read (failure log 10750+, source 3411+). Mangled guard hunk `-#endif // CRYPTO_SQUARE_H+} // namespace crypto_square` (failure log 10729, source 3390). Every contract element was invented differently: PascalCase `Cipher`, no constructor/state, a single `encode(text)` method instead of the five-method stateful surface. (The rectangle math was roughly right; the API was wrong.) Applied (failure log 10805-10806, source 3466-3467).

**Test run 1 — compile failure** (shard-0 ~30240-30306): `error: 'cipher' is not a member of 'crypto_square'; did you mean 'Cipher'?` at every `crypto_square::cipher(...)` construction (shard-0 30240-30250, quoting crypto_square_test.cpp:21, 25, ...), ending `Tests failed: .../crypto-square` (shard-0 30306).

### Attempt 2 (retry with compiler output) — outcome False (compile failure: rename-only repair)

**What the retry changed.** Exactly one thing: `class Cipher` → `class cipher` in both files (shard-0 30474-30500, applied 30504-30505), still diff format. The class kept its single `encode(const std::string&)` method and **no user-declared constructor**.

**Reflection churn.** Signal-free █ prompts put the marker on the `encode` declaration; the model circled: "The error marker is pointing to the `encode` declaration. This is syntactically correct C++." (shard-0 37553-37555) and "If the code provided in the previous message is the 'true content' ... there should be no error." (shard-0 37573-37576) — without ever asking what the *test* needs (a constructor and five methods), and without the attempt-1 error output having quoted any test line that would reveal the full call pattern beyond `cipher(...)`.

**Terminal result — compile failure** (failure log 11536-11849, source ~38250-38590): `error: no matching function for call to 'crypto_square::cipher::cipher(const char [1])'` at test:10, `(const char [12])` at test:17, `(const char [2])` at test:21, `(const char [5])` at test:25, `(const char [6])` at test:29, `(const char [13])` at test:35, `(const char [11])` at test:44, `(const char [71])` at test:54 (failure log 11548-11786, source 38257-38495). With no user-declared constructor, the implicit copy/move constructors can't match a string literal. `Tests failed: .../crypto-square` (failure log 11802, source 38511); JSON `tests_outcomes: [false, false]` (failure log 11810-11813).

### Hard evidence vs inference

- Hard evidence: invented `Cipher` + `encode` API (failure log 10724-10727), mangled hunk (failure log 10729), attempt-1 `'cipher' is not a member` errors (shard-0 30240-30250, 30306), rename-only attempt-2 diff (shard-0 30474-30500), terminal `no matching constructor` errors (failure log 11548-11786), churn quotes (shard-0 37553-37576).
- Inference: two-stage API invention. Stage 1: the model designed the "natural" one-shot `encode` interface instead of the stateful exercism-cpp `cipher` class. Stage 2: given a naming error, it fixed the name and stopped — the repair treated the compiler's "did you mean" as the *entire* defect, never probing whether the construction syntax `cipher("...")` (visible in the attempt-1 error quotes, which include `crypto_square::cipher` used as a constructor) implies a string-taking constructor and member methods. The reflection turns had no error signal and produced pure wheel-spinning. Missing capability: inferring constructor+method surface from quoted test call expressions.

## 4. Knowledge / Capability Gaps

- **G1 — Stateful-class vs one-shot-function design judgment.** The contract is a constructed object whose methods expose pipeline stages (normalize → segments → ciphertext); the model flattened it to a stateless `encode` (failure log 10724-10727 vs example.h:13-23).
- **G2 — Lowercase class naming.** `cipher`, not `Cipher` (example.h:10; failure log 10724; compile cost shard-0 30240-30250). Same G-family as clock's `Clock`→`clock`.
- **G3 — Constructor surface from call expressions.** Test constructs `cipher(const char[N])` — a user-declared `cipher(std::string const&)` is required (example.h:13); the model shipped none (terminal errors failure log 11548-11786).
- **G4 — Repair completeness.** Rename-only fix (shard-0 30474-30500): the model addresses the *named* symbol in the diagnostic and never re-examines the *usage* in the quoted test lines for further requirements (constructor, five methods).
- **G5 — Whole-file format contract.** Diff-hunk answers (failure log 10715-10718), mangled guard line (failure log 10729).
- **G6 — Signal-free reflection convergence.** █-only prompts produced "this is valid C++" loops (shard-0 37553-37576) with no strategy (re-read the original test-error output, check the test's call shapes) — same pattern as allergies/clock.

## 5. SFT Task Specifications (24 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-tide-encoder
- Files: tide_code.cpp, tide_code.h (test file: tide_code_test.cpp)
- API: namespace `coast`; `std::string slugify(const std::string& raw);`
- Prompt shape: harbor log slug generator; whole-file instruction prominent.
- Target capability: G5 — complete whole-file listings only.
- Target answer shape: two whole-file listings, no diff fences.
- Difficulty / variation: minimal; format-only trap.

### Spec 02: lowercase-class-vault-door
- Files: vault_door.cpp, vault_door.h (test file: vault_door_test.cpp)
- API: namespace `bankvault`; `class vault_door { public: void spin(int clicks); int dial() const; };`
- Prompt shape: vault door mechanism; hidden tests use the lowercase class name.
- Target capability: G2 — lowercase class naming convention.
- Target answer shape: `class vault_door` exactly.
- Difficulty / variation: naming prior.

### Spec 03: stateful-pipeline-class-tea-brewer
- Files: brewer.cpp, brewer.h (test file: brewer_test.cpp)
- API: namespace `tea`; `class brewer { public: explicit brewer(const std::string& leaves); std::string rinsed() const; std::vector<std::string> stages() const; std::string poured() const; };`
- Prompt shape: tea-brewing pipeline where each method exposes a stage of the process on stored input.
- Target capability: G1 — store constructor input; methods operate on member state, not parameters.
- Target answer shape: `std::string const leaves_;` member; parameterless const methods.
- Difficulty / variation: stateful-design drill.

### Spec 04: constructor-from-string-label-printer
- Files: labeler.cpp, labeler.h (test file: labeler_test.cpp)
- API: namespace `shipping`; `class label { public: label(const std::string& raw); std::string formatted() const; };`
- Prompt shape: parcel label formatter; tests construct `label("Some Text")` directly.
- Target capability: G3 — a class constructed from a string needs a user-declared `std::string const&` constructor; implicit constructors don't convert.
- Target answer shape: explicit ctor storing the input.
- Difficulty / variation: constructor-surface drill.

### Spec 05: usage-driven-api-inference-fossil
- Files: fossil.cpp, fossil.h (test file: fossil_test.cpp)
- API: namespace `museum`; (underdetermined: tests construct `specimen("...")` and call `.cataloged()` — the repair target must infer both from quoted error lines).
- Prompt shape: repair — turn 2 compiler output quotes test lines `museum::specimen("T. rex").cataloged()` with `no matching function for call to 'specimen::specimen(const char [7])'`; history answer is a renamed-only class with a one-shot static.
- Target capability: G3/G4 — decode constructor + method surface from quoted call expressions; complete repair.
- Target answer shape: ctor taking the string + the called method; nothing else added.
- Difficulty / variation: the exact crypto-square attempt-2 gap.

### Spec 06: rename-only-trap-semaphore
- Files: semaphore.cpp, semaphore.h (test file: semaphore_test.cpp)
- API: namespace `rail`; test expects `class signal` with `signal(const std::string& aspect)`; history answer shipped `class Signal` with `static std::string show(const std::string&)`; turn 2 shows the case error.
- Prompt shape: repair — fix the case AND the design (ctor + member), not just the case.
- Target capability: G4 — treat the diagnostic as a starting point, not the full defect list.
- Target answer shape: lowercase class with string ctor and member method; static removed.
- Difficulty / variation: counter-trains rename-only repair.

### Spec 07: text-normalization-menu-code
- Files: menu_code.cpp, menu_code.h (test file: menu_code_test.cpp)
- API: namespace `cafe`; `std::string normalize(const std::string& raw);` — drop spaces and punctuation, lowercase the rest.
- Prompt shape: café menu shorthand codes.
- Target capability: character processing — `std::isalnum`/`std::tolower` with `static_cast<unsigned char>`, `<cctype>` included.
- Target answer shape: cast-guarded ctype calls; correct include.
- Difficulty / variation: normalization drill.

### Spec 08: empty-after-normalization-sticker
- Files: sticker.cpp, sticker.h (test file: sticker_test.cpp)
- API: namespace `print`; `std::string condensed(const std::string& raw);`
- Prompt shape: sticker text condenser; hidden tests pass strings that normalize to empty (all punctuation) and expect empty, not a crash or space.
- Target capability: edge cases — empty-result policy after filtering.
- Target answer shape: early return on empty; no division by zero in downstream math.
- Difficulty / variation: empty-edge discipline.

### Spec 09: rectangle-dimensions-photo-grid
- Files: photo_grid.cpp, photo_grid.h (test file: photo_grid_test.cpp)
- API: namespace `album`; `std::pair<std::size_t, std::size_t> grid_dims(std::size_t count);` — rows×cols with cols >= rows, cols - rows <= 1, minimal area.
- Prompt shape: photo album grid layout.
- Target capability: grid math — derive r and c from n with the inequality constraints (ceil-sqrt family), tested at perfect squares, primes, and n=0/1.
- Target answer shape: loop or sqrt-based computation satisfying all constraints.
- Difficulty / variation: the rectangle-math core, fresh domain.

### Spec 10: column-read-transpose-banner
- Files: banner.cpp, banner.h (test file: banner_test.cpp)
- API: namespace `stadium`; `std::string read_columns(const std::vector<std::string>& rows);`
- Prompt shape: stadium banner letters read down columns.
- Target capability: index arithmetic — column-major traversal over ragged rows with bounds checks.
- Target answer shape: column-outer loop; skip missing cells.
- Difficulty / variation: traversal drill.

### Spec 11: chunked-output-padded-call-sign
- Files: call_sign.cpp, call_sign.h (test file: call_sign_test.cpp)
- API: namespace `radio`; `std::string grouped(const std::string& code, std::size_t group);` — insert a space every `group` characters.
- Prompt shape: radio call-sign formatting.
- Target capability: output formatting — chunk joining with single separators, no trailing separator.
- Target answer shape: loop building groups joined by one space.
- Difficulty / variation: separator discipline.

### Spec 12: segments-method-window-blinds
- Files: blinds.cpp, blinds.h (test file: blinds_test.cpp)
- API: namespace `home`; `class blind_set { public: explicit blind_set(const std::string& code); std::vector<std::string> slats() const; };`
- Prompt shape: window-blind slats split a stored code into fixed-size chunks (last may be short).
- Target capability: G1 + chunking — `substr(i, len)` stepping; vector return; ragged final chunk.
- Target answer shape: loop `for (i = 0; i < s.size(); i += len)` pushing substr.
- Difficulty / variation: segments-analog method.

### Spec 13: size-ceiling-warehouse-aisles
- Files: aisles.cpp, aisles.h (test file: aisles_test.cpp)
- API: namespace `depot`; `std::size_t smallest_square_side(std::size_t boxes);`
- Prompt shape: depot floor planner; smallest n with n² >= boxes.
- Target capability: numeric edge — increment loop or sqrt ceil; overflow-safe comparison.
- Target answer shape: `while (side*side < boxes) ++side;`.
- Difficulty / variation: size()-analog computation.

### Spec 14: no-empty-fence-lantern-code
- Files: lantern_code.cpp, lantern_code.h (test file: lantern_code_test.cpp)
- API: namespace `festival`; `std::string encode(const std::string& raw);`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines, no compiler output.
- Target capability: G6 — no empty fences; state no error is visible; re-emit whole unchanged files.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 15: marker-on-valid-line-strategy-dockyard
- Files: crane.cpp, crane.h (test file: crane_test.cpp)
- API: namespace `port`; `class crane { public: explicit crane(int capacity); int lifts() const; };`
- Prompt shape: repair turn — █ marks a valid declaration; the true defect (missing ctor) is elsewhere in the same file; the turn-1 test output (in history) names it.
- Target capability: G6/G4 — consult the history's real diagnostics instead of hallucinating at the marker.
- Target answer shape: fix at the real site; marker line untouched.
- Difficulty / variation: red-herring marker with history signal.

### Spec 16: whole-file-on-retry-cipher-wheel-analog
- Files: dial_code.cpp, dial_code.h (test file: dial_code_test.cpp)
- API: namespace `fair`; `std::string rotate(const std::string& text, int places);`
- Prompt shape: turn 1 answer in diff-hunk format (malformed); turn 2 repeats whole-file requirement.
- Target capability: G5 — format recovery on retry.
- Target answer shape: whole files, same semantics.
- Difficulty / variation: conditioned format repair.

### Spec 17: multi-method-surface-beer-song-analog
- Files: recipe.cpp, recipe.h (test file: recipe_test.cpp)
- API: namespace `kitchen`; `class recipe { public: explicit recipe(const std::string& raw); std::string ingredients() const; std::vector<std::string> steps() const; std::string card() const; std::string summary() const; };`
- Prompt shape: recipe card pipeline with four output methods on stored text.
- Target capability: G1 — multi-method stateful surface; each method derives from the same member.
- Target answer shape: one stored member; four const methods.
- Difficulty / variation: surface breadth (five-method analog).

### Spec 18: const-method-discipline-greenhouse-log
- Files: env_log.cpp, env_log.h (test file: env_log_test.cpp)
- API: namespace `garden`; `class env_log { public: explicit env_log(const std::string& notes); std::string digest() const; };`
- Prompt shape: greenhouse log digest; tests call methods on const temporaries.
- Target capability: const-correctness — all readout methods const-qualified.
- Target answer shape: trailing const on every accessor.
- Difficulty / variation: qualifier drill.

### Spec 19: cctype-casts-barcode-wand
- Files: wand.cpp, wand.h (test file: wand_test.cpp)
- API: namespace `retail`; `std::string scrub(const std::string& raw);`
- Prompt shape: barcode wand input cleanup; spec warns about signed-char UB in ctype functions.
- Target capability: correctness — `static_cast<unsigned char>` before `std::tolower`/`std::isalnum`.
- Target answer shape: guarded casts at every ctype call.
- Difficulty / variation: UB-avoidance nuance.

### Spec 20: reserve-and-build-ticker-tape
- Files: ticker.cpp, ticker.h (test file: ticker_test.cpp)
- API: namespace `news`; `std::string compact(const std::string& raw);`
- Prompt shape: news ticker compactor; spec suggests reserving capacity for efficiency.
- Target capability: string building hygiene — `reserve`, append in loop, no quadratic reallocation chatter.
- Target answer shape: reserve + single-pass append.
- Difficulty / variation: efficiency-flavored foundational.

### Spec 21: ragged-grid-padding-crate-manifest
- Files: manifest.cpp, manifest.h (test file: manifest_test.cpp)
- API: namespace `dock`; `std::string column_read(const std::vector<std::string>& rows, char pad);` — short rows are padded before the column read.
- Prompt shape: crate manifest read down columns; padding character given.
- Target capability: edge cases — ragged input padded to rectangle before transposition.
- Target answer shape: pad-then-read; no out-of-range indexing.
- Difficulty / variation: padding variant of Spec 10.

### Spec 22: contrastive-static-vs-stateful-cipher-analog
- Files: scramble.cpp, scramble.h (test file: scramble_test.cpp)
- API: namespace `puzzle`; `class scrambler { public: explicit scrambler(const std::string& seed); std::string round() const; };`
- Prompt shape: contrastive — history shows `class Scrambler { static std::string run(const std::string&); }` failing construction/method tests; target converts to the stateful design.
- Target capability: G1/G4 — recognize from constructor-call diagnostics that a stateful object is required.
- Target answer shape: ctor + member method; static removed.
- Difficulty / variation: negative-example-first.

### Spec 23: empty-input-grid-photo-wall
- Files: photo_wall.cpp, photo_wall.h (test file: photo_wall_test.cpp)
- API: namespace `studio`; `std::vector<std::string> layout(const std::string& sequence);`
- Prompt shape: studio wall layout; hidden tests include empty sequence → empty vector (not one empty row).
- Target capability: edge cases — empty input yields empty output structure, no synthetic empty chunk.
- Target answer shape: early return before the chunk loop.
- Difficulty / variation: structural empty edge.

### Spec 24: capstone-square-transpose-analog
- Files: route_square.cpp, route_square.h (test file: route_square_test.cpp)
- API: namespace `courier`; `class route_square { public: explicit route_square(const std::string& stops); std::string normalized_stops() const; std::size_t belt() const; std::vector<std::string> legs() const; std::string condensed() const; std::string grouped_readout() const; private: std::string const stops_; };` — normalize, near-square grid, column readout (grouped and condensed variants).
- Prompt shape: courier stop-list obfuscation with prose behavior spec; names underdetermined, behaviors pinned.
- Target capability: G1+G2+G3+normalization+grid capstone — full stateful text-pipeline class.
- Target answer shape: complete conventional implementation; whole files.
- Difficulty / variation: integrative final spec mirroring the full reference surface.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, trailing newline present. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass in the benchmark's CMake/Catch2 shape; receipt stored.
3. **API-conformance gate**: class case, constructor-from-string, stateful member methods with exact names — checked by compiling tests that construct from string literals and call every method.
4. **Behavior gate**: normalization (punctuation/space stripping, case folding), grid-dimension constraints (c >= r, c - r <= 1), column-read, grouped/condensed variants, and empty-after-normalize cases all covered in each pipeline spec's tests.
5. **Repair-turn gate**: repair specs (05, 06, 15, 22) must seed turn-1 answers producing the shown diagnostics; turn-2 targets fix the FULL surface defect (not rename-only) — mechanically checked for the required ctor/methods.
6. **No-op-turn gate**: signal-free retry specs (14, 15) targets contain no empty fences and no spurious changes.
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce crypto-square's (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the raw shard-0 log, and ground truth:

1. **Re-read every cited line/range** and confirmed quotes verbatim: failure log 10168-10171 (header), 10710-10806 (attempt-1 answer; `Cipher`/`encode` declaration 10724-10727 = source 3385-3388, mangled hunk 10729 = source 3390, applied 10805-10806), 11536-11849 (terminal block; constructor-mismatch errors 11548-11786 = source 38257-38495, Tests failed 11802 = source 38511), 11810-11813 (`tests_outcomes: [false, false]` = source 38519-38522); shard-0 30240-30250 (attempt-1 `'cipher' is not a member` errors quoting test:21/25), 30306 (attempt-1 Tests failed), 30474-30500 (rename-only diff `Cipher`→`cipher`), 30504-30505 (applied), 37553-37576 (churn quotes "syntactically correct C++" / "there should be no error"), 38505 (raw terminal Tests failed).
2. **Re-checked every API claim** against `.meta/example.h` (`class cipher` line 10, ctor line 13, five methods lines 15-23, stored `text_` line 26), `.meta/example.cpp` (normalize helper lines 20-26, ctor storing normalized text lines 33-36, `size()` lines 43-50, `plain_text_segments` lines 52-60, `cipher_text` lines 62-69), and `crypto_square_test.cpp` (constructor temporaries with `normalized_cipher_text()` lines 10, 17, 21, 25, 29). All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 0, result FAIL — matches header (10168-10171) and terminal JSON (11810-11813).
4. **Corrections made during cross-check**:
   - Verified against the raw shard log that attempt 2 changed ONLY the class name (shard-0 30474-30500: `Cipher`→`cipher` in both files, `encode` retained) — the "rename-only repair" framing is hard evidence, not inference.
   - Confirmed the terminal errors are constructor mismatches (`cipher(const char [N])` against a class with no user-declared ctor), not missing methods — the five-method gap never even got to compile-time visibility; noted in section 3 that the constructor gap was the terminal blocker with the method gap latent behind it.
   - Cross-referenced the circular-buffer section's chunk-1 bleed (failure log 5761-6465) as the same raw source range — recorded in section 1 note 2.
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `crypto_square_test.cpp` are present, consistent, and authoritative.
