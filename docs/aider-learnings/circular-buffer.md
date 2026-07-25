# circular-buffer — Failure Learning Document

## 1. Task Identity & Evidence Pointers

- Task slug: `circular-buffer`
- Shard: `0` (failure log section header, line 5713: "- Shard: `0`")
- Test outcomes: `[False, False]` (failure log line 5715; terminal JSON `tests_outcomes: [false, false]`, failure log lines 7427-7430 / raw shard-0 lines 63399-63402)
- Result: `FAIL` (failure log line 5716)
- Failure-log section: `modal_run_logs/glm47-aider-expansion-sft-fixed26-20260723T091839Z/glm47-aider-expansion-sft-fixed26-20260723T091839Z_prompt_response_failure_log.md` lines **5711-7474**
- Raw shard log (cross-check source): `.../glm47-aider-expansion-sft-fixed26-20260723T091839Z-shard-0/benchmark.log` (circular-buffer run spans source lines ~45950-63444; interleaved with concurrent tasks)
- Ground truth (read-only):
  - `polyglot-benchmark/cpp/exercises/practice/circular-buffer/.meta/example.h` (header-only template reference; no `.meta/example.cpp` exists)
  - `polyglot-benchmark/cpp/exercises/practice/circular-buffer/circular_buffer_test.cpp`
- Existing analog dir: none (`aider-fixed26-analogs/` covers only b001-b007).

### Evidence-handling notes

1. **Chunk-1 bleed-over.** "Attempt/log chunk 1, source lines 37531-38230" (failure log 5761-6465) is entirely the *crypto-square* task (`error: 'cipher' is not a member of 'crypto_square'`, failure log 5796, source 37563). The circular-buffer material starts in chunk 2 (failure log 6466+, source 45950+).
2. **Failure log omits intermediate turns.** The attempt-1 test failure and attempt-2 repair turns exist only in the raw shard-0 log, cited as "shard-0 line N".
3. **Reference layout.** The reference is entirely in `.meta/example.h` (header-only template); there is no `.meta/example.cpp`. The model instead put template definitions in the `.cpp` and later patched with explicit instantiation.

## 2. Benchmark Contract (Ground Truth)

File set: `circular_buffer.h` + `circular_buffer.cpp`, namespace `circular_buffer`.

Public API (from `.meta/example.h`, enforced by `circular_buffer_test.cpp`):

- `template <typename ValueType> class circular_buffer` — snake_case class whose name equals the namespace (example.h:9-10). The test declares `circular_buffer::circular_buffer<int> buffer(1);` (circular_buffer_test.cpp:14, 22, 32, ...) and also `circular_buffer::circular_buffer<std::string> buffer(3);` (test:205).
- `circular_buffer(std::size_t capacity)` (example.h:12-13) — capacity constructor.
- `ValueType read();` — removes and returns the oldest item (example.h:14, 30-36).
- `void write(ValueType item);` — appends; throws when full (example.h:15, 38-42).
- `void overwrite(ValueType item);` — separate method: appends, evicting the oldest item when full (example.h:16, 44-48). Test: `buffer.overwrite(3);` (test:157, 179, 196, 216, 237-238).
- `void clear();` — empties the buffer **by advancing head to tail** (`clear() { head_ = tail_; }`, example.h:17), i.e. it does NOT reset indices to 0. Enforced by `items_cleared_out_of_buffer_cant_be_read` (test:98-106), `clear_does_nothing_on_empty_buffer` (test:123-127), and `initial_clear_does_not_affect_wrapping_around` (test:228-246).

Exception policy: **`std::domain_error`** ("Circular buffer is empty.", example.h:32) on read-from-empty and ("Circular buffer is full.", example.h:40) on write-to-full. Enforced by `REQUIRE_THROWS_AS(buffer.read(), std::domain_error)` (test:16, 39, 106, 246) and `REQUIRE_THROWS_AS(buffer.write(2), std::domain_error)` (test:61, 197). Note the asymmetry: `write` throws when full even right after an `overwrite` filled the buffer (test:191-197) — `write` never silently overwrites.

Capacity semantics: the reference uses a capacity+1 slot with `is_full()`/`is_empty()` derived purely from head/tail positions (example.h:12, 26-27) — no element counter, so no counter drift. Read frees capacity for another write (test:64-77); overwrite replaces the oldest remaining item even after reads (test:166-189).

## 3. Failure Anatomy

### Attempt 1 — outcome False (compile failure: invented non-template API + invented overwrite flag)

**What the model emitted.** A **diff-hunk answer** (failure log 7218-7310, source 46699-46791): `class CircularBuffer` (PascalCase, non-template, `int`-only) with `explicit CircularBuffer(int capacity)`, `int size() const`, `empty()`, `full()`, `void write(int value, bool force_overwrite = false);`, `int read();` (failure log 7232-7249, source 46713-46730) and implementation throwing **`std::runtime_error`** ("Buffer is full and overwrite is disabled.", failure log 7284-7286, source 46765-46767; "Buffer is empty.", failure log 7296, source 46777). The overwrite capability was folded into `write` as a defaulted bool flag — an invented API. Mangled guard hunk `-#endif // CIRCULAR_BUFFER_H+#endif // CIRCULAR_BUFFER_H` (failure log 7253, source 46734). Applied (failure log 7309-7310, source 46790-46791).

**Test run 1 — compile failure** (shard-0 ~48580-48709): `error: 'circular_buffer' is not a member of 'circular_buffer'; did you mean 'CircularBuffer'?` at `circular_buffer::circular_buffer<int> buffer(1);` (shard-0 48580-48584, quoting circular_buffer_test.cpp:111), plus `buffer.clear()` `'buffer' was not declared in this scope` cascades (shard-0 48588-48594). `Tests failed: .../circular-buffer` (shard-0 48709).

### Attempt 2 (retry with compiler output) — outcome False (runtime failures: exception type + counter/clear bugs)

**What the retry changed.** The model renamed the class to `template <typename T> class circular_buffer` and added `overwrite(const T&)` and `clear()` (shard-0 49560-49665, applied 49664-49665) — the right surface names — but kept every latent semantic defect:

1. **Kept `std::runtime_error`** everywhere (shard-0 49610-49612, 49630-49632) instead of the required `std::domain_error`.
2. **Kept `write(const T& value, bool force_overwrite)`** with the defaulted flag (shard-0 49603-49610) instead of making `write` always-throw-when-full.
3. **`overwrite` inflates the counter past capacity**: `if (full()) head = (head+1)%capacity;` then unconditionally `count++` (shard-0 49620-49628). After overwriting a full capacity-1 buffer, `count` becomes 2 > capacity, so `full()` (`count == capacity`) is permanently false — `write` stops throwing.
4. **`clear()` resets indices to 0** (`head = 0; tail = 0; count = 0;`, shard-0 49644-49650) instead of `head = tail`, corrupting wrap-around position state.
5. **Template definitions in the `.cpp`**, later patched with `template class circular_buffer<int>; template class circular_buffer<std::string>;` explicit instantiation (shard-0 52358-52363, applied 52372-52373) instead of moving definitions to the header.

**Reflection turns.** Subsequent `# Fix any errors below` █ prompts drew "no changes are needed" + empty ```` ```diff ```` fences (shard-0 53175-53190, 63080-63105; applied as no-ops at 53186-53187, 63102-63103; "Only 3 reflections allowed, stopping." 63165).

**Terminal result — compiles, 6 of 16 test cases fail** (failure log 7340-7419, source 63312-63391):

- Wrong exception type, four cases: `REQUIRE_THROWS_AS(buffer.read(), std::domain_error)` — "due to unexpected exception with message: Buffer is empty." (failure log 7352-7360, source 63324-63332; test:16; likewise test:39 at 7363-7371, test:106 at 7385-7393, source 63357-63365) and `REQUIRE_THROWS_AS(buffer.write(2), std::domain_error)` — "...Buffer is full and overwrite is disabled." (failure log 7374-7382, source 63346-63354; test:61).
- `full_buffer_cant_be_written_after_overwrite`: `REQUIRE_THROWS_AS(buffer.write(3), std::domain_error)` — "no exception was thrown" (failure log 7396-7404, source 63368-63378; test:191-197) — the count-inflation bug (defect 3).
- `initial_clear_does_not_affect_wrapping_around`: `REQUIRE(expected == buffer.read())` expanded to `3 == 4` (failure log 7406-7409, source 63378-63381; test:228-241) — the index-reset `clear()` bug (defect 4).

`test cases: 16 | 10 passed | 6 failed` (failure log 7412-7413, source 63384-63385); `Tests failed` (failure log 7419, source 63391); JSON `tests_outcomes: [false, false]` (failure log 7427-7430).

### Hard evidence vs inference

- Hard evidence: invented `CircularBuffer` + `force_overwrite` flag (failure log 7232-7249), `std::runtime_error` throws (failure log 7284-7296), attempt-1 compile errors (shard-0 48580-48594), attempt-2 template rename retaining runtime_error/flag/counter/clear defects (shard-0 49560-49665), count-inflation and clear-reset code (shard-0 49620-49650), the six terminal failures (failure log 7352-7414), empty-diff no-ops (shard-0 53175-53190, 63080-63105).
- Inference: attempt 1 is the familiar API-invention failure (PascalCase class, bool-flag overwrite, runtime_error). Attempt 2 fixed only what the compiler could name (class name, missing methods) and never re-derived semantics: the exception TYPE was never visible in attempt-1's compile errors (they were all name errors), so the model had to read it from `REQUIRE_THROWS_AS(..., std::domain_error)` lines quoted in test output — but the terminal failure quotes show it never did. The counter-based design (vs the reference's position-only full/empty derivation) invited two independent state bugs (count inflation in overwrite; index reset in clear) that a position-only design structurally cannot have. Design choice, not just oversight.

## 4. Knowledge / Capability Gaps

- **G1 — Canonical API surface.** Template snake_case class named after the namespace, separate `overwrite()` method, no flag parameters (contract: example.h:9-17; invented away at failure log 7232-7249; compile cost at shard-0 48580-48584).
- **G2 — Exception-type fidelity.** `std::domain_error` for full/empty, not `std::runtime_error`. The model never adopted it across both attempts (failure log 7284-7296; shard-0 49610-49632; terminal proof 7352-7382). Reading `REQUIRE_THROWS_AS` expectations out of test-quoting output is the missing skill.
- **G3 — Counter vs position invariants.** Tracking `count` alongside head/tail creates a redundant invariant the model violated twice: `overwrite` increments count past capacity (shard-0 49620-49628 → failure 7396-7404) and `clear` desyncs indices (shard-0 49644-49650 → failure 7406-7414). Position-derived full/empty (reference example.h:26-27) is the robust idiom.
- **G4 — Clear semantics.** `clear()` must preserve position continuity (`head_ = tail_`), not reset to zero — a subtle wrap-around state-machine requirement the model got wrong (shard-0 49644-49650; test:228-246).
- **G5 — Template placement.** Definitions in `.cpp` + explicit instantiation patch (shard-0 52358-52363) instead of header-only templates (reference is entirely in the header).
- **G6 — Whole-file format contract.** All answers were ```` ```diff ```` hunks (failure log 7221-7224; shard-0 49560+), with a mangled guard line (failure log 7253); reflection turns produced empty-diff no-ops (shard-0 53186-53187, 63102-63103).

## 5. SFT Task Specifications (24 specs)

Answer-blind: every spec uses a new story domain; no benchmark test fixtures or reference code are copied. Ordered foundational → advanced.

### Spec 01: whole-file-listing-rain-gauge
- Files: rain_log.cpp, rain_log.h (test file: rain_log_test.cpp)
- API: namespace `weather`; `class log { public: void add(double mm); double total() const; };`
- Prompt shape: rainfall logging; whole-file instruction prominent.
- Target capability: G6 — complete whole-file listings only.
- Target answer shape: two whole-file listings, no diff fences.
- Difficulty / variation: minimal; format-only trap.

### Spec 02: namespace-named-class-token-ring
- Files: token_ring.h, token_ring.cpp (test file: token_ring_test.cpp)
- API: namespace `token_ring`; `template <typename T> class token_ring { public: explicit token_ring(std::size_t capacity); void pass(const T& token); T next(); };`
- Prompt shape: token-ring network simulator; hidden tests declare `token_ring::token_ring<int>`.
- Target capability: G1 — class named exactly like its namespace, snake_case, templated.
- Target answer shape: template class with the namespace-matching name.
- Difficulty / variation: naming prior (same pattern as the benchmark task, new domain).

### Spec 03: domain-error-policy-mail-slots
- Files: mail_slot.h, mail_slot.cpp (test file: mail_slot_test.cpp)
- API: namespace `post`; `template <typename T> class slot_box { public: explicit slot_box(std::size_t slots); void deposit(const T& letter); T collect(); };` full deposit and empty collect throw `std::domain_error`.
- Prompt shape: apartment mail slots; hidden tests use `REQUIRE_THROWS_AS(..., std::domain_error)`.
- Target capability: G2 — choose `std::domain_error` (bounded-container policy), not `std::runtime_error`; include `<stdexcept>`.
- Target answer shape: domain_error at both guard sites with clear messages.
- Difficulty / variation: exception-type drill.

### Spec 04: exception-type-repair-coffee-queue
- Files: order_rail.h, order_rail.cpp (test file: order_rail_test.cpp)
- API: namespace `cafe`; test expects `std::overflow_error` on full push; history answer threw `std::runtime_error`; turn 2 shows `REQUIRE_THROWS_AS(..., std::overflow_error) ... due to unexpected exception with message: ...`.
- Prompt shape: repair — change exactly the exception types, nothing else.
- Target capability: G2 — map "due to unexpected exception with message" failures to a wrong exception TYPE; minimal type swap.
- Target answer shape: whole files; only the throw types changed.
- Difficulty / variation: the exact terminal diagnostic from the failure log.

### Spec 05: separate-overwrite-method-dvr
- Files: recorder.h, recorder.cpp (test file: recorder_test.cpp)
- API: namespace `tv`; `template <typename T> class reel { public: explicit reel(std::size_t hours); void record(const T& show); void record_over(const T& show); T playback_oldest(); };` — `record` throws when full; `record_over` evicts oldest when full.
- Prompt shape: DVR with finite hours and an explicit record-over mode; instructions forbid flag parameters.
- Target capability: G1 — two methods for two policies; never a `bool force` parameter.
- Target answer shape: separate methods sharing a private append helper.
- Difficulty / variation: API-shape fidelity (counter to the force_overwrite invention).

### Spec 06: position-derived-full-empty-ferry-lane
- Files: lane.h, lane.cpp (test file: lane_test.cpp)
- API: namespace `harbor`; `template <typename T> class ferry_lane { public: explicit ferry_lane(std::size_t capacity); bool lane_full() const; bool lane_empty() const; void enter(const T& ship); T leave(); };`
- Prompt shape: ferry holding lane with capacity+1 slot trick described in the story.
- Target capability: G3 — derive full/empty from head/tail positions only; no element counter.
- Target answer shape: `is_empty` = head==tail; `is_full` = head==(tail+1)%size; no count member.
- Difficulty / variation: the reference's invariant style.

### Spec 07: counter-invariant-discipline-parking-ring
- Files: ring.h, ring.cpp (test file: ring_test.cpp)
- API: namespace `garage`; `template <typename T> class ring { public: explicit ring(std::size_t capacity); void park(const T& car); T retrieve(); void evict_oldest_and_park(const T& car); std::size_t parked() const; };`
- Prompt shape: ring parking where a `count` member is required by the `parked()` accessor; spec warns count must never exceed capacity.
- Target capability: G3 — if a counter is kept, maintain its invariant on every path including eviction (decrement-or-hold on overwrite).
- Target answer shape: eviction path adjusts head without incrementing count past capacity.
- Difficulty / variation: counter-trains the count-inflation bug while keeping a counter.

### Spec 08: clear-preserves-position-turntable
- Files: turntable.h, turntable.cpp (test file: turntable_test.cpp)
- API: namespace `rail`; `template <typename T> class turntable { public: explicit turntable(std::size_t slots); void load(const T& car); T unload(); void empty_table(); };` — `empty_table` must be equivalent to "unload all" without disturbing position arithmetic.
- Prompt shape: rail turntable; hidden tests clear mid-stream then verify wrap-around still works.
- Target capability: G4 — clear via `head = tail`, never index reset; understand why position continuity matters.
- Target answer shape: one-line clear; a comment noting positions are monotonic modulo size.
- Difficulty / variation: the exact clear bug, fresh domain.

### Spec 09: header-only-template-queue-lift-tickets
- Files: ticket_roll.h, ticket_roll.cpp (test file: ticket_roll_test.cpp)
- API: namespace `ski`; `template <typename T> class roll { public: void tear_off(const T& t); T next(); bool any() const; };`
- Prompt shape: lift-ticket roll; note says the cpp is compiled separately and T is a template.
- Target capability: G5 — all template definitions in the header; cpp holds only include + empty namespace.
- Target answer shape: header-only implementation.
- Difficulty / variation: template placement discipline.

### Spec 10: string-instantiation-bumper-cars
- Files: arena.h, arena.cpp (test file: arena_test.cpp)
- API: namespace `fair`; `template <typename T> class arena_queue { public: explicit arena_queue(std::size_t n); void join(const T& name); T call_next(); };`
- Prompt shape: bumper-car queue; hidden tests use both `int` tickets and `std::string` names.
- Target capability: G5/G1 — genuinely generic code (no int assumptions); both instantiations compile.
- Target answer shape: nothing type-specific outside the template parameter.
- Difficulty / variation: generality check.

### Spec 11: read-frees-capacity-canoe-locker
- Files: locker_ring.h, locker_ring.cpp (test file: locker_ring_test.cpp)
- API: namespace `marina`; `template <typename T> class key_ring { public: explicit key_ring(std::size_t hooks); void hang(const T& key); T take(); };`
- Prompt shape: kayak key ring; hidden tests fill, take one, hang again, verify no false-full.
- Target capability: edge cases — full/empty transitions alternate correctly; a read frees exactly one slot.
- Target answer shape: position advance on both operations.
- Difficulty / variation: alternating-transition drill.

### Spec 12: overwrite-after-read-oldest-log-ring
- Files: sensor_ring.h, sensor_ring.cpp (test file: sensor_ring_test.cpp)
- API: namespace `buoy`; `template <typename T> class reading_ring { public: explicit reading_ring(std::size_t n); void push(const T& r); void push_overwrite(const T& r); T oldest(); };`
- Prompt shape: drifting-buoy reading ring; hidden tests read some, then overwrite, expecting eviction of the oldest REMAINING item (not the original oldest).
- Target capability: edge cases — eviction targets current head, whatever it is.
- Target answer shape: overwrite advances head only when full, then appends at tail.
- Difficulty / variation: mirrors test:166-189 semantics.

### Spec 13: write-after-overwrite-still-throws-photo-drum
- Files: drum.h, drum.cpp (test file: drum_test.cpp)
- API: namespace `lab`; `template <typename T> class photo_drum { public: explicit photo_drum(std::size_t n); void add(const T& frame); void add_overwrite(const T& frame); T take(); };`
- Prompt shape: photo-development drum; hidden tests: fill, overwrite (still full), plain add must throw.
- Target capability: G3/G2 — overwrite leaves the buffer full; the plain-write guard must still fire (no state corruption from overwrite).
- Target answer shape: full predicate correct after overwrite; throw observed.
- Difficulty / variation: the exact "no exception was thrown" failure, fresh wrapper.

### Spec 14: no-empty-fence-tide-clock
- Files: tide_clock.cpp, tide_clock.h (test file: tide_clock_test.cpp)
- API: namespace `coast`; `class tide_clock { public: void advance(); int hour() const; };`
- Prompt shape: multi-turn — turn 2 is "Fix any errors below" with █ markers on correct lines, no compiler output.
- Target capability: G6 — no empty fences; whole unchanged files or explicit no-change statement.
- Target answer shape: whole unchanged files + one sentence.
- Difficulty / variation: no-op-reply policy.

### Spec 15: rename-and-templatize-repair-grain-silo
- Files: silo.h, silo.cpp (test file: silo_test.cpp)
- API: namespace `farm`; test expects `template <typename T> class silo_ring`; history answer shipped `class SiloRing` int-only; turn 2 shows `'silo_ring' is not a member of 'farm'; did you mean 'SiloRing'?`.
- Prompt shape: repair — rename AND templatize AND fix member types in one turn.
- Target capability: G1 — complete surface conformance in a single repair turn.
- Target answer shape: whole files; template throughout; old class gone.
- Difficulty / variation: combined rename+generality repair.

### Spec 16: exception-message-text-gondola
- Files: gondola.h, gondola.cpp (test file: gondola_test.cpp)
- API: namespace `mountain`; `template <typename T> class cabin_line { public: void board(const T& p); T alight(); };` empty alight throws `std::domain_error` with a message naming the container.
- Prompt shape: ski gondola; spec notes tests check only type, but messages must be descriptive for logs.
- Target capability: G2 — type is contractual, message is diagnostic; write both well.
- Target answer shape: descriptive messages; single exception type.
- Difficulty / variation: type-vs-message reinforcement.

### Spec 17: capacity-constructor-types-locker-ring
- Files: padlock_ring.h, padlock_ring.cpp (test file: padlock_ring_test.cpp)
- API: namespace `gym`; `template <typename T> class padlock_ring { public: explicit padlock_ring(std::size_t hooks); };`
- Prompt shape: gym padlock ring; constructor takes `std::size_t` and must be `explicit`.
- Target capability: API fidelity — `explicit` single-arg constructor, `std::size_t` for capacities.
- Target answer shape: exact signature; no implicit conversions.
- Difficulty / variation: ctor-signature precision.

### Spec 18: contrastive-flag-vs-method-music-queue
- Files: deck.h, deck.cpp (test file: deck_test.cpp)
- API: namespace `dj`; `template <typename T> class deck_queue { public: void cue(const T& track); void cue_bump(const T& track); T spin(); };`
- Prompt shape: contrastive — history shows a `cue(track, bool bump=false)` design failing the contract tests; target splits into two methods.
- Target capability: G1 — flag-parameter anti-pattern vs separate methods; recognize from failing tests.
- Target answer shape: two methods; flag removed everywhere.
- Difficulty / variation: negative-example-first.

### Spec 19: clear-on-empty-is-noop-wave-tank
- Files: tank.h, tank.cpp (test file: tank_test.cpp)
- API: namespace `ocean`; `template <typename T> class sample_well { public: void add(const T& s); T draw(); void drain(); };`
- Prompt shape: wave-tank sampling; hidden tests drain an already-empty well then keep using it.
- Target capability: G4/edge cases — clear on empty is a safe no-op; state stays consistent.
- Target answer shape: `head = tail` handles empty naturally.
- Difficulty / variation: no-op edge of clear semantics.

### Spec 20: whole-file-on-retry-beehive-frames
- Files: frame_ring.cpp, frame_ring.h (test file: frame_ring_test.cpp)
- API: namespace `apiary`; `template <typename T> class frame_ring { public: void insert(const T& f); T remove(); };`
- Prompt shape: turn 1 answer in diff-hunk format (malformed); turn 2 repeats whole-file requirement.
- Target capability: G6 — format recovery on retry.
- Target answer shape: whole files, same semantics.
- Difficulty / variation: conditioned format repair.

### Spec 21: read-once-semantics-ticket-gate
- Files: gate_ring.h, gate_ring.cpp (test file: gate_ring_test.cpp)
- API: namespace `transit`; `template <typename T> class gate_ring { public: void feed(const T& ticket); T scan(); };`
- Prompt shape: ticket gate buffer; hidden tests write once, read twice — second read must throw.
- Target capability: edge cases — a read consumes; no ghost elements remain.
- Target answer shape: head advance on read; empty predicate correct afterward.
- Difficulty / variation: consume-on-read invariant.

### Spec 22: modulo-wrap-discipline-orbit-slots
- Files: orbit_ring.h, orbit_ring.cpp (test file: orbit_ring_test.cpp)
- API: namespace `space`; `template <typename T> class orbit_ring { public: explicit orbit_ring(std::size_t slots); void dock(const T& craft); T undock(); };`
- Prompt shape: station docking ring; indices must wrap modulo the slot count.
- Target capability: ring arithmetic — `(i + 1) % size` in exactly the advance paths; no out-of-range access.
- Target answer shape: single advance helper used by both operations.
- Difficulty / variation: wrap-arithmetic drill.

### Spec 23: exception-safety-on-throw-ice-cream-line
- Files: scoop_ring.h, scoop_ring.cpp (test file: scoop_ring_test.cpp)
- API: namespace `parlor`; `template <typename T> class tub_ring { public: void scoop_in(const T& flavor); T scoop_out(); };`
- Prompt shape: ice-cream tub ring; hidden tests attempt a throwing operation then verify prior contents are intact.
- Target capability: edge cases — throw paths leave state untouched (no partial head/tail/count updates).
- Target answer shape: guard before any mutation.
- Difficulty / variation: exception-safety ordering.

### Spec 24: capstone-lantern-ring
- Files: lantern_ring.h, lantern_ring.cpp (test file: lantern_ring_test.cpp)
- API: namespace `festival`; `template <typename T> class lantern_ring final { public: explicit lantern_ring(std::size_t capacity); T light_next(); void hang(const T& lantern); void hang_replace(const T& lantern); void take_down_all(); bool unlit() const; bool crowded() const; };` — full ring semantics: domain_error on empty light/full hang, position-derived predicates, continuity-preserving clear, header-only template.
- Prompt shape: festival lantern ring with prose policy description; prompt underdetermines names but pins behaviors.
- Target capability: G1+G2+G3+G4+G5 capstone — complete contract-shaped ring buffer.
- Target answer shape: whole files; position-only state; correct exception types; no counter.
- Difficulty / variation: integrative final spec.

## 6. Acceptance & Validation Gates

1. **Format gate**: target answers parse as Aider whole-file listings — no diff hunks, no empty fences, trailing newline present. Parser receipt required.
2. **Compile+test receipt**: hidden tests compile and pass in the benchmark's CMake/Catch2 shape; template specs must instantiate at least `int` and `std::string`. Receipt stored.
3. **Exception-policy gate**: guards throw the specified exception type (e.g. `std::domain_error`); tests include the "due to unexpected exception" failure mode check by asserting with `REQUIRE_THROWS_AS` of the SPECIFIED type only.
4. **Ring-semantics gate**: tests must include fill→read→refill, overwrite-when-full, overwrite-then-plain-write-throws, clear-mid-stream-then-wrap, clear-on-empty, and read-once cases — enumerated in row metadata.
5. **Invariant gate**: position-derived full/empty OR a counter proven consistent on every path (overwrite must not inflate past capacity) — checked by the Spec-13-style test.
6. **Repair-turn gate**: repair specs (04, 15, 18) must seed turn-1 answers producing the shown diagnostics; turn-2 targets fix exactly the seeded defects.
7. **Contamination check**: stories, identifiers, and fixtures must not reproduce circular-buffer's (or any polyglot-benchmark task's) instructions, test names, or reference code; similarity screen against `polyglot-benchmark/`.
8. **Answer-blind review**: reviewer confirms no spec text or target answer quotes benchmark tests or `.meta` solutions.

## 7. Cross-Check Statement (2026-07-24)

Cross-check performed on 2026-07-24 against the failure log, the raw shard-0 log, and ground truth:

1. **Re-read every cited line/range** and confirmed quotes verbatim: failure log 5713-5716 (header), 5796 (crypto-square bleed), 7218-7310 (attempt-1 answer; class surface 7232-7249 = source 46713-46730, runtime_error throws 7284-7296 = source 46765-46777, mangled guard 7253 = source 46734, applied 7309-7310), 7340-7419 (terminal: domain_error failures 7352-7393 = source 63324-63365, no-exception failure 7396-7404 = source 63368-63378, `3 == 4` failure 7406-7409 = source 63378-63381, summary 7412-7413 = source 63384-63385, Tests failed 7419 = source 63391), 7427-7430 (`tests_outcomes: [false, false]` = source 63399-63402); shard-0 48580-48594 (attempt-1 compile errors quoting test:111), 48709 (attempt-1 Tests failed), 49560-49665 (attempt-2 template rewrite; force-flag kept at 49603-49610, runtime_error kept at 49610-49632, count-inflation overwrite at 49620-49628, index-reset clear at 49644-49650), 49664-49665 (applied), 52358-52373 (explicit-instantiation patch), 53175-53190 and 63080-63105 (empty-diff no-ops), 63378 (terminal Tests failed).
2. **Re-checked every API claim** against `.meta/example.h` (template class lines 9-10, ctor lines 12-13, API lines 14-17, domain_error lines 32/40, position-derived predicates lines 26-27, clear line 17, capacity+1 buffer line 12) and `circular_buffer_test.cpp` (construction lines 14/22/32, string instantiation line 205, throw expectations lines 16/39/61/106/197/246, clear cases 98-127, overwrite cases 135-197, wrap-after-clear case 228-246). Verified `.meta/` has no `example.cpp` — stated in section 1 note 3. All contract claims match.
3. **Outcome array and shard**: `[False, False]`, shard 0, result FAIL — matches header (5713-5716) and terminal JSON (7427-7430).
4. **Corrections made during cross-check**:
   - Chunk 1 (source 37531-38230) is entirely the crypto-square task — documented as bleed (section 1 note 1), excluded from the failure anatomy.
   - Draft attributed the terminal failures to the attempt-1 code; re-reading shard-0 49560-49665 shows attempt 2 renamed/templatized the class (which is why the terminal run compiled) while preserving the semantic defects — the two-phase anatomy in section 3 reflects this.
   - Root-cause chain for the "no exception thrown" failure was verified by re-reading the attempt-2 `overwrite` body (shard-0 49620-49628): unconditional `count++` after evicting head — recorded as defect 3 with the mechanism stated, labeled inference.
   - Corrected six citation line numbers after re-grep: class surface 7232-7249 (draft 7231-7248), runtime_error throws 7284-7296 (draft 7283-7295), mangled guard 7253 (draft 7252), full-write terminal block source 63346-63354 (draft said through 63357, which is the test:106 block at 7385-7393), and the `3 == 4` failure at 7406-7409 / source 63378-63381 (draft 7406-7414 / 63378-63389).
5. **No ground-truth problems**: `.meta/example.h` and `circular_buffer_test.cpp` are present, consistent, and authoritative; the absent `.meta/example.cpp` is intentional (header-only template), not missing ground truth.
