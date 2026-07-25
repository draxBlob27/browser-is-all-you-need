# clock — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `clock`
- Shard: `0` (failure log section header, line 7477: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 7479; terminal JSON `tests_outcomes: [false, false]`, failure log lines 8841-8844 / raw shard-0 lines 62735-62738)
- Result: `FAIL` (failure log line 7480)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **7475-8896**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log` (clock run spans source lines ~4347-62788; interleaved with concurrent tasks; `num_exhausted_context_windows: 1`)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/clock/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/clock/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/clock/clock_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Chunk-1 bleed-over.** "Attempt/log chunk 1, source lines 3762-4356" (failure log 7525-8124) is foreign-task material (a bank-account empty-diff answer at failure log 7906, source 4140; dnd-character FAILED assertions at failure log 7985-8072). The clock run's `fnames:` marker is at failure log 8113 (source 4347); clock content begins in chunk 2 (failure log 8125+, source 5596+).
2. **Terminal excerpt truncation.** The failure log's terminal block (failure log 8567-8896, source 62466-62788) starts mid-error-stream: it contains only the `operator!=` candidate-note cascade. The earlier `basic_string(clock)` conversion errors (raw shard-0 61274-61470) are NOT in the failure log and are cited as "shard-0" lines.
3. **Citation scheme.** Failure-log lines carry the log's raw-shard source-line prefixes; raw shard-0 lines are labeled "shard-0".

## 2. Benchmark Contract (Ground Truth)

File set: `clock.h` + `clock.cpp`, namespace `date_independent`.

Public API (from `.meta/example.h`, enforced by `clock_test.cpp`):

- `class clock` — lowercase name (example.h:9). The test calls `date_independent::clock::at(...)` (clock_test.cpp:183, 194, 204-205).
- `static clock at(int hour, int minute = 0);` — static factory; the two-arg constructor is **private** (example.h:12, 22).
- `clock& plus(int minutes);` / `clock& minus(int minutes);` — mutate and return **reference to self** (example.h:14-15). Test chains: `string(date_independent::clock::at(a.hour, a.minute).plus(a.add))` (clock_test.cpp:194).
- `operator std::string() const;` — **implicit conversion operator**, not a named `time()`/`to_string()` method (example.h:17; implemented with `setw(2) << setfill('0')` zero-padding, example.cpp:32-37). Enforced by `const auto actual = string(date_independent::clock::at(t.hour, t.minute));` (clock_test.cpp:183) — direct `std::string` construction from `clock`.
- `bool operator==(const clock& rhs) const;` (example.h:19) AND a free `inline bool operator!=(const clock& lhs, const clock& rhs)` (example.h:28-31). Both are exercised: `REQUIRE(clock1 == clock2);` (clock_test.cpp:209) and `REQUIRE(clock1 != clock2);` (clock_test.cpp:213).

Exception policy: none.

Arithmetic semantics: 24-hour wraparound in both directions (negative minutes/hours normalize, example.cpp:46-58); equality compares normalized hour/minute (example.cpp:65-69). String format is exactly `HH:MM` zero-padded (example.cpp:35).

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: invented API, wrong case, named time method)

**What the model emitted.** A **diff-hunk answer** (failure log 8444-8539, source 5912-6007): `class Clock` (PascalCase) with a **public** `Clock(int hour, int minute)`, `Clock add(int minutes)` / `Clock subtract(int minutes)` (by value), `std::string time()`, `bool operator==`, private `int minutes_since_midnight; void normalize();` (failure log 8469-8480, source 5937-5948). Mangled guard hunk `-#endif // CLOCK_H+private:` (failure log 8477, source 5945). The `time()` implementation prints **unpadded** components — `ss << hour << ":" << minute;` (failure log 8516-8521, source 5984-5989) — which would render "8:7" instead of "08:07" (latent runtime failure even had it compiled). Applied (failure log 8538-8539, source 6006-6007).

Every contract element was invented differently: wrong class case (`Clock` vs `clock`), public ctor instead of private + `static at`, `add`/`subtract` instead of `plus`/`minus`, named `time()` instead of `operator std::string()`, no `operator!=`.

**Reflection turns.** Three `# Fix any errors below` █ prompts produced no-op applies (shard-0 8250-8251, 9429-9430, 11832-11833; "Only 3 reflections allowed, stopping." shard-0 11857).

**Test run 1 — compile failure** (shard-0 ~11900-11975): `error: 'clock' is not a member of 'date_independent'; did you mean 'Clock'?` at `string(date_independent::clock::at(t.hour, t.minute))` (shard-0 11901-11904, quoting clock_test.cpp:183; likewise test:194, 204-205), ending `Tests failed: .../clock` (shard-0 11975).

### Attempt 2 (retry with compiler output) — outcome False (compile failure: conversion operator and `operator!=` never added)

**What the retry changed.** The model renamed the class to lowercase `clock` and adopted the factory shape — the header state quoted in its own later thinking shows `class clock { public: static clock at(int hour, int minute); clock plus(int minutes); clock minus(int minutes); std::string time(); bool operator==(const clock& other) const; ... }` (shard-0 30600-30616) — but kept `std::string time()` instead of `operator std::string()`, kept by-value `plus`/`minus` returns, and never added `operator!=`.

**Reflection churn.** Later signal-free █ turns circled: "the code provided ... is syntactically correct ... Is it possible the `clock` class name is conflicting with `std::clock`? It's in a namespace `date_independent`, so it's fine." (shard-0 30639-30646) and "If I cannot find an error, I will output the files again" (shard-0 30663-30664); another turn noticed the OLD error was "'clock' is not a member ... which was a real error. This time, the lines..." carry no new signal (shard-0 53475-53535). The run burned one full context window (`num_exhausted_context_windows: 1`, failure log 8851, source 62745).

**Terminal result — compile failure, two defect families** (raw shard-0 61274-62727; failure log 8567-8896, source 62466-62788):

1. Missing conversion operator: `error: no matching function for call to 'std::__cxx11::basic_string<char>::basic_string(date_independent::clock)'` at test:183, and the same at test:194 (`.plus(...)` result) and test:208 (shard-0 61274-61317, 61377-61409, 61470).
2. Missing `operator!=`: `error: no match for 'operator!=' (operand types are 'const date_independent::clock' and 'const date_independent::clock')` at `REQUIRE(clock1 != clock2);` test:213 (failure log 8825-8831, source 62719-62725; the candidate-note cascade fills failure log 8569-8824).

`Tests failed: .../clock` (failure log 8833, source 62727); JSON `tests_outcomes: [false, false]` (failure log 8841-8844).

### Hard evidence vs inference

- Hard evidence: invented attempt-1 API (failure log 8469-8480), unpadded `time()` (failure log 8516-8521), attempt-1 `'clock' is not a member` errors (shard-0 11901-11904), attempt-2 header retaining `time()` (shard-0 30600-30616), terminal conversion-operator errors (shard-0 61274-61470), terminal `operator!=` error (failure log 8825), reflection churn quotes (shard-0 30639-30664).
- Inference: attempt 1 is wholesale API invention (the model designed "a Clock class" rather than the exercism-cpp `date_independent::clock` value type). Attempt 2 demonstrates the recurring pattern: compiler-nameable defects (class case, factory shape) get fixed, while defects the compiler can't name yet (conversion operator, `operator!=`) are never inferred from the test usage quoted in error output — even though attempt-1's errors quoted `string(date_independent::clock::at(...))` verbatim, which a careful reader can decode as "needs `operator std::string`". The model also never supplies `!=` from `==` — the C++17 idiom of defining one in terms of the other (as the reference does inline, example.h:28-31) is missing from its toolbox. Latent even if compiled: the unpadded `ss << hour << ":" << minute` formatting would fail every string-format assertion.

## 4. Knowledge / Capability Gaps

- **G1 — Canonical value-type API shape.** Lowercase `clock`, private ctor + `static at` factory, `plus`/`minus` returning `clock&` (contract: example.h:9-22; invented as `Clock`/public ctor/`add`/`subtract` at failure log 8469-8480; compile cost at shard-0 11901-11904).
- **G2 — Conversion operators.** `operator std::string() const` is the required surface for `string(clock_value)`; a named `time()` method is invisible to that call syntax (shard-0 30600-30616 kept `time()`; terminal error shard-0 61274-61317). The model appears not to know user-defined conversion operators as a design option.
- **G3 — Zero-padded formatting.** `setw(2) << setfill('0')` via `<iomanip>` (example.cpp:32-37) vs the model's raw `ss << hour << ":" << minute` (failure log 8516-8521) — a latent every-case runtime failure.
- **G4 — `!=` from `==`.** Providing only `operator==` leaves `!=` unusable pre-C++20 (terminal error failure log 8825); the idiom of a free inline `operator!=` delegating to `==` (example.h:28-31) is missing.
- **G5 — Decoding test usage from error output.** The attempt-1 errors quoted the exact expressions the test uses (`string(...::at(...).plus(...))`); every required API element is visible there. The model fixed only the name, not the usage patterns (G2/G4).
- **G6 — Whole-file format contract.** Diff-hunk answers under `edit_format: whole` (failure log 8451-8454), mangled guard line (failure log 8469), and no-op reflection applies (shard-0 8250-8251, 9429-9430, 11832-11833).
- **G7 — Reference-returning mutators.** `plus`/`minus` return `clock&` enabling fluent chaining (example.h:14-15); the model returned by value both attempts (failure log 8464-8465; shard-0 30606-30607) — works for the test but diverges from the contract's mutate-in-place semantics.

## 5. SFT Task Specifications (24 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-odometer
- Files: odometer.cpp, odometer.h (test file: odometer_test.cpp)
- API: namespace `garage`; `class trip { public: void drive(int km); int km() const; };`
- Prompt shape: car trip meter; whole-file instruction prominent.
- Target capability: G6 — complete whole-file listings only.
- Target answer shape: two whole-file listings, no diff fences.
- Difficulty / variation: minimal; format-only trap.

### Spec 02: lowercase-class-value-type-angle
- Files: angle.cpp, angle.h (test file: angle_test.cpp)
- API: namespace `geometry`; `class angle { public: static angle degrees(int deg); };`
- Prompt shape: compass-angle value type; hidden tests use lowercase `angle`.
- Target capability: G1 — lowercase class names for value types in this contract family.
- Target answer shape: `class angle` exactly.
- Difficulty / variation: naming-case prior.

### Spec 03: static-factory-private-ctor-thermometer
- Files: thermometer.cpp, thermometer.h (test file: thermometer_test.cpp)
- API: namespace `lab`; `class reading { public: static reading celsius(int tenths); private: explicit reading(int tenths); };`
- Prompt shape: lab thermometer readings created only through named factories.
- Target capability: G1 — private constructor + static factory method shape.
- Target answer shape: ctor in private section; factory returns by value.
- Difficulty / variation: factory idiom.

### Spec 04: conversion-operator-barcode
- Files: barcode.cpp, barcode.h (test file: barcode_test.cpp)
- API: namespace `retail`; `class sku { public: static sku from_digits(int digits); operator std::string() const; };`
- Prompt shape: product SKU rendered directly as `std::string(sku_value)` in tests.
- Target capability: G2 — implicit conversion operator as the stringification surface; not a named method.
- Target answer shape: `operator std::string() const;` declared and defined; no `to_string()`/`str()` method.
- Difficulty / variation: the core clock gap, minimal wrapper.

### Spec 05: conversion-operator-repair-speedometer
- Files: speedo.cpp, speedo.h (test file: speedo_test.cpp)
- API: namespace `bike`; test uses `string(speed::at(kmh))`; history answer shipped `std::string display()`; turn 2 shows `error: no matching function for call to 'basic_string(bike::speed)'`.
- Prompt shape: repair — replace the named method with a conversion operator.
- Target capability: G2/G5 — map the basic_string-construction diagnostic to a missing conversion operator.
- Target answer shape: whole files; named method removed, operator added.
- Difficulty / variation: repair with the log's exact diagnostic family.

### Spec 06: zero-padded-format-scoreboard
- Files: board.cpp, board.h (test file: board_test.cpp)
- API: namespace `arena`; `class timer { public: static timer at(int minutes, int seconds); operator std::string() const; };` — format `MM:SS` zero-padded.
- Prompt shape: arena countdown timer; hidden tests expect "08:07"-style padding.
- Target capability: G3 — `std::setw(2) << std::setfill('0')` with `<iomanip>` and `<sstream>`.
- Target answer shape: padded ostringstream build; both fields padded.
- Difficulty / variation: formatting drill.

### Spec 07: neq-from-eq-balance-scale
- Files: scale.cpp, scale.h (test file: scale_test.cpp)
- API: namespace `lab`; `class weight { public: bool operator==(const weight&) const; };` plus free `inline bool operator!=(const weight&, const weight&);`
- Prompt shape: balance-scale weights compared with both `==` and `!=` in tests.
- Target capability: G4 — always ship `!=` when `==` exists (pre-C++20), defined as its negation.
- Target answer shape: free inline `operator!=` in the header delegating to `==`.
- Difficulty / variation: operator-pair discipline.

### Spec 08: neq-repair-sundial
- Files: sundial.cpp, sundial.h (test file: sundial_test.cpp)
- API: namespace `garden`; test uses `dial1 != dial2`; history answer shipped only `operator==`; turn 2 shows `error: no match for 'operator!=' (operand types are 'const garden::dial' and 'const garden::dial')`.
- Prompt shape: repair — add the free `operator!=`; nothing else changes.
- Target capability: G4/G5 — map this exact diagnostic to the missing operator pair.
- Target answer shape: whole files; one inline operator added.
- Difficulty / variation: minimal repair with the log's diagnostic.

### Spec 09: wraparound-arithmetic-hourglass
- Files: egg_timer.cpp, egg_timer.h (test file: egg_timer_test.cpp)
- API: namespace `kitchen`; `class dial { public: static dial at(int value); dial& advance(int clicks); };` — dial wraps modulo 12 in both directions.
- Prompt shape: kitchen timer dial; hidden tests wrap past max and below zero.
- Target capability: edge cases — modulo normalization for positive AND negative deltas: `((v % n) + n) % n`.
- Target answer shape: normalize helper called from every mutator.
- Difficulty / variation: wraparound drill.

### Spec 10: negative-normalization-elevator
- Files: lift_dial.cpp, lift_dial.h (test file: lift_dial_test.cpp)
- API: namespace `hotel`; `class floor_wheel { public: static floor_wheel at(int floor); floor_wheel& rotate(int steps); int position() const; };` — 10-position wheel; -3 from 2 lands on 9.
- Prompt shape: elevator floor selector wheel; negative rotation emphasized.
- Target capability: edge cases — negative modulo (C++ `%` keeps sign); correct the bias.
- Target answer shape: explicit add-mod-add pattern with comment.
- Difficulty / variation: negative-wrap focus.

### Spec 11: fluent-ref-mutators-odometer-dial
- Files: counter.cpp, counter.h (test file: counter_test.cpp)
- API: namespace `fair`; `class clicker { public: static clicker at(int n); clicker& bump(int delta); clicker& drop(int delta); };` — tests chain `clicker::at(5).bump(3).drop(1)`.
- Prompt shape: turnstile clicker with chained adjustments.
- Target capability: G7 — mutators return `*this` by reference for chaining.
- Target answer shape: `clicker&` returns; `return *this;`.
- Difficulty / variation: fluent-interface shape.

### Spec 12: decode-api-from-test-usage-morse-key
- Files: keyer.cpp, keyer.h (test file: keyer_test.cpp)
- API: namespace `radio`; (determined by hidden tests: factory + ref mutators + conversion operator).
- Prompt shape: repair — turn 2's compiler output QUOTES the test's usage lines verbatim but names only one missing symbol; target must decode all three required API elements from the quoted usage.
- Target capability: G5 — read quoted call expressions as an API specification, not just an error locator.
- Target answer shape: whole files implementing every element visible in the quoted usage.
- Difficulty / variation: the meta-skill behind the clock attempt-2 failure.

### Spec 13: carry-between-fields-tide-dial
- Files: tide_dial.cpp, tide_dial.h (test file: tide_dial_test.cpp)
- API: namespace `harbor`; `class gauge { public: static gauge at(int marks, int submarks); gauge& advance(int submarks); };` — 60 submarks per mark; overflow carries.
- Prompt shape: tidal gauge with two-field display; minutes-style carry.
- Target capability: edge cases — field carry in both directions (60 submarks → 1 mark; negative borrows).
- Target answer shape: normalize computing carry and remainder explicitly.
- Difficulty / variation: two-field normalization (reference's clean() shape).

### Spec 14: equality-normalized-fuel-gauge
- Files: fuel.cpp, fuel.h (test file: fuel_test.cpp)
- API: namespace `tractor`; `class tank { public: static tank at(int liters); tank& burn(int liters); bool operator==(const tank&) const; };` — tanks equal when normalized levels equal (0..capacity).
- Prompt shape: tractor fuel gauge; equality after wraparound normalization.
- Target capability: semantics — compare normalized state, not raw accumulators.
- Target answer shape: normalization before/inside comparison.
- Difficulty / variation: equality-semantics nuance.

### Spec 15: contrastive-named-method-vs-operator-rain-dial
- Files: rain_dial.cpp, rain_dial.h (test file: rain_dial_test.cpp)
- API: namespace `farm`; `class dial { public: static dial at(int mm); operator std::string() const; };`
- Prompt shape: contrastive — history shows a `to_string()` answer failing `string(dial::at(5))` constructions; target uses the conversion operator.
- Target capability: G2 — recognize why a named method can never satisfy construction syntax.
- Target answer shape: operator version; named method gone.
- Difficulty / variation: negative-example-first.

### Spec 16: no-empty-fence-bell-tower
- Files: bells.cpp, bells.h (test file: bells_test.cpp)
- API: namespace `tower`; `class ringer { public: void ring(); int count() const; };`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines, no compiler output.
- Target capability: G6 — no empty fences; whole unchanged files or explicit no-change statement.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 17: stale-error-log-discipline-cable-car
- Files: car.cpp, car.h (test file: car_test.cpp)
- API: namespace `mountain`; `class car { public: static car at(int stop); car& advance(int stops); };`
- Prompt shape: multi-turn — turn 3 re-quotes an OLD compiler error that the turn-2 answer already fixed; target must recognize the staleness and not revert the fix.
- Target capability: G5 — distinguish stale diagnostics from current ones; verify against current file state.
- Target answer shape: unchanged correct files + note that the quoted error predates the fix.
- Difficulty / variation: counter-trains the clock re-litigation churn.

### Spec 18: context-budget-one-repair-pass-sunroom
- Files: blinds.cpp, blinds.h (test file: blinds_test.cpp)
- API: namespace `sunroom`; `class blind { public: static blind at(int pct); blind& adjust(int delta); operator std::string() const; bool operator==(const blind&) const; };` + free `operator!=`.
- Prompt shape: scripted two-turn — turn 1 answer has THREE API defects; turn 2 shows all diagnostics at once; target fixes all three in one pass.
- Target capability: G5/G7 — comprehensive single-pass repair to conserve reflection/context budget.
- Target answer shape: all defects fixed in one whole-file answer.
- Difficulty / variation: budget-efficiency drill.

### Spec 19: header-inline-operators-greenhouse
- Files: vent.cpp, vent.h (test file: vent_test.cpp)
- API: namespace `glass`; `class vent { public: bool operator==(const vent&) const; };` + free `inline bool operator!=` defined in the header.
- Prompt shape: greenhouse vent positions; spec notes the free operator must be `inline` in the header to avoid ODR issues.
- Target capability: G4 + header/impl separation — free operators in headers need `inline`.
- Target answer shape: `inline` free function after the class, inside the namespace.
- Difficulty / variation: ODR/inline nuance.

### Spec 20: default-minute-arg-buzzer
- Files: buzzer.cpp, buzzer.h (test file: buzzer_test.cpp)
- API: namespace `desk`; `class timer { public: static timer at(int hours, int minutes = 0); };`
- Prompt shape: desk timer; tests call `at(8)` and `at(8, 30)`.
- Target capability: API fidelity — default argument in the declaration only (not repeated in the definition).
- Target answer shape: default in header; definition without default.
- Difficulty / variation: default-arg placement.

### Spec 21: whole-file-on-retry-lighthouse
- Files: lamp.cpp, lamp.h (test file: lamp_test.cpp)
- API: namespace `coast`; `class lamp { public: static lamp at(int period); operator std::string() const; };`
- Prompt shape: turn 1 answer in diff-hunk format (malformed); turn 2 repeats whole-file requirement.
- Target capability: G6 — format recovery on retry.
- Target answer shape: whole files, same semantics.
- Difficulty / variation: conditioned format repair.

### Spec 22: seconds-rollover-darkroom
- Files: enlarger.cpp, enlarger.h (test file: enlarger_test.cpp)
- API: namespace `darkroom`; `class exposure { public: static exposure at(int seconds); exposure& add(int seconds); operator std::string() const; };` — display `MM:SS`, wraps at 60 minutes.
- Prompt shape: photo enlarger timer; combined carry + padding + conversion operator.
- Target capability: G2+G3+wraparound — integrative mid-level drill.
- Target answer shape: padded two-field rendering after normalization.
- Difficulty / variation: combined skills.

### Spec 23: private-normalize-helper-ferry-wheel
- Files: wheel.cpp, wheel.h (test file: wheel_test.cpp)
- API: namespace `carnival`; `class wheel { public: static wheel at(int gondola); wheel& spin(int steps); int position() const; private: void normalize(); int pos_; };`
- Prompt shape: ferris-wheel position; normalization logic shared by ctor and spin.
- Target capability: code organization — private normalize helper (like the reference's clean()) instead of duplicated modulo code.
- Target answer shape: single private helper called from both entry points.
- Difficulty / variation: structure mirrors reference idiom.

### Spec 24: capstone-station-clock-analog
- Files: platform_clock.cpp, platform_clock.h (test file: platform_clock_test.cpp)
- API: namespace `station`; `class platform_clock { public: static platform_clock at(int hours, int minutes = 0); platform_clock& forward(int minutes); platform_clock& back(int minutes); operator std::string() const; bool operator==(const platform_clock&) const; private: platform_clock(int hours, int minutes); void normalize(); int total_minutes_; };` + free `inline bool operator!=` in header. String format `HH:MM` zero-padded; 24h wraparound both directions.
- Prompt shape: railway platform clock with prose behavior spec; names underdetermined, behaviors pinned.
- Target capability: G1+G2+G3+G4+G7+wrap capstone — the full value-type surface in one answer.
- Target answer shape: complete conventional implementation; whole files.
- Difficulty / variation: integrative final spec mirroring the full reference surface.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, trailing newline present. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass in the benchmark's CMake/Catch2 shape; receipt stored.
3. **API-conformance gate**: class case, factory shape, conversion operator (not named methods), ref-returning mutators, and free `operator!=` all present exactly as specified — checked by compiling tests that use construction syntax `std::string(value)`, chaining, and `!=`.
4. **Formatting gate**: string outputs verified zero-padded for both fields across boundary values (0, 9, 10, 59, 60, wrap).
5. **Wraparound gate**: tests include positive and negative deltas crossing the modulus multiple times.
6. **Repair-turn gate**: repair specs (05, 08, 12, 15, 17, 18) must seed turn-1 answers producing the shown diagnostics; turn-2 targets fix exactly (and for Spec 18, all of) the seeded defects.
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce clock's (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the raw shard-0 log, and ground truth:

1. **Re-read every cited line/range** and confirmed quotes verbatim: failure log 7477-7480 (header), 7906 and 7985-8072 (chunk-1 foreign bleed), 8113 (clock `fnames:` marker), 8444-8539 (attempt-1 answer; class surface 8469-8480 = source 5937-5948, mangled hunk 8477 = source 5945, unpadded `time()` 8516-8521 = source 5984-5989, applied 8538-8539), 8567-8896 (terminal block; `operator!=` error 8825-8831 = source 62719-62725, Tests failed 8833 = source 62727), 8841-8844 (`tests_outcomes: [false, false]` = source 62735-62738), 8851 (`num_exhausted_context_windows: 1` = source 62745); shard-0 8250-8251, 9429-9430, 11832-11833 (no-op reflection applies), 11857 (reflections exhausted), 11901-11904 and 11975 (attempt-1 `'clock' is not a member` errors + Tests failed), 30600-30616 (attempt-2 header state with `time()` retained), 30639-30664 (churn quotes), 53475-53535 (stale-error reflection), 61274-61470 (terminal basic_string conversion errors — NOT present in the failure log excerpt; see note 2), 62714 (raw Tests failed).
2. **Re-checked every API claim** against `.meta/example.h` (`class clock` line 9, `static at` line 12, `plus`/`minus` returning `clock&` lines 14-15, `operator std::string() const` line 17, `operator==` line 19, private ctor line 22, free inline `operator!=` lines 28-31), `.meta/example.cpp` (zero-padded rendering lines 32-37, normalize lines 46-58, equality lines 65-69), and `clock_test.cpp` (`string(...::at(...))` line 183, `.plus(...)` chain line 194, `==`/`!=` lines 209/213). All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 0, result FAIL — matches header (7477-7480) and terminal JSON (8841-8844).
4. **Corrections made during cross-check**:
   - Chunk 1 (source 3762-4356) is foreign-task bleed (bank-account/dnd-character) — documented in section 1 note 1.
   - The failure log's terminal block begins at source 62466, mid-error-stream: the conversion-operator errors (shard-0 61274-61470) precede it and were recovered from the raw shard log — documented in section 1 note 2 and cited as shard-0 evidence. An early draft of section 3 claimed the terminal failure was "only `operator!=`"; corrected to the two-defect-family account.
   - Verified by re-reading shard-0 30600-30616 that the attempt-2 header kept `std::string time()` (no conversion operator was ever added) — the inference that `time()` survived to the terminal state is thus hard evidence, and is stated as such.
   - Corrected three citation line numbers after re-grep: attempt-1 class surface is at failure log 8469-8480 (draft said 8461-8473), the mangled hunk at 8477 (draft said 8469), and the unpadded `time()` at 8516-8521 (draft said 8508-8513).
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `clock_test.cpp` are present, consistent, and authoritative.
