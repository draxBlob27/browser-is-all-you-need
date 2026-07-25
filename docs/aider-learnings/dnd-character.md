# Aider Learning: dnd-character

## 1. Task Identity & Evidence Pointers

- Task slug: `dnd-character`
- Shard: `0` (failure log line 13157: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 13159: "- Test outcomes: `[False, False]`"; terminal results JSON `"tests_outcomes": [false, false]` at failure log lines 14337-14339, log source lines 4314-4316)
- Result: `FAIL` (failure log line 13160)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md`, lines **13155-14368**
  - Attempt 1 excerpts: "Attempt/log chunk 1, source lines 2011-2586" (failure log line 13205)
  - Attempt 2 (retry) excerpts: "Attempt/log chunk 2, source lines 3490-3761" (failure log line 13786)
  - Terminal test log: "Source lines 4045-4343" (failure log line 14063; note source lines ~4045-4189 are interleaved output from a concurrently-running `bank-account` task in shard 0's shared benchmark.log — only source lines 4190-4342 belong to dnd-character)
- Raw shard log cross-check: `...-shard-0/benchmark.log` lines 2576, 4220, 4266 confirm the quoted compile error and test-failure lines verbatim.
- Ground truth (read-only): `polyglot-benchmark/cpp/exercises/practice/dnd-character/`
  - Reference: `.meta/example.h`, `.meta/example.cpp`
  - Tests: `dnd_character_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` has no dnd-character entry).

## 2. Benchmark Contract (Ground Truth)

File set: `dnd_character.h` + `dnd_character.cpp`, namespace `dnd_character`.

Public API (`.meta/example.h`):

- `int modifier(int score);` — `.meta/example.h:4`
- `int ability();` — `.meta/example.h:5`
- `struct Character` with seven public `int` fields (`strength, dexterity, constitution, intelligence, wisdom, charisma, hitpoints`) **and a default constructor that populates all of them** — `.meta/example.h:7-24`; constructor body at `.meta/example.h:8-16` rolls each ability via `ability()` and sets `hitpoints = 10 + modifier(constitution)` (`.meta/example.h:15`).

Semantics (`.meta/example.cpp`):

- `modifier` is **floor** division: `std::floor((static_cast<double>(score) - 10) / 2)` — `.meta/example.cpp:9-11`. Truncating integer division is wrong for odd scores below 10.
- `ability()` rolls 4d6 and drops the lowest: `.meta/example.cpp:15-20` (sum of four rolls minus the minimum), range [3, 18].

Enforced by tests (`dnd_character_test.cpp`):

- `modifier(3) == -4`, `modifier(5) == -3`, `modifier(7) == -2`, `modifier(9) == -1` — test lines 30-58. These are exactly the cases where truncation-toward-zero differs from floor.
- Full modifier table 3..18 — test lines 30-94.
- `dnd_character::ability()` must exist as a free function returning a value in [3, 18] — test lines 96-99 (`int result{dnd_character::ability()};` at line 97).
- `dnd_character::Character character;` — **default construction** must yield all six abilities in [3, 18] and `hitpoints == 10 + modifier(constitution)` — test lines 101-110. There is no factory function in the contract; the struct must self-initialize.

Exception policy: none. No throwing API in this contract.

Output-format constraints: Aider whole-file listing; both files emitted in full; standard library only.

## 3. Failure Anatomy

### Attempt 1 (log source lines 2011-2586) — compile error + two latent bugs

Hard evidence:

- The model invented its own API instead of the contract's. Its header declares a field-only struct plus a free factory function (failure log lines 13595-13605, source lines 2398-2408):
  - `+    struct Character {` (source 2398) with bare `int` fields and **no constructor**
  - `+    Character generate_character();` (source 2408)
  - It never declares `int ability();`.
- The test file requires `dnd_character::ability()` (test line 97), so the build fails: "error: 'ability' is not a member of 'dnd_character'" (failure log line 13773, source line 2576; source line 2577 shows `int result{dnd_character::ability()};`).
- Latent bug 1 (masked by the compile error): `modifier` implemented as `return (score - 10) / 2;` (failure log line 13643, source line 2446) — truncation toward zero, not floor.
- Latent bug 2 (masked): `struct Character` has no constructor, so default-constructing it (as the test does at test line 102) leaves all seven fields indeterminate.

Inference (root cause): the model designed the API from the prose instructions alone ("Write a random character generator") and guessed a `generate_character()` factory shape, without anticipating that hidden tests would (a) call a free `ability()` and (b) default-construct `Character`. It also read "divide by 2 and round down" in the prompt but implemented C++ integer division, which rounds toward zero for negative operands.

### Attempt 2 / retry (log source lines 3490-3761) — compile error fixed, semantics untouched

Hard evidence:

- Retry diagnosis was narrowly scoped to the surfaced compile error: "Therefore, I need to add `int ability();` to the header file and implement it in the source file." (failure log line 13813, source line 3514).
- The retry diff adds only `+    int ability();` (failure log line 13946, source line 3647) and `+    int ability() { return roll_4d6_drop_lowest(); }` (failure log lines 13963-13966, source lines 3663-3666).
- The retry's whole-file output keeps the truncating modifier unchanged: `return (score - 10) / 2;` (failure log line 14031, source line 3732) and keeps the constructor-less struct (source lines 3688-3696).

### Terminal test run (log source lines 4190-4342) — attempt 2 fails 5 of 18 test cases

Hard evidence:

- Build now succeeds (source lines 4203-4207).
- Modifier floor bug: `REQUIRE( -4 == dnd_character::modifier(3) )` … `-4 == -3` (failure log lines 14242-14245, source lines 4219-4222); same pattern for scores 5, 7, 9 (source lines 4230-4255).
- Uninitialized struct: `CHECK_THAT( character.strength, IsBetweenMatcher(3, 18) )` … `1478975544 (0x58276038) should be between 3 and 18` (failure log lines 14286-14289, source lines 4263-4266); all six abilities show garbage; `character.hitpoints == ...` shows `1479503168 (0x582f6d40) == 56` (failure log lines 14316-14319, source lines 4293-4296). Indeterminate values prove the fields were never initialized.
- Summary: `test cases: 18 | 13 passed | 5 failed` / `assertions: 24 | 13 passed | 11 failed` (failure log lines 14321-14323, source lines 4298-4300).

Inference (root cause of retry failure): the repair was error-driven, not contract-driven. The model fixed exactly the one symbol the compiler named and never re-audited the file against the instruction text ("round down") or against plausible hidden-test usage (default construction). Both remaining bugs were directly deducible from the prompt and from the first attempt's own design choices.

## 4. Knowledge / Capability Gaps

- **G1 — API-shape inference for hidden tests.** The model invented `generate_character()` and a passive struct instead of the contract's `ability()` free function plus a self-initializing `Character`. Evidence: source lines 2398-2408 (attempt-1 header), compile error source 2576, terminal garbage-field failures source 4263-4296.
- **G2 — Rounding semantics: floor vs truncation for negative operands.** "Subtract 10, divide by 2, round down" was implemented as `(score - 10) / 2`, which truncates toward zero and is wrong for odd scores < 10. Evidence: source line 2446; kept at source 3732; failures source 4219-4255. Not fixed even on retry.
- **G3 — Initialization discipline for aggregate structs.** A struct with bare `int` members and no constructor holds indeterminate values; the model shipped it as the public character type. Evidence: source 2398-2406 (no ctor); garbage expansions source 4263-4296 (`1478975544 ... should be between 3 and 18`).
- **G4 — Retry-repair breadth.** On the "Fix any errors" turn the model repaired only the surfaced compile error and re-emitted both latent semantic bugs unchanged. Evidence: retry scope statement source 3514; unchanged modifier source 3732; constructor-less struct source 3688-3696; terminal failures source 4219-4300.

(No exception-policy gap: this contract has no throwing API.)

## 5. SFT Task Specifications (30 specs)

Answer-blind: no spec reuses the D&D story, the benchmark tests, or the reference code. Domains are all distinct.

### Spec 01: weather-station-readout-files
- Files: `weather_station.cpp`, `weather_station.h` (test file: `weather_station_test.cpp`)
- API: namespace `weather`; `double celsius_to_fahrenheit(double c);` `struct Reading { double temp_c; double humidity; };`
- Prompt shape: weather-station story; starter files are empty namespace skeletons in both .h and .cpp.
- Target capability: format contract — emit exactly the two named files as complete whole-file listings, no elision, no extra files (supports G1 contract fidelity).
- Target answer shape: two whole-file listings, header with declarations + struct, impl with definitions, minimal includes.
- Difficulty / variation: baseline format row; no edge cases.

### Spec 02: pantry-inventory-retry-format
- Files: `pantry.cpp`, `pantry.h` (test file: `pantry_test.cpp`)
- API: namespace `pantry`; `int total_items();` `void add_item(const std::string& name, int count);`
- Prompt shape: kitchen-inventory story; two-turn prompt — turn 2 is "Fix any errors below" with a compiler excerpt; the fix must still be a whole-file listing of both files.
- Target capability: format contract under retry — never switch to diff fragments or prose-only answers on the repair turn (supports G4).
- Target answer shape: full re-listing of both files with the small fix applied.
- Difficulty / variation: retry turn includes a misleading hint that only one file needs changes; both must be re-emitted.

### Spec 03: vault-door-access-codes
- Files: `vault.cpp`, `vault.h` (test file: `vault_test.cpp`)
- API: namespace `vault;` → namespace `vault`; `int combine_codes(int a, int b);` `struct Door { Door(); int code_a; int code_b; bool sealed; };` — constructor declared in header, defined in .cpp.
- Prompt shape: bank-vault story; starter skeleton files.
- Target capability: header/impl separation — declarations in .h, definitions in .cpp, no stray definitions in the header (Gap G1).
- Target answer shape: header with guard/`#pragma once`, declarations only; impl file defines everything in the namespace.
- Difficulty / variation: constructor out-of-line, forcing the model to write `Door::Door()` in the .cpp.

### Spec 04: playlist-runtime-summary
- Files: `playlist.cpp`, `playlist.h` (test file: `playlist_test.cpp`)
- API: namespace `tunes`; `int total_seconds(const std::vector<int>& tracks);` `struct Summary { Summary(); int tracks; int seconds; };` with an inline default constructor in the header that zero-initializes members.
- Prompt shape: music-playlist story; starter skeleton files.
- Target capability: header/impl separation + member initialization — an inline header constructor must still initialize every member (Gaps G1, G3).
- Target answer shape: header with inline ctor using member initializers; impl only for the free function.
- Difficulty / variation: ctor is inline (contrast with Spec 03's out-of-line ctor).

### Spec 05: cargo-hold-load-allowance
- Files: `cargo.cpp`, `cargo.h` (test file: `cargo_test.cpp`)
- API: namespace `cargo`; `int load_bonus(int manifest_weight);` defined as floor((manifest_weight - 20) / 5) for any int, including weights below 20.
- Prompt shape: spaceship cargo story; starter skeleton files.
- Target capability: Gap G2 — floor division for negative numerators; implement via `std::floor` on a double or a corrective integer formula, never bare `/`.
- Target answer shape: two-file listing; impl includes `<cmath>`; a comment noting floor semantics for negatives.
- Difficulty / variation: negative results are the common case, not the edge case.

### Spec 06: alpine-temperature-comfort
- Files: `comfort.cpp`, `comfort.h` (test file: `comfort_test.cpp`)
- API: namespace `alpine`; `int comfort_index(int tenths_above_freezing);` = floor((x - 100) / 20); must handle x from -500 to 500.
- Prompt shape: mountain-hut weather story; starter skeleton files.
- Target capability: Gap G2 — correct floor for odd/even negative offsets across a wide domain.
- Target answer shape: two-file listing; `<cmath>` floor or integer `(x - 100 - (x<100?19:0)) / 20`-style correction.
- Difficulty / variation: wide negative domain; tests boundary x = 100 (result 0).

### Spec 07: chess-rating-halfpenalty
- Files: `rating.cpp`, `rating.h` (test file: `rating_test.cpp`)
- API: namespace `chessclub`; `int rating_delta(int points_over_par);` = floor(points_over_par / 2) for negative and positive values.
- Prompt shape: chess-tournament story; starter skeleton files.
- Target capability: Gap G2 — "halve and round down" applied symmetrically; model must not rely on C++ `/` truncation.
- Target answer shape: two-file listing with explicit floor logic and a test-comment table for -3, -2, -1, 0, 1.
- Difficulty / variation: smallest-magnitude negatives (-3 → -2, -1 → -1) catch the truncation bug immediately.

### Spec 08: truncation-vs-floor-contrast
- Files: `offset.cpp`, `offset.h` (test file: `offset_test.cpp`)
- API: namespace `offsetutil`; `int half_down(int n);` = floor(n / 2) for all int n.
- Prompt shape: contrastive row — prompt shows a buggy existing implementation `return n / 2;` in the starter .cpp and a failing-test excerpt for n = -3; the model must explain and fix.
- Target capability: Gap G2 (contrastive) — recognize truncation-toward-zero as the bug; produce the floor version.
- Target answer shape: whole-file listings where only the arithmetic changes; short note on why `n / 2` differs from floor for negatives.
- Difficulty / variation: negative/contrastive spec; starter is wrong, not empty.

### Spec 09: library-late-fee-tiers
- Files: `fees.cpp`, `fees.h` (test file: `fees_test.cpp`)
- API: namespace `library`; `int fee_credit(int days_early);` = floor((days_early - 3) / 2) with exact boundary behavior at odd negative values.
- Prompt shape: library returns desk story; starter skeleton files.
- Target capability: Gap G2 — edge-case reasoning over a full small table (every input -9..9 must match floor semantics).
- Target answer shape: two-file listing; implementation plus an in-comment lookup table the model derives itself.
- Difficulty / variation: exhaustive small-domain table forces exactness, like the modifier table 3..18.

### Spec 10: potion-potency-boundaries
- Files: `potions.cpp`, `potions.h` (test file: `potions_test.cpp`)
- API: namespace `apothecary`; `int potency_tier(int drops);` = floor((drops - 10) / 2); tests pin drops = 3 and drops = 18 endpoints.
- Prompt shape: potion-brewing story (generic fantasy, NOT D&D character generation); starter skeleton files.
- Target capability: Gap G2 — endpoint correctness where the extremes are odd and negative-offset (3 → -4-style case).
- Target answer shape: two-file listing with floor-correct arithmetic.
- Difficulty / variation: closest structural analog to the failed task; distinct story.

### Spec 11: robot-registry-selfinit
- Files: `robot_registry.cpp`, `robot_registry.h` (test file: `robot_registry_test.cpp`)
- API: namespace `robots`; `int draw_serial();` (random in [100, 999]); `struct Robot { Robot(); int serial; int firmware; };` — default constructor must populate both fields.
- Prompt shape: factory robot-registry story; starter skeleton files.
- Target capability: Gaps G1, G3 — self-initializing struct: the default constructor fills members; no factory function.
- Target answer shape: header with inline or declared ctor; impl with a `<random>`-based helper; every member initialized.
- Difficulty / variation: two-member struct, one derived from the other (firmware = serial % 7).

### Spec 12: raffle-ticket-full-draw
- Files: `raffle.cpp`, `raffle.h` (test file: `raffle_test.cpp`)
- API: namespace `raffle;` → namespace `raffle`; `int draw_number();` (range [1, 49]); `struct Ticket { Ticket(); int a, b, c, d, e, f; int bonus; };` — constructor draws all six and sets `bonus` from a formula on them.
- Prompt shape: charity-raffle story; starter skeleton files.
- Target capability: Gaps G1, G3 — six self-drawn fields plus a derived seventh field consistent with them (the hitpoints pattern, new story).
- Target answer shape: struct ctor draws fields in order and computes the derived field from another field's final value.
- Difficulty / variation: derived-field consistency invariant checked by tests: `bonus == f(a)`.

### Spec 13: field-journal-weather-snapshot
- Files: `snapshot.cpp`, `snapshot.h` (test file: `snapshot_test.cpp`)
- API: namespace `fieldnotes`; `struct Snapshot { Snapshot(); int temperature; int wind; int chill; };` where `chill` is a deterministic function of temperature and wind set by the constructor.
- Prompt shape: arctic expedition log story; starter skeleton files.
- Target capability: Gap G3 — no member left indeterminate; derived member computed after the members it depends on.
- Target answer shape: ctor body assigns members in dependency order; impl split across .h/.cpp.
- Difficulty / variation: ordering trap — computing `chill` before assigning `wind` must be avoided.

### Spec 14: aquarium-tank-derived-invariant
- Files: `tank.cpp`, `tank.h` (test file: `tank_test.cpp`)
- API: namespace `aquarium`; `int safe_level(int capacity);` `struct Tank { Tank(); int capacity; int fill; };` with invariant `fill == safe_level(capacity)` after construction.
- Prompt shape: public-aquarium story; starter skeleton files.
- Target capability: Gap G3 edge case — post-construction invariant tying one field to a function of another (the `hitpoints == 10 + modifier(constitution)` pattern).
- Target answer shape: ctor sets capacity (random in range), then fill via the free function; invariant stated in a comment.
- Difficulty / variation: invariant is test-observable; any truncation bug in `safe_level` breaks it.

### Spec 15: starship-crew-header-ctor
- Files: `crew.cpp`, `crew.h` (test file: `crew_test.cpp`)
- API: namespace `fleet`; `int assign_station();` `struct CrewMember { CrewMember(); int station; int shift; };` with the ctor defined inline in the header delegating to the free function.
- Prompt shape: starship crew roster story; starter skeleton files.
- Target capability: Gap G1 — header-defined constructor calling a namespace free function declared above it; correct declaration order.
- Target answer shape: header declares free functions before the struct; ctor body inside the struct.
- Difficulty / variation: tests declaration-order discipline in the header.

### Spec 16: repair-uninitialized-greenhouse
- Files: `greenhouse.cpp`, `greenhouse.h` (test file: `greenhouse_test.cpp`)
- API: namespace `greenhouse`; `struct Bed { int zone; int moisture; };` (starter has no ctor) plus `int ideal_moisture(int zone);`.
- Prompt shape: repair row — starter already contains the constructor-less struct; the retry prompt shows test output with huge garbage integers "should be between" bounds; the model must add an initializing constructor.
- Target capability: Gaps G3, G4 — recognize indeterminate-value test failures as a missing constructor, not as a randomness bug.
- Target answer shape: whole-file listings adding `Bed();` and its definition; no other churn.
- Difficulty / variation: failure evidence is runtime garbage values, not a compile error.

### Spec 17: auction-quote-droplowest
- Files: `auction.cpp`, `auction.h` (test file: `auction_test.cpp`)
- API: namespace `auctioneer`; `int best_quote_total();` — draws four random quotes in [1, 6]-style small range, discards the lowest, sums the rest (result range [3, 18]-style).
- Prompt shape: sealed-bid auction story; starter skeleton files.
- Target capability: Gap G1 — free namespace function returning a bounded random aggregate; "sum minus min" reasoning without sort if preferred.
- Target answer shape: two-file listing; impl accumulates four draws and subtracts the minimum; range comment.
- Difficulty / variation: same aggregate shape as the failed task's `ability()`, new story; tests only range-membership.

### Spec 18: kiln-firing-random-range
- Files: `kiln.cpp`, `kiln.h` (test file: `kiln_test.cpp`)
- API: namespace `pottery`; `int firing_temp();` random in [950, 1300]; `int glaze_variant();` random in [1, 4].
- Prompt shape: ceramics-studio story; starter skeleton files.
- Target capability: Gap G1 — correct bounded random generation with `<random>` (or `<cstdlib>` with correct scaling); values always inside the published range.
- Target answer shape: two-file listing; no modulo bias discussion required, but bounds must be inclusive-exact.
- Difficulty / variation: two different ranges in one file; tests call each function many times.

### Spec 19: min-max-achievable-proof
- Files: `darts.cpp`, `darts.h` (test file: `darts_test.cpp`)
- API: namespace `darts;` → namespace `darts`; `int round_score();` = sum of best three of four throws, each throw in [1, 20].
- Prompt shape: pub-darts story; starter skeleton files; prompt explicitly asks the model to state the minimum and maximum achievable score in a comment.
- Target capability: Gaps G1, G2 — edge-case reasoning: derive range [3, 60] from the aggregation rule before coding.
- Target answer shape: two-file listing with a range comment matching the implementation's actual bounds.
- Difficulty / variation: comment-vs-code consistency is checked by review; wider range than siblings.

### Spec 20: factory-vs-selfinit-contrast
- Files: `badge.cpp`, `badge.h` (test file: `badge_test.cpp`)
- API: namespace `security`; `struct Badge { Badge(); int id; int clearance; };` — tests default-construct `Badge`.
- Prompt shape: contrastive row — the starter .h offers BOTH a passive struct and a `Badge make_badge();` factory; a test excerpt shows `Badge b;` default construction failing. The model must convert to a self-initializing struct and may drop or keep the factory.
- Target capability: Gap G1 (contrastive) — choose the design the test usage implies (self-initializing struct) over the factory design.
- Target answer shape: whole-file listings with ctor added; explanation of why the factory alone is insufficient.
- Difficulty / variation: negative/contrastive spec mirroring the exact attempt-1 design mistake.

### Spec 21: repair-missing-namespace-member
- Files: `observatory.cpp`, `observatory.h` (test file: `observatory_test.cpp`)
- API: namespace `observatory`; `int seeing_score();` must exist; `int cloud_cover();` already present.
- Prompt shape: repair row — starter compiles standalone but the retry prompt shows `error: 'seeing_score' is not a member of 'observatory'`; model must add the missing free function without renaming anything.
- Target capability: Gap G4 — surgical repair: add exactly the missing symbol, keep all existing behavior identical.
- Target answer shape: whole-file listings of both files with the single addition.
- Difficulty / variation: mirrors the attempt-2 compile fix that was done correctly; teaches doing it without collateral edits.

### Spec 22: repair-floor-after-compile-fix
- Files: `ski_resort.cpp`, `ski_resort.h` (test file: `ski_resort_test.cpp`)
- API: namespace `ski;` → namespace `ski`; `int lift_level(int altitude);` = floor((altitude - 1500) / 100).
- Prompt shape: two-turn repair — turn 1 starter has BOTH a missing symbol and a truncating `(altitude - 1500) / 100`; turn 1 fixes only the missing symbol (compile error); turn 2 shows failing assertions `-2 == -1` and requires fixing the arithmetic too.
- Target capability: Gaps G4, G2 — a retry must audit semantics, not just the surfaced error; fixing one bug must not freeze the other in place.
- Target answer shape: turn-2 whole-file listings with floor-correct arithmetic and a one-line rationale.
- Difficulty / variation: staged exactly like the dnd-character failure; different domain.

### Spec 23: repair-two-latent-bugs
- Files: `beehive.cpp`, `beehive.h` (test file: `beehive_test.cpp`)
- API: namespace `apiary`; `struct Hive { Hive(); int bees; int frames; int honey; };` with `honey` derived; plus floor-division helper `int frames_per_box(int frames);`.
- Prompt shape: repair row — compile error about a missing function masks (a) truncating division and (b) a constructor-less struct; the retry prompt shows only the compile error, but the correct repair fixes all three.
- Target capability: Gap G4 — proactive full-file audit during repair: search the file for other contract violations while fixing the reported one.
- Target answer shape: whole-file listings fixing all three defects in the second turn.
- Difficulty / variation: tests the "fix beyond the surfaced error" behavior directly.

### Spec 24: repair-partial-test-output-audit
- Files: `harbor.cpp`, `harbor.h` (test file: `harbor_test.cpp`)
- API: namespace `harbor`; `int tide_phase(int hour);` = floor((hour - 6) / 6); `struct Buoy { Buoy(); int channel; int phase; };`.
- Prompt shape: repair row — retry prompt contains truncated test output naming only one failed assertion; the model must re-read its own turn-1 files and find the second defect (uninitialized struct member) unaided.
- Target capability: Gap G4 — repair from incomplete evidence; whole-file self-review on the fix turn.
- Target answer shape: whole-file listings; both defects fixed; brief enumeration of what was checked.
- Difficulty / variation: evidence deliberately incomplete; no compiler help.

### Spec 25: negative-division-language-semantics
- Files: `ledger.cpp`, `ledger.h` (test file: `ledger_test.cpp`)
- API: namespace `ledger;` → namespace `ledger`; `int split_evenly_floor(int cents);` `int split_evenly_trunc(int cents);` — both provided so the difference for negative cents is explicit.
- Prompt shape: shared-expenses ledger story; starter skeleton files; prompt asks for a comment contrasting the two division modes.
- Target capability: Gap G2 — explicit knowledge that C++ integer division truncates toward zero (unlike Python floor division).
- Target answer shape: two functions side by side; comment with -7/2 example (-4 floor vs -3 trunc).
- Difficulty / variation: teaching-the-contrast row; both behaviors coexist.

### Spec 26: internal-helpers-linkage
- Files: `greenhouse_ctrl.cpp`, `greenhouse_ctrl.h` (test file: `greenhouse_ctrl_test.cpp`)
- API: namespace `gh;` → namespace `gh`; public: `int mist_cycle();` `struct Valve { Valve(); int zone; int flow; };` — private helpers (single-draw function) must live in the .cpp only, in an unnamed namespace or as static, NOT declared in the header.
- Prompt shape: automated greenhouse story; starter skeleton files.
- Target capability: Gaps G1, header/impl separation — keep internal helpers out of the public header; only the test-facing API is declared.
- Target answer shape: header with only public API; .cpp with unnamed-namespace helpers.
- Difficulty / variation: penalizes leaking `roll_d6`-style helpers into the header.

### Spec 27: name-fidelity-no-rename
- Files: `ferry.cpp`, `ferry.h` (test file: `ferry_test.cpp`)
- API: namespace `ferry;` → namespace `ferry`; `int crossing_minutes();` `struct Manifest { Manifest(); int cars; int trucks; };` — names fixed by starter declarations that must be kept verbatim.
- Prompt shape: harbor-ferry story; starter files already contain declaration names; prompt stresses "Don't change the names of existing functions or classes."
- Target capability: Gap G1 — name/namespace fidelity: extend the given declarations rather than inventing parallel ones (`make_manifest` etc.).
- Target answer shape: whole-file listings preserving every existing identifier, adding only bodies and helpers.
- Difficulty / variation: starter declarations are deliberately sparse (no ctor) so the model must add, not rename.

### Spec 28: long-file-whole-listing
- Files: `observatory_log.cpp`, `observatory_log.h` (test file: `observatory_log_test.cpp`)
- API: namespace `starlog`; five free functions + one self-initializing struct, ~150 lines total.
- Prompt shape: astronomy observation-log story; larger starter with several implemented functions plus two to add.
- Target capability: format contract — whole-file listing of a long file with zero elision (no "..." or "rest unchanged" comments), both files emitted.
- Target answer shape: complete listings; unchanged regions reproduced verbatim.
- Difficulty / variation: length pressure tests the no-elision rule.

### Spec 29: all-faces-equal-edge
- Files: `bingo.cpp`, `bingo.h` (test file: `bingo_test.cpp`)
- API: namespace `bingo;` → namespace `bingo`; `int card_score(int a, int b, int c, int d);` = sum of largest three of four equal-range values.
- Prompt shape: bingo-night story; deterministic scoring function (no randomness) so degenerate inputs are testable.
- Target capability: Gap G2/G1 edge case — degenerate inputs: all four equal (drop one, sum 3x), all minimal, all maximal.
- Target answer shape: two-file listing; implementation correct for ties (any one of the equal minima dropped).
- Difficulty / variation: tie-handling is the trap for sort-then-index implementations.

### Spec 30: uninitialized-vs-value-init-contrast
- Files: `capsule.cpp`, `capsule.h` (test file: `capsule_test.cpp`)
- API: namespace `space`; `struct Capsule { Capsule(); int oxygen; int fuel; };`
- Prompt shape: contrastive row — starter shows the struct with no ctor and a comment claiming "fields are zero-initialized automatically"; the retry excerpt shows garbage-value test failures. Model must correct the misconception and the code.
- Target capability: Gap G3 (contrastive) — know that default-initialized `int` members are indeterminate; only constructors, default member initializers, or value-initialization make them defined.
- Target answer shape: whole-file listings with ctor or in-class initializers; corrected comment.
- Difficulty / variation: the starter's wrong comment must be fixed too — sweeps stale comments after behavior change.

Gap coverage: G1 — specs 01, 03, 04, 11, 12, 15, 17, 18, 19, 20, 26, 27; G2 — 05, 06, 07, 08, 09, 10, 22, 25, 29; G3 — 04, 11, 12, 13, 14, 16, 23, 30; G4 — 02, 16, 21, 22, 23, 24. Required mix: format-contract 3 (01, 02, 28), header/impl separation 3 (03, 04, 26), exception-policy 0 (contract has none), edge cases 6 (06, 09, 10, 14, 19, 29), repair/retry 5 (16, 21, 22, 23, 24), contrastive 3 (08, 20, 30).

## 6. Acceptance & Validation Gates

- Parser validity: each training row's answer must parse as Aider whole-file listings — bare filename line, opening fence, full content, closing fence; no `diff` fences, no elision comments.
- Compile+test receipt: every row must build with the benchmark's CMake/Catch2 setup (`g++`, C++17, `-Wall`-clean) and pass its own synthetic test file; receipts stored with the row.
- Hidden-edge coverage: rows teaching floor division must include at least one odd negative-offset case (e.g. x = 3 in a `(x-10)/2` shape); rows teaching self-initializing structs must include a default-construction range/invariant test.
- Repair rows: turn-1 answer must be genuinely wrong in the scripted way (missing symbol / truncation / missing ctor), and turn-2 must fix all scripted defects; a row where turn-2 still fails its tests is rejected.
- Contrastive rows: the "wrong" variant must actually fail the row's tests and the "right" variant must pass; both are retained as the contrast pair.
- Contamination check: no spec's prompt, test file, or target answer may share story text, identifier sets, or test values with `dnd_character_test.cpp` or `.meta/example.*`; automated similarity scan against the benchmark exercise directory before inclusion.
- Whole-file output rule: rejected rows include partial listings, diff-only answers, prose-only answers, or answers that rename the given API.

## 7. Cross-Check Statement (2026-07-24)

Performed on 2026-07-24:

1. Re-read every cited failure-log range via `sed -n` on the failure log and re-verified quote text and line numbers:
   - Section header/outcomes at lines 13155-13160 (shard 0, `[False, False]`, FAIL) — confirmed.
   - Attempt-1 header/impl quotes (source lines 2398-2408, 2445-2446) — confirmed at failure-log lines 13595-13605 and 13642-13643; corrected one citation: the `modifier` truncating return is source line 2446 (failure-log line 13643), not 2447.
   - Compile error (source lines 2576-2577) — confirmed at failure-log lines 13773-13774, and independently against `...-shard-0/benchmark.log` line 2576 (identical text).
   - Retry scope quote (source line 3514) — confirmed at failure-log line 13813.
   - Retry additions (source lines 3647, 3663-3666) and unchanged truncating modifier (source line 3732) — confirmed at failure-log lines 13946, 13962-13965, 14031.
   - Terminal failures (source lines 4219-4222, 4263-4266, 4293-4296, 4298-4300) — confirmed at failure-log lines 14242-14245, 14286-14289, 14316-14319, 14321-14323; shard-0 `benchmark.log` lines 4220 and 4266 match verbatim.
   - Results JSON `tests_outcomes [false, false]` (source lines 4314-4316) — confirmed at failure-log lines 14337-14339; matches the section header outcome array and the run summary.
2. Re-checked every API claim against ground truth: `int modifier(int score);` (`.meta/example.h:4`), `int ability();` (`.meta/example.h:5`), `struct Character` with self-initializing ctor (`.meta/example.h:7-24`, ctor body 8-16), floor-based modifier (`.meta/example.cpp:9-11`), drop-lowest `ability()` (`.meta/example.cpp:15-20`), and the enforcing tests (`dnd_character_test.cpp:30-58` modifier table including odd scores 3/5/7/9, `:96-99` free `ability()`, `:101-110` default-constructed `Character` with hitpoints invariant). All confirmed; the contract has no exception policy, so section 4 and the spec mix record none.
3. Noted in section 1 that terminal-log source lines ~4045-4189 are interleaved `bank-account` content from the shared shard-0 log; only dnd-character lines were used as evidence.
4. Corrections made during cross-check: the `modifier` source-line citation (2446, not 2447); added the failure-log absolute line numbers alongside source line numbers for every quote. No other discrepancies found.
