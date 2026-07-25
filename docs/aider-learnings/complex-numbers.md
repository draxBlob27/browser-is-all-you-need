# complex-numbers — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `complex-numbers`
- Shard: `0` (failure log section header, line 8899: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 8901; terminal JSON `tests_outcomes: [false, false]`, failure log lines 10122-10125 / raw shard-0 lines 41482-41485)
- Result: `FAIL` (failure log line 8902)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **8897-10165**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log` (complex-numbers run spans source lines ~1158-41550; interleaved with concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/complex-numbers/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/complex-numbers/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/complex-numbers/complex_numbers_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Failure log omits the attempt-2 answer.** Chunk 1 (failure log 8947+, source 1158-1518) is attempt 1; chunk 2 (failure log 9313+, source 6593-7292) is attempt-1 reflection churn ending in a near-empty answer (failure log 9965-9991). The attempt-1 test failure and the attempt-2 rewrite exist only in the raw shard-0 log, cited as "shard-0 line N".
2. **Citation scheme.** Failure-log lines carry the log's raw-shard source-line prefixes; raw shard-0 lines are labeled "shard-0".

## 2. Benchmark Contract (Ground Truth)

File set: `complex_numbers.h` + `complex_numbers.cpp`, namespace `complex_numbers`.

Public API (from `.meta/example.h`, enforced by `complex_numbers_test.cpp`):

- `class Complex` with `Complex(double, double);` constructor and **private** data `double re, im;` (example.h:7-9, 21-22) — no public fields.
- Member arithmetic operators: `Complex operator+(const Complex&) const`, `operator-`, `operator*`, `operator/` (example.h:10-13).
- Accessors as **member functions**: `double real() const; double imag() const;` (example.h:17-18). The test calls them as functions: `REQUIRE_THAT(lhs.real(), Catch::Matchers::WithinAbs(rhs.real(), eps));` (complex_numbers_test.cpp:29-32).
- `double abs() const;` (returns a scalar, example.h:15, example.cpp:33), `Complex conj() const;` (example.h:16), `Complex exp() const;` (example.h:19) — short names, member functions.
- Free `bool operator==(const Complex&, const Complex&)` (example.h:25) and `std::ostream& operator<<(std::ostream&, const Complex&)` (example.h:26).
- **Scalar overloads in both orders**: `operator+(const Complex&, double)`, `operator+(double, const Complex&)`, and the same for `-`, `*`, `/` (example.h:27-34). The test exercises mixed Complex/double arithmetic (terminal errors quoting `operator+ (operand types are 'const complex_numbers::Complex' and 'double')`, shard-0 ~36530-36550, show the test's expectations).

Exception policy: none.

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: struct-with-statics invention)

**What the model emitted.** A **diff-hunk answer** (failure log 9198-9282, source 1406-1490): `struct Complex { double real; double imag; Complex(); Complex(double r, double i); static Complex add(Complex a, Complex b); static Complex subtract(...); static Complex multiply(...); static Complex divide(...); static Complex conjugate(Complex z); static double absolute_value(Complex z); static Complex exponent(Complex z); };` (failure log 9211-9225, source 1419-1433) with matching static definitions (failure log 9236-9265+, source 1450-1475+). The mathematical formulas (multiply, divide, conjugate, abs) were correct; the entire API *shape* was invented: public fields named `real`/`imag`, static methods instead of operators/members, long names (`conjugate`, `absolute_value`, `exponent`) instead of `conj`/`abs`/`exp`, no operators, no scalar overloads, no `<<`/`==`. Applied (failure log 9281-9282, source 1489-1490).

**Reflection turn.** A `# Fix any errors below` █ prompt drew an **empty header diff** plus a cosmetic `<cmath>` addition to the cpp (failure log 9965-9991, source 7242-7268) — no substantive repair.

**Test run 1 — compile failure** (shard-0 ~36490-36566): `error: 'const struct complex_numbers::Complex' has no member named 'exp'` (shard-0 36490-36494, quoting complex_numbers_test.cpp:228), `error: no match for 'operator+' (operand types are 'const complex_numbers::Complex' and 'double')` and `'double' and 'const complex_numbers::Complex'` (shard-0 ~36530-36550, quoting test:247-283), plus `real()`/`imag()` used-as-function errors. `Tests failed: .../complex-numbers` (shard-0 36566).

### Attempt 2 (retry with compiler output) — outcome False (compile failure: member/method name collision)

**What the retry changed.** The rewrite (shard-0 39000-39139, applied 39138-39139) kept the struct with public `double real; double imag;` fields and **added member functions with the same names**:

```
+    double real() const { return real; }
+    double imag() const { return imag; }
+    Complex abs() const;
+    Complex conj() const;
+    Complex exp() const;
+    Complex operator+(const Complex& other) const; ... (and -, *, /)
+    friend Complex operator+(const Complex& c, double d); ... (both orders, four ops)
```
(shard-0 39010-39029.) It also mis-typed `abs` as returning `Complex` (`Complex Complex::abs() const { return Complex(std::sqrt(real * real + imag * imag), 0.0); }`, shard-0 39051-39052) where the contract returns `double`.

**Terminal result — compile failure** (failure log 10018-10165, source ~41390-41550):

- `complex_numbers.h:15:40: error: 'double complex_numbers::Complex::real() const' conflicts with a previous declaration` — `15 | double real() const { return real; }`, with note `previous declaration 'double complex_numbers::Complex::real'` at line 9 (failure log 10040-10045, source 41400-41405); identical conflict for `imag` (failure log 10046-10053, source 41406-41413). A data member and a member function cannot share a name — the exact bank-account `balance` mistake repeated.
- Cascading: `complex_numbers_test.cpp:29:26: error: expression cannot be used as a function` at `lhs.real()` and repetitions at test lines 30-69 (failure log 10054-10092, source 41414-41452).
- `catch.hpp:3774:54: error: cannot convert 'const complex_numbers::Complex' to 'const double&'` (failure log 10093, source 41453) — the `abs` misuse inside comparisons.

`Tests failed: .../complex-numbers` (failure log 10114, source 41474); JSON `tests_outcomes: [false, false]` (failure log 10122-10125).

### Hard evidence vs inference

- Hard evidence: static-method struct API (failure log 9211-9225), empty-diff reflection (failure log 9965-9991), attempt-1 errors (shard-0 36490-36550, 36566), attempt-2 member/method collisions (shard-0 39010-39016; failure log 10040-10053), `abs` returning `Complex` (shard-0 39051-39052), terminal cascades (failure log 10054-10093).
- Inference: attempt 1 is the math-correct/API-invented pattern — the model knows complex arithmetic cold but defaulted to a C-style struct-with-statics design instead of the C++ operator-overloaded value type the exercise family expects. Attempt 2 added the right *names* (`real()`, `imag()`, `abs`, `conj`, `exp`, operators, scalar overloads) onto the wrong *substrate* (public fields), producing the name-collision compile error instead of restructuring to private `re`/`im`. The repair habit of patching over a flawed foundation rather than rebuilding it (also seen in allergies' factory shim) recurs. The `abs`→`Complex` return-type slip shows signature fidelity degrading under large rewrites.

## 4. Knowledge / Capability Gaps

- **G1 — Operator-overload value-type design.** C++ numeric value types use member/free operators, not static named functions (contract: example.h:10-13, 27-34; invented as statics at failure log 9211-9225; test expects operators, shard-0 ~36530-36550).
- **G2 — Member/method name collision (again).** Public fields `real`/`imag` plus methods `real()`/`imag()` cannot coexist (failure log 10040-10053). Private `re`/`im` backing stores (example.h:22) or trailing-underscore members are the standard escape — never applied.
- **G3 — Accessor-as-function convention.** The contract calls `z.real()` as a function (complex_numbers_test.cpp:29-32); shipping data members breaks every accessor call site.
- **G4 — Signature fidelity under rewrite.** `abs` must return `double` (example.h:15); attempt 2 declared/defined `Complex abs() const` (shard-0 39010-39013, 39051-39052). Return types must be copied from the contract, not intuited.
- **G5 — Short-name conventions.** `abs`/`conj`/`exp` (not `absolute_value`/`conjugate`/`exponent`) — canonical exercism-cpp naming (failure log 9222-9224 vs example.h:15-19).
- **G6 — Scalar-operator overloads, both orders.** `(Complex, double)` AND `(double, Complex)` for all four operators (example.h:27-34); absent in attempt 1 (shard-0 ~36530-36550), added only as friends in attempt 2.
- **G7 — Whole-file format contract.** Diff-hunk answers (failure log 9211-9225), empty-diff no-op (failure log 9965-9979).

## 5. SFT Task Specifications (24 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-odometer-reading
- Files: reading.cpp, reading.h (test file: reading_test.cpp)
- API: namespace `rail`; `class odometer { public: void roll(int km); int total() const; };`
- Prompt shape: rail odometer; whole-file instruction prominent.
- Target capability: G7 — complete whole-file listings only.
- Target answer shape: two whole-file listings, no diff fences.
- Difficulty / variation: minimal; format-only trap.

### Spec 02: operator-overload-vector2d
- Files: vec2.cpp, vec2.h (test file: vec2_test.cpp)
- API: namespace `geom`; `class Vec2 { public: Vec2(double x, double y); Vec2 operator+(const Vec2&) const; Vec2 operator-(const Vec2&) const; Vec2 operator*(double) const; double x() const; double y() const; private: double x_, y_; };`
- Prompt shape: 2-D physics vector; hidden tests use `a + b`, never named methods.
- Target capability: G1 — member operator overloading for arithmetic value types.
- Target answer shape: operators as const members; private fields with trailing underscore.
- Difficulty / variation: operator-design drill.

### Spec 03: no-static-methods-fraction
- Files: fraction.cpp, fraction.h (test file: fraction_test.cpp)
- API: namespace `mathx`; `class Fraction { public: Fraction(int num, int den); Fraction operator*(const Fraction&) const; int num() const; int den() const; };`
- Prompt shape: contrastive — history shows a struct with `static Fraction mul(Fraction, Fraction)` failing operator tests.
- Target capability: G1 — operators are members/free functions, never static named methods.
- Target answer shape: operator version; statics removed.
- Difficulty / variation: negative-example-first.

### Spec 04: accessor-methods-not-fields-temperature
- Files: temp.cpp, temp.h (test file: temp_test.cpp)
- API: namespace `hvac`; `class Reading { public: Reading(double c, double f); double celsius() const; double fahrenheit() const; private: double c_, f_; };`
- Prompt shape: HVAC sensor reading; tests call `r.celsius()` as functions.
- Target capability: G3 — accessor member functions backed by private fields, not public data members.
- Target answer shape: private fields, public const accessors.
- Difficulty / variation: encapsulation convention.

### Spec 05: field-method-collision-repair-grid-point
- Files: grid_point.cpp, grid_point.h (test file: grid_point_test.cpp)
- API: namespace `plot`; test expects `p.x()`/`p.y()`; history answer shipped public `double x; double y;` then added `double x() const { return x; }`; turn 2 shows `error: 'double plot::Point::x() const' conflicts with a previous declaration`.
- Prompt shape: repair — restructure to private `x_`/`y_` with method accessors; update every use site.
- Target capability: G2 — resolve member/method collisions by renaming the DATA, keeping the accessor name the tests demand.
- Target answer shape: whole files; collision gone; no remaining public fields.
- Difficulty / variation: the exact complex-numbers attempt-2 bug.

### Spec 06: return-type-fidelity-decibel
- Files: db.cpp, db.h (test file: db_test.cpp)
- API: namespace `audio`; `class Signal { public: Signal(double re, double im); double magnitude() const; Signal normalized() const; };` — `magnitude` returns scalar, `normalized` returns Signal.
- Prompt shape: audio signal; spec stresses which functions return scalars vs objects.
- Target capability: G4 — copy return types from the spec exactly; don't intuit.
- Target answer shape: `double` scalar return for magnitude.
- Difficulty / variation: counter-trains the `abs`→`Complex` slip.

### Spec 07: short-canonical-names-polar
- Files: polar.cpp, polar.h (test file: polar_test.cpp)
- API: namespace `nav`; `class Heading { public: Heading(double r, double t); double mag() const; double ang() const; Heading rot(double delta) const; };`
- Prompt shape: navigation heading; hidden tests use short names `mag`/`ang`/`rot`, not `magnitude`/`angle`/`rotate`.
- Target capability: G5 — canonical short names for value-type operations.
- Target answer shape: exact short names.
- Difficulty / variation: naming prior.

### Spec 08: scalar-overloads-both-orders-baking
- Files: measure.cpp, measure.h (test file: measure_test.cpp)
- API: namespace `kitchen`; `class Amount { public: explicit Amount(double grams); Amount operator+(const Amount&) const; };` + free `Amount operator+(const Amount&, double)` and `Amount operator+(double, const Amount&)`.
- Prompt shape: recipe scaling; tests do `flour + 50.0` and `50.0 + flour`.
- Target capability: G6 — scalar overloads in both operand orders; the double-first form must be a free (or friend) function.
- Target answer shape: two free operators; member handles only the symmetric object case.
- Difficulty / variation: overload-set completeness.

### Spec 09: scalar-all-four-ops-currency
- Files: money.cpp, money.h (test file: money_test.cpp)
- API: namespace `cash`; `class Purse { public: explicit Purse(double cents); /* + - * / with Purse and with double, both orders */ };`
- Prompt shape: wallet arithmetic; tests exercise all four scalar operators in both orders.
- Target capability: G6 — full 8-function scalar overload set without omissions.
- Target answer shape: complete set; no missing operator.
- Difficulty / variation: overload-set scale-up.

### Spec 10: friend-vs-free-scalar-geometry-scale
- Files: scale.cpp, scale.h (test file: scale_test.cpp)
- API: namespace `draft`; `class Length { public: explicit Length(double mm); private: double mm_; };` scalar ops need private access.
- Prompt shape: drafting lengths; spec allows either friend declarations or public accessors for the free operators.
- Target capability: G6 — know both mechanisms for free operators needing private data; pick one and be consistent.
- Target answer shape: friend declarations in-class with out-of-class definitions, or accessor-based free functions.
- Difficulty / variation: mechanism choice.

### Spec 11: ostream-operator-latlong
- Files: latlong.cpp, latlong.h (test file: latlong_test.cpp)
- API: namespace `geo`; `class Point { public: Point(double la, double lo); double lat() const; double lng() const; };` + `std::ostream& operator<<(std::ostream&, const Point&)`.
- Prompt shape: map coordinates printable via `os << point`.
- Target capability: G1/G6 — stream-insertion operator shape: free function returning `std::ostream&`, `<ostream>` included.
- Target answer shape: exact signature; returns the stream.
- Difficulty / variation: streaming idiom.

### Spec 12: equality-free-function-spectrum
- Files: sample.cpp, sample.h (test file: sample_test.cpp)
- API: namespace `audio`; `class Sample { public: Sample(double l, double r); };` + free `bool operator==(const Sample&, const Sample&)`.
- Prompt shape: stereo sample equality; tests compare with `==`.
- Target capability: G1 — equality as a free symmetric operator (reference style) vs member; consistency.
- Target answer shape: free `operator==` delegating to accessors.
- Difficulty / variation: equality-placement nuance.

### Spec 13: complex-math-analog-phasor
- Files: phasor.cpp, phasor.h (test file: phasor_test.cpp)
- API: namespace `power`; `class Phasor { public: Phasor(double re, double im); Phasor operator*(const Phasor&) const; Phasor operator/(const Phasor&) const; double re() const; double im() const; };`
- Prompt shape: AC-circuit phasor math; multiply/divide formulas required (not given in prompt).
- Target capability: math fidelity — (ac−bd, ad+bc) and division via denominator |b|², with the sign in the right place.
- Target answer shape: correct formulas; no swapped signs.
- Difficulty / variation: domain-math correctness (model had this right — reinforce).

### Spec 14: euler-exp-analog-signal-growth
- Files: growth.cpp, growth.h (test file: growth_test.cpp)
- API: namespace `signal`; `class Kernel { public: Kernel(double a, double b); Kernel propagate() const; private: double a_, b_; };` — propagate computes (e^a·cos b, e^a·sin b).
- Prompt shape: signal kernel propagation; formula stated in the story.
- Target capability: math + includes — `std::exp`, `std::cos`, `std::sin` from `<cmath>` in the cpp.
- Target answer shape: `<cmath>` include; correct formula.
- Difficulty / variation: cmath hygiene.

### Spec 15: private-backing-fields-quaternion
- Files: quat.cpp, quat.h (test file: quat_test.cpp)
- API: namespace `rot`; `class Quat { public: Quat(double w, double x, double y, double z); double w() const; /* x(), y(), z() */ private: double w_, x_, y_, z_; };`
- Prompt shape: rotation quaternions; all components accessible via methods.
- Target capability: G2/G3 — private fields + method accessors at 4-component scale.
- Target answer shape: underscore-suffixed privates; no public data.
- Difficulty / variation: encapsulation scale-up.

### Spec 16: repair-statics-to-operators-matrix2
- Files: mat2.cpp, mat2.h (test file: mat2_test.cpp)
- API: namespace `gfx`; test expects `m1 * m2` and `m.det()`; history answer shipped `static Mat2 multiply(Mat2, Mat2)` and `static double determinant(Mat2)`.
- Prompt shape: repair — convert static named methods to operators/members; keep the math identical.
- Target capability: G1/G5 — API-shape repair preserving correct internals.
- Target answer shape: `operator*` member + `det()` accessor; statics deleted.
- Difficulty / variation: shape-migration repair.

### Spec 17: no-empty-fence-barometer
- Files: barometer.cpp, barometer.h (test file: barometer_test.cpp)
- API: namespace `weather`; `class reading { public: void sample(double kpa); double last() const; };`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines, no compiler output.
- Target capability: G7 — no empty fences; whole unchanged files or explicit no-change statement.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 18: whole-file-on-retry-seismograph
- Files: trace.cpp, trace.h (test file: trace_test.cpp)
- API: namespace `geo`; `class trace { public: void add(double v); double peak() const; };`
- Prompt shape: turn 1 answer in diff-hunk format (malformed); turn 2 repeats whole-file requirement.
- Target capability: G7 — format recovery on retry.
- Target answer shape: whole files, same semantics.
- Difficulty / variation: conditioned format repair.

### Spec 19: division-denominator-orbit
- Files: state.cpp, state.h (test file: state_test.cpp)
- API: namespace `orbit`; `class Spin { public: Spin(double u, double v); Spin operator/(const Spin&) const; };` — division formula given in story.
- Prompt shape: orbital spin ratio; spec warns about the denominator being sum-of-squares, not component-wise division.
- Target capability: math precision — denominator computed once; both numerator terms use it.
- Target answer shape: single denominator variable; correct numerator signs.
- Difficulty / variation: formula-precision drill.

### Spec 20: approx-equality-testing-awareness-balance
- Files: beam.cpp, beam.h (test file: beam_test.cpp)
- API: namespace `physics`; `class Beam { public: Beam(double l, double w); Beam operator+(const Beam&) const; double length() const; double weight() const; };`
- Prompt shape: beam loading; story notes tests compare doubles approximately — no epsilon logic belongs in the class.
- Target capability: semantics — never bake tolerances into the value type; keep exact arithmetic.
- Target answer shape: exact operations; no epsilon constants in the class.
- Difficulty / variation: test-awareness boundary.

### Spec 21: conj-style-short-op-filter
- Files: filter.cpp, filter.h (test file: filter_test.cpp)
- API: namespace `dsp`; `class Tap { public: Tap(double re, double im); Tap flip() const; double mag() const; };`
- Prompt shape: DSP filter tap; `flip` negates the imaginary part (story-stated).
- Target capability: G5 + math — short operation names; targeted component negation.
- Target answer shape: `Tap(a_, -b_)` construction.
- Difficulty / variation: conj analog, fresh domain.

### Spec 22: const-correct-operators-rational
- Files: rational.cpp, rational.h (test file: rational_test.cpp)
- API: namespace `num`; `class Rational { public: Rational(int n, int d); Rational operator+(const Rational&) const; Rational operator-() const; };`
- Prompt shape: rationals; tests call operators on const objects and use unary minus.
- Target capability: const-correctness — all operators const-qualified; unary operator support.
- Target answer shape: trailing `const` on every operator; unary `-` returns negation.
- Difficulty / variation: qualifier + unary drill.

### Spec 23: brace-init-construction-particle
- Files: particle.cpp, particle.h (test file: particle_test.cpp)
- API: namespace `lab`; `class Particle { public: Particle(double px, double py); };`
- Prompt shape: particle momentum; spec style note: construct results with brace initialization `Particle{a, b}` inside operator bodies.
- Target capability: style consistency — brace-init in factory-style operator bodies (reference idiom).
- Target answer shape: brace constructions throughout.
- Difficulty / variation: idiom matching.

### Spec 24: capstone-complex-analog-impedance
- Files: impedance.cpp, impedance.h (test file: impedance_test.cpp)
- API: namespace `circuit`; `class Impedance { public: Impedance(double re, double im); Impedance operator+(const Impedance&) const; Impedance operator-(const Impedance&) const; Impedance operator*(const Impedance&) const; Impedance operator/(const Impedance&) const; double mag() const; Impedance inv_conj() const; double re() const; double im() const; Impedance euler() const; private: double re_, im_; };` + free `operator==`, `operator<<`, and full scalar overload set (both orders, four ops).
- Prompt shape: AC-circuit impedance arithmetic with prose behavior spec; names underdetermined, behaviors pinned.
- Target capability: G1+G2+G3+G4+G5+G6 capstone — full operator-overloaded value type in one answer.
- Target answer shape: complete conventional implementation; whole files.
- Difficulty / variation: integrative final spec mirroring the full reference surface.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, trailing newline present. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass in the benchmark's CMake/Catch2 shape; receipt stored.
3. **API-conformance gate**: operators (not statics), accessor methods (not public fields), short canonical names, scalar overloads in both orders, exact return types — all checked by compiling the spec's tests, which deliberately use `z + 1.0`, `1.0 + z`, `==`, and `<<`.
4. **Collision gate**: no data member shares a name with a member function — mechanically checked in target headers.
5. **Math gate**: multiply/divide/exp-analog formulas verified against known values in each spec's tests (including sign placement and denominator reuse).
6. **Repair-turn gate**: repair specs (03, 05, 16) must seed turn-1 answers producing the shown diagnostics; turn-2 targets fix the seeded defects completely (no leftover statics, fields, or wrong return types).
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce complex-numbers' (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the raw shard-0 log, and ground truth:

1. **Re-read every cited line/range** and confirmed quotes verbatim: failure log 8899-8902 (header), 9198-9282 (attempt-1 answer; struct-with-statics surface 9211-9225 = source 1419-1433, applied 9281-9282), 9965-9991 (empty header diff + `<cmath>` reflection answer = source 7242-7268), 10018-10165 (terminal block; name-collision errors 10040-10053 = source 41400-41413, used-as-function cascades 10054-10092 = source 41414-41452, catch conversion error 10093 = source 41453, Tests failed 10114 = source 41474), 10122-10125 (`tests_outcomes: [false, false]` = source 41482-41485); shard-0 36490-36494 (attempt-1 `no member named 'exp'` quoting test:228), ~36530-36550 (attempt-1 scalar `operator+` mismatches quoting test:247-283), 36566 (attempt-1 Tests failed), 39000-39139 (attempt-2 rewrite; colliding inline accessors at 39010-39016, `Complex abs() const` return-type slip at 39051-39052), 39138-39139 (applied), 41467 (raw terminal Tests failed).
2. **Re-checked every API claim** against `.meta/example.h` (class + ctor lines 7-9, member operators lines 10-13, `abs`/`conj`/`real`/`imag`/`exp` lines 15-19, private `re, im` line 22, free `==`/`<<` lines 25-26, scalar overloads both orders lines 27-34), `.meta/example.cpp` (operator formulas lines 10-31, `abs` returning `double` line 33, `conj` lines 35-38, `exp` lines 44-47), and `complex_numbers_test.cpp` (`lhs.real()` used as function lines 29-32). All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 0, result FAIL — matches header (8899-8902) and terminal JSON (10122-10125).
4. **Corrections made during cross-check**:
   - Draft described attempt 2 as "added accessors to the struct"; re-reading shard-0 39000-39139 shows it also added member operators and friend scalar overloads, and mis-typed `abs` as returning `Complex` — all three facts are now in section 3 (the `abs` return-type slip became G4).
   - Verified the failure-log terminal block's quoted header lines (`15 | double real() const { return real; }`, failure log 10041 = source 41401) confirm the collision was inline in the header — cited as such.
   - Noted the near-empty reflection answer (failure log 9965-9991) belongs to attempt 1's reflection phase (source 7242 precedes the attempt-1 Tests failed at shard-0 36566), not attempt 2 — assigned correctly in section 3.
   - Corrected two citation line numbers after re-grep: the struct-with-statics surface is at failure log 9211-9225 (draft said 9205-9221) and the long-name static declarations at 9222-9224 (draft said 9217-9219).
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `complex_numbers_test.cpp` are present, consistent, and authoritative.
