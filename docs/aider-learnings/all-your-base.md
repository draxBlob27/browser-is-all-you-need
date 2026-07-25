# Aider Learning Document: `all-your-base`

Failure analysis of GLM-4.7 SFT eval run `glm47-aider-expansion-sft-fixed26-20260723T091839Z`
and the resulting SFT dataset plan. Answer-blind: no benchmark test fixtures or reference
code are copied into training-task specifications below; the reference is used only to
diagnose the failure and derive abstract requirements.

## 1. Task Identity & Evidence Pointers

- Task slug: `all-your-base`
- Shard: `0` (failure-log section header, line 188: "Shard: `0`")
- Editable files: `all_your_base.cpp, all_your_base.h` (failure-log line 189)
- Test outcomes: `[False, False]` (failure-log line 190); Result: `FAIL` (line 191)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md`, lines 186-1335.
  - Prompt messages: lines 193-234.
  - Attempt 1 excerpt: lines 236-598 ("Attempt/log chunk 1, source lines 458-816").
  - Attempt 2 excerpt: lines 600-1008 ("Attempt/log chunk 2, source lines 4357-4761").
  - Terminal test log + result JSON: lines 1010-1335 (source lines 20513-20826).
- Raw shard log (cross-check evidence): `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log`. Because the shard ran tasks in parallel threads, the `all-your-base` conversation is interleaved with other tasks; the model produced 6 answers total (`num_user_asks: 6`, result JSON source line 20786), applied edits at shard lines 793-794, 4738, 8449-8450, 13196-13197, 13817, 19789-19790.
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/all-your-base/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/all-your-base/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/all-your-base/all_your_base_test.cpp`
- Existing analog dir (granularity reference): `aider-fixed26-analogs/fixed26-b001-all-your-base/` (50 implemented analogs).

## 2. Benchmark Contract (Ground Truth)

File set: exactly `all_your_base.h` + `all_your_base.cpp`; tests live in `all_your_base_test.cpp` and include the header (`all_your_base_test.cpp:1`).

- Namespace: `all_your_base` (`.meta/example.h:6`, `.meta/example.cpp:5`).
- Public API — a single free function, bases first, digits second (`.meta/example.h:8-10`):
  ```cpp
  std::vector<unsigned int> convert(unsigned int input_base,
                                    const std::vector<unsigned int>& input_digits,
                                    unsigned int output_base);
  ```
  The header must include `<vector>` (`.meta/example.h:4`).
- Call convention enforced by the tests: base, then digits, then base — e.g.
  `all_your_base::convert(2, in_digits, 10)` (`all_your_base_test.cpp:15`),
  `convert(97, in_digits, 73)` (`all_your_base_test.cpp:72`). Parameter order is part of
  the contract; a digits-first signature does not compile against the tests.
- Exception policy: throw `std::invalid_argument` when `input_base <= 1` or
  `output_base <= 1` (`.meta/example.cpp:12-13`), and when any digit is `>= input_base`
  (`.meta/example.cpp:16-18`). Enforced by five `REQUIRE_THROWS_AS(..., std::invalid_argument)`
  tests: `first_base_is_one` (`all_your_base_test.cpp:109-113`), `first_base_is_zero`
  (`:115-119`), `invalid_positive_digit` (`:121-125`), `second_base_is_one` (`:127-131`),
  `second_base_is_zero` (`:133-137`). Requires `<stdexcept>` (`.meta/example.cpp:3`).
- Zero semantics: a zero numeric value converts to an **empty** digit vector, not `{0}`.
  `single_zero` expects `in_digits{0}` -> `expected{}` (`all_your_base_test.cpp:85-91`);
  `multiple_zeros` expects `{0,0,0}` -> `{}` (`:93-99`). This falls out of the reference
  loop `while (value != 0)` (`.meta/example.cpp:21-25`): value 0 yields an empty result.
- Empty input: `convert(2, {}, 10)` returns `{}` (`all_your_base_test.cpp:77-83`;
  `.meta/example.cpp:14-15`).
- Leading zeros: `{0, 6, 0}` base 7 -> `{4, 2}` base 10, i.e. leading zeros contribute
  nothing under Horner accumulation (`all_your_base_test.cpp:101-107`).
- Large radices: digits are integer values, not characters; base 97 / 73 appear in
  `fifteen_bit_integer` (`all_your_base_test.cpp:69-75`).
- Output-format constraint (Aider harness): the system prompt demands *whole-file*
  listings — filename line, opening fence, entire file content, closing fence; "NEVER
  skip, omit or elide content" (failure-log lines 199-210). `edit_format` is `whole`
  (result JSON, source line 20776).

## 3. Failure Anatomy

### Attempt 1 (shard-log source lines 458-816, excerpted at failure-log lines 236-580)

What the model emitted: `all_your_base.h` and `all_your_base.cpp` as **```diff hunk
fences**, not whole-file listings — source line 718 opens the header with "```diff" and
an `@@ -1,8 +1,12 @@` hunk; source lines 739-790 do the same for the `.cpp`. The harness
still applied them (source lines 793-795: "Applied edit to all_your_base.cpp / .h"), so
the format violation was not itself fatal here, but it set up the later empty-diff
disaster. The header hunk also contains a mangled line
`-#endif // ALL_YOUR_BASE_H+#endif // ALL_YOUR_BASE_H` (source line 732), caused by the
starter header lacking a trailing newline.

Semantic divergences from the contract (all hard evidence from the emitted diff body):

1. **Wrong parameter order.** Emitted signature
   `std::vector<unsigned int> convert(const std::vector<unsigned int>& digits, int from_base, int to_base)`
   (source lines 746-747) — digits first. The tests call `convert(2, in_digits, 10)`;
   the first test compile therefore failed:
   shard-0 line 7800: `all_your_base_test.cpp:15:62: error: invalid initialization of reference of type 'const std::vector<unsigned int>&' from expression of type 'int'`,
   repeated for every test case (shard lines 7800-7920), with
   shard line 7804: `all_your_base.h:8:68: note: in passing argument 1 of '...convert(const std::vector<unsigned int>&, int, int)'`.
2. **Sentinel-return instead of exceptions.** Thinking: source lines 489-490 —
   "Invalid `from_base` (<= 1): Return empty vector." / "Invalid digits (digits >= `from_base`): Return empty vector."
   Emitted code, source lines 749-751: `if (from_base <= 1 || to_base <= 1) { return {}; }`
   and lines 758-763: digit-validation also `return {};`. The contract requires
   `throw std::invalid_argument` in all three situations.
3. **Wrong zero representation.** Thinking, source line 502: "If `decimal_value` is 0,
   return `[0]`." Emitted code, source lines 771-774:
   `if (decimal_value == 0) { return {0}; }`. The contract expects `{}`.
4. **Type drift (non-fatal).** Bases declared `int` instead of `unsigned int`
   (source line 747) — still compiles against the tests, but off-contract.

Inference (root cause, attempt 1): the model **hallucinated prior knowledge of this exact
Exercism task and got it wrong**. In the retry thinking it explicitly asserted (shard-log
source lines 4419-4421): "looking at Exercism C++ track 'All Your Base', the signature is
indeed `convert(const std::vector<unsigned int>& digits, int from_base, int to_base);`" —
that remembered signature is false; the real contract is bases-first with `unsigned int`
bases (`.meta/example.h:8-10`). The instructions shown to the model never mention
exceptions or zero representation, so gaps 2 and 3 were partly hidden-contract failures —
but the model *chose* its policy by unverified assumption instead of flagging the
ambiguity, despite the system prompt's "If the request is ambiguous, ask questions."

### Retry loop (6 answers total; `num_user_asks: 6`, source line 20786)

- **Round 2** (source lines 4357-4761): the retry prompt contained no error text at all —
  only "# Fix any errors below, if possible." and "## See relevant line below marked with █."
  followed by a snippet of the header (source lines 797-808). After ~370 lines of
  reasoning the model concluded "The code is valid. I will return the file content
  unchanged" (source lines 4687-4688) and then emitted an **empty diff fence**:
  source lines 4732-4736 —
  ```
  all_your_base.h

  ```diff

  ```
  ```
  i.e. a filename followed by a fence containing nothing. "Applied edit to
  all_your_base.h" (source line 4740) — a no-op. Nothing was fixed.
- **Round 3** (shard lines ~8260-8450): this prompt reached the model with the actual
  compiler errors. The thinking quotes `all_your_base_test.cpp:112:46: error: invalid
  initialization of reference ...` and the full source line
  `REQUIRE_THROWS_AS(all_your_base::convert(1, in_digits, 10), std::invalid_argument);`
  (shard lines 8287-8290). The answer correctly diagnosed "the test file calls the
  function with the arguments in the order `(int, vector, int)`, but the header file
  declares them as `(vector, int, int)`" and swapped the signature to
  `convert(int from_base, const std::vector<unsigned int>& digits, int to_base)` via diff
  hunks (applied, shard lines 8449-8450). **Critical miss:** the `std::invalid_argument`
  requirement was *literally visible* in the quoted test line, yet the model fixed only
  the parameter order and kept the `return {};` policy and the `{0}` zero case. After
  this round the code compiled.
- **Rounds 4-6** (shard answers before lines 13196-13197, 13817, 19789-19790): each
  prompt was again only a █-marked snippet with no error message. Each time the model's
  thinking composed the full, correct file contents (e.g. round 5 thinking writes out the
  complete header, shard lines ~13775-13790; round 6 thinking writes out both complete
  files, shard lines ~19660-19720) — and each time the emitted answer was **empty
  ```diff fences** for one or both files. Three more no-op rounds; the retry budget was
  exhausted without the semantic failures ever being addressed.

### Terminal test run (source lines 20678-20769)

The final code compiled (`[100%] Built target all-your-base`, source line 20683) and ran:
`test cases: 17 | 10 passed | 7 failed` (source lines 20762-20763). The 7 failures:

- `single_zero` (source lines 20689-20698): `REQUIRE( expected == out_digits )` with
  expansion `{  } == { 0 }` — test expects `{}`, model returned `{0}`.
- `multiple_zeros` (source lines 20700-20709): same expansion `{  } == { 0 }`.
- `first_base_is_one` (source lines 20717-20719):
  `REQUIRE_THROWS_AS( all_your_base::convert(1, in_digits, 10), std::invalid_argument )`
  "because no exception was thrown where one was expected".
- `first_base_is_zero` (source lines 20727-20729), `invalid_positive_digit` (20737-20739),
  `second_base_is_one` (20747-20749), `second_base_is_zero` (20757-20759): all
  "no exception was thrown where one was expected".

Result JSON (source lines 20772-20780): `"tests_outcomes": [false, false]`,
`"num_malformed_responses": 0` (source line 20788 — the empty-diff answers were not even
counted as malformed), `"num_exhausted_context_windows": 0` (20787).

## 4. Knowledge / Capability Gaps

- **G1 — Aider whole-file format discipline.** The model emitted ```diff hunk fences
  against an explicit whole-file contract (attempt 1, source lines 718, 739-740), and —
  far worse — emitted *empty* diff fences on 4 of 5 retry rounds (source lines 4732-4736;
  shard answers before lines 13196, 13817, 19789), each time after composing the full
  file in its thinking. A response whose answer body contains no content is the single
  most damaging behavior observed: it burned the entire retry budget.
- **G2 — Signature fidelity vs. hallucinated recall.** The model invented a digits-first
  signature and later explicitly defended it with a false memory of the Exercism C++
  track (source lines 4419-4421). It lacked the discipline to treat the prompt and
  compiler/test feedback — not memorized kata solutions — as the contract (attempt-1
  signature at source lines 746-747 vs `.meta/example.h:8-10`; compile errors at shard
  lines 7800-7920).
- **G3 — Exception-policy awareness.** Faced with an unstated error-handling contract,
  the model defaulted to sentinel returns (`return {};`, source lines 749-751, 758-763)
  and never reconsidered, producing all five `REQUIRE_THROWS_AS` failures (source lines
  20717-20759). It does not know the C++-exercise convention that invalid arguments
  mean `throw std::invalid_argument` (`<stdexcept>`), not empty results.
- **G4 — Zero / edge-case representation reasoning.** The model guessed "0 in any base
  is just `[0]`" (source lines 491-492, 502, 771-774); the contract's digit-sequence
  model yields an empty sequence for value zero (test lines 85-99). It did not reason
  about what a repeated-division loop naturally produces for input value 0.
- **G5 — Behavior under sparse repair feedback.** Given only a █-marked line and no
  error message (source lines 797-808), the model reasoned "the code is valid ... return
  the file content unchanged" (source lines 4687-4688) and then did not even do that —
  it emitted an empty fence (G1). It lacked a sane fallback: re-emit the full current
  files, or re-audit the code against everything known (call sites, prior compiler
  errors) before declaring "no errors".
- **G6 — Mining visible error output for the *whole* contract.** In round 3 the model
  quoted `REQUIRE_THROWS_AS(..., std::invalid_argument)` from the compiler output (shard
  lines 8287-8290) and still fixed only the parameter order. It extracted the compile
  error but not the exception expectation staring at it in the same quoted lines.

## 5. SFT Task Specifications (30 specs)

Domain variety is deliberate; no spec reuses the "base conversion / math professor"
story. Each spec teaches ONE primary capability and names the gap it repairs.

### Spec 01: beacon-frame-whole-file
- Files: `beacon_frame.cpp`, `beacon_frame.h` (test file: `beacon_frame_test.cpp`)
- API: namespace `beacon`; `std::vector<unsigned int> reencode(unsigned int symbol_radix, const std::vector<unsigned int>& symbols, unsigned int wire_radix);` throws `std::invalid_argument` if either radix < 2 or any symbol >= symbol_radix.
- Prompt shape: satellite ground-station re-encodes telemetry symbol frames between two symbol alphabets; model sees empty namespace stubs in both files plus the whole-file listing instructions.
- Target capability: G1 — emit two complete whole-file listings with plain fences; no diff hunks, no elision.
- Target answer shape: brief plan sentence, then `beacon_frame.h` full listing (guards, `<vector>`, declaration) and `beacon_frame.cpp` full listing (`<stdexcept>`, definition).
- Difficulty / variation: foundational; starter files end without trailing newline to reproduce the hunk-mangle hazard seen at source line 732.

### Spec 02: glacier-core-whole-file
- Files: `glacier_core.cpp`, `glacier_core.h` (test file: `glacier_core_test.cpp`)
- API: namespace `glacier`; `std::vector<unsigned int> rescale(unsigned int from_step, const std::vector<unsigned int>& readings, unsigned int to_step);` throws `std::invalid_argument` on step < 2 or reading >= from_step.
- Prompt shape: ice-core drill logs depth readings in one measurement step, lab needs another; empty stubs.
- Target capability: G1 — whole-file listing discipline when the correct implementation is long (~50 lines); no "// rest unchanged".
- Target answer shape: both files complete; `.cpp` includes only `<stdexcept>` and its own header.
- Difficulty / variation: longer implementation than Spec 01 to tempt elision.

### Spec 03: empty-fence-recovery
- Files: `harbor_dock.cpp`, `harbor_dock.h` (test file: `harbor_dock_test.cpp`)
- API: namespace `harbor`; `std::vector<unsigned int> reberth(unsigned int old_lanes, const std::vector<unsigned int>& ships, unsigned int new_lanes);` throws `std::invalid_argument` on lanes < 2 or ship >= old_lanes.
- Prompt shape: two-turn repair. Turn 1: implement from stubs. Turn 2 prompt: "# Fix any errors below, if possible." plus a █-marked snippet of the header with no error text; the model's (seeded) turn-1 answer in the transcript ended with an empty code fence.
- Target capability: G1+G5 — never answer with an empty fence; on sparse feedback, re-emit the full current correct files.
- Target answer shape: turn 2 is two complete whole-file listings identical in content to a correct turn 1.
- Difficulty / variation: directly counterfactual to the observed rounds 2/4/5/6 behavior.

### Spec 04: tide-gauge-header-split
- Files: `tide_gauge.cpp`, `tide_gauge.h` (test file: `tide_gauge_test.cpp`)
- API: namespace `tide`; declaration only in header: `std::vector<unsigned int> convert_marks(unsigned int staff_units, const std::vector<unsigned int>& marks, unsigned int chart_units);` throws `std::invalid_argument` on units < 2.
- Prompt shape: harbor office converts tide-staff marks to chart units; stubs with include guards present.
- Target capability: G2 — header/impl separation: guards + `<vector>` + declaration in `.h`, single definition in `.cpp`, no logic in header.
- Target answer shape: `.h` contains no function body; `.cpp` includes its own header first.
- Difficulty / variation: foundational header-discipline row.

### Spec 05: orchard-index-header-split
- Files: `orchard_index.cpp`, `orchard_index.h` (test file: `orchard_index_test.cpp`)
- API: namespace `orchard`; `std::vector<unsigned int> rebin(unsigned int bins_per_row, const std::vector<unsigned int>& crates, unsigned int bins_per_truck);` throws `std::invalid_argument` on bins < 2 or crate >= bins_per_row.
- Prompt shape: packing cooperative re-bins apple-crate counts; stubs.
- Target capability: G2 — header/impl separation with exact matching signatures across both files (any drift is a compile error).
- Target answer shape: signature text identical between declaration and definition, parameter names included in both.
- Difficulty / variation: parameter names differ from sibling specs to force copying discipline rather than memorized shape.

### Spec 06: kiln-bricks-call-order
- Files: `kiln_bricks.cpp`, `kiln_bricks.h` (test file: `kiln_bricks_test.cpp`)
- API: namespace `kiln`; `std::vector<unsigned int> restack(unsigned int stack_base, const std::vector<unsigned int>& stack, unsigned int pallet_base);` throws `std::invalid_argument` on base < 2 or entry >= stack_base.
- Prompt shape: pottery kiln restacks numbered brick positions; the prompt's usage paragraph shows one concrete call `restack(8, positions, 4)` establishing operand order; stubs.
- Target capability: G2 — derive parameter order from the prompt's shown call site, not from habit.
- Target answer shape: signature with radix parameters flanking the vector, matching the shown call.
- Difficulty / variation: call-site order is (radix, digits, radix); a sibling (Spec 07) uses a different story but same order to reinforce.

### Spec 07: ferry-manifest-unsigned
- Files: `ferry_manifest.cpp`, `ferry_manifest.h` (test file: `ferry_manifest_test.cpp`)
- API: namespace `ferry`; `std::vector<unsigned int> relist(unsigned int lane_count, const std::vector<unsigned int>& vehicles, unsigned int deck_count);` — `unsigned int` for all scalar parameters and elements; throws `std::invalid_argument` on count < 2 or vehicle >= lane_count.
- Prompt shape: ferry operator reassigns vehicle lane numbers to deck numbering; stubs.
- Target capability: G2 — exact unsigned-type fidelity; no `int`/`unsigned` mix that forces casts like the observed `(unsigned int)from_base`.
- Target answer shape: comparisons `v >= lane_count` with no casts anywhere.
- Difficulty / variation: implementation must avoid signed/unsigned comparison warnings.

### Spec 08: memorized-signature-trap (contrastive)
- Files: `archive_scroll.cpp`, `archive_scroll.h` (test file: `archive_scroll_test.cpp`)
- API: namespace `archive`; `std::vector<unsigned int> transliterate(unsigned int script_base, const std::vector<unsigned int>& glyphs, unsigned int codex_base);` throws `std::invalid_argument` on base < 2 or glyph >= script_base.
- Prompt shape: deliberately resembles a famous kata ("convert glyphs between ancient numeral systems") but the prompt explicitly specifies base-first order; include a seeded wrong first attempt that used the digits-first "remembered" signature and the compiler error it produced.
- Target capability: G2 — contrastive: prompt/call-site contract overrides memorized kata signatures.
- Target answer shape: corrected base-first signature in both files, whole-file listings.
- Difficulty / variation: the only spec where the story intentionally baits memorization.

### Spec 09: vault-dial-radix-throw
- Files: `vault_dial.cpp`, `vault_dial.h` (test file: `vault_dial_test.cpp`)
- API: namespace `vault`; `std::vector<unsigned int> recommbo(unsigned int dial_ticks, const std::vector<unsigned int>& combo, unsigned int door_ticks);` throws `std::invalid_argument` when either tick count < 2, and when any combo value >= dial_ticks.
- Prompt shape: locksmith re-expresses a safe combination on a door dial with a different tick count; stubs.
- Target capability: G3 — throw `std::invalid_argument` (with `<stdexcept>`) for out-of-domain scalar parameters instead of returning sentinels.
- Target answer shape: guard clause at top of function throwing before any accumulation.
- Difficulty / variation: exception on scalars only; digit check is the sibling Spec 10.

### Spec 10: cargo-lanes-digit-throw
- Files: `cargo_lanes.cpp`, `cargo_lanes.h` (test file: `cargo_lanes_test.cpp`)
- API: namespace `cargo`; `std::vector<unsigned int> reshuffle(unsigned int lane_radix, const std::vector<unsigned int>& manifest, unsigned int hold_radix);` throws `std::invalid_argument` when any manifest entry >= lane_radix (message "invalid manifest entry"), and on radix < 2.
- Prompt shape: port authority re-manifests cargo lane assignments; stubs.
- Target capability: G3 — per-element validation loop that throws on the first invalid element.
- Target answer shape: range-for validation with throw inside the loop, before value accumulation.
- Difficulty / variation: element-level throw; scalar-level throw is Spec 09.

### Spec 11: assay-ledger-two-throw-sites
- Files: `assay_ledger.cpp`, `assay_ledger.h` (test file: `assay_ledger_test.cpp`)
- API: namespace `assay`; `std::vector<unsigned int> regrade(unsigned int ore_scale, const std::vector<unsigned int>& samples, unsigned int report_scale);` two distinct throw sites with distinct messages ("scale too small", "sample off scale").
- Prompt shape: mining lab converts ore-sample grades between reporting scales; stubs.
- Target capability: G3 — multiple exception sites, each with a descriptive message string; correct `#include <stdexcept>` placement in the `.cpp`.
- Target answer shape: base-check throw first, digit-check throw second, both with messages.
- Difficulty / variation: message strings required (tests match on `.what()` substrings).

### Spec 12: throws-from-compiler-output (repair)
- Files: `rail_gauge.cpp`, `rail_gauge.h` (test file: `rail_gauge_test.cpp`)
- API: namespace `rail`; `std::vector<unsigned int> respace(unsigned int tie_spacing, const std::vector<unsigned int>& ties, unsigned int sleeper_spacing);` throws `std::invalid_argument` on spacing < 2 or tie >= tie_spacing.
- Prompt shape: two-turn repair. Turn 1 seeded answer uses `return {};` sentinel policy and compiles. Turn 2 prompt shows Catch2 output: three `REQUIRE_THROWS_AS(..., std::invalid_argument)` failures "no exception was thrown where one was expected".
- Target capability: G3+G6 — convert sentinel-return policy to throwing policy when test output demands it.
- Target answer shape: turn 2 rewrites validation to throws; everything else unchanged; whole-file listings.
- Difficulty / variation: error output contains only runtime failures, no compile errors.

### Spec 13: zero-yield-empty-result
- Files: `harvest_yield.cpp`, `harvest_yield.h` (test file: `harvest_yield_test.cpp`)
- API: namespace `fields`; `std::vector<unsigned int> rebale(unsigned int field_rows, const std::vector<unsigned int>& bales, unsigned int barn_rows);` throws `std::invalid_argument` as usual; a zero total yield returns an empty vector.
- Prompt shape: farm co-op re-tallies bale counts between field and barn layouts; prompt's examples include one showing zero input producing an empty tally; stubs.
- Target capability: G4 — value-zero maps to an empty digit sequence, not a single zero element.
- Target answer shape: accumulation + `while (value != 0)` emit loop with no special-case `return {0}`.
- Difficulty / variation: prompt example states the rule explicitly; Spec 14 hides it.

### Spec 14: empty-crate-empty-result
- Files: `crate_tally.cpp`, `crate_tally.h` (test file: `crate_tally_test.cpp`)
- API: namespace `depot`; `std::vector<unsigned int> restow(unsigned int shelf_width, const std::vector<unsigned int>& crates, unsigned int pallet_width);` empty crate list returns empty; throws on width < 2 or crate >= shelf_width.
- Prompt shape: warehouse restows crate positions; stubs; no hint about empty input.
- Target capability: G4 — empty input vector short-circuits to empty output before validation of digits (but after radix validation, matching the reference's ordering: base check, empty check, digit check).
- Target answer shape: three-step guard ordering: throw on bad radix, return {} on empty, throw on bad element.
- Difficulty / variation: guard *ordering* is the lesson — radix check must precede the empty early-return so `convert(1, {}, 10)` still throws (mirrors `first_base_is_one` with empty digits, test lines 109-113).

### Spec 15: leading-zeros-horner
- Files: `trail_markers.cpp`, `trail_markers.h` (test file: `trail_markers_test.cpp`)
- API: namespace `trail`; `std::vector<unsigned int> reblaze(unsigned int old_posts, const std::vector<unsigned int>& markers, unsigned int new_posts);` leading zero markers are insignificant; throws as usual.
- Prompt shape: hiking club renumbers trail markers; stubs.
- Target capability: G4 — Horner accumulation (`value = value * radix + d`) makes leading zeros free; no pre-stripping pass.
- Target answer shape: single accumulation loop, no special leading-zero handling.
- Difficulty / variation: tests include inputs with several leading zeros and all-zero prefixes.

### Spec 16: all-zeros-frame
- Files: `signal_frame.cpp`, `signal_frame.h` (test file: `signal_frame_test.cpp`)
- API: namespace `signal`; `std::vector<unsigned int> remod(unsigned int carrier_levels, const std::vector<unsigned int>& frame, unsigned int line_levels);` an all-zero frame of any length returns an empty vector; throws as usual.
- Prompt shape: radio technician re-modulates a silence frame; stubs.
- Target capability: G4 — repeated zeros accumulate to value 0, hence empty output; distinct from the empty-input case (Spec 14).
- Target answer shape: no branch on input contents; zero handling falls out of the emit loop.
- Difficulty / variation: sibling of Spec 13 but with multi-element all-zero input, matching the `multiple_zeros` failure at source lines 20700-20709.

### Spec 17: large-radix-archive
- Files: `scroll_archive.cpp`, `scroll_archive.h` (test file: `scroll_archive_test.cpp`)
- API: namespace `scrolls`; `std::vector<unsigned int> reshelve(unsigned int room_code, const std::vector<unsigned int>& volumes, unsigned int vault_code);` radices up to 250; digit values are integers, never characters; throws as usual.
- Prompt shape: monastery re-shelves volume codes between rooms with hundreds of slots; stubs.
- Target capability: G4 — digits-as-integers mindset; no char/alphabet mapping, no `std::stoi`, no `pow`.
- Target answer shape: pure integer arithmetic; no `<string>` or `<cmath>` includes.
- Difficulty / variation: tests use radix > 36 to break any base-N-as-string instinct.

### Spec 18: horner-chain-odometer
- Files: `odometer_gears.cpp`, `odometer_gears.h` (test file: `odometer_gears_test.cpp`)
- API: namespace `odometer`; `std::vector<unsigned int> regear(unsigned int gear_teeth_in, const std::vector<unsigned int>& reading, unsigned int gear_teeth_out);` throws as usual; conversion must be manual.
- Prompt shape: bicycle computer re-expresses an odometer reading on different gear ratios; prompt forbids library base conversion helpers; stubs.
- Target capability: G4 — manual positional-notation accumulation and repeated-division emission (the exercise's "implement it yourself" rule).
- Target answer shape: two loops (accumulate, divide-collect-reverse) or divide-insert-at-front; no `std::pow`, no `std::stoul`.
- Difficulty / variation: algorithmic-core row; story forbids the same helpers as the original exercise note.

### Spec 19: reverse-collect-press
- Files: `press_plates.cpp`, `press_plates.h` (test file: `press_plates_test.cpp`)
- API: namespace `press`; `std::vector<unsigned int> repress(unsigned int plate_slots, const std::vector<unsigned int>& plates, unsigned int tray_slots);` throws as usual.
- Prompt shape: printing shop re-arranges plate counts into tray counts; stubs.
- Target capability: G4 — correct digit order on emission: least-significant-first collection must be reversed (or inserted at front); tests catch reversed output.
- Target answer shape: `std::reverse` with `<algorithm>`, or `insert(begin(), d)`; a comment noting why.
- Difficulty / variation: tests use multi-digit outputs where reversal is observable.

### Spec 20: sparse-marker-repair
- Files: `lighthouse_lens.cpp`, `lighthouse_lens.h` (test file: `lighthouse_lens_test.cpp`)
- API: namespace `light`; `std::vector<unsigned int> refract(unsigned int prism_facets, const std::vector<unsigned int>& flashes, unsigned int lens_facets);` throws as usual.
- Prompt shape: two-turn repair where turn 2 is exactly the observed failure shape: "# Fix any errors below, if possible." + "## See relevant line below marked with █." + header snippet, no error text; the seeded turn-1 answer is already correct except it used signed `int` facet counts.
- Target capability: G5 — under message-free repair prompts, re-audit against the original spec, make the one defensible improvement, and emit full files.
- Target answer shape: whole-file listings with the unsigned-type correction; never an empty fence.
- Difficulty / variation: sparsest possible feedback; directly replays source lines 797-808.

### Spec 21: signature-swap-repair
- Files: `canal_locks.cpp`, `canal_locks.h` (test file: `canal_locks_test.cpp`)
- API: namespace `canal`; `std::vector<unsigned int> rekey(unsigned int chamber_count, const std::vector<unsigned int>& boats, unsigned int gate_count);` throws as usual.
- Prompt shape: two-turn repair. Seeded turn 1 declares `rekey(const std::vector<unsigned int>& boats, unsigned int chamber_count, unsigned int gate_count)` (digits first). Turn 2 shows gcc output: `error: invalid initialization of reference of type 'const std::vector<unsigned int>&' from expression of type 'int'` at the test's call sites.
- Target capability: G2+G1 — read argument-order compile errors, swap the signature in BOTH files, emit whole files.
- Target answer shape: corrected order in header and definition; call-free explanation of one sentence.
- Difficulty / variation: replays the round-3 success so it becomes reliable, not lucky.

### Spec 22: sentinel-to-throw-repair
- Files: `aqueduct_arches.cpp`, `aqueduct_arches.h` (test file: `aqueduct_arches_test.cpp`)
- API: namespace `aqua`; `std::vector<unsigned int> respan(unsigned int arch_span, const std::vector<unsigned int>& piers, unsigned int channel_span);` throws `std::invalid_argument` on span < 2 or pier >= arch_span.
- Prompt shape: two-turn repair. Seeded turn 1 validates with `return {};`. Turn 2 shows Catch2 `REQUIRE_THROWS_AS` failures AND the test source line containing `std::invalid_argument`.
- Target capability: G6 — extract the exception type named in visible test output and apply it, the exact move missed in round 3 (shard lines 8287-8290).
- Target answer shape: guard clauses now throw; zero/empty behavior untouched; whole files.
- Difficulty / variation: error output mixes compile notes and runtime failures; model must fix the runtime contract, not just what failed to compile.

### Spec 23: sentinel-vs-exception-contrast (contrastive)
- Files: `observatory_dome.cpp`, `observatory_dome.h` (test file: `observatory_dome_test.cpp`)
- API: namespace `dome`; `std::vector<unsigned int> reslot(unsigned int sky_sectors, const std::vector<unsigned int>& stars, unsigned int dome_slots);` throws `std::invalid_argument` on sector < 2 or star >= sky_sectors.
- Prompt shape: prompt includes a "common mistake" note: an earlier intern returned an empty list for invalid sector counts and the observatory's tests rejected it; implement the throwing policy.
- Target capability: G3 — contrastive: sentinel-return vs exception-throw for invalid arguments; the row pairs the wrong and right shapes in the prompt.
- Target answer shape: throwing guards; no empty-return validation path.
- Difficulty / variation: explicitly names the anti-pattern in prose, training recognition of the policy fork.

### Spec 24: zero-digit-vs-empty-contrast (contrastive)
- Files: `abacus_rows.cpp`, `abacus_rows.h` (test file: `abacus_rows_test.cpp`)
- API: namespace `abacus`; `std::vector<unsigned int> rethread(unsigned int rods_in, const std::vector<unsigned int>& beads, unsigned int rods_out);` zero beads total -> empty vector; throws as usual.
- Prompt shape: prompt contrasts two shops: one represents "no beads" as a single zero bead, the target shop represents it as an empty row list; implement the target shop's rule.
- Target capability: G4 — contrastive: `{0}` vs `{}` representation of zero value.
- Target answer shape: emit loop only; no zero special case.
- Difficulty / variation: the representation rule is stated as a shop convention, not a math fact, teaching convention-following over assumption.

### Spec 25: no-elision-long-file
- Files: `observatory_log.cpp`, `observatory_log.h` (test file: `observatory_log_test.cpp`)
- API: namespace `stargaze`; two functions: `std::vector<unsigned int> rescale_magnitudes(unsigned int in_scale, const std::vector<unsigned int>& mags, unsigned int out_scale);` and `unsigned int total_magnitude(const std::vector<unsigned int>& mags, unsigned int scale);` first throws as usual, second never throws.
- Prompt shape: astronomy club re-scales its observation log; stubs; solution requires ~70 lines in the `.cpp`.
- Target capability: G1 — long whole-file emission with zero elision; the two-function file tempts `// ... rest unchanged`.
- Target answer shape: both functions fully defined; no comment placeholders.
- Difficulty / variation: length pressure on the format contract.

### Spec 26: plain-fence-discipline
- Files: `greenhouse_vents.cpp`, `greenhouse_vents.h` (test file: `greenhouse_vents_test.cpp`)
- API: namespace `greenhouse`; `std::vector<unsigned int> relouver(unsigned int vent_stops, const std::vector<unsigned int>& settings, unsigned int motor_stops);` throws as usual.
- Prompt shape: system prompt repeats the whole-file listing rules verbatim and adds "do not use diff format"; stubs.
- Target capability: G1 — plain triple-backtick fences with no language tag like `diff`; filename alone on the listing's first line.
- Target answer shape: `greenhouse_vents.h` then a bare fence; same for `.cpp`; no `@@` hunks anywhere.
- Difficulty / variation: fence-syntax-only drill; story is trivial.

### Spec 27: guard-namespace-consistency
- Files: `fountain_jets.cpp`, `fountain_jets.h` (test file: `fountain_jets_test.cpp`)
- API: namespace `fountain`; `std::vector<unsigned int> rejet(unsigned int pump_levels, const std::vector<unsigned int>& jets, unsigned int nozzle_levels);` throws as usual.
- Prompt shape: starter files already contain include guards (`#if !defined(...)`) and an empty namespace; model must preserve both exactly, including the `#endif // NAME` comment style and the trailing newline.
- Target capability: G2 — non-destructive editing of boilerplate: guards, namespace wrapper, and file terminator survive unchanged (the observed hunk mangle at source line 732 ate the header's last line).
- Target answer shape: diff of starter vs answer touches only added lines inside the namespace; final line is `#endif // FOUNTAIN_JETS_H` followed by a newline.
- Difficulty / variation: file-hygiene micro-drill.

### Spec 28: unsigned-accumulator-overflow
- Files: `granary_silos.cpp`, `granary_silos.h` (test file: `granary_silos_test.cpp`)
- API: namespace `granary`; `std::vector<unsigned int> rebucket(unsigned int bin_base, const std::vector<unsigned int>& scoops, unsigned int silo_base);` throws as usual; intermediate value uses `unsigned long long` to survive 15-digit inputs.
- Prompt shape: grain elevator re-buckets scoop counts; prompt warns some tallies are large; stubs.
- Target capability: G4 — choose a wide enough accumulator and reason about overflow, instead of the observed bare `unsigned int decimal_value` (source lines 663-666).
- Target answer shape: accumulator type named and justified in one comment; modulo/division in the wider type, digits cast back on emission.
- Difficulty / variation: advanced edge case; tests include a 12-digit base-60 input.

### Spec 29: mine-the-error-output
- Files: `clockwork_escapement.cpp`, `clockwork_escapement.h` (test file: `clockwork_escapement_test.cpp`)
- API: namespace `clockwork`; `std::vector<unsigned int> retick(unsigned int escape_teeth, const std::vector<unsigned int>& ticks, unsigned int pendulum_beats);` throws `std::invalid_argument` on teeth/beats < 2 or tick >= escape_teeth.
- Prompt shape: two-turn repair. Turn 2 shows compiler output in which the test's `REQUIRE_THROWS_AS(retick(1, ticks, 60), std::invalid_argument)` line appears inside the error text (because the seeded turn 1 also has an argument-order bug). The model must fix BOTH the order and the exception policy.
- Target capability: G6 — mine every contract signal in quoted error output, not just the one that caused the compile error.
- Target answer shape: base-first throwing implementation; answer prose lists both fixes.
- Difficulty / variation: composite repair; the highest-value replay of the actual round-3 miss.

### Spec 30: never-empty-answer
- Files: `windmill_sails.cpp`, `windmill_sails.h` (test file: `windmill_sails_test.cpp`)
- API: namespace `windmill`; `std::vector<unsigned int> rerig(unsigned int sail_notches, const std::vector<unsigned int>& settings, unsigned int brake_notches);` throws as usual.
- Prompt shape: two-turn repair. Seeded turn 1 is fully correct. Turn 2 prompt: "# Fix any errors below, if possible." with a █-marked snippet and no message.
- Target capability: G1+G5 — when the honest conclusion is "no errors", the answer still re-emits the complete current files (whole-file contract) instead of an empty fence or prose-only reply.
- Target answer shape: one sentence ("no errors found; current files re-listed for confirmation") plus both full listings.
- Difficulty / variation: teaches the no-op-repair terminal behavior that would have saved rounds 2, 4, 5 and 6.

Gap coverage check: G1 — Specs 01, 02, 03, 25, 26, 30; G2 — Specs 04, 05, 06, 07, 08, 21, 27; G3 — Specs 09, 10, 11, 12, 22, 23; G4 — Specs 13, 14, 15, 16, 17, 18, 19, 24, 28; G5 — Specs 03, 20, 30; G6 — Specs 12, 22, 29. Required mix: format-contract 01/02/25/26 (>=2), header/impl 04/05/27 (>=2), exception-policy 09/10/11 (>=2), edge cases 13-17, 19, 28 (>=3), repair 03/12/20/21/22/29/30 (>=2), contrastive 08/23/24 (>=1). Every gap covered at least twice; all 30 story wrappers distinct.

## 6. Acceptance & Validation Gates

Rows built from these specs enter training only if all of the following hold:

1. **Parser validity:** the target answer parses under the Aider whole-file listing
   grammar — each changed file is `filename\n```` ... entire content ... `\n```` with no
   diff hunks, no language tags that change semantics, no elision comments, and no empty
   fences. An automated check rejects any answer whose fence body is empty or whose
   filename line carries extra markup.
2. **Compile + test receipts:** the listed files are written to a scratch copy of the
   synthetic exercise and must compile with the same toolchain flags as the benchmark
   (C++17, `-Wall`) and pass the synthetic `*_test.cpp` under Catch2. The receipt
   (command + exit code) is stored with the row.
3. **Hidden-edge coverage:** each synthetic test file must include the edge cases its
   spec names (zero-value -> empty, empty input, leading zeros, radix < 2 throw,
   digit >= radix throw, guard ordering where specified) so a sentinel-return or
   `{0}`-for-zero solution provably fails validation.
4. **Contamination check:** prompt text, story nouns, function names, and test data must
   not collide with `polyglot-benchmark` content; an automated similarity scan against
   the benchmark checkout (filenames, identifiers, instruction text) must pass. The
   reference `.meta/example.*` may calibrate API shapes abstractly but no reference line
   may appear in a row.
5. **Whole-file output rule:** for repair specs, both turns' answers must be complete
   listings; a turn-2 answer that only describes the fix or emits an empty fence fails
   the row.
6. **Format-failure negative sampling:** contrastive rows (Specs 08, 23, 24) are only
   valid if the "wrong" variant demonstrably fails the synthetic tests and the "right"
   variant passes, so the pair teaches a real distinction.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the shard-0 raw log, and
ground truth:

- Re-read every cited failure-log range: section header lines 186-192 (shard 0,
  `[False, False]`, FAIL — matches run summary), attempt-1 chunk header at line 236
  ("source lines 458-816"), attempt-2 chunk header at line 600 ("source lines
  4357-4761"), terminal test log lines 825-1335 with result JSON at source lines
  20772-20826 (`tests_outcomes [false, false]`, `num_user_asks 6`,
  `num_malformed_responses 0`). Verified.
- Re-verified attempt-1 quotes: "```diff" fence at source line 718; mangled
  `#endif` hunk line at source line 732; digits-first signature at source lines 746-747;
  `return {};` guards at source lines 749-751 and 758-763; `return {0};` at source lines
  771-774; thinking assumptions at source lines 489-490 and 502; "Applied edit" at
  source lines 793-795. Verified against `sed -n '236,580p'` of the failure log.
- Re-verified retry quotes: content-free █ prompt at source lines 797-808; empty-diff
  answer at source lines 4732-4736; "Applied edit to all_your_base.h" at source line
  4740; false-memory claim at source lines 4419-4421; "code is valid ... unchanged"
  conclusion at source lines 4687-4688. Verified.
- Re-verified shard-0 raw-log citations: compile error `invalid initialization of
  reference ... from expression of type 'int'` at line 7800 and the `note:` at line
  7804; round-3 thinking quoting `all_your_base_test.cpp:112` `REQUIRE_THROWS_AS` at
  lines 8287-8290; applied edits at lines 793-794, 4738, 8449-8450, 13196-13197, 13817,
  19789-19790 (six answers, consistent with `num_user_asks: 6`). Verified.
- Re-verified terminal failures: `{  } == { 0 }` expansions at source lines 20695-20698
  and 20706-20909 range (single_zero 20695-20698, multiple_zeros 20706-20709); the five
  "no exception was thrown" failures at source lines 20717-20759; summary
  `17 | 10 passed | 7 failed` at source lines 20762-20763. Verified.
- Re-checked every API claim against `.meta/example.h` (lines 4, 6, 8-10),
  `.meta/example.cpp` (lines 3, 12-18, 21-25) and `all_your_base_test.cpp` (lines 1, 15,
  69-75, 77-83, 85-99, 101-107, 109-137). Verified: signature, namespace, throw
  conditions, empty-input return, zero -> empty semantics, and guard ordering
  (base check precedes empty check) all match section 2.
- Corrections made during cross-check: (a) initial draft attributed the empty-diff
  answers to "4 of 6 rounds"; corrected to "4 of 5 retry rounds" (attempt 1 used
  non-empty diff hunks; rounds 2, 4, 5, 6 emitted empty fences; round 3 emitted non-empty
  hunks). (b) Initial draft said the round-3 prompt "was shown in the failure log"; the
  failure log excerpts only rounds 1-2, so round-3/4/5/6 evidence was re-cited to the
  shard-0 raw log line numbers. (c) Fixed a transposed line range for the
  `multiple_zeros` expansion (source lines 20706-20709, not 20700-20704, which is the
  test-case header).
- Ground-truth status: `.meta/example.h` / `.meta/example.cpp` present and self-
  consistent with the test file; no fallback to starter files was needed; no
  ground-truth problem encountered.
