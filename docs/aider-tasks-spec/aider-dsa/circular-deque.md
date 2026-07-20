# Circular Deque Family Remediation Audit

Selected prompt: `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`.
Scope: 20 immutable legacy roots and the parallel reverify family. Purpose:
local family remediation only.

## Findings and dispositions

### CDEQUE-001 — permanent-holdout semantic overlap

**Severity:** blocker

**Scope:** all 20 legacy roots.

**Observed evidence:** every root implements a fixed-capacity integer ring,
empty removal, full-write reject/evict, ordered removal, snapshot, and clear.
The permanent holdout specifies the same core state and behavior.

**Root cause:** one benchmark-adjacent template was multiplied by domain nouns.

**Remedy:** reject every legacy root and preserve its tree unchanged.

**Status:** resolved by rejection; the owner emits no rejected ID.

### CDEQUE-002 — family template duplication

**Severity:** major

**Scope:** all 20 legacy roots.

**Observed evidence:** normalized references collapse to the same ring control
flow with only removal-end and overflow toggles.

**Root cause:** task identity was based on names, not independent logic.

**Remedy:** use exactly 15 independent roots. The owner fails on count bounds,
root-specific false substitutes, and artifact-derived semantic overlap across
normalized docs, public API, reference source, and visible tests.

**Status:** resolved structurally: all 105 candidate pairs pass the v4 semantic
screen and all root-specific negative fixtures pass.

### CDEQUE-003 — unavailable host oracle prerequisites

**Severity:** note

**Scope:** legacy audit and replacement verifier.

**Observed evidence:** the host has `c++` but not `cmake`, so the repo-owned
host verifier correctly reports `oracle_not_completed`.

**Remedy:** use the repository-pinned C++ sanity image when no
family-designated locked runtime exists, run it with networking disabled, and
label the result `docker_sanity` rather than `locked_oracle`.

**Status:** resolved for local-family verification. The exact `docker run
--rm --network none` command in `.state/docker-sanity.json` used image
`sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
All 15 roots discovered and passed two tests in both clean normal and fresh
ASan/UBSan modes. This remains Docker sanity evidence, not a locked-oracle
claim.

### CDEQUE-004 — requested family count was undershot

**Severity:** major

**Scope:** the prior three-root reverify family.

**Observed evidence:** the user required at least 15 and at most 20 tasks; the
prior owner emitted three.

**Root cause:** the representative-sample judgment incorrectly treated the
count as optional.

**Remedy:** make 15–20 a binding owner/test/skill gate and expand to exactly 15
without weakening semantic diversity.

**Status:** resolved: the owner emits exactly 15 roots and focused tests enforce
the 15–20 bound plus hard diversity rule.

### CDEQUE-005 — label-based hard-rule verification loophole

**Severity:** blocker

**Scope:** the prior replacement-family duplicate screen and tests.

**Observed evidence:** the previous signature started with the task's unique
kind label, and its test fell back to that label. Unique names therefore made
the check pass before implementation logic was compared.

**Root cause:** metadata identity was treated as semantic evidence.

**Remedy:** derive comparisons only from normalized task artifacts and compare
all pairwise docs/API/reference/test combinations. Add adversarial clones that
rename the domain and identifiers, change constants/policy syntax, or reverse
deque ends; every clone must still be rejected.

**Status:** resolved. Normalizer `circular-deque-semantic-v4` checks 105 family
pairs and 15 holdout pairs. The strongest real family pair scores 0.417 below
the 0.78 rejection threshold; the strongest holdout pair scores 0.092 below
0.72. All three adversarial clone classes fail with `duplicate_family`.

## Structural matrix

| Root | Primary objective | Logic/implementation distinction | Disposition |
|---|---|---|---|
| all 20 legacy `cdeque-*` roots | bounded renamed ring | none; holdout-adjacent | reject |
| `deque-work-steal-scheduler` | owner/thief scheduling | dynamic owned ring and growth | repair-in-place |
| `deque-window-extrema` | streaming aggregation | two monotonic deques | repair-in-place |
| `deque-zero-one-router` | graph shortest paths | adjacency plus 0-1 BFS | repair-in-place |
| `deque-center-sequence` | center-index sequence operations | balanced halves | replace |
| `deque-prefix-expression` | recursive expression evaluation | token deque and checked recursion | replace |
| `deque-run-segment-editor` | normalized end editing | maximal run deque | replace |
| `deque-snake-arena` | body movement/collision | body deque plus occupancy set | replace |
| `deque-deficit-scheduler` | fair variable-cost service | active flows, per-flow queues, deficits | replace |
| `deque-temporal-join` | event-time pairing | two monotonic stream deques | replace |
| `deque-palindrome-fingerprint` | dynamic palindrome query | reversible hashes plus character deque | replace |
| `deque-chunked-text` | bounded chunk editing | string-chunk deque | replace |
| `deque-josephus-elimination` | circular elimination | directional rotation | replace |
| `deque-lexicographic-end-picker` | end-choice minimization | inward tie lookahead | replace |
| `deque-card-war-cycle` | deck simulation | paired decks plus state set | replace |
| `deque-stable-radix` | stable digit sorting | digit bucket deques | replace |

The prompt contains only docs and declared editable files. References, hidden
tests, metadata, CMake, receipts, and remedies stay private. Dataset handoff is
`not_requested`; this report makes no release or uplift claim.

## Per-root evidence

The original three roots use `repair-in-place` for the v3 expansion; the
twelve new roots use `replace`. Every record contains its exact before/after
tree hash and remedy-spec hash. `primary_core_objective: achieved` is
supported separately by a required-marker-removal fixture and a named
forbidden-substitute fixture for each root.

| Root | After tree hash | Distinct core | Prompt/family/holdout | Oracle/status |
|---|---|---|---|---|
| `deque-work-steal-scheduler` | `12050d8ee687...` | dynamic owner/thief ring | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-window-extrema` | `ea921ca6a191...` | dual monotonic extrema | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-zero-one-router` | `b9539cc4109f...` | 0-1 BFS relaxation | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-center-sequence` | `5654ed424b9d...` | balanced halves | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-prefix-expression` | `1e30265a56d0...` | recursive token parser | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-run-segment-editor` | `36f0e2627e55...` | maximal run normalization | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-snake-arena` | `f7fdd9433562...` | body plus occupancy index | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-deficit-scheduler` | `921452f7eee7...` | deficit round robin | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-temporal-join` | `4b3e331f1f22...` | two-stream greedy join | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-palindrome-fingerprint` | `7da6df23aaa0...` | reversible rolling hashes | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-chunked-text` | `934c8d69a617...` | bounded string chunks | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-josephus-elimination` | `f93391194cba...` | directional rotation | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-lexicographic-end-picker` | `084ccfd43bde...` | inward tie lookahead | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-card-war-cycle` | `e057bf52abb3...` | paired-state cycle simulation | pass/pass/pass | Docker sanity 2/2 modes; local family verified |
| `deque-stable-radix` | `b2c731871fc9...` | stable digit buckets | pass/pass/pass | Docker sanity 2/2 modes; local family verified |

The following legacy IDs each have disposition `reject`, their exact before
hash in an individual remedy record, benchmark screen `reject`, and unchanged
source bytes:

`cdeque-audio-jitter`, `cdeque-browser-tabs`,
`cdeque-build-work-items`, `cdeque-card-draw-pile`,
`cdeque-delivery-resequence`, `cdeque-event-replay`,
`cdeque-game-turns`, `cdeque-log-recovery`, `cdeque-meal-orders`,
`cdeque-media-preview`, `cdeque-patient-triage`,
`cdeque-print-priority`, `cdeque-route-detours`,
`cdeque-sensor-calibration`, `cdeque-shuttle-stops`,
`cdeque-support-callbacks`, `cdeque-ticket-escalation`,
`cdeque-tool-rental`, `cdeque-transit-passengers`, and
`cdeque-warehouse-loading`.

Changed owners are the remediation skill, curriculum, this audit, the
circular-deque generator, its artifact-derived semantic normalizer, the
declarative case owner, its focused test, and the prepare/verify wrappers.
Strict C++17 diagnostic compilation and execution passed for all 15 visible
and 15 private binaries. The focused suite reported 26 passes; skill validation
and Python compilation passed. The mandatory network-disabled Docker sanity
receipt records two normal and two fresh ASan/UBSan tests per root with matching host/container tree hashes. It is not claimed as a locked oracle.
