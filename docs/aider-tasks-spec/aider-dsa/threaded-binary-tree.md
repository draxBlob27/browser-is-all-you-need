# Threaded-Binary-Tree Family Remediation Specification

## Scope and immutable inputs

This report controls local remediation of the 20 generated roots under
`.w8-biayn/data/aider-tasks/aider-dsa/threaded-binary-tree/`. That legacy tree
is immutable audit input. The owner is
`src/w8_biayn/integrations/moonlight_threaded_binary_tree_aider_tasks.py`; fresh
artifacts go only under the parallel `aider-tasks-reverify` family root.

The selected workflow is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`, with
`FAMILY_NAME=threaded-binary-tree` and `FAMILY_TYPE=aider-dsa`. Official Aider
C++ `binary-search-tree` is a permanent holdout. No dataset rows, splits,
token/mask evidence, exports, training, or uplift claims are authorized.

## Legacy audit

All 20 legacy roots use one noun-and-verb parameterized template. Their APIs
reduce to positive unique integer insertion/removal, predecessor/lower-bound,
forward/reverse snapshots, and an inclusive range. References and tests
normalize identically. Every deletion collects an ordered vector, destroys the
entire tree, and reinserts survivors instead of locally repairing threads.

### TBT-F1 — semantic template duplication

**Severity:** major

**Scope:** all 20 legacy roots.

**Observed evidence:** `_ROWS` supplies only class/entity/method nouns to the
same `_header`, `_reference`, `_starter`, and `_test` renderers.

**Why it matters:** solving one root transfers mechanically to the other 19.

**Root cause:** curriculum blurbs were not bound to distinct executable
contracts and discriminating private traces.

**Remedy:** repair lexicographically smallest `threaded-appointment-book` in
place; replace every other root with the new ID, API, state, transition rules,
reference fragment, and test trace below.

**Verification after remedy:** require 20 unique logic tags, all 190 family
pairs, prompt/role checks, a negative fixture, and all bound holdout screens.

**Status:** open until generated receipts pass.

### TBT-F2 — deletion avoids the advertised mechanism

**Severity:** major

**Scope:** all 20 legacy roots.

**Observed evidence:** legacy `remove` takes an inorder snapshot, clears the
root, and repeatedly inserts. No local leaf, one-child, two-child, root,
predecessor, or successor repair occurs.

**Why it matters:** final ordering does not prove threaded mutation.

**Root cause:** tests never discriminate local repair from vector rebuilding.

**Remedy:** v2 owns nodes with parent, child/thread pointers, and explicit
markers. Insertion/deletion directly repair adjacent threads. A compilable
`legacy-rebuild-template` fixture must reach `invariant_not_enforced`.

**Verification after remedy:** private tests run a topology/thread audit after
task-specific mutations; owner `--verify-core` rejects the fixture.

**Status:** open until core and runtime evidence pass.

### TBT-F3 — evidence below local completion

**Severity:** moderate

**Scope:** all 20 legacy roots.

**Observed evidence:** the legacy tree had no tree-bound network-disabled
normal/sanitizer receipts, positive discovery comparison, prompt hashes,
complete family screen, or semantic comparison with all 26 official C++
holdouts. The first v2 remediation later produced runtime receipts but
incorrectly treated one shared structural fixture and similarity assertions as
hard-rule evidence.

**Why it matters:** host compilation cannot establish `local_family_verified`.

**Root cause:** the legacy owner predates the deterministic remedy contract.

**Remedy:** create per-root receipts in the pinned sanity image with fresh
normal and ASan/UBSan builds and equal positive test counts.

**Verification after remedy:** receipts bind live trees, references, owner,
Catch, image, compiler, CMake, commands, and network policy.

**Status:** determined only by final receipts.

### TBT-F4 — v2 hard-rule overclaim

**Severity:** major

**Scope:** the v2 screen, focused test, generated negative evidence, and prior
`local_family_verified` report.

**Observed evidence:** the focused test measured clone similarity but never
called the rejecting screen. Its renamed clone scored below the production
threshold. The owner compared one combined profile instead of proving all
seven required dimensions for every unordered pair, and every root reused
`legacy-rebuild-template` instead of executing a topic-specific false
implementation.

**Why it matters:** those artifacts did not satisfy the skill's hard diversity
rule, regardless of passing reference builds.

**Remedy:** v3 derives a seven-dimension matrix from emitted artifacts, checks
all 190 unordered pairs, and makes any equal required dimension fail closed.
Focused tests inject domain/identifier-renamed, constants-or-policy-only, and
opposite-end-selection clones into the real screen. Each root emits a distinct
private false implementation that must strictly compile and then fail the
same two executed tests.

**Status:** the v2 hard-rule claim is withdrawn. V3 remains
`pending_execution` until fresh Docker evidence imports successfully.

## Remediated inventory and dispositions

| Legacy root | Disposition | Remediated root | Independent primary logic |
| --- | --- | --- | --- |
| `threaded-appointment-book` | repair-in-place | `threaded-appointment-book` | direct double-threaded mutation |
| `threaded-auction-bids` | replace | `threaded-bid-multiplicity-index` | per-level multiplicity nodes |
| `threaded-audit-browser` | replace | `threaded-audit-tombstone-index` | lazy tombstones and compaction |
| `threaded-calendar-navigator` | replace | `threaded-calendar-cursor` | cursor with delete fallback |
| `threaded-cargo-manifest` | replace | `threaded-cargo-interval-tree` | interval overlap scan |
| `threaded-document-anchors` | replace | `threaded-anchor-rank-tree` | rank and select walk |
| `threaded-fare-tiers` | replace | `threaded-fare-prefix-tree` | prefix aggregate selection |
| `threaded-file-version-browser` | replace | `threaded-version-access-index` | access counts and tie scan |
| `threaded-flight-departures` | replace | `threaded-departure-day-index` | gate-filtered time scan |
| `threaded-inventory-catalog` | replace | `threaded-catalog-stock-index` | stock transitions and filtered successor |
| `threaded-library-shelves` | replace | `threaded-shelf-bulk-builder` | balanced bulk build and overlay |
| `threaded-medication-times` | replace | `threaded-dose-range-pruner` | successor-driven range erasure |
| `threaded-museum-waypoints` | replace | `threaded-waypoint-split-tree` | pivot partition and side erasure |
| `threaded-network-ports` | replace | `threaded-port-gap-tree` | gap and run detection |
| `threaded-parking-space-guide` | replace | `threaded-space-state-tree` | payload-filtered free scan |
| `threaded-route-stations` | replace | `threaded-station-rekey-tree` | atomic key replacement |
| `threaded-score-history` | replace | `threaded-score-thread-auditor` | independent thread audit/repair |
| `threaded-sensor-thresholds` | replace | `threaded-threshold-hysteresis-tree` | stateful hysteresis transition |
| `threaded-ticket-browser` | replace | `threaded-ticket-priority-tree` | composite priority and rekey |
| `threaded-transit-service` | replace | `threaded-service-wrap-tree` | cyclic boundary view |

Per-legacy-root JSON records and exact twelve-section Markdown contracts live
under the sibling `.state/remedy/` directory and bind legacy hashes captured
before owner changes plus the pre-change owner hash.

## Structural, prompt, and core contract

Each root declares two slug-named editable files and two suffix-mapped private
references. Prompts contain only docs and editable starters. Tests, references,
metadata, CMake, support, provenance, and receipts remain private. References
own heap nodes, distinguish children from threads, maintain parent relations,
and support independent child-edge auditing. Associative/list containers,
authoritative sorted vectors, hard-coded traces, unthreaded trees, and
clear-and-reinsert single-key deletion are forbidden.

## Family and benchmark screen

Normalizer `aider-threaded-tree-artifact-semantics-v3` derives seven hashes
from actual emitted docs, public API, owned state/algorithm,
mutation/selection rules, invalid/boundary behavior, task-specific reference
control flow, deterministic visible/private oracle, and topic-specific false
implementation. Every one of the 190 unordered pairs must differ in all seven
dimensions, and normalized primary-artifact containment must remain below
`0.98`. False implementations are excluded from aggregate similarity so they
cannot manufacture diversity. The owner also executes the three required
emitted clone controls and compares each root with every available bound
official C++ holdout. Missing holdout content is `not_completed`, never pass.
Whole-slug, semantic holdout, equal-dimension, aggregate-duplicate, or surviving
adversarial-clone findings fail closed.

## Acceptance and strongest conclusion

```bash
uv run pytest -q tests/test_moonlight_threaded_binary_tree_aider_tasks.py
bash examples/slime/moonlight_cpp_perf/prepare_threaded_binary_tree_aider_tasks.sh --force --verify-core --verify
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

Final normal, fresh sanitizer, and false-implementation runs must use the pinned
`w8-biayn-polyglot-cpp` digest with `--network none`, discovering two positive
CTest entries per root per mode with exact equal counts. Every topic-specific
false implementation must compile under the same strict flags, discover those
same tests, execute, and return nonzero because the tests reject it.
`local_family_verified` is forbidden until prompt, roles, core, all three clone
controls, all 190 seven-dimension pair checks, all twenty executed negative
fixtures, all-26 holdouts, normal, and sanitizer gates pass. This is local
candidate evidence.

## Final re-verification evidence

The earlier 2026-07-18 v2 conclusion and generator hash are invalidated by
TBT-F4 and are not hard-rule evidence.

The v2 owner regenerated the complete sibling family with generator content
hash `sha256:c13a475d3441a0f78771019b4876b54ef14db01dd3d4d6f1fc7a605e103bc86c`.
Every per-legacy-root remedy record under `.state/remedy/` binds its exact
before tree hash, disposition, remediated ID, exact after tree hash, changed
owner paths, prompt/role result, family and benchmark result, oracle receipt,
and discovered counts. The inventory table above accounts for one
`repair-in-place` and 19 replacements.

The required run uses network-disabled
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
GCC 13.4.0, CMake/CTest 3.25.1, explicit Unix Makefiles, and separate fresh
normal and ASan/UBSan directories. Those normal/sanitizer results remain
historical diagnostics, but the prompt/role result, shared
`legacy-rebuild-template` rejection, and aggregate 190-pair result do not
establish v3 hard-rule compliance. The old `0.72` threshold and strongest-pair
claim are superseded.

The corrected v3 owner then regenerated the complete sibling family with
generator content hash
`sha256:389287cd0369bb42c7c5668030e92458ab0f3a07bd694e8cf93d0c431d2e795c`.
The real screen rejected the domain/identifier-renamed,
constants-or-policy-only, and opposite-end-selection emitted clones through
`duplicate_family`. It compared all 190 unordered pairs across all seven
required dimensions; every pair differed in every dimension. The strongest
primary-artifact pair was `threaded-audit-tombstone-index` /
`threaded-space-state-tree` at `0.907407`, below the fail-closed `0.98`
containment threshold. All 26 bound official C++ holdouts were available and
passed the whole-slug and semantic screens.

The fresh pinned network-disabled Docker run used GCC 13.4.0 and CMake/CTest
3.25.1. It discovered and passed 40 normal and 40 fresh ASan/UBSan tests.
Twenty distinct topic-specific false implementations compiled under the same
strict flags, each discovered its root's same two tests, and all twenty were
rejected by executed CTest runs (40 negative test entries total). A second
host-side audit matched every live generated-tree hash to its per-root receipt,
materialization manifest, and remedy record; matched every current legacy tree
hash to its frozen before hash; and confirmed twenty verified remedy records.
The evidence class is `docker_sanity`, not `locked_oracle`, and the strongest
truthful status for all twenty roots is `local_family_verified`.

Changed owner paths are the materializer, its independent case registry, the
focused pytest, remedy planner, curriculum, this specification,
materialization guide, and preparation wrapper. Generated tasks, remedy
ledgers, screen receipts, oracle receipts, and manifest remain ignored under
the re-verification root. The legacy family was reused only as immutable audit
input.
