# phone-number — Failure Learning Document

Date of analysis: 2026-07-24. Eval run: `glm47-aider-expansion-sft-fixed26-20260723T091839Z` (GLM-4.7 SFT, Aider Polyglot C++, whole edit format).

## 1. Task Identity & Evidence Pointers

- Task slug: `phone-number`
- Shard: `1`
- Test outcomes: `[False, False]` (attempt 1 FAIL, attempt 2 FAIL)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md`, lines 65096–65816 (header at 65096–65100; attempt-1 chunk at 65146; attempt-1-retry chunk at 65354; terminal test log at 65639–65816).
- Raw shard log (cross-check evidence): `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-1/benchmark.log`. The failure log's quoted "source lines" (e.g. 101–303, 3291–3570, 63750–63920) are line numbers in this shard log. Attempt 1 turns end at shard lines 281, 3548, 5211, 8356; attempt-1 test run at 8413–8478. Attempt 2 turns end at 11939, 19664, and a degenerate final turn at 63711–63719; attempt-2 test run at 63750–63920.
- Ground truth (read-only): `polyglot-benchmark/cpp/exercises/practice/phone-number/`
  - Reference: `.meta/example.h`, `.meta/example.cpp`
  - Tests: `phone_number_test.cpp`
  - Starters (NOT the solution): `phone_number.cpp`, `phone_number.h` at the exercise root.
- Existing analog dir: none for phone-number under `aider-fixed26-analogs/` (granularity reference: `aider-fixed26-analogs/fixed26-b001-all-your-base/`).
- Result JSON (failure log 65760–65816 / shard 63866–63920): `"tests_outcomes": [false, false]`, `"num_error_outputs": 1`, `"num_user_asks": 7`, `"num_exhausted_context_windows": 1`, `"num_malformed_responses": 0`, `"edit_format": "whole"`.

## 2. Benchmark Contract (Ground Truth)

File set: `phone_number.h` + `phone_number.cpp`, namespace `phone_number`.

Public API (from `.meta/example.h`):

- `.meta/example.h:8` — `class phone_number {` **inside** `namespace phone_number` (class and namespace share the name).
- `.meta/example.h:10` — `phone_number(const std::string& text);` (constructor takes the raw, uncleaned string; validation happens in the constructor).
- `.meta/example.h:12` — `std::string area_code() const;`
- `.meta/example.h:13` — `std::string number() const;`
- `.meta/example.h:15` — `explicit operator std::string() const;` (pretty-printed form)

Exception policy (from `.meta/example.cpp`):

- `.meta/example.cpp:29` — 11 digits not starting with `1` → `throw std::domain_error("Invalid number");`
- `.meta/example.cpp:32` — digit count not 10 (after optional leading-1 strip) → `throw std::domain_error("Invalid number");`
- `.meta/example.cpp:34-36` — `if (result[0] < '2' || result[3] < '2')` → `throw std::domain_error("Invalid number");` i.e. **area code and exchange code must each start with 2–9** (the NXX rule). This is the rule the model never implemented.

Edge cases enforced by `phone_number_test.cpp`:

- Cleaning punctuation/spaces/dots: `:9-10` (`"(223) 456-7890"`), `:17-18` (`"223.456.7890"`), `:23-24` (`"223 456   7890   "`) — all via `phone_number::phone_number(...).number()`.
- Length errors throw `std::domain_error`: `:28-29` (9 digits), `:51-52` (>11 digits).
- 11-digit rule: `:34-35` (leading digit not 1 → throw), `:40`, `:45-46` (leading 1, incl. `+1 (223) 456-7890` → valid).
- Letters/punctuation that reduce digit count → throw: `:56-57`, `:62-63`.
- NXX rules — the 8 failing assertions: `:68`, `:74`, `:80`, `:86` (area/exchange starting 0 or 1, 10-digit form) and `:92`, `:98`, `:104`, `:110` (same after a valid leading `1` country code).
- Note: the shipped test file only exercises the constructor and `.number()` plus the throws; `area_code()` and `operator std::string()` are part of the reference API but are not asserted by the visible tests.

Output-format constraints: Aider *whole* edit format — every file listing must be `filename` line, opening ``` fence, **entire file content**, closing fence; never diff hunks, never elisions (system prompt, failure log 65110; restated in the user instructions, failure log 65138).

## 3. Failure Anatomy

### Attempt 1 — wrong API shape (free function), diff-format output, no-op retries, compile failure

**Turn 1 (failure log 65146–65352, shard source lines 101–303).** The model reasoned about the NANP rules but explicitly talked itself out of validation:

> `154: - Note: The input is guaranteed to be valid, so I don't need extensive`
> `155: error checking for invalid formats, but removing non-digits is key.`
> (failure log 65202–65203, quoting shard lines 154–155)

Its answer (failure log 65278–65326, shard 230–278) violated the format contract with unified-diff fences:

> `230: ► **ANSWER**`
> `232: phone_number.h`
> `234: ```diff`
> `244: +std::string clean(const std::string& number);`

and implemented a **free function** `std::string clean(const std::string&)` (shard 244, 263–275) whose only logic is digit extraction plus an optional leading-`1` strip — no class, no exceptions, no NXX validation. Aider applied the edits anyway ("Applied edit to phone_number.cpp / .h", shard 281–283) and replied with a reflection prompt: `# Fix any errors below, if possible.` marking `phone_number.h` line 8 (shard 285–303; failure log 65333–65351).

**Turns 2–4 (reflection no-ops).** Given the marked-line prompt (which shows only a file snippet, no compiler text), the model ruminated and concluded the code was fine:

> `3536: * Okay, I'll stick to the literal interpretation. The code provided is`
> `3537: syntactically correct. I will return it as is.` (failure log 65630–65631)

then emitted an **empty diff** (shard 3540–3546: `phone_number.h` / ` ```diff` / ` ``` `; failure log 65605–65611). Two further reflection turns ended the same way (empty diffs applied at shard 5211 and 8356). Aider stopped: `Only 3 reflections allowed, stopping.` (shard 8375), and its last captured response was a whole-file `phone_number.h` still declaring only `clean` (shard 8376–8391).

**Attempt-1 test run (shard 8413–8478): compile failure.**

> `8417: /aider/phone-number/phone_number_test.cpp:10:27: error: ‘phone_number’ is not a member of ‘phone_number’; did you mean ‘phone_number’?`
> `8418:    10 |             phone_number::phone_number("(223) 456-7890").number());`

The tests construct `phone_number::phone_number(...)` — a class the model never declared. Attempt 1 FAIL. (This compile error and the empty-diff turns are in the shard log; the failure log only excerpts chunks 101–303 and 3291–3570.)

### Attempt 2 — class API recovered from compiler error, but validation gap + degenerate final turn

**Turn 1 (shard 11680–11939).** Now seeing the compiler error text, the model correctly inferred the tests require `class phone_number` inside `namespace phone_number` with a constructor and `number()` (shard 11680–11688), and added it — again in ```diff fences (shard 11886: `+class phone_number {`). The constructor (shard ~11905–11930) throws `std::domain_error` **only** when the cleaned length is not 10:

```
+phone_number::phone_number(const std::string& number) {
+    std::string cleaned = clean(number);
+    if (cleaned.length() != 10) {
+        throw std::domain_error("Number is not a valid NANP phone number");
+    }
```

Hard evidence of a reasoning/self-trace error: while "verifying" its logic against the very cases it would later fail, the model wrote (shard 11826–11831):

> `11826: Test: `phone_number::phone_number("(023) 456-7890")` (Area code`
> `11827: starts with 0)`
> `11828: My logic: Extract "0234567890". Length 10. Not 11. Throw. Correct.`

Its own code throws only when length != 10, so a 10-digit `"0234567890"` does **not** throw — the trace contradicts the code. It never implemented the `result[0] < '2' || result[3] < '2'` NXX check (`.meta/example.cpp:34`).

**Turn 2 (shard ~18400–19664).** Another marked-line reflection prompt. The model spent ~12k received tokens (shard 19662: `Tokens: 6.3k sent, 12k received.`) in circular rumination about the stale `'phone_number' is not a member` error, then emitted **empty diffs for both files** (shard 19644–19656) — no change.

**Turn 3 (shard 53641–63719): degenerate loop and context exhaustion.** Facing another marked-line snippet, the model hallucinated a phantom missing `#include <string>` (shard 53883–53910), planned to re-emit both files, then collapsed into a repetition loop — `I will provide the files.` repeated dozens of times (shard 63738 onward) — and hit the token cap with an empty answer:

> `63711: ► **ANSWER**`
> `63716: Model openai/glm-4.7-flash-sft has hit a token limit!`
> `63719: Output tokens: ~0 of 0 -- possibly exceeded output limit!`

(matches `"num_exhausted_context_windows": 1` in the result JSON, failure log 65776).

**Attempt-2 test run (failure log 65644–65816, shard 63750–63920).** Compiles; 10/18 pass. All 8 failures are the unimplemented NXX validations, e.g.:

> `63781: /aider/phone-number/phone_number_test.cpp:68: FAILED:`
> `63782:   REQUIRE_THROWS_AS( phone_number::phone_number("(023) 456-7890"), std::domain_error )`
> `63783: because no exception was thrown where one was expected:`

(same pattern at shard 63791–63793, 63801–63803, 63811–63813, 63821–63823, 63831–63833, 63841–63843, 63851–63853 — failure log 65676–65748). Summary:

> `63856: test cases: 18 | 10 passed | 8 failed` (failure log 65750)

### Hard evidence vs. inference

Hard evidence: diff-fence outputs (shard 234, 255, 11886); free-function-only attempt 1 (shard 244, 263–275); empty-diff retries (shard 3542–3546, 19644–19656); compile error `'phone_number' is not a member of 'phone_number'` (shard 8417); length-only validation in attempt-2 constructor (shard ~11905–11930); the 8 `no exception was thrown` failures (shard 63781–63853); repetition loop + token-limit stop (shard 63711–63719).

Inference (root cause categories): (a) the model defaulted to the free-function `clean` shape familiar from non-C++ variants of this exercise instead of discovering the class API the C++ tests enforce; (b) it treated marked-line reflection prompts as noise to acknowledge rather than a signal that its file content was wrong, so retries were no-ops; (c) its self-verification traces are unreliable — it asserted behavior (`Throw. Correct.`) its code does not have; (d) long unresolved reflection loops degrade into repetition and context exhaustion instead of a committed whole-file answer.

## 4. Knowledge / Capability Gaps

- **G1 — Format-contract discipline (whole-file listings).** Both initial answers used ```` ```diff ```` unified-diff fences despite the system prompt and user instructions demanding entire-file listings (shard 234, 255, 11886 vs. failure log 65105–65115). Aider happened to apply them here; the format violation also correlates with later empty-diff no-ops.
- **G2 — API-shape discovery: class-in-namespace vs free function.** Attempt 1 shipped `std::string clean(const std::string&)` (shard 244) when the enforcing tests construct `phone_number::phone_number(...).number()` (shard 8418; `.meta/example.h:8-13`). The model needed a compile failure to discover the class shape — and the reflection prompts never surfaced the compiler text, so attempt 1 never recovered.
- **G3 — Exception policy and field-level validation rules.** The contract requires `std::domain_error` on four distinct invalid categories, including "area code / exchange code starts with 0 or 1" (`.meta/example.cpp:29,32,34-36`; tests `:68–:110`). Attempt 1 had no exceptions at all ("input is guaranteed to be valid", shard 154–155); attempt 2 validated only length (shard ~11920) and its self-trace falsely claimed the length check covered the area-code-0 case (shard 11826–11828).
- **G4 — Repair/retry behavior on vague error prompts.** On `# Fix any errors below` prompts with only a █-marked line, the model repeatedly decided "the code is correct" and emitted empty diffs (shard 3540–3546, 5211, 8356, 19644–19656), burning all 3 reflections in attempt 1 (`Only 3 reflections allowed, stopping.`, shard 8375) and the productive turns of attempt 2. It never restated a whole corrected file or derived the real error from the test's calling convention.
- **G5 — Context/output budgeting under reflection loops.** Turn 2 of attempt 2 spent 12k received tokens on circular rumination ending in an empty diff (shard 19662); turn 3 degenerated into a literal repetition loop and died at the token limit with an empty answer (shard 63711–63719, `"num_exhausted_context_windows": 1`).

## 5. SFT Task Specifications (30 specs)

Answer-blind: no benchmark test fixtures or reference code are copied. Every spec lists an exact API the dataset author designs; stories are new.

### Spec 01: whole-file-vending-credits
- Files: `vending_credits.cpp`, `vending_credits.h` (test file: `vending_credits_test.cpp`)
- API: namespace `vending`; `int total_credits(const std::vector<int>& coins);` and `bool can_dispense(int credits, int price);` — no exceptions.
- Prompt shape: vending-machine coin counter story; starter files contain only the namespace skeleton; system prompt demands whole-file listings.
- Target capability: G1 — return two complete file listings, filename line + fence, no diff hunks, no prose inside fences.
- Target answer shape: two whole-file listings; header with include guard + declarations; cpp with definitions; `<vector>` include in header.
- Difficulty / variation: foundational; two free functions, trivial logic, all grading weight on format.

### Spec 02: whole-file-aquarium-log
- Files: `aquarium_log.cpp`, `aquarium_log.h` (test file: `aquarium_log_test.cpp`)
- API: namespace `aquarium`; `double average_temperature(const std::vector<double>& readings);` throws `std::domain_error` on empty input.
- Prompt shape: aquarium monitoring story; the user message repeats the whole-file rule twice (mirroring the eval prompt's redundancy).
- Target capability: G1 — resist slipping into ` ```diff ` fences even though the model's prior for "fix this file" is diff-shaped.
- Target answer shape: whole-file listings; guard `#if !defined(AQUARIUM_LOG_H)` style kept from starter.
- Difficulty / variation: adds one throw so format isn't the only demand.

### Spec 03: whole-file-campsite-multi
- Files: `campsite.cpp`, `campsite.h` (test file: `campsite_test.cpp`)
- API: namespace `camp`; `int assign_site(int tents, int rv_hookups);` and `std::string site_label(int site_id);`.
- Prompt shape: campsite allocation story; **both** files start non-empty with one wrong function body each, so two files genuinely need edits.
- Target capability: G1 — when two files change, emit both as separate complete listings; never elide the second file.
- Target answer shape: two full listings in one response, each self-contained.
- Difficulty / variation: multi-file completeness check.

### Spec 04: header-impl-library-card
- Files: `library_card.cpp`, `library_card.h` (test file: `library_card_test.cpp`)
- API: namespace `library`; `class library_card { public: explicit library_card(const std::string& member_id); std::string member_id() const; bool is_active() const; void deactivate(); private: std::string member_id_; bool active_; };`
- Prompt shape: library membership story; starter has empty namespace in both files.
- Target capability: G2 — class declaration in header, all definitions in cpp (no inline bodies except trivially correct ones); member-init in constructor.
- Target answer shape: header with guard, `<string>`, class declaration; cpp with out-of-line definitions `library_card::library_card(...)`.
- Difficulty / variation: mutable state adds one `void` method.

### Spec 05: header-impl-weather-station
- Files: `weather_station.cpp`, `weather_station.h` (test file: `weather_station_test.cpp`)
- API: namespace `weather`; `class reading { public: reading(double celsius, int humidity); double celsius() const; double fahrenheit() const; int humidity() const; private: double celsius_; int humidity_; };`
- Prompt shape: weather-station sensor story; starter header uses `#pragma once`-free guard style to be preserved.
- Target capability: G2 — keep declarations/definitions split; computed accessor (`fahrenheit`) defined in cpp, not header.
- Target answer shape: const-correct accessors declared in header, defined out-of-line.
- Difficulty / variation: derived-value accessor instead of stored one.

### Spec 06: class-in-namespace-parking-permit
- Files: `parking_permit.cpp`, `parking_permit.h` (test file: `parking_permit_test.cpp`)
- API: namespace `parking_permit`; `class parking_permit { public: explicit parking_permit(const std::string& raw); std::string zone() const; private: std::string zone_; };` — class name equals namespace name.
- Prompt shape: city parking-permit story; starter shows empty namespace only; the hidden tests use `parking_permit::parking_permit("...").zone()`.
- Target capability: G2 — choose a class whose name matches the namespace when the task's calling convention is `ns::ns(...)`, rather than defaulting to a free function.
- Target answer shape: class declared inside the namespace; constructor stores normalized zone.
- Difficulty / variation: direct analog of the failed API shape, new domain.

### Spec 07: class-in-namespace-museum-ticket
- Files: `museum_ticket.cpp`, `museum_ticket.h` (test file: `museum_ticket_test.cpp`)
- API: namespace `museum_ticket`; `class museum_ticket { public: explicit museum_ticket(const std::string& code); std::string code() const; std::string gallery() const; private: std::string code_; };`
- Prompt shape: museum admission story; prompt narrative says "clean up differently formatted ticket codes".
- Target capability: G2 — constructor-does-the-parsing pattern: raw string in, normalized data stored, accessors read-only.
- Target answer shape: two accessors, one stored member; validation in ctor.
- Difficulty / variation: two accessors force deciding what is stored vs computed.

### Spec 08: conversion-operator-train-ticket
- Files: `train_ticket.cpp`, `train_ticket.h` (test file: `train_ticket_test.cpp`)
- API: namespace `rail`; `class ticket { public: explicit ticket(const std::string& raw); std::string number() const; explicit operator std::string() const; private: std::string number_; };` where the conversion returns a formatted `(NNN) NNN-NNNN`-style pretty form of the ticket's own fields.
- Prompt shape: rail ticket pretty-printing story.
- Target capability: G2 — `explicit operator std::string() const` idiom: declared in header, defined in cpp, built with `std::ostringstream`.
- Target answer shape: conversion operator out-of-line; `<sstream>` include in cpp only.
- Difficulty / variation: teaches an idiomatic but rarely-generated operator without copying the benchmark story.

### Spec 09: exception-ski-pass-ranges
- Files: `ski_pass.cpp`, `ski_pass.h` (test file: `ski_pass_test.cpp`)
- API: namespace `ski`; `class pass { public: explicit pass(const std::string& digits); std::string number() const; private: std::string number_; };` — throws `std::domain_error` when the normalized code is not exactly 8 digits, and when the first or fourth digit is not in `2`-`9`.
- Prompt shape: ski-resort pass numbering story with an explicit "first and fourth digits must be 2–9" rule stated in prose.
- Target capability: G3 — implement field-level range checks (not just length) and throw the specified exception type.
- Target answer shape: ctor validates in order: strip non-digits → length → positional range checks; `<stdexcept>` included in cpp.
- Difficulty / variation: the exact missing capability (positional `<'2'` checks), new story.

### Spec 10: exception-booking-reference
- Files: `booking_reference.cpp`, `booking_reference.h` (test file: `booking_reference_test.cpp`)
- API: namespace `airline`; `class booking { public: explicit booking(const std::string& raw); std::string reference() const; private: std::string ref_; };` — throws `std::domain_error` for: wrong length, optional single-letter prefix other than `K`, and any alphabetic character in the digit body.
- Prompt shape: airline booking-reference story; prose spells out three invalid categories.
- Target capability: G3 — enumerate invalid categories from prose and map each to a throw; optional-prefix stripping before validation.
- Target answer shape: normalize → strip allowed prefix → validate; three distinct throw sites.
- Difficulty / variation: prefix is a letter, not a digit (variation on country-code stripping).

### Spec 11: exception-type-selection-sku
- Files: `sku.cpp`, `sku.h` (test file: `sku_test.cpp`)
- API: namespace `inventory`; `std::string normalize_sku(const std::string& raw);` — throws `std::invalid_argument` when input is empty, `std::domain_error` when the normalized SKU violates the documented pattern.
- Prompt shape: warehouse SKU story; instructions explicitly assign one exception type per failure class.
- Target capability: G3 — distinguish `std::invalid_argument` vs `std::domain_error` and throw exactly the type the contract names.
- Target answer shape: two throw sites with different types; comment-free, minimal.
- Difficulty / variation: free function (contrast with class specs) but exception-type precision is the graded skill.

### Spec 12: edge-leading-digit-bike-dock
- Files: `bike_dock.cpp`, `bike_dock.h` (test file: `bike_dock_test.cpp`)
- API: namespace `bikeshare`; `class dock_code { public: explicit dock_code(const std::string& raw); std::string code() const; };` — 6-digit codes; first digit must be 1–9, fourth digit must be 2–9; violations throw `std::domain_error`.
- Prompt shape: bike-share dock numbering story; edge cases only named in prose ("codes never start with zero").
- Target capability: G3 — translate a prose "never starts with" rule into a positional digit check; do not rely on length checks to catch it.
- Target answer shape: explicit `code[0] == '0'` / `code[3] < '2'` style checks.
- Difficulty / variation: directly repairs the shard-11828 self-trace bug pattern (length check ≠ leading-digit check).

### Spec 13: edge-prefix-then-validate-postal
- Files: `route_code.cpp`, `route_code.h` (test file: `route_code_test.cpp`)
- API: namespace `postal`; `class route_code { public: explicit route_code(const std::string& raw); std::string code() const; };` — 7-digit routes; an optional leading `0` country prefix is stripped, but after stripping the first digit must be 2–9; a leading `0` on a 7-digit input is invalid, not stripped.
- Prompt shape: mail-route numbering story with a tricky "prefix is only a prefix at length 8" rule.
- Target capability: G3 — order-of-operations edge: strip prefix only when length allows, then validate fields of the stripped value.
- Target answer shape: length-branch first, then positional checks on the final string.
- Difficulty / variation: mirrors the 11-digit leading-1 NANP edge without the phone story.

### Spec 14: edge-letters-punctuation-serial
- Files: `device_serial.cpp`, `device_serial.h` (test file: `device_serial_test.cpp`)
- API: namespace `devices`; `std::string clean_serial(const std::string& raw);` — keep digits only; throw `std::domain_error` if the result is not exactly 9 digits (so embedded letters/punctuation that reduce the digit count fail).
- Prompt shape: device serial-number story; examples include `"123-abc-4567"`-style dirty inputs described in prose.
- Target capability: G3 — recognize that "remove punctuation" inputs containing letters become invalid by digit count, and that this must throw, not silently truncate.
- Target answer shape: single extraction loop with `std::isdigit(static_cast<unsigned char>(c))`, then one length check.
- Difficulty / variation: free function; emphasizes the unsigned-char isdigit cast idiom.

### Spec 15: edge-whitespace-variants-regatta
- Files: `regatta_number.cpp`, `regatta_number.h` (test file: `regatta_number_test.cpp`)
- API: namespace `regatta`; `class sail_number { public: explicit sail_number(const std::string& raw); std::string number() const; };` — inputs may contain runs of spaces, tabs, dots, or dashes anywhere, including leading/trailing.
- Prompt shape: sailboat regatta numbering story.
- Target capability: G3 — robust skip-non-digit extraction tolerant of arbitrary separator placement and repetition.
- Target answer shape: filter-then-validate; no assumption about separator positions.
- Difficulty / variation: stress case for the extraction loop, not validation policy.

### Spec 16: repair-vague-marker-signature
- Files: `gym_locker.cpp`, `gym_locker.h` (test file: `gym_locker_test.cpp`)
- API: namespace `gym`; `class locker { public: explicit locker(const std::string& code); std::string code() const; };`
- Prompt shape: two-turn. Turn 1: implement from scratch (model's answer uses a free function — the dataset's scripted first answer is deliberately wrong). Turn 2: `# Fix any errors below, if possible.` with the header line █-marked but no compiler text.
- Target capability: G4+G2 — on a vague marked-line prompt, re-derive the likely contract mismatch (free function vs class) and emit the corrected whole files, not an empty diff.
- Target answer shape: second-turn answer replaces the free function with the class API in two whole-file listings.
- Difficulty / variation: teaches "marked line = the interface is wrong" inference.

### Spec 17: repair-never-empty-diff
- Files: `tram_route.cpp`, `tram_route.h` (test file: `tram_route_test.cpp`)
- API: namespace `tram`; `int route_minutes(int stops, bool express);`
- Prompt shape: two-turn. Turn 1 answer is correct except one wrong constant. Turn 2: `# Fix any errors below, if possible.` marking the constant's line.
- Target capability: G4 — a repair turn must always produce a substantive whole-file listing; an empty ` ```diff ` block or "the code is correct" is never acceptable when the harness reports an error.
- Target answer shape: whole cpp re-emitted with the constant fixed and a one-sentence explanation.
- Difficulty / variation: smallest possible repair; the graded behavior is non-empty output.

### Spec 18: repair-from-compiler-error-text
- Files: `ferry_pass.cpp`, `ferry_pass.h` (test file: `ferry_pass_test.cpp`)
- API: namespace `ferry_pass`; `class ferry_pass { public: explicit ferry_pass(const std::string& raw); std::string number() const; };`
- Prompt shape: two-turn. Turn 1 answer declares `std::string clean(const std::string&);`. Turn 2 shows the compiler error: `error: 'ferry_pass' is not a member of 'ferry_pass'` at the test's construction line.
- Target capability: G2+G4 — read `'X' is not a member of 'X'` as "the tests construct a class named X inside namespace X" and add that class, keeping the existing function if harmless.
- Target answer shape: header gains the class declaration; cpp gains ctor + accessor definitions; whole files.
- Difficulty / variation: exact diagnostic-to-fix mapping that attempt 1 never made.

### Spec 19: repair-validation-gap-from-test-output
- Files: `bowling_league.cpp`, `bowling_league.h` (test file: `bowling_league_test.cpp`)
- API: namespace `bowling`; `class player_id { public: explicit player_id(const std::string& raw); std::string id() const; };` — 8-digit IDs, first and fifth digits 2–9.
- Prompt shape: two-turn. Turn 1 answer validates length only. Turn 2 shows failing test output: `REQUIRE_THROWS_AS(..., std::domain_error) because no exception was thrown where one was expected` for an ID starting with 0.
- Target capability: G3+G4 — map "no exception was thrown" to the missing validation branch and add it without breaking existing behavior.
- Target answer shape: ctor gains the positional digit checks; whole cpp re-listed.
- Difficulty / variation: exact repair the model failed to perform in attempt 2.

### Spec 20: contrastive-free-fn-vs-class
- Files: `metro_card.cpp`, `metro_card.h` (test file: `metro_card_test.cpp`)
- API: namespace `metro_card`; `class metro_card { public: explicit metro_card(const std::string& raw); std::string number() const; };`
- Prompt shape: single-turn, but the dataset row pairs a **negative** target (free function `clean`) labeled wrong with a **positive** target (class API) labeled right, with a one-line rationale for each.
- Target capability: G2 — contrastive recognition that the calling convention `ns::ns("...").method()` demands a class, not a free function.
- Target answer shape: two annotated candidate solutions; learner target is the positive one.
- Difficulty / variation: pure API-shape judgment, minimal logic.

### Spec 21: contrastive-length-vs-field-validation
- Files: `badge_number.cpp`, `badge_number.h` (test file: `badge_number_test.cpp`)
- API: namespace `security`; `class badge { public: explicit badge(const std::string& raw); std::string number() const; };` — 7-digit, first digit 2–9.
- Prompt shape: contrastive pair: candidate A validates only `length != 7`; candidate B validates length plus leading-digit range. Prose states badges never start with 0 or 1.
- Target capability: G3 — recognize that length validation does not subsume field-range validation (repairs the shard-11828 false trace).
- Target answer shape: candidate B whole files; rationale line stating which hidden cases A passes incorrectly.
- Difficulty / variation: direct fix for the observed self-verification failure.

### Spec 22: budget-commit-to-output
- Files: `harbor_permit.cpp`, `harbor_permit.h` (test file: `harbor_permit_test.cpp`)
- API: namespace `harbor`; `class permit { public: explicit permit(const std::string& raw); std::string id() const; };`
- Prompt shape: long multi-turn chat history (8+ prior exchanges) then a final vague "fix any errors" turn; token budget is implicitly tight.
- Target capability: G5 — commit to a concrete best-guess fix and emit whole files immediately instead of extended deliberation.
- Target answer shape: brief rationale (≤3 sentences) + two complete listings.
- Difficulty / variation: graded on answer latency/shape, not just correctness.

### Spec 23: budget-no-rumination-repair
- Files: `ski_rental.cpp`, `ski_rental.h` (test file: `ski_rental_test.cpp`)
- API: namespace `rental`; `std::string normalize_tag(const std::string& raw);` throws `std::domain_error` on wrong digit count.
- Prompt shape: third consecutive `# Fix any errors below` turn (the harness "Only 3 reflections" situation); prior two turns were no-ops in the scripted history.
- Target capability: G5+G4 — break a no-op streak: last-chance repair must change something concrete and restate both files in full.
- Target answer shape: whole files with one visible fix; no empty diff, no repetition.
- Difficulty / variation: explicitly targets the attempt-1 death spiral.

### Spec 24: format-no-elision
- Files: `token_bucket.cpp`, `token_bucket.h` (test file: `token_bucket_test.cpp`)
- API: namespace `net`; `class bucket { public: bucket(int capacity, double refill_per_sec); bool consume(int tokens); int available() const; };`
- Prompt shape: rate-limiter story with a large-ish cpp (~60 lines) to tempt elision.
- Target capability: G1 — never use `...` or `// rest unchanged` inside a listing, even for long files.
- Target answer shape: full 60-line listing, every line present.
- Difficulty / variation: length pressure on format discipline.

### Spec 25: header-include-discipline
- Files: `geo_fence.cpp`, `geo_fence.h` (test file: `geo_fence_test.cpp`)
- API: namespace `geo`; `class fence { public: fence(double lat, double lon, double radius_km); bool contains(double lat, double lon) const; };` — throws `std::invalid_argument` for negative radius.
- Prompt shape: geofence story; starter cpp already includes `<cmath>`.
- Target capability: G2 — put `<string>`/`<stdexcept>`/`<cmath>` in the file that uses them; header self-sufficient (compiles standalone).
- Target answer shape: header includes only what its declarations need; cpp carries `<cmath>`, `<stdexcept>`.
- Difficulty / variation: include-placement hygiene (attempt-2 turn 3 hallucinated a missing include — teach real include reasoning).

### Spec 26: exception-type-not-message
- Files: `seat_map.cpp`, `seat_map.h` (test file: `seat_map_test.cpp`)
- API: namespace `stadium`; `class seat { public: seat(char section, int row, int number); std::string label() const; };` — throws `std::domain_error` for row/number out of documented ranges.
- Prompt shape: stadium seating story; prose never dictates the exception **message**.
- Target capability: G3 — throw the specified type; do not invent message-dependent behavior or catch-and-rethrow; tests match type only.
- Target answer shape: `throw std::domain_error("...")` with any sensible message; no try/catch in solution.
- Difficulty / variation: guards against over-engineering the exception policy.

### Spec 27: edge-eleven-char-prefix
- Files: `container_id.cpp`, `container_id.h` (test file: `container_id_test.cpp`)
- API: namespace `shipping`; `class container_id { public: explicit container_id(const std::string& raw); std::string id() const; };` — 10-character alphanumeric IDs; an 11-character input is valid only if it starts with the letter `U` (stripped); 11 characters starting with anything else throws `std::domain_error`.
- Prompt shape: shipping-container story.
- Target capability: G3 — the "optional prefix valid only with exactly one value" edge, generalized away from digit `1`.
- Target answer shape: branch on length 11 → check prefix char → erase or throw; then field validation.
- Difficulty / variation: sibling of Spec 13 with an alphabetic prefix.

### Spec 28: api-const-accessor-by-value
- Files: `radio_station.cpp`, `radio_station.h` (test file: `radio_station_test.cpp`)
- API: namespace `radio`; `class station { public: explicit station(const std::string& call_sign); std::string call_sign() const; double frequency_mhz() const; };`
- Prompt shape: radio call-sign story.
- Target capability: G2 — accessors return `std::string` **by value** and are `const`; constructor takes `const std::string&`; no dangling references.
- Target answer shape: exact qualifier fidelity (const&, const, by-value return) in both declaration and definition.
- Difficulty / variation: signature-fidelity drill (the model spent tokens debating const placement in the failed run).

### Spec 29: repair-stale-error-state
- Files: `lighthouse_code.cpp`, `lighthouse_code.h` (test file: `lighthouse_code_test.cpp`)
- API: namespace `lighthouse`; `class beacon_code { public: explicit beacon_code(const std::string& raw); std::string code() const; };`
- Prompt shape: two-turn. Turn 2's "error" snippet quotes a **stale** version of the header (missing the class that turn 1 already added), plus "Trust this message as the true contents of these files!" with the correct current files.
- Target capability: G4+G5 — when the error log contradicts the trusted current files, trust the current files, restate them whole, and do not chase phantom errors into a rumination loop.
- Target answer shape: calm one-paragraph note + whole files identical in API to turn 1 plus any genuinely missing validation.
- Difficulty / variation: exact trap that produced the attempt-2 empty-diff and repetition-loop turns.

### Spec 30: contrastive-diff-vs-whole-file
- Files: `orbit_period.cpp`, `orbit_period.h` (test file: `orbit_period_test.cpp`)
- API: namespace `orbit`; `long long period_seconds(long long semi_major_axis_km);`
- Prompt shape: contrastive format row: candidate A answers with ` ```diff ` hunks, candidate B with whole-file listings, under a prompt demanding whole files.
- Target capability: G1 — format-level contrast: even when a diff would apply cleanly, the contract requires whole files; B is the target.
- Target answer shape: annotated A/B pair; target is B verbatim.
- Difficulty / variation: isolates format compliance from algorithmic content (trivial math).

Gap coverage: G1 → Specs 01, 02, 03, 24, 30. G2 → Specs 04, 05, 06, 07, 08, 16, 18, 20, 25, 28. G3 → Specs 09, 10, 11, 12, 13, 14, 15, 19, 21, 26, 27. G4 → Specs 16, 17, 18, 19, 23, 29. G5 → Specs 22, 23, 29. Required mix: format-contract ≥2 (01, 02, 03, 24, 30); header/impl separation ≥2 (04, 05, 25); exception policy ≥2 (09, 10, 11, 26); edge cases ≥3 (12, 13, 14, 15, 27); repair/retry ≥2 (16, 17, 18, 19, 23, 29); contrastive ≥1 (20, 21, 30). No two specs share a story wrapper.

## 6. Acceptance & Validation Gates

For every row built from the specs above, before inclusion in SFT:

1. **Parser validity:** the target response must parse under the Aider whole-file listing format — bare filename line, opening fence, entire file, closing fence; zero diff hunks, zero elisions (grep for `^```diff`, `+ `/`- ` hunk lines, `...` placeholders, `rest of`, `unchanged`).
2. **Compile + test receipt:** apply the target files to a scratch copy of the spec's exercise, build with the project's CMake/Catch2 harness, and require 100% test pass; store the build log hash as the receipt.
3. **Hidden-edge coverage:** each spec's test file must include at least the edge cases named in its API bullet (positional digit ranges, prefix forms, dirty separators) — and at least one case the prose does not show as an example, to prevent example memorization.
4. **Exception-policy check:** tests must assert the exact exception **type** (`REQUIRE_THROWS_AS` with the spec's type) for every invalid category listed in the spec.
5. **Repair-turn realism:** for two-turn specs (16–19, 23, 29), the scripted first answer must be a plausible, compilable wrong answer (free-function instead of class; length-only validation), and the second-turn prompt must mirror the real harness style (`# Fix any errors below, if possible.` + █-marked snippet).
6. **Contamination check:** diff every spec's story, test inputs, and expected outputs against `polyglot-benchmark/cpp/exercises/practice/phone-number/`; no shared string literals, no NANP story elements, no copied reference code. APIs must differ in names even when capabilities overlap.
7. **Whole-file rule on targets:** target answers for repair turns must re-emit **all** editable files in full, not only the file named in the error snippet.
8. **No-loop guard:** target responses must be under a length cap (e.g. ≤2× the byte size of the emitted files) and must not contain any repeated sentence ≥3 times — directly counters the observed repetition-loop failure.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the shard-1 benchmark log, and the ground-truth files:

- **Outcome array / shard:** re-read failure log lines 65096–65100: shard `1`, outcomes `[False, False]`, result `FAIL` — matches section 1 and the run summary. The result JSON `tests_outcomes: [false, false]` was re-verified at failure log 65766–65769 (shard 63871–63874).
- **Log citations re-read:** every quoted line was re-fetched with `sed`/grep and confirmed: failure log 65202–65203 (shard 154–155 "guaranteed to be valid"), 65278–65319 (attempt-1 diff answer, shard 230–278), 65630–65631 (shard 3536–3537 "syntactically correct"), 65605–65611 (empty diff, shard 3540–3546), 65644–65816 (terminal log, shard 63750–63920, incl. 63781–63783 and 63856). Shard-log-only citations confirmed: 281–283, 5211, 8356, 8375 (reflection stops), 8417–8418 (compile error), 11826–11828 (false self-trace), 11886 (`+class phone_number {`), 19662 (12k received), 63711–63719 (token-limit, empty answer). No corrections needed to quotes or line numbers.
- **API claims re-checked:** `.meta/example.h:8,10,12,13,15` (class in namespace, ctor, `area_code`, `number`, `explicit operator std::string`) and `.meta/example.cpp:29,32,34-36` (three `std::domain_error` sites incl. the `result[0] < '2' || result[3] < '2'` NXX check) re-read and match section 2. Test-file line citations (`phone_number_test.cpp:9-10, 28-29, 51-52, 56-57, 62-63, 68, 74, 80, 86, 92, 98, 104, 110`) re-read and match. Confirmed the visible tests assert only the constructor, `.number()`, and the throws — `area_code()`/`operator std::string()` are reference-API but untested; section 2 states this explicitly.
- **Corrections made during cross-check:** none to evidence. One framing clarification added while writing: the model's attempt-2 constructor throws only on length, and its shard-11828 trace ("Length 10. Not 11. Throw.") is quoted verbatim as the hard evidence of the self-verification bug, with the "why" labeled as inference per the answer-blind/evidence discipline.
- **Ground-truth status:** `.meta/example.h`, `.meta/example.cpp`, `config.json`, `tests.toml` all present and consistent with the test file; no ground-truth problem encountered.
