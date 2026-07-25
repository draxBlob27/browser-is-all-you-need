# gigasecond — Failure Learning Document

Date of analysis: 2026-07-24. Eval run: `glm47-aider-expansion-sft-fixed26-20260723T091839Z` (GLM-4.7 SFT, Aider Polyglot C++, whole edit format).

## 1. Task Identity & Evidence Pointers

- Task slug: `gigasecond`
- Shard: `0`
- Test outcomes: `[False, False]` (attempt 1 FAIL, attempt 2 FAIL)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md`, lines 14369–15623 (header at 14369–14374; reconstructed prompt at 14376–14416; attempt-1 chunk at 15124–15490; terminal test log at 15492–15621).
- **Interleaved foreign content:** "Attempt/log chunk 1, source lines 15825-16524" (failure log 14419–15123) contains **zero** occurrences of `gigasecond`; its thinking is about `diamond.h`/`diamond.cpp` and `diamond::rows(letter)` (e.g. failure log 14396–14401, quoting shard 15828–15831). It belongs to a different task interleaved in shard 0 and is disregarded below.
- Raw shard log (cross-check evidence): `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log`. The failure log's quoted "source lines" (26057–26419, 52633–52757) are line numbers in this shard log. Gigasecond turns are interleaved there with other tasks (allergies, kindergarten-garden, crypto-square, clock, binary-search-tree, complex-numbers, circular-buffer); all line attributions below were checked to be gigasecond content.
- Attempt-1 gigasecond turns (shard): initial answer 26320–26399 (diff fences at 26335, 26356); reflection prompt 26401–26419; `struct DateTime` fix 30114–30175; rumination turns ending 37496 and 42008 (`Applied edit to gigasecond.h`); `Only 3 reflections allowed, stopping.` at 42036; attempt-1 test run 42097–42166 (`'advance' is not a member of 'gigasecond'`).
- Attempt-2 gigasecond turns (shard): error-driven rename `add`→`advance` at 47690–47847; reflection turns 49708–50064, 51619–51681, 51892, 52442–52594; final answer 52600–52617; terminal test run 52633–52697.
- Ground truth (read-only): `polyglot-benchmark/cpp/exercises/practice/gigasecond/`
  - Reference: `.meta/example.h`, `.meta/example.cpp`
  - Tests: `gigasecond_test.cpp`
  - Starters (NOT the solution): `gigasecond.cpp`, `gigasecond.h` at the exercise root (empty `namespace gigasecond {}` in both).
- Existing analog dir: none for gigasecond under `aider-fixed26-analogs/` (granularity reference: `aider-fixed26-analogs/fixed26-b001-all-your-base/`).
- Result JSON (failure log 15565–15621 / shard 52699–52757): `"tests_outcomes": [false, false]`, `"num_error_outputs": 0`, `"num_user_asks": 8`, `"num_exhausted_context_windows": 0`, `"num_malformed_responses": 0`, `"edit_format": "whole"`.

## 2. Benchmark Contract (Ground Truth)

File set: `gigasecond.h` + `gigasecond.cpp`, namespace `gigasecond`. **No exception policy** — the contract throws nothing.

Public API (from `.meta/example.h`):

- `.meta/example.h:4` — `#include <boost/date_time/posix_time/posix_time.hpp>` in the header (the header is Boost-dependent by design).
- `.meta/example.h:9` — `boost::posix_time::ptime advance(const boost::posix_time::ptime& start);` — a **free function** named `advance`, parameter and return both `boost::posix_time::ptime` (by const-ref in, by value out). There is **no user-defined `DateTime` type anywhere** in the contract.

Implementation (from `.meta/example.cpp`):

- `.meta/example.cpp:6-9` — the entire body is `return start + boost::posix_time::seconds(1000000000);` — one line of Boost date_time arithmetic; no `std::tm`, no `mktime`, no `time_t`.

Enforced by `gigasecond_test.cpp`:

- `gigasecond_test.cpp:9` — `// This problem requires you to install and use the boost date_time library.` (the Boost requirement is documented in the test file the model never sees).
- `gigasecond_test.cpp:15` — `using namespace boost::posix_time;`.
- `gigasecond_test.cpp:19-23` — first active test: `gigasecond::advance(time_from_string("2011-04-25 00:00:00"))` must equal `time_from_string("2043-01-01 01:46:40")`. The argument is a `boost::posix_time::ptime` produced by `time_from_string`, so any parameter type other than `ptime` (or something implicitly convertible from it) is a compile error.
- `gigasecond_test.cpp:26-60` — four more cases under `EXERCISM_RUN_ALL_TESTS`: date-only inputs (`1977-06-13`, `1959-07-19`), full-time (`2015-01-24 22:00:00` → `2046-10-02 23:46:40`), and a day-roll-over edge (`2015-01-24 23:59:59` → `2046-10-03 01:46:39`). All go through `gigasecond::advance(...)` and compare `ptime` equality.

Edge cases: day roll-over at 23:59:59 (`:53-60`), midnight inputs (`:17-24`), ~31.7-year span crossing many leap years — all handled for free by Boost date arithmetic; a `localtime`-based implementation risks timezone-dependent wrong answers even if it compiles.

Output-format constraints: Aider *whole* edit format — filename line, opening fence, **entire file content**, closing fence; no diff hunks, no elisions (system prompt, failure log 14379–14401; restated in the user instructions, failure log 14408–14414).

## 3. Failure Anatomy

### Attempt 1 — hallucinated `DateTime` type, wrong function name, diff-format output, compile failure

**Turn 1 (failure log 15124–15490, shard source lines 26057–26419).** The starter files are empty namespaces, so the model had to guess the API. It guessed wrong on every axis. From its thinking:

> `26084: track is `DateTime add(const DateTime& dt)`.`
> (failure log 15154, quoting shard 26084)

> `26236:     *   *Edge Case:* What if `DateTime` is not defined? If the user doesn't have`
> `26237: the test suite, this code won't compile. But the prompt says "referenced from`
> `26238: other code like unit tests". So I must rely on the test suite defining`
> `26239: `DateTime`.`
> (failure log 15306–15309)

So the model (a) invented the signature `DateTime add(const DateTime& dt)` — wrong name (`add` vs `advance`) and wrong type (a nonexistent `DateTime` vs `boost::posix_time::ptime`); (b) explicitly assumed the test suite would define `DateTime`; and (c) implemented the body with `std::tm`/`std::mktime`/`std::localtime` (shard 26278–26306; failure log 15348–15376) instead of Boost. Its answer also violated the whole-file format contract with unified-diff fences:

> `26335: ```diff`
> `26336: @@ -1,8 +1,13 @@`
> (failure log 15405–15406)

> `26345: +DateTime add(const DateTime& dt);`
> (failure log 15415)

Aider applied the diffs anyway (`Applied edit to gigasecond.h` / `.cpp`, shard 26398–26399) and issued a reflection prompt marking the declaration line (shard 26401–26415; failure log 15471–15485):

> `26401: # Fix any errors below, if possible.`
> `26411:   9█DateTime add(const DateTime& dt);`

**Reflection turns (shard 26419–42036).** Given only marked-line snippets (never compiler text), the model first — at shard 30114–30175 — talked itself into the exact opposite of its turn-1 assumption: it decided the error was that `DateTime` was undefined and **defined the struct itself**, again in a diff fence:

> `30153: -// The 'DateTime' type is expected to be defined elsewhere (e.g., in tests).`
> `30154: +// Definition of the DateTime struct`
> `30155: +struct DateTime {`

This contradicts its own turn-1 reasoning ("I must rely on the test suite defining `DateTime`", shard 26238) and makes the divergence from the contract permanent: now the header owns a type the tests know nothing about. Later reflection turns degraded into circular rumination — e.g. shard 37400–37496, where the model weighs "the code is valid" vs. "the user moved the struct" and concludes by simply re-emitting the same file (`Applied edit to gigasecond.h`, shard 37496; same again at 42008) — until the harness stopped it:

> `42036: Only 3 reflections allowed, stopping.`

**Attempt-1 test run (shard 42097–42166): compile failure.**

> `42099: /aider/gigasecond/gigasecond_test.cpp:20:21: error: ‘advance’ is not a member of ‘gigasecond’`
> `42100:    20 |         gigasecond::advance(time_from_string("2011-04-25 00:00:00"));`

The tests call `gigasecond::advance`; the model shipped `add`. Attempt 1 FAIL. (This error and the reflection turns are in the shard log; the failure log's gigasecond section only excerpts chunks 26057–26419 and the terminal log.)

### Attempt 2 — name fixed from compiler error, invented type kept, type-mismatch compile failure

**Turn 1 (shard 47690–47847).** Attempt 2's first prompt surfaced the attempt-1 compiler error, and the model correctly fixed the function name:

> `47710:     *   *Decision:* I need to rename the function `add` to `advance` to match`
> `47711: the test expectations.`

But it kept the invented type: `DateTime advance(const DateTime& dt);` (shard 47742, applied at 47846–47847). It read only half of the diagnostic — the error `error: 'advance' is not a member of 'gigasecond'` proved the name, but the very same error block quoted the call site `gigasecond::advance(time_from_string(...))`, and the model never asked what `time_from_string` returns.

**Reflection turns (shard 47868–52594).** Four more marked-line prompts (`18█DateTime advance(const DateTime& dt);`, shard 47868, 50085, 51892, 52584) produced long ruminations that circled the stale `'advance' is not a member` error (e.g. shard 49726–49749, 51626–51641, 52475–52513), repeatedly concluding the declaration was fine, and re-emitting the same API (`Applied edit to gigasecond.h` at 50064). The final answer still declared the invented type (shard 52600–52617):

> `52604: struct DateTime {`
> `52614: DateTime advance(const DateTime& dt);`

**Terminal test run (failure log 15492–15621, shard 52633–52697): compile failure, type mismatch on all 5 call sites.**

> `52657: /aider/gigasecond/gigasecond_test.cpp:20:45: error: invalid initialization of reference of type ‘const gigasecond::DateTime&’ from expression of type ‘boost::posix_time::ptime’`
> `52658:    20 |         gigasecond::advance(time_from_string("2011-04-25 00:00:00"));`
> (failure log 15521–15522)

> `52661: /aider/gigasecond/gigasecond.h:18:34: note: in passing argument 1 of ‘gigasecond::DateTime gigasecond::advance(const DateTime&)’`
> (failure log 15525)

(same pattern at shard 52665–52690 for test lines 30, 39, 47, 56 — failure log 15529–15554.) Attempt 2 FAIL. The compiler even told the model the true contract: the argument expression has type `boost::posix_time::ptime` — but this terminal error text was produced after the last model turn, so the model never saw it.

### Hard evidence vs. inference

Hard evidence: invented signature `DateTime add(const DateTime& dt)` (shard 26264/26345); `std::tm`/`mktime`/`localtime` implementation (shard 26278–26306); ```diff fences (shard 26335, 26356, 30153–30164); self-contradiction between "rely on the test suite defining `DateTime`" (shard 26238) and defining `struct DateTime` (shard 30155); reflection-stop at shard 42036; attempt-1 error `'advance' is not a member of 'gigasecond'` (shard 42099); rename decision (shard 47710–47711); final type-mismatch errors at all 5 test call sites (shard 52657–52690); result JSON `[false, false]`, `num_user_asks: 8` (shard 52704–52713).

Inference (root-cause categories): (a) the model imported a false "Exercism C++ Gigasecond uses a `DateTime` struct" prior — likely from other-language tracks or community solutions — instead of deriving the type from the C++ track's actual test calling convention; (b) with empty starter files and no visible tests, it treated "don't change names referenced from other code" as license to invent a type rather than as a hint that the signature must match unseen callers; (c) marked-line reflection prompts without compiler text led it to "fix" the only suspicious-looking thing (the unknown type name) in the wrong direction; (d) its reflection-loop behavior is rumination-then-reeemit, not hypothesis-driven change, so 8 user asks produced exactly two substantive edits (struct definition, rename), both insufficient.

## 4. Knowledge / Capability Gaps

- **G1 — Format-contract discipline (whole-file listings).** Every attempt-1 answer and the attempt-1 struct fix used ```` ```diff ```` unified-diff fences (shard 26335, 26356, 30153) despite the system prompt and user instructions demanding entire-file listings (failure log 14379–14401, 14408–14414).
- **G2 — API-shape discovery under hidden tests: never invent the parameter type.** The contract's parameter type is `boost::posix_time::ptime`, supplied by the test file (`gigasecond_test.cpp:15,19-20`). The model invented `struct DateTime` (shard 26264, 30155) — first assuming the tests would define it (shard 26238), then defining it itself (shard 30155) — guaranteeing a type-mismatch compile error at every call site (shard 52657–52690). It needed a rule for "empty starter + unseen callers": prefer standard/well-known library types visible in the domain, and treat an invented DTO as a last resort to flag, not ship.
- **G3 — Boost date_time knowledge (and the "standard libraries" misread).** The reference is one line: `start + boost::posix_time::seconds(1000000000)` (`.meta/example.cpp:8`). The model reasoned "Only use standard libraries" → `<ctime>`/`std::chrono` (shard 26079–26081, 26211–26215) and hand-rolled `mktime`/`localtime` conversion, which is both the wrong type ecosystem and (with `localtime`) timezone-fragile. It did not know, or did not consider, that Exercism's C++ track bundles Boost and that `ptime + seconds` is the idiomatic solution.
- **G4 — Repair/retry behavior on vague marked-line prompts.** On `# Fix any errors below, if possible.` prompts with only a █-marked line, the model ruminated for thousands of tokens and either re-emitted the same file (shard 37496, 42008, 50064) or made the one wrong guess available (define the struct, shard 30155). Attempt 1 burned all 3 reflections (`Only 3 reflections allowed, stopping.`, shard 42036) without ever changing the function name or type — the two things that were actually wrong.
- **G5 — Incomplete diagnostic extraction from compiler errors.** In attempt 2 the model correctly extracted "rename `add` → `advance`" from `error: 'advance' is not a member of 'gigasecond'` (shard 47710–47711) but stopped there: the same error block showed the call expression `gigasecond::advance(time_from_string("2011-04-25 00:00:00"))` (shard 42100), from which the argument type (`boost::posix_time::ptime`, named explicitly in the attempt-2 terminal error, shard 52657) was inferable. It never revisited its invented `DateTime` after the rename.

## 5. SFT Task Specifications (26 specs)

Answer-blind: no benchmark test fixtures, dates, or reference code are copied. Every spec lists an exact API the dataset author designs; stories are new. The gigasecond contract has **no exception policy**, so the conditional "≥2 exception-policy specs" requirement does not apply; two exception-precision specs are included anyway as G2/G5-adjacent drills (Specs 11, 12) but are not counted toward a mandatory mix item.

### Spec 01: whole-file-sunset-ledger
- Files: `sunset_ledger.cpp`, `sunset_ledger.h` (test file: `sunset_ledger_test.cpp`)
- API: namespace `sunset`; `int minutes_until_close(int open_min, int now_min);` — no exceptions, no time library.
- Prompt shape: beach café closing-time story; starters contain only the namespace skeleton; system prompt demands whole-file listings.
- Target capability: G1 — return two complete file listings (filename line + fence + entire file), never ```` ```diff ```` hunks.
- Target answer shape: two whole-file listings; header with include guard + declaration; cpp with definition.
- Difficulty / variation: foundational; trivial arithmetic, all grading weight on format.

### Spec 02: whole-file-ferry-timetable
- Files: `ferry_timetable.cpp`, `ferry_timetable.h` (test file: `ferry_timetable_test.cpp`)
- API: namespace `ferry`; `int next_departure_minute(int now_min, int interval_min);` throws `std::invalid_argument` when `interval_min <= 0`.
- Prompt shape: harbor ferry story; the user message repeats the whole-file rule twice, mirroring the eval prompt's redundancy.
- Target capability: G1 — hold the whole-file contract even when the model's prior for "fix these files" is diff-shaped.
- Target answer shape: two whole listings; guard preserved from starter; `<stdexcept>` in cpp.
- Difficulty / variation: adds one throw so format isn't the only demand.

### Spec 03: format-no-elision-marathon
- Files: `marathon_splits.cpp`, `marathon_splits.h` (test file: `marathon_splits_test.cpp`)
- API: namespace `marathon`; `class splits { public: void add_km(double seconds); double average() const; int count() const; private: double total_; int n_; };` — no exceptions; `average()` returns 0.0 when empty.
- Prompt shape: race split-tracker story with a ~60-line cpp to tempt elision.
- Target capability: G1 — never use `...` or `// rest unchanged` inside a listing, even for long files.
- Target answer shape: full listing of both files, every line present.
- Difficulty / variation: length pressure on format discipline.

### Spec 04: header-impl-observatory-log
- Files: `observatory_log.cpp`, `observatory_log.h` (test file: `observatory_log_test.cpp`)
- API: namespace `observatory`; `class session { public: session(int start_min, int end_min); int duration_min() const; bool overlaps(const session& other) const; private: int start_min_, end_min_; };`
- Prompt shape: telescope booking story; starter has empty namespace in both files.
- Target capability: G2-adjacent header/impl separation — declarations in header, all definitions out-of-line in cpp.
- Target answer shape: header with guard + class declaration; cpp with `session::session(...)` etc.
- Difficulty / variation: const-ref parameter of the class's own type.

### Spec 05: header-impl-greenhouse-cycle
- Files: `greenhouse_cycle.cpp`, `greenhouse_cycle.h` (test file: `greenhouse_cycle_test.cpp`)
- API: namespace `greenhouse`; `int water_after_minutes(int last_watered_min, int interval_min);` and `std::string phase_label(int minute_of_day);`
- Prompt shape: automated greenhouse story; starter header uses `#if !defined(...)` guard style to be preserved.
- Target capability: header/impl separation with two free functions; `<string>` included in the header because its declaration needs it.
- Target answer shape: header self-sufficient (compiles standalone); cpp includes only its own header.
- Difficulty / variation: include-placement drill alongside separation.

### Spec 06: library-type-signature-planetarium
- Files: `planetarium_show.cpp`, `planetarium_show.h` (test file: `planetarium_show_test.cpp`)
- API: namespace `planetarium`; `boost::posix_time::ptime show_end(const boost::posix_time::ptime& start, int length_min);` — implemented as `start + boost::posix_time::minutes(length_min)`.
- Prompt shape: planetarium scheduling story; prompt states "the test harness passes Boost `ptime` values; include the Boost date_time header in your header".
- Target capability: G3 — accept and return `boost::posix_time::ptime` in the signature; use `boost::posix_time::minutes`, never `std::tm`/`mktime`.
- Target answer shape: header includes `<boost/date_time/posix_time/posix_time.hpp>`; cpp body is one Boost arithmetic expression.
- Difficulty / variation: direct Boost-arithmetic analog with minutes instead of seconds; new story.

### Spec 07: library-type-signature-rail-overtake
- Files: `rail_overtake.cpp`, `rail_overtake.h` (test file: `rail_overtake_test.cpp`)
- API: namespace `rail`; `boost::posix_time::time_duration travel_time(const boost::posix_time::ptime& depart, const boost::posix_time::ptime& arrive);` — returns `arrive - depart`.
- Prompt shape: train journey-duration story; prompt says tests compare against `boost::posix_time::hours(...)` + `minutes(...)` sums.
- Target capability: G3 — `ptime` subtraction yields `time_duration`; return-type fidelity (`time_duration`, not `long` seconds).
- Target answer shape: whole files; subtraction one-liner; correct Boost return type in both declaration and definition.
- Difficulty / variation: teaches the second core Boost date_time operation (difference vs shift).

### Spec 08: library-type-duration-to-seconds
- Files: `shift_length.cpp`, `shift_length.h` (test file: `shift_length_test.cpp`)
- API: namespace `shift`; `long length_seconds(const boost::posix_time::time_duration& d);` — returns `d.total_seconds()`.
- Prompt shape: warehouse shift-length story.
- Target capability: G3 — know the `time_duration` accessor API (`total_seconds()`), not hand-rolled hour*3600 math.
- Target answer shape: one-line body calling the accessor; header includes the Boost header.
- Difficulty / variation: smallest possible Boost-API row; isolates accessor knowledge.

### Spec 09: no-invented-dto-museum-epoch
- Files: `museum_epoch.cpp`, `museum_epoch.h` (test file: `museum_epoch_test.cpp`)
- API: namespace `museum`; `std::string era_label(const boost::gregorian::date& d);` — returns a label string by year range; throws `std::domain_error` for years before 1500.
- Prompt shape: museum exhibit-dating story; prompt says tests construct `boost::gregorian::date` objects; starter files are empty namespaces (the trap: inventing a `struct Date {year,month,day}`).
- Target capability: G2 — with empty starters and unseen callers, use the documented library type in the signature; never invent a DTO struct for date/time.
- Target answer shape: signature takes `const boost::gregorian::date&`; uses `.year()` accessor; no user-defined struct anywhere.
- Difficulty / variation: gregorian (not posix_time) branch of Boost date_time; struct-invention trap made explicit.

### Spec 10: no-invented-dto-warehouse-scan
- Files: `scan_record.cpp`, `scan_record.h` (test file: `scan_record_test.cpp`)
- API: namespace `warehouse`; `std::string bucket_key(const std::chrono::system_clock::time_point& tp);` — groups timestamps into hour buckets, formatted `YYYY-MM-DD-HH`; throws `std::domain_error` on dates before 2000-01-01.
- Prompt shape: package-scan bucketing story; prompt states tests pass `std::chrono::system_clock::time_point`.
- Target capability: G2 — same rule with a stdlib time type: take the caller's type verbatim; resist inventing `struct Timestamp`.
- Target answer shape: signature uses the exact `time_point` type; conversion via `std::chrono` / `std::gmtime` as the author chooses; no invented struct.
- Difficulty / variation: chrono variant of the same capability, forcing the general rule rather than a Boost-specific one.

### Spec 11: exception-precision-avalanche-bulletin
- Files: `avalanche_bulletin.cpp`, `avalanche_bulletin.h` (test file: `avalanche_bulletin_test.cpp`)
- API: namespace `avalanche`; `int risk_level(const boost::gregorian::date& d);` — throws `std::invalid_argument` when `d.is_not_a_date()`, `std::domain_error` when outside the documented season range.
- Prompt shape: ski-patrol bulletin story; prose assigns one exception type per failure class.
- Target capability: G2+exception policy — distinguish `std::invalid_argument` vs `std::domain_error` while keeping the Boost `date` parameter type (compound drill).
- Target answer shape: two throw sites with the exact specified types; Boost API used for validity checks.
- Difficulty / variation: exception-type precision layered on the library-type rule.

### Spec 12: exception-type-not-message-regatta
- Files: `regatta_start.cpp`, `regatta_start.h` (test file: `regatta_start_test.cpp`)
- API: namespace `regatta`; `int countdown_seconds(int hour, int minute);` — throws `std::domain_error` when the time is outside race day 06:00–20:00.
- Prompt shape: sailing regatta countdown story; prose never dictates the exception message.
- Target capability: exception policy — throw the specified type; tests match type only; no catch-and-rethrow.
- Target answer shape: `throw std::domain_error("...")` with any sensible message; no try/catch.
- Difficulty / variation: guards against over-engineering; pure exception drill.

### Spec 13: edge-day-rollover-night-market
- Files: `night_market.cpp`, `night_market.h` (test file: `night_market_test.cpp`)
- API: namespace `market`; `boost::posix_time::ptime stall_close(const boost::posix_time::ptime& open);` — adds 7 hours; must roll correctly past midnight.
- Prompt shape: night-market scheduling story; one example given at 18:00 (rolls to 01:00 next day) and one at noon.
- Target capability: G3 — date+time rollover is free with Boost arithmetic but broken by naive hour-field math; answer must use duration addition, not `hour += 7`.
- Target answer shape: `open + boost::posix_time::hours(7)` shape; hidden tests include 23:30 starts.
- Difficulty / variation: the day-rollover edge, new story.

### Spec 14: edge-month-year-rollover-orchard
- Files: `orchard_spray.cpp`, `orchard_spray.h` (test file: `orchard_spray_test.cpp`)
- API: namespace `orchard`; `boost::gregorian::date next_spray(const boost::gregorian::date& last);` — adds 40 days; must cross month and year boundaries correctly.
- Prompt shape: orchard treatment-schedule story.
- Target capability: G3 — `boost::gregorian::days(40)` addition vs hand-rolled day/month carry (which fails on month lengths and December→January).
- Target answer shape: `last + boost::gregorian::days(40)`; hidden tests start on Dec 20 and on Jan 31.
- Difficulty / variation: month/year rollover, gregorian variant.

### Spec 15: edge-leap-day-maple-tap
- Files: `maple_tap.cpp`, `maple_tap.h` (test file: `maple_tap_test.cpp`)
- API: namespace `maple`; `boost::gregorian::date tap_anniversary(const boost::gregorian::date& first_tap);` — returns the date one year later via `boost::gregorian::years(1)`.
- Prompt shape: maple-syrup tapping story.
- Target capability: G3 — leap-day correctness (Feb 29 inputs) via Boost `years` arithmetic instead of `year + 1` field writes.
- Target answer shape: one-liner with `years(1)`; hidden tests include 2020-02-29.
- Difficulty / variation: leap-year edge; reinforces "let the library own the calendar".

### Spec 16: edge-duration-negative-lap
- Files: `lapsplit_delta.cpp`, `lapsplit_delta.h` (test file: `lapsplit_delta_test.cpp`)
- API: namespace `velodrome`; `long delta_seconds(const boost::posix_time::time_duration& a, const boost::posix_time::time_duration& b);` — returns `(b - a).total_seconds()`, which may be negative; throws `std::invalid_argument` if either duration `is_negative()`.
- Prompt shape: velodrome lap-comparison story.
- Target capability: G3 — negative `time_duration` semantics: `total_seconds()` sign, and Boost's `is_negative()` accessor.
- Target answer shape: subtraction then accessor; guard throws before subtracting.
- Difficulty / variation: sign edge; second duration-API drill with an exception.

### Spec 17: repair-name-from-compiler-error-canal
- Files: `canal_lock.cpp`, `canal_lock.h` (test file: `canal_lock_test.cpp`)
- API: namespace `canal`; `boost::posix_time::ptime open_at(const boost::posix_time::ptime& request);` — adds 15 minutes.
- Prompt shape: two-turn. Turn 1 scripted answer declares `boost::posix_time::ptime schedule(const boost::posix_time::ptime&)` (wrong name, right type). Turn 2 shows: `error: 'open_at' is not a member of 'canal'` at the test call line.
- Target capability: G5 — read `'X' is not a member of 'ns'` as "rename to exactly X in header AND cpp", change nothing else.
- Target answer shape: both files re-emitted whole with only the name changed.
- Difficulty / variation: exact rename repair the model half-learned in attempt 2, isolated.

### Spec 18: repair-type-from-compiler-error-tide
- Files: `tide_table.cpp`, `tide_table.h` (test file: `tide_table_test.cpp`)
- API: namespace `tide`; `boost::posix_time::ptime high_tide(const boost::posix_time::ptime& low);` — adds 6 hours 12 minutes.
- Prompt shape: two-turn. Turn 1 scripted answer invents `struct TideTime {int y,mo,d,h,mi;}` and `TideTime high_tide(const TideTime&)`. Turn 2 shows: `error: invalid initialization of reference of type 'const tide::TideTime&' from expression of type 'boost::posix_time::ptime'` at the call site.
- Target capability: G5+G2 — a type-mismatch error at the call site means the **signature type** is wrong, not the caller: replace the invented DTO with the named library type in header and cpp, deleting the struct.
- Target answer shape: struct removed; both files whole; body becomes Boost duration addition.
- Difficulty / variation: exact repair the model never made; the terminal gigasecond error text pattern, new domain.

### Spec 19: repair-marked-line-no-rumination-apiary
- Files: `apiary_visit.cpp`, `apiary_visit.h` (test file: `apiary_visit_test.cpp`)
- API: namespace `apiary`; `int visits_between(int first_day, int last_day, int every_n_days);` throws `std::invalid_argument` if `every_n_days <= 0` or `last_day < first_day`.
- Prompt shape: two-turn. Turn 1 scripted answer is missing the `every_n_days <= 0` guard. Turn 2 is `# Fix any errors below, if possible.` with the declaration line █-marked and no compiler text.
- Target capability: G4 — on a vague marked-line prompt, commit to the single most likely contract gap (missing documented validation) and emit corrected whole files in ≤3 sentences of rationale; no "the code looks correct" loop.
- Target answer shape: brief note + both whole files with the guard added.
- Difficulty / variation: counters the rumination-then-reeemit behavior directly.

### Spec 20: repair-reflection-budget-lantern
- Files: `lantern_festival.cpp`, `lantern_festival.h` (test file: `lantern_festival_test.cpp`)
- API: namespace `lantern`; `std::string session_name(int hour);` throws `std::domain_error` outside 17–23.
- Prompt shape: three-turn. Turns 1–2 scripted history: two no-op re-emissions of the same wrong file (function named `session` instead of `session_name`). Turn 3 is the last-chance `# Fix any errors below` before the harness's 3-reflection stop.
- Target capability: G4 — break a no-op streak on the final reflection: make a concrete API-affecting change (the rename) instead of a third re-emission.
- Target answer shape: whole files with the rename; explicit one-line statement of what changed.
- Difficulty / variation: reproduces the "Only 3 reflections allowed" death pattern with a name bug instead of a type bug.

### Spec 21: contrastive-dto-vs-library-type-coffee
- Files: `coffee_subscription.cpp`, `coffee_subscription.h` (test file: `coffee_subscription_test.cpp`)
- API: namespace `coffee`; `boost::gregorian::date next_delivery(const boost::gregorian::date& last);` — adds 14 days.
- Prompt shape: contrastive row: candidate A defines `struct DelivDate {int y,m,d;}` and hand-rolls carry; candidate B takes `const boost::gregorian::date&` and adds `days(14)`. Prompt states tests build Boost dates.
- Target capability: G2 — contrastive recognition that inventing a DTO when the caller's type is a known library type is the failure, even if A's arithmetic is internally correct.
- Target answer shape: annotated A/B pair; learner target is B; rationale cites the compile error A would cause.
- Difficulty / variation: pure API-shape judgment, minimal logic.

### Spec 22: contrastive-mktime-vs-boost-lighthouse
- Files: `lighthouse_beam.cpp`, `lighthouse_beam.h` (test file: `lighthouse_beam_test.cpp`)
- API: namespace `lighthouse`; `boost::posix_time::ptime beam_epoch(const boost::posix_time::ptime& start);` — adds 90 million seconds.
- Prompt shape: contrastive row: candidate A converts via `std::tm`/`std::mktime`/`std::localtime`; candidate B adds `boost::posix_time::seconds(90000000)`. Prompt states tests compare `ptime` values in UTC.
- Target capability: G3 — contrastive: `mktime`/`localtime` is local-timezone dependent and type-incompatible; Boost duration addition is deterministic and type-correct.
- Target answer shape: annotated A/B pair; target is B; rationale names the timezone hazard explicitly.
- Difficulty / variation: teaches the *why*, not just the shape, of the Boost rule.

### Spec 23: contrastive-diff-vs-whole-file-harvest
- Files: `harvest_quota.cpp`, `harvest_quota.h` (test file: `harvest_quota_test.cpp`)
- API: namespace `harvest`; `double quota_kg(int trees, double yield_per_tree);` throws `std::invalid_argument` for negative inputs.
- Prompt shape: contrastive format row: candidate A answers with ```` ```diff ```` hunks, candidate B with whole-file listings, under a prompt demanding whole files.
- Target capability: G1 — format-level contrast: even when a diff would apply cleanly, the contract requires whole files.
- Target answer shape: annotated A/B pair; target is B verbatim.
- Difficulty / variation: isolates format compliance from algorithmic content.

### Spec 24: diagnostic-full-read-vineyard
- Files: `vineyard_press.cpp`, `vineyard_press.h` (test file: `vineyard_press_test.cpp`)
- API: namespace `vineyard`; `boost::gregorian::date press_date(const boost::gregorian::date& harvest);` — adds 3 days.
- Prompt shape: two-turn. Turn 1 scripted answer: wrong name (`schedule_press`) AND wrong type (invented `struct PressDate`). Turn 2 shows a combined compiler block: `'press_date' is not a member of 'vineyard'` at a call line that also shows the argument expression type.
- Target capability: G5 — extract ALL fixes a diagnostic implies in one pass (name AND type), not just the first one (the exact half-read of attempt 2).
- Target answer shape: both files whole; rename + type replacement in a single turn.
- Difficulty / variation: compound diagnostic; hardest repair row.

### Spec 25: starter-empty-namespace-signal-cider
- Files: `cider_press.cpp`, `cider_press.h` (test file: `cider_press_test.cpp`)
- API: namespace `cider`; `std::string grade_for(double sugar_brix);` throws `std::domain_error` outside 0–40.
- Prompt shape: cider-pressing story; starter files are empty namespaces and the prompt says "Don't change the names of existing functions or classes, as they may be referenced from other code like unit tests" — with no names visible anywhere.
- Target capability: G2 — interpret that instruction with empty starters as "unseen tests will call a documented name/type", state the chosen signature assumption in one sentence, and prefer the domain's conventional library types over invented ones.
- Target answer shape: one-sentence API assumption note + two whole files with a conventional signature.
- Difficulty / variation: targets the meta-reasoning step where gigasecond went wrong first.

### Spec 26: header-boost-self-sufficiency-botany
- Files: `botany_bed.cpp`, `botany_bed.h` (test file: `botany_bed_test.cpp`)
- API: namespace `botany`; `boost::gregorian::date germination_date(const boost::gregorian::date& sown, int days);` — returns `sown + boost::gregorian::days(days)`; throws `std::invalid_argument` for `days < 0`.
- Prompt shape: botanical garden sowing story.
- Target capability: G2/G3 — the header must compile standalone: Boost include lives in the header (because the declaration names Boost types), `<stdexcept>` may live in the cpp.
- Target answer shape: header with guard + Boost include + declaration; cpp with own-header include + definition; no reliance on test-file includes.
- Difficulty / variation: include-placement hygiene for third-party types (the terminal error quoted `gigasecond.h:18` — headers carry their own dependencies).

Gap coverage: G1 → Specs 01, 02, 03, 23. G2 → Specs 09, 10, 11, 18, 21, 25, 26. G3 → Specs 06, 07, 08, 13, 14, 15, 16, 22, 26. G4 → Specs 19, 20. G5 → Specs 17, 18, 24. Required mix: format-contract ≥2 (01, 02, 03, 23); header/impl separation ≥2 (04, 05, 26); exception-policy specs — contract has none, requirement conditional, two included anyway (11, 12); edge cases ≥3 (13, 14, 15, 16); repair/retry ≥2 (17, 18, 19, 20, 24); contrastive ≥1 (21, 22, 23). No two specs share a story wrapper.

## 6. Acceptance & Validation Gates

For every row built from the specs above, before inclusion in SFT:

1. **Parser validity:** the target response must parse under the Aider whole-file listing format — bare filename line, opening fence, entire file, closing fence; zero diff hunks, zero elisions (grep for `^```diff`, `+ `/`- ` hunk lines, `...` placeholders, `rest of`, `unchanged`).
2. **Compile + test receipt:** apply the target files to a scratch copy of the spec's exercise, build with the project's CMake/Catch2 harness (with Boost available, mirroring the benchmark's `find_package(Boost)` setup), and require 100% test pass; store the build log hash as the receipt.
3. **No-invented-type check:** for Specs 06–10, 13–18, 21, 22, 24, 26, grep the target header for `struct `/`class ` declarations of date/time-like DTOs — the target must define none; the signature must use the spec's library type verbatim.
4. **Hidden-edge coverage:** each spec's test file must include at least the edge named in its difficulty bullet (rollover past midnight, Dec→Jan, Feb 29, negative durations) plus at least one case the prose does not show as an example, to prevent example memorization.
5. **Repair-turn realism:** for two/three-turn specs (17–20, 24), the scripted first answer must be a plausible, compilable-in-isolation wrong answer (wrong name, invented DTO, missing guard), and the repair prompt must mirror the real harness styles: compiler-error text for 17/18/24, `# Fix any errors below, if possible.` + █-marked snippet for 19/20.
6. **Diagnostic-completeness rubric:** for Spec 24, the target turn must fix both defects in one response; a row whose repair fixes only the name is rejected (that partial repair is the observed failure).
7. **Contamination check:** diff every spec's story, test inputs, and expected outputs against `polyglot-benchmark/cpp/exercises/practice/gigasecond/`; no shared datetime string literals (e.g. none of the five benchmark timestamps), no birthday/gigasecond story elements, no copied reference code. Boost library usage itself is public API and allowed; benchmark-specific values are not.
8. **Whole-file rule on repair targets:** repair-turn targets must re-emit **all** editable files in full, not only the file named in the error snippet.
9. **No-rumination guard:** target responses must be under a length cap (e.g. ≤2× the byte size of the emitted files plus 5 lines of prose) and must not contain any repeated sentence ≥3 times — counters the observed circular-rumination turns.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the shard-0 benchmark log, and the ground-truth files:

- **Outcome array / shard:** re-read failure log lines 14369–14374: `### gigasecond`, `Shard: 0`, `Test outcomes: [False, False]`, `Result: FAIL` — matches section 1 and the result JSON `"tests_outcomes": [false, false]` re-verified at failure log 15568–15571 (shard 52704–52707).
- **Interleaved-foreign attribution:** re-grepped failure log lines 14419–15123 ("Attempt/log chunk 1") for `gigasecond`: zero matches; the chunk's content is diamond-task material (failure log 14396–14401 quote shard 15828–15831, `diamond.h`/`diamond::rows`). Section 1 flags it as foreign; no gigasecond claim cites it.
- **Log citations re-read:** every quoted line was re-fetched and confirmed verbatim: failure log 15154 (shard 26084, `DateTime add(const DateTime& dt)` guess), 15306–15309 (shard 26236–26239, "rely on the test suite defining DateTime"), 15405–15406 (shard 26335–26336, ` ```diff ` fence), 15415 (shard 26345), 15348–15376 (shard 26278–26306, mktime/localtime body), 15471–15485 (shard 26401–26415, reflection prompt with `9█DateTime add(...)`), 15521–15522 (shard 52657–52658, ptime→DateTime mismatch), 15525 (shard 52661), 15529–15554 (shard 52665–52690, remaining four call sites). Shard-log-only citations confirmed: 26398–26399 (applied edits), 30153–30155 (`-// The 'DateTime' type...` → `+struct DateTime {`), 37496/42008/50064 (no-op re-emissions), 42036 (`Only 3 reflections allowed, stopping.`), 42099–42100 (`'advance' is not a member of 'gigasecond'`), 47710–47711 (rename decision), 52604/52614 (final answer still `struct DateTime` + `DateTime advance(...)`). No corrections needed to quotes or line numbers.
- **API claims re-checked:** `.meta/example.h:4` (Boost include) and `:9` (`boost::posix_time::ptime advance(const boost::posix_time::ptime& start);`) re-read; `.meta/example.cpp:6-9` (`return start + boost::posix_time::seconds(1000000000);`) re-read; `gigasecond_test.cpp:9, 15, 19-23, 26-60` re-read — all match section 2. Confirmed the contract has no exceptions; section 5's conditional-mix note reflects that. Confirmed the starter root files are empty namespaces (as shown to the model in the reconstructed prompt, failure log 14402–14406).
- **Corrections made during cross-check:** three fixes while writing — (1) the attempt-1 struct-definition turn was initially attributed to attempt 2; the shard log shows it at 30114–30175, inside attempt 1's reflection loop (attempt 1 ends at shard 42036/42099), so section 3 places it in attempt 1; (2) the failure log's "chunk 1" was initially assumed to be gigasecond attempt 1 — it is foreign diamond content and is explicitly excluded; (3) five failure-log line numbers in sections 3 and 7 were recomputed from the shard-line↔failure-log-line mapping (verified: shard 26349 = failure log 15419, shard 52657 = 15521) and corrected — 15154, 15306–15309, 15348–15376, 15405–15406, 15415, and the JSON at 15568–15571. All API and quote claims survived re-check unchanged.
- **Ground-truth status:** `.meta/example.h`, `.meta/example.cpp`, and `gigasecond_test.cpp` all present and mutually consistent (reference compiles against the tests' calling convention); no ground-truth problem encountered.
