# bank-account — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `bank-account`
- Shard: `0` (failure log section header, line 2939: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 2941; terminal JSON `tests_outcomes: [false, false]`, failure log lines 4220-4223 / raw shard-0 lines 47985-47988)
- Result: `FAIL` (failure log line 2942)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **2937-4267**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log` (bank-account run spans source lines ~104-48030; interleaved with concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/bank-account/.meta/example.h`
  - `polyglot-benchmark/cpp/exercises/practice/bank-account/.meta/example.cpp`
  - `polyglot-benchmark/cpp/exercises/practice/bank-account/bank_account_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Interleaved bleed.** dnd-character FAILED assertions appear at failure log 3806-3893 (source 4219-4306), and a full *gigasecond* rename answer (`DateTime add` → `advance`) at failure log 4042-4071 (source 47807-47856) — both foreign-task bleed inside the bank-account section, not bank-account model output.
2. **Failure log omits attempt 2.** The log excerpts end at source 4356 and resume at the terminal block (failure log 3946, source 47885+). The attempt-1 test failure and the attempt-2 repair turns exist only in the raw shard-0 log and are cited as "shard-0 line N".
3. **Citation scheme.** Failure-log lines carry the log's raw-shard source-line prefixes; raw shard-0 lines are labeled "shard-0".

## 2. Benchmark Contract (Ground Truth)

File set: `bank_account.h` + `bank_account.cpp`, namespace `Bankaccount`, class `Bankaccount` (example.h:6-7; the starter already declares `class Bankaccount {};`).

Public API (`.meta/example.h:9-13`), all enforced by `bank_account_test.cpp`:

- `void open();` — test: `account.open();` (bank_account_test.cpp:13, 20, ...).
- `void deposit(int amount);` / `void withdraw(int amount);` — int amounts (example.h:10-11).
- `void close();`
- `int balance();` — a **method named exactly `balance`** (example.h:13), called as `account.balance()` (test:14).

State-machine + exception policy (`.meta/example.cpp`), all throwing `std::runtime_error`:

- The account **starts unopened**: `bool open_{false};` (example.h:20). Deposit into an unopened account throws (example.cpp:16 → check at 46-50; test:77-79 "Cannot deposit into unopened account"), and closing an unopened account throws (example.cpp:35-38; test:90-93).
- `open()` on an already-open account throws `"account already open"` (example.cpp:6-9; test:96-100).
- `open()` **resets the balance to 0** — a reopened account does not retain its old balance (example.cpp:11; test:104-111 `REQUIRE(account.balance() == 0)`).
- `deposit`/`withdraw` validate the amount: negative amounts throw `"amount must be greater than 0"` (example.cpp:52-56; test:122-126 "Cannot withdraw negative", 129-133 "Cannot deposit negative").
- `withdraw` beyond the balance throws (example.cpp:28-31; test:114-119).
- `balance()` throws when the account is not open (example.cpp:40-44; test:61-66 "annot check balance of closed account").
- Concurrency: deposit/withdraw/balance lock a mutex (`std::mutex mutex_{};` example.h:21; `std::lock_guard` example.cpp:15, 23, 41); the test spawns threads doing concurrent deposits (bank_account_test.cpp:136-151, `#include <thread>` at :9).

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: missing `open()`, member/method name collision)

**What the model emitted.** A **diff-hunk answer** under `edit_format: whole` (failure log 3228-3312, source 342-426): header adds `<mutex>`, `<stdexcept>`, and a class with `Bankaccount(); void close(); void deposit(double amount); void withdraw(double amount); double get_balance();` plus private `double balance; bool isOpen; mutable std::mutex mtx;` (failure log 3244-3255, source 358-369). The diff contains two mangled merge lines from newline-less starter files: `-#endif  // BANK_ACCOUNT_H+private:` (failure log 3252, source 366) and `-namespace Bankaccount {}+namespace Bankaccount {` (failure log 3273, source 387). Applied (failure log 3311-3312, source 425-426).

**The defects.** (a) No `open()` — the model made the constructor open the account (`Bankaccount::Bankaccount() : balance(0.0), isOpen(true) {}`, failure log 3275, source 389), inventing an auto-open lifecycle. (b) The accessor is named `get_balance()` while the test calls `account.balance()`. (c) The private member is named `balance`, colliding with the required method name. (d) No negative-amount validation, no double-open check, no balance reset — but those were latent; attempt 1 failed earlier, at compile time.

**Reflection turns.** Three `# Fix any errors below` █ prompts (marker on the `mutable std::mutex mtx;` line, failure log 3334, source 448) drew **empty ```` ```diff ```` fences** (failure log 3727-3742, source 4140-4154; applied as no-ops, failure log 3745-3746; further no-op applies at shard-0 6221-6222, 8791-8792; "Only 3 reflections allowed, stopping." shard-0 8822).

**Test run 1 — compile failure** (shard-0 8925-9276): `error: 'class Bankaccount::Bankaccount' has no member named 'open'; did you mean 'bool Bankaccount::Bankaccount::isOpen'?` at `account.open();` (shard-0 8925-8930, quoting bank_account_test.cpp:13) and `error: 'double Bankaccount::Bankaccount::balance' is private within this context` / `expression cannot be used as a function` at `REQUIRE(account.balance() == 0);` (shard-0 8936-8946, quoting test:14). `Tests failed: .../bank-account` (shard-0 9276).

### Attempt 2 (retry with compiler output) — outcome False (runtime failures: state-machine semantics)

**What the retry changed.** The repair turn diagnosed the signature mismatch correctly (shard-0 12380-12384: "The tests use `open()` and `balance()`... Renaming `get_balance` to `balance` is the most direct fix") and emitted a diff (shard-0 12417-12509) that: added `void open();`, renamed `get_balance()` → `double balance() const`, renamed the member `balance` → `m_balance`, made `balance()` throw when closed, and added `open()` — **but as a bare `isOpen = true;`**: no already-open check, no balance reset, and the constructor still auto-opens (`Bankaccount::Bankaccount() : m_balance(0.0), isOpen(true) {}`, shard-0 12446). Applied at shard-0 12508-12509. Still diff format. No negative-amount validation was added.

**Terminal result — compiles, 6 of 17 runtime assertions fail** (failure log 4140-4212, source 47905-47977):

- `Cannot deposit into unopened account`: `REQUIRE_THROWS_AS(account.deposit(50), std::runtime_error)` — "no exception was thrown" (failure log 4149-4151, source 47914-47916; test:77-79) because the constructor auto-opens.
- `Cannot close an account that was not opened`: close on unopened didn't throw (failure log 4159-4161, source 47924-47926; test:90-93) — same root cause.
- `Cannot open an already opened account`: `open()` has no guard (failure log 4169-4171, source 47934-47936; test:96-100).
- `Reopened account does not retain balance`: `REQUIRE(account.balance() == 0)` expanded to `50.0 == 0` (failure log 4179-4182, source 47944-47947; test:104-111) — `open()` never resets.
- `Cannot withdraw negative` / `Cannot deposit negative`: no amount validation (failure log 4190-4202, source 47955-47967; test:122-133).

`test cases: 17 | 11 passed | 6 failed` (failure log 4205-4206, source 47970-47971); `Tests failed: .../bank-account` (failure log 4212, source 47977); JSON `tests_outcomes: [false, false]` (failure log 4220-4223). Notably the concurrency test passed — the mutex handling was fine.

### Hard evidence vs inference

- Hard evidence: diff-format answers (failure log 3232-3235, 3727-3742), missing `open()` + `get_balance` + member-name collision (failure log 3246-3257), attempt-1 compile errors (shard-0 8925-8946), attempt-2 signature fix retaining auto-open ctor and guardless `open()` (shard-0 12417-12509), six terminal runtime failures (failure log 4149-4202).
- Inference: attempt 1's root cause is lifecycle invention — the model designed the "obvious" account (open at construction, getter accessor) instead of the exercism-cpp contract (explicit `open()`, `balance()` method), and picked a member name (`balance`) that collided with the required method. Attempt 2 shows strong signature-level repair (all compile errors fixed in one turn) but weak semantic repair: the model treated the `REQUIRE_THROWS_AS` cases visible in the test-quoting error output as satisfied by its existing closed-account checks, never re-deriving the full state machine (start-unopened, double-open throw, reopen reset, negative-amount throw). The runtime failures are all "missing guard clause" defects — a systematic under-validation gap, not isolated oversights.

## 4. Knowledge / Capability Gaps

- **G1 — Canonical API surface for stateful exercism classes.** Explicit `open()`/`close()` lifecycle and a noun-named accessor `balance()` (not `get_balance()`) were invented away (failure log 3244-3255), costing attempt 1 (shard-0 8925-8946).
- **G2 — Member/method namespace collision awareness.** A data member and a member function cannot share the name `balance`; the model shipped exactly that (failure log 3253-3254, source 367-368) and needed compiler feedback (shard-0 8936-8946) plus a rename (`m_balance`, shard-0 12436) to escape.
- **G3 — State-machine completeness (guard clauses).** Six failing behaviors are all missing guards: start-unopened (ctor sets `isOpen(true)`, shard-0 12446), double-open check, reopen-resets-balance, negative-amount validation (failure log 4149-4202). The model validates the transitions it thought of and never enumerates the full transition×state matrix.
- **G4 — Exception policy fidelity.** Every guard throws `std::runtime_error` (test uses `REQUIRE_THROWS_AS(..., std::runtime_error)` throughout, failure log 4150/4160/4170); the model got the type right where it guarded but missed most guard sites.
- **G5 — Whole-file format contract.** All substantive answers were ```` ```diff ```` hunks (failure log 3232, 3727-3742; shard-0 12417+), including two mangled merge lines (failure log 3252, 3273); reflection turns produced empty-diff no-ops.
- **G6 — Mining test-quoting error output for semantics.** The attempt-1 error output quoted the test file's call shapes; attempt 2 used it for signatures but not for the *behavioral* requirements (`REQUIRE_THROWS_AS` cases), a selective-reading gap.

## 5. SFT Task Specifications (24 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-coffee-punch-card
- Files: punch_card.cpp, punch_card.h (test file: punch_card_test.cpp)
- API: namespace `cafe`; `class card { public: void stamp(); int stamps() const; };`
- Prompt shape: loyalty punch card; starter guard + empty namespace; whole-file instruction prominent.
- Target capability: G5 — complete whole-file listings only.
- Target answer shape: two whole-file listings; no diff fences.
- Difficulty / variation: minimal; format-only trap.

### Spec 02: noun-accessor-not-getter-thermostat
- Files: thermostat.cpp, thermostat.h (test file: thermostat_test.cpp)
- API: namespace `home`; `class thermostat { public: void set(int celsius); int temperature() const; };`
- Prompt shape: smart-home thermostat; hidden tests call `temperature()`, never `get_temperature()`.
- Target capability: G1 — noun-named accessors matching the contract; resist getter-prefix habit.
- Target answer shape: `int temperature() const;` exactly.
- Difficulty / variation: accessor-naming prior.

### Spec 03: explicit-lifecycle-gym-locker
- Files: locker.cpp, locker.h (test file: locker_test.cpp)
- API: namespace `gym`; `class locker { public: void assign(); void release(); bool assigned() const; };`
- Prompt shape: gym locker allocation; object starts unassigned; `assign()`/`release()` explicit.
- Target capability: G1 — explicit lifecycle methods instead of constructor-side effects.
- Target answer shape: ctor initializes "free" state only.
- Difficulty / variation: lifecycle prior, boolean-state simplicity.

### Spec 04: member-method-collision-toll-booth
- Files: booth.cpp, booth.h (test file: booth_test.cpp)
- API: namespace `tollway`; `class booth { public: void record(int cents); int total(); };`
- Prompt shape: toll booth revenue; the natural member name `total` collides with the method `total()`; spec requires distinct member naming convention.
- Target capability: G2 — never name a data member identically to a member function; use `total_`/`m_total`.
- Target answer shape: trailing-underscore member convention; compiles with method of the noun name.
- Difficulty / variation: collision-avoidance discipline.

### Spec 05: guard-matrix-state-machine-vending
- Files: vending.cpp, vending.h (test file: vending_test.cpp)
- API: namespace `snacks`; `class machine { public: void stock(); void vend(); void service(); int inventory(); };` with a full state×operation throw matrix (unstocked/servicing states).
- Prompt shape: vending machine with an explicit state chart described in prose.
- Target capability: G3 — enumerate every (state, operation) pair and implement a guard for each invalid one.
- Target answer shape: guard clause first in every public method; no transition left implicit.
- Difficulty / variation: systematic state-machine coverage.

### Spec 06: runtime-error-policy-parking-meter
- Files: meter.cpp, meter.h (test file: meter_test.cpp)
- API: namespace `parking`; `class meter { public: void activate(); void pay(int cents); void expire(); int remaining(); };` all invalid operations throw `std::runtime_error`.
- Prompt shape: parking meter; hidden tests use `REQUIRE_THROWS_AS(..., std::runtime_error)` exclusively.
- Target capability: G4 — consistent `std::runtime_error` (not `logic_error`, not custom) + `<stdexcept>` include.
- Target answer shape: uniform exception type at all guard sites.
- Difficulty / variation: exception-type fidelity.

### Spec 07: negative-amount-validation-tip-jar
- Files: jar.cpp, jar.h (test file: jar_test.cpp)
- API: namespace `cafe`; `class tip_jar { public: void open(); void add(int cents); void take(int cents); int total(); };` negative amounts throw.
- Prompt shape: café tip jar; hidden tests pass negative values to both mutators.
- Target capability: G3/G4 — validate value-domain (amount > 0) separately from state-domain (open/closed).
- Target answer shape: two independent guard clauses per mutator.
- Difficulty / variation: two-axis validation.

### Spec 08: reset-on-reopen-hotel-room
- Files: room.cpp, room.h (test file: room_test.cpp)
- API: namespace `hotel`; `class room { public: void check_in(); void check_out(); void charge(int cents); int folio(); };` `check_in` on an occupied room throws; check-in resets the folio to 0.
- Prompt shape: hotel room billing; hidden tests charge, check out, check in again, expect folio 0.
- Target capability: G3 — lifecycle reset semantics: re-entry transitions restore initial observable state.
- Target answer shape: reset inside the entry transition, guarded by state check.
- Difficulty / variation: direct analog of the reopen-reset failure.

### Spec 09: start-unopened-pool-pass
- Files: pass.cpp, pass.h (test file: pass_test.cpp)
- API: namespace `pool`; `class day_pass { public: void activate(); void use(); int uses(); };` use before activation throws.
- Prompt shape: swim-pool day pass; hidden tests exercise every operation before activation expecting throws.
- Target capability: G3 — initial state is inactive; constructor must not pre-activate.
- Target answer shape: bool member default-initialized false; guards on all operations.
- Difficulty / variation: initial-state trap (the attempt-1 root cause).

### Spec 10: signature-repair-library-card
- Files: library_card.cpp, library_card.h (test file: library_card_test.cpp)
- API: namespace `library`; test expects `class card` with `void activate(); int loans();`; history answer shipped `get_loans()` and no `activate`; turn 2 shows both compile errors.
- Prompt shape: repair/retry with real diagnostics; fix is add + rename.
- Target capability: G1/G6 — mine compiler output for the expected call shapes; fix all signature errors in one turn.
- Target answer shape: whole files; add `activate()`, rename accessor, resolve any member collision.
- Difficulty / variation: signature-repair drill mirroring attempt 2's partial success.

### Spec 11: semantics-from-throw-tests-arcade
- Files: token_box.cpp, token_box.h (test file: token_box_test.cpp)
- API: namespace `arcade`; `class box { public: void unlock(); void insert(int tokens); void spend(int tokens); int count(); };`
- Prompt shape: repair — turn 2's error output quotes hidden-test `REQUIRE_THROWS_AS` lines for un-activated use, overspend, and negative insert; target must implement ALL quoted behaviors, not just the compile fix.
- Target capability: G6/G3 — extract behavioral requirements from test-quoting output; enumerate every quoted assertion.
- Target answer shape: guards covering every quoted throw case.
- Difficulty / variation: selective-reading counter-training.

### Spec 12: mutex-concurrency-shared-playlist
- Files: playlist_counter.cpp, playlist_counter.h (test file: playlist_counter_test.cpp)
- API: namespace `music`; `class counter { public: void add(); int total(); private: int count_; std::mutex m_; };`
- Prompt shape: shared party-playlist vote counter; hidden test increments from multiple threads.
- Target capability: thread safety — mutex member, `std::lock_guard` in every mutator/reader, `<mutex>` include.
- Target answer shape: lock in each public function touching state.
- Difficulty / variation: concurrency spec (the part the model got right — reinforce).

### Spec 13: no-empty-fence-observatory-dome
- Files: dome.cpp, dome.h (test file: dome_test.cpp)
- API: namespace `observatory`; `class dome { public: void rotate(int deg); int heading() const; };`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines, no compiler output.
- Target capability: G5 — no empty fences; re-emit whole unchanged files or state no change.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 14: whole-file-on-retry-canoe-rental
- Files: rental.cpp, rental.h (test file: rental_test.cpp)
- API: namespace `livery`; `class rental { public: void checkout(); void checkin(); bool out() const; };`
- Prompt shape: turn 1 answer in diff-hunk format (malformed); turn 2 repeats whole-file requirement.
- Target capability: G5 — format recovery on retry.
- Target answer shape: whole files, same semantics.
- Difficulty / variation: conditioned format repair.

### Spec 15: double-transition-throw-ski-pass
- Files: pass.cpp, pass.h (test file: pass_test.cpp)
- API: namespace `ski`; `class lift_pass { public: void activate(); void deactivate(); bool active() const; };` activating an active pass throws; deactivating an inactive one throws.
- Prompt shape: ski lift pass; both illegal double-transitions tested.
- Target capability: G3 — symmetric transition guards in both directions.
- Target answer shape: guard at top of each transition method.
- Difficulty / variation: symmetric-guard drill.

### Spec 16: overspend-guard-transit-card
- Files: fare_card.cpp, fare_card.h (test file: fare_card_test.cpp)
- API: namespace `transit`; `class card { public: void load(int cents); void ride(int fare); int balance(); };` riding with insufficient funds throws and balance is unchanged.
- Prompt shape: stored-value transit card.
- Target capability: G3/G4 — insufficient-funds guard; exception safety: failed op leaves state untouched.
- Target answer shape: check before mutation; throw path has no side effects.
- Difficulty / variation: guard + atomicity.

### Spec 17: contrastive-auto-open-photo-studio
- Files: session.cpp, session.h (test file: session_test.cpp)
- API: namespace `studio`; `class session { public: void begin(); void end(); int shots(); };`
- Prompt shape: contrastive — history shows an auto-begin constructor failing "cannot end an unbegun session"; target corrects to explicit lifecycle.
- Target capability: G1/G3 — recognize constructor-side-effect anti-pattern from its failing test.
- Target answer shape: ctor neutral; explicit begin/end.
- Difficulty / variation: negative-example-first.

### Spec 18: int-money-not-double-bake-sale
- Files: till.cpp, till.h (test file: till_test.cpp)
- API: namespace `bakesale`; `class till { public: void ring_up(int cents); int total(); };`
- Prompt shape: school bake-sale till; story notes all amounts are whole cents.
- Target capability: API judgment — integer money (cents) instead of floating point; match the specified `int` signatures.
- Target answer shape: `int` end-to-end.
- Difficulty / variation: numeric-type choice (reference uses `int`).

### Spec 19: const-accessor-with-throw-aquarium-gate
- Files: gate.cpp, gate.h (test file: gate_test.cpp)
- API: namespace `aquarium`; `class gate { public: void open_gate(); int admitted(); };` — `admitted()` throws when closed; note the reference-family tension: a throwing accessor cannot be `const` if it locks a non-mutable mutex.
- Prompt shape: aquarium entry gate; spec text calls out the const/mutex design point.
- Target capability: API judgment — choose `mutable` mutex + const accessor, or non-const accessor; justify briefly.
- Target answer shape: consistent qualifier choice; compiles with threaded test.
- Difficulty / variation: advanced const-correctness nuance.

### Spec 20: guard-helper-extraction-boat-club
- Files: berth.cpp, berth.h (test file: berth_test.cpp)
- API: namespace `marina`; `class berth { public: void reserve(); void release(); void moor(int fee); int dues(); private: void require_reserved() const; void require_positive(int) const; bool reserved_; int dues_; };`
- Prompt shape: boat-club berth fees; repeated guards across four methods.
- Target capability: code organization — private guard-helper methods (like the reference's `check_*` helpers) instead of duplicated if-throws.
- Target answer shape: two private helpers used by all public methods.
- Difficulty / variation: structure mirrors reference idiom.

### Spec 21: exception-message-irrelevance-climbing-gym
- Files: membership.cpp, membership.h (test file: membership_test.cpp)
- API: namespace `climb`; `class membership { public: void activate(); void freeze(); bool active() const; };`
- Prompt shape: gym membership; hidden tests check only the exception TYPE.
- Target capability: G4 — messages are free but type is contractual; still write clear messages.
- Target answer shape: descriptive message strings; single exception type.
- Difficulty / variation: type-vs-message distinction.

### Spec 22: repair-minimal-diff-orchard-stand
- Files: stand.cpp, stand.h (test file: stand_test.cpp)
- API: namespace `farm`; `class stand { public: void open_stand(); void sell(int cents); int revenue(); };`
- Prompt shape: repair — turn 2 shows exactly one failing assertion (sell-before-open doesn't throw); everything else passes.
- Target capability: G3/G6 — add exactly the missing guard; no unrelated refactoring.
- Target answer shape: whole files differing only in the added guard clause.
- Difficulty / variation: minimal-repair discipline.

### Spec 23: closed-account-balance-throw-vault
- Files: vault.cpp, vault.h (test file: vault_test.cpp)
- API: namespace `bankvault`; `class vault { public: void unlock_vault(); void lock_vault(); int contents(); };` `contents()` throws when locked.
- Prompt shape: vault audit; hidden test reads state after closing and expects a throw.
- Target capability: G3 — read operations also carry state guards, not just mutators.
- Target answer shape: guard in the accessor too.
- Difficulty / variation: read-side guard trap.

### Spec 24: full-matrix-capstone-laundromat
- Files: washer.cpp, washer.h (test file: washer_test.cpp)
- API: namespace `laundromat`; `class washer { public: void unlock(); void load(); void run(int cents); void unload(); int coins(); private: bool unlocked_; bool loaded_; int coins_; std::mutex m_; };` full state matrix: unlock→load→run→unload, illegal orders throw `std::runtime_error`, negative coins throw, concurrent loads safe.
- Prompt shape: laundromat washer cycle with prose state chart; hidden tests cover every illegal transition plus a threaded load test.
- Target capability: G1+G3+G4+concurrency capstone — complete state machine with guards, validation, and locking.
- Target answer shape: guard-first methods, helpers, mutex; whole files.
- Difficulty / variation: integrative final spec.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, trailing newline present. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass against the target in the benchmark's CMake/Catch2 shape (including `-pthread` for concurrency specs); receipt stored.
3. **API-conformance gate**: method names (`open`-family, noun accessors), parameter types (`int` amounts), and class/namespace names match the spec exactly — checked by compiling the spec's tests.
4. **State-matrix gate**: for stateful specs, the test suite must include every (state, operation) invalid pair and the reopen/reset case; coverage enumerated in the row metadata.
5. **Exception-policy gate**: all guards throw the specified exception type; negative-amount and closed-state axes are tested independently.
6. **Repair-turn gate**: repair specs (10, 11, 17, 22) must seed turn-1 answers that genuinely produce the shown diagnostics/failures; turn-2 targets fix exactly the seeded defects (mechanically minimal where specified).
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce bank-account's (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the raw shard-0 log, and ground truth:

1. **Re-read every cited line/range** and confirmed quotes verbatim: failure log 2939-2942 (header), 3228-3312 (attempt-1 diff answer; class surface at 3244-3255 = source 358-369, mangled hunks at 3252 = source 366 and 3273 = source 387), 3334 (█ on mutex line, source 448), 3727-3746 (empty-diff no-op), 3806-3893 (dnd-character bleed), 4042-4071 (gigasecond bleed), 4149-4202 (six runtime failures), 4205-4206 (11 passed / 6 failed), 4212 (Tests failed), 4220-4223 (`tests_outcomes: [false, false]`); shard-0 8925-8946 (attempt-1 compile errors quoting test:13-14), 9276 (attempt-1 Tests failed), 8822 (reflections exhausted), 12380-12509 (attempt-2 repair thinking + diff, auto-open ctor retained at 12446), 12508-12509 (applied).
2. **Re-checked every API claim** against `.meta/example.h` (namespace/class lines 6-7; API lines 9-13; `open_{false}` line 20; mutex line 21), `.meta/example.cpp` (open guard+reset lines 6-12, deposit/withdraw validation 14-33, close guard 35-38, balance guard 40-44, helpers 46-56), and `bank_account_test.cpp` (`account.open()` line 13, `account.balance()` line 14, unopened-deposit 77-79, unopened-close 90-93, double-open 96-100, reopen-reset 104-111, overspend 114-119, negative 122-133, concurrency 136-151). All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 0, result FAIL — matches header (2939-2942) and terminal JSON (4220-4223).
4. **Corrections made during cross-check**:
   - Bleed attribution: dnd-character failures (failure log 3806-3893) and the gigasecond rename answer (failure log 4042-4071) are concurrent-task interleaving — documented in section 1 note 1, excluded from the failure anatomy.
   - The failure log contains no attempt-2 bank-account turns; the repair answer and attempt-1 compile errors were recovered from the raw shard-0 log and are labeled "shard-0" at each citation (section 1 note 2).
   - Draft stated attempt 1 failed only on the missing `open()`; re-reading shard-0 8936-8946 shows the member/method `balance` collision was an equal, independent compile error — both are now listed as attempt-1 defects (section 3).
   - Corrected three citation line numbers after re-grep: the class surface spans failure log 3244-3255 (draft said 3246-3257), the colliding member declarations are at 3253-3254 / source 367-368 (draft said source 365-366), and the auto-open constructor is at failure log 3275 (draft said 3303).
5. **No ground-truth problems**: `.meta/example.h`, `.meta/example.cpp`, and `bank_account_test.cpp` are present, consistent, and authoritative.
