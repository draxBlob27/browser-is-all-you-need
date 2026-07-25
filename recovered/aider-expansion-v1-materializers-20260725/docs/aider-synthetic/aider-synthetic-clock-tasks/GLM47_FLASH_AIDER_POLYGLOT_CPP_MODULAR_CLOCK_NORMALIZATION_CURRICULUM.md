# Modular Clock Normalization, Wraparound, And Signed Offsets Curriculum

Status: executable clean-room creation contract for exactly 60 new local task
roots in the binding `Time/date` count-plan cell “Modular clock
normalization, wraparound, and signed offsets.” This document is the output of
`docs/aider-tasks-spec/prompts/generate-family-spec.md`. It creates no SFT rows,
release, training authorization, or benchmark-uplift claim.

## Identity and output boundary

- Family ID: `aider-expansion-modular-clock-normalization-v1`.
- Lineage: every retained root is a new root with no parent or replacement.
- Owner: `src/w8_biayn/integrations/moonlight_modular_clock_normalization_aider_tasks.py`.
- Focused test: `tests/test_moonlight_modular_clock_normalization_aider_tasks.py`.
- Generated family root:
  `.w8-biayn/data/aider-tasks-expansion-v1/time-date/modular-clock-normalization/`.
- Mutable evidence root: the generated family root's `.state/` directory.
- Count: exactly 60 retained roots; controls, rejected proposals, and `.state`
  records never count.

The owner must refuse both existing generated trees as outputs, refuse every
path outside the named expansion family, reject symlinks/hardlinks into either
existing tree, and reject any ID or semantic lineage already present in the
legacy, reverify, or expansion inventories. Forced regeneration may replace
only owner-matching roots in this family and must invalidate prior receipts.

## Behavior contract

The model receives visible instructions plus exactly two task-named editable
C++17 files and returns complete replacements for both files. References,
tests, CMake, provenance, contracts, manifests, receipts, and clone controls
remain private. All arithmetic is integer, deterministic, offline, and
independent of host time, locale, time-zone databases, filesystems, and
networking.

Every root specifies a positive cycle or radix explicitly. Euclidean
normalization means `r = x mod p` with `0 <= r < p`, including negative `x`.
Checked multiplication/addition must reject overflow before mutation. Invalid
input returns the task's documented invalid result and leaves persistent state
unchanged. Caller ordering is preserved unless the contract names a different
stable tie rule.

The general-purpose Aider `clock` value-object contract is forbidden. No root
may expose constructor-plus-add/subtract/string behavior. The official
`clock`, `gigasecond`, and `meetup` tasks—and all other 26 official C++ roots—
are permanent holdouts.

## Exact root inventory

The declarations below are in namespace `curriculum`. Each class owns only the
state named in its row. `std::nullopt` or `valid=false` is the complete invalid
result; no partial output is returned unless the row explicitly names a valid
prefix diagnostic.

| # | Task ID and public API | Core mechanism and exact boundary policy | Coherent false substitute that tests must reject |
|---:|---|---|---|
| 1 | `mcn-euclidean-residue-ledger`: `ResidueLedger::fold(long long period, long long start, const vector<long long>& deltas) -> optional<Ledger{residue,wraps}>` | Reduce each delta before checked accumulation; count signed quotient crossings after every step. `period<=0` or noncanonical start is invalid. | C++ `%` used directly, producing a negative residue and wrong wrap count. |
| 2 | `mcn-balanced-phase-residue`: `BalancedResidue::normalize(long long value,long long period,Tie tie)->optional<long long>` | Map to the centered interval; for even periods choose `-p/2` or `+p/2` by `Tie`. | Always choose the positive half-period endpoint. |
| 3 | `mcn-anchored-cycle-window`: `AnchoredWindow::place(long long value,long long origin,long long period)->optional<Placement{value,cycle_index}>` | Return the unique representative in `[origin,origin+period)` plus mathematical floor quotient. | Truncating division for negative displacement. |
| 4 | `mcn-directed-phase-distance`: `DirectedDistance::measure(long long from,long long to,long long period)->optional<Distance{clockwise,counterclockwise,shortest,direction}>` | Both directed distances are nonnegative residues; exact ties use `Direction::counterclockwise`. | Linear absolute difference without wraparound. |
| 5 | `mcn-affine-phase-map`: `AffinePhaseMap::apply(long long phase,long long multiplier,long long shift,long long period)->optional<long long>` | Overflow-safe double-and-add modular multiplication followed by Euclidean shift. | Raw `multiplier*phase+shift`, which overflows. |
| 6 | `mcn-linear-congruence-rendezvous`: `CongruenceRendezvous::first(long long rate,long long target,long long period)->optional<Solution{exists,step,repeats}>` | Extended-GCD reduction of `rate*t == target (mod period)`; return least nonnegative solution and solution count. | Brute-force search capped before a full reduced period. |
| 7 | `mcn-paired-clock-crt`: `PairedClockCrt::combine(long long a,long long pa,long long b,long long pb)->optional<Solution{compatible,value,period}>` | Generalized two-modulus CRT with non-coprime compatibility and checked LCM. | Assume coprime moduli and multiply inverses unconditionally. |
| 8 | `mcn-tick-rate-resampler`: `TickRateResampler::map(long long tick,long long source_period,long long target_period,Rounding mode)->optional<Mapped{tick,remainder}>` | Scale one normalized phase by a rational period ratio using quotient/remainder and explicit floor/nearest-even rounding. | Integer-divide before multiplying, losing fractional phase. |
| 9 | `mcn-fractional-phase-accumulator`: stateful `FractionalPhaseAccumulator(period,numerator,denominator); advance(long long source_ticks)->Report{valid,phase,fraction}` | Maintain reduced fractional carry across calls; phase advances only on complete denominator units. Negative ticks use floor division. | Discard the fractional remainder on every call. |
| 10 | `mcn-mixed-period-flattener`: `MixedPeriodFlattener::flatten(const vector<long long>& digits,const vector<long long>& radices)->optional<Flat{index,period}>` and `expand(index,radices)` | Checked mixed-radix Horner flattening and exact inverse; every radix is at least two and every digit canonical. | Treat all positions as the final radix. |
| 11 | `mcn-signed-hms-normalizer`: `SignedHmsNormalizer::normalize(long long hours,long long minutes,long long seconds,long long day_hours)->optional<Hms{day, hour,minute,second}>` | Combine by checked operations, floor-divide by configurable day length, then expand base 60. | Borrow only one unit, failing multi-day negative values. |
| 12 | `mcn-film-timecode-carry`: `FilmTimecodeCarry::normalize(Timecode value,int fps,int hours_per_reel)->optional<Normalized{reel,code}>` | Cascade signed frame/second/minute/hour carries with configurable FPS and reel hours. | Normalize frames but forget to carry overflowing seconds. |
| 13 | `mcn-music-grid-normalizer`: `MusicGridNormalizer::normalize(Position value,int beats_per_bar,int ticks_per_beat)->optional<Position>` | Floor-carry signed ticks through beats into signed bars; bar is unbounded. | Clamp negative ticks instead of borrowing. |
| 14 | `mcn-shift-slot-subtick`: `ShiftSlotSubtick::normalize(long long shift,long long slot,long long subtick,int slots,int subticks)->optional<Coordinate>` | Heterogeneous two-level Euclidean carry with checked unbounded shift. | Apply `%` independently to slot and subtick without carries. |
| 15 | `mcn-weighted-phase-histogram`: `WeightedPhaseHistogram::fold(long long period,const vector<Sample>& samples)->optional<vector<Bucket>>` | Euclidean-normalize signed sample phases, aggregate equal phases with checked weight addition, elide zero totals, and return ascending buckets. | Overwrite an equal normalized phase with its latest weight instead of aggregating. |
| 16 | `mcn-heterogeneous-wheel-carry`: `WheelCarry::normalize(vector<long long> digits,const vector<long long>& radices)->optional<WheelState{outer,digits}>` | Right-to-left floor carry through per-wheel radices; the outer quotient remains signed. | Left-to-right carry, coupling the wrong wheels. |
| 17 | `mcn-quotient-remainder-duration`: `DurationQuotient::split(long long signed_units,const vector<long long>& unit_sizes)->optional<Parts{sign,magnitude}>` | Preserve a separate sign while expanding absolute magnitude through strictly descending divisible unit sizes; reject `LLONG_MIN`. | Normalize negative duration as a previous-cycle time of day. |
| 18 | `mcn-carry-trace-normalizer`: `CarryTraceNormalizer::normalize(vector<long long> digits,const vector<long long>& radices)->optional<Trace{digits,carries}>` | Record the exact floor carry emitted by every position while normalizing from least to most significant. | Return correct digits but fabricate zero carry evidence. |
| 19 | `mcn-bounded-era-phase`: `BoundedEraPhase::advance(EraPhase start,long long delta,long long period,long long min_era,long long max_era)->Report` | Normalize phase and checked era quotient atomically; out-of-era advance rejects without mutation. | Clamp the era at a boundary while still changing phase. |
| 20 | `mcn-sparse-unit-canonicalizer`: `SparseUnitCanonicalizer::normalize(const vector<Term>& terms,const vector<Unit>& basis)->optional<vector<Term>>` | Validate an acyclic integral conversion chain, accumulate checked base units, and emit canonical largest-to-smallest nonzero terms. | Sort terms by label without performing conversion or carries. |
| 21 | `mcn-claimed-wrap-validator`: `ClaimedWrapValidator::validate(const vector<Reading{phase,wrap}>&,long long period)->Report{valid,bad_index,absolute}` | Verify canonical phases and nondecreasing exact absolute readings derived from claimed wrap counters. | Trust wrap counters without checking phase drops or absolute order. |
| 22 | `mcn-monotone-phase-unwrapper`: `MonotonePhaseUnwrapper::unwrap(const vector<long long>& phases,long long period)->optional<vector<long long>>` | Choose the smallest nondecreasing absolute representative for each phase. | Add one period on every sample rather than only when required. |
| 23 | `mcn-bounded-jump-unwrapper`: `BoundedJumpUnwrapper::unwrap(phases,period,max_step)->Report{valid,bad_index,values}` | At each sample choose the unique forward representative within `[0,max_step]`; reject absent or ambiguous choices. | Always choose the smallest forward delta even when above the bound. |
| 24 | `mcn-directed-phase-unwrapper`: `DirectedPhaseUnwrapper::unwrap(const vector<Sample{phase,direction}>&,period)->optional<vector<long long>>` | Each edge chooses the least strictly positive/negative representative according to its direction; stationary is explicit. | Ignore direction hints and always unwrap forward. |
| 25 | `mcn-nearest-anchor-unwrapper`: `NearestAnchorUnwrapper::place(phases,anchors,period,Tie)->optional<vector<long long>>` | Independently choose the representative nearest each absolute anchor; exact ties use the supplied global tie. | Anchor only the first sample and propagate monotonically. |
| 26 | `mcn-sensor-phase-aligner`: `SensorPhaseAligner::align(const vector<Sensor{phase,offset}>&,period)->optional<vector<Aligned>>` | Subtract each calibrated signed offset, normalize to reference phase, and stable-sort by phase then original index. | Add offsets instead of subtracting them. |
| 27 | `mcn-gap-aware-phase-unwrapper`: `GapAwareUnwrapper::unwrap(const vector<Sample{phase,missing_before}>&,period,max_per_step)->Report` | Bound total advance by `(missing_before+1)*max_per_step` and choose the unique minimum forward lift. | Ignore missing-sample multiplicity when checking the bound. |
| 28 | `mcn-reset-aware-phase-trace`: `ResetAwareTrace::unwrap(const vector<Event{phase,reset}>&,period)->optional<vector<Point{epoch,absolute}>>` | A reset starts a new epoch at the supplied canonical phase; otherwise unwrap monotonically within the epoch. | Treat every phase decrease as an implicit reset. |
| 29 | `mcn-jitter-filtered-unwrapper`: `JitterFilteredUnwrapper::unwrap(phases,period,backward_tolerance)->Report` | Small backward jitter preserves the epoch and absolute value decreases; larger drops create exactly one wrap. | Convert every negative delta into a wrap. |
| 30 | `mcn-modular-delta-codec`: `ModularDeltaCodec::encode(phases,period,Tie)->optional<vector<long long>>` and `decode(first,deltas,period)` | Encode shortest signed modular deltas with explicit half-period tie and prove exact normalized decode. | Encode raw linear subtraction, yielding nonminimal deltas. |
| 31 | `mcn-anchored-arc-splitter`: `AnchoredArcSplitter::split(Arc,long long anchor,long long period)->optional<vector<Segment>>` | Rotate an arc to anchor-relative coordinates and split only if it crosses the anchor cut; preserve half-open emptiness. | Split at numeric zero instead of the caller's anchor. |
| 32 | `mcn-cyclic-overlap-measurer`: `CyclicOverlapMeasurer::measure(Arc a,Arc b,long long period)->optional<Overlap{length,pieces}>` | Linearize each half-open arc into at most two pieces, intersect all pairs, and coalesce adjacency. | Compare endpoints linearly and miss wrapped overlap. |
| 33 | `mcn-periodic-cover-coalescer`: `PeriodicCoverCoalescer::coalesce(vector<Arc>,period)->optional<Cover{full,pieces}>` | Event-sweep coverage counts on one cycle, merging boundary-connected first/last pieces. | Merge sorted endpoints without tracking coverage depth. |
| 34 | `mcn-circular-gap-complement`: `CircularGapComplement::gaps(vector<Arc>,period)->optional<vector<Arc>>` | Coalesce coverage then emit complement gaps clockwise from the smallest uncovered phase; full/empty have explicit results. | Reverse covered intervals instead of computing complement. |
| 35 | `mcn-minimum-covering-arc`: `MinimumCoveringArc::cover(vector<long long> phases,long long period)->optional<Arc{start,end,length}>` | Sort unique phases, remove the largest clockwise gap, and break equal gaps by smallest resulting start. | Use linear min/max and ignore the boundary gap. |
| 36 | `mcn-boundary-aware-window`: `BoundaryAwareWindow::classify(phase,Window,period)->optional<Location{outside,start,inside,end}>` | Normalize phase and apply independently open/closed start/end semantics, including wrapped and equal-endpoint windows. | Treat every window as closed on both ends. |
| 37 | `mcn-anchor-relative-clipper`: `AnchorRelativeClipper::clip(vector<Arc>,anchor,horizon,period)->optional<vector<LinearSpan>>` | Project periodic arcs into the finite absolute window `[anchor,anchor+horizon)` and clip repeated occurrences. | Inspect only the occurrence containing the anchor. |
| 38 | `mcn-shifted-reservation-normalizer`: `ReservationNormalizer::shift(vector<Reservation{id,arc}>,offset,period)->optional<vector<Reservation>>` | Shift both endpoints, canonicalize wrapped arcs, preserve IDs/input order, and reject full-cycle ambiguity. | Shift only starts while leaving ends unchanged. |
| 39 | `mcn-circular-bin-rebalancer`: `CircularBinRebalancer::rebin(values,source_bins,target_bins)->optional<vector<Fraction{num,den}>>` | Distribute source-bin mass by exact overlap of rational cyclic bin boundaries; reduce fractions. | Assign each source bin wholly to its nearest target bin. |
| 40 | `mcn-cyclic-range-subtractor`: `CyclicRangeSubtractor::subtract(Arc source,const vector<Arc>& cuts,period)->optional<vector<Arc>>` | Coalesce cuts, subtract from source pieces, and return clockwise source-relative fragments. | Remove a fragment whenever any endpoint lies inside a cut. |
| 41 | `mcn-offset-day-quotient-board`: `OffsetDayBoard::render(reference,period,vector<Location{label,offset}>)->optional<vector<Reading{label,phase,day_delta}>>` | Euclidean-normalize each signed offset and retain the full mathematical day quotient, not only previous/same/next. | Clamp day delta to `-1..1`. |
| 42 | `mcn-offset-graph-consistency`: `OffsetGraphConsistency::solve(node_count,edges,period)->Report{consistent,bad_edge,potentials}` | BFS modular potentials per component; every edge must equal `to-from mod period`; roots use zero. | Check only cycle sums in the first connected component. |
| 43 | `mcn-canonical-offset-table`: `CanonicalOffsetTable::build(period,vector<Entry{label,offset}>)->optional<vector<Group>>` | Normalize offsets, reject duplicate labels, group equal residues, and order groups by residue with labels stable. | Deduplicate by raw offset before normalization. |
| 44 | `mcn-inverse-offset-resolver`: `InverseOffsetResolver::resolve(local,period,vector<Candidate{id,offset}>,optional<long long> day)->optional<vector<Instant>>` | Subtract each offset; optional day selects one absolute representative; results order by absolute then ID. | Add offset and return local phases as reference instants. |
| 45 | `mcn-offset-roundtrip-auditor`: `OffsetRoundtripAuditor::audit(vector<Record{reference,offset,local,day}>,period)->Report{valid,bad_index}` | Recompute checked absolute local `reference+offset`, compare quotient and residue exactly, and report first mismatch. | Compare only normalized residue and ignore day quotient. |
| 46 | `mcn-staged-offset-transition`: `StagedOffsetTransition::map(reference,period,initial_offset,vector<Change{at,new_offset}>)->Report` | Validate ordered absolute transitions and select the last change not after reference; detect local gaps/overlaps around each change. | Select transitions by normalized phase rather than absolute instant. |
| 47 | `mcn-variable-period-segment-map`: `VariablePeriodMap::locate(absolute_tick,vector<Segment{length,period}>)->optional<Position{segment,cycle,phase}>` | Prefix-scan checked finite segments; each has its own period and may contain partial final cycle. | Apply the first segment's period to the entire timeline. |
| 48 | `mcn-dual-cycle-rendezvous`: `DualCycleRendezvous::next(after,phase_a,period_a,phase_b,period_b)->optional<Solution{exists,tick,repeat}>` | Generalized CRT followed by checked ceiling lift strictly after `after`. | Return the base CRT representative even when not after the bound. |
| 49 | `mcn-reference-window-projector`: `ReferenceWindowProjector::project(local_arc,offset,reference_begin,reference_end,period)->optional<vector<Span>>` | Subtract offset and enumerate/clamp every periodic occurrence in an absolute reference window. | Project only normalized endpoints and lose repeated days. |
| 50 | `mcn-offset-equivalence-grouper`: `OffsetEquivalenceGrouper::group(vector<Source{id,offset,period}>,common_period)->optional<vector<Group>>` | Convert offsets only when source/common periods are commensurate; group by exact common-period residue. | Compare offsets after decimal scaling or raw equality. |
| 51 | `mcn-circular-l1-median`: `CircularL1Median::select(phases,period)->optional<Result{phase,cost}>` | Evaluate unique candidate phases with shortest-arc L1 cost; ties choose smallest phase. | Take the ordinary linear median. |
| 52 | `mcn-squared-phase-medoid`: `SquaredPhaseMedoid::select(phases,period,Tie)->optional<Result{index,cost}>` | Compute overflow-checked squared shortest-arc distances and choose an input medoid; tie by direction then index. | Compute distance from the arithmetic mean on a line. |
| 53 | `mcn-modular-mode-selector`: `ModularModeSelector::select(phases,period,anchor)->optional<Result{phase,count,distance}>` | Count normalized residues; maximize frequency, then minimize clockwise distance from anchor, then phase. | Break ties by smallest numeric phase only. |
| 54 | `mcn-shortest-enclosing-arc`: `ShortestEnclosingArc::enclose(weighted_phases,period,required_weight)->optional<Arc>` | Duplicated sorted sweep finds the shortest half-open clockwise arc reaching required weight; tie by start. | Use a fixed-size sliding count ignoring weights. |
| 55 | `mcn-largest-gap-clusterer`: `LargestGapClusterer::cluster(phases,period,cluster_count)->optional<vector<Cluster>>` | Cut the `k` largest circular gaps with deterministic gap/start ties and emit clockwise clusters. | Sort linearly and split into equal-sized chunks. |
| 56 | `mcn-nearest-free-phase`: `NearestFreePhase::choose(request,period,blocked,Tie)->optional<Result{found,phase,distance}>` | For periods at most one million, normalize/unique blocked phases, expand distance symmetrically, and resolve equidistant free phases by tie direction. | Search clockwise only. |
| 57 | `mcn-minimal-cycle-rotation`: `MinimalCycleRotation::canonical(values,period)->optional<Rotation{start,values}>` | Normalize entries then use Booth's algorithm for lexicographically minimal rotation; smallest start for periodic ties. | Sort values, destroying cyclic adjacency. |
| 58 | `mcn-rotation-invariant-deltas`: `RotationInvariantDeltas::canonical(phases,period)->optional<vector<long long>>` | Convert a cyclic phase sequence to clockwise deltas and choose the lexicographically minimal rotation of the delta word. | Canonicalize the phase values directly, which is not rotation invariant. |
| 59 | `mcn-dihedral-phase-canonicalizer`: `DihedralCanonicalizer::canonical(phases,period)->optional<Result{reflected,rotation,values}>` | Compare all rotations of normalized forward and reflected/reversed sequences; tie prefers nonreflected then smallest rotation. | Consider rotations but never reflections. |
| 60 | `mcn-modular-permutation-auditor`: `ModularPermutationAuditor::audit(multiplier,shift,period)->optional<Report{bijective,cycles,fixed_points}>` | Use gcd for bijectivity, then explicit visited-cycle decomposition of the affine permutation when bijective. | Declare every nonzero multiplier bijective. |

## Required implementation evidence

Every root must have task-named `.h`/`.cpp` starters, complete matching private
references, one visible and one hidden deterministic executable, one
strict-compiling coherent false substitute, C++17 strict-warning CMake, role
metadata, and clean-room provenance. Hidden tests cover empty, invalid,
duplicate/absent, exact boundary, negative, multi-wrap, ordering/tie, and
overflow behavior applicable to that contract. Stateful roots compare every
operation result and full observable state against an independent value model.

The owner must derive the seven mandatory diversity dimensions from actual
emitted docs, public API, reference, visible/private tests, and negative
fixture. It must compare all `60*59/2 = 1770` unordered pairs and require every
pair to be materially different in each dimension. Raw IDs, story nouns,
declared mechanism labels, and unequal hashes are inventory evidence only.

Three coherent controls are mandatory: a domain/identifier rename, a
constants-or-policy-only change, and an opposite-end selection change. Each
control must change emitted files, retain complete safe roles, compile, pass
its internally consistent normal and sanitizer behavior tests, and be rejected
by the exact production family evaluator in every dimension. Focused tests
must independently inspect all 1770 pair records, every per-dimension
decision, nonempty control mutations, and control rejection without trusting a
top-level pass bit.

Before materialization the owner must freeze both existing inventories and the
official 26-root holdout inventory. It must screen task IDs, prompt hashes,
reference hashes, normalized contracts/APIs/references/tests/oracle logic,
and semantic lineage across all three local trees. Any overlap rejects the
proposal; a renamed candidate cannot be retained.

Final creator preflight requires deterministic owner regeneration, focused
tests, prompt/whole-file boundaries, 60 positive normal and 60 equal fresh
ASan/UBSan task results in the pinned network-disabled repository sanity
image, rejection of all 60 false substitutes in both modes, coherent-control
execution, all-pairs diversity, and holdout/lineage screening. The receipt
binds owner, curriculum, focused test, inventories, tree, prompt, starter,
reference, tests, image, compiler, CMake, commands, policy, controls, and
results by digest.

## Acceptance and non-claims

Only a fresh read-only `audit-sft-data-quality` pass over the exact final tree
may close creation. Every audit finding receives a stable ID and immutable
report, then routes through `aider-task-family-remediation`, owner changes,
complete regeneration, remediation verification, and a new audit. A rejected
root requires a genuinely new backfill and the entire loop.

The strongest permitted terminal status is `local_family_verified` with
exactly 60 retained roots. Dataset handoff is `not_requested`: no JSONL,
token/mask evidence, split, release, export, training, or uplift follows from
local verification.
