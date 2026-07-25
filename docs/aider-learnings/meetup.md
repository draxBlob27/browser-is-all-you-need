# Aider Learning: meetup

## 1. Task Identity & Evidence Pointers

- Task slug: `meetup`
- Shard: `1`
- Test outcomes: `[False, False]` — attempt 1 failed, attempt 2 failed. Result: `FAIL`.
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines 60545–62290.
  - Section header / reconstructed prompt: lines 60545–60592.
  - Attempt/log chunk 1 (source lines 3571–4234): failure-log lines 60593–61263.
  - Attempt/log chunk 2 (source lines 6372–7071): failure-log lines 61264–61968.
  - Terminal test log + result JSON (source lines 52503–52817): failure-log lines 61969–62290.
- Raw shard log (interleaved with other parallel tasks; meetup spans the whole file): `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-1/benchmark.log`. Key anchors: attempt-1 edits applied at lines 4210–4211, attempt-1 test run lines 6776–7953 ("Tests failed" line 7953); attempt-2 scheduler edits applied at lines 12928–12929, further fix edits at lines 14689 and 17717, terminal test run lines 50039–52755 ("Tests failed" line 52755), result JSON lines 52759–52817.
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/meetup/.meta/example.h` (reference solution; header-only — there is **no** `.meta/example.cpp` for this exercise; `example.h` plus `tests.toml`/`config.json` are the complete reference, so this is not a missing-reference situation).
  - `polyglot-benchmark/cpp/exercises/practice/meetup/meetup_test.cpp` (90 `TEST_CASE`s, 735 lines).
  - `polyglot-benchmark/cpp/exercises/practice/meetup/CMakeLists.txt`.
  - Starter files `meetup.h`/`meetup.cpp` at the exercise root are empty namespaces, NOT the solution.
- Existing analog dir: none (`aider-fixed26-analogs/` covers b001–b007, meetup not among them). Granularity reference: `aider-fixed26-analogs/fixed26-b001-all-your-base/`.

## 2. Benchmark Contract (Ground Truth)

File set: `meetup.h` + `meetup.cpp` (both compiled with `meetup_test.cpp`; the reference implements everything in the header — `CMakeLists.txt:18-22` allows an absent `.cpp`, but the harness ships a starter `meetup.cpp`).

Boost dependency is mandatory: `CMakeLists.txt:14` — `find_package(Boost 1.58 REQUIRED COMPONENTS date_time)`. The test file says so explicitly at `meetup_test.cpp:9-13` ("This problem requires you to install and use the boost date_time library").

Exact API (all from `.meta/example.h`):

- Include: `#include <boost/date_time/gregorian/gregorian.hpp>` (example.h:4).
- Namespace: `namespace meetup` (example.h:6).
- `class scheduler` (example.h:9) with constructor:
  `scheduler(boost::gregorian::date::month_type month, boost::gregorian::date::year_type year)` (example.h:12-13).
- 42 public **const** member functions returning `boost::gregorian::date`:
  - 7 teenth: `monteenth()`, `tuesteenth()`, `wednesteenth()`, `thursteenth()`, `friteenth()`, `saturteenth()`, `sunteenth()` (example.h:18-45).
  - 35 ordinal: `first_/second_/third_/fourth_/last_` × `monday()…sunday()` (example.h:47-190).
- Exception policy: none — no throwing paths in the contract.
- Semantics: teenth = first given weekday strictly after the 12th (example.h:193-196); nth/last weekday via `boost::gregorian::nth_day_of_the_week_in_month` / `first_day_of_the_week_in_month` / `last_day_of_the_week_in_month` (example.h:198-228).

How the tests enforce it:

- Construction from a boost month constant and an int year, on a **const** object: `const meetup::scheduler meetup{boost::gregorian::May, 2013};` (meetup_test.cpp:17).
- Calls on the const object demand const member functions: `REQUIRE(expected == meetup.monteenth());` (meetup_test.cpp:20).
- Equality against `boost::gregorian::date expected{2013, boost::gregorian::May, 13};` (meetup_test.cpp:19) — so the return type must be `boost::gregorian::date` (or comparable).
- All 90 cases use years 2013 (and 1953-style teenth cases in the prompt), e.g. final case `last_Sunday_of_April_2013` expects `boost::gregorian::Apr, 28` (meetup_test.cpp:726-733).

Output-format constraints: Aider "whole" edit format — every changed file as a complete file listing (filename line, then fenced block with the entire content); the system prompt forbids elision (failure-log lines 60555-60572).

## 3. Failure Anatomy

### Attempt 1 — invented a string-based free-function API; never compiled (outcome[0] = False)

Hard evidence:

- The starter files are empty namespaces, and the model explicitly chose to invent an interface: "since the provided files are empty, I have to infer the expected interface or create a standard one" (failure-log line 60609, quoting source line 3596-3600); "*Standard Interface:* `tm meetup_day(const std::string& weekday_name, const std::string& week_specifier, int month, int year);`" (failure-log line 60622, source 3610-3611); and after finishing: "There were none. I created `meetup_day`. This is the standard name for this problem." (failure-log line 61157, source 4054-4056).
- Emitted answer: `struct tm meetup_day(const std::string& weekday, const std::string& week, int month, int year);` in `meetup.h` and a `<ctime>`/`<map>` implementation in `meetup.cpp` (failure-log lines 61171-61175 / 61203-61205, source 4099-4100 / 4126-4127). No `scheduler` class, no boost.
- Format violation: both listings were emitted as ` ```diff ` unified-diff blocks (failure-log lines 61166-61190, source 4088-4112) although the edit format is `whole`; the harness nonetheless applied them ("Applied edit to meetup.h", failure-log line 61242, source 4212).
- Aider reflection turn "# Fix any errors below, if possible." marked `meetup.h` line 9 (failure-log lines 61248-61258, source 4215-4234). Instead of recognizing the real problem (wrong API vs the hidden tests), the model hallucinated a case-sensitivity bug in the weekday map lookup: "**This is likely the error.**" (failure-log line 61506, source 6540) and applied a lowercase-normalization patch to `meetup.cpp` (failure-log lines 61591-61597, source 6628-6634; "Applied edit to meetup.cpp", failure-log line 61607, source 6645).
- The compile then failed with the true error, repeated for every test case: `error: 'scheduler' in namespace 'meetup' does not name a type` / `17 | const meetup::scheduler meetup{boost::gregorian::May, 2013};` (shard benchmark.log lines 6781-6783, mirrored in failure-log lines 61742-61745). Attempt 1 ends "Tests failed … /practice/meetup" (shard line 7953).

Inference (root cause): the model has no knowledge of this exercise's canonical exercism-cpp API (a `meetup::scheduler` class over `boost::gregorian`) and, more generally, no strategy for "empty starter + hidden tests" tasks — it confidently fabricated a "standard" string-based signature instead of designing the class-shaped, typed API the domain implies.

### Attempt 2 — built a `scheduler` class but with an ill-formed constructor type and non-const methods; retry loop misdiagnosed (outcome[1] = False)

Hard evidence:

- Seeing the attempt-1 compiler output, the model correctly inferred a `scheduler` class was required and that the tests use Boost: "The error messages indicate that the test code expects a `scheduler` class within the `meetup` namespace … uses Boost types" (shard benchmark.log lines 12637-12645). It declared `scheduler(boost::gregorian::month month, int year);` plus all 42 methods as `boost::gregorian::date monteenth(); … last_sunday();` — all **without `const`** (shard lines 12673-12720).
- Two fatal defects in that API:
  1. `boost::gregorian::month` is not a type. The compiler said: `meetup.h:15:42: error: expected ')' before 'month'` and `meetup.h:60:27: error: 'month' in namespace 'boost::gregorian' does not name a type; did you mean 'months'` (shard lines 50042, 50046). The ill-formed constructor declaration was dropped, so every test construction failed: `error: no matching function for call to 'meetup::scheduler::scheduler(<brace-enclosed initializer list>)'` with only implicit candidates (`candidate expects 0 arguments, 2 provided`) (failure-log lines 62024-62034, source 52520-52530).
  2. All 42 methods were non-const, so calls on the tests' `const meetup::scheduler` failed: `error: passing 'const meetup::scheduler' as 'this' argument discards qualifiers [-fpermissive]` / `in call to 'boost::gregorian::date meetup::scheduler::last_wednesday()'` (failure-log lines 62011-62016, source 52507-52512), repeated for every method (e.g. `last_thursday` at failure-log lines 62074-62079, source 52569-52574).
- Retry/repair loop failures after the scheduler edit:
  - Fix round at shard line 14689: the model decided the problem was a missing `#include <boost/date_time/gregorian/gregorian.hpp>` in `meetup.h` and applied only that (shard lines 14590-14689). The `boost::gregorian::month` type error and the const errors remained.
  - Fix round at shard line 17717: the model hallucinated a `struct tm` visibility error and emitted an **empty diff** for `meetup.h` ("I will output the file content provided in the prompt" followed by a ` ```diff ` block with no hunks, shard lines 17699-17714), which aider still "applied".
  - Later reasoning declared the broken code sound: "`scheduler(boost::gregorian::month month, int year)` `: month_(month), year_(year) {}` Correct." and "The code provided in the prompt looks correct." (shard lines 46559-46563, 46611-46613).
  - The token `greg_month` never appears anywhere in the shard log — the model never discovered the correct boost month type, despite the compiler's "did you mean 'months'" hint and the test's own `boost::gregorian::May` usage pointing at `boost::date_time::months_of_year` / `date::month_type`.
- Session metadata: `num_error_outputs: 1`, `num_user_asks: 5`, `num_exhausted_context_windows: 1` (failure-log lines 62250-62253, source 52780-52782); 95,958 prompt tokens, 25,819 completion tokens, duration 815.6s (failure-log lines 62247-62248, source 52777/52788-52789).
- Terminal state: `make: *** [Makefile:91: all] Error 2` (failure-log line 62230, source 52759-52761), "Tests failed: …/practice/meetup" (failure-log line 62235, source 52764), `"tests_outcomes": [false, false]` (failure-log lines 62242-62245, source 52772-52775).

Inference (root cause): attempt 2 shows partial recovery — the model can infer a class API from compiler errors — but it lacked (a) concrete `boost::date_time` type knowledge (`greg_month`/`date::month_type` vs the nonexistent `boost::gregorian::month`), (b) const-correctness discipline (the tests construct `const` objects; every method must be const), and (c) honest error-driven repair: in the fix loop it invented errors not present in the log, produced an empty patch, and rubber-stamped code that the compiler had already rejected.

## 4. Knowledge / Capability Gaps

- G1 — Hidden-test API anticipation / class-shaped API design. With empty starter namespaces, the model fabricates a "standard" free-function string API instead of a typed class API (section 3, attempt 1: failure-log lines 60609, 60622, 61157).
- G2 — Boost date_time vocabulary. The model used the nonexistent `boost::gregorian::month` type and never corrected it to `boost::gregorian::greg_month` / `boost::date_time::months_of_year` / `boost::gregorian::date::month_type`, even with the compiler suggesting `months` (shard lines 50042-50046; `greg_month` absent from the entire log). It also never used the purpose-built generators (`nth_day_of_the_week_in_month`, `first_day_of_the_week_after`, …) the reference relies on.
- G3 — Const-correctness. All 42 methods were declared non-const while tests call them on a `const meetup::scheduler`; the compiler emitted hundreds of "discards qualifiers" errors and the model never added a single `const` (failure-log lines 62011-62016, 62074-62079).
- G4 — Error-driven repair honesty. In "# Fix any errors" rounds the model hallucinated faults (weekday case-sensitivity, `struct tm` visibility, `date_from_tm` signature), emitted an empty diff, and declared compiler-rejected code "correct" (failure-log line 61506; shard lines 17699-17714, 46611-46613).
- G5 — Whole-file format contract. Both attempt-1 listings were ` ```diff ` hunks despite the explicit whole-file rule in the system prompt (failure-log lines 61166-61190 vs 60555-60572). The harness tolerated it here; against a strict parser this is an automatic fail.
- G6 — Compiler-diagnostic triage. `candidate expects 0 arguments, 2 provided` + `expected ')' before 'month'` point squarely at the constructor declaration line, yet the model chased unrelated theories for five user-ask rounds (shard lines 50042-50060; failure-log lines 62024-62034).

Note on prompt/exporter quirk (not the failure cause): the instruction "Only use standard libraries" conflicts with the mandatory Boost test dependency; the model noticed and reasonably prioritized the compiler evidence (shard lines 12610-12630). Worth flagging to the exporter owners, but attempts failed on API/type/const errors, not on this conflict.

## 5. SFT Task Specifications

Answer-blind: none of these reuse the meetup story, its test fixtures, or the reference's 42-method `scheduler` API. Each teaches one gap with a distinct domain wrapper.

### Spec 01: whole-file-listing-clock-display
- Files: `clock_face.cpp`, `clock_face.h` (test file: `clock_face_test.cpp`)
- API: `namespace clock_face; std::string render(int hour, int minute);`
- Prompt shape: two starter files with an empty `clock_face` namespace; ask for a 24-hour "HH:MM" renderer. Starter state: empty namespace in both files.
- Target capability: G5 — respond with complete file listings (filename line + fenced whole content), never diff fences or elisions.
- Target answer shape: two whole-file listings; declaration in `.h`, definition in `.cpp`; only `<string>` include.
- Difficulty / variation: trivial logic isolates pure format discipline.

### Spec 02: whole-file-listing-ticket-price
- Files: `fare.cpp`, `fare.h` (test file: `fare_test.cpp`)
- API: `namespace fare; double price(int age, bool is_member);`
- Prompt shape: transit fare rules story; starter `.h` has an outdated signature the model must replace — forcing a full rewrite of both files.
- Target capability: G5 — whole-file replacement discipline when the entire content changes (no ` ```diff `, no "// rest unchanged").
- Target answer shape: two complete listings with matching guards/includes.
- Difficulty / variation: tempts diff-style output because only a few lines differ; correct answer still rewrites everything.

### Spec 03: header-impl-split-recipe-scaler
- Files: `recipe.cpp`, `recipe.h` (test file: `recipe_test.cpp`)
- API: `namespace recipe; class scaler { public: explicit scaler(double factor); double quantity(double base) const; private: double factor_; };`
- Prompt shape: kitchen recipe scaling; starter files contain only include guards and an empty namespace.
- Target capability: header/impl separation — class declaration + member declarations in `.h`, out-of-line definitions in `.cpp` inside the same namespace.
- Target answer shape: `.h` with guard, class body, no definitions; `.cpp` with `#include "recipe.h"` and `scaler::` definitions.
- Difficulty / variation: single-translation-unit temptation to inline everything; tests link against the `.cpp`.

### Spec 04: header-impl-split-parking-meter
- Files: `parking.cpp`, `parking.h` (test file: `parking_test.cpp`)
- API: `namespace parking; class meter { public: meter(int rate_cents, int max_minutes); int cost(int minutes) const; bool exceeds(int minutes) const; private: int rate_cents_; int max_minutes_; };`
- Prompt shape: city parking meter fees; empty-namespace starter.
- Target capability: header/impl separation plus private state initialized via ctor initializer list in the `.cpp`.
- Target answer shape: two whole-file listings; definitions qualified `meter::`.
- Difficulty / variation: two accessors forces disciplined declaration/definition pairing.

### Spec 05: class-api-library-rooms
- Files: `rooms.cpp`, `rooms.h` (test file: `rooms_test.cpp`)
- API: `namespace rooms; class booking_calendar { public: booking_calendar(int year, int month); int first_open_day(int weekday) const; int last_open_day(int weekday) const; private: int year_; int month_; };`
- Prompt shape: library study-room booking; empty starter, instructions describe "first/last <weekday> of a month" without naming an API.
- Target capability: G1 — when the starter is an empty namespace, design a small typed class (constructor carries context; methods answer queries) instead of a bag-of-strings free function.
- Target answer shape: class with typed `int` params, const query methods, header/impl split.
- Difficulty / variation: instructions give examples but no signature; model must infer a clean class shape.

### Spec 06: class-api-gym-schedule
- Files: `gym.cpp`, `gym.h` (test file: `gym_test.cpp`)
- API: `namespace gym; enum class weekday { monday, tuesday, wednesday, thursday, friday, saturday, sunday }; class class_schedule { public: class_schedule(int year, int month); int nth_session(weekday day, int n) const; private: int year_; int month_; };`
- Prompt shape: gym class timetable ("3rd Tuesday spin class"); empty starter.
- Target capability: G1 — introduce a scoped enum for weekday instead of parsing weekday strings.
- Target answer shape: enum + class declared in `.h`, `nth_session` defined in `.cpp` with wrap-around offset math.
- Difficulty / variation: adds an enum type the model must place correctly (header, inside namespace).

### Spec 07: const-correct-museum-pass
- Files: `museum.cpp`, `museum.h` (test file: `museum_test.cpp`)
- API: `namespace museum; class pass { public: pass(int year, int month); bool valid_on(int day) const; int days_remaining(int day) const; private: int year_; int month_; };`
- Prompt shape: museum monthly pass validity; the stated usage is `const museum::pass p{2024, 6};`.
- Target capability: G3 — every query method must be `const` because the client object is const.
- Target answer shape: `const` on both methods in declaration and definition; members declared `const` where immutable.
- Difficulty / variation: prompt shows const-client usage explicitly; hidden tests instantiate const objects.

### Spec 08: const-correct-solar-billing
- Files: `solar.cpp`, `solar.h` (test file: `solar_test.cpp`)
- API: `namespace solar; class invoice { public: invoice(int year, int month); int billing_days() const; double daily_rate() const; double total() const; private: int year_; int month_; };`
- Prompt shape: solar lease billing; `total()` is specified to be implemented by calling the other two member functions.
- Target capability: G3 — const method calling sibling const methods; reinforces that non-const siblings break const callers.
- Target answer shape: all three methods const; `total()` delegates.
- Difficulty / variation: delegation chain makes a single missing `const` cascade into compile errors.

### Spec 09: boost-date-holiday-finder
- Files: `holiday.cpp`, `holiday.h` (test file: `holiday_test.cpp`)
- API: `namespace holiday; boost::gregorian::date observed(int year, boost::gregorian::date::month_type month, int day);`
- Prompt shape: holiday observance shifting; Boost is installed and the prompt states the test uses `boost::gregorian::date`.
- Target capability: G2 — correct boost date types: `boost::gregorian::date`, constructor `{year, month, day}`, and `date::month_type` as the month parameter type (never a made-up `boost::gregorian::month`).
- Target answer shape: `.h` includes `<boost/date_time/gregorian/gregorian.hpp>`; free function with exact types.
- Difficulty / variation: introduces the month-type pitfall head-on.

### Spec 10: boost-month-type-lease-start
- Files: `lease.cpp`, `lease.h` (test file: `lease_test.cpp`)
- API: `namespace lease; class term { public: term(boost::gregorian::date::month_type month, boost::gregorian::date::year_type year); boost::gregorian::date start() const; boost::gregorian::date end() const; private: boost::gregorian::date::month_type month_; boost::gregorian::date::year_type year_; };`
- Prompt shape: apartment lease terms; tests construct with `boost::gregorian::Jan` style constants.
- Target capability: G2 — constructor/member typing with `date::month_type` and `date::year_type`; brace-init compatibility with boost month constants.
- Target answer shape: class with boost-typed members, const accessors, header/impl split.
- Difficulty / variation: mirrors the constructor-typing failure mode of the diagnosed task in a new story.

### Spec 11: boost-nth-weekday-trash-pickup
- Files: `pickup.cpp`, `pickup.h` (test file: `pickup_test.cpp`)
- API: `namespace pickup; boost::gregorian::date nth_weekday(boost::gregorian::date::year_type year, boost::gregorian::date::month_type month, boost::date_time::weekdays day, int n);` throws `std::invalid_argument` if `n < 1 || n > 4`.
- Prompt shape: municipal trash pickup ("2nd Wednesday"); Boost available.
- Target capability: G2 — use `boost::gregorian::nth_day_of_the_week_in_month` instead of hand-rolled mktime arithmetic.
- Target answer shape: one function in `.cpp` delegating to the boost generator; validation throws.
- Difficulty / variation: adds an exception policy on top of the generator usage.

### Spec 12: boost-last-weekday-payday
- Files: `payday.cpp`, `payday.h` (test file: `payday_test.cpp`)
- API: `namespace payday; boost::gregorian::date last_weekday_of_month(boost::gregorian::date::year_type year, boost::gregorian::date::month_type month, boost::date_time::weekdays day);`
- Prompt shape: payroll "last Friday of the month" story.
- Target capability: G2 — `boost::gregorian::last_day_of_the_week_in_month` and its `.get_date(year)` call pattern.
- Target answer shape: small function delegating to the generator; correct header include.
- Difficulty / variation: "last" semantics differ from "nth"; teaches a second generator.

### Spec 13: boost-first-after-clinic
- Files: `clinic.cpp`, `clinic.h` (test file: `clinic_test.cpp`)
- API: `namespace clinic; boost::gregorian::date first_after(const boost::gregorian::date& anchor, boost::date_time::weekdays day);`
- Prompt shape: clinic follow-up visits ("first Monday after the 12th").
- Target capability: G2 — `boost::gregorian::first_day_of_the_week_after` with an anchor date; strict-after semantics.
- Target answer shape: function building the generator from the anchor and calling `.get_date(anchor)`.
- Difficulty / variation: strict-after vs on-or-after distinction is the tested edge.

### Spec 14: boost-teenth-window-reunion
- Files: `reunion.cpp`, `reunion.h` (test file: `reunion_test.cpp`)
- API: `namespace reunion; boost::gregorian::date mid_month_day(boost::gregorian::date::year_type year, boost::gregorian::date::month_type month, boost::date_time::weekdays day);` — the given weekday falling on days 13–19.
- Prompt shape: alumni reunion always in the "13th–19th" window.
- Target capability: G2 + edge reasoning — implement a day-range window (13–19) using boost generators or a checked loop over `boost::gregorian::date`.
- Target answer shape: function selecting the unique matching date in the window.
- Difficulty / variation: window semantics without using the benchmark's story or method names.

### Spec 15: leap-year-garden-planner
- Files: `garden.cpp`, `garden.h` (test file: `garden_test.cpp`)
- API: `namespace garden; int days_in_month(int year, int month);` throws `std::out_of_range` if `month < 1 || month > 12`.
- Prompt shape: planting-calendar day counts.
- Target capability: G6-adjacent edge-case reasoning — Gregorian leap rule (divisible by 4, except centuries unless by 400).
- Target answer shape: compact function; February branch with full century rule; throw on bad month.
- Difficulty / variation: century years (1900 vs 2000) are the discriminating cases.

### Spec 16: weekday-offset-bakery
- Files: `bakery.cpp`, `bakery.h` (test file: `bakery_test.cpp`)
- API: `namespace bakery; int nth_weekday_of_month(int year, int month, int weekday, int n);` — weekday 0=Sunday..6=Saturday, n in 1..4; returns day-of-month.
- Prompt shape: bakery delivery schedule without any date library.
- Target capability: edge-case reasoning — `(target - first + 7) % 7` wrap-around offset math done correctly.
- Target answer shape: pure arithmetic implementation with the wrap-safe modulo; no library.
- Difficulty / variation: months starting on/after the target weekday exercise both modulo branches.

### Spec 17: last-weekday-warehouse
- Files: `warehouse.cpp`, `warehouse.h` (test file: `warehouse_test.cpp`)
- API: `namespace warehouse; int last_weekday_of_month(int year, int month, int weekday);`
- Prompt shape: warehouse inventory count on the last given weekday; no date library.
- Target capability: edge-case reasoning — walk backward from month end with correct month-length handling (uses leap logic internally).
- Target answer shape: backward loop or arithmetic from `days_in_month`; correct for 28/29/30/31-day months.
- Difficulty / variation: February leap years are the hidden discriminator.

### Spec 18: diagnostic-bad-type-name
- Files: `ferry.cpp`, `ferry.h` (test file: `ferry_test.cpp`)
- API: `namespace ferry; boost::gregorian::date next_sailing(boost::gregorian::date::month_type month, int day);`
- Prompt shape: ferry timetable. Two-turn: turn 1 asks for the function; the seeded first answer (shown in prompt history) used a fictional `boost::gregorian::month` type; turn 2 supplies the compiler error `error: 'month' in namespace 'boost::gregorian' does not name a type; did you mean 'months'`.
- Target capability: G6 + G2 — read the exact "does not name a type" diagnostic and replace the bogus type with a real one (`date::month_type` or `greg_month`).
- Target answer shape: whole-file listings with only the type corrected; no other churn.
- Difficulty / variation: the fix is one type name; tests penalize unrelated edits.

### Spec 19: diagnostic-discards-qualifiers
- Files: `gallery.cpp`, `gallery.h` (test file: `gallery_test.cpp`)
- API: `namespace gallery; class exhibit { public: exhibit(int year, int month); int opening_day() const; int closing_day() const; private: int year_; int month_; };`
- Prompt shape: art-gallery exhibit dates. Two-turn: seeded first answer declares the methods non-const; turn 2 supplies `error: passing 'const gallery::exhibit' as 'this' argument discards qualifiers [-fpermissive]`.
- Target capability: G6 + G3 — map "discards qualifiers" to "add `const` to the member function" in both declaration and definition.
- Target answer shape: whole-file listings with `const` added consistently; nothing else changed.
- Difficulty / variation: error repeated for every method; the repair must fix all of them, not just the first.

### Spec 20: diagnostic-ctor-candidate-mismatch
- Files: `cinema.cpp`, `cinema.h` (test file: `cinema_test.cpp`)
- API: `namespace cinema; class festival { public: festival(int year, int month); int opening_weekend() const; private: int year_; int month_; };`
- Prompt shape: film-festival scheduling. Two-turn: seeded first answer's constructor declaration is syntactically ill-formed (bad parameter type), so the compiler reports `no matching function for call … candidate expects 0 arguments, 2 provided`; turn 2 supplies that output.
- Target capability: G6 — connect "candidate expects 0 arguments, 2 provided" to an ill-formed constructor declaration (the declaration was dropped), not to the call site.
- Target answer shape: corrected constructor declaration + definition; whole files.
- Difficulty / variation: teaches the indirect diagnostic where the real error is earlier in the log.

### Spec 21: diagnostic-missing-include
- Files: `observatory.cpp`, `observatory.h` (test file: `observatory_test.cpp`)
- API: `namespace observatory; boost::gregorian::date next_full_moon_estimate(boost::gregorian::date::month_type month, int year);`
- Prompt shape: observatory event calendar. Two-turn: seeded first answer uses `boost::gregorian::date` in the header without including the boost header; turn 2 supplies `error: 'date' in namespace 'boost::gregorian' does not name a type`.
- Target capability: G6 — recognize a missing-include diagnostic and add the include to the header (self-contained headers).
- Target answer shape: `.h` gains `#include <boost/date_time/gregorian/gregorian.hpp>`; `.cpp` unchanged or minimal.
- Difficulty / variation: distinguishes header self-containment from cpp-only includes.

### Spec 22: edge-month-boundary-campsite
- Files: `campsite.cpp`, `campsite.h` (test file: `campsite_test.cpp`)
- API: `namespace campsite; int checkout_day(int year, int month, int weekday, int n);` — nth given weekday, must never roll past month end; throws `std::out_of_range` if the nth weekday does not exist.
- Prompt shape: campsite reservation rules.
- Target capability: edge cases — nth-weekday overflow past month length must be detected, not silently wrapped.
- Target answer shape: arithmetic + explicit bound check against month length; throw on overflow.
- Difficulty / variation: "5th Monday exists only sometimes" forces the guard.

### Spec 23: edge-teenth-window-festival
- Files: `festival.cpp`, `festival.h` (test file: `festival_test.cpp`)
- API: `namespace festival; int mid_month_weekday(int year, int month, int weekday);` — unique day in 13..19 matching weekday.
- Prompt shape: music festival always mid-month; no date library.
- Target capability: edge cases — prove uniqueness inside a 7-day window and compute without overflow into the next month.
- Target answer shape: small loop over 13..19 with weekday computed by anchor math.
- Difficulty / variation: months where the 13th itself is the target weekday (boundary hit).

### Spec 24: edge-century-leap-anniversary
- Files: `anniversary.cpp`, `anniversary.h` (test file: `anniversary_test.cpp`)
- API: `namespace anniversary; bool is_leap(int year); int founding_day_count(int year);`
- Prompt shape: town founding anniversary counts.
- Target capability: edge cases — 1900 not leap, 2000 leap, 2100 not leap.
- Target answer shape: canonical `(y % 4 == 0 && y % 100 != 0) || y % 400 == 0`.
- Difficulty / variation: pure century-rule drilling.

### Spec 25: repair-honest-nofix-lighthouse
- Files: `lighthouse.cpp`, `lighthouse.h` (test file: `lighthouse_test.cpp`)
- API: `namespace lighthouse; int beam_cycle_day(int year, int month);`
- Prompt shape: lighthouse maintenance. Two-turn: turn 1 answer is actually correct; turn 2 is a bare "# Fix any errors below, if possible." with no error text.
- Target capability: G4 — when no error is shown and the code is correct, state that and re-emit the unchanged whole files; do not invent faults.
- Target answer shape: brief statement + identical whole-file listings.
- Difficulty / variation: directly counter-trains the hallucinated-case-sensitivity behavior seen in attempt 1's fix round.

### Spec 26: repair-no-empty-patch-harbor
- Files: `harbor.cpp`, `harbor.h` (test file: `harbor_test.cpp`)
- API: `namespace harbor; class tide_table { public: explicit tide_table(int month); int high_tide_day(int n) const; private: int month_; };`
- Prompt shape: harbor tide tables. Two-turn: seeded first answer has a genuine but small bug (wrong month-length table); turn 2 shows a failing assertion.
- Target capability: G4 — a repair turn must contain a real, minimal code change; an empty diff or "the code looks correct" is never acceptable when a failure receipt exists.
- Target answer shape: whole files with exactly the faulty table/logic corrected.
- Difficulty / variation: counter-trains the empty-diff turn observed in attempt 2.

### Spec 27: repair-read-the-first-error-vineyard
- Files: `vineyard.cpp`, `vineyard.h` (test file: `vineyard_test.cpp`)
- API: `namespace vineyard; class harvest { public: harvest(int year, int month); int first_pick(int weekday) const; private: int year_; int month_; };`
- Prompt shape: vineyard harvest scheduling. Two-turn: seeded first answer has two defects (non-const method AND a misspelled type); turn 2 supplies a long compiler log whose first error is the misspelled type.
- Target capability: G4 + G6 — fix errors in log order; understand that cascading "no matching function" errors originate from the first ill-formed declaration.
- Target answer shape: both defects fixed in one whole-file pass.
- Difficulty / variation: long noisy log; tests reward fixing root cause first.

### Spec 28: repair-add-missing-method-aquarium
- Files: `aquarium.cpp`, `aquarium.h` (test file: `aquarium_test.cpp`)
- API: `namespace aquarium; class feed_schedule { public: feed_schedule(int year, int month); int morning_feed(int weekday) const; int evening_feed(int weekday) const; private: int year_; int month_; };`
- Prompt shape: aquarium feeding times. Two-turn: seeded first answer omits `evening_feed`; turn 2 supplies `error: 'class aquarium::feed_schedule' has no member named 'evening_feed'`.
- Target capability: G4 — extend both header and cpp consistently when adding a missing member.
- Target answer shape: declaration + definition added; const preserved.
- Difficulty / variation: header/impl co-update under repair pressure.

### Spec 29: contrastive-string-api-vs-typed-api-bookclub
- Files: `bookclub.cpp`, `bookclub.h` (test file: `bookclub_test.cpp`)
- API: `namespace bookclub; enum class week { first, second, third, fourth, last }; enum class weekday { monday, tuesday, wednesday, thursday, friday, saturday, sunday }; class session_calendar { public: session_calendar(int year, int month); int session_day(week w, weekday d) const; private: int year_; int month_; };`
- Prompt shape: book-club meeting dates. The prompt history shows a rejected prior answer using `std::tm session_day(const std::string& week, const std::string& weekday, …)` with reviewer feedback "stringly-typed, wrong shape".
- Target capability: G1 (contrastive) — typed enums + class over string-parsing free function.
- Target answer shape: enum-driven class API; no string parameters anywhere.
- Difficulty / variation: explicit wrong-vs-right contrast in the prompt.

### Spec 30: contrastive-mktime-vs-generators-rail
- Files: `rail.cpp`, `rail.h` (test file: `rail_test.cpp`)
- API: `namespace rail; boost::gregorian::date third_service_day(boost::gregorian::date::year_type year, boost::gregorian::date::month_type month, boost::date_time::weekdays day);`
- Prompt shape: heritage-railway service days; Boost available. Prompt history shows a rejected `std::mktime`-based answer with feedback "timezone-dependent, fragile".
- Target capability: G2 (contrastive) — boost date generators over `std::tm`/`std::mktime` calendar hacking.
- Target answer shape: single delegation to `nth_day_of_the_week_in_month`.
- Difficulty / variation: teaches why mktime normalization is the wrong tool.

### Spec 31: boost-date-equality-orchard
- Files: `orchard.cpp`, `orchard.h` (test file: `orchard_test.cpp`)
- API: `namespace orchard; class picking_window { public: picking_window(boost::gregorian::date start, boost::gregorian::date end); bool contains(const boost::gregorian::date& d) const; private: boost::gregorian::date start_; boost::gregorian::date end_; };`
- Prompt shape: orchard u-pick season windows.
- Target capability: G2 — boost date comparison operators and value semantics (tests compare with `==` against expected dates).
- Target answer shape: comparisons via `<`/`==` on `boost::gregorian::date`; const method.
- Difficulty / variation: value-type date handling without tm conversion.

### Spec 32: hidden-test-api-inference-planetarium
- Files: `planetarium.cpp`, `planetarium.h` (test file: `planetarium_test.cpp`)
- API: `namespace planetarium; class show_calendar { public: show_calendar(int year, int month); int premiere_day() const; int encore_day() const; private: int year_; int month_; };`
- Prompt shape: planetarium show dates; starter is an empty namespace; instructions give worked examples but no signature, and state "do not change names referenced by other code".
- Target capability: G1 — infer a conservative, small, const-correct class API from prose + examples instead of inventing string-based signatures.
- Target answer shape: minimal class with typed params and const methods.
- Difficulty / variation: no explicit API in the prompt at all; graded on shape judgment.

### Spec 33: exception-policy-nth-validity-market
- Files: `market.cpp`, `market.h` (test file: `market_test.cpp`)
- API: `namespace market; int stall_day(int year, int month, int weekday, int n);` throws `std::invalid_argument` when `n < 1 || n > 5`, `std::out_of_range` when the nth weekday doesn't occur in the month.
- Prompt shape: farmers-market stall allocation.
- Target capability: exception policy — two distinct standard exceptions with precise throw conditions, documented in the header comment.
- Target answer shape: validation-first implementation; throws before arithmetic.
- Difficulty / variation: distinguishes domain-error (`invalid_argument`) from range-error (`out_of_range`).

### Spec 34: exception-policy-bad-month-theater
- Files: `theater.cpp`, `theater.h` (test file: `theater_test.cpp`)
- API: `namespace theater; class season { public: season(int year, int month); int opening_night(int weekday) const; private: int year_; int month_; };` constructor throws `std::out_of_range` if `month < 1 || month > 12`.
- Prompt shape: theater season openings.
- Target capability: exception policy in a constructor + const-correct query (G3 cross-cover).
- Target answer shape: throwing ctor with initializer list; const method; header/impl split.
- Difficulty / variation: validation inside a constructor rather than a free function.

### Spec 35: format-multi-file-full-rewrite-canal
- Files: `canal.cpp`, `canal.h` (test file: `canal_test.cpp`)
- API: `namespace canal; class lock_schedule { public: lock_schedule(int year, int month); int first_transit(int weekday) const; int last_transit(int weekday) const; private: int year_; int month_; };`
- Prompt shape: canal lock transit days. The seeded conversation includes a prior turn where the model emitted ` ```diff ` hunks and the harness rejected them with "could not parse edit"; the model must re-emit.
- Target capability: G5 — recover from a format rejection by emitting strict whole-file listings.
- Target answer shape: two complete listings, correct fence usage, no prose between filename and fence.
- Difficulty / variation: format recovery after an explicit parser rejection.

### Spec 36: const-and-enum-zoo-feedings
- Files: `zoo.cpp`, `zoo.h` (test file: `zoo_test.cpp`)
- API: `namespace zoo; enum class weekday { monday, tuesday, wednesday, thursday, friday, saturday, sunday }; class feeding_plan { public: feeding_plan(int year, int month); int big_cats(weekday d) const; int reptiles(weekday d) const; private: int year_; int month_; int nth(int n, weekday d) const; };`
- Prompt shape: zoo feeding rotations ("big cats feed every 2nd and 4th <weekday>"); const client usage stated.
- Target capability: G3 + G1 combined — private const helper shared by public const methods; enum-typed parameters.
- Target answer shape: private helper `nth` declared const and defined once; publics delegate.
- Difficulty / variation: introduces a private-helper pattern; a non-const helper breaks both publics.

## 6. Acceptance & Validation Gates

For every row built from the specs above, before inclusion in SFT:

1. Parser validity: the assistant turn must parse under the Aider whole-file listing grammar — filename line, fenced block, complete content; zero diff fences, zero elision comments (`grep -c 'rest of' / '...'` must be 0 inside listings).
2. Compile + test receipts: each task ships its own Catch2 tests; the row is admitted only with a clean `cmake && make && ./<task>` receipt in the benchmark Docker image (Boost 1.83 available for boost specs).
3. Hidden-edge coverage: tests must include the spec's discriminating edge (century leap, month-end overflow, strict-after, 13–19 window boundaries) and at least one const-object instantiation for class specs.
4. Const-correctness probe: for every class spec, a compile probe constructs the object as `const` and calls every public method; the build must succeed.
5. Contamination check: prompt text, test names, and API identifiers must not match `polyglot-benchmark` meetup (or any exercise) fixtures — no `meetup::scheduler`, no `monteenth`/`first_monday`-style 42-method API, no copied test cases.
6. Repair-turn honesty: for two-turn repair specs, the second turn must change exactly the lines implicated by the supplied error log; rows whose repair rewrites unrelated code or emits empty diffs are rejected.
7. Whole-file rule: both files must be listed in full on every turn that changes them, matching the benchmark's edit-format contract.

## 7. Cross-Check Statement (2026-07-24)

Performed after drafting:

- Re-read via `sed` every failure-log line range cited: 60545-60592 (header/outcomes `[False, False]`, shard 1), 60555-60572 (whole-file format rules), 60609/60622/61157 (attempt-1 API invention quotes), 61166-61190 (diff fences), 61242 (Applied edit), 61248-61258 (Fix-any-errors turn), 61506/61591-61597/61607 (hallucinated case-sensitivity fix), 61742-61745 ('scheduler' does not name a type), 62011-62016 and 62074-62079 (discards-qualifiers errors), 62024-62034 (ctor candidate errors), 62230-62253 (make failure, Tests failed, JSON metadata), 62242-62245 (tests_outcomes [false,false]). All quotes and line numbers confirmed accurate.
- Re-read shard-log anchors: 4210-4211, 6776-6783, 7953, 12442-12527, 12673-12720, 14590-14689, 17699-17714, 46559-46613, 50042-50060, 52455-52510, 52755-52817. Confirmed: `boost::gregorian::month` type error at 50042/50046; methods non-const in the final state (52503-52516); `greg_month` absent from the entire shard log (grep, zero matches).
- Re-checked every API claim against ground truth: `.meta/example.h` (constructor at lines 12-13 with `boost::gregorian::date::month_type`/`year_type`; 42 const methods at lines 18-190; no exceptions); `meetup_test.cpp:17,19-20` (const construction, `boost::gregorian::May`, date equality); 90 TEST_CASEs (grep -c); `CMakeLists.txt:14` (Boost date_time REQUIRED). Confirmed `.meta/example.cpp` does not exist — the reference is header-only (`example.h` is present and authoritative; not a missing-reference case).
- Confirmed outcome array `[False, False]` and shard 1 match both the section header (failure-log lines 60547-60550) and the result JSON (source lines 52772-52775).
- Corrections made during cross-check: (1) initially drafted "example.cpp missing — reported as ground-truth problem"; corrected after finding the reference is intentionally header-only (`example.h` present, CMake supports header-only), so it is not a defect. (2) Tightened the attempt-2 narrative to note the ill-formed constructor declaration was dropped by the compiler (hence "expects 0 arguments"), rather than implying the model omitted the constructor. (3) Added the prompt/exporter "standard libraries only" conflict note after re-reading shard lines 12610-12630.
