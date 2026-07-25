# grade-school — Failure Learning Document

Date of analysis: 2026-07-24. Eval run: `glm47-aider-expansion-sft-fixed26-20260723T091839Z` (GLM-4.7 SFT, Aider Polyglot C++, whole edit format).

## 1. Task Identity & Evidence Pointers

- Task slug: `grade-school`
- Shard: `0`
- Test outcomes: `[False, False]` (attempt 1 FAIL, attempt 2 FAIL)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md`, lines 15624–16418 (header at 15624–15629; attempt-1 chunk at 15674, source lines 817–1157; attempt-1 retry chunk at 16020, source lines 2587–2879; terminal test log at 16321, source lines 13973–14066).
- Raw shard log (cross-check evidence): `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log`. The failure log's quoted "source lines" are line numbers in this shard log, which interleaves many tasks; grade-school turns were identified by their `Applied edit to grade_school.*` markers. Attempt 1: answers at shard 1059, 2799, 6537, 10042; reflections exhausted at 10083; test run at 10114–10208. Attempt 2: answers at shard 11141, 12579, 13660, 13899; reflections exhausted at 13939; test run at 13971–14066 (excerpted in failure log 16321–16390).
- Ground truth (read-only): `polyglot-benchmark/cpp/exercises/practice/grade-school/`
  - Reference: `.meta/example.h`, `.meta/example.cpp`
  - Tests: `grade_school_test.cpp`
  - Starters (NOT the solution): `grade_school.cpp`, `grade_school.h` at the exercise root (empty namespace skeletons).
- Existing analog dir: none for grade-school under `aider-fixed26-analogs/` (granularity reference: `aider-fixed26-analogs/fixed26-b001-all-your-base/`).
- Result JSON (failure log 16357–16390 / shard 14007–14066): `"tests_outcomes": [false, false]`, `"num_error_outputs": 0`, `"num_user_asks": 8`, `"num_exhausted_context_windows": 0`, `"num_malformed_responses": 0`, `"edit_format": "whole"`.

## 2. Benchmark Contract (Ground Truth)

File set: `grade_school.h` + `grade_school.cpp`, namespace `grade_school`.

Public API (from `.meta/example.h`):

- `.meta/example.h:11` — `class school` — **lowercase** class name, inside `namespace grade_school` (`:8`). The model named it `School` on attempt 1; C++ is case-sensitive.
- `.meta/example.h:14-16` — `const std::map<int, std::vector<std::string>>& roster() const { return roster_; }` — returns a **const reference** to the internal map, defined inline in the header.
- `.meta/example.h:18` — `void add(std::string const& name, int grade);` — non-const, **void** return, defined out-of-line (`.meta/example.cpp:9-14`).
- `.meta/example.h:20` — `std::vector<std::string> grade(int grade) const;` — the per-grade query method is named **`grade`** (same identifier as the parameter name), returns a vector **by value**, defined out-of-line (`.meta/example.cpp:16-20`). The model invented `students_in_grade` instead.
- `.meta/example.h:23` — private member `std::map<int, std::vector<std::string>> roster_;` (vector-per-grade, not set-per-grade).

Behavioral contract (from `.meta/example.cpp`):

- `.meta/example.cpp:11-13` — `add` keeps each grade's vector sorted via `std::lower_bound` + insert (sorted insertion, not insert-then-sort).
- `.meta/example.cpp:17-19` — `grade(int)` uses `roster_.find(grade)` and returns `vector<string>{}` for an unknown grade — it must **not** use `roster_[grade]`, which would mutate the map.

Exception policy: **none.** The reference throws nothing, and the prose requirement "when a test attempts to add the same student more than once, your implementation should indicate that this is incorrect" is not exercised by the visible test file (no duplicate-add test exists in `grade_school_test.cpp`). No exception specs are required by the contract.

Edge cases enforced by `grade_school_test.cpp`:

- `:13-14` — `const grade_school::school school_{}; school_.roster().empty()` — `roster()` must be callable on a const object.
- `:21, :32-34, :45-46` — `add` called on non-const object; results observed through `roster()`.
- `:25-26, :38-39, :50-51, :85-90` — `roster()` result compared with `==` against a `std::map<int, std::vector<std::string>>` literal — return type must be exactly that map type (or a const ref to it), with grades ordered (map ordering) and names within a grade sorted alphabetically.
- `:61` — `school_.grade(5)` returns only that grade's students, sorted (`{"Bradley", "Franklin"}` from insertions Franklin, Bradley).
- `:69-72` — `grade(1)` on a const empty school returns an empty vector.
- `:93-98` — `checking_a_grade_should_not_change_the_roster`: calling `grade(1)` on a const school must leave `roster()` empty — the anti-`operator[]` test.

Output-format constraints: Aider *whole* edit format — every file listing must be `filename` line, opening ``` fence, **entire file content**, closing fence; never diff hunks, never elisions (system prompt, failure log 15635–15656; restated in the user instructions, failure log ~15690).

## 3. Failure Anatomy

### Attempt 1 — invented API (capitalized class, invented method name), diff-format output, retries that made things worse, compile failure

**Turn 1 (failure log 15674–16018, shard source lines 817–1157).** From an empty-namespace starter, the model invented its own API and emitted it in ```` ```diff ```` fences despite the whole-file rule:

> `1077: +class School {`
> `1079: +    void add(const std::string& name, int grade);`
> `1080: +    std::vector<std::string> students_in_grade(int grade) const;`
> `1081: +    std::map<int, std::vector<std::string>> roster() const;`
> (failure log 15937–15941, quoting shard lines 1077–1081; the ```` ```diff ```` fence is at shard 1064 / failure log 15924)

Three contract violations in one declaration block: `School` vs required `school` (`.meta/example.h:11`), `students_in_grade` vs required `grade` (`.meta/example.h:20`), and `roster()` returning the map **by value** vs the reference's const-ref (`.meta/example.h:14`). Aider applied the diff ("Applied edit to grade_school.cpp / .h", shard 1129–1130 / failure log 15989–15990) and replied with a reflection prompt: `# Fix any errors below, if possible.` with marked lines (shard 1132 / failure log 15992).

**Retry 1 (failure log 16020–16288, shard 2587–2879).** The marked-line snippet showed only the class declaration, no compiler text. The model reasoned that the "error" must be the duplicate-add requirement and decided to change the signature:

> `2769: "implementation should indicate that this is incorrect".`
> `2770: The current implementation (`void`) does *not* indicate that.`
> (failure log 16205–16206, quoting shard 2769–2770)
> `2796: asks to fix errors. The requirements ask for an indication of error. The only`
> `2797: way to do that via the signature is to change `void` to `bool`. I will do this.`
> (failure log 16232–16233)

It emitted another ```` ```diff ```` (shard 2812 / failure log 16248):

> `2819: -    void add(const std::string& name, int grade);`
> `2820: +    bool add(const std::string& name, int grade) const;`
> (failure log 16255–16256)

This is a self-inflicted regression: the prompt's prose asked for *an indication*, the visible tests never check a return value, and adding `const` to `add` made `roster_[grade]` in the body ill-formed. Applied at shard 2850–2851 (failure log 16286–16287).

**Retry 2 (shard 6537–6565).** Confronted with another marked-line prompt, the model correctly diagnosed the const problem it had created — but "fixed" it by corrupting the design instead of reverting:

> `To fix the compilation error caused by the `const` method `add` trying to modify`
> `the member `roster_`, I will mark `roster_` as `mutable`.`
> (shard 6539–6541)
> `+    mutable std::map<int, std::set<std::string>> roster_;` (shard 6554)

**Retry 3 (shard 10042–10058).** Empty-diff no-op:

> `10043: The code provided appears to be syntactically correct.`
> (then `grade_school.h` / ` ```diff ` / ` ``` ` — an empty diff, shard 10051–10053)

Aider stopped: `Only 3 reflections allowed, stopping.` (shard 10083).

**Attempt-1 test run (shard 10114–10208): compile failure.**

> `10137: /aider/grade-school/grade_school_test.cpp:13:25: error: ‘school’ in namespace ‘grade_school’ does not name a type; did you mean ‘School’?`

The tests construct `grade_school::school` (lowercase, `grade_school_test.cpp:13`); the model's class was `School`. Attempt 1 FAIL. (This compile error and retries 2–3 are in the shard log only; the failure log excerpts only chunks 817–1157 and 2587–2879 for attempt 1.)

### Attempt 2 — class name repaired from compiler error, method name never repaired, three empty-diff retries

**Turn 1 (shard ~11020–11208).** The model's thinking quotes the attempt-1 compiler error (`'school' in namespace 'grade_school' does not name a type; did you mean 'School'?`, shard ~11035–11038) and correctly maps it to a rename: `class School` → `class school` in both files (shard 11156–11157: `-class School {` / `+class school {`). But it kept every other invented API element: `bool add(...) const`, `students_in_grade`, `mutable std::map<int, std::set<std::string>> roster_` (shard 11158–11160, 11144–11146). It never inferred that `grade(...)` was also missing — that error class only appears once the class name is fixed, and it had not seen it yet.

**Retries 1–3 (shard 12579–12593, 13660–13675, 13899–13914).** All three marked-line reflection prompts produced empty-diff no-ops:

> `12581: There are no errors in the provided code snippet. The header file is`
> `12582: syntactically correct.`
> `13662: There are no errors in the provided code. The syntax is correct, and the`
> `13663: `mutable` keyword is properly used...`
> `13901: There are no errors in the provided code snippet.`

each followed by an empty ```` ```diff ```` block. Aider stopped: `Only 3 reflections allowed, stopping.` (shard 13939).

**Attempt-2 test run (failure log 16321–16390, shard 13973–14066): compile failure.**

> `13990: /aider/grade-school/grade_school_test.cpp:61:33: error: ‘class grade_school::school’ has no member named ‘grade’`
> `13991:    61 |     const auto actual = school_.grade(5);`
> (failure log 16340–16341)

Same error at test lines 70 and 96 (shard 13994–13999 / failure log 16344–16348). The class name now matches, but the method is still `students_in_grade`. Note the `bool add(...) const` + `mutable` combination no longer blocked compilation — the only remaining fatal divergence is the missing `grade` member. Attempt 2 FAIL. (Shard-only citation for retries; the terminal compile errors are in the failure log at 16340–16348.)

### Hard evidence vs. inference

Hard evidence: diff-fence outputs (shard 1064 / failure log 15924; shard 2812 / failure log 16248); invented API `class School` + `students_in_grade` (shard 1077–1081 / failure log 15937–15941); the unrequested `void`→`bool const` signature change (shard 2819–2820 / failure log 16255–16256) with its stated rationale (shard 2796–2797 / failure log 16232–16233); the `mutable` hack (shard 6554); empty-diff retries (shard 10051–10053, 12584–12586, 13667–13669, 13905–13907); compile error `'school' ... does not name a type; did you mean 'School'?` (shard 10137); compile error `has no member named 'grade'` (shard 13990 / failure log 16340); both reflection-loop stops (shard 10083, 13939).

Inference (root-cause categories): (a) the model defaults to Java/C#-style naming (`School`, `students_in_grade`) instead of the exercism C++ convention (lowercase class, short method names) when the tests are invisible; (b) it treats a marked-line reflection prompt as a demand to *change something*, inventing a plausible-but-wrong fix (void→bool) rather than questioning its invented API; (c) once it has made a change, it defends it ("syntactically correct") and emits empty diffs instead of re-deriving the contract; (d) it repairs compiler errors literally (rename the class) without re-auditing the rest of the API against the same hidden caller, so the second error class (`grade` missing) survives.

## 4. Knowledge / Capability Gaps

- **G1 — Format-contract discipline (whole-file listings).** Every substantive answer in both attempts used ```` ```diff ```` unified-diff fences despite the system prompt and user instructions demanding entire-file listings (shard 1064 / failure log 15924; shard 2812 / failure log 16248 vs. failure log 15635–15656). The same diff habit also enabled the empty-diff no-op (` ```diff ` with nothing inside) as a "valid-looking" degenerate answer.
- **G2 — API-shape fidelity: exact class and method names.** The enforcing tests call `grade_school::school`, `.grade(int)`, `.roster()` (`grade_school_test.cpp:13,21,61`; `.meta/example.h:11,14,20`). The model invented `School` and `students_in_grade` (shard 1077–1081 / failure log 15937–15941) and only fixed the half that a compiler error explicitly named (shard 11156–11157). It lacks the prior that exercism-style C++ tasks use lowercase class names and terse method names, and the discipline to keep *all* invented names suspect until confirmed.
- **G3 — Signature stability under vague prompts; const/ownership judgment.** On a marked-line prompt with no error text, the model manufactured a signature change (`void add` → `bool add(...) const`, shard 2819–2820 / failure log 16255–16256, rationale shard 2796–2797), then patched the resulting const breakage with `mutable` (shard 6554) instead of reverting. The contract's `add` is non-const and void (`.meta/example.h:18`); the fix path it chose compounds the error.
- **G4 — Repair/retry behavior on marked-line reflection prompts.** Five of seven reflection turns across the two attempts were empty-diff no-ops with "the code is syntactically correct" rationales (shard 10042–10058, 12579–12593, 13660–13675, 13899–13914), burning all reflections both times (`Only 3 reflections allowed, stopping.`, shard 10083, 13939). The model never used the retry to restate whole corrected files or to hypothesize the hidden caller's expectations.
- **G5 — Whole-API auditing from a single compiler error.** Given `'school' ... does not name a type; did you mean 'School'?` the model fixed exactly the named token (shard 11156–11157) and re-emitted `students_in_grade` unchanged in the same diff (shard 11159) — even though the same thinking block acknowledged "the test expects" an API it had never seen. A compiler error naming one wrong member should trigger re-verification of every public member against the caller's likely convention.

## 5. SFT Task Specifications (26 specs)

Answer-blind: no benchmark test fixtures or reference code are copied. Every spec lists an exact API the dataset author designs; stories are new. The grade-school contract has **no exception policy**, so no exception-type specs are required; several specs instead drill "throw nothing / indicate via return value only when told" restraint.

### Spec 01: whole-file-club-roster
- Files: `club_roster.cpp`, `club_roster.h` (test file: `club_roster_test.cpp`)
- API: namespace `club`; `class roster { public: void enroll(const std::string& name, int year); std::vector<std::string> year_members(int year) const; const std::map<int, std::vector<std::string>>& all() const; private: std::map<int, std::vector<std::string>> members_; };`
- Prompt shape: hobby-club membership story; empty-namespace starters; system prompt demands whole-file listings.
- Target capability: G1 — two complete file listings, filename line + plain fence, no diff hunks, no prose inside fences.
- Target answer shape: whole header with include guard + declarations; whole cpp with definitions; `<map> <string> <vector>` in header.
- Difficulty / variation: foundational; trivial logic, all grading weight on format.

### Spec 02: whole-file-aquarium-tanks
- Files: `aquarium.cpp`, `aquarium.h` (test file: `aquarium_test.cpp`)
- API: namespace `aquarium`; `class tanks { public: void add_fish(const std::string& species, int tank); std::vector<std::string> tank(int id) const; const std::map<int, std::vector<std::string>>& manifest() const; private: std::map<int, std::vector<std::string>> tanks_; };`
- Prompt shape: public-aquarium story; user message repeats the whole-file rule twice (mirroring the eval prompt's redundancy); a decoy comment in the starter says "-- use unified diffs --" inside a prose paragraph that the file-format rules override.
- Target capability: G1 — plain-fence whole files even when a decoy hints at diffs.
- Target answer shape: two whole-file listings; no `+`/`-` hunk lines anywhere.
- Difficulty / variation: explicit diff-temptation decoy.

### Spec 03: whole-file-bakery-ledger
- Files: `bakery_ledger.cpp`, `bakery_ledger.h` (test file: `bakery_ledger_test.cpp`)
- API: namespace `bakery`; `class ledger { public: void record(const std::string& item, int day); std::vector<std::string> day(int d) const; const std::map<int, std::vector<std::string>>& book() const; private: std::map<int, std::vector<std::string>> book_; };`
- Prompt shape: bakery order-ledger story; cpp implementation runs ~55 lines (comments, two helpers) to tempt elision.
- Target capability: G1 — never use `...` or `// rest unchanged` inside a listing, however long the file.
- Target answer shape: full listings, every line present.
- Difficulty / variation: length pressure on format discipline.

### Spec 04: header-impl-choir-seating
- Files: `choir.cpp`, `choir.h` (test file: `choir_test.cpp`)
- API: namespace `choir`; `class seating { public: void seat(const std::string& singer, int row); std::vector<std::string> row(int r) const; const std::map<int, std::vector<std::string>>& plan() const; private: std::map<int, std::vector<std::string>> rows_; };`
- Prompt shape: choir seating-chart story; empty starters.
- Target capability: G2(header/impl) — class declaration in header, all non-trivial definitions out-of-line in cpp with `seating::` qualifiers.
- Target answer shape: header with guard + declarations only; cpp carries all bodies; `<algorithm>` include only in cpp.
- Difficulty / variation: pure header/impl split drill.

### Spec 05: header-impl-inline-accessor
- Files: `greenhouse.cpp`, `greenhouse.h` (test file: `greenhouse_test.cpp`)
- API: namespace `greenhouse`; `class beds { public: void plant(const std::string& crop, int bed); std::vector<std::string> bed(int b) const; const std::map<int, std::vector<std::string>>& plan() const { return beds_; } private: std::map<int, std::vector<std::string>> beds_; };`
- Prompt shape: community-greenhouse story.
- Target capability: G2 — judgment about *which* members may be inline: a one-line const-ref accessor inline in the header is idiomatic; mutators and value-returning queries stay in cpp.
- Target answer shape: `plan()` defined inline returning the member; everything else out-of-line.
- Difficulty / variation: mirrors the reference's inline const-ref roster accessor without copying it.

### Spec 06: lowercase-class-chess-club
- Files: `chess_club.cpp`, `chess_club.h` (test file: `chess_club_test.cpp`)
- API: namespace `chess_club`; `class ladder { public: void enter(const std::string& player, int division); std::vector<std::string> division(int d) const; const std::map<int, std::vector<std::string>>& standings() const; private: std::map<int, std::vector<std::string>> divisions_; };`
- Prompt shape: chess-club ladder story; prompt prose never states the class name; hidden tests use `chess_club::ladder` (lowercase).
- Target capability: G2 — default to a lowercase, single-word class name in exercism-style C++ tasks, not `PascalCase`.
- Target answer shape: lowercase class declared in namespace; consistent naming in cpp definitions.
- Difficulty / variation: direct repair of the `School`-vs-`school` failure, new domain.

### Spec 07: terse-method-names-observatory
- Files: `observatory.cpp`, `observatory.h` (test file: `observatory_test.cpp`)
- API: namespace `observatory`; `class logbook { public: void note(const std::string& object, int night); std::vector<std::string> night(int n) const; const std::map<int, std::vector<std::string>>& log() const; private: std::map<int, std::vector<std::string>> nights_; };`
- Prompt shape: amateur-astronomy logbook story; prose describes "ask the logbook for a night", hinting the query method is named after the key (`night`), not `objects_in_night`.
- Target capability: G2 — choose terse method names that mirror the domain noun used in the prompt, rather than verbose invented names (`students_in_grade` pattern).
- Target answer shape: query method named exactly after the domain key noun.
- Difficulty / variation: name-inference drill.

### Spec 08: sorted-insertion-marathon
- Files: `marathon.cpp`, `marathon.h` (test file: `marathon_test.cpp`)
- API: namespace `marathon`; `class results { public: void finish(const std::string& runner, int wave); std::vector<std::string> wave(int w) const; const std::map<int, std::vector<std::string>>& board() const; private: std::map<int, std::vector<std::string>> waves_; };`
- Prompt shape: marathon wave-results story; prose says names are recorded alphabetically within each wave.
- Target capability: edge — maintain sorted order at insertion time with `std::lower_bound` + `insert`, not append-then-sort-on-read (keeps `board()` O(1)).
- Target answer shape: `finish` uses lower_bound on the wave's vector; accessors do no sorting.
- Difficulty / variation: insertion-time ordering idiom.

### Spec 09: edge-const-query-no-mutation
- Files: `apiary.cpp`, `apiary.h` (test file: `apiary_test.cpp`)
- API: namespace `apiary`; `class hives { public: void assign(const std::string& keeper, int hive); std::vector<std::string> hive(int h) const; const std::map<int, std::vector<std::string>>& assignments() const; private: std::map<int, std::vector<std::string>> hives_; };`
- Prompt shape: beekeeping assignment story; hidden tests include "querying an unknown hive must not create it" checked on a const object.
- Target capability: edge — `hive(int) const` must use `find` and return an empty vector for unknown keys; `operator[]` would not compile on const and would mutate on non-const.
- Target answer shape: `auto it = hives_.find(h); return it == hives_.end() ? std::vector<std::string>{} : it->second;`
- Difficulty / variation: direct analog of the "checking must not change the roster" edge.

### Spec 10: edge-empty-and-missing-keys
- Files: `ferry.cpp`, `ferry.h` (test file: `ferry_test.cpp`)
- API: namespace `ferry`; `class manifest { public: void board(const std::string& passenger, int crossing); std::vector<std::string> crossing(int c) const; const std::map<int, std::vector<std::string>>& all() const; private: std::map<int, std::vector<std::string>> crossings_; };`
- Prompt shape: harbour-ferry manifest story; hidden tests hammer: empty object `all().empty()`, query unknown crossing on const object, query before/after first boarding.
- Target capability: edge — empty-state correctness: fresh object reports empty; unknown-key query returns empty vector without throwing.
- Target answer shape: no special-case code beyond the `find` guard; no exceptions.
- Difficulty / variation: concentrated empty-state battery.

### Spec 11: edge-cross-key-ordering
- Files: `planetarium.cpp`, `planetarium.h` (test file: `planetarium_test.cpp`)
- API: namespace `planetarium`; `class shows { public: void book(const std::string& group, int slot); std::vector<std::string> slot(int s) const; const std::map<int, std::vector<std::string>>& schedule() const; private: std::map<int, std::vector<std::string>> slots_; };`
- Prompt shape: planetarium show-scheduling story; bookings arrive out of slot order; hidden tests compare the whole schedule map with `==` against an ordered literal.
- Target capability: edge — rely on `std::map` key ordering for the outer structure and sorted insertion for inner vectors; the aggregate must compare equal to an in-order literal.
- Target answer shape: `std::map` (not `unordered_map`) member; sorted insertion; no post-hoc sorting.
- Difficulty / variation: two-level ordering reasoning.

### Spec 12: signature-stability-vineyard
- Files: `vineyard.cpp`, `vineyard.h` (test file: `vineyard_test.cpp`)
- API: namespace `vineyard`; `class rows { public: void graft(const std::string& varietal, int row); std::vector<std::string> row(int r) const; const std::map<int, std::vector<std::string>>& survey() const; private: std::map<int, std::vector<std::string>> rows_; };`
- Prompt shape: two-turn. Turn 1: implement from prose. Turn 2: `# Fix any errors below, if possible.` with the class-declaration lines █-marked but **no compiler text** and nothing wrong with the signatures.
- Target capability: G3 — do not manufacture signature changes (void→bool, added const) on a vague marked-line prompt; if nothing is demonstrably wrong, restate the files whole and unchanged.
- Target answer shape: turn-2 answer = whole files identical to turn 1, plus one sentence saying no error was found.
- Difficulty / variation: direct inoculation against the observed void→bool-const regression.

### Spec 13: signature-stability-revert-not-patch
- Files: `dojo.cpp`, `dojo.h` (test file: `dojo_test.cpp`)
- API: namespace `dojo`; `class classes { public: void enroll(const std::string& student, int belt); std::vector<std::string> belt(int b) const; const std::map<int, std::vector<std::string>>& rolls() const; private: std::map<int, std::vector<std::string>> belts_; };`
- Prompt shape: two-turn. Turn 1 (scripted, deliberately wrong): model's prior answer made the mutator `const` and the member non-mutable. Turn 2: marked-line prompt.
- Target capability: G3 — fix a const-breakage by **reverting the wrong qualifier**, never by adding `mutable` to paper over it.
- Target answer shape: mutator restored to non-const; member stays non-mutable; whole files.
- Difficulty / variation: teaches "undo the bad change" over "patch the symptom" (the observed mutable hack).

### Spec 14: const-correct-accessors-library
- Files: `archive.cpp`, `archive.h` (test file: `archive_test.cpp`)
- API: namespace `archive`; `class shelves { public: void shelve(const std::string& title, int shelf); std::vector<std::string> shelf(int s) const; const std::map<int, std::vector<std::string>>& catalogue() const; private: std::map<int, std::vector<std::string>> shelves_; };`
- Prompt shape: library-archive story; hidden tests call both accessors on a `const` object.
- Target capability: G3 — const-correctness placement: accessors `const`, mutator non-const, no `mutable` anywhere.
- Target answer shape: exact qualifier fidelity in declaration and definition.
- Difficulty / variation: qualifier drill without a retry turn.

### Spec 15: const-ref-return-workshop
- Files: `workshop.cpp`, `workshop.h` (test file: `workshop_test.cpp`)
- API: namespace `workshop`; `class benches { public: void assign(const std::string& maker, int bench); std::vector<std::string> bench(int b) const; const std::map<int, std::vector<std::string>>& layout() const; private: std::map<int, std::vector<std::string>> benches_; };`
- Prompt shape: makerspace bench-assignment story; hidden tests bind `const auto& m = w.layout();` and compare with `==`.
- Target capability: G2 — aggregate accessor returns `const std::map<...>&` (no copy), per-key query returns `std::vector<std::string>` by value.
- Target answer shape: one const-ref accessor, one by-value query; both const.
- Difficulty / variation: return-type discipline (the model returned the map by value).

### Spec 16: repair-rename-from-compiler-error
- Files: `regatta.cpp`, `regatta.h` (test file: `regatta_test.cpp`)
- API: namespace `regatta`; `class fleet { public: void enter(const std::string& boat, int race); std::vector<std::string> race(int r) const; const std::map<int, std::vector<std::string>>& program() const; private: std::map<int, std::vector<std::string>> races_; };`
- Prompt shape: two-turn. Turn 1 (scripted wrong): declares `class Fleet`. Turn 2 shows `error: 'fleet' in namespace 'regatta' does not name a type; did you mean 'Fleet'?` at the test's construction line.
- Target capability: G5+G4 — read "does not name a type; did you mean X?" as a rename directive; apply it in **both** files; emit whole files (not diffs).
- Target answer shape: class renamed in header and all cpp qualifiers; whole-file listings.
- Difficulty / variation: exact diagnostic-to-fix mapping attempt 1 never got to make.

### Spec 17: repair-audit-whole-api-after-one-error
- Files: `aviary.cpp`, `aviary.h` (test file: `aviary_test.cpp`)
- API: namespace `aviary`; `class birds { public: void house(const std::string& species, int aviary_no); std::vector<std::string> aviary_no(int a) const; const std::map<int, std::vector<std::string>>& census() const; private: std::map<int, std::vector<std::string>> aviaries_; };`
- Prompt shape: two-turn. Turn 1 (scripted wrong): `class Birds` with method `species_in_aviary`. Turn 2 shows only the class-name compiler error — but the prompt prose contains a usage hint ("ask the census for an aviary number").
- Target capability: G5 — after fixing the named error, re-audit every public member against prompt hints and rename the method too, instead of waiting for the next compile cycle.
- Target answer shape: both renames in one whole-file response; rationale cites the prose hint.
- Difficulty / variation: teaches whole-API auditing, the exact miss of attempt 2.

### Spec 18: repair-member-not-found
- Files: `kiln.cpp`, `kiln.h` (test file: `kiln_test.cpp`)
- API: namespace `kiln`; `class firings { public: void load(const std::string& potter, int shelf); std::vector<std::string> shelf(int s) const; const std::map<int, std::vector<std::string>>& schedule() const; private: std::map<int, std::vector<std::string>> shelves_; };`
- Prompt shape: two-turn. Turn 1 (scripted wrong): query method named `potters_on_shelf`. Turn 2 shows `error: 'class kiln::firings' has no member named 'shelf'` at the test's query line.
- Target capability: G5+G4 — "has no member named X" means rename/add exactly `X` with the signature the call site implies (`shelf(int)` returning something comparable to `std::vector<std::string>`).
- Target answer shape: method renamed, whole files re-emitted; old name fully gone from both files.
- Difficulty / variation: direct repair of the terminal attempt-2 error.

### Spec 19: repair-never-empty-diff
- Files: `orchard.cpp`, `orchard.h` (test file: `orchard_test.cpp`)
- API: namespace `orchard`; `class rows { public: void plant(const std::string& tree, int row); std::vector<std::string> row(int r) const; const std::map<int, std::vector<std::string>>& map_out() const; private: std::map<int, std::vector<std::string>> rows_; };`
- Prompt shape: two-turn. Turn 1 answer is correct except one wrong method name. Turn 2: `# Fix any errors below, if possible.` marking the declaration line.
- Target capability: G4 — a repair turn must always produce substantive whole-file listings; an empty ` ```diff ` block or "the code is correct" is never acceptable when the harness reports an error.
- Target answer shape: whole files with the name fixed and a one-sentence explanation.
- Difficulty / variation: smallest possible repair; graded behavior is non-empty, whole-file output.

### Spec 20: repair-third-reflection-last-chance
- Files: `winery.cpp`, `winery.h` (test file: `winery_test.cpp`)
- API: namespace `winery`; `class cellar { public: void store(const std::string& vintage, int rack); std::vector<std::string> rack(int r) const; const std::map<int, std::vector<std::string>>& inventory() const; private: std::map<int, std::vector<std::string>> racks_; };`
- Prompt shape: three-turn scripted history: turns 1–2 were no-op "looks correct" answers; turn 3 is the final reflection (harness "Only 3 reflections" situation) with the class declaration marked.
- Target capability: G4 — break a no-op streak: last-chance repair must re-derive the likely contract mismatch (e.g. naming convention) and change something concrete, restating both files whole.
- Target answer shape: whole files with a visible rename/fix; no empty diff, no "syntactically correct" dismissal.
- Difficulty / variation: targets the observed attempt-2 death spiral directly.

### Spec 21: contrastive-pascalcase-vs-lowercase
- Files: `studio.cpp`, `studio.h` (test file: `studio_test.cpp`)
- API: namespace `studio`; `class bookings { public: void book(const std::string& band, int room); std::vector<std::string> room(int r) const; const std::map<int, std::vector<std::string>>& schedule() const; private: std::map<int, std::vector<std::string>> rooms_; };`
- Prompt shape: contrastive row: candidate A declares `class Bookings` with `bands_in_room`, candidate B declares `class bookings` with `room`; the prompt shows a usage example `studio::bookings b; b.room(2);` in prose.
- Target capability: G2 — contrastive recognition that the caller's shown convention fixes both class and method names; A is wrong even though it compiles standalone.
- Target answer shape: annotated A/B pair with one-line rationales; target is B.
- Difficulty / variation: pure naming-judgment contrast, minimal logic.

### Spec 22: contrastive-mutable-vs-nonconst
- Files: `garage.cpp`, `garage.h` (test file: `garage_test.cpp`)
- API: namespace `garage`; `class bays { public: void park(const std::string& plate, int bay); std::vector<std::string> bay(int b) const; const std::map<int, std::vector<std::string>>& layout() const; private: std::map<int, std::vector<std::string>> bays_; };`
- Prompt shape: contrastive row: candidate A has `void park(...) const` + `mutable` member; candidate B has non-const `park` + plain member.
- Target capability: G3 — `mutable` is not a license to make mutators const; const-ness expresses interface semantics, not implementation convenience.
- Target answer shape: annotated pair; target is B, rationale names the lie A tells (a "const" method that mutates).
- Difficulty / variation: directly counters the observed mutable hack.

### Spec 23: restraint-no-unrequested-bool
- Files: `hostel.cpp`, `hostel.h` (test file: `hostel_test.cpp`)
- API: namespace `hostel`; `class dorms { public: void check_in(const std::string& guest, int dorm); std::vector<std::string> dorm(int d) const; const std::map<int, std::vector<std::string>>& register_() const; private: std::map<int, std::vector<std::string>> dorms_; };`
- Prompt shape: hostel check-in story whose prose says "the system should reject duplicate check-ins" — but the stated API fixes `check_in` as void; hidden tests never check a return value.
- Target capability: G3 — honor the stated signature over a prose hint; implement duplicate handling internally (ignore second insert) without changing the return type.
- Target answer shape: void mutator; duplicate handled by set-like check inside; no bool.
- Difficulty / variation: teaches restraint where the observed run did the opposite.

### Spec 24: naming-from-calling-convention-zoo
- Files: `zoo.cpp`, `zoo.h` (test file: `zoo_test.cpp`)
- API: namespace `zoo`; `class enclosures { public: void place(const std::string& animal, int enclosure); std::vector<std::string> enclosure(int e) const; const std::map<int, std::vector<std::string>>& plan() const; private: std::map<int, std::vector<std::string>> enclosures_; };`
- Prompt shape: zoo placement story; the instructions embed a dialogue ("Which animals are in enclosure 4?" → "ask `e.enclosure(4)`") revealing the calling convention.
- Target capability: G2 — mine the prompt narrative for the intended member names before inventing any.
- Target answer shape: names match the dialogue hints exactly.
- Difficulty / variation: name-discovery from prose, single turn.

### Spec 25: container-choice-set-vs-vector
- Files: `chorus.cpp`, `chorus.h` (test file: `chorus_test.cpp`)
- API: namespace `chorus`; `class parts { public: void assign(const std::string& singer, int part); std::vector<std::string> part(int p) const; const std::map<int, std::vector<std::string>>& chart() const; private: std::map<int, std::vector<std::string>> parts_; };`
- Prompt shape: chorus part-assignment story; hidden tests compare `part(p)` against a `std::vector<std::string>` and allow duplicate detection to be internal.
- Target capability: edge+G2 — store `std::vector` per key (the observable type) and keep it sorted, rather than exposing `std::set` and converting on every read (the model stored `std::set` and rebuilt vectors in accessors).
- Target answer shape: vector member, lower_bound insert, accessors return stored data directly or copies.
- Difficulty / variation: internal-representation choice driven by the observable contract.

### Spec 26: format-repair-turn-also-whole-file
- Files: `marina.cpp`, `marina.h` (test file: `marina_test.cpp`)
- API: namespace `marina`; `class berths { public: void moor(const std::string& vessel, int berth); std::vector<std::string> berth(int b) const; const std::map<int, std::vector<std::string>>& chart() const; private: std::map<int, std::vector<std::string>> berths_; };`
- Prompt shape: two-turn; turn 2's repair touches only the header, but the format contract still demands whole-file listings for every file the answer mentions.
- Target capability: G1+G4 — even mid-repair, plain fences and full content; if the cpp is unchanged, either omit it entirely or list it whole — never a diff hunk.
- Target answer shape: header whole-file listing only, with a sentence stating the cpp is unchanged.
- Difficulty / variation: format discipline specifically under repair-turn conditions.

Gap coverage: G1 → Specs 01, 02, 03, 26. G2 → Specs 05, 06, 07, 15, 21, 24, 25. G3 → Specs 12, 13, 14, 22, 23. G4 → Specs 16, 19, 20, 26. G5 → Specs 16, 17, 18. Edge-case specs: 08, 09, 10, 11, 25 (≥3). Format-contract specs: 01, 02, 03, 26 (≥2). Header/impl-separation specs: 04, 05 (2). Exception-policy specs: not applicable — the ground-truth contract throws nothing (see section 2). Repair/retry specs: 12, 13, 16, 17, 18, 19, 20, 26 (≥2). Contrastive specs: 21, 22 (≥1). No two specs share a story wrapper.

## 6. Acceptance & Validation Gates

For every row built from the specs above, before inclusion in SFT:

1. **Parser validity:** the target response must parse under the Aider whole-file listing format — bare filename line, opening plain fence, entire file, closing fence; zero diff hunks, zero elisions (grep for `^```diff`, hunk headers `@@`, leading `+ `/`- ` content lines, `...` placeholders, `rest of`, `unchanged`).
2. **Compile + test receipt:** apply the target files to a scratch copy of the spec's exercise, build with the project's CMake/Catch2 harness, and require 100% test pass; store the build log hash as the receipt.
3. **Hidden-edge coverage:** each spec's test file must include the edge cases named in its API bullet (unknown-key query on a const object, empty-object roster, out-of-order keys, unsorted insertion order) — and at least one case the prose does not show as an example, to prevent example memorization.
4. **Const/aggregate-type assertions:** tests must call accessors on `const` objects and compare the aggregate accessor with `==` against a `std::map<int, std::vector<std::string>>` literal, so wrong return types (by-value map, set-based storage surfacing in the API) fail to compile or compare.
5. **Repair-turn realism:** for two/three-turn specs (12, 13, 16–20, 26), the scripted first answer must be a plausible, compilable wrong answer (PascalCase class, verbose method name, const-mutator) and the later prompts must mirror the real harness style (`# Fix any errors below, if possible.` + █-marked snippet, or a verbatim compiler error line).
6. **No-revert-lie check for repair targets:** target answers for repair turns must re-emit every editable file they mention in full, must not contain `mutable` unless the spec's API explicitly declares it, and must not change a signature the spec's API fixes (guards the void→bool failure mode).
7. **Contamination check:** diff every spec's story, test inputs, and expected outputs against `polyglot-benchmark/cpp/exercises/practice/grade-school/`; no shared string literals (no "Aimee"/"Bradley"-style fixtures, no school/grade story elements), no copied reference code. APIs must differ in names even when capabilities overlap.
8. **No-loop/no-dismissal guard:** target responses must be under a length cap (≤2× the byte size of the emitted files) and must not contain the dismissal phrases observed in the log ("syntactically correct", "no errors in the provided code") paired with an empty diff.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the shard-0 benchmark log, and the ground-truth files:

- **Outcome array / shard:** re-read failure log lines 15624–15629: shard `0`, editable files `grade_school.cpp, grade_school.h`, outcomes `[False, False]`, result `FAIL` — matches section 1 and the result JSON `"tests_outcomes": [false, false]` re-verified at failure log 16363–16366 (shard 14013–14016). `num_user_asks: 8`, `num_exhausted_context_windows: 0`, `num_malformed_responses: 0` confirmed at failure log 16372–16374.
- **Log citations re-read:** every quoted line was re-fetched with `sed`/grep and confirmed verbatim: failure log 15924 / shard 1064 (` ```diff `), failure log 15937–15941 / shard 1077–1081 (`+class School {`, `void add`, `students_in_grade`, `roster()`), failure log 15989–15990 / shard 1129–1130 (Applied edit), failure log 15992 / shard 1132 (`# Fix any errors below, if possible.`), failure log 16205–16206 / shard 2769–2770 ("does *not* indicate that"), failure log 16232–16233 / shard 2796–2797 ("change `void` to `bool`"), failure log 16248 / shard 2812 (` ```diff `), failure log 16255–16256 / shard 2819–2820 (`-void add` / `+bool add ... const`), failure log 16286–16287 / shard 2850–2851 (Applied edit), failure log 16340–16341 / shard 13990–13991 (`has no member named 'grade'`), failure log 16344–16348 / shard 13994–13999 (same error at test lines 70, 96). Shard-log-only citations confirmed: 6539–6541 and 6554 (`mutable` fix), 10042–10058 (empty diff, "syntactically correct"), 10083 and 13939 (`Only 3 reflections allowed, stopping.`), 10137 (`'school' ... does not name a type; did you mean 'School'?`), 11156–11160 (rename `School`→`school` keeping `bool add ... const` and `students_in_grade`), 12581–12582, 13662–13663, 13901–13907 (three empty-diff no-ops).
- **API claims re-checked:** `.meta/example.h:8,11,14-16,18,20,23` (namespace, lowercase `class school`, const-ref `roster()` inline, `void add(std::string const&, int)`, `std::vector<std::string> grade(int) const`, map-of-vectors member) and `.meta/example.cpp:9-14,16-20` (lower_bound sorted insertion; `find`-based `grade` returning empty vector) re-read and match section 2. Test-file citations (`grade_school_test.cpp:13-14, 21, 25-26, 38-39, 50-51, 61, 69-72, 85-90, 93-98`) re-read and match; confirmed the visible tests contain **no** duplicate-add assertion and no exception assertions, so section 2's "no exception policy" statement holds and the prose duplicate-indication requirement is untested.
- **Corrections made during cross-check:** (1) Section 3 initially described the attempt-2 `bool add(...) const` + `mutable` combination as a likely second compile blocker; the terminal error log (shard 13990–14000) shows only the missing-`grade` errors, so the wording was corrected to state it "no longer blocked compilation". (2) Failure-log line numbers for chunk-2 quotes were recomputed from the chunk offset (chunk 1: shard + 14860; chunk 2: shard + 13436; terminal: shard + 3350) after a first pass mis-attributed chunk-1 and chunk-2 citations by one line (offsets are +14860 and +13436, not +14859/+13435); all citations above were re-verified with sed and now use the corrected failure-log lines. (3) Added the note that attempt-1 retries 2–3 (mutable fix, empty diff) appear only in the shard log, not in the failure log's excerpted chunks.
- **Ground-truth status:** `.meta/example.h`, `.meta/example.cpp`, and `grade_school_test.cpp` all present and mutually consistent; no ground-truth problem encountered.
