# kindergarten-garden — Failure Learning Document

Date of analysis: 2026-07-24. Eval run: `glm47-aider-expansion-sft-fixed26-20260723T091839Z` (GLM-4.7 SFT, Aider Polyglot C++, whole edit format).

## 1. Task Identity & Evidence Pointers

- Task slug: `kindergarten-garden`
- Shard: `0`
- Test outcomes: `[False, False]` (test run 1 FAIL — compile errors; test run 2 FAIL — compile errors)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md`, lines 16419–18426 (header at 16419–16424; attempt chunk 1 at 16469, source lines 4762–5577; attempt chunk 2 at 17290, source lines 10214–11015; terminal test log at 18099 (`Source lines 47370-47692:`) through 18426).
- Raw shard log (cross-check evidence): `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log`. The failure log's quoted "source lines" are line numbers in this shard log. The failure log omits all middle turns between source 11015 and 47370; those turns (attempt-1 reflections, test run 1, all of attempt 2) were recovered from the shard log: attempt-1 reflection no-ops at 15790–15800 and 20050–20060, reflections stop at 20080, test run 1 at 20122–20659; attempt-2 answers applied at 27264–27265, 32564, 40264–40265, reflections stop at 47190, final whole-file response at 47191–47260+, test run 2 at 47370–47692. The shard log interleaves 8 concurrent tasks (dnd-character, all-your-base, bank-account, grade-school, clock, diamond, allergies, gigasecond, binary-search-tree, crypto-square, complex-numbers, circular_buffer among them); only turns touching `kindergarten_garden.*` belong to this task.
- Ground truth (read-only): `polyglot-benchmark/cpp/exercises/practice/kindergarten-garden/`
  - Reference: `.meta/example.h`, `.meta/example.cpp`
  - Tests: `kindergarten_garden_test.cpp`
  - Starters (NOT the solution): `kindergarten_garden.cpp`, `kindergarten_garden.h` at the exercise root (empty namespace in both).
- Existing analog dir: none for kindergarten-garden under `aider-fixed26-analogs/` (granularity reference: `aider-fixed26-analogs/fixed26-b001-all-your-base/`).
- Result JSON (failure log 18365–18424 / shard 47633–47692): `"tests_outcomes": [false, false]`, `"num_error_outputs": 0`, `"num_user_asks": 8`, `"num_exhausted_context_windows": 0`, `"num_malformed_responses": 0`, `"edit_format": "whole"`.

## 2. Benchmark Contract (Ground Truth)

File set: `kindergarten_garden.h` + `kindergarten_garden.cpp`, namespace `kindergarten_garden`.

Public API (from `.meta/example.h`):

- `.meta/example.h:1` — `#pragma once` header guard style.
- `.meta/example.h:3-4` — `#include <array>` and `#include <string_view>` (header is self-sufficient).
- `.meta/example.h:8` — `enum class Plants : char { grass = 'G', clover = 'C', radishes = 'R', violets = 'V' };` — scoped enum with **`char` underlying type and lowercase, pluralized enumerator names mapped to the diagram letters**. This is the contract element the model never reproduced.
- `.meta/example.h:10-11` — `std::array<Plants, 4> plants(std::string_view diagram, std::string_view student);` — a **free function** in the namespace (no class), returning a fixed-size `std::array`, parameters **`diagram` first, `student` second**, both by `std::string_view`.

Semantics (from `.meta/example.cpp`):

- `.meta/example.cpp:12` — `const int first_plant_index = 2 * (student.at(0) - 'A');` — each child gets **two** cups per row; the column offset is `2 *` the alphabetical index (derived from the first letter of the name), not `4 *`.
- `.meta/example.cpp:13` — second row located via `diagram.find('\n') + first_plant_index + 1` (rows separated by `\n` in the diagram string).
- `.meta/example.cpp:20-21` — char-to-enum conversion via `std::transform` + `static_cast<Plants>(c)` (legal because the enumerators carry the diagram char values).

Tests enforcing the contract (`kindergarten_garden_test.cpp`):

- `:9-14` — `CATCH_REGISTER_ENUM(kindergarten_garden::Plants, ...::clover, ...::grass, ...::violets, ...::radishes)` — the test file names the exact lowercase plural enumerators; any other enumerator spelling fails to compile.
- `:16-17` — `std::array<kindergarten_garden::Plants, 4> expected{...}; REQUIRE(kindergarten_garden::plants("RC\nGG", "Alice") == expected);` — calling convention: namespace-qualified free function, diagram string first, student name second, `std::array` equality.
- All further cases (`:21` onward) sit under `#if defined(EXERCISM_RUN_ALL_TESTS)` (`:19`) and exercise Bob/Charlie/etc. and the full 24-cup diagram.

Exception policy: none — the reference throws nothing and the tests assert no throws. (The model's invented `std::invalid_argument` for unknown diagram chars is extra, not contract.)

Output-format constraints: Aider *whole* edit format — filename line, opening fence, **entire file content**, closing fence; never diff hunks, never elisions (system prompt, failure log 16427–16449; restated in the user instructions, failure log 16467).

## 3. Failure Anatomy

### Attempt 1 — invented `Garden` class returning `std::vector<std::string>`, diff-format answer, reflection no-ops, compile failure

**Turn 1 (failure log 17185–17288, shard 5475–5574).** The model announced an API of its own invention:

> `5477: To solve the Kindergarten Garden problem, I have defined a `Garden` class with a`
> `5478: static method `plants`. This method takes a student's name and the diagram`
> (failure log 17185–17187, quoting shard lines 5477–5478)

and answered in ```` ```diff ```` fences for both files (shard 5491, 5514):

> `5501: +class Garden {`
> `5503: +    static std::vector<std::string> plants(const std::string& student, const`
> (failure log 17211–17213, quoting shard 5501–5503)

Three contract violations in one answer: (a) class + static method instead of a namespace-scope free function; (b) `std::vector<std::string>` of plant **name strings** (`{'G', "Grass"}, ...` at shard 5530–5535) instead of `std::array<Plants, 4>`; (c) parameter order `(student, diagram)` instead of `(diagram, student)`. Latent logic bug: `size_t start_index = student_index * 4;` and `row_1_start = 48 + start_index;` (shard 5547–5549) — 4 cups per row and a hardcoded 48-plant row stride, vs. the contract's 2-per-row and `find('\n')` (`.meta/example.cpp:12-13`). Aider applied the diffs (`Applied edit to kindergarten_garden.cpp / .h`, shard 5573–5574) and replied with `# Fix any errors below, if possible.` (shard 5576).

**Turns 2–4 (reflection no-ops; not excerpted in the failure log, shard log only).** Facing vague marked-line prompts, the model twice concluded the code was correct and emitted **empty diffs**:

> `I will output the files.` ... `kindergarten_garden.h` / ```` ```diff ```` / ```` ``` ```` (shard 15790–15798; `Tokens: 3.2k sent, 12k received.` at 15798 — 12k tokens of rumination for an empty diff)

A second empty-diff turn followed (shard 20050–20060, `Tokens: 3.9k sent, 1.6k received.`), then `Only 3 reflections allowed, stopping.` (shard 20080). The final captured response was a whole-file listing still declaring only `class Garden` (shard 20081–20107). The reflection prompts never included compiler text, so attempt 1 never learned the real error.

**Test run 1 (shard 20122–20659): compile failure.**

> `20122: /aider/kindergarten-garden/kindergarten_garden_test.cpp:9:42: error: ‘Plants’ is not a member of ‘kindergarten_garden’`
> `20150: /aider/kindergarten-garden/kindergarten_garden_test.cpp:17:32: error: ‘plants’ is not a member of ‘kindergarten_garden’`

The tests reference `kindergarten_garden::Plants` (an enum the model never declared) and `kindergarten_garden::plants` (a free function hidden inside `Garden`). Attempt 1 FAIL.

### Attempt 2 — enum added with wrong enumerator names; signature order never fixed; compile failure again

Attempt 2's fresh chat included the compiler errors.

**Turn 1 (shard ~26950–27270; answer applied at 27264–27265).** The model correctly diagnosed the two missing names ("The test file is expecting a `Plants` enum type and a return type of `std::array<Plants, 4>`", shard ~27140–27143) and answered — again in ```` ```diff ```` fences — adding:

> `+enum class Plants {`
> `+    Grass,`
> `+    Clover,`
> `+    Radish,`
> `+    Violet`
> (shard 27165–27170)

Right shape family (scoped enum + `std::array<Plants, 4>`), wrong details: enumerators are capitalized singular (`Grass`) where the contract requires lowercase plural (`grass`), and no `: char` underlying values. It also **kept** the static method inside `class Garden` and the `(student, diagram)` order, and kept the 4-per-row indexing (`start_index = student_index * 4` retained in the same hunk).

**Turn 2 (shard ~32220–32564): empty-diff no-op.** ~340 lines of circular reasoning about whether the enum belonged inside or outside the class (`enum class Plants { ... }; is *outside* the class.`, shard ~32331) ended in an empty diff:

> `kindergarten_garden.h` / ```` ```diff ```` / ```` ``` ```` (shard 32557–32559; `Tokens: 22k sent, 3.8k received.` at 32562)

**Turn 3 (shard ~39900–40265; applied at 40264–40265).** The model finally fixed one real error:

> `I have identified the issue. The test file is calling `kindergarten_garden::plants`, but the function was previously defined inside the `Garden` class.` (shard ~40208–40214)

moving `plants` to namespace scope (`std::array<Plants, 4> plants(const std::string& student, const std::string& diagram);`, shard 40229–40231) — but still with `(student, diagram)` order and `Grass/Clover/Radish/Violet`.

**Turn 4 (shard 47190–47260+).** `Only 3 reflections allowed, stopping.` (shard 47190); the final response was a whole-file listing of both files with the same wrong enum names and parameter order (shard 47191–47260).

**Test run 2 (failure log 18099–18426, shard 47370–47692): compile failure.** Every test's `expected{...}` line errors on the enumerator spellings, e.g.:

> `47469: /aider/kindergarten-garden/kindergarten_garden_test.cpp:53:197: error: ‘grass’ is not a member of ‘kindergarten_garden::Plants’; did you mean ‘Grass’?`
> (failure log 18201)

Identical `did you mean` errors for `clover`/`radishes`/`violets` at test lines 53, 58, 63, 68, 73, 78, 83, 88, 93, 98 (failure log 18183–18357), ending `make: *** [Makefile:91: all] Error 2` (shard 47628) and `Tests failed: ... kindergarten-garden` (shard 47631, failure log 18363). Attempt 2 FAIL. (Because compilation failed, the latent bugs — swapped parameter order, 4-per-row indexing, `return {}` for unknown students — were never even exercised.)

### Hard evidence vs. inference

Hard evidence: diff-fence outputs (shard 5491, 5514, 10966, 27150, 32557, 40216); invented `Garden` class with `std::vector<std::string>` (shard 5501–5504, 5523); empty-diff retries (shard 15790–15798, 20050–20060, 32557–32559); test-run-1 errors `'Plants' is not a member` / `'plants' is not a member` (shard 20122, 20150); capitalized-singular enum (shard 27165–27170, 47199–47204); test-run-2 errors `'grass' is not a member ... did you mean 'Grass'` (shard 47469 and siblings); both outcomes false (failure log 18371–18374).

Inference (root-cause categories): (a) the model defaulted to a generic "parser class returning display strings" design instead of discovering the enum + free-function API the C++ tests enforce; (b) it treated the `# Fix any errors below` reflection prompts as requests to confirm correctness, so 5 of 8 turns changed nothing; (c) when it did add the enum, it trusted its own naming intuition (`Grass`) over the exact spelling the compiler error context made recoverable — the test-file line quoted in the error output (`did you mean 'Grass'`-style messages appear only after the fact, but the attempt-2 prompt already showed `CATCH_REGISTER_ENUM(...Plants::clover, ...)` in the compiler output at shard 20123–20128, which named the correct spellings); (d) it never re-checked parameter order against the test call `plants("RC\nGG", "Alice")` visible in the same compiler output (shard 20150–20151).

## 4. Knowledge / Capability Gaps

- **G1 — Format-contract discipline (whole-file listings).** Every substantive answer and every no-op used ```` ```diff ```` fences despite the whole-file mandate (shard 5491, 5514, 10966–10968, 27150, 32557, 40216 vs. failure log 16427–16449). Empty diff blocks were also emitted as "answers" (shard 32557–32559).
- **G2 — API-shape discovery from test-call conventions.** Attempt 1 invented `class Garden { static std::vector<std::string> plants(...) }` (shard 5501–5504) when the enforcing tests call the free function `kindergarten_garden::plants("RC\nGG", "Alice")` returning `std::array<kindergarten_garden::Plants, 4>` (`kindergarten_garden_test.cpp:16-17`; `.meta/example.h:8-11`). The model needed a compile failure to discover each API element — and recovered them one per attempt (enum in attempt 2 turn 1, free function in attempt 2 turn 3).
- **G3 — Enum contract fidelity: exact enumerator names and underlying values.** The contract pins `grass/clover/radishes/violets` with `char` values (`.meta/example.h:8`); the model shipped `Grass/Clover/Radish/Violet` with no values (shard 27165–27170) and never corrected it, even though the attempt-2 prompt's quoted compiler output displayed the correct lowercase spellings from `CATCH_REGISTER_ENUM` (shard 20123–20128). Test run 2 is a pure G3 failure (`did you mean 'Grass'`, shard 47469).
- **G4 — Repair/retry behavior on vague marked-line prompts.** 5 of 8 turns were empty diffs or "code is correct" confirmations (shard 15790–15798, 20050–20060, 32557–32559, 47191's confirm-only response), burning all 3 reflections in both attempts (`Only 3 reflections allowed, stopping.`, shard 20080, 47190) at costs up to 22k sent / 3.8k received for a no-op (shard 32562).
- **G5 — Signature fidelity beyond names: parameter order and fixed-size return types.** The model kept `plants(const std::string& student, const std::string& diagram)` (shard 40229–40231) while the contract is `plants(std::string_view diagram, std::string_view student)` (`.meta/example.h:10-11`), despite the test call `plants("RC\nGG", "Alice")` (diagram first) being visible in quoted compiler output (shard 20150–20151). Also `const std::string&` vs `std::string_view`, and `std::vector` vs `std::array<..., 4>` in attempt 1.
- **G6 — Word-problem indexing semantics.** "Two on each row" became `student_index * 4` with a hardcoded `48`-plant row stride (shard 5547–5549) instead of `2 * index` and `find('\n')` (`.meta/example.cpp:12-13`). Never tested (compile failures masked it), but wrong in every emitted version including the final one (shard 47248–47255).

## 5. SFT Task Specifications (26 specs)

Answer-blind: no benchmark test fixtures, diagram strings, or reference code are copied. Every spec lists an exact API the dataset author designs; stories are new. (The contract has no exception policy, so the "≥2 exception-policy" requirement does not apply; one exception-flavored spec is included anyway as G3/G5 reinforcement.)

### Spec 01: whole-file-ferry-manifest
- Files: `ferry_manifest.cpp`, `ferry_manifest.h` (test file: `ferry_manifest_test.cpp`)
- API: namespace `ferry`; `int total_vehicles(const std::vector<int>& deck_counts);` and `bool has_capacity(int vehicles, int limit);` — no exceptions.
- Prompt shape: ferry-loading story; starters contain only the empty namespace; system prompt demands whole-file listings.
- Target capability: G1 — return two complete file listings (filename line, fence, entire file), no diff hunks, no prose between filename and fence.
- Target answer shape: two whole-file listings; header with `#pragma once` + declarations; cpp with definitions; `<vector>` in header.
- Difficulty / variation: foundational; trivial logic, all grading weight on format.

### Spec 02: whole-file-observatory-log
- Files: `observatory_log.cpp`, `observatory_log.h` (test file: `observatory_log_test.cpp`)
- API: namespace `observatory`; `double median_magnitude(std::vector<double> readings);` — no exceptions.
- Prompt shape: telescope observation story; the user message repeats the whole-file rule twice, and both starters begin with a plausible-but-wrong body to be replaced wholesale.
- Target capability: G1 — resist ```` ```diff ```` even when the pre-existing file makes "fix" feel diff-shaped.
- Target answer shape: whole files; sort + midpoint logic; `<algorithm>` include.
- Difficulty / variation: replacement (not extension) of starter content.

### Spec 03: format-no-empty-answer
- Files: `canal_lock.cpp`, `canal_lock.h` (test file: `canal_lock_test.cpp`)
- API: namespace `canal`; `class lock_state { public: lock_state(); void open_gate(); void close_gate(); bool is_open() const; private: bool open_; };`
- Prompt shape: canal-lock story with a mid-size cpp (~50 lines) to tempt elision or empty confirmation.
- Target capability: G1 — a "confirmation" turn must still emit whole files; `...`, `// unchanged`, and empty fences are all forbidden.
- Target answer shape: full listings of both files, every line present.
- Difficulty / variation: length + "nothing to change" pressure on format discipline.

### Spec 04: header-impl-apiary-registry
- Files: `apiary_registry.cpp`, `apiary_registry.h` (test file: `apiary_registry_test.cpp`)
- API: namespace `apiary`; `class hive { public: explicit hive(int capacity); int capacity() const; int bees() const; void add_bees(int n); private: int capacity_; int bees_; };`
- Prompt shape: beekeeping story; starters have empty namespaces.
- Target capability: G2 — class declaration in header, all definitions out-of-line in cpp, member-init lists, const-correct accessors.
- Target answer shape: header declares only; cpp defines `hive::hive(...)`, `hive::bees()`, etc.; no bodies in the header.
- Difficulty / variation: mutable state with one void method.

### Spec 05: header-impl-tide-gauge
- Files: `tide_gauge.cpp`, `tide_gauge.h` (test file: `tide_gauge_test.cpp`)
- API: namespace `tide`; `double high_tide(const std::vector<double>& levels);` and `double low_tide(const std::vector<double>& levels);`
- Prompt shape: coastal tide-gauge story; starter header uses `#pragma once` (to be preserved), starter cpp already includes `<vector>` (to be moved/kept correctly).
- Target capability: G2 — include hygiene: header includes only what declarations need; cpp includes what definitions need; free functions defined out-of-line.
- Target answer shape: two listings with correct include placement.
- Difficulty / variation: free functions rather than a class; include-placement is the graded skill.

### Spec 06: enum-contract-orchard-crates
- Files: `orchard_crates.cpp`, `orchard_crates.h` (test file: `orchard_crates_test.cpp`)
- API: namespace `orchard`; `enum class Fruit : char { apples = 'A', pears = 'P', cherries = 'C', plums = 'L' };` plus `int count(const std::vector<Fruit>& crate, Fruit kind);`
- Prompt shape: orchard crate-labeling story; prose says "the label letters are A, P, C, L" but never spells the enumerator identifiers.
- Target capability: G3 — declare a scoped enum with an explicit `char` underlying type and exact lowercase plural enumerator names bound to the label letters; naming must follow the prompt's convention, not the model's default (`Apple`).
- Target answer shape: header with the exact enum line; cpp with the counting loop; no string mapping anywhere.
- Difficulty / variation: direct analog of the failed enum contract, new domain; answer reviewed for exact spellings.

### Spec 07: enum-contract-rail-signals
- Files: `rail_signals.cpp`, `rail_signals.h` (test file: `rail_signals_test.cpp`)
- API: namespace `signals`; `enum class Aspect : char { red = 'R', amber = 'A', green = 'G' };` plus `Aspect from_char(char c);` (behavior on unknown char: return `Aspect::red`, documented in prose — no throw).
- Prompt shape: railway signal-aspect story; a second-turn variant shows a compiler error `'green' is not a member of 'signals::Aspect'; did you mean 'Green'?` when the scripted first answer used `Green`.
- Target capability: G3 — read a `did you mean` compiler error as "my enumerator spelling is wrong" and fix the **declaration**, not the test's expectation.
- Target answer shape: corrected enum declaration with lowercase enumerators, whole header re-emitted.
- Difficulty / variation: exact repair the model failed to perform in attempt 2.

### Spec 08: enum-from-char-static-cast
- Files: `mineral_assay.cpp`, `mineral_assay.h` (test file: `mineral_assay_test.cpp`)
- API: namespace `assay`; `enum class Mineral : char { quartz = 'Q', mica = 'M', feldspar = 'F' };` plus `std::array<Mineral, 3> classify(std::string_view codes);` (input guaranteed to be exactly 3 valid codes).
- Prompt shape: geology assay story.
- Target capability: G3 — exploit char-valued enumerators: convert with `static_cast<Mineral>(c)` instead of writing a switch/map.
- Target answer shape: `std::transform` (or loop) with `static_cast`; `<array>`, `<string_view>`, `<algorithm>` includes placed correctly.
- Difficulty / variation: teaches the idiomatic conversion the reference uses without copying it.

### Spec 09: enum-vs-strings-contrast
- Files: `laundry_tags.cpp`, `laundry_tags.h` (test file: `laundry_tags_test.cpp`)
- API: namespace `laundry`; `enum class Care : char { wash = 'W', dry = 'D', iron = 'I' };` plus `std::array<Care, 2> decode(std::string_view tag);`
- Prompt shape: contrastive row. Candidate A returns `std::vector<std::string>` of care-instruction words; candidate B returns `std::array<Care, 2>`. The prompt's calling convention shows `laundry::decode("WI")` compared against `Care` arrays.
- Target capability: G2+G3 — recognize that a typed-enum return beats display strings when the consumer is typed code, not a human.
- Target answer shape: annotated A/B pair; B is the target, with a one-line rationale.
- Difficulty / variation: contrastive spec (required mix), repairs the attempt-1 `vector<string>` design.

### Spec 10: free-function-vs-class-aviary
- Files: `aviary_counts.cpp`, `aviary_counts.h` (test file: `aviary_counts_test.cpp`)
- API: namespace `aviary`; `int birds_in_row(std::string_view chart, int row);` — free function, no class.
- Prompt shape: aviary seating-chart story; prompt states "other code calls `aviary::birds_in_row(chart, 2)`".
- Target capability: G2 — when the stated calling convention is a namespace-qualified free function, do not wrap it in a class or make it static.
- Target answer shape: free function declared in header, defined in cpp; no class anywhere.
- Difficulty / variation: pure API-shape judgment, trivial logic.

### Spec 11: api-discovery-from-compiler-error
- Files: `bakery_orders.cpp`, `bakery_orders.h` (test file: `bakery_orders_test.cpp`)
- API: namespace `bakery`; `enum class Pastry : char { tarts = 'T', scones = 'S' };` plus `std::array<Pastry, 2> order(std::string_view slip);`
- Prompt shape: two-turn. Turn 1 scripted wrong answer: `class Oven { public: static std::vector<std::string> order(...); };`. Turn 2 shows compiler errors `'Pastry' is not a member of 'bakery'` and `'order' is not a member of 'bakery'` pointing at the test's call line.
- Target capability: G2 — recover the **entire** API (enum with exact names + free function + array return) from compiler error text in one repair turn, not one element per attempt.
- Target answer shape: second turn emits both whole files with the full correct API.
- Difficulty / variation: compresses this task's two-attempt recovery into one turn.

### Spec 12: signature-param-order-carpark
- Files: `carpark_layout.cpp`, `carpark_layout.h` (test file: `carpark_layout_test.cpp`)
- API: namespace `carpark`; `std::array<char, 2> slots(std::string_view map, std::string_view driver);`
- Prompt shape: car-park allocation story; prose example call written as `slots("AB\nCD", "Dan")` — data argument first, selector second.
- Target capability: G5 — fix parameter **order** from the example call, not from what "reads naturally"; keep `std::string_view` for read-only string params.
- Target answer shape: exact signature in both declaration and definition; body indexes the map by driver.
- Difficulty / variation: isolates argument order; logic is two lookups.

### Spec 13: signature-stringview-array-fidelity
- Files: `vineyard_rows.cpp`, `vineyard_rows.h` (test file: `vineyard_rows_test.cpp`)
- API: namespace `vineyard`; `std::array<int, 4> grape_counts(std::string_view row_a, std::string_view row_b);`
- Prompt shape: vineyard harvest story; scripted first answer uses `const std::string&` and `std::vector<int>`; second turn demands exact signature match.
- Target capability: G5 — signature-fidelity drill: `std::string_view` by value, `std::array<T, N>` fixed return, identical qualifiers in header and cpp.
- Target answer shape: corrected whole files; no `std::string`, no `std::vector` in the interface.
- Difficulty / variation: type-vocabulary precision rather than naming.

### Spec 14: edge-two-per-group-indexing
- Files: `aquarium_wall.cpp`, `aquarium_wall.h` (test file: `aquarium_wall_test.cpp`)
- API: namespace `aquarium`; `std::array<char, 4> tanks_for(std::string_view chart, int visitor_index);` — chart has two `\n`-separated rows; each visitor owns **two** adjacent tanks per row.
- Prompt shape: aquarium-wall story; prose stresses "two tanks on each row".
- Target capability: G6 — translate "two per row" into `2 * index` offsets and locate the second row via `find('\n') + 1`, never a hardcoded stride.
- Target answer shape: offset math `2 * visitor_index`, `row2 = chart.find('\n') + 1 + 2 * visitor_index`.
- Difficulty / variation: direct repair of the `* 4` / `48`-stride bug, new story.

### Spec 15: edge-selector-from-name-letter
- Files: `choir_seats.cpp`, `choir_seats.h` (test file: `choir_seats_test.cpp`)
- API: namespace `choir`; `int seat_number(std::string_view name);` — seat index derives from the first letter of the singer's first name (`name.at(0) - 'A'`), names guaranteed to start with A–L.
- Prompt shape: choir seating story; prose explains the alphabetical rule with a 12-name roster.
- Target capability: G6 — derive an index from `name.at(0) - 'A'` when the roster is fixed and alphabetical, instead of building and searching a name table.
- Target answer shape: one-line index derivation; documented assumption comment optional.
- Difficulty / variation: teaches the reference's index trick abstractly.

### Spec 16: edge-newline-delimited-rows
- Files: `greenhouse_beds.cpp`, `greenhouse_beds.h` (test file: `greenhouse_beds_test.cpp`)
- API: namespace `greenhouse`; `std::array<char, 2> bed_pair(std::string_view layout, int column);` — layout is two rows joined by `'\n'`; rows may have **different lengths**, so a fixed stride is wrong.
- Prompt shape: greenhouse layout story; hidden tests use unequal row lengths.
- Target capability: G6 — row separation must come from `find('\n')`, robust to unequal rows; a hardcoded stride silently passes equal-row examples and fails hidden ones.
- Target answer shape: `find`-based indexing with bounds documented.
- Difficulty / variation: adversarial to the hardcoded-48 pattern.

### Spec 17: edge-first-vs-second-row-order
- Files: `market_stalls.cpp`, `market_stalls.h` (test file: `market_stalls_test.cpp`)
- API: namespace `market`; `std::array<char, 4> goods(std::string_view board, int stall);` — result order is row 1 pair **then** row 2 pair; prose example makes the order observable.
- Prompt shape: market-stall board story.
- Target capability: G6 — result element ordering across rows: [r1c1, r1c2, r2c1, r2c2], not interleaved and not reversed.
- Target answer shape: four indexed assignments in the documented order.
- Difficulty / variation: ordering edge; sibling of Spec 14 with emphasis on output order.

### Spec 18: edge-unknown-selector-policy
- Files: `hostel_bunks.cpp`, `hostel_bunks.h` (test file: `hostel_bunks_test.cpp`)
- API: namespace `hostel`; `int bunk_of(std::string_view guest);` — guests outside the documented roster are **out of contract**; prose says inputs are always roster members.
- Prompt shape: hostel bunk story; contrastive sub-answers: one adds a `return -1` fallback, one trusts the contract.
- Target capability: G6+G5 — don't invent defensive behavior (empty returns, sentinel values) for inputs the contract excludes; match the stated precondition.
- Target answer shape: implementation without dead fallback branches; rationale line citing the precondition.
- Difficulty / variation: counters the model's `return {}` for unknown students.

### Spec 19: repair-marked-line-enum-spelling
- Files: `dojo_belts.cpp`, `dojo_belts.h` (test file: `dojo_belts_test.cpp`)
- API: namespace `dojo`; `enum class Belt : char { white = 'W', brown = 'B', black = 'K' };` plus `Belt from_tag(char tag);`
- Prompt shape: two-turn. Turn 1 scripted answer declares `enum class Belt { White, Brown, Black };`. Turn 2 is `# Fix any errors below, if possible.` with the enum lines █-marked, no compiler text.
- Target capability: G4+G3 — on a vague marked-line prompt, treat the marking as "this declaration is wrong", audit it against the prompt's naming convention, and emit a corrected whole file — never an empty diff.
- Target answer shape: whole header with lowercase enumerators + `char` values; brief note.
- Difficulty / variation: teaches marked-line → declaration-audit inference.

### Spec 20: repair-never-empty-diff
- Files: `tram_timetable.cpp`, `tram_timetable.h` (test file: `tram_timetable_test.cpp`)
- API: namespace `tram`; `int next_departure(int now_minutes, int headway);`
- Prompt shape: two-turn. Turn 1 answer is correct except one wrong constant. Turn 2: `# Fix any errors below, if possible.` marking the constant's line.
- Target capability: G4 — a repair turn must always produce substantive whole-file output; empty ```` ```diff ```` blocks are never acceptable.
- Target answer shape: whole cpp re-emitted with the constant fixed.
- Difficulty / variation: smallest possible repair; graded on non-empty output.

### Spec 21: repair-stale-confirm-trap
- Files: `harbor_signals.cpp`, `harbor_signals.h` (test file: `harbor_signals_test.cpp`)
- API: namespace `harbor`; `char flag_for(int vessel_class);`
- Prompt shape: two-turn. Turn 1 answer is already correct. Turn 2 shows a marked-line snippet of a **stale** header plus "Trust this message as the true contents of these files!" with the correct current files.
- Target capability: G4 — when nothing is wrong, restate the correct files whole (per format contract) instead of either emitting empty diffs or inventing a fix; do not ruminate for thousands of tokens.
- Target answer shape: one-sentence confirmation + both whole files, identical in API to turn 1.
- Difficulty / variation: targets the 22k-sent/3.8k-received no-op turn.

### Spec 22: contrastive-diff-vs-whole-file
- Files: `glacier_cores.cpp`, `glacier_cores.h` (test file: `glacier_cores_test.cpp`)
- API: namespace `glacier`; `double mean_depth(const std::vector<double>& cores);`
- Prompt shape: contrastive format row: candidate A answers with ```` ```diff ```` hunks, candidate B with whole-file listings, under a prompt demanding whole files.
- Target capability: G1 — format-level contrast: even when a diff would apply cleanly, the contract requires whole files; B is the target.
- Target answer shape: annotated A/B pair; target is B verbatim.
- Difficulty / variation: isolates format compliance from algorithmic content.

### Spec 23: enum-discovery-from-register-macro
- Files: `botany_plots.cpp`, `botany_plots.h` (test file: `botany_plots_test.cpp`)
- API: namespace `botany`; `enum class Herb : char { thyme = 'T', sage = 'S', mint = 'M' };` plus `std::array<Herb, 2> plot(std::string_view row, int offset);`
- Prompt shape: two-turn. Turn 1 scripted wrong answer omits the enum. Turn 2's compiler output quotes the consumer's registration line `CATCH_REGISTER_ENUM(botany::Herb, botany::Herb::sage, botany::Herb::mint, ...)` inside the error text.
- Target capability: G3 — mine the **exact enumerator spellings** from quoted consumer code in compiler output instead of inventing names.
- Target answer shape: second-turn whole header whose enum matches the quoted spellings exactly.
- Difficulty / variation: exact recovery skill attempt 2 lacked (shard 20123–20128 showed the spellings; the model still guessed).

### Spec 24: api-no-superfluous-throw
- Files: `census_wards.cpp`, `census_wards.h` (test file: `census_wards_test.cpp`)
- API: namespace `census`; `char ward_code(std::string_view record, int position);` — contract guarantees valid records; no throwing behavior specified.
- Prompt shape: census record story; contrastive sub-answers: one adds `throw std::invalid_argument` on an impossible branch, one omits it.
- Target capability: G5 — don't invent an exception policy the contract doesn't have; match specified behavior exactly (the model added an unrequested `std::invalid_argument` in attempt 2).
- Target answer shape: implementation without throw sites; rationale line.
- Difficulty / variation: exception-policy restraint (contract here is explicitly throw-free).

### Spec 25: multi-error-single-repair
- Files: `ski_jump_scores.cpp`, `ski_jump_scores.h` (test file: `ski_jump_scores_test.cpp`)
- API: namespace `skijump`; `enum class Style : char { aerial = 'A', mogul = 'M' };` plus `std::array<Style, 2> styles(std::string_view card, std::string_view judge);`
- Prompt shape: two-turn. Turn 1 scripted answer has **three** simultaneous contract violations (class-wrapped function, swapped params, wrong enum names). Turn 2 shows all corresponding compiler errors at once.
- Target capability: G2+G3+G5 — fix every reported contract violation in one pass; partial fixes that leave one violation for the next attempt are the failure mode being trained away.
- Target answer shape: whole files with all three violations corrected simultaneously.
- Difficulty / variation: capstone repair; mirrors this task's drip-feed recovery across two attempts.

### Spec 26: diagram-indexing-capstone
- Files: `terrarium_grid.cpp`, `terrarium_grid.h` (test file: `terrarium_grid_test.cpp`)
- API: namespace `terrarium`; `enum class Creature : char { ants = 'A', beetles = 'B', worms = 'W' };` plus `std::array<Creature, 4> creatures(std::string_view grid, std::string_view keeper);` — two `\n`-separated rows, each keeper (identified by first letter, roster A–F) owns two cells per row.
- Prompt shape: terrarium story combining every element: enum with char values, free function, `string_view`, array return, first-letter indexing, two-per-row, `find('\n')` row split.
- Target capability: G2+G3+G5+G6 — integration capstone; single-turn, graded on all contract elements at once.
- Target answer shape: both whole files, exact API, `2 * index` offsets, `find`-based row 2, `static_cast<Creature>` conversion.
- Difficulty / variation: full-analog difficulty; distinct story from the benchmark task.

Gap coverage: G1 → Specs 01, 02, 03, 22. G2 → Specs 04, 05, 09, 10, 11, 25, 26. G3 → Specs 06, 07, 08, 09, 19, 23, 25, 26. G4 → Specs 19, 20, 21. G5 → Specs 12, 13, 18, 24, 25, 26. G6 → Specs 14, 15, 16, 17, 18, 26. Required mix: format-contract ≥2 (01, 02, 03, 22); header/impl separation ≥2 (04, 05); exception-policy — contract has none (not required; restraint drill at 24); edge cases ≥3 (14, 15, 16, 17, 18); repair/retry ≥2 (19, 20, 21, 23, 25); contrastive ≥1 (09, 22). No two specs share a story wrapper.

## 6. Acceptance & Validation Gates

For every row built from the specs above, before inclusion in SFT:

1. **Parser validity:** the target response must parse under the Aider whole-file listing format — bare filename line, opening fence, entire file, closing fence; zero diff hunks, zero elisions (grep for `^```diff`, `+ `/`- ` hunk lines, `...` placeholders, `rest of`, `unchanged`).
2. **Compile + test receipt:** apply the target files to a scratch copy of the spec's exercise, build with the project's CMake/Catch2 harness, and require 100% test pass; store the build log hash as the receipt.
3. **Exact-identifier gate:** a script compares every enum enumerator, function name, namespace, and parameter order in the target answer against the spec's API bullet character-for-character — this failure was purely a spelling/`did-you-mean` mismatch, so fuzzy review is not enough.
4. **Hidden-edge coverage:** each spec's test file must include the edge cases named in its API bullet (unequal row lengths, non-zero student offsets, ordering across rows) and at least one case not shown as a prose example, to prevent example memorization.
5. **Repair-turn realism:** for two-turn specs (07, 11, 19, 20, 21, 23, 25), the scripted first answer must be a plausible compilable-or-nearly-compilable wrong answer of the observed type (class-instead-of-free-function, wrong enum spellings, swapped params), and the second-turn prompt must mirror the real harness (`# Fix any errors below, if possible.` + █-marked snippet, or quoted compiler text).
6. **No-empty-answer gate:** target responses to repair turns must re-emit **all** editable files in full; empty fences or confirm-only answers are rejected outright.
7. **Contamination check:** diff every spec's story, test inputs, and expected outputs against `polyglot-benchmark/cpp/exercises/practice/kindergarten-garden/`; no shared diagram strings, no child-name roster, no plant enum names, no copied reference code. APIs must differ in names even when capabilities overlap.
8. **No-rumination guard:** target responses must be under a length cap (≤2× the byte size of the emitted files) and contain no repeated sentence ≥3 times — counters the 12k/22k-token no-op turns.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the shard-0 benchmark log, and the ground-truth files:

- **Outcome array / shard:** re-read failure log lines 16419–16424: `### kindergarten-garden`, `- Shard: `0``, `- Test outcomes: `[False, False]``, `- Result: `FAIL`` — matches section 1. The result JSON `"tests_outcomes": [false, false]` re-verified at failure log 18371–18374 (shard 47639–47642); `"edit_format": "whole"` at failure log 18370, `"num_user_asks": 8` at 18380.
- **Log citations re-read:** every quoted line was re-fetched with `sed` and confirmed verbatim: failure log 17185–17187 (shard 5477–5478 "defined a `Garden` class"), 17211–17213 (shard 5501–5503 `+class Garden` / `static std::vector<std::string> plants`), 17290 (chunk 2 header), 18099 (`Source lines 47370-47692:`), 18201 (shard 47469 `'grass' is not a member ... did you mean 'Grass'`), 18358–18363 (`make` errors + `Tests failed`). Shard-log-only citations confirmed: 5530–5535 (plant_map strings), 5547–5549 (`start_index = student_index * 4`, `row_1_start = 48 + start_index`), 5573–5576 (applied edits + first reflection prompt), 10966–10968 (empty diff turn for the newline "fix"), 15790–15798 (empty-diff no-op, 12k received), 20050–20060 (second empty-diff no-op), 20080 (`Only 3 reflections allowed`), 20081–20107 (attempt-1 final header), 20122/20150 (test-run-1 errors), 20123–20128 (`CATCH_REGISTER_ENUM` spellings visible in quoted error output), 20150–20151 (`plants("RC\nGG", "Alice")` call visible), 27165–27170 (`enum class Plants { Grass, Clover, Radish, Violet`), 27264–27265 (applied), 32557–32562 (empty diff, 22k/3.8k), 40208–40231 (free-function move, still `(student, diagram)`), 40264–40265 (applied), 47190–47260 (reflection stop + final whole-file response with `Grass`/`Clover`/`Radish`/`Violet` and `start_index = student_index * 4` at 47248–47255), 47469 (test-run-2 `did you mean 'Grass'`). Line numbers corrected during this re-read are listed under "Corrections" below; all quotes matched verbatim.
- **API claims re-checked:** `.meta/example.h:1,3-4,8,10-11` (pragma once; `<array>`/`<string_view>`; `enum class Plants : char { grass = 'G', clover = 'C', radishes = 'R', violets = 'V' };`; `std::array<Plants, 4> plants(std::string_view diagram, std::string_view student);`) and `.meta/example.cpp:12-13,20-21` (`2 * (student.at(0) - 'A')`, `find('\n')`, `static_cast<Plants>(c)`) re-read and match section 2. Test-file citations re-read: `kindergarten_garden_test.cpp:9-14` (CATCH_REGISTER_ENUM with lowercase plural spellings), `:16-17` (free-function call, diagram first, `std::array` equality), `:19` (`EXERCISM_RUN_ALL_TESTS` gate). Confirmed the contract has no exception policy; section 2 says so and the spec mix requirement was adjusted accordingly (noted in section 5).
- **Corrections made during cross-check:** four. (1) An earlier draft said the attempt-2 prompt "never showed" the correct enum spellings; re-reading shard 20123–20128 showed the `CATCH_REGISTER_ENUM` line with `clover, grass, violets, radishes` **was** present in the quoted compiler output of attempt 2's prompt — section 4 G3 and Spec 23 were rewritten to reflect that the model had the spellings available and still guessed. (2) Several failure-log line citations were off by 1–9 lines and were corrected to the re-read values: the attempt-1 answer quote (17210–17212 → 17211–17213), the shard-47469 error (18200 → 18201), the result-JSON fields (18362–18421/18366/18367–18370/18376 → 18365–18424/18370/18371–18374/18380), the `make`/`Tests failed` range (18357–18360 → 18358–18363), the `start_index` shard range (5549–5551 → 5547–5549), and the visible test call (shard 20131 → 20150–20151). (3) The attempt-2 turn-2 thinking quote (shard ~32331 "outside the class") was re-verified and its line number kept approximate since only the region (32220–32564) was excerpted, not the exact line. (4) The result-JSON line numbers in section 1 were aligned with the same re-read.
- **Ground-truth status:** `.meta/example.h`, `.meta/example.cpp`, and `kindergarten_garden_test.cpp` all present and mutually consistent; no ground-truth problem encountered.
