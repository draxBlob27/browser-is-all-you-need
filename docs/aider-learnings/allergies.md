# allergies — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `allergies`
- Shard: `0` (failure log section header, line 1338: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 1340; terminal JSON `tests_outcomes: [false, false]`, failure log lines 2880-2883 / raw shard-0 lines 51550-51553)
- Result: `FAIL` (failure log line 1341)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **1336-2936**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log` (allergies run spans source lines ~26420-51603; interleaved with concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/allergies/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/allergies/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/allergies/allergies_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Chunk-1 bleed-over.** "Attempt/log chunk 1, source lines 19892-20591" (failure log 1386-2090) is entirely the *kindergarten-garden* task (its answer at failure log 1551-1565, source 20054-20065; its test run through source 20123+). No allergies content appears until chunk 2.
2. **Terminal-only excerpt.** The failure log includes only the final terminal test log (failure log 2607-2936, source 51281-51603). The attempt-1 test failure and the intermediate repair turns exist only in the raw shard-0 log; they are cited below as "shard-0 line N".
3. **Citation scheme.** Failure-log lines carry the log's raw-shard source-line prefixes; raw shard-0 lines are labeled "shard-0".

## 2. Benchmark Contract (Ground Truth)

File set: `allergies.h` + `allergies.cpp`, namespace `allergies`.

Public API (from `.meta/example.h`):

- `std::map<std::string, unsigned int> const ALLERGENS` — the 8 name→bit-value pairs (eggs=1 … cats=128), defined **in the header** (example.h:11-20).
- `class allergy_test` — snake_case class name (example.h:22). The test constructs temporaries: `allergies::allergy_test(0).is_allergic_to("eggs")` (allergies_test.cpp:9), `allergies::allergy_test(5).get_allergies()` (quoted in terminal errors, failure log 2814-2816).
- `allergy_test(unsigned int test_result);` constructor (example.h:25) — takes the raw score.
- `bool is_allergic_to(std::string const& allergen) const;` (example.h:27) — **string parameter**, enforced by calls like `is_allergic_to("pollen")` (terminal error quote, failure log 2619, source 51289: `cannot convert 'const char [7]' to ...`).
- `std::unordered_set<std::string> get_allergies() const;` (example.h:28) — **set of strings**, enforced by `REQUIRE(expected == allergies::allergy_test(3).get_allergies());` (failure log 2815, source 51485) where `expected` is a set of strings.
- Includes needed: `<string>`, `<map>`, `<unordered_set>` in the header (example.h:4-6).

Exception policy: none enforced by tests. (Reference uses `ALLERGENS.at(allergen)`, example.cpp:15, which would throw `std::out_of_range` for unknown names — not tested.)

Semantics: bitmask over the score — `is_allergic_to` is `(result & bit) == bit` (example.cpp:13-17); `get_allergies` collects every allergen whose bit is set (example.cpp:19-28). Scores may exceed 255 (e.g. 509, 257 — terminal error quotes, failure log 2850/2860, source 51519/51529), so unknown high bits must be tolerated (they simply match no allergen).

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: wholly invented API)

**What the model emitted.** The answer (failure log 2474, source 26800 `► **ANSWER**`) announced its invention up front: "defining the `Allergen` enum to map specific items to their bit scores, creating an `Allergies` class to manage the score" (failure log 2476-2479, source 26802-26805), then shipped **diff-hunk listings** under `edit_format: whole` (failure log 2490-2561, source 26814-26887):

- `enum class Allergen : int { eggs = 1, ..., cats = 128 };` (failure log 2500-2509, source 26826-26835)
- `class Allergies { public: explicit Allergies(unsigned int score); bool is_allergic_to(const Allergen& allergen) const; std::unordered_set<Allergen> list() const; ... };` (failure log 2511-2519, source 26837-26845)
- The hunk also contains a mangled guard line `-#endif // ALLERGIES_H+class Allergies {` (failure log 2511, source 26837) — starter file lacked a trailing newline.

Applied (failure log 2565-2566, source 26891-26892). Every element diverges from the contract: wrong class name (`Allergies` vs `allergy_test`), wrong parameter type (`const Allergen&` vs `std::string const&`), wrong method name and return type (`list()`→`unordered_set<Allergen>` vs `get_allergies()`→`unordered_set<std::string>`), and an invented enum replacing the string→value map.

**Reflection turns.** Three `# Fix any errors below` █-marker prompts followed; each time the model concluded the code was correct and answered "no changes are needed" with **empty ```` ```diff ```` fences** (shard-0 32132-32166, quote shard-0 32132-32141: "The code appears to be syntactically correct and logically sound... Therefore, no changes are needed." + empty fences; applied as no-ops at shard-0 32165-32166, 36727-36728).

**Test run 1.** Compile failure: `error: 'allergy_test' is not a member of 'allergies'; did you mean 'Allergies'?` at every test call site (shard-0 41030-41057, e.g. 41050-41053: `allergies_test.cpp:207:40: error ... REQUIRE(expected == allergies::allergy_test(255).get_allergies());`), then `Tests failed: .../allergies` (shard-0 41058).

### Attempt 2 (retry with compiler output) — outcome False (compile failure: factory-function patch + test-blaming)

**What the retry changed — and didn't.** Shown `error: 'allergy_test' is not a member of 'allergies'`, the model reasoned: "The test calls `allergy_test`. I am adding a *new* function (free function) named `allergy_test`. This does not change existing names." (shard-0 41111-41115) and emitted a diff adding a **free factory function** instead of renaming the class:

```
+Allergies allergy_test(unsigned int score);            (shard-0 41241)
+Allergies allergy_test(unsigned int score) {
+    return Allergies(score);
+}                                                        (shard-0 41259-41261)
```
applied at shard-0 41268-41269. This patches only the constructor-call expression; the underlying class still lacks `get_allergies()` and still takes `const Allergen&` instead of a string, so compilation was doomed.

**Test-blaming under signal-free turns.** In later reflection thinking the model explicitly noticed the remaining mismatches and dismissed them: "If the test calls `get_allergies()`, but the class has `list()`, that's a test error, not a code error." (shard-0 49111) and "I will trust the provided code." (shard-0 49116). Further turns again emitted empty-diff no-ops (shard-0 42368-42369, 49167-49168).

**Terminal result.** Final compile failed with two error families (failure log 2607-2936, source 51281-51603):
- `error: cannot convert 'const char [7]' to 'const allergies::Allergen&'` — test passes string literals, model requires the enum (failure log 2614-2619, source 51284-51289, and repeated across test lines 147/151/155/159...);
- `error: 'class allergies::Allergies' has no member named 'get_allergies'; did you mean 'Allergies'?` (failure log 2814-2816, source 51483-51485, repeated at test lines 192/197/202/207/212/217).
`Tests failed: .../allergies` (failure log 2873, source 51542); result JSON `tests_outcomes: [false, false]` (failure log 2880-2883).

### Hard evidence vs inference

- Hard evidence: invented enum+class API (failure log 2500-2519), diff format + mangled guard hunk (failure log 2490-2511), empty-diff no-ops (shard-0 32132-32166, 42368-42369, 49167-49168), attempt-1 `'allergy_test' is not a member` errors (shard-0 41030-41057), factory-function patch (shard-0 41241-41261), test-blaming quote (shard-0 49111), terminal conversion + missing-member errors (failure log 2614-2816).
- Inference: root cause is total API invention under an underdetermined prompt — the model designed the "nice" enum-based interface it preferred instead of the exercism-cpp canonical string-based `allergy_test` class. The repair then minimized churn against the model's own design (add a factory) rather than accepting that the whole surface was wrong, and a rationalization habit ("test error, not code error") replaced conformance to the test-facing contract. The compiler's "did you mean 'Allergies'?" was treated as confirmation of the model's naming rather than as proof the test demands a different class.

## 4. Knowledge / Capability Gaps

- **G1 — Canonical Exercism C++ API conventions.** The contract is a snake_case class `allergy_test` with string-based methods; the model invented a PascalCase `Allergies` class + `enum class Allergen` (failure log 2500-2519) and paid two failed attempts for it.
- **G2 — Test-facing contract over internal aesthetics.** The test calls `is_allergic_to("eggs")` with string literals; a type-safe enum interface is objectively nicer C++ but fails the contract (failure log 2614-2619). The model must treat the hidden test's call shapes as the specification.
- **G3 — Repair strategy: replace vs patch a wrong surface.** When the diagnostic shows the test wants a *class* it can construct and call two missing methods on, the correct repair is renaming/rebuilding the class surface — not adding a free factory function (shard-0 41241-41261) that leaves both method errors intact.
- **G4 — Signal-free retry handling / no-op policy.** Six reflection turns produced "no changes needed" + empty fences (shard-0 32132-32166 etc.) instead of either a real diagnosis or whole unchanged files; empty fences burned the 3-reflection budget both times.
- **G5 — Never blame the test.** "that's a test error, not a code error" (shard-0 49111) is the exact anti-pattern: in this harness the test is immutable ground truth; noticing a mismatch must trigger conformance, not dismissal.
- **G6 — Whole-file format contract.** Both substantive answers were ```` ```diff ```` hunks under `edit_format: whole` (failure log 2490-2561, shard-0 41241-41261), including a mangled `-#endif ... +class` merge line from a missing trailing newline (failure log 2511, source 26837).

## 5. SFT Task Specifications (24 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-star-log
- Files: star_log.cpp, star_log.h (test file: star_log_test.cpp)
- API: namespace `astronomy`; `class observation { public: explicit observation(int magnitude); bool visible_naked_eye() const; };`
- Prompt shape: amateur astronomy log; starter files guard + empty namespace; whole-file instruction prominent.
- Target capability: G6 — complete whole-file listings only.
- Target answer shape: two whole-file listings; no diff fences, no elisions.
- Difficulty / variation: minimal; format-only trap.

### Spec 02: guard-merge-newline-trap-tide
- Files: buoy.cpp, buoy.h (test file: buoy_test.cpp)
- API: namespace `harbor`; `class buoy { public: int channel() const; };`
- Prompt shape: starter header lacks a trailing newline after `#endif`; any edit must not produce merged guard lines.
- Target capability: G6 — whole-file answers sidestep diff-merge artifacts; teach the trailing-newline hazard.
- Target answer shape: clean whole files with proper final newline.
- Difficulty / variation: artifact-focused foundational.

### Spec 03: snake-case-class-pest-survey
- Files: trap_count.cpp, trap_count.h (test file: trap_count_test.cpp)
- API: namespace `orchard`; `class trap_check { public: explicit trap_check(unsigned int code); bool contains(const std::string& pest) const; };`
- Prompt shape: orchard pest-trap bitmask survey; prompt underdetermines the class name; hidden tests construct `trap_check(3)`.
- Target capability: G1 — snake_case class naming matching the exercise-stem convention, not PascalCase inventions.
- Target answer shape: snake_case class, ctor from `unsigned int`.
- Difficulty / variation: direct analog of the allergies naming failure.

### Spec 04: string-interface-not-enum-vet
- Files: symptom_mask.cpp, symptom_mask.h (test file: symptom_mask_test.cpp)
- API: namespace `clinic`; `class symptom_check { public: explicit symptom_check(unsigned int mask); bool has_symptom(const std::string& name) const; std::unordered_set<std::string> symptoms() const; };`
- Prompt shape: veterinary intake bitmask; a tempting enum design is possible, but the hidden contract passes strings.
- Target capability: G2 — string-keyed public interface even when an enum is aesthetically superior; map/lookup internally.
- Target answer shape: string→bit table (map or if-chain); methods take/return strings.
- Difficulty / variation: counter-trains the enum invention directly.

### Spec 05: bitmask-basics-herbarium
- Files: press.cpp, press.h (test file: press_test.cpp)
- API: namespace `herbarium`; `class specimen_sheet { public: explicit specimen_sheet(unsigned int marks); bool has(const std::string& plant) const; };`
- Prompt shape: pressed-flower collection flags.
- Target capability: bitmask idiom — power-of-two values, `(mask & bit) == bit` test.
- Target answer shape: per-allergen-style lookup + bitwise and; no floating point, no shifts on wrong side.
- Difficulty / variation: core bit skill, fresh domain.

### Spec 06: set-collector-bitmask-aviary
- Files: bird_log.cpp, bird_log.h (test file: bird_log_test.cpp)
- API: namespace `aviary`; `class sighting_card { public: explicit sighting_card(unsigned int bits); std::unordered_set<std::string> species_seen() const; };`
- Prompt shape: birdwatching punch-card; tests compare against `std::unordered_set<std::string>`.
- Target capability: G2 — exact return type fidelity (`std::unordered_set<std::string>`, not vector, not set of enum).
- Target answer shape: header includes `<unordered_set>` and `<string>`; iteration over the table collecting names.
- Difficulty / variation: return-type contract.

### Spec 07: high-bits-tolerance-observatory
- Files: flags.cpp, flags.h (test file: flags_test.cpp)
- API: namespace `observatory`; `class condition_flags { public: explicit condition_flags(unsigned int raw); bool raised(const std::string& flag) const; std::unordered_set<std::string> all_raised() const; };`
- Prompt shape: telescope status flags; hidden tests pass values with bits beyond the known 8 (e.g. 509) and expect them ignored, not rejected.
- Target capability: edge cases — unknown high bits tolerated; only known bits reported.
- Target answer shape: no validation throw on unknown bits; iteration bounded by the known table.
- Difficulty / variation: boundary-robustness spec.

### Spec 08: rename-class-repair-garden-moles
- Files: burrow.cpp, burrow.h (test file: burrow_test.cpp)
- API: namespace `garden`; test expects `class mole_check` with `bool present(const std::string&) const`; history answer shipped `class Moles`; turn 2 shows `error: 'mole_check' is not a member of 'garden'; did you mean 'Moles'?`.
- Prompt shape: repair/retry — rename the class everywhere (declaration, ctor, out-of-line definitions), delete the old name.
- Target capability: G1/G3 — treat the compiler's "did you mean" as proof of the expected name; full rename, not a wrapper.
- Target answer shape: whole files; no alias/forwarding shim left behind.
- Difficulty / variation: pure rename repair.

### Spec 09: no-factory-shim-repair-lottery
- Files: scratcher.cpp, scratcher.h (test file: scratcher_test.cpp)
- API: namespace `lottery`; test expects `class ticket_check` constructible from `unsigned int` with member `prizes()`; history answer shipped `class Ticket` plus a free function `Ticket ticket_check(unsigned int)`.
- Prompt shape: repair — compiler output shows member-call errors persisting after the factory shim; fix by making the class itself match the contract.
- Target capability: G3 — a factory shim cannot satisfy a member-function contract; replace the surface instead of patching around it.
- Target answer shape: class renamed/rebuilt; factory removed.
- Difficulty / variation: counter-trains the exact allergies attempt-2 mistake.

### Spec 10: never-blame-the-test-cipher-wheel
- Files: wheel.cpp, wheel.h (test file: wheel_test.cpp)
- API: namespace `cipher`; `class wheel { public: std::string decode(const std::string& token) const; };`
- Prompt shape: repair turn where the model's analysis (shown in history) concluded "the test is wrong"; the dataset target instead conforms the code to the test's call shape.
- Target capability: G5 — test-is-truth policy: mismatches are always fixed in the editable files.
- Target answer shape: conformed whole files; commentary explicitly retracts the test-blaming.
- Difficulty / variation: behavior-policy spec with explicit retraction.

### Spec 11: no-empty-fence-museum-frames
- Files: frame.cpp, frame.h (test file: frame_test.cpp)
- API: namespace `museum`; `class frame { public: int width() const; };`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines, no compiler output.
- Target capability: G4 — respond that no error is visible and re-emit whole unchanged files; never empty fences.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 12: widen-diagnosis-two-files-cable-ferry
- Files: cable.cpp, cable.h (test file: cable_test.cpp)
- API: namespace `ferry`; `class cable_car { public: bool ready() const; };`
- Prompt shape: repair turn where █ markers sit in the header but the true defect (wrong method name) is in the cpp; both files are in context.
- Target capability: G4 — inspect both editable files before concluding; fix the real defect wherever it lives.
- Target answer shape: whole cpp with the fix; header unchanged or re-emitted.
- Difficulty / variation: red-herring markers.

### Spec 13: map-in-header-constants-wine-cellar
- Files: cellar.cpp, cellar.h (test file: cellar_test.cpp)
- API: namespace `cellar`; `extern const std::map<std::string, int> BOTTLE_VALUES;` plus `class stock_check { public: explicit stock_check(unsigned int code); bool stocked(const std::string&) const; };`
- Prompt shape: wine-cellar inventory codes; the name→value table must be visible to both files.
- Target capability: header/impl separation for constants — declare/define a shared lookup table correctly (header `const` map with internal linkage or extern + cpp definition) and include `<map>`.
- Target answer shape: table defined once; both files compile; correct includes.
- Difficulty / variation: header/impl nuance the reference exercises.

### Spec 14: exact-method-name-repair-skate-park
- Files: tricks.cpp, tricks.h (test file: tricks_test.cpp)
- API: namespace `skate`; test expects `landed()` but history answer shipped `list_tricks()`; turn 2 shows `error: 'class skate::run' has no member named 'landed'`.
- Prompt shape: repair — rename the method to the one the test calls; keep return type semantics (set of strings).
- Target capability: G1/G3 — method-level conformance repair.
- Target answer shape: whole files with the method renamed in declaration and definition.
- Difficulty / variation: method-name variant of Spec 08.

### Spec 15: unsigned-score-types-reef-survey
- Files: reef.cpp, reef.h (test file: reef_test.cpp)
- API: namespace `reef`; `class dive_card { public: explicit dive_card(unsigned int code); bool spotted(const std::string&) const; };`
- Prompt shape: coral-reef dive log; tests pass large unsigned scores.
- Target capability: type fidelity — `unsigned int` score end-to-end; no narrowing to `int`/`char`.
- Target answer shape: unsigned in ctor, member, and bit ops.
- Difficulty / variation: numeric-type fidelity.

### Spec 16: contrastive-enum-vs-string-api-food-truck
- Files: menu_flags.cpp, menu_flags.h (test file: menu_flags_test.cpp)
- API: namespace `truck`; `class order_slip { public: explicit order_slip(unsigned int bits); bool wants(const std::string& item) const; };`
- Prompt shape: contrastive — history shows an enum-based design failing to compile against string-literal test calls, then asks for the corrected interface.
- Target capability: G2 — recognize from `cannot convert 'const char [N]' to 'const X&'` errors that the contract is string-based.
- Target answer shape: string-keyed implementation; enum removed entirely.
- Difficulty / variation: negative-example-first with the exact diagnostic family from the failure log.

### Spec 17: whole-file-on-retry-bonsai
- Files: pruning.cpp, pruning.h (test file: pruning_test.cpp)
- API: namespace `bonsai`; `class schedule { public: int next_month() const; };`
- Prompt shape: turn 1 answer is diff-hunk format (malformed); turn 2 repeats the whole-file requirement.
- Target capability: G6 — format recovery on retry.
- Target answer shape: whole files with identical semantics.
- Difficulty / variation: conditioned format repair.

### Spec 18: additive-only-existing-names-apiary-flags
- Files: hive_flags.cpp, hive_flags.h (test file: hive_flags_test.cpp)
- API: namespace `apiary`; starter already defines `struct frame_code { unsigned int bits; };`; model adds `class inspection { public: explicit inspection(frame_code f); bool flagged(const std::string&) const; };` without altering `frame_code`.
- Prompt shape: instruction "don't change names of existing functions or classes"; starter has one existing declaration.
- Target capability: preserve existing declarations verbatim; additive edits only.
- Target answer shape: starter declaration byte-identical in the answer.
- Difficulty / variation: additive-edit discipline.

### Spec 19: header-self-sufficiency-tidepools
- Files: pool.cpp, pool.h (test file: pool_test.cpp)
- API: namespace `pools`; `class sample { public: std::unordered_set<std::string> tags() const; };`
- Prompt shape: starter header uses `std::unordered_set<std::string>` but includes neither `<unordered_set>` nor `<string>`.
- Target capability: header self-sufficiency — include what you use in the header itself.
- Target answer shape: header compiles standalone.
- Difficulty / variation: include hygiene for the exact types this contract family uses.

### Spec 20: reflection-budget-use-climbing-wall
- Files: route_flags.cpp, route_flags.h (test file: route_flags_test.cpp)
- API: namespace `gym`; `class route_card { public: explicit route_card(unsigned int code); bool marked(const std::string&) const; };`
- Prompt shape: three-turn scripted chat — turn 1 wrong-API answer with compiler error available on turn 2; the target turn-2 answer must do the full correct repair immediately rather than no-op.
- Target capability: G4/G3 — spend reflection turns on real repairs when diagnostics exist; no-op only when truly signal-free.
- Target answer shape: turn-2 whole files with full API conformance.
- Difficulty / variation: budget-efficiency training.

### Spec 21: zero-and-full-masks-campsite
- Files: gear_flags.cpp, gear_flags.h (test file: gear_flags_test.cpp)
- API: namespace `camp`; `class pack_list { public: explicit pack_list(unsigned int bits); std::unordered_set<std::string> packed() const; bool has(const std::string&) const; };`
- Prompt shape: camping checklist; hidden tests include 0 (empty set, all false) and all-bits-set (everything present).
- Target capability: edge cases — 0 and full masks; empty result correctness.
- Target answer shape: loops handle both extremes without special cases.
- Difficulty / variation: numeric extremes.

### Spec 22: bit-equality-vs-nonzero-bakery-orders
- Files: order_flags.cpp, order_flags.h (test file: order_flags_test.cpp)
- API: namespace `bakery`; `class ticket { public: explicit ticket(unsigned int code); bool includes(const std::string&) const; };`
- Prompt shape: contrastive — history shows `(code & bit) != 0` vs `(code & bit) == bit` discussion; for single-bit values both work, but the spec requires the exact-mask comparison idiom and explains when they diverge.
- Target capability: precise bitmask test idiom and knowledge of its edge behavior.
- Target answer shape: `== bit` comparison with a one-line rationale.
- Difficulty / variation: idiom-precision spec.

### Spec 23: unknown-name-policy-botanical
- Files: key_card.cpp, key_card.h (test file: key_card_test.cpp)
- API: namespace `garden`; `class key { public: explicit key(unsigned int bits); bool unlocks(const std::string& door) const; };` — unknown door names return false (do not throw).
- Prompt shape: greenhouse door card; hidden tests query a name not in the table.
- Target capability: edge cases — policy choice for unknown keys: return false vs `map::at` throw; implement and document the specified policy.
- Target answer shape: lookup guarded (find != end), no exception escapes.
- Difficulty / variation: policy-awareness spec (contrast with reference's throwing `.at`).

### Spec 24: conformance-checklist-capstone-regatta
- Files: race_flags.cpp, race_flags.h (test file: race_flags_test.cpp)
- API: namespace `regatta`; `class protest_review { public: explicit protest_review(unsigned int code); bool cites(const std::string& rule) const; std::unordered_set<std::string> cited_rules() const; };`
- Prompt shape: sailing protest committee; prompt underdetermines all names; dataset-side checklist requires: snake_case class, string params, unordered_set<string> return, whole files, minimal surface.
- Target capability: G1+G2+G6 capstone — full conformance discipline under underdetermination.
- Target answer shape: fully conventional surface; nothing invented.
- Difficulty / variation: integrative final spec.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, no elisions; files end with a trailing newline. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass against the target in the benchmark's CMake/Catch2 shape; receipt stored.
3. **API-conformance gate**: class/method names, parameter and return types match the spec exactly (snake_case class, `const std::string&`, `std::unordered_set<std::string>` where specified) — checked by compiling the spec's tests.
4. **Repair-turn gate**: repair specs (08, 09, 10, 14, 16, 17, 20) must seed turn-1 answers that genuinely produce the shown diagnostics; turn-2 targets must fix them with no leftover shims (mechanically checked: no factory functions, no old names).
5. **No-op-turn gate**: signal-free retry specs (11, 12) targets contain no empty fences and no spurious changes — byte-wise verification.
6. **Hidden-edge coverage**: bitmask specs' tests must include 0, full mask, and values with unknown high bits set.
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce allergies' (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the raw shard-0 log, and ground truth:

1. **Re-read every cited line/range** and confirmed quotes verbatim: failure log 1338-1341 (header), 1551-1565 (kindergarten-garden bleed in chunk 1), 2474-2566 (attempt-1 answer; enum at 2500-2509 = source 26826-26835, class at 2511-2519 = source 26837-26845, mangled guard hunk at 2511 = source 26837), 2607-2936 (terminal block; conversion errors 2614-2619 = source 51284-51289, `get_allergies` errors 2814-2816 = source 51483-51485, Tests failed 2873 = source 51542, `tests_outcomes: [false, false]` 2880-2883 = source 51550-51553); shard-0 32132-32166 (empty-diff reflection), 41030-41058 (attempt-1 `'allergy_test' is not a member` errors + Tests failed), 41111-41115 (factory rationale), 41241-41261 (factory diff), 41268-41269 (applied), 42368-42369 and 49167-49168 (further empty-diff no-ops), 49111 ("that's a test error, not a code error"), 51531 (attempt-2 Tests failed).
2. **Re-checked every API claim** against `.meta/example.h` (`ALLERGENS` map lines 11-20, `class allergy_test` line 22, ctor line 25, `is_allergic_to(std::string const&)` line 27, `get_allergies()` → `std::unordered_set<std::string>` line 28, includes lines 4-6), `.meta/example.cpp` (bit semantics lines 13-28), and `allergies_test.cpp` (constructor temporaries line 9, 15, 19, ...; string literal arguments). All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 0, result FAIL — matches header (1338-1341) and terminal JSON (2880-2883).
4. **Corrections made during cross-check**:
   - Chunk 1 (source 19892-20591) is entirely the kindergarten-garden task — documented as bleed (section 1 note 1), excluded from the failure anatomy.
   - The failure log omits the attempt-1 test run and all intermediate turns; these were recovered from the raw shard-0 log and are explicitly labeled "shard-0" wherever cited (section 1 note 2).
   - Draft attributed the "test error, not a code error" quote to attempt 1; re-checking shard-0 line context (49111, after the 41058 attempt-1 failure and 41268 factory patch) places it in attempt 2's reflection phase — corrected in section 3.
   - Corrected two citation line numbers after re-grep: the `allergy_test(509)`/`allergy_test(257)` terminal quotes are at failure log 2850/2860 (draft said 2825/2835).
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `allergies_test.cpp` are present, consistent, and authoritative.
