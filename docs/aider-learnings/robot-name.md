# robot-name — Failure Learning Document

Date of analysis: 2026-07-24. Eval run: `glm47-aider-expansion-sft-fixed26-20260723T091839Z` (GLM-4.7 SFT, Aider Polyglot C++, whole edit format).

## 1. Task Identity & Evidence Pointers

- Task slug: `robot-name`
- Shard: `1`
- Test outcomes: `[False, True]` (attempt 1 FAIL, attempt 2 PASS) — final result `PASS`.
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md`, lines 66799–85043 (section header at 66799–66804; reconstructed prompt JSON at 66806–66847; attempt-1 chunk at 66849; attempt-1-retry chunk at 67330; "Where It Failed / Terminal Test Log" at 68035 spanning shard source lines 28862–45863; result JSON at 84990–85041).
- The failure log embeds raw shard-log excerpts with the shard log's own line numbers (e.g. `1072:`, `45622:`). The terminal excerpt (failure log 68040–85041) covers shard lines 28862–45863 and therefore contains interleaved content from **other tasks** (zebra-puzzle ~28961/29993, sublist ~30466/39280, queen-attack ~39851, linked-list ~41645, parallel-letter-frequency ~35213/35325). All robot-name evidence cited below was attributed by checking that the quoted lines reference `robot_name`/`robot-name`; the zebra-puzzle "error message" the model appears to recite at shard 28961–28962 is foreign-task content from the shared shard log, not robot-name reasoning.
- Ground truth (read-only): `polyglot-benchmark/cpp/exercises/practice/robot-name/`
  - Reference: `.meta/example.h`, `.meta/example.cpp`
  - Tests: `robot_name_test.cpp`
  - Starters (NOT the solution): `robot_name.cpp`, `robot_name.h` at the exercise root (empty `namespace robot_name { }` in both, per the chat file-dump at failure log 66832).
- Existing analog dir: none for robot-name under `aider-fixed26-analogs/` (granularity reference: `aider-fixed26-analogs/fixed26-b001-all-your-base/`).
- Result JSON (failure log 84990–85041 / shard 45812–45863): `"tests_outcomes": [false, true]`, `"num_error_outputs": 1`, `"num_user_asks": 6`, `"num_exhausted_context_windows": 1`, `"num_malformed_responses": 0`, `"edit_format": "whole"`, `"completion_tokens": 16994`. Final test run: `All tests passed (2004 assertions in 5 test cases)` (failure log 84985–84986 / shard 45807–45808).

## 2. Benchmark Contract (Ground Truth)

File set: `robot_name.h` + `robot_name.cpp`, namespace `robot_name`.

Public API (from `.meta/example.h`):

- `.meta/example.h:9` — `class robot` **inside** `namespace robot_name` — note the class name is **lowercase** `robot`. This casing is the hard contract: the tests write `robot_name::robot` (`robot_name_test.cpp:29,37,44,45,52,62`).
- `.meta/example.h:12` — `robot();` (constructor assigns the first name).
- `.meta/example.h:14` — `std::string const &name() const { return name_; }` (reference returns `const&` and is header-inline; returning `std::string` **by value** out-of-line also satisfies the tests — the model's passing solution did exactly that).
- `.meta/example.h:16` — `void reset();` (assigns a new, previously unused name).
- `.meta/example.h:18-19` — `private: std::string name_;`

Semantics enforced by `robot_name_test.cpp`:

- Name format: exactly 5 chars, 2 uppercase letters + 3 digits — `validate_name` helper at `robot_name_test.cpp:18-24` (`isupper/isupper/isdigit×3`), asserted at `:31` and in the loop at `:69`.
- Name is stable across calls without reset: `:35-40` (`name_is_the_same_each_time`).
- Two distinct robots have distinct names: `:42-48`.
- `reset()` changes the name: `:50-58`.
- **Exhaustion edge case**: `:60-72` (`exhausting_digits_yields_different_names`) — 1000 consecutive `reset()` calls must each yield a fresh, valid, never-before-seen name (this produces the bulk of the "2004 assertions in 5 test cases"). Note 1000 resets exhaust the full 000–999 digit space of one letter prefix, so a naive fixed-prefix generator fails here; a collision-retry RNG scheme or a prefix-rollover counter both pass.
- The tests do **not** assert randomness quality, exception types, or header-inline vs out-of-line accessors.

Reference implementation notes (`.meta/example.cpp`, NOT copied into any spec): sequential generation — static prefix `"AA"` and counter in `generate_name()` (`.meta/example.cpp:30-43`), `next_prefix` helper (`.meta/example.cpp:14-28`) invoked for rollover when `unit_number > 999` (`:35-36`), and `throw range_error("prefix combinations exhausted")` (`:20`, i.e. `std::range_error` via `using namespace std`) only when all 676 prefixes are used up. This exhaustion `std::range_error` is the contract's only exception policy and is **not reachable** by the shipped tests. The instructions prose (failure log 66841) demands *random* names ("should not follow a predictable sequence"); the reference is sequential — evidence that the enforced contract is the test file, not the prose or the reference's strategy.

Output-format constraints: Aider *whole* edit format — filename line, opening ``` fence, entire file content, closing fence; never diff hunks, never elisions (system prompt, failure log 66813; restated in the user instructions, failure log 66841).

## 3. Failure Anatomy

### Attempt 1 — `Robot` vs `robot` casing mismatch → compile failure; retry died in a repetition loop

**Turn 1 (failure log 66849–67327, shard source lines 1072–1547).** The model's design was substantively fine — class in namespace, static `_used_names` collision set, `mt19937` + `ostringstream` zero-padded digits — but it named the class with its default C++ convention instead of the exercise convention:

> `1420: robot_name.h`
> `1422: ```diff`
> `1435: +class Robot {`
> (failure log 67200–67215, quoting shard lines 1420–1435)

Both files were emitted as ` ```diff ` unified-diff hunks (header at shard 1422–1452, cpp at shard 1458–1511; failure log 67202–67327), violating the whole-file mandate (failure log 66813, 66841). Aider applied the diffs anyway (`1515: Applied edit to robot_name.h`, failure log 67295) and issued a reflection prompt with only a █-marked snippet of the header — no compiler text (shard 1518–1543, failure log 67298–67323).

**Turn 2 (failure log 67330–68031, shard 25195–25894): the retry that never landed.** Facing the vague marked-line prompt, the model rummaged through hypotheses about static members and missing includes for ~700 thinking lines, then collapsed into a mechanical repetition loop:

> `25875:             *Wait, the prompt says "Fix any errors below".*`
> `25876:             Maybe the error is that `std::ostringstream` is not a type? It is.`
> `25878:             *I will output the files.*`
> (failure log 68013–68016; identical `Wait … / Maybe the error is that std::mt19937 / std::string is not a type? It is. / I will output the files.` triples repeat through shard 25893, failure log 68028–68031)

The excerpt ends mid-thinking at shard 25894; no edit was applied to `robot_name.*` before the attempt-1 test run. Combined with `"num_exhausted_context_windows": 1` (failure log 85006), the evidence supports (inference) that this turn hit the output-token limit and produced no usable answer — the one real bug (class-name casing) was never touched.

**Attempt-1 test run (failure log 68040–68132, shard 28862–28955): compile failure.**

> `28885: /aider/robot-name/robot_name_test.cpp:29:23: error: ‘robot’ in namespace ‘robot_name’ does not name a type; did you mean ‘Robot’?`
> `28886:    29 |     const robot_name::robot robot;`
> (failure log 68063–68064)

The same `‘robot’ … did you mean ‘Robot’?` error recurs at test lines 37, 44, 45, 52, 62 (shard 28897–28940, failure log 68075–68118), followed by a secondary `-Werror=unused-function` error on the test file's own `validate_name` helper (shard 28945–28948, failure log 68123–68126) — a cascade artifact of the primary errors, not a separate bug. Attempt 1 FAIL (`28953: Tests failed: … robot-name`, failure log 68131).

### Attempt 2 — compiler error text visible → one-line casing fix → PASS (with three noisy reflection turns)

**Turn 1 (failure log 69682–69985, shard 30497–30807).** This time the turn-2 prompt included the compiler output, and the model diagnosed it immediately and correctly:

> `30505:         1.  `/aider/robot-name/robot_name_test.cpp:29:23: error: 'robot' in `
> `30506: namespace 'robot_name' does not name a type; did you mean 'Robot'?` -> The test `
> `30507: code is trying to use `robot_name::robot`, but the header defines `
> `30508: `robot_name::Robot`.`
> (failure log 69683–69686)

It also (correctly) classified the `validate_name` unused-function error as a secondary artifact it could not and need not fix in the test file (shard 30509–30526, failure log 69687–69704), then emitted a rename-only fix — again in ` ```diff ` fences (failure log 69919–69930, shard 30741–30752):

> `30750: -class Robot {`
> `30751: +class robot {`
> (failure log 69928–69929)

plus the matching `Robot::` → `robot::` definition renames in the cpp (shard 30795–30796, failure log 69973–69974). `Applied edit to robot_name.h / .cpp` (shard 30806–30807, failure log 69984–69985). This single casing rename is the entire functional delta between FAIL and PASS.

**Reflection turns 2–4 (noise, not progress).** Aider issued three more `# Fix any errors below, if possible.` marked-line prompts (first at shard 30809, failure log 69987). With the code now actually correct, the model had nothing to fix and behaved accordingly badly: two **empty diff blocks** (`robot_name.h` / ` ```diff ` / ` ``` `, shard 38538–38542 and 40770–40774; failure log 77716–77720 and 79948–79952), then a speculative third turn claiming a missing `#include <iomanip>` for `std::setw`/`std::setfill` and diff-appending it to the header (shard 45625–45651, failure log 84803–84829) with an empty cpp diff (shard 45657–45659, failure log 84835–84837). Aider stopped: `45694: Only 3 reflections allowed, stopping.` (failure log 84872).

**Attempt-2 test run (failure log 84965–84988, shard 45787–45810).** The final file state (captured whole-file at shard 45696–45785, failure log 84874–84963: `class robot` with static `_used_names`, collision-retry `_generateName`) compiles and:

> `45807: ===============================================================================`
> `45808: All tests passed (2004 assertions in 5 test cases)`
> (failure log 84985–84986)

### Hard evidence vs. inference

Hard evidence: `+class Robot {` in attempt 1 (failure log 67215); diff-fence outputs in every attempt-1/attempt-2 turn (67202, 69921, 77718, 79950, 84818); the attempt-1 repetition loop (68013–68031); compile error `‘robot’ … did you mean ‘Robot’?` (68063–68064); the attempt-2 diagnosis quote (69683–69686); the rename diff (69928–69929); two empty-diff reflection turns (77716–77720, 79948–79952); the speculative `<iomanip>` turn (84803–84829); `All tests passed` (84985–84986); result JSON `[false, true]` (84996–84999).

Inference (root-cause categories): (a) the model defaulted to the universal PascalCase class convention (`Robot`) instead of the Exercism-C++ convention (lowercase class matching the namespace, `robot_name::robot`) — it had no way to see the test file, and nothing in the prompt named the class; (b) attempt 1's retry turn exhausted the output window in the repetition loop (`num_exhausted_context_windows: 1`, failure log 85006) — the excerpt ending mid-loop at shard 25894 supports this but the shard log's token-limit line is outside the quoted ranges; (c) the `<iomanip>` "fix" was speculative noise — the marked-line prompt gave no error, and whether the code truly needed the include (transitive includes via `<sstream>` may already provide `std::setw` under libstdc++) is not established by any log line; (d) the model's substantive design (static collision set + RNG) differed from the reference (sequential counter) but satisfied the real contract — divergence from the reference was not the failure.

## 4. Knowledge / Capability Gaps

- **G1 — Format-contract discipline (whole-file listings).** Every turn of both attempts used ` ```diff ` fences despite the twice-stated whole-file mandate (failure log 67202, 69921, 77718, 79950, 84818 vs. 66813/66841). Benign here because Aider applied the diffs, but the same prior produced *empty* diffs in the reflection turns.
- **G2 — Identifier fidelity under convention ambiguity: `robot` vs `Robot`.** The model invented the class name from its own style prior (failure log 67215) when the enforcing tests construct `robot_name::robot` (68063–68064; `.meta/example.h:9`). When the starter declares no class and the prompt says "Don't change the names of existing functions or classes" (66841), the model must infer the expected identifier from task conventions — or, on retry, read the compiler's `did you mean` hint. Attempt 1 never got the compiler text; attempt 2 did and fixed it in one pass (69683–69686, 69928–69929).
- **G3 — Repair/retry behavior on vague marked-line prompts.** On `# Fix any errors below` prompts with only a █-marked snippet, attempt 1 ruminated ~700 lines and died in a `Wait, the prompt says…` loop without emitting anything (68013–68031); attempt 2 emitted two empty diffs (77716–77720, 79948–79952) and one speculative include change (84803–84829). Required behavior: commit to the single most probable defect, restate whole files, stop.
- **G4 — Context/output budgeting under reflection loops.** 16,994 completion tokens (failure log 85013) for a one-line fix; one exhausted context window (85006); the attempt-1 loop and the attempt-2 token counts (`Tokens: 4.2k sent, 4.5k received.` at shard 38545 / failure log 77723, `4.8k sent, 3.8k received` at 84840) show the cost shape.
- **G5 — `<random>`/mutable-static-state idiom quality.** The passing implementation seeds `std::mt19937 _gen` from `_rd` but then draws letters via `letters[dist(_rd)]` — feeding a `uniform_int_distribution` a `random_device` per call (failure log 84938–84941, shard 45760–45763), and relies on class-static RNG state shared by all instances (84900–84903). It passed, but the idiom is wrong-headed (distribution should consume the engine; per-call `random_device` draws are slow and can deplete entropy). Training should teach the canonical `static std::mt19937 gen{std::random_device{}()}` + `dist(gen)` pattern.

## 5. SFT Task Specifications (30 specs)

Answer-blind: no benchmark test fixtures or reference code are copied. Every spec defines a fresh API; stories are new; no two specs share a story wrapper.

### Spec 01: whole-file-vending-token
- Files: `vending_token.cpp`, `vending_token.h` (test file: `vending_token_test.cpp`)
- API: namespace `vending`; `int token_value(const std::string& code);` and `bool is_valid_token(const std::string& code);` — no exceptions.
- Prompt shape: vending-machine token story; starter files contain only the namespace skeleton; system prompt demands whole-file listings.
- Target capability: G1 — two complete file listings, filename line + plain fence, no diff hunks, no prose inside fences.
- Target answer shape: two whole-file listings; guard + declarations in header, definitions in cpp; `<string>` in header.
- Difficulty / variation: foundational; trivial logic, all grading weight on format.

### Spec 02: whole-file-parking-gate
- Files: `parking_gate.cpp`, `parking_gate.h` (test file: `parking_gate_test.cpp`)
- API: namespace `parking`; `class gate_log { public: void record(int spot); int last_spot() const; int entries() const; };` — throws `std::domain_error` from `last_spot()` when empty.
- Prompt shape: parking-gate log story; the whole-file rule is repeated twice in the user message (mirroring the eval prompt's redundancy).
- Target capability: G1 — resist ` ```diff ` fences even though "fix this file" priors are diff-shaped.
- Target answer shape: whole files; no `+`/`-` hunk lines anywhere in the response.
- Difficulty / variation: adds a class and one throw so format isn't the only demand.

### Spec 03: contrastive-diff-vs-whole-file
- Files: `orbit_timer.cpp`, `orbit_timer.h` (test file: `orbit_timer_test.cpp`)
- API: namespace `orbit`; `long long period_seconds(long long radius_km);`
- Prompt shape: satellite-orbit story; dataset row pairs a negative target (answer in ` ```diff ` hunks) with a positive target (whole-file listings) under a prompt demanding whole files.
- Target capability: G1 — format-level contrast: even when a diff would apply cleanly, the contract is whole files.
- Target answer shape: annotated A/B pair; learner target is the whole-file candidate verbatim.
- Difficulty / variation: isolates format compliance from algorithmic content (trivial math).

### Spec 04: lowercase-class-drone-callsign
- Files: `drone_callsign.cpp`, `drone_callsign.h` (test file: `drone_callsign_test.cpp`)
- API: namespace `drone_callsign`; `class drone_callsign { public: drone_callsign(); std::string callsign() const; void regenerate(); private: std::string callsign_; };` — class name equals namespace name, all lowercase.
- Prompt shape: delivery-drone fleet story; starter shows an empty namespace; the hidden tests use `drone_callsign::drone_callsign d;`.
- Target capability: G2 — choose a lowercase class name matching the namespace when the task convention is `ns::ns`, instead of defaulting to PascalCase.
- Target answer shape: lowercase class declared in header, defined out-of-line in cpp.
- Difficulty / variation: direct analog of the failed casing, new domain.

### Spec 05: lowercase-class-buoy-id
- Files: `harbor_buoy.cpp`, `harbor_buoy.h` (test file: `harbor_buoy_test.cpp`)
- API: namespace `harbor_buoy`; `class harbor_buoy { public: harbor_buoy(); std::string id() const; void reset(); };` — ID format: one uppercase letter + four digits.
- Prompt shape: harbor buoy numbering story; prose never spells the class name, forcing convention inference.
- Target capability: G2 — identifier fidelity when the prompt is silent: match the exercise's lowercase `ns::ns` convention.
- Target answer shape: `class harbor_buoy` (not `HarborBuoy`, not `Harbor_Buoy`) with the three-method API.
- Difficulty / variation: same skill as Spec 04 with a different name shape (snake-case multiword), testing resistance to `HarborBuoy` camelization.

### Spec 06: contrastive-pascalcase-vs-convention
- Files: `metro_pass.cpp`, `metro_pass.h` (test file: `metro_pass_test.cpp`)
- API: namespace `metro_pass`; `class metro_pass { public: metro_pass(); std::string serial() const; };`
- Prompt shape: transit-pass story; contrastive row pairing candidate A (`class MetroPass`) labeled wrong (cites the `'metro_pass' … does not name a type; did you mean 'MetroPass'?` style of diagnostic in prose) with candidate B (`class metro_pass`) labeled right.
- Target capability: G2 — contrastive recognition that style-default PascalCase breaks a lowercase calling convention.
- Target answer shape: two annotated candidates; learner target is B.
- Difficulty / variation: pure naming judgment, minimal logic.

### Spec 07: header-impl-greenhouse-sensor
- Files: `greenhouse_sensor.cpp`, `greenhouse_sensor.h` (test file: `greenhouse_sensor_test.cpp`)
- API: namespace `greenhouse`; `class sensor { public: explicit sensor(int channel); double celsius() const; double fahrenheit() const; void calibrate(double offset); private: int channel_; double offset_; };`
- Prompt shape: greenhouse climate story; starter has empty namespace in both files.
- Target capability: G2/G5-adjacent — declaration/definition split: header declares, cpp defines all non-trivial bodies; member-init lists in the constructor.
- Target answer shape: guard + `<string>`-free header, out-of-line `sensor::sensor(...)` etc. in cpp.
- Difficulty / variation: computed accessor (`fahrenheit`) forces deciding stored vs computed state.

### Spec 08: header-impl-wind-turbine-statics
- Files: `turbine_registry.cpp`, `turbine_registry.h` (test file: `turbine_registry_test.cpp`)
- API: namespace `windfarm`; `class turbine { public: turbine(); std::string id() const; void recommission(); private: std::string id_; static std::unordered_set<std::string> issued_ids_; static std::string mint_id(); };`
- Prompt shape: wind-farm commissioning story; uniqueness of IDs across turbines required by prose.
- Target capability: G2/G5 — class-static members: declared `static` in the header, **defined once at namespace scope in the cpp** (`std::unordered_set<std::string> turbine::issued_ids_;`), never defined in the header (pre-C++17 style).
- Target answer shape: header with static declarations only; cpp with out-of-class static definitions plus methods.
- Difficulty / variation: the exact static-member structure the model used, taught with correct placement discipline.

### Spec 09: random-idiom-arcade-token
- Files: `arcade_token.cpp`, `arcade_token.h` (test file: `arcade_token_test.cpp`)
- API: namespace `arcade`; `std::string mint_token();` — returns two uppercase letters + two digits, randomly drawn.
- Prompt shape: arcade prize-token story.
- Target capability: G5 — canonical `<random>` usage: one `static std::mt19937` seeded once from `std::random_device`, `std::uniform_int_distribution` objects **consuming the engine** (`dist(gen)`), never `dist(random_device)` per draw.
- Target answer shape: function-local or namespace-scope static engine; distributions constructed per call or static; no `random_device` in the draw loop.
- Difficulty / variation: free function; isolates the RNG idiom.

### Spec 10: random-uniqueness-race-bib
- Files: `race_bib.cpp`, `race_bib.h` (test file: `race_bib_test.cpp`)
- API: namespace `marathon`; `class bib { public: bib(); std::string number() const; void reassign(); private: std::string number_; static std::unordered_set<std::string> taken_; };` — format: letter + 3 digits; collision retry until unique.
- Prompt shape: marathon bib-assignment story; prose requires that 500 reassignments never repeat a number.
- Target capability: G5 — combine seeded-engine RNG with a static used-set and a retry-until-unique loop; ensure `reassign` leaves the old number in the set.
- Target answer shape: `while (true)` candidate loop with `find == end` check and insert; static set defined in cpp.
- Difficulty / variation: the model's passing design, re-taught with correct RNG plumbing.

### Spec 11: random-device-once-firework-show
- Files: `firework_show.cpp`, `firework_show.h` (test file: `firework_show_test.cpp`)
- API: namespace `pyro`; `class show { public: show(); std::string cue_code() const; void next_cue(); private: std::string cue_; };`
- Prompt shape: choreographed firework story; cue codes are 3 letters + 1 digit.
- Target capability: G5 — `std::random_device` used exactly once (as seed source); explain in one comment-free line of code that engines are cheap to reuse and devices are not.
- Target answer shape: `static std::mt19937 engine{std::random_device{}()};` inside the cpp; all draws via distributions on `engine`.
- Difficulty / variation: directly counters the observed `dist(_rd)` antipattern (failure log 84940).

### Spec 12: exception-exhaustion-seed-vault
- Files: `seed_vault.cpp`, `seed_vault.h` (test file: `seed_vault_test.cpp`)
- API: namespace `vault`; `class drawer { public: drawer(); std::string label() const; void advance(); };` — labels are sequential `A001…Z999`-style; when all labels are consumed, `advance()` throws `std::range_error` with any message.
- Prompt shape: seed-vault drawer labeling story; prose states the exhaustion rule and names `std::range_error`.
- Target capability: G5 + exception policy — sequential minting with rollover counters and a named exception type thrown exactly at exhaustion.
- Target answer shape: rollover branch then throw site; `<stdexcept>` in cpp.
- Difficulty / variation: teaches the reference's exhaustion policy shape without its code.

### Spec 13: exception-exhaustion-grid-relay
- Files: `grid_relay.cpp`, `grid_relay.h` (test file: `grid_relay_test.cpp`)
- API: namespace `powergrid`; `class relay { public: relay(); std::string code() const; void recommission(); };` — codes `R-00…R-99` then letter rollover; exhaustion throws `std::range_error`; a documented `bool retire()` returns false if already retired (no throw) to contrast error-channel choices.
- Prompt shape: power-grid relay story; prose distinguishes "exceptional" (exhaustion) from "expected" (double-retire) outcomes.
- Target capability: exception policy — choose throw vs return-code per the documented contract; throw the exact named type.
- Target answer shape: one throw site, one bool path, no catch blocks.
- Difficulty / variation: sibling of Spec 12 with a mixed error-channel design.

### Spec 14: edge-reset-loop-kayak-registry
- Files: `kayak_registry.cpp`, `kayak_registry.h` (test file: `kayak_registry_test.cpp`)
- API: namespace `regatta`; `class kayak { public: kayak(); std::string tag() const; void reassign(); };` — tag: 2 letters + 3 digits; 1000 consecutive `reassign()` calls must each produce a fresh valid tag.
- Prompt shape: kayak race-registry story; the 1000-reassignment requirement is stated only as "must survive a full season of daily re-tagging".
- Target capability: G3/G5 — design for the exhaustion edge: either collision-retry RNG over a 676,000-name space or prefix rollover; a fixed-prefix 000–999 counter must fail by design and is the negative example.
- Target answer shape: generator whose space exceeds 1000 draws with uniqueness tracking.
- Difficulty / variation: direct analog of the benchmark's heaviest test (`exhausting_digits…`), new story.

### Spec 15: edge-name-stability-telescope
- Files: `telescope_mount.cpp`, `telescope_mount.h` (test file: `telescope_mount_test.cpp`)
- API: namespace `observatory`; `class mount { public: mount(); std::string serial() const; void recalibrate(); };` — `serial()` called twice without `recalibrate()` must return identical values.
- Prompt shape: telescope-mount asset story.
- Target capability: G5 — lazy-vs-eager generation semantics: generate once at construction, store, and return the stored value; never regenerate inside the accessor.
- Target answer shape: accessor returns member; generation only in ctor and `recalibrate`.
- Difficulty / variation: targets the `name_is_the_same_each_time` class of bug (accessor with side effects).

### Spec 16: edge-rollover-courier-sequencer
- Files: `courier_sequencer.cpp`, `courier_sequencer.h` (test file: `courier_sequencer_test.cpp`)
- API: namespace `courier`; `std::string next_manifest_code();` — sequential `AA000`–`AA999`, then `AB000`; after `ZZ999` throws `std::range_error`.
- Prompt shape: courier manifest numbering story.
- Target capability: G5 — multi-digit rollover arithmetic (units → letter rollover) and state carried across calls via function-local statics.
- Target answer shape: static prefix pair + counter; explicit rollover branch; throw at the end of space.
- Difficulty / variation: the reference's own strategy, abstracted to a free function and new domain.

### Spec 17: edge-multi-instance-trail-camera
- Files: `trail_camera.cpp`, `trail_camera.h` (test file: `trail_camera_test.cpp`)
- API: namespace `wildlife`; `class camera { public: camera(); std::string id() const; void reset(); };` — two live `camera` objects must hold different IDs at all times.
- Prompt shape: wildlife trail-camera deployment story.
- Target capability: G5 — uniqueness is a *global* invariant: per-instance counters fail; class-static state (or a shared registry) is required; the ID set must include IDs of live objects.
- Target answer shape: static registry shared across instances; ctor and `reset` both go through the unique-mint path.
- Difficulty / variation: targets the `different_robots_have_different_names` class of test.

### Spec 18: repair-vague-marker-rename
- Files: `ski_lift.cpp`, `ski_lift.h` (test file: `ski_lift_test.cpp`)
- API: namespace `ski_lift`; `class ski_lift { public: ski_lift(); std::string code() const; void reset(); };`
- Prompt shape: two-turn. Turn 1: implement from scratch (the dataset's scripted first answer uses `class SkiLift` — deliberately wrong casing). Turn 2: `# Fix any errors below, if possible.` with header lines █-marked, no compiler text.
- Target capability: G3+G2 — on a vague marked-line prompt, hypothesize the highest-probability contract mismatch (identifier casing/naming) and emit corrected whole files, not an empty diff and not a rumination loop.
- Target answer shape: whole files with the class renamed to the convention; ≤3-sentence rationale.
- Difficulty / variation: teaches "marked lines on the class declaration → suspect the identifier itself".

### Spec 19: repair-from-did-you-mean-diagnostic
- Files: `ferry_ticket.cpp`, `ferry_ticket.h` (test file: `ferry_ticket_test.cpp`)
- API: namespace `ferry_ticket`; `class ferry_ticket { public: ferry_ticket(); std::string code() const; };`
- Prompt shape: two-turn. Turn 1 answer declares `class FerryTicket`. Turn 2 shows the compiler error: `error: 'ferry_ticket' in namespace 'ferry_ticket' does not name a type; did you mean 'FerryTicket'?` plus a `-Werror=unused-function` cascade in the test file.
- Target capability: G2+G3 — read `did you mean` as a direct rename instruction; classify the unused-function warning as a downstream artifact needing no fix; change only the identifier everywhere (declaration + out-of-line definitions).
- Target answer shape: whole files, casing fixed in both, everything else untouched.
- Difficulty / variation: the exact diagnostic-to-fix mapping attempt 2 performed — taught as a first-class skill.

### Spec 20: repair-never-empty-diff
- Files: `tram_passenger.cpp`, `tram_passenger.h` (test file: `tram_passenger_test.cpp`)
- API: namespace `tram`; `int passenger_count(int boardings, int alightings);` — throws `std::domain_error` if the result would be negative.
- Prompt shape: two-turn. Turn 1 answer is correct except one wrong constant. Turn 2: marked-line prompt on the constant.
- Target capability: G3 — a repair turn must always produce a substantive whole-file listing; an empty ` ```diff ` block is never acceptable when the harness reports an error.
- Target answer shape: whole cpp re-emitted with the constant fixed.
- Difficulty / variation: smallest possible repair; graded on non-empty, format-correct output.

### Spec 21: contrastive-random-device-per-draw
- Files: `lottery_ball.cpp`, `lottery_ball.h` (test file: `lottery_ball_test.cpp`)
- API: namespace `lottery`; `int draw_ball();` — uniform in 1–49.
- Prompt shape: contrastive row: candidate A constructs `std::random_device` and feeds it to a distribution on every call; candidate B seeds a static `std::mt19937` once and reuses it. Both compile; only B is acceptable.
- Target capability: G5 — contrastive recognition of the `dist(_rd)` antipattern observed in the passing solution (failure log 84940).
- Target answer shape: annotated A/B pair with a one-line rationale (entropy cost, distribution quality); learner target is B.
- Difficulty / variation: pure RNG-idiom judgment.

### Spec 22: budget-commit-to-output
- Files: `harbor_permit.cpp`, `harbor_permit.h` (test file: `harbor_permit_test.cpp`)
- API: namespace `harbor`; `class permit { public: permit(); std::string id() const; void renew(); };`
- Prompt shape: long multi-turn chat history (8+ prior exchanges) then a final vague "fix any errors" turn; token budget implicitly tight.
- Target capability: G4 — commit to the best-guess fix and emit whole files immediately; deliberation ≤3 sentences.
- Target answer shape: brief rationale + two complete listings.
- Difficulty / variation: graded on answer shape and brevity, not just correctness.

### Spec 23: budget-break-noop-streak
- Files: `stage_light.cpp`, `stage_light.h` (test file: `stage_light_test.cpp`)
- API: namespace `stage`; `class dimmer { public: dimmer(); int level() const; void bump(int delta); };`
- Prompt shape: third consecutive `# Fix any errors below` turn (harness "Only 3 reflections" situation); the scripted history has two prior no-op turns.
- Target capability: G4+G3 — break a no-op streak: last-chance repair must change something concrete, restate both files in full, and never repeat a sentence.
- Target answer shape: whole files with one visible fix; no repetition, no empty fences.
- Difficulty / variation: directly counters the attempt-1 death spiral and attempt-2 empty diffs.

### Spec 24: include-placement-planetarium
- Files: `planetarium_show.cpp`, `planetarium_show.h` (test file: `planetarium_show_test.cpp`)
- API: namespace `planetarium`; `std::string format_show_code(int series, int episode);` — zero-padded `SxxExxx`-style formatting.
- Prompt shape: planetarium show-scheduling story; starter cpp uses `std::setw`/`std::setfill` but omits `<iomanip>`.
- Target capability: G5/G3 — include hygiene: recognize which header provides each manipulator (`<iomanip>` for `std::setw`/`std::setfill`, `<sstream>` for `std::ostringstream`) and add the genuinely missing one — rather than speculatively editing includes on a vague prompt.
- Target answer shape: whole cpp with `<iomanip>` added; no other churn.
- Difficulty / variation: converts the model's speculative third reflection into a grounded, test-verified skill.

### Spec 25: static-registry-toll-plaza
- Files: `toll_plaza.cpp`, `toll_plaza.h` (test file: `toll_plaza_test.cpp`)
- API: namespace `tollway`; `class transponder { public: transponder(); std::string id() const; void replace(); private: std::string id_; static std::unordered_set<std::string> active_ids_; };`
- Prompt shape: toll-transponder issuance story; prose requires all live transponders distinct.
- Target capability: G5 — static-set lifetime semantics: decide whether `replace()` releases the old ID (and defend the choice against the uniqueness invariant); static definition in cpp.
- Target answer shape: one documented policy implemented consistently in ctor and `replace`.
- Difficulty / variation: state-semantics judgment beyond mechanical uniqueness.

### Spec 26: accessor-constness-chess-clock
- Files: `chess_clock.cpp`, `chess_clock.h` (test file: `chess_clock_test.cpp`)
- API: namespace `chess`; `class clock { public: clock(int minutes); std::string display() const; int remaining_seconds() const; void tick(int seconds); };`
- Prompt shape: chess-clock story.
- Target capability: G2-adjacent signature fidelity — accessors `const`, returning `std::string` by value; mutators non-const; exact qualifier match between declaration and definition.
- Target answer shape: qualifier-identical header/cpp pairs.
- Difficulty / variation: signature-fidelity drill in a non-RNG domain.

### Spec 27: naming-from-instructions-mail-sorter
- Files: `mail_sorter.cpp`, `mail_sorter.h` (test file: `mail_sorter_test.cpp`)
- API: namespace `mail_sorter`; `class mail_sorter { public: mail_sorter(); std::string bin_code() const; void reassign_bin(); };`
- Prompt shape: mail-sorting story; prompt says "Don't change the names of existing functions or classes" while the starter declares **no** class — the model must create one named after the module, lowercase.
- Target capability: G2 — interpret "don't rename" as "match the established module naming convention", producing `mail_sorter::mail_sorter`, not a novel name.
- Target answer shape: class name identical to namespace; three methods only.
- Difficulty / variation: teaches reading the instruction as a convention constraint, the exact ambiguity that produced `Robot`.

### Spec 28: format-no-elision-cargo-crane
- Files: `cargo_crane.cpp`, `cargo_crane.h` (test file: `cargo_crane_test.cpp`)
- API: namespace `port`; `class crane { public: crane(int max_load_kg); bool lift(int kg); int load() const; void release(); };`
- Prompt shape: cargo-crane story with a ~70-line cpp to tempt elision.
- Target capability: G1 — never use `...` or `// rest unchanged` inside a listing, even for long files.
- Target answer shape: full listing, every line present, plain fences.
- Difficulty / variation: length pressure on format discipline.

### Spec 29: repair-trust-current-files-weather-balloon
- Files: `weather_balloon.cpp`, `weather_balloon.h` (test file: `weather_balloon_test.cpp`)
- API: namespace `atmos`; `class balloon { public: balloon(); std::string flight_id() const; void relaunch(); };`
- Prompt shape: two-turn. Turn 2's error snippet quotes a **stale** header (wrong class name that turn 1 already fixed), while "Trust this message as the true contents of these files!" carries the correct current files.
- Target capability: G3+G4 — when the error log contradicts trusted current files, trust the files, restate them whole, and do not chase phantom errors into a rumination or repetition loop.
- Target answer shape: calm note + whole files identical in API to turn 1's corrected state.
- Difficulty / variation: the trap behind both attempts' wasted reflection turns.

### Spec 30: exception-type-precision-aquarium-tag
- Files: `aquarium_tag.cpp`, `aquarium_tag.h` (test file: `aquarium_tag_test.cpp`)
- API: namespace `aquarium`; `class tag { public: explicit tag(const std::string& raw); std::string code() const; };` — throws `std::invalid_argument` for malformed input (wrong charset/length), `std::range_error` only when the sequential tag space is exhausted.
- Prompt shape: aquarium specimen-tagging story; prose assigns one exception type per failure class and never dictates messages.
- Target capability: exception policy — `std::invalid_argument` vs `std::range_error` discrimination; tests match type only, so no message-dependent behavior and no catch-and-rethrow.
- Target answer shape: two throw sites with distinct types; `<stdexcept>` included where thrown.
- Difficulty / variation: exception-type precision in a constructor-validation setting, complementing Specs 12–13.

Gap coverage: G1 → Specs 01, 02, 03, 28. G2 → Specs 04, 05, 06, 18, 19, 26, 27. G3 → Specs 18, 19, 20, 23, 24, 29. G4 → Specs 22, 23, 29. G5 → Specs 08, 09, 10, 11, 14, 15, 16, 17, 21, 25. Required mix: format-contract ≥2 (01, 02, 03, 28); header/impl separation ≥2 (07, 08, 24); exception policy ≥2 (12, 13, 30 — the contract's only exception is the reference's exhaustion `std::range_error`, untested by the visible tests, so these teach the policy shape plus adjacent type precision); edge cases ≥3 (14, 15, 16, 17); repair/retry ≥2 (18, 19, 20, 23, 29); contrastive ≥1 (03, 06, 21). No two specs share a story wrapper.

## 6. Acceptance & Validation Gates

For every row built from the specs above, before inclusion in SFT:

1. **Parser validity:** the target response must parse under the Aider whole-file listing format — bare filename line, opening plain fence, entire file, closing fence; zero diff hunks, zero elisions (grep for `^```diff`, `+ `/`- ` hunk lines, `...` placeholders, `rest of`, `unchanged`).
2. **Compile + test receipt:** apply the target files to a scratch copy of the spec's exercise, build with the project's CMake/Catch2 harness with `-Werror` on, and require 100% test pass; store the build log hash as the receipt.
3. **Identifier-fidelity check (specs 04–06, 18, 19, 27):** the test file must exercise the exact `ns::ns` lowercase construction, and a CI grep must confirm the target header declares the class with the exact required spelling/casing — this is the regression the run actually suffered.
4. **Hidden-edge coverage:** RNG/uniqueness specs (09–11, 14, 17) must include a many-iteration uniqueness loop (≥1000 draws/resets) and at least one case the prose does not show as an example; rollover specs (12, 13, 16) must test the exact boundary value and the value one past it.
5. **Exception-policy check (specs 12, 13, 30):** tests must assert the exact exception **type** (`REQUIRE_THROWS_AS`) at exhaustion and at invalid input, and must not match on message text.
6. **Repair-turn realism (specs 18–20, 23, 29):** the scripted first answer must be a plausible, compilable wrong answer (PascalCase class; one wrong constant), and the second-turn prompt must mirror the real harness style (`# Fix any errors below, if possible.` + █-marked snippet, with and without compiler text).
7. **Whole-file rule on repair targets:** second-turn targets must re-emit **all** editable files in full, not only the file named in the error snippet — the empty-diff turns (failure log 77716–77720, 79948–79952) are the negative pattern.
8. **No-loop guard:** target responses must be under a length cap (≤2× the byte size of the emitted files) and must not contain any sentence repeated ≥3 times — directly counters the `Wait, the prompt says…` repetition loop (failure log 68013–68031).
9. **Contamination check:** diff every spec's story, test inputs, and expected outputs against `polyglot-benchmark/cpp/exercises/practice/robot-name/`; no robot/factory story elements, no `RX837`/`BC811`-style literals, no copied reference code (in particular not the `next_prefix` helper). APIs must differ in names even when capabilities overlap.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log and the ground-truth files:

- **Outcome array / shard:** re-read failure log lines 66799–66804: `### robot-name`, shard `1`, outcomes `[False, True]`, result `PASS` — matches section 1 and the run summary. Result JSON re-verified at failure log 84996–84999 (`"tests_outcomes": [false, true]`), 85006 (`"num_exhausted_context_windows": 1`), 85013 (`"completion_tokens": 16994`), and the passing summary at 84985–84986 (`All tests passed (2004 assertions in 5 test cases)`).
- **Log citations re-read:** every quoted line was re-fetched with `sed` and confirmed verbatim: 67200–67215 (`robot_name.h` / ` ```diff ` / `+class Robot {`), 67295 (`Applied edit`), 67298–67323 (reflection prompt + █-marked snippet), 68013–68016 and 68028–68031 (repetition loop), 68063–68064 (`'robot' … did you mean 'Robot'?`), 68075–68118 (recurrences at test lines 37–62), 68123–68126 (`-Werror=unused-function` on `validate_name`), 68131 (`Tests failed`), 69683–69686 (attempt-2 diagnosis), 69928–69929 (`-class Robot {` / `+class robot {`), 69973–69974 (`robot::_generateName` rename), 69984–69987 (applied edits + next reflection), 77716–77723 and 79948–79956 (empty-diff reflection turns), 84803–84829 (speculative `<iomanip>` diff), 84835–84837 (empty cpp diff), 84872 (`Only 3 reflections allowed, stopping.`), 84874–84963 (final whole-file state). No quote or line number required correction.
- **Foreign-content attribution verified:** the terminal excerpt (failure log 68040–85041 = shard 28862–45863) spans other tasks; confirmed that shard 28961–28962 (zebra-puzzle `solveRecursive`), 29993, 30466–30468 (sublist), 35213/35325 (parallel-letter-frequency token limit / test failure), 39280, 39851, 41645 are not robot-name lines and are excluded from the failure anatomy. Robot-name's own token-limit line is not inside the quoted shard ranges; section 3 labels the attempt-1 token-exhaustion death as inference supported by `"num_exhausted_context_windows": 1` plus the mid-loop excerpt cutoff at shard 25894.
- **API claims re-checked:** `.meta/example.h:9,12,14,16,18-19` (lowercase `class robot` in `namespace robot_name`; ctor; `std::string const &name() const` header-inline; `reset()`; `name_`) and `.meta/example.cpp:14-28,20,30-43,35-36` (`next_prefix` helper, `throw range_error("prefix combinations exhausted")` at :20, sequential minting in `generate_name`, rollover branch) re-read and match section 2. Test-file citations (`robot_name_test.cpp:18-24,29,31,35-40,42-48,50-58,60-72`) re-read and match; confirmed the tests assert format/stability/uniqueness/reset only — no randomness, exception, or return-type-category assertions, so the model's by-value `std::string name() const` legitimately passes, as section 2 states.
- **Corrections made during cross-check:** one real correction — the initial draft cited `.meta/example.h:11/13/15/17` and `.meta/example.cpp:30/33-46`; re-reading with `cat -n`/`grep -n` showed the correct lines are `example.h:12` (ctor), `:14` (`name()`), `:16` (`reset()`), `:18-19` (`name_`), and `example.cpp:14-28` (`next_prefix`), `:20` (the `throw range_error` site), `:30-43`/`35-36` (`generate_name` and its rollover branch). Sections 2 and 7 were fixed accordingly. No failure-log quote or line number required correction. Two framing decisions recorded: (a) the `Robot`→`robot` casing mismatch is presented as the sole functional failure, with the diff-format violation called out as contract-noncompliant-but-benign because Aider applied the diffs; (b) the reference's sequential strategy vs the model's RNG strategy is explicitly documented as an acceptable divergence (tests enforce uniqueness, not randomness), to keep future specs from over-fitting to the reference implementation.
- **Ground-truth status:** `.meta/example.h`, `.meta/example.cpp`, and `robot_name_test.cpp` all present and mutually consistent; no ground-truth problem encountered.
