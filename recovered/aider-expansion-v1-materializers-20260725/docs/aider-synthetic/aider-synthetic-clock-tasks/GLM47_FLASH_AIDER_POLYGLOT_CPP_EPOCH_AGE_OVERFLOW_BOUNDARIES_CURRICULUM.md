# Epoch, Age, And Overflow-Boundary Expansion Curriculum

Status: implementation contract for exactly 80 new clean-room local Aider
task roots. The roots are candidates only; this document does not authorize an
SFT projection, dataset release, training, or benchmark-uplift claim.

Cycle 001's 80 IDs are preserved as rejected design lineages by the immutable
independent audit. Cycles 002-003 implement each advertised mechanism as a
distinct replacement root; cycle 003 replaced the five clone-admitted cycle-002
IDs (`temporal-normalize-nanos`, `temporal-nearest-era10`,
`temporal-mjd-split`, `temporal-nano-day`, and `temporal-age-march1`). The
current replacement inventory is binding:

- Epoch/codecs: `temporal-floor-split`, `temporal-normalize-subsecond`,
  `temporal-epoch-range-intersection`, `temporal-fixed-fraction`,
  `temporal-nearest-era32`, `temporal-era-consensus`,
  `temporal-week-seconds`, `temporal-filetime-split`,
  `temporal-unsigned-epoch-offset`, `temporal-leap-table-digest`,
  `temporal-excel-serial`, `temporal-dos-fields`, `temporal-bcd-fields`,
  `temporal-signed48`, `temporal-step-lookup`, `temporal-utc-to-tai`,
  `temporal-tai-to-utc`, `temporal-leap-label`,
  `temporal-signed-duration-parts`, and `temporal-rational-ticks`.
- Civil age: `temporal-age-feb28`, `temporal-age-threshold-date`,
  `temporal-age-clamped`, `temporal-age-borrowed`,
  `temporal-birthday-nearest`, `temporal-milestone`,
  `temporal-majority-epoch`, `temporal-cohort-cutoff`,
  `temporal-actuarial`, `temporal-gestational`, `temporal-age-fraction`,
  `temporal-age-band`, `temporal-age-series`, `temporal-eligibility`,
  `temporal-leapling-count`, `temporal-retirement`,
  `temporal-sibling-gap`, `temporal-completed-months`,
  `temporal-iso-weeks`, and `temporal-century-birthdays`.
- Checked ranges: `temporal-checked-add`, `temporal-compose-duration`,
  `temporal-exact-ratio`, `temporal-saturating-add`, `temporal-bounded-add`,
  `temporal-day-product`, `temporal-join-nanos`, `temporal-euclidean-div`,
  `temporal-affine-map`, `temporal-transactional-sum`,
  `temporal-overflow-frontier`, `temporal-interval-shift`,
  `temporal-range-rescale`, `temporal-weighted-centroid`,
  `temporal-interpolate`, `temporal-nth-occurrence`, `temporal-backoff`,
  `temporal-arithmetic-sum`, `temporal-dot-product`, and
  `temporal-window-count`.
- Rollover/order: `temporal-unwrap32`, `temporal-unwrap16`,
  `temporal-serial-order`, `temporal-gps-sequence`,
  `temporal-reset-segments`, `temporal-two-point-calibration`,
  `temporal-piecewise-offset`, `temporal-median-offset`,
  `temporal-drift-envelope`, `temporal-packet-order`, `temporal-watermark`,
  `temporal-tolerance-dedup`, `temporal-delta2`, `temporal-gap-runs`,
  `temporal-bucket-index`, `temporal-slew-distribution`,
  `temporal-quantize`, `temporal-common-timebase`, `temporal-tagged-era`, and
  `temporal-euclidean-shard-key`.

Every replacement records its cycle-001 `replaces_task_id`; none of the
rejected IDs remains in the selected or materialized candidate inventory.

## Authority And Count Cell

This curriculum implements the binding 80-root `Epoch, age, large-range, and
overflow-safe conversion` cell in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`. All roots are
new-root lineages and must materialize only below:

```text
.w8-biayn/data/aider-tasks-expansion-v1/aider-dates-and-clocks/epoch-age-overflow-boundaries/
```

The existing `.w8-biayn/data/aider-tasks/` and
`.w8-biayn/data/aider-tasks-reverify/` trees are immutable comparison inputs.
The generator must fail on any ID, prompt, reference, test, API, normalized
contract, or semantic-lineage collision with either tree. The official 26
Aider Polyglot C++ tasks, especially `clock`, `gigasecond`, and `meetup`, are
permanent holdouts. No wording, API, tests, reference, model output, or repair
history from them is an authoring input.

The selected specification prompt is
`docs/aider-tasks-spec/prompts/generate-family-spec.md`. Implementation uses
`docs/aider-tasks-spec/prompts/implement-family-for-sft.md` only after this
contract is present.

## Family-Wide Executable Contract

Every root is C++17, deterministic, offline, and header-only with exactly one
editable `<task-id>.h`. The starter declares the complete public API and throws
`std::logic_error("not implemented")` from the unfinished operation. The
private reference is `.meta/example.h`. `task_visible_test.cpp` and
`.meta/task_hidden_test.cpp` are separate executables and CTest entries.
`.meta/negative.h` is a coherent, strict-warning-clean implementation of the
same API that violates the named task rule and must be rejected by an executed
production test. The prompt exposes only `.docs/introduction.md`,
`.docs/instructions.md`, and the starter header.

All integer arithmetic is defined without signed overflow. Invalid input
returns `std::nullopt`, `false`, or a documented status and never partially
mutates caller-owned output. Division of signed values uses Euclidean
quotient/remainder where the contract says so. Dates use the proleptic
Gregorian calendar with astronomical year numbering unless a task explicitly
defines a different external encoding. Resource bounds are O(1), O(n), or
O(n log n) as stated by the task and never depend on wall-clock state.

Each retained root must differ from every other retained root in all seven
mandatory dimensions: public API; owned state or algorithm; mutation or
selection rules; invalid and boundary behavior; reference control flow;
deterministic oracle; and topic-specific negative fixture. Pairwise proof is
derived from emitted artifacts after removing comments, strings, literals,
identifiers, and clean-room domain nouns. IDs, kind labels, hashes, and
declared profiles are not diversity evidence.

## Root Inventory: Epoch And External-Code Conversion (1-20)

| # | Task ID and public API | Core mechanism and boundary contract | Coherent wrong substitute rejected |
|---:|---|---|---|
| 1 | `temporal-floor-split`: `optional<DaySecond> temporal_floor_split(int64_t unix_seconds)` | Split signed Unix seconds into a day index and second-of-day using pure-Euclidean partitioning. The remainder is always in [0, 86399], including at INT64_MIN. | Substitutes truncating division. |
| 2 | `temporal-normalize-subsecond`: `optional<SecondMillis> temporal_normalize_subsecond(int64_t seconds, int64_t millis)` | Normalize a seconds/millisecond pair by carrying an arbitrary signed millisecond field. Reject when the carried seconds are outside int64_t; return a remainder in [0, 999]. | Substitutes clamped remainder. |
| 3 | `temporal-epoch-range-intersection`: `optional<EpochRange> temporal_epoch_range_intersection(EpochRange left, EpochRange right)` | Intersect timestamp intervals after validating their closed endpoints. Reject malformed intervals and preserve an exact touching-point intersection. | Substitutes endpoint union. |
| 4 | `temporal-fixed-fraction`: `uint32_t temporal_fixed_fraction(uint32_t fraction)` | Round an unsigned 32-bit binary fraction to nanoseconds. Use nearest-even rounding without overflowing the fixed-point product. | Substitutes decimal fraction. |
| 5 | `temporal-nearest-era32`: `optional<int64_t> temporal_nearest_era32(uint32_t field, int64_t pivot)` | Lift a transmitted 32-bit NTP second field to the unique era nearest a signed pivot. Reject the exact half-era tie. | Substitutes era zero. |
| 6 | `temporal-era-consensus`: `optional<int64_t> temporal_era_consensus(uint32_t sample, uint32_t modulus, vector<int64_t> pivots)` | Resolve a modular sample only when every supplied absolute pivot selects the same era lift. Reject ties, out-of-range samples, and pivot disagreement. | Substitutes single-pivot nearest lift. |
| 7 | `temporal-week-seconds`: `optional<int64_t> temporal_week_seconds(int64_t week, int64_t second_of_week)` | Validate GPS week and second-of-week and compose continuous seconds. Second 604800 is invalid and all arithmetic is checked. | Substitutes week wrap. |
| 8 | `temporal-filetime-split`: `optional<FiletimeUnix> temporal_filetime_split(uint64_t ticks)` | Translate unsigned 100-nanosecond ticks since 1601 to Unix seconds and residual ticks. The unsigned subtraction and signed result must not wrap. | Substitutes early signed cast. |
| 9 | `temporal-unsigned-epoch-offset`: `optional<int64_t> temporal_unsigned_epoch_offset(uint64_t mac_seconds)` | Translate unsigned seconds since 1904 to signed Unix seconds. Pre-1970 results are valid; only unrepresentable signed results fail. | Substitutes unsigned underflow. |
| 10 | `temporal-leap-table-digest`: `optional<LeapDigest> temporal_leap_table_digest(vector<LeapDelta> table)` | Validate a transition table and return its checked cumulative offset and span. Require strictly increasing transitions and reject cumulative overflow. | Substitutes last offset only. |
| 11 | `temporal-excel-serial`: `optional<ExcelSerialDate> temporal_excel_serial(int64_t serial)` | Decode positive Excel serial dates while representing serial 60 as the fictitious leap label. Serial 0 and negative serials are rejected; later serials are adjusted exactly once. | Substitutes ordinary Gregorian serial. |
| 12 | `temporal-dos-fields`: `optional<DosDateTime> temporal_dos_fields(uint32_t packed)` | Decode a packed DOS date-time word and validate all extracted fields. Reject impossible dates, reserved input width, and odd seconds. | Substitutes unchecked bit fields. |
| 13 | `temporal-bcd-fields`: `optional<BcdTimestamp> temporal_bcd_fields(array<uint8_t, 7> bytes)` | Decode seven packed-BCD timestamp bytes and validate the resulting Gregorian label. Every high and low nibble must be decimal. | Substitutes hex byte conversion. |
| 14 | `temporal-signed48`: `int64_t temporal_signed48(array<uint8_t, 6> bytes)` | Decode a big-endian signed 48-bit two's-complement counter. Sign extension is explicit and portable. | Substitutes zero extension. |
| 15 | `temporal-step-lookup`: `optional<int64_t> temporal_step_lookup(int64_t utc, vector<LeapStep> steps)` | Validate a leap-offset transition table and select the last applicable entry. Transitions are strictly increasing and empty/no-prior tables fail. | Substitutes first future step. |
| 16 | `temporal-utc-to-tai`: `optional<int64_t> temporal_utc_to_tai(int64_t utc, vector<LeapStep> steps)` | Apply the applicable piecewise leap offset to a UTC second. Validate the table and reject checked addition overflow. | Substitutes final offset everywhere. |
| 17 | `temporal-tai-to-utc`: `optional<int64_t> temporal_tai_to_utc(int64_t tai, vector<TaiUtcTransition> steps)` | Invert a piecewise UTC-to-TAI mapping. Reject positive-leap discontinuity gaps and ambiguous inversions. | Substitutes latest-offset subtraction. |
| 18 | `temporal-leap-label`: `bool temporal_leap_label(UtcLabel label, vector<int64_t> leap_days)` | Validate ordinary UTC fields and permit second 60 only at a listed day end. A leap label is valid only at 23:59 on an allowlisted day. | Substitutes second-60 everywhere. |
| 19 | `temporal-signed-duration-parts`: `DurationParts temporal_signed_duration_parts(int64_t nanoseconds)` | Decompose a signed nanosecond duration into sign and unsigned hour/minute/second/nanosecond magnitude. Handle INT64_MIN without signed negation and produce canonical component ranges. | Substitutes signed division fields. |
| 20 | `temporal-rational-ticks`: `optional<int64_t> temporal_rational_ticks(int64_t ticks, uint64_t numerator, uint64_t denominator)` | Convert signed ticks through a positive rational scale using reduced factors. Use nearest-even rounding and reject overflow or a zero denominator. | Substitutes multiply first. |

## Root Inventory: Civil Dates And Human Age (21-40)

| # | Task ID and public API | Core mechanism and boundary contract | Coherent wrong substitute rejected |
|---:|---|---|---|
| 21 | `temporal-age-feb28`: `optional<int64_t> temporal_age_feb28(FebruaryObservedBirth birth, Date as_of)` | Count completed years with February 29 observed on February 28 in common years. Reject invalid or reversed dates. | Substitutes March-1 policy. |
| 22 | `temporal-age-threshold-date`: `optional<Date> temporal_age_threshold_date(Date birth, int64_t age)` | Return the first calendar date on which a person reaches a requested nonnegative age. Clamp February 29 to month end and reject year overflow or invalid birth dates. | Substitutes elapsed-day approximation. |
| 23 | `temporal-age-clamped`: `optional<AgeParts> temporal_age_clamped(Date birth, Date as_of)` | Return canonical year/month/day age by clamping invalid monthly anniversaries. Components reconstruct the reference date from the birth date under the clamp policy. | Substitutes fixed 30-day borrow. |
| 24 | `temporal-age-borrowed`: `optional<AgeParts> temporal_age_borrowed(Date earlier, Date later)` | Subtract calendar components by borrowing the actual preceding month. The borrowed month length depends on the reference calendar. | Substitutes anniversary clamp. |
| 25 | `temporal-birthday-nearest`: `optional<BirthdayChoice> temporal_birthday_nearest(Date birth, Date as_of)` | Select the previous or next valid birthday anniversary by exact day distance. Prefer the previous anniversary on equal distance. | Substitutes day-of-year distance. |
| 26 | `temporal-milestone`: `optional<Date> temporal_milestone(Date birth, Date as_of, vector<int> ages)` | Select the first strictly increasing milestone anniversary not before a reference date. Reject invalid milestones and checked year overflow. | Substitutes age-only selection. |
| 27 | `temporal-majority-epoch`: `optional<int64_t> temporal_majority_epoch(Date birth, int majority_years, int utc_offset_minutes)` | Construct a majority anniversary and translate its local midnight through a fixed offset. The leap policy and checked UTC-minute conversion are explicit. | Substitutes 365-day years. |
| 28 | `temporal-cohort-cutoff`: `optional<int64_t> temporal_cohort_cutoff(Date birth, int cutoff_month, int cutoff_day)` | Assign a cohort year using a validated month/day cutoff. The cutoff's leap-day behavior is explicit. | Substitutes birth-year only. |
| 29 | `temporal-actuarial`: `optional<int64_t> temporal_actuarial(ActuarialBirth birth, Date as_of)` | Round age to the nearer birthday using exact calendar-day distance. Exact midpoint ties round down. | Substitutes six-month rule. |
| 30 | `temporal-gestational`: `optional<WeekDayAge> temporal_gestational(Date start, Date as_of)` | Convert exact elapsed Gregorian days to completed weeks and days. Only the documented 0-45 week range is valid. | Substitutes field subtraction. |
| 31 | `temporal-age-fraction`: `optional<Fraction> temporal_age_fraction(Date birth, Date as_of)` | Represent exact elapsed days in mean Gregorian years as a reduced rational. Use the exact 146097/400 factor and no floating point. | Substitutes 365-day quotient. |
| 32 | `temporal-age-band`: `optional<size_t> temporal_age_band(Date birth, Date as_of, vector<int64_t> thresholds)` | Locate completed age within strictly increasing thresholds. Thresholds and dates are validated before upper-bound selection. | Substitutes raw year difference. |
| 33 | `temporal-age-series`: `optional<vector<int64_t>> temporal_age_series(Date birth, vector<Date> events)` | Compute completed age for a nondecreasing sequence of event dates. Reject disorder transactionally and advance only at anniversaries. | Substitutes year subtraction. |
| 34 | `temporal-eligibility`: `optional<DateRange> temporal_eligibility(Date birth, int minimum_age, int maximum_age)` | Construct a half-open date range between two age anniversaries. Minimum age is inclusive and maximum age exclusive. | Substitutes inclusive upper endpoint. |
| 35 | `temporal-leapling-count`: `optional<int64_t> temporal_leapling_count(Date birth, Date through)` | Count policy-observed birthdays over a date interval without day iteration. Common-year observations count under the selected policy. | Substitutes leap-years only. |
| 36 | `temporal-retirement`: `optional<Date> temporal_retirement(Date birth, int retirement_years)` | Add retirement years while preserving an original month-end relationship. Non-month-end dates clamp only when the target date is invalid. | Substitutes numeric day preservation. |
| 37 | `temporal-sibling-gap`: `optional<AgeParts> temporal_sibling_gap(Date first, Date second)` | Return the canonical calendar gap between two birth dates. Order is normalized and actual month lengths are borrowed. | Substitutes 365/30 conversion. |
| 38 | `temporal-completed-months`: `optional<int64_t> temporal_completed_months(MonthlyAnniversaryBirth birth, Date as_of)` | Count completed monthly anniversaries with day clamping. Subtract one when the reference precedes the clamped monthly anniversary. | Substitutes year-month difference. |
| 39 | `temporal-iso-weeks`: `optional<int64_t> temporal_iso_weeks(Date start, Date finish)` | Count complete seven-day periods between valid dates. Use exact Gregorian day difference across ISO year boundaries. | Substitutes week-label subtraction. |
| 40 | `temporal-century-birthdays`: `optional<vector<Date>> temporal_century_birthdays(Date birth, Date begin, Date end)` | Enumerate 100-year anniversaries within a half-open date range. Use checked 100-year steps and the documented leap policy. | Substitutes year-suffix scan. |

## Root Inventory: Checked Large-Range Arithmetic (41-60)

| # | Task ID and public API | Core mechanism and boundary contract | Coherent wrong substitute rejected |
|---:|---|---|---|
| 41 | `temporal-checked-add`: `optional<int64_t> temporal_checked_add(int64_t value, int64_t offset)` | Add a signed offset to a timestamp without signed overflow. No overflowing expression is evaluated. | Substitutes post-add check. |
| 42 | `temporal-compose-duration`: `optional<int64_t> temporal_compose_duration(DurationParts parts)` | Compose validated day/hour/minute/second fields with checked Horner arithmetic. Reject invalid component ranges and every intermediate overflow. | Substitutes independent products. |
| 43 | `temporal-exact-ratio`: `optional<int64_t> temporal_exact_ratio(int64_t value, uint64_t numerator, uint64_t denominator)` | Scale a signed value by a positive rational only when the mathematical result is integral. Reduce factors before multiplication and reject a zero denominator. | Substitutes multiply first. |
| 44 | `temporal-saturating-add`: `SaturatedShift temporal_saturating_add(int64_t value, int64_t offset)` | Shift a timestamp with explicit lower/upper saturation status. Detect overflow before addition. | Substitutes overflowing clamp. |
| 45 | `temporal-bounded-add`: `optional<int64_t> temporal_bounded_add(int64_t value, int64_t offset, int64_t lower, int64_t upper)` | Shift within caller-provided closed epoch bounds. Reject invalid bounds, arithmetic overflow, and out-of-range results without clamping. | Substitutes clamped bounds. |
| 46 | `temporal-day-product`: `optional<int64_t> temporal_day_product(int64_t days)` | Convert signed days to seconds with predivision multiplication bounds. INT64_MIN is handled without absolute value. | Substitutes absolute-value check. |
| 47 | `temporal-join-nanos`: `optional<int64_t> temporal_join_nanos(int64_t seconds, int32_t nanos)` | Join canonical seconds and nanoseconds into one signed nanosecond count. Nanoseconds must already be in [0, 1e9). | Substitutes implicit normalization. |
| 48 | `temporal-euclidean-div`: `optional<DivResult> temporal_euclidean_div(int64_t dividend, int64_t divisor)` | Divide a signed epoch by a positive unit with nonnegative remainder. The operation is defined for INT64_MIN. | Substitutes C++ truncation. |
| 49 | `temporal-affine-map`: `optional<int64_t> temporal_affine_map(int64_t sample, int64_t origin, int64_t numerator, int64_t denominator)` | Map a timestamp through a rational affine clock relation. Reduce factors, round nearest-even, and reject every overflow. | Substitutes double arithmetic. |
| 50 | `temporal-transactional-sum`: `bool temporal_transactional_sum(int64_t start, vector<int64_t> deltas, int64_t output)` | Apply signed deltas in order and commit only when every prefix is representable. Late failure leaves output unchanged. | Substitutes partial commit. |
| 51 | `temporal-overflow-frontier`: `optional<int64_t> temporal_overflow_frontier(int64_t start, vector<int64_t> deltas)` | Return the first signed-add prefix that would overflow. Distinguish index zero from no overflow. | Substitutes final-sum check. |
| 52 | `temporal-interval-shift`: `optional<Interval> temporal_interval_shift(Interval input, int64_t offset)` | Shift both endpoints of a valid half-open interval atomically. Reject invalid input, endpoint overflow, or inverted output. | Substitutes partial endpoint shift. |
| 53 | `temporal-range-rescale`: `optional<Interval> temporal_range_rescale(Interval input, int64_t numerator, int64_t denominator)` | Rescale a half-open interval by a positive rational with floor lower and ceil upper endpoints. Reject zero denominator and endpoint overflow. | Substitutes toward-zero endpoints. |
| 54 | `temporal-weighted-centroid`: `optional<int64_t> temporal_weighted_centroid(vector<WeightedStamp> samples, int64_t pivot)` | Compute a positive-weight timestamp centroid around a pivot. Use checked weighted deltas and nearest-even rounding. | Substitutes absolute products. |
| 55 | `temporal-interpolate`: `optional<int64_t> temporal_interpolate(int64_t begin, int64_t end, uint64_t numerator, uint64_t denominator)` | Interpolate a rational fraction between ordered timestamps. The fraction is in [0,1], factors are reduced, and overflow is rejected. | Substitutes direct difference product. |
| 56 | `temporal-nth-occurrence`: `optional<int64_t> temporal_nth_occurrence(int64_t first, int64_t period, uint64_t ordinal)` | Compute the one-based nth occurrence of a positive-period recurrence. Use (n-1), reject n=0, and check multiply-add. | Substitutes n-times period. |
| 57 | `temporal-backoff`: `optional<int64_t> temporal_backoff(int64_t start, int64_t base, uint32_t attempts, int64_t cap)` | Compute a doubling backoff capped before adding it to a start time. Reject negative base/cap and checked deadline overflow. | Substitutes left-shift wrap. |
| 58 | `temporal-arithmetic-sum`: `optional<int64_t> temporal_arithmetic_sum(int64_t first, int64_t difference, uint64_t count)` | Sum a finite arithmetic duration schedule by factor cancellation. Reject negative terms and every unrepresentable intermediate. | Substitutes closed-form overflow. |
| 59 | `temporal-dot-product`: `optional<int64_t> temporal_dot_product(vector<int64_t> durations, vector<int64_t> counts)` | Compute a signed duration/count dot product with checked terms and accumulation. Lengths must match and failure is transactional. | Substitutes unsigned accumulator. |
| 60 | `temporal-window-count`: `optional<uint64_t> temporal_window_count(int64_t begin, int64_t end, uint64_t width)` | Count aligned half-open windows between signed endpoints. Avoid signed end-start overflow and reject zero width or reversed endpoints. | Substitutes signed subtraction. |

## Root Inventory: Rollover, Calibration, And Ordering (61-80)

| # | Task ID and public API | Core mechanism and boundary contract | Coherent wrong substitute rejected |
|---:|---|---|---|
| 61 | `temporal-unwrap32`: `optional<vector<int64_t>> temporal_unwrap32(vector<uint32_t> raw, int64_t first)` | Lift raw 32-bit ticks to nearest consecutive absolute ticks. Reject exact half-range ambiguity. | Substitutes decrease-means-rollover. |
| 62 | `temporal-unwrap16`: `optional<vector<int64_t>> temporal_unwrap16(vector<uint16_t> raw, int64_t first, uint32_t max_step)` | Lift each raw 16-bit tick to the unique candidate within a step bound. Reject zero bounds, ambiguity, and missing candidates. | Substitutes unbounded nearest lift. |
| 63 | `temporal-serial-order`: `SerialRelation temporal_serial_order(uint32_t left, uint32_t right)` | Compare 32-bit serials by modular half-range ordering. Distance 2^31 is explicitly unordered. | Substitutes ordinary unsigned order. |
| 64 | `temporal-gps-sequence`: `optional<vector<int64_t>> temporal_gps_sequence(vector<uint16_t> weeks, int64_t first_absolute)` | Unwrap a nondecreasing sequence of ten-bit GPS weeks. Each lift is relative to the prior absolute week and at most 512 weeks ahead. | Substitutes fixed pivot resolution. |
| 65 | `temporal-reset-segments`: `optional<vector<size_t>> temporal_reset_segments(vector<int64_t> timestamps, uint64_t tolerance)` | Partition input-order timestamps when backward movement exceeds tolerance. Do not sort or discard stable indices. | Substitutes sort first. |
| 66 | `temporal-two-point-calibration`: `optional<Calibration> temporal_two_point_calibration(ClockSample first, ClockSample second)` | Reduce a positive rational wall/monotonic slope from two samples. Monotonic deltas must be positive and intercept arithmetic checked. | Substitutes integer slope. |
| 67 | `temporal-piecewise-offset`: `optional<int64_t> temporal_piecewise_offset(int64_t instant, vector<OffsetStep> steps)` | Apply the last offset transition not after an instant. Validate strict transition ordering and checked addition. | Substitutes nearest step. |
| 68 | `temporal-median-offset`: `optional<int64_t> temporal_median_offset(vector<ClockSample> samples)` | Compute the deterministic lower median of checked wall-minus-monotonic offsets. Reject empty or overflowing differences and preserve input. | Substitutes mean offset. |
| 69 | `temporal-drift-envelope`: `bool temporal_drift_envelope(vector<ClockSample> samples, uint64_t max_ppm)` | Validate every adjacent clock-delta ratio against a positive rational envelope. Use integer quotient/remainder comparison and reject disorder. | Substitutes floating endpoint check. |
| 70 | `temporal-packet-order`: `optional<vector<size_t>> temporal_packet_order(vector<PacketStamp> packets)` | Order disjoint uncertainty intervals while preserving order for overlaps and ties. Reject negative uncertainty and endpoint overflow. | Substitutes center sort. |
| 71 | `temporal-watermark`: `optional<int64_t> temporal_watermark(vector<SourceTime> sources, int64_t allowed_lateness, int64_t previous)` | Choose the minimum checked last-seen-minus-lateness across active initialized sources. Any missing active source blocks the watermark. | Substitutes maximum/ignore missing. |
| 72 | `temporal-tolerance-dedup`: `optional<vector<int64_t>> temporal_tolerance_dedup(vector<int64_t> sorted, uint64_t tolerance)` | Keep the first item of each tolerance-connected run in sorted input. Connectivity compares adjacent input items, not only retained representatives. | Substitutes last-kept comparison. |
| 73 | `temporal-delta2`: `optional<vector<int64_t>> temporal_delta2(int64_t first, int64_t first_delta, vector<int64_t> delta2)` | Reconstruct deltas and timestamps through two checked accumulators. Failure leaves no partial decoded output. | Substitutes direct timestamp addition. |
| 74 | `temporal-gap-runs`: `optional<vector<GapRun>> temporal_gap_runs(vector<int64_t> timestamps, uint64_t threshold)` | Classify adjacent gaps and coalesce consecutive equal classes. Validate thresholds and sorted input. | Substitutes timestamp classification. |
| 75 | `temporal-bucket-index`: `optional<int64_t> temporal_bucket_index(int64_t instant, int64_t anchor, uint64_t width)` | Compute a Euclidean bucket index relative to an anchor. Avoid signed subtraction overflow and reject zero width. | Substitutes truncating difference. |
| 76 | `temporal-slew-distribution`: `optional<vector<int64_t>> temporal_slew_distribution(int64_t correction, uint64_t steps)` | Distribute a signed correction over steps so the exact sum is preserved and prefix error is bounded. Reject zero steps and avoid front/back loading the whole correction. | Substitutes last-step correction. |
| 77 | `temporal-quantize`: `optional<Quantized> temporal_quantize(int64_t value, uint64_t quantum)` | Round to the nearest positive bucket with ties to even and report signed error. Reject reconstruction overflow. | Substitutes half-up rounding. |
| 78 | `temporal-common-timebase`: `optional<CommonTick> temporal_common_timebase(uint64_t first_hz, uint64_t second_hz)` | Compute checked LCM and source multipliers for two positive timebases. Divide by GCD before multiplication. | Substitutes multiply first. |
| 79 | `temporal-tagged-era`: `optional<int64_t> temporal_tagged_era(EraStamp stamp)` | Translate one of three explicit epoch tags to Unix seconds. Validate tag-specific alignment and checked offsets. | Substitutes all tags Unix. |
| 80 | `temporal-euclidean-shard-key`: `optional<ShardKey> temporal_euclidean_shard_key(int64_t instant, int64_t anchor, uint64_t width, uint32_t shard_count)` | Compute Euclidean time bucket, nonnegative shard, and checked bucket origin. Reject zero shard count and avoid negative C++ remainders. | Substitutes raw remainder. |

## Files, Metadata, And Provenance

Each root contains the following roles:

```text
.docs/introduction.md                 prompt-visible context
.docs/instructions.md                 prompt-visible complete contract
.meta/config.json                     private role map
.meta/provenance.json                 private clean-room/new-root lineage
.meta/tests.toml                      private named coverage inventory
.meta/example.h                       private complete reference replacement
.meta/negative.h                      private coherent wrong replacement
.meta/task_hidden_test.cpp            private deterministic oracle
<task-id>.h                           sole editable starter
task_visible_test.cpp                 non-editable visible behavior test
CMakeLists.txt                        non-editable strict C++17 build
```

`files.solution`, `files.example`, and `files.test` must be safe, relative,
role-disjoint, present, and order-aligned. Provenance binds this curriculum,
the selected prompts, owner, task-spec version, clean-room origin, new-root
lineage, count-plan cell, and the statement `dataset_handoff: not_requested`.

## Test And Oracle Contract

Every visible test covers a normal example and a public boundary. Every hidden
test covers invalid input, the named overflow/rounding/ordering boundary, and
at least one deterministic property or inverse/model comparison. Normal and a
fresh ASan/UBSan configuration must each discover exactly two positive CTest
entries and pass the reference. The negative replacement must compile with the
same `-Wall -Wextra -Wpedantic -Werror` flags and fail at least one of the same
two tests in both configurations. Zero discovery, unequal counts, a compiling
failure used as a discriminator, or a sanitizer-only failure is a hard failure.

The repository-pinned image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
is the mandatory network-disabled Docker sanity environment. It is
`docker_sanity`, not a family-designated locked oracle. Receipts bind the live
tree, deterministic archive, mounted tree, owner, curriculum, prompts,
references, tests, negatives, compiler path/version/hash, CMake version,
commands, image ID, and `network_policy: none`.

## Diversity And Adversarial Clone Controls

The owner rereads the emitted docs, public header, reference, visible/private
tests, and negative fixture. It computes all 3,160 unordered task pairs over
the exact seven dimensions. Each dimension has its own normalized artifact
scope, feature set, overlap, symmetric difference, threshold, witnesses, and
decision. A pair passes only if all seven decisions pass.

Three coherent controls are generated from one emitted root beneath family
`.state/controls/`: a domain/identifier rename; a constants-or-policy-only
variant; and an opposite-end/rounding-selection variant. Each control must
change nonempty files, retain correct internal filenames/metadata, compile,
and pass its own adjusted behavior tests in normal and sanitizer modes. The
production pair evaluator must nevertheless reject it as a semantic clone in
every required dimension. Focused tests independently tokenize emitted files,
recompute the exact root/pair/dimension counts, inspect per-dimension decisions,
and verify that controls changed files and were rejected; they may not trust a
top-level production `pass` boolean.

## Cross-Tree And Benchmark Screening

Before materialization and before every verification, freeze sorted real-root
inventories for the legacy, reverify, and expansion trees, excluding all
`.state` paths. Reject any duplicate task ID, normalized prompt, reference,
test suite, public API, or semantic lineage. Compare all candidate artifact
roles with every bound official C++ holdout after removing comments, strings,
literals, identifiers, and domain nouns while retaining arity, operators,
control flow, and assertions. Missing holdout content is `not_completed`, not
a pass. No `--force` option may weaken these checks.

## Creator, Audit, And Remediation Evidence

The owner preserves raw proposals, selected roots, rejected roots, inventories,
manifests, screens, receipts, and append-only cycle records separately under
the family `.state/`. Creator preflight is owner regeneration, focused tests,
prompt/role checks, exact 80 count, 3,160-by-seven diversity proof, three clone
controls, cross-tree and holdout screens, host iteration when available, and
mandatory Docker normal/sanitizer/negative evidence.

An independent read-only `audit-sft-data-quality` pass then catalogs all 80
roots and issues stable findings. Any finding is routed through
`aider-task-family-remediation`, assigned `repair-in-place`, `replace`, or
`reject`, fixed only in this curriculum/owner/tests, and followed by full
regeneration plus a fresh audit. A rejected root is backfilled by a new
contract so exactly 80 passing roots remain. Only a clean fresh audit of the
exact final tree may record `local_family_verified`.

## Acceptance And Non-Claims

Cycle 002's immutable independent audit is
`docs/aider-tasks-spec/aider-dates-and-clocks/epoch-age-overflow-boundaries-audit-cycle-002.md`
(SHA-256 `43ef5dca466ccdbdc98e48c0d8d1d1a4fd916807e31d1c6ef95ba274edda22c7`).
Cycle 003 routes AEO-C02-F001 through AEO-C02-F005. It replaces the five
clone-admitted IDs with `temporal-epoch-range-intersection`,
`temporal-era-consensus`, `temporal-leap-table-digest`,
`temporal-signed-duration-parts`, and `temporal-age-threshold-date`; repairs
the other 75 roots; uses one 0.95 decision threshold with alpha-normalized
ordinary identifiers for candidates and controls; binds exact sorted legacy,
reverify, sibling-expansion, and holdout inventories; removes the warning
suppression; and makes UBSan nonrecovering with halt-on-error diagnostics.
The packet uncertainty, active-source watermark, adjacent-run deduplication,
and delta-of-delta decoding contracts receive executable substitute
discriminators. Cycle 003 remains pending until a fresh independent audit of
its exact regenerated subject closes every finding.

Cycle 003's independent report is immutable at
`docs/aider-tasks-spec/aider-dates-and-clocks/epoch-age-overflow-boundaries-audit-cycle-003.md`
(SHA-256 `2b1f767ecd936f2bbbb7d9773b7933a878cff54403e0657c86a085fb5dc1707a`).
Cycle 004 routes AEO-C03-F001 through AEO-C03-F004 by making the opposite-end
control's public contract and exact-boundary oracle agree with its code,
re-freezing the live sibling inventory, replacing packet interval sorting with
a checked stable topological order that rejects contradictory overlap
constraints, and adding unsigned-magnitude rational cancellation plus
overflow-free month stepping for the remaining sanitizer counterexamples.

Cycle 004's independent report is immutable at
`docs/aider-tasks-spec/aider-dates-and-clocks/epoch-age-overflow-boundaries-audit-cycle-004.md`
(SHA-256 `db367251ee22c0c2b5774d95e4463702cded4907c504b1c50738329585407185`).
Cycle 005 routes AEO-C04-F001 and AEO-C04-F002 by adjusting both public
integer-range statements of the opposite-end control and by adding an
executable equal-date `INT64_MIN` fast path and hidden sanitizer discriminator
before civil-day conversion.

Cycle 005's independent report is immutable at
`docs/aider-tasks-spec/aider-dates-and-clocks/epoch-age-overflow-boundaries-audit-cycle-005.md`.
Cycle 006 resolves AEO-C05-F001 by changing the base task and control to use "pure-Euclidean partitioning" and "right-closed partitioning" respectively. The 80 regenerated roots pass all controls and dimension gates.

Cycle 006's independent report is immutable at
`docs/aider-tasks-spec/aider-dates-and-clocks/epoch-age-overflow-boundaries-audit-cycle-006.md`.

Cycle 007 routes the 2026-07-24 read-only expansion-remediation-team audit
(findings F001-F005 over subject tree
`ece690f095eb53bc4242eaaa7523a906119571c934ef2d7a463d303f7fc96c6e`) as
`repair-in-place` on the case renderer and owner. F001/F002: the emitted
instructions now state every rejection rule the hidden tests enforce (Excel
serial 0 and the reversed-date, validation, and bounds rules swept across the
family). F003: the hidden suites of `temporal-age-clamped`,
`temporal-age-feb28`, `temporal-birthday-nearest`, `temporal-exact-ratio`,
`temporal-filetime-split`, `temporal-reset-segments`,
`temporal-signed-duration-parts`, `temporal-step-lookup`,
`temporal-tolerance-dedup`, and `temporal-weighted-centroid` now pin each
root's core policy with assertions that reject the named negative fixture.
F004: raw year subtraction in the actuarial, leapling-count, age-borrowed,
sibling-gap, age-series, age-band, and completed-months references uses
checked arithmetic. F005: `rejected-roots.json` preserves the five cycle-003
replacement lineages, cycle-suffixed remedy records use remedy-v1 vocabulary
with `remedy_spec_path`/`remedy_spec_hash`, the generator manifest reports a
current status, and the inventory tables above list the current binding IDs
and public APIs. Campaign verification is host-only by team gate; fresh Docker
sanity evidence is `not_completed (campaign gate: host verify only)`.

Acceptance requires exactly 80 retained roots; zero unresolved audit findings;
zero retained review/repair/conflict/contamination dispositions; current
normal, sanitizer, negative, prompt, role, diversity, clone-control,
cross-tree, and holdout evidence; and an audit subject hash matching the live
tree. The terminal claim is no stronger than `local_family_verified`.

No local completion creates SFT rows, tokenizer/mask evidence, a split, a
dataset release, export, training authorization, model response, or benchmark
uplift.

## Docs Alignment (Remediation Docs Phase)

The model-facing `.docs` follow the official Aider Polyglot C++ conventions.
`.docs/introduction.md` is a `# <Title>` header plus a domain-motivating
narrative shared per curriculum group (epoch-codec, human-age,
checked-arithmetic, rollover-order); it never states the contract or mentions
the evaluation harness. `.docs/instructions.md` keeps the `# Instructions`
header, states the signature, the complete behavioral contract (every rule the
private tests enforce), and a `## Examples` section rendering the visible
checks as concrete input/output cases. The named negative fixture is expressed
as a natural requirement ("using <substitute> does not satisfy the rules
above"), never as anti-cheat scaffolding; the constraint itself is unchanged.
The generator's focused test asserts this docs shape and rejects meta/audit
vocabulary in both docs files.
