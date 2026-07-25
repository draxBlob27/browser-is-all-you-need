# Modular Clock Normalization Independent Audit — Cycle 01

Status: **remediate**. Confirmed retained roots: **60**. Roots passing every
independent hard gate: **0** while the family-wide expansion-overlap screen and
the findings below remain open. Unresolved hard findings: **6**. The next gate
is owner-level remediation, complete regeneration, a new exact creator
preflight, and a fresh independent audit. This report does not admit SFT rows,
authorize training, or claim benchmark uplift.

## Frozen audit subject

This is a read-only audit of the exact generated task tree at:

`.w8-biayn/data/aider-tasks-expansion-v1/time-date/modular-clock-normalization`

| Evidence | Exact binding |
| --- | --- |
| Audit ID | `mcn-independent-audit-cycle-01-20260722` |
| Family ID | `aider-expansion-modular-clock-normalization-v1` |
| Retained root count | 60 |
| Generated task-file count | 840, excluding `.state/` |
| Creator tree hash | `sha256:178870b164782d3f1d59b076f388411f7e07e87077adbdc17fd42b2d938bafd3` |
| Creator receipt internal hash | `sha256:9f1bb2dc238b2e9895964a2f09285e01b1ac3d99b8987490470124fc044a40a7` |
| Creator receipt file SHA-256 | `sha256:49dfdfa44211cf6a4878640e0cac085bcfe3c4fa98cde2e597d44d369884c4eb` |
| Materialization manifest SHA-256 | `sha256:325bfacbcdfdcc3f639ba3ed7b190c7c632615e3fb704e54b241bf0c5f42ce20` |
| Selected-candidate manifest SHA-256 | `sha256:85c87362f8661e1c989556a92f047da189ced1634fdce61a37133beb606406a3` |
| Hard-rule screen file SHA-256 | `sha256:10255759217e9691fc6ecb965762240d5bd6a4be68a50a697537bdca5d1c6c11` |
| Source-inventory file SHA-256 | `sha256:f67afe91ebcd31fb505fe3771b25947322a7afc7410d71a2b1a70bbe88dad19d` |
| Owner aggregate hash | `sha256:12e9fa6c629ab95cd664115ac954f67639a0909348add2e9212701acda8f7645` |
| Curriculum hash | `sha256:750ab87d8907f2a4a70ff6ffc9a1f5e13b61088591293aaf4f66cb4595568ecf` |
| Focused-test hash | `sha256:4b47f59aa0c6c4dcf1aa886974568741530b3fb5328d0c0e91aec47761f35cf2` |

The tree hash and receipt internal hash were recomputed independently. All 60
live per-root tree hashes and all three live adversarial-control tree hashes
match their creator-receipt bindings. The receipt uses the digest-pinned image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
network policy `none`, GCC 13.4.0 at `/usr/local/bin/g++` with compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
and CMake 3.25.1. Its evidence class is truthfully `docker_sanity`, with
`locked_oracle=false`.

## Behavior contract

| Field | Audited contract |
| --- | --- |
| Task | Implement one of 60 distinct C++17 modular-clock normalization, wraparound, signed-offset, cyclic-range, or canonical-selection contracts. |
| Inputs | The visible task instructions and exactly two task-named editable files; deterministic integer inputs only. |
| Output | Complete whole-file replacements for both editable files. |
| Invariants | Positive periods where required; Euclidean residues; deterministic ordering and tie rules; checked arithmetic; invalid input and overflow do not expose partial mutation. |
| Failure behavior | The declared `nullopt`, invalid report, or atomic rollback result, without undefined behavior or hidden partial state. |
| Resource limits | Offline C++17 under the designated Docker sanity image; no host time, locale, timezone database, filesystem, or network. Any deliberately bounded algorithm must expose the bound in its contract. |
| Evaluation | Strict warnings, visible and hidden deterministic tests, a compiling plausible-but-wrong fixture rejected in normal and fresh ASan/UBSan builds, seven-dimension family screening, existing-tree screening, and the 26-root official holdout screen. |
| Generalization target | New clean-room mechanisms in the binding 60-root count-plan cell, not renamed domains, constants-only variants, opposite-end variants, existing-tree copies, or official Aider C++ roots. |

## Independent checks and quality gates

| Gate | Evidence | Result |
| --- | --- | --- |
| Exact count and root structure | 60 unique selected IDs; 14 files per root; role-safe config and new-root provenance | pass |
| Owner/materialization binding | Owner, curriculum, focused tests, all roots, and receipt hashes recomputed | pass |
| Focused structural tests | `9 passed` with bytecode and pytest cache disabled | pass |
| Prompt/reference boundary | Every prompt excludes reference, hidden test, negative fixture, CMake, provenance, and receipts; both whole-edit targets are mapped | pass |
| Creator Docker execution | 60 roots × 3 CTests in normal and sanitizer modes; every negative fixture rejected; three controls × 2 CTests in both modes | receipt-bound pass, but insufficient for the boundary defects below |
| Within-family diversity | All 1,770 unordered pairs recorded below the seven per-dimension limits | pass |
| Adversarial clone controls | domain/identifier rename, constants/policy-only, and opposite-end controls rejected in all seven dimensions and behavior-tested | pass |
| Exact IDs and exact hashes | 60 unique prompt hashes, 60 unique answer hashes, no legacy/reverify ID collision | pass |
| Existing-tree semantic overlap | 86,400 comparisons cover 731 legacy + 709 reverify roots, but omit the 1,560 non-subject expansion roots in the frozen 1,620-root expansion inventory | **fail** (`cycle-01/family/expansion-semantic-screen-omitted`) |
| Official benchmark contamination | 60 × 26 = 1,560 comparisons; strongest score 0.0690909 against `crypto-square` | pass |
| Reference correctness and overflow behavior | Independent source review plus exact UBSan counterexamples | **fail** (`cycle-01/family/signed-modular-overflow`) |
| Curriculum/reference mechanism agreement | Cyclic coalescing and generalized-CRT contracts disagree with retained references/tests | **fail** |
| Append-only cycle evidence | Cycles 01–09 are preserved, but cycle 09 is `creator_preflight_failed` and no later entry binds the passing receipt/current owner | **fail** (`cycle-01/family/passing-preflight-cycle-unrecorded`) |
| Dataset/token/mask/release gates | Not requested and outside local-family scope | not applicable |

## Stable findings and immutable dispositions

### `cycle-01/family/signed-modular-overflow`

- Severity: hard correctness and sanitizer-evidence failure.
- Disposition: `repair-and-reverify` for every affected root.
- Evidence: retained references perform signed addition/subtraction before
  modulo, or unchecked accumulator/lift arithmetic, on values that the public
  contracts permit near `LLONG_MAX`. This violates the curriculum-wide checked
  arithmetic and invalid-result contract and can execute undefined behavior.
- Independently executed counterexamples:
  - `DirectedDistance::measure(0, LLONG_MAX-1, LLONG_MAX)` terminates under
    non-recovering UBSan at `.meta/example.cpp:36` because
    `LLONG_MAX + (LLONG_MAX-1)` overflows in `(b-a+p)%p`.
  - `PairedClockCrt::combine(0, 1, LLONG_MAX-2, LLONG_MAX)` terminates under
    non-recovering UBSan at `.meta/example.cpp:36` because normalization adds
    the modulus to an already positive remainder.
- Affected roots found by direct reference review:
  `mcn-anchor-relative-clipper`, `mcn-anchored-arc-splitter`,
  `mcn-bounded-era-phase`, `mcn-bounded-jump-unwrapper`,
  `mcn-circular-l1-median`, `mcn-cyclic-range-subtractor`,
  `mcn-directed-phase-distance`, `mcn-dual-cycle-rendezvous`,
  `mcn-fractional-phase-accumulator`, `mcn-gap-aware-phase-unwrapper`,
  `mcn-inverse-offset-resolver`, `mcn-largest-gap-clusterer`,
  `mcn-minimum-covering-arc`, `mcn-modular-delta-codec`,
  `mcn-modular-mode-selector`, `mcn-monotone-phase-unwrapper`,
  `mcn-nearest-anchor-unwrapper`, `mcn-offset-day-quotient-board`,
  `mcn-offset-graph-consistency`, `mcn-offset-roundtrip-auditor`,
  `mcn-paired-clock-crt`, `mcn-reference-window-projector`,
  `mcn-reset-aware-phase-trace`, `mcn-rotation-invariant-deltas`,
  `mcn-sensor-phase-aligner`, `mcn-shifted-reservation-normalizer`,
  `mcn-shortest-enclosing-arc`, `mcn-squared-phase-medoid`, and
  `mcn-staged-offset-transition`.
- Required closure evidence: owner-level checked arithmetic or overflow-safe
  modular helpers, explicit extreme-value tests for each affected arithmetic
  pattern, complete regeneration, and current normal/fresh sanitizer/negative
  receipts. Remediation self-check cannot close this finding.

### `cycle-01/cyclic-range-family/boundary-coalescing-oracle-drift`

- Severity: hard contract/reference/test mismatch.
- Disposition: `repair-and-reverify` for `mcn-cyclic-overlap-measurer` and
  `mcn-periodic-cover-coalescer`.
- Evidence: curriculum row 32 requires adjacent cyclic intersection pieces to
  be coalesced. Its reference returns separately sorted intersections.
  Curriculum row 33 expressly requires merging boundary-connected first/last
  cover pieces. Its reference and visible test retain `{0, ...}` and
  `{..., period}` as two pieces. Thus the production test currently endorses a
  reference that contradicts the frozen curriculum.
- Required closure evidence: resolve the cyclic arc representation in the
  curriculum and prompt, implement the selected boundary merge, add positive
  first/last adjacency discriminators, regenerate, and rerun all evidence.

### `cycle-01/mcn-dual-cycle-rendezvous/crt-mechanism-not-implemented`

- Severity: hard core-mechanism and resource-profile failure.
- Disposition: `repair-and-reverify`.
- Evidence: curriculum row 48 requires generalized CRT followed by a checked
  strict-after ceiling lift. The retained reference instead increments `k`
  from zero through as many as `period_b/gcd` candidates. Small examples can
  pass, but the required CRT mechanism is absent and valid large periods have
  an unbounded linear scan. The existing wrong substitute and tests exercise
  only the final lift, not the required solver.
- Required closure evidence: implement generalized CRT, test compatible and
  incompatible non-coprime systems plus large periods without enumeration,
  retain checked lift behavior, regenerate, and rerun all evidence.

### `cycle-01/contracts/normalization-policy-drift`

- Severity: hard specification ambiguity.
- Disposition: `repair-and-reverify` for `mcn-modular-mode-selector` and
  `mcn-nearest-free-phase`.
- Evidence: curriculum row 53 says to count normalized residues, while the
  case boundary/reference reject noncanonical phase inputs. Curriculum row 56
  says to normalize and unique blocked phases, while the case
  boundary/reference reject noncanonical blocked entries. A model-facing task
  cannot be admitted while its normative curriculum and executable oracle
  disagree on valid input.
- Required closure evidence: select one policy per root, align curriculum,
  visible instructions, case definition, reference, and tests, then regenerate
  and reverify.

### `cycle-01/family/expansion-semantic-screen-omitted`

- Severity: hard duplicate/contamination gate failure.
- Disposition: `review` for all 60 roots until screened; any discovered match
  must become `repair-and-reverify`, `replace`, or `reject`.
- Evidence: the frozen source inventory records 731 legacy, 709 reverify, and
  1,620 expansion roots, including this 60-root subject. The semantic screen
  constructs comparison material only from legacy and reverify, exactly
  explaining its 86,400 comparisons (`60 × (731 + 709)`). It performs no
  semantic comparison against the other 1,560 expansion roots even though the
  creator contract and user scope require avoiding semantic duplicates of all
  existing generated trees. An ID inventory is not a semantic screen.
- Required closure evidence: snapshot and compare against all 1,560
  non-subject expansion roots under a declared policy, persist strongest and
  rejected matches, and bind the new inventory/policy/results into the fresh
  receipt.

### `cycle-01/family/passing-preflight-cycle-unrecorded`

- Severity: hard evidence-lineage failure.
- Disposition: family `repair-and-reverify`.
- Evidence: immutable creation-cycle records 01–09 are present. Cycle 09 binds
  owner hash `sha256:0eb3d8310723a0498b5637bdc64c0fbdcef8b47359af5994a74df603402f37a2`,
  state `creator_preflight_failed`, and finding
  `MCN-CREATOR-016-policy-control-oracle-drift`. The current passing receipt
  binds different owner hash
  `sha256:12e9fa6c629ab95cd664115ac954f67639a0909348add2e9212701acda8f7645`.
  No later append-only cycle records the passing preflight, its receipt hash,
  or the exact final tree, contrary to the iteration contract.
- Required closure evidence: preserve cycles 01–09, append the next cycle for
  the regenerated exact subject, and record the current creator receipt,
  findings, retained/rejected roots, audit subject, and terminal state.

## Row/root audit catalog

Every row has clean-room `new-root` lineage, a unique prompt and target hash,
two whole-edit files, visible/hidden deterministic tests, and a compiled
negative fixture in both recorded modes. `review` below means no root-specific
defect was established in this cycle, but the omitted expansion comparison is
a family-wide unresolved hard gate. `repair-and-reverify` takes precedence
where a root-specific finding exists.

| # | Root | Capability tags | Disposition | Finding |
| ---: | --- | --- | --- | --- |
| 1 | `mcn-euclidean-residue-ledger` | Euclidean residue, signed wraps | review | expansion screen |
| 2 | `mcn-balanced-phase-residue` | centered residue, tie policy | review | expansion screen |
| 3 | `mcn-anchored-cycle-window` | floor quotient, anchored interval | review | expansion screen |
| 4 | `mcn-directed-phase-distance` | directed distance, half-cycle tie | repair-and-reverify | signed overflow |
| 5 | `mcn-affine-phase-map` | modular multiplication, affine map | review | expansion screen |
| 6 | `mcn-linear-congruence-rendezvous` | gcd reduction, modular inverse | review | expansion screen |
| 7 | `mcn-paired-clock-crt` | generalized CRT, checked LCM | repair-and-reverify | signed overflow |
| 8 | `mcn-tick-rate-resampler` | rational scaling, nearest-even | review | expansion screen |
| 9 | `mcn-fractional-phase-accumulator` | stateful carry, floor division | repair-and-reverify | signed overflow |
| 10 | `mcn-mixed-period-flattener` | mixed radix, inverse mapping | review | expansion screen |
| 11 | `mcn-signed-hms-normalizer` | checked H:M:S carry | review | expansion screen |
| 12 | `mcn-film-timecode-carry` | heterogeneous frame carry | review | expansion screen |
| 13 | `mcn-music-grid-normalizer` | signed music-grid carry | review | expansion screen |
| 14 | `mcn-shift-slot-subtick` | nested Euclidean carry | review | expansion screen |
| 15 | `mcn-angular-dms-normalizer` | D:M:S revolution carry | review | expansion screen |
| 16 | `mcn-heterogeneous-wheel-carry` | mixed wheel carry | review | expansion screen |
| 17 | `mcn-quotient-remainder-duration` | signed magnitude decomposition | review | expansion screen |
| 18 | `mcn-carry-trace-normalizer` | carry evidence, mixed radix | review | expansion screen |
| 19 | `mcn-bounded-era-phase` | atomic state, bounded era | repair-and-reverify | signed overflow |
| 20 | `mcn-sparse-unit-canonicalizer` | conversion chain, sparse units | review | expansion screen |
| 21 | `mcn-claimed-wrap-validator` | claimed epoch validation | review | expansion screen |
| 22 | `mcn-monotone-phase-unwrapper` | monotone lift | repair-and-reverify | signed overflow |
| 23 | `mcn-bounded-jump-unwrapper` | unique bounded lift | repair-and-reverify | signed overflow |
| 24 | `mcn-directed-phase-unwrapper` | directed lift, stationary edges | review | expansion screen |
| 25 | `mcn-nearest-anchor-unwrapper` | absolute anchors, tie policy | repair-and-reverify | signed overflow |
| 26 | `mcn-sensor-phase-aligner` | signed calibration, stable order | repair-and-reverify | signed overflow |
| 27 | `mcn-gap-aware-phase-unwrapper` | missing-sample bound | repair-and-reverify | signed overflow |
| 28 | `mcn-reset-aware-phase-trace` | explicit reset epochs | repair-and-reverify | signed overflow |
| 29 | `mcn-jitter-filtered-unwrapper` | jitter tolerance, wrap detection | review | expansion screen |
| 30 | `mcn-modular-delta-codec` | shortest deltas, round trip | repair-and-reverify | signed overflow |
| 31 | `mcn-anchored-arc-splitter` | rotated half-open arcs | repair-and-reverify | signed overflow |
| 32 | `mcn-cyclic-overlap-measurer` | cyclic intersection, adjacency | repair-and-reverify | boundary coalescing |
| 33 | `mcn-periodic-cover-coalescer` | event sweep, cyclic coalescing | repair-and-reverify | boundary coalescing |
| 34 | `mcn-circular-gap-complement` | cover complement | review | expansion screen |
| 35 | `mcn-minimum-covering-arc` | largest-gap complement | repair-and-reverify | signed overflow |
| 36 | `mcn-boundary-aware-window` | open/closed cyclic boundary | review | expansion screen |
| 37 | `mcn-anchor-relative-clipper` | repeated arc projection | repair-and-reverify | signed overflow |
| 38 | `mcn-shifted-reservation-normalizer` | cyclic endpoint shift | repair-and-reverify | signed overflow |
| 39 | `mcn-circular-bin-rebalancer` | rational overlap rebinning | review | expansion screen |
| 40 | `mcn-cyclic-range-subtractor` | cyclic subtraction, source order | repair-and-reverify | signed overflow |
| 41 | `mcn-offset-day-quotient-board` | signed offset quotient | repair-and-reverify | signed overflow |
| 42 | `mcn-offset-graph-consistency` | modular graph potentials | repair-and-reverify | signed overflow |
| 43 | `mcn-canonical-offset-table` | residue grouping, stable labels | review | expansion screen |
| 44 | `mcn-inverse-offset-resolver` | inverse signed offsets | repair-and-reverify | signed overflow |
| 45 | `mcn-offset-roundtrip-auditor` | quotient/residue round trip | repair-and-reverify | signed overflow |
| 46 | `mcn-staged-offset-transition` | ordered transitions, gap/overlap | repair-and-reverify | signed overflow |
| 47 | `mcn-variable-period-segment-map` | checked segment prefix | review | expansion screen |
| 48 | `mcn-dual-cycle-rendezvous` | CRT, strict-after lift | repair-and-reverify | CRT mechanism; signed overflow |
| 49 | `mcn-reference-window-projector` | periodic absolute projection | repair-and-reverify | signed overflow |
| 50 | `mcn-offset-equivalence-grouper` | commensurate period grouping | review | expansion screen |
| 51 | `mcn-circular-l1-median` | circular L1 selection | repair-and-reverify | signed overflow |
| 52 | `mcn-squared-phase-medoid` | checked squared medoid | repair-and-reverify | signed overflow |
| 53 | `mcn-modular-mode-selector` | frequency, anchor ties | repair-and-reverify | signed overflow; normalization drift |
| 54 | `mcn-shortest-enclosing-arc` | weighted two-pointer arc | repair-and-reverify | signed overflow |
| 55 | `mcn-largest-gap-clusterer` | deterministic circular cuts | repair-and-reverify | signed overflow |
| 56 | `mcn-nearest-free-phase` | symmetric search, directional tie | repair-and-reverify | normalization drift |
| 57 | `mcn-minimal-cycle-rotation` | Booth rotation | review | expansion screen |
| 58 | `mcn-rotation-invariant-deltas` | cyclic difference word | repair-and-reverify | signed overflow |
| 59 | `mcn-dihedral-phase-canonicalizer` | rotation/reflection canonical form | review | expansion screen |
| 60 | `mcn-modular-permutation-auditor` | affine bijection cycles | review | expansion screen |

## Duplicate, lineage, and contamination report

- Exact within-family task IDs, prompt hashes, answer hashes, and the seven
  semantic-anchor tuples are unique for all 60 roots.
- The 1,770-pair ledger marks every retained pair materially distinct in all
  seven declared dimensions. The three adversarial clones are correctly
  rejected as duplicates in every dimension, and their behavior tests pass.
- No candidate ID collides with the frozen 731-root legacy or 709-root reverify
  inventories. All selected provenance records say `new-root` with no parent.
- The reverify snapshot contains 709 root records but only 694 unique leaf IDs;
  this does not collide with this family, and the path-qualified inventory
  preserves those pre-existing collisions.
- Official holdout coverage is complete for the 26 expected C++ roots. No exact
  or threshold contamination was reported; the strongest normalized score is
  low and unrelated by contract.
- Semantic non-duplication against the other frozen expansion roots is not
  established. That omission is a hard gate, not evidence that a duplicate
  exists. All 60 rows therefore remain at least `review` until the missing
  comparisons run.

## Corpus composition and limitations

The family intentionally has three equal 20-root tranches: normalization and
carry; sequence unwrapping and cyclic ranges; signed offsets, rendezvous, and
canonical selection. Interaction mode is two-file whole-edit C++17 throughout.
All roots are synthetic clean-room new roots with Docker-sanity receipts; this
uniform provenance is appropriate for the requested local family but is not a
claim about a future training mixture. Token length, assistant loss masks,
train/validation/test splits, release review, producer verification, export,
consumer verification, and model outcomes are outside this local-family audit
and were not inferred.

## Verdict

`remediate`. The exact frozen subject is structurally complete and has useful
creator execution evidence, but it cannot be designated
`local_family_verified`: retained references exhibit valid-input undefined
behavior, two cyclic coalescing oracles conflict with their curriculum, the
dual-cycle task does not implement its required CRT mechanism, two input
normalization policies are internally inconsistent, the expansion-tree
semantic screen is incomplete, and the passing creator preflight is absent
from the append-only cycle ledger. Preserve this report unchanged, route every
finding through owner-level remediation, regenerate the complete affected
family, and conduct a fresh audit of the new exact tree and receipt.
