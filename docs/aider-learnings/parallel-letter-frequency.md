# Aider Learning Document: parallel-letter-frequency

## 1. Task Identity & Evidence Pointers

- Task slug: `parallel-letter-frequency`
- Run: `glm47-aider-expansion-sft-fixed26-20260723T091839Z`, model `openai/glm-4.7-flash-sft`, `edit_format: whole`
- Shard: `1` (failure log line 62293)
- Outcome array: `[False, False]` (failure log line 62295); `Result: FAIL` (line 62296)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines 62291-63589
  - Section header: lines 62291-62296
  - Reconstructed prompt messages: lines 62298-62337
  - Attempt/log chunk 1 (source lines 2654-3290): line 62341 — mostly bleed-over from the previous task (`perfect-numbers`); the `parallel-letter-frequency` aider session banner starts at source line 3278 (failure log 62968, banner content 3278-3290 = failure log 62968-62980)
  - Attempt/log chunk 2 (source lines 4415-4833): line 62983 — the actual attempt-1 thinking + answer + first lint-reflection prompt
  - Terminal test log (source lines 53471-53646): line 63407
  - Result JSON: source lines 53596-53646 (failure log lines 63537-63587) — `tests_outcomes: [false, false]` (failure log 63542-63545), `num_user_asks: 6`, `num_exhausted_context_windows: 1`, `num_malformed_responses: 0`, `prompt_tokens: 17958`, `completion_tokens: 23476` (failure log 63558-63559)
- Raw shard log cross-check: `...-shard-1/benchmark.log` (13 tasks interleaved; this task's lines identified by `parallel_letter_frequency` / `parallel-letter-frequency` matches)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/parallel-letter-frequency/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/parallel-letter-frequency/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/parallel-letter-frequency/parallel_letter_frequency_test.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/parallel-letter-frequency/CMakeLists.txt`
- Existing analog dir: none (the seven `aider-fixed26-analogs/fixed26-bNNN-*` dirs do not include this task)

## 2. Benchmark Contract (Ground Truth)

File set: `parallel_letter_frequency.h` + `parallel_letter_frequency.cpp` (both editable; test file is injected by the harness). C++17 (`CMakeLists.txt:39` — `CXX_STANDARD 17`).

Public API (`.meta/example.h:8-13`):

```cpp
namespace parallel_letter_frequency {

[[nodiscard]] std::unordered_map<char, size_t> frequency(
    std::vector<std::string_view> const& texts);

}
```

Enforced by the test file:

- **Function name and namespace**: every test case calls `parallel_letter_frequency::frequency(texts)` — e.g. `parallel_letter_frequency_test.cpp:18`, `:28`, `:37`, `:49`, `:60`, `:72`, `:83`, `:92`, `:101`, `:116`, and the benchmark cases at `:411` and `:451` (12 call sites, all visible in the terminal compile errors, shard-log source lines 53504-53587).
- **Parameter type**: every call site passes `std::vector<std::string_view> const texts` (test line 17 and repeated at each case). A parameter of type `const std::vector<std::string>&` does NOT compile — `std::vector<std::string_view>` is not convertible to it (terminal error, source line 53504).
- **Return type is only loosely constrained**: tests use `auto freqs = ...`, `freqs.empty()` (test line 19), and `freqs['a'] == 1`-style `operator[]` lookups against int literals (test lines 28-29, 63, 131-138, etc.). `std::map<char, int>` would satisfy the test; `std::unordered_map<char, size_t>` is the reference choice. The return type was NOT a failure driver here.
- **Semantics** (`.meta/example.cpp:18-47`):
  - Empty input vector → empty map (test lines 15-19).
  - Case-insensitive counting via `std::tolower` on `unsigned char` (test lines 66-73: `"m","M"` → `freqs['m'] == 2` at line 73).
  - Non-letters ignored: whitespace-only texts → empty map (test lines 76-84), punctuation → empty (lines 87-93), digits → empty (lines 96-102).
  - Counts accumulate across a long mixed-case text with punctuation (test lines 105-138, e.g. `freqs['a'] == 32` at line 117), large texts (test lines 141-438, counts up to 1143 at line 416), and many small texts (lines 439-457, `"abbccc"` x50 → `freqs['c'] == 150`).
- **Parallelism expectation**: instructions ask for parallel computation; reference uses `std::transform` with `std::execution::par_unseq` guarded by an Apple-Clang `#ifdef` (`.meta/example.cpp:6-12, 35-36`), with a sequential merge (lines 38-44). The tests do not verify parallelism — any correct sequential implementation passes.
- **Exception policy**: none. No throw requirements anywhere in the test file.
- **Starter state given to the model**: both files contain an empty `namespace parallel_letter_frequency {}` (failure log lines 62316-62329), so the entire public API had to be invented by the model.

## 3. Failure Anatomy

### Attempt 1 (initial answer)

Model thinking (shard-log source lines 4415-4731, failure log chunk 2 starting line 62983) explicitly guessed the API from the task name:

- source lines 4466-4469: "The user didn't provide a signature in the empty files, but the exercise name is `parallel_letter_frequency`. Usually, it's `std::map<char, int> parallel_letter_frequency(const std::vector<std::string>& texts)`."
- source lines 4491-4494 settle on a helper plus `std::map<char, int> parallel_letter_frequency(const std::vector<std::string>& texts)`.

The emitted answer (source lines 4734-4807, failure log lines 63305-63378):

- **Wrong function name**: `+std::map<char, int> parallel_letter_frequency(const std::vector<std::string>& texts)` in both the `.cpp` diff (source lines 4749-4750, failure log lines 63320-63321) and the `.h` diff (source lines 4800-4801, failure log lines 63371-63372). A function named identically to its enclosing namespace is also ill-formed C++, and it is not the `frequency` name the tests call.
- **Wrong parameter type**: `const std::vector<std::string>&` instead of `const std::vector<std::string_view>&`.
- **Wrong output format**: both files were emitted as unified diffs inside ```` ```diff ```` fences (source lines 4738-4739: ```` ```diff ```` / `@@ -1,5 +1,39 @@`; source lines 4788-4789 for the header) despite the system prompt's whole-file listing contract and `edit_format: whole`. Aider nevertheless applied them ("Applied edit to parallel_letter_frequency.cpp/.h", source lines 4811-4812, failure log lines 63382-63383).
- **Latent include error (inference, never surfaced)**: thinking at source lines 4721-4722 asserts "`std::transform_reduce` with `std::execution::par` requires `<execution>`? No, it's included in `<algorithm>` in C++17." Both claims are wrong (`transform_reduce` lives in `<numeric>`; policies in `<execution>`). Compilation never reached these errors because the test TU failed first.

Aider's lint reflection then sent "# Fix any errors below, if possible." with only a █ marker on header line 10 and **no diagnostic text** (source lines 4814-4833, failure log lines 63385-63406: `10█std::map<char, int> parallel_letter_frequency(const ...`).

### Attempt-1 repair spiral (still before test run 1)

- The model could not derive the error from a bare marker and entered a degenerate repetition loop: "Wait, I see the error marker again. ... Maybe the error is that the function should be `... texts) const;`? ... I will output the header file." repeated hundreds of times (shard log lines ~31700-35183; sampled at lines 31896-31929). The phrase "I will output the header file" appears 537 times across the shard log, the bulk from this loop.
- It hallucinated impossible fixes, e.g. adding `const` to a free function signature (shard log line ~31900).
- Three "Model openai/glm-4.7-flash-sft has hit a token limit!" events with empty ANSWER sections (shard log lines 28835, 35208, 49663); the run JSON records `num_exhausted_context_windows: 1` (failure log line 63552) and 23476 completion tokens.
- When it did answer, it emitted **empty ```` ```diff ```` blocks** — no-op edits that aider "applied" (shard log lines 40319-40340: ```` ```diff ```` with no content, then "Tokens: 4.0k sent, 5.6k received. / Applied edit to parallel_letter_frequency.cpp / Applied edit to parallel_letter_frequency.h"; same pattern again at lines 43138-43140).

### Test run 1 (end of attempt 1)

- source lines 35268-35270: `parallel_letter_frequency_test.cpp:18:45: error: 'frequency' is not a member of 'parallel_letter_frequency'` — repeated for all 12 call sites (source lines 35268-35360). The old function name still stood, and the name error masked the parameter-type mismatch (overload resolution never happened).

### Attempt 2 (retry with test output)

- The model correctly diagnosed the naming error (shard log lines 37029-37106: "The test file `parallel_letter_frequency_test.cpp` is calling `parallel_letter_frequency::frequency(...)`, but my previous implementation [named it] `parallel_letter_frequency::parallel_letter_frequency(...)` ... *Decision:* Rename the function `parallel_letter_frequency` to `frequency`") and applied the rename (shard log lines 37265-37266).
- **But it kept `const std::vector<std::string>&`** — the very next reflection prompt shows the new header line 10: `10█std::map<char, int> frequency(const std::vector<std::string>& texts);` (shard log lines 37268-37280).
- Further █-marker reflections (again with no diagnostic text) sent it back into confused loops, now hallucinating the *stale* previous error: "`parallel_letter_frequency.h:10: ... error: 'frequency' is not a member of 'parallel_letter_frequency'`" (shard log lines 39867-39868), followed by more empty-diff no-ops (shard log lines 40338-40340, 43138-43140).

### Test run 2 (terminal)

- 12 compile errors, all the same root cause (source lines 53503-53587): `error: invalid initialization of reference of type 'const std::vector<std::__cxx11::basic_string<char> >&' from expression of type 'const std::vector<std::basic_string_view<char> >'` at every call site, with `parallel_letter_frequency.h:10:63: note: in passing argument 1 of 'std::map<char, int> parallel_letter_frequency::frequency(const std::vector<...basic_string<char> >&)'` (source lines 53504-53510).
- `make` fails (source lines 53588-53590); result JSON `tests_outcomes: [false, false]` (failure log lines 63544-63547).

### Hard evidence vs inference

- **Hard evidence**: wrong invented name (source lines 4749-4750, 4800-4801); diff-fence format (source lines 4738-4739, 4788-4789); bare-marker reflection prompts (source lines 4814-4833, 37268-37280); repetition loop (lines 31896-31929); empty-diff no-ops (lines 40319-40340); token-limit events (lines 28835, 35208, 49663); test-run-1 name errors (35268-35270); test-run-2 string_view errors (53504-53587); result JSON (failure log 63539-63554).
- **Inference**: (a) root cause of both test failures is the invented API (`parallel_letter_frequency`/`std::string`) vs the canonical contract (`frequency`/`std::string_view`) — strongly supported by compiler output; (b) the model could not recover from diagnostic-free █ reflections, which converted a one-line fix into a 20k-token loop; (c) `<numeric>`/`<execution>` includes would have been the next compile failure had the name/type been right — plausible but unverified.

## 4. Knowledge / Capability Gaps

- **G1 — Canonical-contract inference from empty starters.** When starter files contain only an empty namespace, the public API must be inferred from exercism-cpp conventions: a short verb/noun function name (`frequency`), not the task slug reused as a function name. Evidence: source lines 4466-4469 (guess), 35269 (name error).
- **G2 — C++ name-hiding rule: function name == enclosing namespace name is ill-formed.** The model declared `parallel_letter_frequency::parallel_letter_frequency(...)` and never recognized the problem even with line 10 flagged; it wondered "Is it possible the namespace is wrong?" (shard log line ~30915) instead of seeing the collision. Evidence: source lines 4749, 4814-4833.
- **G3 — Modern C++ read-only string parameter idiom: `std::string_view`.** The canonical contract takes `std::vector<std::string_view>`; the model chose `std::vector<std::string>` and never revised it even on retry, because test-run-1's name error masked the type error. Evidence: source lines 37278 (kept `std::string` after rename), 53504-53587 (terminal type errors).
- **G4 — Whole-file listing format compliance.** Emitted ```` ```diff ```` unified diffs under `edit_format: whole`, and later emitted *empty* ```` ```diff ```` blocks as no-op answers instead of either a real fix or an explicit "no changes" statement. Evidence: source lines 4738-4739, 4788-4789, 40319-40340, 43138-43140.
- **G5 — Repair behavior under underspecified diagnostics.** Given a █-marked line with no message, the model must enumerate concrete plausible causes (name collision? missing include? const/ref mismatch?) and commit to the most likely real change. Instead it looped on cosmetic hypotheses (`inline`? `static`? `extern "C"`? `throw()`? trailing `const`?) and repeated itself hundreds of times. Evidence: source lines 31896-31929, 39867-39868.
- **G6 — Context/output budgeting.** Repetitive thinking burned the completion budget: 3 token-limit blowouts (source lines 28835, 35208, 49663), 1 exhausted context window, 23.5k completion tokens for a ~40-line solution. Evidence: failure log lines 63552-63561.
- **G7 — Include/idiom correctness for parallel algorithms.** `std::transform_reduce` needs `<numeric>`; execution policies need `<execution>`. Model asserted the opposite (source lines 4721-4722). Latent for this run but a real knowledge gap in the target domain of the exercise.
